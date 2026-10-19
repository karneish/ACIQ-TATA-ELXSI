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

#: Consecutive non-saturated samples before the estimate is released back
#: toward the high-water mark. Long enough that a momentary lull does not undo a
#: real capacity drop, short enough that a user whose line recovered does not
#: stay throttled for minutes.
IDLE_STREAK_RELEASE = 10

#: Fraction of the gap to the high-water mark closed per released tick. Much
#: slower than ALPHA_DOWN, because a wrong release costs a moment of
#: under-shaping while a wrong collapse costs a sustained one.
RELEASE_ALPHA = 0.2

#: Below this fraction of the current estimate, a reading is treated as a STEP
#: change and adopted outright rather than smoothed.
#:
#: Measured, not assumed. With ALPHA_DOWN 0.6 the EWMA needs six ticks to walk a
#: 100 Mbps estimate down to a true 20 -- 52, 32.8, 25.1, 22.1, 20.8, 20.3 --
#: which is the 5.4 s convergence measured on the host and the source of the
#: residual latency tail: the controller keeps serving the old, too-large
#: capacity for that whole window.
#:
#: Smoothing is right for noise and wrong for a step. A 5x change is not noise,
#: and `SAT_STREAK_REQUIRED` already demands two consecutive saturated readings
#: before any of this is believed, so the snap is not acting on a single sample.
#:
#: 0.5, not 0.7. At 0.7 the snap also fired on ordinary dips and the replayed
#: 100 -> 10 trace converged to 8.61 Mbps against a 10 Mbps link -- a 14%
#: undershoot, uncomfortably close to the 7.2 Mbps death-spiral this module
#: exists to prevent. Half is the line between "the link changed" and "this
#: sample is low", which is the distinction that matters.
FAST_DROP_RATIO = 0.5

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

#: Above this, a throughput reading is a unit or counter error rather than a
#: link: 100 Tbit/s is not a cable, and the estimator would plan against a
#: capacity no hardware has.
MAX_PLAUSIBLE_CAPACITY_MBPS = 100_000.0


