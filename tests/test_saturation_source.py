"""Option A: external congestion is judged by the external bottleneck.

THE DEFECT

`Measurement.saturated` consulted the controller's OWN parent class before the
out-of-band bottleneck. Under the differentiated-ceiling policy the sum of
child ceilings always exceeds the parent rate, so class 1:1 is overlimit by
construction:

    build_plan(estimate=20.26)
      -> 1:1 rate  = 20
      -> children  = bulk 17.0 + adaptive 6.0 + interactive 10.0 = 33
      -> 33 > 20  -> overlimit every tick, permanently

The controller therefore reported congestion caused by its own shaping, a
stale estimate made that self-sustaining, and the capacity-release path could
never start. Measured on the host: the link was restored to 100 Mbps and
`saturated` stayed True on every tick from t=30 to t=59.5.

THE FIX

When the bottleneck can be read it decides, alone. When it cannot be read the
old order stands, because both telemetry fields are Optional and `None` is
genuinely distinguishable from `0` -- before `set_capacity` installs the netem
qdisc, `tc -s qdisc show` reports `qdisc noqueue` with no backlog line at all.

Missing telemetry must never be read as a clear link, which is the whole reason
the fallback exists.
"""
import unittest

from aciq.capacity import SAT_OVERLIMIT_MIN, CapacityEstimator, Measurement


def _m(**kw):
    return Measurement(**kw)


class TestSelfInducedParentOverlimitsDoNotAssertCongestion(unittest.TestCase):
    """The defect, stated as a test."""

    def test_parent_overlimit_alone_does_not_saturate(self):
        m = _m(t=1.0, goodput_mbps=17.0,
               link_overlimit_rate_per_s=SAT_OVERLIMIT_MIN * 2,
               bottleneck_backlog_bytes=0)
        self.assertFalse(m.saturated,
                         "an intentional parent overlimit was read as external "
                         "congestion -- this is the defect")

    def test_parent_overlimit_with_no_bottleneck_telemetry_keeps_the_old_behaviour(self):
        """The fallback must stay conservative, not silently permissive."""
        m = _m(t=1.0, goodput_mbps=17.0,
               link_overlimit_rate_per_s=SAT_OVERLIMIT_MIN * 2,
               bottleneck_backlog_bytes=None,
               bottleneck_drop_rate_per_s=None)
        self.assertTrue(m.saturated,
                        "with no external telemetry the parent signal must "
                        "still be honoured -- missing telemetry is not a clear "
                        "link")

    def test_self_induced_overlimits_do_not_drag_the_estimate_down(self):
        """End to end: our own shaping must not read as congestion.

        The estimate is learned from a saturated link, so a stream of CLEAR
        samples carrying heavy parent overlimits must leave it exactly where it
        was. If parent overlimits still counted, the samples would not be
        clear, the estimator would see 30 Mbps as the capacity, and the whole
        model would contract toward our own ceil -- the defect in miniature.
        """
        e = CapacityEstimator()
        t = 0.0
        for _ in range(4):
            e.observe(_m(t=t, goodput_mbps=100.0, bottleneck_backlog_bytes=40000))
            t += 1.0
        before = e.current.mbps
        for _ in range(20):
            e.observe(_m(t=t, goodput_mbps=30.0,
                         link_overlimit_rate_per_s=SAT_OVERLIMIT_MIN * 3,
                         bottleneck_backlog_bytes=0))
            t += 1.0
        self.assertAlmostEqual(e.current.mbps, before, places=6,
                               msg="the estimator was dragged down by the "
                                   "controller's own shaping")


class TestGenuineExternalCongestionIsStillDetected(unittest.TestCase):
    """Option A must not have made the controller blind."""

    def test_backlog_alone_saturates(self):
        self.assertTrue(_m(t=1.0, goodput_mbps=20.0,
                           bottleneck_backlog_bytes=40000).saturated)

    def test_drops_alone_saturate(self):
        self.assertTrue(_m(t=1.0, goodput_mbps=20.0,
                           bottleneck_drop_rate_per_s=0.5,
                           bottleneck_backlog_bytes=0).saturated)

    def test_sustained_backlog_prevents_a_capacity_increase(self):
        e = CapacityEstimator()
        t = 0.0
        # A rate is only LEARNED from a saturated link -- that is the whole
        # design. Establishing 100 Mbps therefore needs a non-empty queue;
        # seeding it with backlog=0 would leave the estimate at 0 and the test
        # would be measuring nothing.
        for _ in range(4):
            e.observe(_m(t=t, goodput_mbps=100.0, bottleneck_backlog_bytes=40000))
            t += 1.0
        high = e.current.mbps
        self.assertAlmostEqual(high, 100.0, places=6, msg="precondition")
        # The link is genuinely congested: it must not drift upward.
        for _ in range(40):
            e.observe(_m(t=t, goodput_mbps=20.0, bottleneck_backlog_bytes=40000))
            t += 1.0
        self.assertLessEqual(e.current.mbps, high + 1e-6,
                             "capacity rose while the external link was "
                             "demonstrably congested")

    def test_child_backlog_still_counts_when_there_is_no_bottleneck(self):
        m = _m(t=1.0, goodput_mbps=5.0,
               link_overlimit_rate_per_s=0.0,
               link_drop_rate_per_s=0.0,
               bottleneck_backlog_bytes=None,
               child_backlog_bytes=10_000_000)
        self.assertTrue(m.saturated)


