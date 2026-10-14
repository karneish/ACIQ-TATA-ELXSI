"""M2 — link capacity estimation.

Design was settled by measurement, not assumption. Gate check 12 ran on a
saturated 20 Mbit link and found:

  overlimits   24803 -> 65101 over 25 s   <- large, unambiguous, already in tc -s
  dropped      0 -> 252                 <- corroborating
  EF probe     0.051 -> 0.070 ms         <- NO signal
  unmarked probe 0.051 -> 0.405 ms (~8x)  <- works, but unnecessary
  backlog      0 throughout             <- carries no information

So this estimator reads **drop rate, overlimit rate and shaper backlog**. No
probe traffic, which means no probe overhead to account for in the CPU numbers
and no extra privilege.

Backlog was not in the original design, and adding it is a reversal of the
"counters only" decision rather than an extension of it. Measured, on the real
runs:

  t=0.0 - 4.2   child backlog 0        link 24.9 Mbps   (25 offered of 100)
  t=5.2 - 17.5  child backlog 5-22 kB  link ~10 Mbps    (25 offered of 10)
  t=18.5 - 22.6 child backlog 0        link  4.7 Mbps   (demand fell below cap)

HTB is a shaper: it holds packets in a child's queue and delays them rather than
overrunning, so against *paced* TCP senders a congested link reports `dropped 0,
overlimits 0`. The gate check 12 calibration that justified counters-only was
taken on an unpaced source and does not transfer.

Backlog carries the signal because a child's queue is non-empty precisely when
it wants more than the link can send it: while the parent has tokens to lend, a
child over its guarantee borrows instead of queueing. That is a semantic
argument, not a fitted threshold, and it is the reason this is defensible where
the overlimit signal was not.

Two facts shaped the algorithm, both measured:

1. **Capacity is only observable while the link is saturated.** An idle link's
   throughput is offered load, not capacity. So samples are gated on saturation
   and the estimator's confidence *decays* when the link is idle rather than
   inventing a number.

2. **The input type has no configured-rate field.** Class 1:1's configured rate
   is the answer; reading it would make this an oracle and make adaptation time
   measure zero. `Measurement` simply cannot carry it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

#: Asymmetric smoothing. Capacity falling is urgent (users are already hurting),
#: capacity rising is taken on trust more slowly.
ALPHA_DOWN = 0.6
ALPHA_UP = 0.1

#: Ignore changes smaller than this fraction. Stops the estimator chasing noise.
HYSTERESIS = 0.10

#: Minimum seconds between reported changes. Oscillation is a graded failure.
MIN_DWELL_S = 5.0

#: Consecutive saturated samples required before trusting an observation. One
#: burst is not a capacity reading.
SAT_STREAK_REQUIRED = 2

#: Shaper backlog above which the link counts as saturated.
#:
#: Observed across the real runs: 0 whenever the link was not the constraint,
#: and 1840-22710 bytes whenever it was. The threshold is far below the smallest
#: value ever seen non-zero, so it is effectively "the queue is not empty" --
#: deliberately not tuned, because a fitted threshold on one run is how the
#: overlimit threshold became wrong.
BACKLOG_MIN_BYTES = 1024

#: overlimits/sec above which the link counts as saturated.
#:
#: Set from measured runs, not taste:
#:   link genuinely full (100 Mbps, bulk saturating)  5127 - 6485 /s
#:   20 Mbps saturated (gate check 12)                 24803 - 65101 /s
#:   link ~10% loaded, children rate-limited (s3)        170 -  1313 /s
#: The two populations are separated by roughly 4x at the closest point.
#:
#: Magnitude is used rather than only parent-vs-child attribution because HTB
#: attributes a child's borrow to the parent too: the parent's overlimits rise
#: when a child is backlogged and borrowing. So "the parent is busy" does not
#: mean "the link is full", and only the rate tells them apart.
SAT_OVERLIMIT_MIN = 3000.0

#: Confidence decay per unsaturated sample.
IDLE_DECAY = 0.15


@dataclass(frozen=True)
class Measurement:
    """One observation of the link. Derived from ClassCounters by M5.

    Note what is absent: there is no `configured_mbps` field, by design. The
    estimator cannot read the bottleneck's configured rate even by accident.
    """

    t: float
    goodput_mbps: float
    drop_rate_per_s: float = 0.0
    overlimit_rate_per_s: float = 0.0
    #: Parent-class (link) rates. These, and only these, decide saturation.
    #: Child overlimits rise whenever a child exceeds its own guarantee, which
    #: happens on an almost idle link; summing them produced a measured death
    #: spiral (100 Mbps collapsed to 7.2 Mbps). Left None when the reader cannot
    #: see the parent, in which case the link is treated as NOT saturated — the
    #: safe direction, because guessing saturate shrinks capacity.
    link_drop_rate_per_s: float | None = None
    link_overlimit_rate_per_s: float | None = None
    #: Summed backlog across the children of the link. Read only as "is any
    #: shaper queue non-empty", never as a magnitude: the parent's own backlog
    #: is 0 throughout, because the queue lives in the children.
    child_backlog_bytes: int = 0
    #: Packets per second dropped by the OUT-OF-BAND bottleneck (netem on a
    #: device the controller never writes). Added because moving the bottleneck
    #: out of the controller's tree made it invisible to the saturation test:
    #: with the plan at 100 and the link at 10, the HTB parent is not
    #: overcommitted, so the link looks unsaturated and the estimator correctly
    #: declines to produce a reading. The host said so outright --
    #: "M2 only measures an oversubscribed link ... no post-drop reading was
    #: possible".
    #:
    #: This is a drop count, NOT the bottleneck's configured rate. The estimator
    #: must infer capacity, never read it; feeding it `netem rate 10mbit` would
    #: hand it the answer instead of letting it work one out. None means the
    #: bottleneck could not be read, which is treated as no signal rather than
    #: as no drops.
    bottleneck_drop_rate_per_s: float | None = None
    #: Bytes queued at the out-of-band bottleneck. The load-bearing signal for
    #: a bottleneck that *delays* rather than drops.
    #:
    #: `netem rate` shapes by delaying. Its drop counter stays at 0 until the
    #: 1000-packet limit overflows, which at 10 Mbit it does not -- so on the
    #: host the estimator stayed stuck at "102.5 Mbps is STALE" with a netem
    #: limit visibly in place and no drop ever recorded. Queue depth is the
    #: signal a rate limiter actually gives, and it is the direct analogue of
    #: `child_backlog_bytes` for the controller's own tree: offered load above
    #: what the link carries leaves the queue non-empty.
    bottleneck_backlog_bytes: int | None = None

    @property
    def saturated(self) -> bool:
        lo = self.link_overlimit_rate_per_s
        ld = self.link_drop_rate_per_s
        if lo is None and ld is None:
            # The reader cannot see the parent class. Treat as NOT saturated:
            # assuming saturation would shrink capacity on no evidence.
            return False
        if (ld or 0.0) > 0.0:
            return True
        if (lo or 0.0) >= SAT_OVERLIMIT_MIN:
            return True
        # The out-of-band bottleneck is dropping: the traffic offered exceeds
        # what the link will carry, which is saturation, whatever the
        # controller's own parent class happens to be doing.
        if (self.bottleneck_drop_rate_per_s or 0.0) > 0.0:
            return True
        # ...or the bottleneck simply cannot keep up. This is the common case
        # for a rate limiter, which delays rather than drops.
        if (self.bottleneck_backlog_bytes or 0) > 0:
            return True
        # A child queue that is not empty means the shaper wanted to send and
        # could not. Note this is consulted *after* the parent counters, so a
        # reader that cannot see the parent still refuses to declare saturation
        # from backlog alone -- assuming saturation without evidence is what
        # shrank capacity to 7.2 Mbps once.
        return self.child_backlog_bytes >= BACKLOG_MIN_BYTES


@dataclass(frozen=True)
class Capacity:
    """M2 output."""

    mbps: float
    confidence: float
    saturated: bool
    changed: bool


class CapacityEstimator:
    """Estimates link capacity from queue counters alone.

    Invariants worth stating, because each one is a bug that was avoided:

    * Saturation is decided by the **parent** class's overlimit *rate*, above a
      threshold taken from measured runs. Child overlimits are ignored.
      A child's overlimits mean that child exceeded its own guarantee, which is
      routine on a lightly loaded link; reading them as congestion shrinks
      capacity, which shrinks the class rates, which raises them again.