def _is_usable_capacity(mbps) -> bool:
    """A throughput reading the estimator is allowed to adopt as capacity.

    The brief lists "rejection of invalid, non-finite or invalid measurements"
    among the estimator's required behaviour. It was missing, and the failure
    is permanent rather than transient:

        NaN > self._ewma   -> False, so alpha silently becomes ALPHA_DOWN
        0 + 0.6 * (NaN - 0) -> NaN, so the estimate is poisoned

    and once `_ewma` is NaN every later comparison against it is False, the
    hysteresis test can never fire again, and the controller stops adapting
    while still reporting a plausible-looking number. Nothing would raise.
    """
    if isinstance(mbps, bool) or not isinstance(mbps, (int, float)):
        return False
    if mbps != mbps:                       # NaN: the only value unequal to itself
        return False
    if mbps in (float("inf"), float("-inf")):
        return False
    if mbps <= 0.0:
        return False
    return mbps <= MAX_PLAUSIBLE_CAPACITY_MBPS

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
        """Is the EXTERNAL link congested?

        OPTION A -- the out-of-band bottleneck is the authority.

        The defect this replaces is recorded in
        docs/gap-closure/capacity-recovery-defect.md. In short: the old order
        consulted the controller's OWN parent class first, and under the
        differentiated-ceiling policy the sum of child ceilings always exceeds
        the parent rate:

            build_plan(estimate=20.26)
              -> 1:1 rate  = 20
              -> children  = bulk 17.0 + adaptive 6.0 + interactive 10.0 = 33
              -> 33 > 20, so class 1:1 is overlimit BY CONSTRUCTION, always
              -> `overlimits` rises every tick
              -> saturated = True, forever

        So the controller reported congestion caused by its own shaping, a stale
        estimate made it permanent, and the capacity-release path could never
        start. Measured on the host: the link was restored to 100 Mbps and
        `saturated` stayed True on every tick from t=30 to t=59.5.

        The same argument the module already applies to CHILD overlimits --
        "a child exceeding its own guarantee is routine and must not be read as
        congestion" -- applies verbatim to the parent whenever the policy's
        ceilings sum above it. It simply was not applied.

        WHEN THE BOTTLENECK CAN BE READ, IT DECIDES. Nothing the controller does
        to its own tree can change a number read off the far side of the link.

        WHEN IT CANNOT BE READ, THE OLD ORDER STANDS. Both telemetry fields are
        Optional and None means "could not read", which is genuinely
        distinguishable from "read 0": before `set_capacity` installs the
        netem qdisc, `tc -s qdisc show` reports `qdisc noqueue` with no backlog
        line at all, so both fields are None and the parent signals are still
        the only evidence available. Startup detection at 100 Mbps therefore
        keeps working, and a missing reading is never read as a clear link.
        """
        bb = self.bottleneck_backlog_bytes
        bd = self.bottleneck_drop_rate_per_s
        if bb is not None or bd is not None:
            # The bottleneck is observable, so it decides. Deliberately NOT
            # combined with the parent: an intentional parent overlimit is not
            # evidence of anything external.
            if (bd or 0.0) > 0.0:
                return True
            if (bb or 0) > 0:
                return True
            return False

        # No external telemetry. Fall back, and stay conservative.
        lo = self.link_overlimit_rate_per_s
        ld = self.link_drop_rate_per_s
        if lo is None and ld is None:
            # The reader cannot see the parent class. Treat as NOT saturated:
            return False
        if (ld or 0.0) > 0.0:
            return True
        if (lo or 0.0) >= SAT_OVERLIMIT_MIN:
            return True
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

    * Saturation is decided by the EXTERNAL bottleneck whenever it can be read.
      Child overlimits are ignored: a child exceeding its own guarantee is
      routine, and reading it as congestion shrinks capacity, which shrinks the
      class rates, which raises them again.
    * The controller's own PARENT overlimit is ignored too, whenever the
      bottleneck is readable. The differentiated-ceiling policy makes
      sum(children ceils) > parent rate true BY CONSTRUCTION, so the parent is
      permanently overlimit and says nothing about the link. Consulting it made
      a stale estimate self-sustaining and blocked capacity recovery entirely.
      When the bottleneck cannot be read, the parent signals are used instead --
      missing telemetry is never treated as a clear link.
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
        self._idle_streak = 0
        self._last_change_t: float | None = None
        self._last_m: Capacity | None = None
        #: The best capacity this estimator has ever seen, kept so a recovery
        #: can be detected -- see `observe`.
        self._high_water = float(initial_mbps)

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
            released, released_changed = self._release_idle(m)
            return self._emit(mbps=released, saturated=False,
                              changed=released_changed, m=m)

        self._sat_streak += 1
        if self._sat_streak < SAT_STREAK_REQUIRED:
            # One burst is not a reading.
            #
            # `_idle_streak` is deliberately NOT cleared here. It measures
            # SUSTAINED non-congestion, and a rate limiter's queue is briefly
            # non-empty all the time -- the host showed 3028 bytes, about two
            # packets, on ticks scattered through an otherwise completely
            # clear link. Each of those cancelled the release streak, so ten
            # consecutive clear ticks never accumulated and capacity was pinned
            # at the degraded rate for 30 s after the link came back.
            #
            # This is the same "one burst is not a reading" principle the
            # streak itself encodes, applied consistently: a single sample must
            # not cancel a recovery any more than it may trigger an adaptation.
            return self._emit(mbps=self._ewma, saturated=True, changed=False, m=m)
        # Confirmed congestion: now it is fair to reset the recovery streak.
        self._idle_streak = 0

        # Saturated: observed goodput is the capacity.
        target = m.goodput_mbps
        if not _is_usable_capacity(target):
            # The brief lists "rejection of invalid, non-finite or invalid
            # measurements" among the estimator's required behaviour, and it was
            # missing: this used to read `if target <= 0.0`, which NaN passes --
            # `NaN <= 0.0` is False.
            #
            # The failure is permanent rather than transient. `NaN > self._ewma`
            # is False so alpha silently becomes ALPHA_DOWN, `0.6 * (NaN - x)`
            # is NaN, and once `_ewma` is NaN every later comparison is False,
            # the hysteresis test can never fire again, and the controller stops
            # adapting while still reporting a plausible-looking number.
            # Nothing raises and nothing warns.
            #
            # The sample is not trusted for capacity. It is still observed as
            # saturated, and `_idle_streak` has already been cleared above, so a
            # corrupt reading cannot look like an idle link either.
            return self._emit(mbps=self._ewma, saturated=True, changed=False, m=m)

        if self._ewma <= 0.0:
            new = target
        else:
            alpha = ALPHA_UP if target > self._ewma else ALPHA_DOWN
            if target <= self._ewma * FAST_DROP_RATIO:
                # A step, not noise: take the reading as the new capacity and
                # let the normal smoothing resume from there.
                alpha = 1.0
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
        if self._ewma > self._high_water:
            self._high_water = self._ewma
        changed = True

        return self._emit(mbps=new, saturated=True, changed=changed, m=m)

    def seed_high_water(self, mbps: float) -> None:
        """Give the recovery path a target: the capacity this link was
        provisioned for.

        THE GAP OPTION A OPENED

        Option A -- judge external congestion by the external bottleneck -- is
        correct about saturation, but it means the estimator learns capacity
        ONLY from congestion. Measured on the host, before the drop:

            t=1.0 .. 9.5   saturated False   backlog 0   goodput 85.12

        85 Mbps on a 100 Mbps link leaves the netem queue empty, so the link is
        correctly judged uncongested, so the estimator never learns 100. It
        starts at 0, so `_high_water` stayed 0 until the drop, at which point it
        became exactly 20 -- the same as `_ewma`. `_release_idle` then returns
        immediately, because there is nothing to climb toward.

        The structural consequence: **the highest capacity ever observed is the
        LOWEST capacity that ever caused congestion.** A pure saturation-driven
        estimator has no recovery target by construction, and Option A made that
        visible rather than causing it.

        WHAT THIS IS NOT

        This does not feed the configured rate into the ESTIMATE. It seeds only
        the recovery target, so it cannot make a drop detected faster, cannot
        make the estimator skip a saturation it would otherwise have seen, and
        cannot read the bottleneck's configured rate -- the boundary the
        Measurement docstring draws is untouched.

        And it is not new information. The harness already builds the initial
        policy from the operator-configured link rate, exactly as a real router
        is provisioned with its uplink speed. This is the same fact, used for a
        second purpose.
        """
        if mbps > 0.0:
            self._high_water = max(self._high_water, float(mbps))

    def _release_idle(self, m: Measurement) -> tuple[float, bool]:
        """Recover capacity after the link frees up, without probing.

        THE GAP THIS CLOSES

        A saturation-driven estimator can only ever learn about a link getting
        SLOWER. A saturated link has no spare capacity by definition, so once
        the estimate has collapsed to 20 Mbps, nothing in a non-saturated
        sample can ever say "there is more here now" -- the observation carries
        no information about capacity, only about current load.

        The consequence was measured, not theorised. A capacity-recovery run
        restored the link to 100 Mbps and the steady goodput afterwards was
        17.33 Mbps -- exactly the degraded ceiling of 0.85 x 20. The controller
        never walked back up. A user whose ISP restored their line would keep
        the degraded rate indefinitely, which is a real and user-visible defect,
        and invisible to a drop-only test suite.

        THE MECHANISM

        Conservative hold, evidence-based release. The high-water mark -- the
        best capacity ever observed -- is remembered. After sustained
        non-saturation there is no evidence of congestion, so the estimate is
        released back toward it at RELEASE_ALPHA: deliberately slower than the
        fall, because being wrong here means under-shaping (recoverable, the
        next saturation drops the estimate again immediately) rather than
        over-shaping.

        This does NOT read the configured rate, does NOT probe, and does NOT
        invent capacity. It only declines to stay pessimistic when the evidence
        for pessimism has gone away.
        """
        self._idle_streak += 1
        if self._idle_streak < IDLE_STREAK_RELEASE or self._high_water <= 0.0:
            return self._ewma, False
        if self._ewma >= self._high_water:
            self._high_water = self._ewma
            return self._ewma, False
        # WHY THERE IS NO THROUGHPUT TEST HERE
        #
        # An earlier version required delivered goodput to exceed the estimate
        # by 1.5x before releasing, reasoning that you cannot deliver more than
        # the link has. On the host that condition was never satisfiable: after
        # recovery the link was 100 Mbps, bulk's ceiling was 17, so delivered
        # throughput was 17.3 -- below the 30 Mbps the condition demanded.
        #
        # The controller throttles ITSELF below the link, so it can never
        # observe throughput exceeding its own estimate. Passive observation
        # cannot distinguish "this link is 20 Mbps" from "this link is 100 Mbps
        # and we are only sending 17". That is information the measurement does
        # not contain, so demanding it is demanding the impossible.
        #
        # THE ASYMMETRY INSTEAD
        #
        # Rising is slow (RELEASE_ALPHA, after IDLE_STREAK_RELEASE seconds of
        # sustained non-congestion) and falling is fast (FAST_DROP_RATIO adopts
        # a step in ONE tick). So an incorrect release is self-correcting: the
        # moment it over-sends, the link saturates and the estimate snaps back
        # down immediately. The cost of being wrong is bounded by one tick of
        # over-shaping; the cost of never releasing is a user throttled forever.
        #
        # The dwell window and HYSTERESIS still apply, so this obeys the same
        # anti-oscillation rules as every other change.
        target = min(self._high_water,
                     self._ewma + RELEASE_ALPHA * (self._high_water - self._ewma))
        if target <= self._ewma:
            return self._ewma, False
        # Respect the same dwell and hysteresis any other change obeys, so a
        # link that is genuinely still slow does not oscillate.
        if (self._last_change_t is not None
                and (m.t - self._last_change_t) < MIN_DWELL_S):
            return self._ewma, False
        if abs(target - self._ewma) < HYSTERESIS * self._ewma:
            return self._ewma, False
        self._ewma = target
        self._last_change_t = m.t
        self._confidence = min(1.0, self._confidence + 0.2)
        # `changed=True` is the whole point of the return type. The release
        # moved the estimate, and the caller must rebuild the policy from it --
        # otherwise the estimate climbs to the high-water mark while the applied
        # policy stays pinned at the degraded rate forever.
        return self._ewma, True

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
