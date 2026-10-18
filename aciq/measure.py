"""Measurement: turning individual probe observations into reported metrics.

Separated from `metrics.py` because this is arithmetic, it must be testable
against deterministic synthetic traces, and it has no business importing
anything that can touch `tc`.

## Why this module exists

`rtt_p95`, `jitter_ms` and `loss_ratio` were reported as `0.0` in every run this
project ever produced. Two independent causes, both upstream of any arithmetic:

* `MetricsCollector.ingest` stored evaluation data keyed by **workload label**
  (`call`, `tv1`) while `poll` read it back by **class value**
  (`adaptive_video`). The lookup never matched, so the evaluation branch was
  dead code and the `0.0` defaults survived.
* the generators only wrote their summary once, at the end of the run, so there
  was no per-tick series to report even if the lookup had worked.

Fixing the lookup alone would have produced a step function mislabelled as a
time series. This module exists so the arithmetic is correct and testable
independently of both.

## Definitions, stated so they cannot drift between arms

**RTT** is round-trip time: send timestamp to receive timestamp of the *same*
sequence number, on a monotonic clock. One-way delay is **not** measured — there
are no synchronised clocks across the namespaces, and claiming it would be
unsupported.

**Jitter** is the mean absolute difference between consecutive valid RTT
observations, in arrival order. This is the RFC 3550 smoothed-interarrival form
simplified to consecutive-sample PDV. The generator uses the same definition, so
the two agree by construction rather than by coincidence.

**Loss** is `1 - received / expected`, where *expected* is the highest sequence
number sent that the measurement window can legitimately account for — not simply
the number sent, because the last packets are still in flight when the window
closes. Counting them as lost would report a loss spike at the end of every run.

**Validity** is explicit. A metric that could not be computed is `None` with a
reason, never `0.0`. Zero is a real measurement — a flow with no delay variation
and no loss has jitter 0.0 — and conflating the two is what made the previous
dashboard label negative latency.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from collections.abc import Iterable, Sequence

#: Below this many valid RTT samples, percentiles are reported as None rather
#: than computed. A p99 from three samples is a number, not an estimate, and
#: publishing it as one is how a "0.1 ms p99" claim survives review.
MIN_SAMPLES_FOR_PERCENTILES = 10

#: A sample whose RTT exceeds this is discarded as a suspected pause (GC, a
#: scheduling hiccup, a host suspend). Retaining it turns a control-plane blip
#: into a latency result. Must be comfortably above any real delay the testbed
#: can produce, or real congestion gets filtered out.
MAX_PLAUSIBLE_RTT_MS = 5000.0

#: Validity states. `not_measured` is the one that must never be rendered as 0.
NOT_MEASURED = "not_measured"
INSUFFICIENT_SAMPLES = "insufficient_samples"
VALID = "valid"


@dataclass(frozen=True)
class Observation:
    """One probe exchange.

    `recv_mono_s` is None when the reply never arrived within the timeout. The
    sequence number is what makes loss computable at all; without it, a
    receiver can only count packets and cannot distinguish loss from reordering.
    """

    seq: int
    sent_mono_s: float
    recv_mono_s: float | None = None
    status: str = VALID

    @property
    def rtt_ms(self) -> float | None:
        if self.recv_mono_s is None:
            return None
        return (self.recv_mono_s - self.sent_mono_s) * 1000.0

    @property
    def lost(self) -> bool:
        return self.recv_mono_s is None


@dataclass(frozen=True)
class Metrics:
    """Derived figures plus their validity. Every value is Optional on purpose."""

    rtt_p50_ms: float | None = None
    rtt_p95_ms: float | None = None
    rtt_p99_ms: float | None = None
    jitter_ms: float | None = None
    loss_ratio: float | None = None
    expected: int = 0
    received: int = 0
    valid: int = 0
    discarded_outlier: int = 0
    duplicated: int = 0
    reordered: int = 0
    status: str = NOT_MEASURED
    window_s: float = 0.0

    @property
    def usable(self) -> bool:
        return self.status == VALID

    def to_dict(self) -> dict:
        return {
            "rtt_p50_ms": self.rtt_p50_ms, "rtt_p95_ms": self.rtt_p95_ms,
            "rtt_p99_ms": self.rtt_p99_ms, "jitter_ms": self.jitter_ms,
            "loss_ratio": self.loss_ratio, "expected": self.expected,
            "received": self.received, "valid": self.valid,
            "discarded_outlier": self.discarded_outlier,
            "duplicated": self.duplicated, "reordered": self.reordered,
            "status": self.status, "window_s": self.window_s,
        }


def dedupe(observations: Iterable[Observation]) -> tuple[list[Observation], int, int]:
    """-> (unique_in_seq_order, n_duplicates, n_reordered).

    A UDP probe receives duplicates and reordering in normal operation. Counting
    a duplicate as a receipt inflates goodput; counting an out-of-order packet as
    a loss invents loss that never happened.

    **First occurrence wins.** A repeated sequence number is a duplicate reply,
    not a second measurement; the first one sent is the real round trip. Keeping
    whichever happened to be shorter would let a duplicate *reduce* the reported
    delay, which is the wrong direction for a conservative measurement.

    Reordering is counted from the **arrival order as supplied**, before
    sorting. Counting it afterwards is a bug: sorting by sequence removes every
    inversion, so the counter is structurally always zero -- which is exactly
    what the first version of this function did, and the test caught.
    """
    seqs = [ob.seq for ob in observations]
    reordered = sum(1 for i in range(1, len(seqs)) if seqs[i] < seqs[i - 1])

    by_seq: dict[int, Observation] = {}
    dups = 0
    for ob in observations:
        if ob.seq in by_seq:
            dups += 1
            continue                      # first occurrence wins
        by_seq[ob.seq] = ob

    return [by_seq[s] for s in sorted(by_seq)], dups, reordered


def percentile(values: Sequence[float], p: float) -> float:
    """Nearest-rank percentile on a sorted copy.

    Nearest-rank rather than interpolating: with tens of samples, an
    interpolated p99 invents a value between two observations that were never
    measured.
    """
    if not values:
        raise ValueError("percentile of an empty sample")
    xs = sorted(values)
    if p <= 0:
        return xs[0]
    if p >= 100:
        return xs[-1]
    rank = math.ceil(p / 100.0 * len(xs))
    return xs[max(0, min(len(xs) - 1, rank - 1))]


def jitter(observations: Sequence[Observation]) -> float | None:
    """Mean absolute consecutive RTT difference, in arrival order. None if <2."""
    rtts = [o.rtt_ms for o in observations
            if o.rtt_ms is not None and 0 <= o.rtt_ms <= MAX_PLAUSIBLE_RTT_MS]
    if len(rtts) < 2:
        return None
    diffs = [abs(rtts[i] - rtts[i - 1]) for i in range(1, len(rtts))]
    return sum(diffs) / len(diffs)


def loss_ratio(observations: Sequence[Observation],
               in_flight: int = 0) -> float | None:
    """(expected - received) / expected, with `in_flight` excluded.

    `in_flight` is how many sequences were sent but had no chance to return
    before the window closed. Without it every run reports a loss spike at its
    last tick, which is an artefact of the measurement window, not of the link.
    """
    if not observations:
        return None
    expected = len(observations) - max(0, in_flight)
    if expected <= 0:
        return None
    received = sum(1 for o in observations if not o.lost)
    return max(0.0, (expected - received) / expected)


def compute(observations: Iterable[Observation],
            in_flight: int = 0) -> Metrics:
    """The whole pipeline. Pure: same input, same output, no clock, no I/O."""
    raw = list(observations)
    if not raw:
        return Metrics(status=NOT_MEASURED)

    ordered, dups, reordered = dedupe(raw)
    rtts: list[float] = []
    outliers = 0
    for ob in ordered:
        r = ob.rtt_ms
        if r is None:
            continue
        if r < 0 or r > MAX_PLAUSIBLE_RTT_MS:
            outliers += 1
            continue
        rtts.append(r)

    span = (max(o.sent_mono_s for o in ordered) - min(o.sent_mono_s for o in ordered))
    received = sum(1 for o in ordered if not o.lost)

    if not rtts:
        # Every packet was lost, or every sample was implausible. Loss is still
        # a real measurement here; latency is genuinely unavailable.
        lr = loss_ratio(ordered, in_flight)
        return Metrics(loss_ratio=lr, expected=len(ordered), received=received,
                       valid=0, discarded_outlier=outliers, duplicated=dups,
                       reordered=reordered,
                       status=INSUFFICIENT_SAMPLES if lr == 0 else VALID,
                       window_s=span)

    enough = len(rtts) >= MIN_SAMPLES_FOR_PERCENTILES
    return Metrics(
        rtt_p50_ms=percentile(rtts, 50) if enough else None,
        rtt_p95_ms=percentile(rtts, 95) if enough else None,
        rtt_p99_ms=percentile(rtts, 99) if enough else None,
        jitter_ms=jitter(ordered),
        loss_ratio=loss_ratio(ordered, in_flight),
        expected=len(ordered), received=received, valid=len(rtts),
        discarded_outlier=outliers, duplicated=dups, reordered=reordered,
        status=VALID if enough else INSUFFICIENT_SAMPLES,
        window_s=span)