class TestMeasurementSourceSelection(unittest.TestCase):
    def test_bottleneck_decides_when_either_field_is_readable(self):
        """Drop rate readable, backlog not: still the bottleneck's call."""
        m = _m(t=1.0, goodput_mbps=5.0,
               link_overlimit_rate_per_s=SAT_OVERLIMIT_MIN * 5,
               bottleneck_backlog_bytes=None,
               bottleneck_drop_rate_per_s=0.0)
        self.assertFalse(m.saturated)

    def test_neither_field_readable_is_the_fallback_case(self):
        m = _m(t=1.0, goodput_mbps=5.0,
               link_overlimit_rate_per_s=SAT_OVERLIMIT_MIN * 5,
               bottleneck_backlog_bytes=None,
               bottleneck_drop_rate_per_s=None)
        self.assertTrue(m.saturated)

    def test_no_reader_at_all_is_not_saturated(self):
        """Blind reader keeps the original safe default."""
        m = _m(t=1.0, goodput_mbps=5.0,
               link_overlimit_rate_per_s=None,
               link_drop_rate_per_s=None,
               bottleneck_backlog_bytes=None,
               bottleneck_drop_rate_per_s=None)
        self.assertFalse(m.saturated)


class TestStartupBeforeTheBottleneckExists(unittest.TestCase):
    """`qdisc noqueue` has no backlog line, so both fields are None."""

    def test_startup_detection_still_works(self):
        e = CapacityEstimator()
        t = 0.0
        # Before set_capacity: no netem qdisc, parent is the only evidence.
        for _ in range(4):
            e.observe(_m(t=t, goodput_mbps=100.0,
                         link_overlimit_rate_per_s=SAT_OVERLIMIT_MIN * 2,
                         bottleneck_backlog_bytes=None,
                         bottleneck_drop_rate_per_s=None))
            t += 1.0
        self.assertGreater(e.current.mbps, 50.0,
                           "startup detection at 100 Mbps regressed")

    def test_transitions_cleanly_when_the_bottleneck_appears(self):
        e = CapacityEstimator()
        t = 0.0
        for _ in range(4):
            e.observe(_m(t=t, goodput_mbps=100.0,
                         link_overlimit_rate_per_s=SAT_OVERLIMIT_MIN * 2,
                         bottleneck_backlog_bytes=None))
            t += 1.0
        for _ in range(4):
            e.observe(_m(t=t, goodput_mbps=100.0, bottleneck_backlog_bytes=40000))
            t += 1.0
        self.assertGreater(e.current.mbps, 50.0,
                           "the estimate collapsed when the bottleneck "
                           "appeared on a wide, busy link")


class TestFailedWorkaroundsHaveNotReturned(unittest.TestCase):
    """None of the three failed attempts may creep back in.

    Recorded in docs/gap-closure/capacity-recovery-defect.md:

      1. release on any sustained non-saturation  -> oscillated upward
      2. require throughput > 1.5x the estimate  -> unreachable, the
         controller throttles itself below the link
      3. rise-slow / fall-fast asymmetry          -> sound, but `saturated`
         never went false, so it never ran

    Option A removes the cause instead. These pin that the removed constants
    stay removed, so nobody re-introduces them as a substitute.
    """

    def test_the_unreachable_throughput_ratio_is_gone(self):
        import aciq.capacity as cap
        self.assertFalse(hasattr(cap, "RELEASE_EVIDENCE_RATIO"),
                         "the throughput-ratio release condition has returned; "
                         "it can never be satisfied by a self-throttling "
                         "controller")

    def test_release_still_obeys_the_dwell_and_hysteresis(self):
        """Asymmetry must not have bypassed the anti-oscillation rules."""
        import aciq.capacity as cap
        self.assertLess(cap.RELEASE_ALPHA, cap.FAST_DROP_RATIO,
                        "rising must remain slower than falling")
        self.assertGreater(cap.IDLE_STREAK_RELEASE, 1)
        self.assertGreater(cap.MIN_DWELL_S, 0.0)

    def test_no_release_happens_on_a_single_clear_sample(self):
        e = CapacityEstimator()
        t = 0.0
        for _ in range(4):
            e.observe(_m(t=t, goodput_mbps=100.0, bottleneck_backlog_bytes=40000))
            t += 1.0
        for _ in range(4):
            e.observe(_m(t=t, goodput_mbps=20.0, bottleneck_backlog_bytes=40000))
            t += 1.0
        low = e.current.mbps
        e.observe(_m(t=t, goodput_mbps=20.0, bottleneck_backlog_bytes=0))
        self.assertAlmostEqual(e.current.mbps, low, places=6,
                               msg="one clear sample moved the estimate")


if __name__ == "__main__":
    unittest.main()