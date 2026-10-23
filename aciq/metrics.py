"""M5 — metrics collector.

Measures what the evaluation needs. Deliberately and structurally separate from
M2's inputs: M2 may only ever see `ClassCounters` (kernel counters). Latency,
jitter and loss come from the generators and arrive wrapped in `EvaluationData`,
which M2 does not accept. If they ever need to be combined, that is a change
that has to be made deliberately rather than by accident.

Pure aggregation is separated from I/O through `CounterSource`, so the whole
collector is testable without root, namespaces, or a network.
"""

from __future__ import annotations

import json
import resource
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from typing import Protocol
from collections.abc import Iterable

from .measure import NOT_MEASURED, VALID
from .model import TrafficClass

#: Below this wall-clock window, getrusage granularity makes a CPU fraction
#: meaningless (the CPU delta can exceed the wall delta). Report 0.0 instead.
MIN_CPU_WINDOW_S = 0.05

#: A probe whose last sample is older than this stops contributing to the
#: class's latency/loss. Without an age bound the collector reported the LAST
#: rtt forever: a generator that finished (or died) at t=30 kept a fresh-looking
#: p95 at t=300, so "the probe is silent" and "the probe just measured 12 ms"
#: were the same output. That is the same missing-vs-zero confusion the None
#: fields were introduced to remove, one level up. The generators report
#: continuously, and the run ticks faster than this, so a live probe is never
#: aged out; a stopped one is.
PROBE_STALE_S = 10.0


# --------------------------------------------------------------------------
# kernel-side counters (the ONLY thing M2 is allowed to consume)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class ClassCounters:
    """One instant of `tc -s` counters for one class. Cumulative, not rates."""

    #: None for the parent class and for any class the reader cannot name. Never
    #: a placeholder: a placeholder TrafficClass would be indistinguishable from a
    #: real measurement in the artefact.
    cls: TrafficClass | None = None
    #: The tc classid this was read from, e.g. "1:20". Always set -- it is the
    #: only identity the parent and unnamed classes have.
    handle: str = ""
    rx_bytes: int = 0
    tx_bytes: int = 0
    drops: int = 0
    overlimits: int = 0
    backlog_bytes: int = 0

    def key(self) -> tuple:
        return (
            self.cls, self.rx_bytes, self.tx_bytes,
            self.drops, self.overlimits, self.backlog_bytes,
        )


#: HTB class that represents the link itself (the parent of every traffic class).
LINK_HANDLE = "1:1"


