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
import subprocess
import time
from dataclasses import dataclass, field
from typing import Iterable, Protocol

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
    goodput_mbps: float = 0.0
    drop_rate_per_s: float = 0.0
    overlimit_rate_per_s: float = 0.0
    backlog_bytes: int = 0
    rtt_p50: float = 0.0
    rtt_p95: float = 0.0
    rtt_p99: float = 0.0
    jitter_ms: float = 0.0
    loss_ratio: float = 0.0


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
        self._ru0 = resource.getrusage(resource.RUSAGE_SELF)
        self._t0 = time.monotonic()

    # --- evaluation-side input -------------------------------------------
    def ingest(self, data: EvaluationData) -> None:
        if data.rtt_ms is not None:
            self._rtts.setdefault(data.label, []).append(data.rtt_ms)
            self._rtts[data.label] = self._rtts[data.label][-self.window :]
        self._last_eval[data.label] = data

    def rtts(self, label: str) -> list[float]:
        return list(self._rtts.get(label, []))

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

            ev = self._last_eval.get(cls.value)
            if ev is not None:
                if ev.rtt_ms is not None:
                    p = percentiles(self.rtts(cls.value))
                    m.rtt_p50, m.rtt_p95, m.rtt_p99 = p["p50"], p["p95"], p["p99"]
                    m.jitter_ms = ev.jitter_ms or jitter_from_samples(self.rtts(cls.value))
                m.loss_ratio = ev.loss_ratio or 0.0
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
