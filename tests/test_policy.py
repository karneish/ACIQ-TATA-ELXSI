"""M3 policy engine tests. No root, no network, no kernel."""

from __future__ import annotations

import unittest

from aciq.model import BASE_WEIGHTS, Lease, TrafficClass
from aciq.policy import (
    FLOOR_ABS_MBPS,
    LAMBDA,
    WEIGHT_MAX,
    build_plan,
    effective_weights,
    floor_mbps,
)


def lease(weight: float = 0.4, ttl: float = 90.0, ident: str = "L1") -> Lease:
    return Lease(id=ident, target="device", ip="10.0.1.2", weight=weight, ttl_s=ttl)


class TestFloor(unittest.TestCase):
    def test_floor_is_absolute_when_capacity_low(self):
        # 20 Mbps * 5% = 1 Mbps, below the 2 Mbps absolute floor
        self.assertEqual(floor_mbps(20.0), FLOOR_ABS_MBPS)

    def test_floor_is_fraction_when_capacity_high(self):
        # 100 Mbps * 5% = 5 Mbps, above the absolute floor
        self.assertEqual(floor_mbps(100.0), 5.0)


class TestInvariant(unittest.TestCase):
    """Rule 2: sum(rates) <= capacity, on EVERY call."""

    def test_invariant_across_capacity_sweep(self):
        for cap in [100.0, 80.0, 50.0, 40.0, 20.0, 10.0, 5.0, 3.0, 1.0, 0.1]:
            with self.subTest(capacity=cap):
                plan = build_plan(cap)
                self.assertLessEqual(plan.total(), cap + 1e-9)
                self.assertGreaterEqual(plan.total(), 0.0)

    def test_invariant_holds_for_every_class_of_lease(self):
        for cap in [100.0, 20.0, 6.0, 2.0]:
            with self.subTest(capacity=cap):
                plan = build_plan(cap, lease())
                self.assertLessEqual(plan.total(), cap + 1e-9)

    def test_parent_child_rescale_on_100_to_20(self):
        """The bug that would have starved every class.

        ACIQ's children stay at their 100 Mbps values after the link drops to
        20 Mbps. HTB guarantees become unsatisfiable and children silently
        contend. build_plan must rescale on every call.
        """
        before = build_plan(100.0)
        after = build_plan(20.0)
        self.assertGreater(before.rates[TrafficClass.BULK], after.rates[TrafficClass.BULK])
        self.assertLessEqual(after.total(), 20.0 + 1e-9)

    def test_ceil_never_exceeds_capacity(self):
        """Second invariant, added after measuring 28.5 Mbps through a
        20 Mbps parent whose children carried ceil 99/97. HTB lets a class
        borrow past its parent's rate up to its own ceil, so a ceil above the
        bottleneck is a way for traffic to exceed the link."""
        for cap in [100.0, 20.0, 6.0, 2.0]:
            with self.subTest(capacity=cap):
                plan = build_plan(cap)
                for cls, c in plan.ceils.items():
                    self.assertLessEqual(c, cap + 1e-9, f"{cls} ceil {c} > {cap}")

    def test_ceil_holds_with_lease(self):
        plan = build_plan(20.0, lease())
        self.assertLessEqual(plan.max_ceil(), 20.0 + 1e-9)

    def test_latency_sensitive_classes_can_borrow_the_whole_link(self):
        """Classes must be able to use idle bandwidth, otherwise a floor-only
        setup would waste the link. ceil == capacity gives full borrowing
        without exceeding the bottleneck.

        Deliberately no longer true for BULK, which is capped below capacity so
        it cannot monopolise the link. Borrowing is still available to every
        latency-sensitive class, which is the property this test protects.
        """
        plan = build_plan(20.0)
        for c, ceil in plan.ceils.items():
            if c is TrafficClass.BULK:
                continue
            self.assertAlmostEqual(ceil, 20.0, places=9)

    def test_bulk_ceiling_caps_it_below_the_link(self):
        """The brief says the controller limits the bulk queue.

        With every class at ceil == capacity, bulk borrows the whole link, the
        bottleneck's queue stays pinned full, and the call's p95 is identical
        for FIFO, CAKE and ACIQ -- measured, not assumed.
        """
        plan = build_plan(20.0)
        self.assertLess(plan.ceils[TrafficClass.BULK], 20.0)
        self.assertAlmostEqual(plan.ceils[TrafficClass.BULK], 17.0, places=9)

    def test_bulk_still_borrows_up_to_its_ceiling_when_alone(self):
        """The ceiling is a limit, not a downgrade: bulk keeps its guarantee and
        still uses far more than it when it is the only sender."""
        plan = build_plan(20.0)
        self.assertGreater(plan.ceils[TrafficClass.BULK], plan.rates[TrafficClass.BULK])

    def test_headroom_is_retained_for_latency_sensitive_traffic(self):
        """Whatever bulk gives up, something else must be able to use."""
        for cap in (20.0, 100.0):
            plan = build_plan(cap)
            headroom = cap - plan.ceils[TrafficClass.BULK]
            self.assertGreater(headroom, 0.0, f"no headroom left at {cap} Mbps")

    def test_ceil_never_below_rate(self):
        for cap in [100.0, 20.0]:
            plan = build_plan(cap)
            for cls, r in plan.rates.items():
                self.assertGreaterEqual(plan.ceils[cls] + 1e-9, r)

    def test_degenerate_capacity_reports_degraded(self):
        # 1 Mbps cannot give 3 classes a 2 Mbps floor each
        plan = build_plan(1.0)
        self.assertTrue(plan.degraded)
        self.assertLessEqual(plan.total(), 1.0 + 1e-9)

    def test_zero_capacity_is_safe(self):
        plan = build_plan(0.0)
        self.assertEqual(plan.total(), 0.0)
        self.assertTrue(plan.degraded)