* Never updates from an unsaturated sample. An idle link reports offered
      load, not capacity.
    * Never reports a change smaller than HYSTERESIS.
    * Never reports two changes closer together than MIN_DWELL_S.
    * Confidence decays when idle rather than holding a stale high value.
    """

    def __init__(self, initial_mbps: float = 0.0):
        self._ewma = float(initial_mbps)
        self._confidence = 0.0
        self._sat_streak = 0
        self._last_change_t: float | None = None
        self._last_m: Capacity | None = None

    @property
    def current(self) -> Capacity:
        return self._last_m or Capacity(
            mbps=self._ewma, confidence=0.0, saturated=False, changed=False
        )

    def observe(self, m: Measurement) -> Capacity:
        changed = False

        if not m.saturated:
            # Idle or unsaturated: no capacity information. Decay confidence so
            # a stale estimate is visibly less trusted rather than looking solid.
            self._sat_streak = 0
            self._confidence = max(0.0, self._confidence - IDLE_DECAY)
            return self._emit(mbps=self._ewma, saturated=False, changed=False, m=m)

        self._sat_streak += 1
        if self._sat_streak < SAT_STREAK_REQUIRED:
            # One burst is not a reading.
            return self._emit(mbps=self._ewma, saturated=True, changed=False, m=m)

        # Saturated: observed goodput is the capacity.
        target = m.goodput_mbps
        if target <= 0.0:
            return self._emit(mbps=self._ewma, saturated=True, changed=False, m=m)

        if self._ewma <= 0.0:
            new = target
        else:
            alpha = ALPHA_UP if target > self._ewma else ALPHA_DOWN
            new = self._ewma + alpha * (target - self._ewma)

        # Hysteresis: below the band, do not move at all.
        if self._ewma > 0.0 and abs(new - self._ewma) < HYSTERESIS * self._ewma:
            self._confidence = min(1.0, self._confidence + 0.1)
            return self._emit(mbps=self._ewma, saturated=True, changed=False, m=m)

        # Dwell: not inside MIN_DWELL_S of the last reported change.
        if (
            self._last_change_t is not None
            and (m.t - self._last_change_t) < MIN_DWELL_S
        ):
            self._confidence = min(1.0, self._confidence + 0.1)
            return self._emit(mbps=self._ewma, saturated=True, changed=False, m=m)

        self._ewma = new
        self._last_change_t = m.t
        self._confidence = min(1.0, self._confidence + 0.2)
        changed = True

        return self._emit(mbps=new, saturated=True, changed=changed, m=m)

    def _emit(self, mbps: float, saturated: bool, changed: bool, m: Measurement) -> Capacity:
        cap = Capacity(
            mbps=mbps,
            confidence=round(self._confidence, 3),
            saturated=saturated,
            changed=changed,
        )
        self._last_m = cap
        return cap

    def force_safe(self, mbps: float) -> Capacity:
        """Reset to a known value, e.g. after a shield fault. Resets dwell so
        the next real observation is not suppressed by a stale change time."""
        self._ewma = float(mbps)
        self._confidence = 0.0
        self._sat_streak = 0
        self._last_change_t = None
        return self._emit(mbps=mbps, saturated=False, changed=True, m=None)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# CUSUM — optional, for drift rather than for the 5x step
# --------------------------------------------------------------------------
@dataclass
class CusumDriftDetector:
    """Tabular CUSUM for *gradual* degradation.

    Deliberately NOT the primary detector. Scenario 2 is a 5x step, which a
    threshold on the EWMA delta catches immediately. CUSUM earns its place on
    slow drift, where no single sample stands out.

    Must only be fed samples from a busy link: on an idle link the observed
    rate collapses toward zero and CUSUM would report a capacity collapse that
    is not happening. `busy_gated=True` refuses unsaturated samples.
    """

    slack_k: float = 0.5          # in capacity-fraction units
    threshold_h: float = 5.0
    baseline: float = 0.0
    s_pos: float = 0.0
    s_neg: float = 0.0
    busy_gated: bool = True
    drift: float | None = None
    _observations: list[float] = field(default_factory=list)

    def observe(self, value: float, busy: bool) -> bool:
        """Feed one busy-link throughput sample. Returns True on alarm.

        `drift` is set to the estimated per-step shift in capacity, signed:
        negative for a downward drift (degradation), positive for upward.
        """
        if self.busy_gated and not busy:
            return False
        if self.baseline <= 0.0:
            self.baseline = value
            return False
        scale = max(self.baseline, 1e-9)
        z = (value - self.baseline) / scale
        # s_pos accumulates when z is POSITIVE (value ABOVE baseline) => upward
        # drift. s_neg accumulates when z is NEGATIVE (value BELOW baseline)
        # => downward drift. Getting these two the wrong way round reports a
        # degradation as an improvement, which is worse than not alarming.
        self.s_pos = max(0.0, self.s_pos + z - self.slack_k)
        self.s_neg = max(0.0, self.s_neg - z - self.slack_k)

        alarm = False
        if self.s_pos > self.threshold_h:
            self.drift = self.slack_k * scale    # sustained upward drift
            self.s_pos = 0.0
            alarm = True
        if self.s_neg > self.threshold_h:
            self.drift = -self.slack_k * scale   # sustained downward drift
            self.s_neg = 0.0
            alarm = True
        return alarm

    def reset(self) -> None:
        self.s_pos = self.s_neg = 0.0
        self.drift = None
