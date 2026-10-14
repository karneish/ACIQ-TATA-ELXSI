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
import os
import resource
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Iterable, Protocol

from .measure import NOT_MEASURED, VALID
from .model import TrafficClass

#: Below this wall-clock window, getrusage granularity makes a CPU fraction
#: meaningless (the CPU delta can exceed the wall delta). Report 0.0 instead.
MIN_CPU_WINDOW_S = 0.05


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
        cmd = ["ip", "netns", "exec", self.ns, "tc", "-s", "qdisc", "show",
               "dev", self.dev] if self.ns else [
               "tc", "-s", "qdisc", "show", "dev", self.dev]
        try:
            r = self._run(cmd, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None
        if r.returncode != 0:
            return None
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
        cmd = ["ip", "netns", "exec", self.ns, "tc", "-s", "qdisc", "show",
               "dev", self.dev] if self.ns else [
               "tc", "-s", "qdisc", "show", "dev", self.dev]
        try:
            r = self._run(cmd, capture_output=True, text=True, timeout=5)
        except (OSError, subprocess.SubprocessError):
            return None
        if r.returncode != 0:
            return None
        # `backlog 0b 0p requeues 0`
        for m in re.finditer(r"\bbacklog\s+(\d+)b\s+(\d+)p", r.stdout or ""):
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
    link: "ClassCounters | None" = None


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
def percentiles(xs: list[float], ps: tuple[float, ...] = (50, 95, 99)) -> dict[str, float]:
    if not xs:
        return {f"p{int(p)}": 0.0 for p in ps}
    s = sorted(xs)
    out = {}
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
        return 0.0
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
            labels = self.labels_for(cls)
            evals = [self._last_eval[l] for l in labels
                     if l in self._last_eval]
            if evals:
                rtts: list[float] = []
                for lbl in labels:
                    rtts.extend(self.rtts(lbl))
                if rtts:
                    p = percentiles(rtts)
                    m.rtt_p50, m.rtt_p95, m.rtt_p99 = p["p50"], p["p95"], p["p99"]
                # `or` would discard a measured 0.0 and substitute a
                # recomputed value, making genuine zero indistinguishable from
                # missing. Explicit None checks only.
                jitters = [e.jitter_ms for e in evals if e.jitter_ms is not None]
                if jitters:
                    m.jitter_ms = sum(jitters) / len(jitters)
                losses = [e.loss_ratio for e in evals if e.loss_ratio is not None]
                if losses:
                    m.loss_ratio = sum(losses) / len(losses)
                m.metric_status = (VALID if (rtts or jitters or losses)
                                   else NOT_MEASURED)
            frame.per_class[cls] = m

        if goodputs:
            frame.fairness = jain_fairness(goodputs)
        frame.cpu_fraction = self.cpu_fraction()
        self._prev = snap
        return frame

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