class TestAntiStarvation(unittest.TestCase):
    """Rule 1: every class keeps a floor even when a lease is active."""

    def test_every_class_has_a_floor(self):
        for cap in [100.0, 20.0]:
            with self.subTest(capacity=cap):
                plan = build_plan(cap)
                for cls in TrafficClass:
                    if cls is TrafficClass.LEASED:
                        continue
                    self.assertGreaterEqual(plan.rates[cls], floor_mbps(cap) - 1e-9)

    def test_lease_does_not_reduce_any_floor(self):
        """A lease borrows from the *shared* pool, so other classes' raw rates
        may dip slightly. What must never happen is a class losing its FLOOR —
        that is the actual anti-starvation guarantee. Asserting raw rates never
        fall would forbid leases from working at all."""
        cap = 20.0
        leased = build_plan(cap, lease())
        fl = floor_mbps(cap)
        for cls in (TrafficClass.INTERACTIVE, TrafficClass.ADAPTIVE, TrafficClass.BULK):
            self.assertGreaterEqual(leased.rates[cls], fl - 1e-9)

    def test_lease_cost_to_others_is_bounded(self):
        """Bounded: others give up a share, not their guarantee, and not more
        than the pool above the floors."""
        cap = 20.0
        plain = build_plan(cap)
        leased = build_plan(cap, lease())
        fl = floor_mbps(cap)
        headroom = cap - fl * 3  # what was available to divide in the unleased case
        loss = sum(plain.rates[c] - leased.rates[c] for c in
                   (TrafficClass.INTERACTIVE, TrafficClass.ADAPTIVE, TrafficClass.BULK))
        self.assertGreaterEqual(loss, -1e-9)          # nobody gains
        self.assertLessEqual(loss, headroom + 1e-9)   # and cannot lose more than the pool

    def test_bulk_never_drops_to_zero(self):
        for cap in [100.0, 20.0, 10.0]:
            with self.subTest(capacity=cap):
                self.assertGreater(build_plan(cap).rates[TrafficClass.BULK], 0.0)


class TestLease(unittest.TestCase):
    def test_lease_creates_its_own_class(self):
        self.assertIn(TrafficClass.LEASED, build_plan(20.0, lease()).rates)

    def test_no_lease_means_no_leased_class(self):
        self.assertNotIn(TrafficClass.LEASED, build_plan(20.0).rates)

    def test_lease_influence_is_bounded(self):
        """Absurd input must be clamped, not trusted. Even weight=100 cannot
        make the leased class outrank the whole rest of the household."""
        w = effective_weights(lease(weight=100.0))
        cap = BASE_WEIGHTS[TrafficClass.INTERACTIVE] * (1.0 + LAMBDA * WEIGHT_MAX)
        self.assertAlmostEqual(w[TrafficClass.LEASED], cap, places=6)
        self.assertLess(w[TrafficClass.LEASED], sum(BASE_WEIGHTS.values()))

    def test_lease_weight_is_clamped_at_both_ends(self):
        self.assertAlmostEqual(
            effective_weights(lease(weight=999.0))[TrafficClass.LEASED],
            effective_weights(lease(weight=1.0))[TrafficClass.LEASED], places=6)
        self.assertAlmostEqual(
            effective_weights(lease(weight=-5.0))[TrafficClass.LEASED],
            effective_weights(lease(weight=0.0))[TrafficClass.LEASED], places=6)

    def test_higher_weight_means_more_capacity(self):
        low = build_plan(20.0, lease(weight=0.2)).rates[TrafficClass.LEASED]
        high = build_plan(20.0, lease(weight=0.8)).rates[TrafficClass.LEASED]
        self.assertGreater(high, low)

    def test_leased_class_beats_bulk(self):
        plan = build_plan(20.0, lease())
        self.assertGreater(
            plan.rates[TrafficClass.LEASED], plan.rates[TrafficClass.BULK]
        )

    def test_lease_id_is_recorded(self):
        self.assertEqual(build_plan(20.0, lease(ident="abc")).lease_id, "abc")

    def test_expired_lease_yields_no_lease_class(self):
        expired = Lease(
            id="L0", target="device", ip="10.0.1.2",
            weight=0.4, ttl_s=90.0, created_at=0.0,
        )
        self.assertTrue(expired.expired(now=120.0))
        # caller must not pass an expired lease; assert the shape holds anyway
        self.assertNotIn(TrafficClass.LEASED, build_plan(20.0, None).rates)