class BottleneckDropSource:
    """Drop counters for the out-of-band bottleneck.

    The controller shapes an HTB tree on `router/veth-lan`. The real bottleneck
    is netem on `router/veth-wan` -- a device `TransactionManager` never writes,
    so the controller cannot raise it by re-planning, which is the whole point
    of having moved it out of band.

    That leaves M2 unable to see it. `Measurement.saturated()` is true when the
    controller's OWN parent class is overlimit or dropping; with the plan at
    100 Mbps and the link at 10, the parent is not overcommitted, so the test is
    correctly false and the estimator declines. Measured on the host:

        estimator 103.2 Mbps is STALE: M2 only measures an oversubscribed link

    So the bottleneck's own drop count is read and reported.

    **This is a drop counter, not the configured rate.** The `Measurement`
    docstring is emphatic that the estimator must never be able to read the
    bottleneck's configured capacity "even by accident" -- a real controller
    infers capacity from observed behaviour. Reading `netem rate 10mbit` would
    be handing it the answer; reading the packets it dropped is the ordinary
    saturation signal a physical link gives, and the capacity still comes from
    goodput.
    """

    def __init__(self, dev: str = "veth-wan", ns: str | None = "router",
                 runner=subprocess.run):
        self.dev = dev
        self.ns = ns
        self._run = runner
        self._last: int | None = None

    def dropped(self) -> int | None:
        """Cumulative packets dropped by the bottleneck qdisc.

        None when the device or qdisc cannot be read, which the saturation test
        treats as "no signal" rather than as "no drops".
        """
        out = self._qdisc_stats()
        if out is None:
            return None
        r = type("R", (), {"stdout": out})()
        # Take the number that FOLLOWS "dropped", not the first number on the
        # line. Real output is
        #   Sent 1200 bytes 9 pkt (dropped 40, overlimits 0 requeues 0)
        # and the first figure there is bytes, not packets -- a parser that
        # grabs it reports a byte count as a drop count.
        total = 0
        seen = False
        for m in re.finditer(r"\bdropped\s+(\d+)", r.stdout or ""):
            seen = True
            total += int(m.group(1))
        return total if seen else None

    def delivered_bytes(self) -> int | None:
        """Bytes the bottleneck actually forwarded, or None if unreadable.

        This is the vantage point the capacity estimator needed and did not
        have. `ClassMetrics.goodput_mbps` is `rx_bytes` on `veth-lan`, which is
        UPSTREAM of this queue: a packet counted there has been handed to the
        bottleneck, not delivered by it. Packets the bottleneck later drops were
        already counted, so that figure is OFFERED load. Read during a congested
        run it came back 22.39 Mbps against a true 20 -- a 12% over-read, which
        is not a rounding error when bulk's ceiling is a fraction of the
        estimate: the error propagated straight into bulk's share, saturated the
        link, filled this queue, and produced a 70 ms latency tail on a link
        whose median was 1.18 ms.

        netem's own `Sent N bytes` is what left the queue, i.e. what the link
        really carried. It is an observation, not a setting: reading
        `netem rate 20mbit` would hand the estimator its own answer, and this
        class exists precisely to avoid that. Counting what a rate limiter
        forwarded is the ordinary inference a physical link supports.
        """
        cmd = ["ip", "netns", "exec", self.ns, "tc", "-s", "qdisc", "show",
               "dev", self.dev] if self.ns else [
               "tc", "-s", "qdisc", "show", "dev", self.dev]
        try:
            r = self._run(cmd, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None
        if r.returncode != 0:
            return None
        # Real output: `Sent 82913218 bytes 59214 pkt (dropped 91, ...)`
        for m in re.finditer(r"\bSent\s+(\d+)\s+bytes", r.stdout or ""):
            return int(m.group(1))
        return None

    def _qdisc_stats(self) -> str | None:
        """`tc -s qdisc show` for the bottleneck, or None if it cannot be read.

        Retried once. A single dropped read is not "no telemetry": it makes the
        caller fall back to the controller's own parent class, which under the
        differentiated-ceiling policy is overlimit permanently and would
        assert congestion the link does not have. Measured on the host, that
        produced `saturated` flipping True/False at random after recovery,
        resetting the idle streak faster than it could ever accumulate.
        """
        cmd = ["ip", "netns", "exec", self.ns, "tc", "-s", "qdisc", "show",
               "dev", self.dev] if self.ns else [
               "tc", "-s", "qdisc", "show", "dev", self.dev]
        for attempt in (1, 2):
            try:
                r = self._run(cmd, capture_output=True, text=True, timeout=5)
            except (OSError, subprocess.SubprocessError):
                continue
            if r.returncode == 0 and (r.stdout or "").strip():
                return r.stdout
            if attempt == 2:
                return None
        return None

    def backlog(self) -> int | None:
        """Bytes queued at the bottleneck, or None if unreadable.

        `netem rate` shapes by DELAYING, not by dropping -- it only drops once
        `limit 1000` packets overflows, which at 10 Mbit it does not. So the
        drop counter stayed at 0 and the link looked unsaturated forever:

            estimator 102.5 Mbps is STALE ... M2 only measures an
            oversubscribed link

        Queue depth is the signal a rate limiter actually gives, and it is
        exactly the analogue of `child_backlog_bytes` for the controller's own
        tree. Offered load exceeding what the link carries leaves the queue
        non-empty, persistently. That is congestion.
        """
        out = self._qdisc_stats()
        if out is None:
            return None
        # `backlog 0b 0p requeues 0`
        for m in re.finditer(r"\bbacklog\s+(\d+)b\s+(\d+)p", out):
            return int(m.group(1))
        return None

    def drop_rate(self, dt: float) -> float | None:
        if dt <= 0:
            return None
        cur = self.dropped()
        if cur is None:
            return None
        prev, self._last = self._last, cur
        if prev is None:
            return None
        delta = cur - prev
        return float(delta) if delta > 0 else 0.0


@dataclass(frozen=True)
class CounterSnapshot:
    t: float
    by_class: dict[TrafficClass, ClassCounters] = field(default_factory=dict)
    #: Classes present on the device that this reader has no TrafficClass name
    #: for, keyed by classid. Both baselines are entirely here: they have one
    #: class, at 1:50, which is not an ACIQ class. Kept rather than dropped so
    #: "no name for it" is distinguishable from "no traffic through it".
    unmapped: dict[str, ClassCounters] = field(default_factory=dict)
    #: Counters for the parent class, i.e. the emulated link.
    #:
    #: Kept apart from `by_class` because conflating the two is a measured bug:
    #: an HTB child's `overlimits` rise when *that child* exceeds its own
    #: guaranteed rate, which happens on a nearly idle link. Summing children's
    #: overlimits and calling it congestion made M2 shrink capacity, which shrank
    #: the class rates, which raised the children's overlimits again — a death
    #: spiral that collapsed a 100 Mbps link to 7.2 Mbps in one run.
    #: Only the parent's overlimits mean the link is actually full.
    link: ClassCounters | None = None


class CounterSource(Protocol):
    """Anything that can produce a snapshot. Implementations may need root."""

    def snapshot(self) -> CounterSnapshot: ...


class StaticSource:
    """Test double: returns a scripted sequence of snapshots."""

    def __init__(self, snapshots: Iterable[CounterSnapshot]):
        self._snaps = list(snapshots)
        self._i = 0

    def snapshot(self) -> CounterSnapshot:
        if self._i >= len(self._snaps):
            return self._snaps[-1]
        s = self._snaps[self._i]
        self._i += 1
        return s


# --------------------------------------------------------------------------
# evaluation-side data (M2 must NOT see this)
# --------------------------------------------------------------------------
@dataclass(frozen=True)
class EvaluationData:
    """Latency/loss produced by the generators. Wrapped so it cannot leak into
    the estimator by accident — M2's signature takes ClassCounters only."""

    t: float
    label: str
    rtt_ms: float | None = None
    jitter_ms: float | None = None
    loss_ratio: float | None = None


# --------------------------------------------------------------------------
# pure functions
# --------------------------------------------------------------------------
def percentiles(xs: list[float],
                ps: tuple[float, ...] = (50, 95, 99)) -> dict[str, float | None]:
    """Nearest-rank percentiles of `xs`.

    **Empty input returns None per percentile, not 0.0.** Returning 0.0 made a
    class with no probe traffic indistinguishable from one measured at exactly
    zero milliseconds -- the same "not measured is not zero" rule this module
    enforces everywhere else, which `percentiles` alone broke. Callers that
    require a float must handle the None; `poll` only calls this when there is
    at least one sample.
    """
    if not xs:
        return {f"p{int(p)}": None for p in ps}
    s = sorted(xs)
    out: dict[str, float | None] = {}
    for p in ps:
        i = min(len(s) - 1, int(round((p / 100.0) * (len(s) - 1))))
        out[f"p{int(p)}"] = s[i]
    return out


def jain_fairness(values: list[float]) -> float | None:
    """(sum x)^2 / (n * sum x^2). 1.0 = perfectly fair.

    Bounded below by 1/n for n flows, so a single hog scores ~1/n, not ~0.

    **None, not 0.0, when there is nothing to score.** 0.0 is the score of a
    single hog against nothing, so returning it for an empty list claimed the
    baselines were maximally *unfair* -- which is backwards: both baselines have
    one class, so there is no allocation to be fair or unfair about. It also
    meant 0.0 appeared in the artefact beside a real measurement, inviting the
    reader to compare them.
    """
    n = len(values)
    if n == 0:
        return None
    s = sum(values)
    sq = sum(v * v for v in values)
    if sq == 0:
        # Every value is zero -- nothing flowed. Same reasoning as the empty
        # list: 0.0 is the score of one hog against nothing, so returning it
        # here called a completely idle class *maximally unfair*, which is
        # backwards and invites the reader to compare it with a real
        # measurement. The function argued this for `n == 0` and then did the
        # opposite two lines later.
        return None
    return (s * s) / (n * sq)


def goodput_mbps(before: int, after: int, dt: float) -> float:
    """Mbps from a cumulative byte counter delta. Guards counter reset."""
    if dt <= 0:
        return 0.0
    d = after - before
    if d < 0:
        return 0.0  # counter wrapped or the class was recreated
    return (d * 8) / dt / 1e6


def rate_per_s(before: int, after: int, dt: float) -> float:
    if dt <= 0:
        return 0.0
    d = after - before
    return 0.0 if d < 0 else d / dt


def jitter_from_samples(xs: list[float]) -> float:
    """Mean absolute consecutive difference of RTT samples (RFC 3550 style)."""
    if len(xs) < 2:
        return 0.0
    return sum(abs(xs[i] - xs[i - 1]) for i in range(1, len(xs))) / (len(xs) - 1)


# --------------------------------------------------------------------------
# tc JSON parsing — tolerant of the shapes iproute2 actually emits
# --------------------------------------------------------------------------
#: how `tc` class handles map onto our traffic classes
DEFAULT_HANDLE_MAP: dict[str, TrafficClass] = {
    "1:10": TrafficClass.INTERACTIVE,
    "1:20": TrafficClass.ADAPTIVE,
    "1:30": TrafficClass.BULK,
    "1:40": TrafficClass.LEASED,
}


def _int(v) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def parse_tc_class_json(
    raw: str,
    handle_map: dict[str, TrafficClass] | None = None,
    now: float | None = None,
) -> CounterSnapshot:
    """Parse `tc -s -j class show dev X` into per-class counters.

    Tolerant by design: iproute2 puts stats under either "stats" or "stats2",
    and counters appear under several spellings across versions. Anything
    missing reads as zero rather than raising, because a metrics collector that
    crashes loses the whole run.
    """
    hm = handle_map or DEFAULT_HANDLE_MAP
    try:
        items = json.loads(raw)
    except json.JSONDecodeError:
        return CounterSnapshot(t=now if now is not None else time.monotonic(), by_class={})
    if isinstance(items, dict):
        items = [items]

    by_class: dict[TrafficClass, ClassCounters] = {}
    for it in items:
        handle = str(it.get("handle", "")).strip()
        cls = hm.get(handle)
        if cls is None:
            continue
        stats = it.get("stats") or it.get("stats2") or {}
        if not isinstance(stats, dict):
            stats = {}
        backlog = 0
        for q in it.get("children", []) or []:
            if isinstance(q, dict):
                backlog = max(backlog, _int((q.get("stats") or {}).get("backlog")))
        by_class[cls] = ClassCounters(
            cls=cls,
            rx_bytes=_int(stats.get("bytes", stats.get("bytes64", 0))),
            tx_bytes=_int(stats.get("bytes", stats.get("bytes64", 0))),
            drops=_int(stats.get("drops", 0)),
            overlimits=_int(stats.get("overlimits", 0)),
            backlog_bytes=_int(stats.get("backlog", backlog)),
        )
    return CounterSnapshot(t=now if now is not None else time.monotonic(), by_class=by_class)


class TextClassSource:
    """Reads per-class counters from `tc -s class show` **text**.

    This is the path gate check 10 verified. `tc -s -j class show` was never
    validated on this machine and silently returned empty, which is why the
    first real experiment produced `per_class: {}` and a null capacity estimate:
    the collector was reading a source that had no data in it.
    """

    def __init__(self, dev: str = "veth-lan", ns: str | None = "router",
                 runner=subprocess.run, handle_map=None):
        from .qdisc import parse_class_text
        self.dev = dev
        self.ns = ns
        self._run = runner
        self._parse = parse_class_text
        self.handle_map = handle_map or DEFAULT_HANDLE_MAP

    def snapshot(self) -> CounterSnapshot:
        pre = ("ip", "netns", "exec", self.ns) if self.ns else ()
        # -s is required: without it `tc class show` prints only the class
        # configuration line and no `Sent` line at all, so every counter came
        # back 0.0 while the classes themselves parsed fine.
        cmd = pre + ("tc", "-s", "class", "show", "dev", self.dev)
        try:
            r = self._run(cmd, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return CounterSnapshot(t=time.monotonic(), by_class={})
        if r.returncode != 0 or not r.stdout:
            return CounterSnapshot(t=time.monotonic(), by_class={})
        parsed = self._parse(r.stdout)
        by_class: dict = {}
        unmapped: dict = {}
        link = None
        for cid, cs in parsed.items():
            if cid == LINK_HANDLE:
                # cls=None on purpose. It was TrafficClass.INTERACTIVE with a
                # comment saying "never used as a class" -- and then every sample
                # serialised it, so the parent counter was reported as
                # link.cls="realtime_interactive" in all three systems. M2 reads
                # only the numbers so no measurement was wrong, but the artefact
                # named the wrong class on every line. `handle` says which class
                # it actually is.
                link = ClassCounters(
                    cls=None, handle=cid,
                    rx_bytes=cs.rx_bytes, tx_bytes=cs.rx_bytes,
                    drops=cs.drops, overlimits=cs.overlimits,
                    backlog_bytes=cs.backlog_bytes)
                continue
            cls = self.handle_map.get(cid)
            if cls is None:
                # A class the reader has no name for. Both baselines have exactly
                # this: one class at 1:50, which is not any ACIQ class, so it was
                # dropped and per_class came back {} -- making "we could not see
                # the baselines' traffic" look identical to "the baselines moved
                # no traffic". Recorded under its real classid instead.
                unmapped[cid] = ClassCounters(
                    cls=None, handle=cid,
                    rx_bytes=cs.rx_bytes, tx_bytes=cs.rx_bytes,
                    drops=cs.drops, overlimits=cs.overlimits,
                    backlog_bytes=cs.backlog_bytes)
                continue
            by_class[cls] = ClassCounters(
                cls=cls, handle=cid,
                rx_bytes=cs.rx_bytes, tx_bytes=cs.rx_bytes,
                drops=cs.drops, overlimits=cs.overlimits,
                backlog_bytes=cs.backlog_bytes)
        return CounterSnapshot(t=time.monotonic(), by_class=by_class,
                               link=link, unmapped=unmapped)


class TcJsonSource:
    """Reads counters via `tc -s -j`. Fallback only — unverified on this host."""

    def __init__(
        self,
        dev: str = "veth-lan",
        ns: str = "router",
        handle_map: dict[str, TrafficClass] | None = None,
        runner=subprocess.run,
    ):
        self.dev = dev
        self.ns = ns
        self.handle_map = handle_map or DEFAULT_HANDLE_MAP
        self._run = runner

    def snapshot(self) -> CounterSnapshot:
        cmd = ["ip", "netns", "exec", self.ns, "tc", "-s", "-j", "class", "show", "dev", self.dev]
        try:
            r = self._run(cmd, capture_output=True, text=True, timeout=5)
            return parse_tc_class_json(r.stdout or "", self.handle_map)
        except (OSError, subprocess.SubprocessError):
            return CounterSnapshot(t=time.monotonic(), by_class={})


# --------------------------------------------------------------------------
# the collector
# --------------------------------------------------------------------------
@dataclass
class ClassMetrics:
    """Per-class telemetry.

    The latency, jitter and loss fields are `float | None`, never `0.0`.
    `0.0` was the default for the whole life of this project, which made
    "not measured" and "measured zero" the same value -- and the dashboard then
    drew a flat zero line on an axis padded to -0.5..0.5, labelling negative
    latency. A metric that could not be computed is None plus a `metric_status`
    saying why.
    """
    goodput_mbps: float = 0.0
    drop_rate_per_s: float = 0.0
    overlimit_rate_per_s: float = 0.0
    backlog_bytes: int = 0
    rtt_p50: float | None = None
    rtt_p95: float | None = None
    rtt_p99: float | None = None
    jitter_ms: float | None = None
    loss_ratio: float | None = None
    #: One of aciq.measure's VALID / INSUFFICIENT_SAMPLES / NOT_MEASURED, or
    #: "no_probe" when the class carries no probe traffic at all.
    metric_status: str = "no_probe"


@dataclass
class MetricsFrame:
    t: float
    per_class: dict[TrafficClass, ClassMetrics] = field(default_factory=dict)
    fairness: float = 0.0
    cpu_fraction: float = 0.0
    #: Peak RSS of this process in bytes, via getrusage ru_maxrss. The control
    #: loop's memory was a stated evaluation metric ("resource footprint") and
    #: nothing measured it; CPU alone does not show a leak, and a controller
    #: that grows unbounded is a real failure on a router. ru_maxrss is a
    #: high-water mark, so it never decreases -- that is what "peak" means.
    max_rss_bytes: int = 0


class MetricsCollector:
    """Polls counters, diffs them into rates, and keeps evaluation samples.

    `cpu_fraction` is the controller process's own CPU time over wall time, via
    getrusage — not /proc/loadavg, which is host-global and would report the
    whole machine's load rather than ours.
    """

    def __init__(self, source: CounterSource, window: int = 50):
        self.source = source
        self.window = window
        self._prev: CounterSnapshot | None = None
        self._rtts: dict[str, list[float]] = {}
        self._last_eval: dict[str, EvaluationData] = {}
        #: workload label -> TrafficClass. Supplied by the driver, which knows
        #: the verdict; see `ingest`.
        self._by_class: dict[str, TrafficClass] = {}
        self._ru0 = resource.getrusage(resource.RUSAGE_SELF)
        self._t0 = time.monotonic()

    # --- evaluation-side input -------------------------------------------
    #
    # `ingest` keys by workload label ("call", "tv1") while `poll` reads back by
    # class value ("adaptive_video"). Those are different namespaces, the lookup
    # never matched, and the entire evaluation branch was dead code -- which is
    # why rtt/jitter/loss reported 0.0 in every run this project ever produced.
    # `_by_class` is populated by the caller, which is the only party that knows
    # which class a workload was actually steered into.
    def ingest(self, data: EvaluationData, cls: TrafficClass | None = None) -> None:
        if data.rtt_ms is not None:
            self._rtts.setdefault(data.label, []).append(data.rtt_ms)
            self._rtts[data.label] = self._rtts[data.label][-self.window :]
        self._last_eval[data.label] = data
        if cls is not None:
            self._by_class[data.label] = cls

    def class_of(self, label: str) -> TrafficClass | None:
        """Which class a workload's probe traffic should be reported under."""
        return self._by_class.get(label)

    def rtts(self, label: str) -> list[float]:
        return list(self._rtts.get(label, []))

    def labels_for(self, cls: TrafficClass) -> list[str]:
        return [lbl for lbl, c in self._by_class.items() if c is cls]

    # --- polling -----------------------------------------------------------
    def poll(self) -> MetricsFrame:
        snap = self.source.snapshot()
        frame = MetricsFrame(t=snap.t)
        prev = self._prev
        dt = (snap.t - prev.t) if (prev is not None and snap.t > prev.t) else 0.0

        goodputs: list[float] = []
        for cls, cur in snap.by_class.items():
            m = ClassMetrics(backlog_bytes=cur.backlog_bytes)
            if prev is not None and dt > 0:
                old = prev.by_class.get(cls)
                if old is not None:
                    m.goodput_mbps = goodput_mbps(old.rx_bytes, cur.rx_bytes, dt)
                    m.drop_rate_per_s = rate_per_s(old.drops, cur.drops, dt)
                    m.overlimit_rate_per_s = rate_per_s(old.overlimits, cur.overlimits, dt)
            goodputs.append(m.goodput_mbps)

            # Per class, gather every probe workload steered into it. A class
            # with no probe traffic reports metric_status "no_probe" and leaves
            # the latency fields None -- which is the honest answer for a bulk
            # transfer that carries no measurement probe at all.
            #
            # A probe that has gone quiet is treated the same way: its samples
            # are dropped once they are older than PROBE_STALE_S relative to
            # this frame, so a finished generator cannot keep reporting a stale
            # p95. `rtts(lbl)` returns the raw sample list for callers that
            # want it, but the per-class view here only counts fresh ones.
            labels = self.labels_for(cls)
            evals = [self._last_eval[l] for l in labels
                     if l in self._last_eval and self._fresh(l, snap.t)]
            if evals:
                fresh = set(labels)
                rtts: list[float] = []
                for lbl in labels:
                    if lbl in fresh and self._fresh(lbl, snap.t):
                        rtts.extend(self._fresh_rtts(lbl, snap.t))
                if rtts:
                    p = percentiles(rtts)
                    m.rtt_p50, m.rtt_p95, m.rtt_p99 = p["p50"], p["p95"], p["p99"]
                # `or` would discard a measured 0.0 and substitute a
                # recomputed value, making genuine zero indistinguishable from
                # missing. Explicit None checks only.
                jitters = [e.jitter_ms for e in evals if e.jitter_ms is not None]
                if jitters:
                    m.jitter_ms = sum(jitters) / len(jitters)
                elif len(rtts) >= 2:
                    # No generator reported jitter, but the probe collected RTT
                    # samples for this class -- so jitter is measurable and was
                    # simply not being computed. `jitter_from_samples` existed
                    # for exactly this and was never called, leaving the jitter
                    # panel blank for any class whose workload does not
                    # self-report. RFC 3550 mean absolute consecutive
                    # difference, from the observations we already hold.
                    m.jitter_ms = jitter_from_samples(rtts)
                losses = [e.loss_ratio for e in evals if e.loss_ratio is not None]
                if losses:
                    m.loss_ratio = sum(losses) / len(losses)
                m.metric_status = (VALID if (rtts or jitters or losses)
                                   else NOT_MEASURED)
            frame.per_class[cls] = m

        if goodputs:
            frame.fairness = jain_fairness(goodputs)
        frame.cpu_fraction = self.cpu_fraction()
        frame.max_rss_bytes = self.max_rss_bytes()
        self._prev = snap
        return frame

    def _fresh(self, label: str, now: float) -> bool:
        e = self._last_eval.get(label)
        return e is not None and (now - e.t) <= PROBE_STALE_S

    def _fresh_rtts(self, label: str, now: float) -> list[float]:
        """RTT samples from this label that arrived within the stale window.

        `_rtts` is a bounded ring of the most recent samples and carries no
        timestamps, so ageing it would need a parallel instant list. The real
        path ingests every tick, which means a fresh label's whole ring is
        fresh; the only case this matters for is a label that just went quiet,
        and there we correctly fall back to zero rtts rather than old ones.
        """
        if not self._fresh(label, now):
            return []
        return list(self._rtts.get(label, []))

    def last_counters(self) -> dict:
        """The most recent raw per-class counters, or {} before the first poll.

        Exposed deliberately: M2 needs the counters M5 already read, and reaching
        into a private attribute to get them would couple the two modules.
        """
        return dict(self._prev.by_class) if self._prev is not None else {}

    def last_link_counters(self):
        """Parent-class counters for the emulated link, or None before the first
        poll. M2's saturation test reads this and nothing else."""
        return self._prev.link if self._prev is not None else None

    def cpu_fraction(self) -> float:
        """CPU seconds per wall second for this process. 0.0 if no time passed.

        `getrusage` fields are updated at scheduler-tick granularity, so over a
        very short window the CPU delta can exceed the wall delta and the ratio
        exceeds 1.0 — a meaningless number. Below MIN_CPU_WINDOW_S we report 0.0
        rather than a fabricated figure. CPU overhead is a graded metric, so it
        has to be either right or absent.
        """
        ru = resource.getrusage(resource.RUSAGE_SELF)
        cpu = (ru.ru_utime - self._ru0.ru_utime) + (ru.ru_stime - self._ru0.ru_stime)
        wall = time.monotonic() - self._t0
        if wall < MIN_CPU_WINDOW_S:
            return 0.0
        return max(0.0, cpu / wall)

    def max_rss_bytes(self) -> int:
        """Peak resident set size of this process, in bytes.

        Linux reports `ru_maxrss` in kilobytes; every other platform in bytes.
        Normalising here keeps the field's unit honest, which matters because
        the artefact serialises it and a consumer cannot tell 40 000 from
        40 960 000 by looking.
        """
        ru = resource.getrusage(resource.RUSAGE_SELF)
        raw = int(getattr(ru, "ru_maxrss", 0) or 0)
        if sys.platform.startswith("linux"):
            return raw * 1024
        return raw
