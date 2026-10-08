"""M3 — the policy engine.

A pure function: (capacity, lease) -> RatePlan. No kernel access, no I/O, no
root. That is what makes the anti-starvation invariant testable at all.

The three rules that matter:

1. Every class keeps a floor: max(FLOOR_ABS_MBPS, FLOOR_FRACTION * capacity).
   Never revocable. This is the formal answer to "prevent starvation of
   low-priority traffic".

2. sum(rate_mbps) <= capacity_mbps, on EVERY call. Rescaling children when the
   parent shrinks is M3's job — the harness changes only the physical link.

3. A lease adds a bounded share (LAMBDA caps its influence) and never removes
   another class's floor.
"""

from __future__ import annotations

from .model import BASE_WEIGHTS, Lease, RatePlan, TrafficClass

#: A class is guaranteed at least this, whatever else is happening.
FLOOR_ABS_MBPS = 2.0
#: ...and at least this fraction of capacity.
FLOOR_FRACTION = 0.05
#: Upper bound on how much a lease can boost the target, as a fraction of the
#: interactive class it resembles. Bounds influence even for absurd input.
LAMBDA = 0.5
#: Accepted range for Lease.weight. Input is clamped, never trusted.
WEIGHT_MIN = 0.0
WEIGHT_MAX = 1.0
#: Below this, floors cannot all fit and we report degraded rather than lie.
MIN_VIABLE_MBPS = 1e-9

_EPS = 1e-9


def floor_mbps(capacity_mbps: float) -> float:
    """Guaranteed rate for every single class."""
    return max(FLOOR_ABS_MBPS, FLOOR_FRACTION * capacity_mbps)


def effective_weights(lease: Lease | None) -> dict[TrafficClass, float]:
    """Base weights, plus a bounded contribution from an active lease.

    A lease creates its own sub-class rather than boosting an existing class:
    boosting 'interactive' (already weight 8) would compete only with itself
    and produce an effect too small to measure.

    The leased flow is *an interactive flow that was promoted*, so its weight is
    derived from the interactive weight rather than invented from thin air. An
    earlier version used `LAMBDA * weight` directly, which made a lease of 0.4
    worth 0.2 — less than bulk's 2.0. The lease was then weaker than the traffic
    it was meant to protect. Tests caught this; the weight is now anchored to the
    class the lease actually promotes.
    """
    w = dict(BASE_WEIGHTS)
    if lease is None:
        return w
    weight = min(max(lease.weight, WEIGHT_MIN), WEIGHT_MAX)
    w[TrafficClass.LEASED] = BASE_WEIGHTS[TrafficClass.INTERACTIVE] * (1.0 + LAMBDA * weight)
    return w


def build_plan(
    capacity_mbps: float,
    lease: Lease | None = None,
) -> RatePlan:
    """Turn a measured capacity and an optional lease into guaranteed rates.

    Guarantees sum(rates) <= capacity, always. If the capacity is so small that
    the floors cannot all fit, floors are scaled down proportionally and
    `degraded=True` is set, because silently violating rule 1 is worse than
    admitting the link is too small to protect everyone.
    """
    if capacity_mbps <= MIN_VIABLE_MBPS:
        return RatePlan(capacity_mbps=capacity_mbps, rates={}, degraded=True)

    w = effective_weights(lease)
    classes = list(w)
    n = len(classes)

    floor = floor_mbps(capacity_mbps)
    reserved = floor * n

    degraded = False
    if reserved > capacity_mbps:
        # Cannot honour every floor. Scale them all down equally rather than
        # letting the sum exceed the link.
        floor = capacity_mbps / n
        reserved = capacity_mbps
        degraded = True

    remaining = capacity_mbps - reserved
    total_w = sum(w.values())
    if total_w <= _EPS:
        # Degenerate weights (e.g. a zero-weight lease): split evenly.
        total_w = n

    rates = {c: floor + (w[c] / total_w) * remaining for c in classes}

    plan = RatePlan(
        capacity_mbps=capacity_mbps,
        rates=rates,
        # Every class may borrow up to the whole link and no further. Never set
        # ceil above capacity: HTB permits borrowing past the parent's rate up to
        # the child's ceil, measured at 28.5 Mbps on a 20 Mbps parent whose
        # children still carried ceil 99/97. A ceiling above the bottleneck is
        # how traffic exceeds the link.
        ceils={c: capacity_mbps for c in classes},
        lease_id=lease.id if lease is not None else None,
        degraded=degraded,
    )

    # Rule 2 is an invariant, not a hope. Clamp against float drift so callers
    # never see a total that exceeds the link by a rounding error.
    total = plan.total()
    if total > capacity_mbps and total > _EPS:
        scale = capacity_mbps / total
        plan.rates = {c: r * scale for c, r in plan.rates.items()}

    return plan