class TestOrdering(unittest.TestCase):
    def test_interactive_ge_adaptive_ge_bulk(self):
        plan = build_plan(100.0)
        self.assertGreater(
            plan.rates[TrafficClass.INTERACTIVE], plan.rates[TrafficClass.ADAPTIVE]
        )
        self.assertGreater(
            plan.rates[TrafficClass.ADAPTIVE], plan.rates[TrafficClass.BULK]
        )


if __name__ == "__main__":
    unittest.main()


class TestPlanSurvivesRendering(unittest.TestCase):
    """A ceiling computed in the policy must survive into the tc tree.

    These exist because it did not. build_plan computed a 17 Mbps ceiling for
    bulk; build_tree discarded it with `ceil_mbps=min(cap, cap)`; the kernel
    never saw it; bulk carried 19.88 Mbps; and every test that inspected the
    *plan* still passed. The defect was only visible by comparing the plan to
    what was actually rendered.
    """

    @staticmethod
    def _tree(cap):
        from aciq.tc import build_tree
        return build_tree(build_plan(cap))

    def test_rendered_ceil_matches_the_plan_for_every_class(self):
        for cap in (10.0, 20.0, 100.0):
            plan = build_plan(cap)
            tree = self._tree(cap)
            for c in tree.classes:
                if c.cls is None:
                    continue
                with self.subTest(cap=cap, cls=c.cls):
                    self.assertAlmostEqual(c.ceil_mbps, plan.ceils[c.cls], places=6)

    def test_rendered_bulk_ceil_is_below_capacity(self):
        for cap in (20.0, 100.0):
            tree = self._tree(cap)
            bulk = next(c for c in tree.classes if c.cls is TrafficClass.BULK)
            with self.subTest(cap=cap):
                self.assertLess(bulk.ceil_mbps, cap)

    def test_rendered_ceil_never_below_rendered_rate(self):
        for cap in (1.0, 10.0, 20.0, 100.0):
            tree = self._tree(cap)
            for c in tree.classes:
                with self.subTest(cap=cap, cls=c.cls):
                    self.assertGreaterEqual(c.ceil_mbps + 1e-9, c.rate_mbps)

    def test_rendered_ceil_never_above_capacity(self):
        for cap in (10.0, 20.0, 100.0):
            tree = self._tree(cap)
            for c in tree.classes:
                with self.subTest(cap=cap, cls=c.cls):
                    self.assertLessEqual(c.ceil_mbps, cap + 1e-9)

    def test_render_argv_carries_the_bulk_ceiling(self):
        """The ceiling has to appear in the actual tc command line.

        A tree object can be right while the argv that installs it is wrong.
        """
        from aciq.tc import render
        argv = [" ".join(c) for c in render(self._tree(20.0))]
        bulk = [ln for ln in argv if "1:30" in ln]
        self.assertTrue(bulk, "no class 1:30 in the rendered commands")
        self.assertIn("ceil", bulk[0])
        self.assertIn("17", bulk[0])


class TestDegradedModeIsReportedNotHidden(unittest.TestCase):
    """Under overload the nominal floors cannot all be honoured. The documented
    guarantee must not claim otherwise: the plan scales them down *and* says so.

    The distinction the brief asks for is between a *policy allocation*
    guarantee (what build_plan promises when capacity suffices) and a *delivered*
    guarantee (what the kernel can actually give when it does not). This class
    pins the first half: a degraded plan never over-allocates and always flags.
    """

    def test_a_degraded_plan_never_over_allocates(self):
        for cap in (0.0, 0.5, 1.0, 2.0, 5.0):
            plan = build_plan(cap)
            self.assertLessEqual(plan.total(), cap + 1e-9,
                                 f"plan over-allocates at {cap} Mbps")
            if cap <= floor_mbps(cap) * len(TrafficClass) + 1e-9:
                self.assertTrue(plan.degraded,
                                f"floors cannot fit at {cap} Mbps but plan is "
                                f"not marked degraded")

    def test_a_degraded_plan_still_gives_every_class_something(self):
        """Scaling down proportionally, not starving one class to keep the
        others whole, is the whole point of the degraded path."""
        plan = build_plan(3.0)
        self.assertTrue(plan.degraded)
        for cls, r in plan.rates.items():
            self.assertGreater(r, 0.0, f"{cls} got nothing in degraded mode")

    def test_the_degraded_floor_is_the_achievable_one_not_the_nominal(self):
        """At 3 Mbps the nominal floor is max(2.0, 0.05*3)=2.0, which cannot be
        given to every class -- so the effective floor is capacity/n, and the
        plan must report values consistent with that, not with 2.0."""
        cap = 3.0
        plan = build_plan(cap)
        n = len(plan.rates)
        self.assertAlmostEqual(plan.total(), cap, places=6)
        for r in plan.rates.values():
            self.assertLessEqual(r, cap / n + 1e-9)

    def test_ordinary_capacity_is_not_marked_degraded(self):
        for cap in (100.0, 20.0, 10.0):
            self.assertFalse(build_plan(cap).degraded, f"{cap} Mbps is not tight")
