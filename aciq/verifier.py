"""Verification and the rate-change law.

The txn machinery (aciq.txn) applies what was asked. This module answers
three questions the txn path DOES NOT OWN, in
the same order a controller meets them:

1. May the rate move (the LAW), before anything is applied?
2. Was the change justified (VERDICT), after the measurement window?
3. Should we keep trying (BOARD GUARD), when nothing seems to help?

Three hard rules drive every constant here. First, the law must be no wider
than the estimator can plausibly justify in one step: capacity that doubles
in one tick looks like a controller, behaves like an attack on the tree.
Second, a verdict compares the SAME class of caller evidence: before-window
versus after-window medians of the SAME fields. Averaging a noisy momentary
rate into the comparison would be reading tea leaves. Third, a controller
that keeps failing must STAND DOWN, not keep toggling the tree — that is
the difference between "adaptive" and "random".
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass

from .capacity import Measurement

# ---- the law ---------------------------------------------------------------
#: One adaptation may move the parent rate at most this fraction of its own
#: current rate. 25%: even a full mis-estimate is recovered within 3-4
#: legitimate ticks, and no single tick can triple the class sum's rate.
MAX_RATE_STEP_FRAC = 0.25
#: ...but never less time than this between two changes. HTB re-pricing has
#: a transient; changing every millisecond would mean the transient IS the
#: measurement. Also the dwell that phase-4's live gate depends on.
MIN_DWELL_S = 5.0
#: bounded absolute floor so a small link isn't crushed by fraction math.
MIN_RATE_MBPS = 1.0
#: An emergency (severe loss) may skip the dwell ONCE and take a larger step:
#: standing on MIN_DWELL_S while a class is dropping would be policy purity
#: valued above the workload.
EMERGENCY_DROP_RATE_PER_S = 500.0
EMERGENCY_STEP_MULT = 2.0
#: Delay-driven twin of the drop emergency (docs/evidence/task2-params.md):
#: the governor's backed-up-queue failure mode produces delays, not drops, so
#: the drop comparator never fires there. A delay emergency clears a single
#: DOWN move to land at the want in one commit -- the governor has already
#: bounded that want by its ceiling and floors; a full descent can never
#: grow any queue. The governor paces this with its own cooldown.
DELAY_EMERGENCY = True
#: Downward landings keep this fraction of headroom under the target. The
#: 100->30 ramp measured a landing at 33.12 against a 33.0 band top: the
#: target was right, the rounding was not. Two percent is far below the
#: 10 % band and costs nothing the delivered stream can see.
LANDING_HEADROOM_FRAC = 0.02

# ---- the verdict -----------------------------------------------------------
#: Minimum before/after samples (ticks) for a verdict to even be rendered.
#: Fewer than this and the honest verdict is "not enough evidence", not
#: "keep"/"rollback".
MIN_VERDICT_SAMPLES = 4
#: Rollback when after-goodput collapses this far below before-goodput.
GOODPUT_REGRESS_FRAC = 0.15
#: ...or when the after-drop is this much worse than the before-drop (only
#: compared when the before window actually had drops to compare).
DROP_REGRESS_FRAC = 0.30
MIN_BASELINE_DROP = 0.5  # drop/s: below this the drop comparison is not meaningful

# ---- the board guard ------------------------------------------------------
#: Consecutive rollbacks tolerated before standing down.
MAX_CONSECUTIVE_ROLLBACKS = 3
#: How long to stand down after the guard trips. Then the counters reset.
STANDBY_S = 60.0


def _metrics_of(samples: list[Measurement]) -> tuple[float, float] | None:
    """(median goodput, median drop/s) of a window, or None if too short."""
    if len(samples) < MIN_VERDICT_SAMPLES:
        return None
    g = statistics.median(s.goodput_mbps for s in samples)
    d = statistics.median(s.drop_rate_per_s for s in samples)
    return g, d


@dataclass(frozen=True)
class Verdict:
    """KEEP / ROLLBACK with the numbers that decided it, per-sample honest."""

    outcome: str              # "keep" | "rollback" | "insufficient"
    reasons: tuple[str, ...]
    before_median_goodput: float | None
    after_median_goodput: float | None
    before_median_drop: float | None
    after_median_drop: float | None

    def __bool__(self) -> bool:  # keep/insufficient are actionable-positive
        return self.outcome != "rollback"


def timeline_verdict(before: list[Measurement],
                     after: list[Measurement]) -> Verdict:
    """Decide keep-vs-rollback from two windows of the SAME evidence.

    Deliberately no capacity parameter: the windows carry goodput and drop
    rates; a change that halved goodput or tripled drop is worse on the
    workload even if the rate estimate was "correct".
    """
    pre = _metrics_of(before)
    post = _metrics_of(after)
    if pre is None or post is None:
        reasons = []
        if pre is None:
            reasons.append("before window short")
        if post is None:
            reasons.append("after window short")
        return Verdict("insufficient", tuple(reasons), None, None, None, None)
    bg, bd = pre
    ag, ad = post
    reasons = []
    if ag < bg * (1.0 - GOODPUT_REGRESS_FRAC):
        reasons.append(
            f"goodput regressed {bg:.2f}->{ag:.2f}")
    if bd >= MIN_BASELINE_DROP and ad > bd * (1.0 + DROP_REGRESS_FRAC):
        reasons.append(
            f"drop rate regressed {bd:.1f}->{ad:.1f}/s")
    outcome = "rollback" if reasons else "keep"
    return Verdict(outcome, tuple(reasons), round(bg, 3), round(ag, 3),
                   round(bd, 3), round(ad, 3))


@dataclass(frozen=True)
class BoundResult:
    """The rate the law permits, and why anything else was not permitted."""

    rate: float | None       # Mbps to apply, None = do not apply
    reason: str              # documented even when nothing changed
    emergency: bool

    def __bool__(self) -> bool:
        return self.rate is not None


def with_landing_headroom(rate: float | None, prev_rate: float | None,
                          floor: float | None = None) -> float | None:
    """Shave a DOWN landing so a measured carry never sits on the band edge.

    Only descents are touched: an upward move is already bounded by the
    ceiling and must not be made to undershoot. `floor` is re-applied after
    the shave so the headroom can never violate the plan floor.
    """
    if rate is None or prev_rate is None or rate >= prev_rate:
        return rate
    rate *= (1.0 - LANDING_HEADROOM_FRAC)
    if floor is not None:
        rate = max(rate, floor)
    return rate


def bound_rate_change(prev_rate: float | None, want_rate: float,
                      now: float, last_change_t: float | None,
                      drop_rate_per_s: float = 0.0,
                      delay_emergency: bool = False,
                      landing: bool = False) -> BoundResult:
    """Whether and how far the parent rate may move, before it is applied.

    Order of law: first the dwell (unless emergency), then the step
    (emergency doubles it), then the absolute floor. Returns the ORIGINAL
    want when nothing binds — the fast path is common and must be cheap.

    `delay_emergency` (the governor's cleared, cooldown-paced descent flag)
    applies only to DOWN moves: the dwell is skipped and the step bound is
    bypassed entirely — landing below the current rate cannot overshoot or
    grow a queue, which is what the step bound exists to prevent going up.

    `landing` skips the dwell (only) for a corrective landing that may sit a
    hair ABOVE the applied rate. The overshoot branch returns the wire's own
    carry; after a ramp-down the carry can be 0.1-2% over the applied while
    still inside the end-band, and the 5 s dwell deferred it past the 8 s
    landing budget (s2b_ramp_100to30 seeds 1004/1007). It is not a new probe:
    the ceiling and step bounds still apply.
    """
    emergency = drop_rate_per_s >= EMERGENCY_DROP_RATE_PER_S
    if prev_rate is None:
        return BoundResult(want_rate, "first rate", emergency)
    down_emergency = (delay_emergency and DELAY_EMERGENCY
                      and want_rate < prev_rate)
    if last_change_t is not None:
        dwelled = (now - last_change_t) >= MIN_DWELL_S
        if not dwelled and not (emergency or down_emergency or landing):
            return BoundResult(None, "dwell window not elapsed", False)
    step_frac = MAX_RATE_STEP_FRAC * (EMERGENCY_STEP_MULT if emergency else 1.0)
    max_step = max(prev_rate * step_frac, 0.0)
    delta = want_rate - prev_rate
    if down_emergency:
        rate = want_rate
        reason = "delay emergency: descent lands at want in one commit"
    elif abs(delta) <= max_step:
        rate = want_rate
        reason = "within step bound"
    else:
        sign = -1.0 if delta < 0 else 1.0
        rate = prev_rate + sign * max_step
        reason = "step-clamped"
    if rate < MIN_RATE_MBPS:
        rate = MIN_RATE_MBPS
        reason = "clamped at floor"
    return BoundResult(rate, reason, emergency)


@dataclass
class BoardGuard:
    """Stand-down counter: the duty of care against oscillating ROLLBACKs."""

    rollbacks_in_a_row: int = 0
    standby_until: float | None = None

    def note_verdict(self, verdict: Verdict, now: float) -> None:
        if verdict.outcome == "rollback":
            self.rollbacks_in_a_row += 1
            if self.rollbacks_in_a_row >= MAX_CONSECUTIVE_ROLLBACKS:
                self.standby_until = now + STANDBY_S
        elif verdict.outcome == "keep":
            self.rollbacks_in_a_row = 0

    def blocked(self, now: float) -> bool:
        if self.standby_until is None:
            return False
        if now >= self.standby_until:
            # served out the sentence; counters reset
            self.standby_until = None
            self.rollbacks_in_a_row = 0
            return False
        return True
