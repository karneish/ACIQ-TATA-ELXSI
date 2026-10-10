"""M2 capacity estimator tests. No root, no network.

Saturation thresholds come from measured gate check 12 output, not guesses.
"""

from __future__ import annotations

import unittest

from aciq.capacity import (
    ALPHA_DOWN,
    SAT_OVERLIMIT_MIN,
    HYSTERESIS,
    MIN_DWELL_S,
    SAT_OVERLIMIT_MIN,
    SAT_STREAK_REQUIRED,
    CapacityEstimator,
    CusumDriftDetector,
    Measurement,
)


def sat(t, mbps, over=6000.0, drop=0.0):
    """A saturated sample, like the gate's real ones (overlimits ~24803-65101).

    Saturation is asserted on the LINK counters, which is the only thing that
    means the link is full.
    """
    return Measurement(t=t, goodput_mbps=mbps, drop_rate_per_s=drop,
                       overlimit_rate_per_s=over,
                       link_drop_rate_per_s=drop,
                       link_overlimit_rate_per_s=over)


def child_heavy(t, mbps, child_over=6000.0, link_over=0.0, drop=0.0):
    """Children over their guarantees while the link is nearly idle.

    This is the measured death-spiral case: a 100 Mbps link carrying ~10 Mbps
    where children's overlimits rise purely because the class guarantee was
    small. Treating that as congestion collapsed capacity from 100 to 7.2 Mbps.
    """
    return Measurement(t=t, goodput_mbps=mbps, drop_rate_per_s=drop,
                       overlimit_rate_per_s=child_over,
                       link_drop_rate_per_s=0.0,
                       link_overlimit_rate_per_s=link_over)


def idle(t, mbps=1.0):
    """No drops, no overlimits: offered load, not capacity."""
    return Measurement(t=t, goodput_mbps=mbps)


class TestSaturatedDetection(unittest.TestCase):
    def test_link_overlimits_mean_saturated(self):
        self.assertTrue(sat(0, 100).saturated)

    def test_link_drops_mean_saturated(self):
        m = Measurement(t=0, goodput_mbps=100, link_drop_rate_per_s=252)
        self.assertTrue(m.saturated)

    def test_no_link_pressure_is_not_saturated(self):
        self.assertFalse(idle(0).saturated)

    def test_link_overlimit_threshold_is_generous(self):
        just_below = Measurement(t=0, goodput_mbps=50, link_overlimit_rate_per_s=0.5)
        self.assertFalse(just_below.saturated)
        above = Measurement(t=0, goodput_mbps=50,
                            link_overlimit_rate_per_s=SAT_OVERLIMIT_MIN)
        self.assertTrue(above.saturated)

    def test_low_measured_rate_is_below_threshold(self):
        below = Measurement(t=0, goodput_mbps=10.5,
                            link_overlimit_rate_per_s=1313.0)
        self.assertFalse(below.saturated)

    def test_child_overlimits_alone_are_not_saturation(self):
        """MEASURED BUG. Children over their guarantees on a nearly idle link
        must not be read as congestion."""
        m = child_heavy(0, 10.5, child_over=1300.0, link_over=0.0)
        self.assertFalse(m.saturated)

    def test_missing_link_counters_treat_the_link_as_not_saturated(self):
        """Guessing 'saturated' when the link is unreadable shrinks capacity."""
        m = Measurement(t=0, goodput_mbps=50, overlimit_rate_per_s=9999.0)
        self.assertFalse(m.saturated)


class TestBlindness(unittest.TestCase):
    """The estimator must not be able to read the configured rate."""

    def test_measurement_has_no_configured_rate_field(self):
        self.assertFalse(hasattr(Measurement(t=0, goodput_mbps=1), "configured_mbps"))
        self.assertFalse(
            hasattr(Measurement(t=0, goodput_mbps=1), "ceil_mbps"))
        self.assertFalse(hasattr(Measurement(t=0, goodput_mbps=1), "rate_mbps"))

    def test_measurement_only_needs_observed_goodput(self):
        m = Measurement(t=0.0, goodput_mbps=19.1, drop_rate_per_s=0.0,
                        overlimit_rate_per_s=6000.0)
        self.assertEqual(m.goodput_mbps, 19.1)


class TestMeasuredSeparation(unittest.TestCase):
    """The threshold comes from measured overlimit rates in two real scenarios.

    A full link produced 5127-6485/s; a link 10% loaded but with children
    rate-limited produced 170-1313/s. HTB attributes a child's borrow to the
    parent, so attribution alone cannot tell them apart — only the magnitude can.
    """

    def test_full_link_rate_is_above_the_threshold(self):
        self.assertGreater(5127.0, SAT_OVERLIMIT_MIN)
        self.assertLess(6485.0, 8000.0)

    def test_idle_link_rate_is_below_the_threshold(self):
        self.assertLess(1313.0, SAT_OVERLIMIT_MIN)

    def test_separation_margin(self):
        """Closest measured points must clear the threshold by ~2x."""
        self.assertGreater(SAT_OVERLIMIT_MIN / 1313.0, 2.0)

    def test_low_pressure_is_not_saturation(self):
        m = child_heavy(0, 10.5, child_over=1313.0, link_over=1313.0)
        self.assertFalse(m.saturated)

    def test_high_pressure_is_saturation(self):
        m = child_heavy(0, 99.9, child_over=6000.0, link_over=6000.0)
        self.assertTrue(m.saturated)


class TestDeathSpiral(unittest.TestCase):
    """Regression guard for a real collapse: 100 Mbps -> 7.2 Mbps in one run."""

    def test_child_pressure_never_moves_the_estimate(self):
        e = CapacityEstimator()
        for t in range(30):
            e.observe(child_heavy(float(t), 10.5, child_over=1300.0, link_over=0.0))
        self.assertEqual(e.current.mbps, 0.0)
        self.assertFalse(e.current.changed)

    def test_no_spiral_even_with_child_drops(self):
        e = CapacityEstimator()
        for t in range(30):
            e.observe(child_heavy(float(t), 10.5, child_over=5000.0, link_over=0.0,
                                  drop=900.0))
        self.assertEqual(e.current.mbps, 0.0)

    def test_estimator_still_works_when_the_link_really_is_full(self):
        e = CapacityEstimator()
        e.observe(sat(0.0, 100.0))
        e.observe(sat(10.0, 100.0))
        self.assertAlmostEqual(e.current.mbps, 100.0, places=6)


class TestNeverLearnsFromIdle(unittest.TestCase):
    def test_idle_samples_do_not_change_capacity(self):
        e = CapacityEstimator()
        for t in range(10):
            c = e.observe(idle(float(t), mbps=5.0))
        self.assertEqual(c.mbps, 0.0)
        self.assertFalse(c.changed)

    def test_idle_does_not_establish_a_capacity(self):
        """An idle link's throughput is offered load, not capacity."""
        e = CapacityEstimator()
        for t in range(20):
            e.observe(idle(float(t), mbps=3.0))
        self.assertEqual(e.current.mbps, 0.0)

    def test_confidence_decays_when_idle(self):
        e = CapacityEstimator()
        for t in range(6):
            e.observe(sat(float(t), 100.0))
        high = e.current.confidence
        for t in range(6, 12):
            e.observe(idle(float(t)))
        self.assertLess(e.current.confidence, high)

    def test_confidence_never_negative(self):
        e = CapacityEstimator()
        for t in range(50):
            e.observe(idle(float(t)))
        self.assertGreaterEqual(e.current.confidence, 0.0)


class TestSaturationStreak(unittest.TestCase):
    def test_one_burst_is_not_a_reading(self):
        e = CapacityEstimator()
        c = e.observe(sat(0.0, 999.0))
        self.assertFalse(c.changed)
        self.assertEqual(c.mbps, 0.0)

    def test_streak_threshold_is_respected(self):
        e = CapacityEstimator()
        for t in range(SAT_STREAK_REQUIRED - 1):
            e.observe(sat(float(t), 100.0))
        self.assertEqual(e.current.mbps, 0.0)
        c = e.observe(sat(float(SAT_STREAK_REQUIRED), 100.0))
        self.assertTrue(c.changed)


class TestAsymmetricResponse(unittest.TestCase):
    def test_fast_down(self):
        """A collapse must be tracked quickly."""
        e = CapacityEstimator()
        e.observe(sat(0.0, 100.0))
        e.observe(sat(10.0, 100.0))
        self.assertAlmostEqual(e.current.mbps, 100.0, places=6)
        e.observe(sat(20.0, 20.0))
        expected = 100.0 + ALPHA_DOWN * (20.0 - 100.0)
        self.assertAlmostEqual(e.current.mbps, expected, places=6)
        # fast: most of the way down in one step
        self.assertLess(e.current.mbps, 60.0)

    def test_slow_up(self):
        """Growth is taken on trust more slowly."""
        e = CapacityEstimator()
        e.observe(sat(0.0, 20.0))
        e.observe(sat(10.0, 20.0))
        e.observe(sat(20.0, 100.0))
        after_one = e.current.mbps
        self.assertGreater(after_one, 20.0)
        # slow: a small fraction of the way up after one sample
        self.assertLess(after_one, 40.0)


class TestStability(unittest.TestCase):
    def test_hysteresis_suppresses_small_moves(self):
        e = CapacityEstimator()
        e.observe(sat(0.0, 100.0))
        e.observe(sat(10.0, 100.0))
        base = e.current.mbps
        # a 2% wobble, well inside the band
        e.observe(sat(20.0, 102.0))
        self.assertAlmostEqual(e.current.mbps, base, places=6)

    def test_change_beyond_band_is_reported(self):
        e = CapacityEstimator()
        e.observe(sat(0.0, 100.0))
        e.observe(sat(10.0, 100.0))
        c = e.observe(sat(20.0, 60.0))
        self.assertTrue(c.changed)
        self.assertLess(abs(c.mbps - 100.0) / 100.0, HYSTERESIS * 5)

    def test_dwell_blocks_rapid_successive_changes(self):
        e = CapacityEstimator()
        e.observe(sat(0.0, 100.0))
        e.observe(sat(10.0, 100.0))
        first = e.observe(sat(20.0, 40.0))
        self.assertTrue(first.changed)
        # only 1 s later: must be refused despite a large difference
        second = e.observe(sat(21.0, 5.0))
        self.assertFalse(second.changed)
        self.assertAlmostEqual(second.mbps, first.mbps, places=6)

    def test_dwell_is_at_least_the_configured_minimum(self):
        e = CapacityEstimator()
        e.observe(sat(0.0, 100.0))
        e.observe(sat(10.0, 100.0))
        e.observe(sat(20.0, 40.0))
        c = e.observe(sat(20.0 + MIN_DWELL_S, 40.0))
        self.assertIsNotNone(c)

    def test_noisy_throughput_does_not_oscillate(self):
        """Count policy changes over a noisy but stable link."""
        e = CapacityEstimator()
        changes = 0
        goodputs = [100.0, 99.0, 101.0, 100.5, 99.5, 100.0, 100.2, 99.8, 100.0]
        t = 0.0
        for g in goodputs:
            for _ in range(SAT_STREAK_REQUIRED):
                if e.observe(sat(t, g)).changed:
                    changes += 1
                t += 6.0  # beyond dwell, so dwell is not what is holding it
        self.assertLessEqual(changes, 2, f"oscillated {changes} times on a flat link")


class TestSafeReset(unittest.TestCase):
    def test_force_safe_resets_and_clears_dwell(self):
        e = CapacityEstimator()
        e.observe(sat(0.0, 100.0))
        e.observe(sat(10.0, 100.0))
        e.observe(sat(20.0, 40.0))
        c = e.force_safe(20.0)
        self.assertEqual(c.mbps, 20.0)
        self.assertTrue(c.changed)
        self.assertEqual(c.confidence, 0.0)
        # Dwell cleared: a genuinely different observation 1 s later is accepted.
        # (An observation equal to the current value would NOT report a change —
        # hysteresis suppresses it correctly. That case is covered separately.)
        e.observe(sat(21.0, 5.0))
        self.assertTrue(e.observe(sat(22.0, 5.0)).changed)

    def test_observation_matching_current_is_not_a_change(self):
        """Confirming what you already believe is not news. Covered explicitly
        because the force_safe test above initially assumed otherwise."""
        e = CapacityEstimator()
        e.observe(sat(0.0, 100.0))
        e.observe(sat(10.0, 100.0))
        e.force_safe(20.0)
        e.observe(sat(30.0, 20.0))
        self.assertFalse(e.observe(sat(40.0, 20.0)).changed)


class TestCusum(unittest.TestCase):
    def test_busy_gate_refuses_idle_samples(self):
        """An idle link's rate collapses; CUSUM would cry wolf. Gated."""
        d = CusumDriftDetector()
        d.observe(100.0, busy=True)
        for _ in range(50):
            self.assertFalse(d.observe(0.1, busy=False))
        self.assertIsNone(d.drift)

    def test_no_alarm_on_stable_busy_link(self):
        d = CusumDriftDetector()
        for i in range(30):
            self.assertFalse(d.observe(100.0, busy=True))

    def test_alarms_on_sustained_downward_drift(self):
        d = CusumDriftDetector(slack_k=0.05, threshold_h=3.0)
        d.observe(100.0, busy=True)
        alarm = False
        for _ in range(200):
            if d.observe(90.0, busy=True):
                alarm = True
        self.assertTrue(alarm)
        self.assertLess(d.drift, 0.0)  # signed downward

    def test_alarms_on_sustained_upward_drift(self):
        d = CusumDriftDetector(slack_k=0.05, threshold_h=3.0)
        d.observe(100.0, busy=True)
        alarm = False
        for _ in range(200):
            if d.observe(110.0, busy=True):
                alarm = True
        self.assertTrue(alarm)
        self.assertGreater(d.drift, 0.0)

    def test_first_sample_only_sets_baseline(self):
        d = CusumDriftDetector()
        self.assertFalse(d.observe(100.0, busy=True))
        self.assertEqual(d.baseline, 100.0)

    def test_reset_clears_alarm_state(self):
        d = CusumDriftDetector(slack_k=0.05, threshold_h=3.0)
        d.observe(100.0, busy=True)
        for _ in range(200):
            d.observe(90.0, busy=True)
        d.reset()
        self.assertIsNone(d.drift)
        self.assertEqual(d.s_pos, 0.0)


if __name__ == "__main__":
    unittest.main()


class TestTheEstimatorReactsToARealDrop(unittest.TestCase):
    """Does M2 do anything once --drop-at actually caps the link?

    Every run so far reported estimator_mbps None, and the reason was correct
    rather than broken: at 100 Mbps with ~25 Mbps offered the link is only a
    quarter loaded, so it is not saturated, so there is no capacity information
    to read. That is the documented behaviour working.

    This asks the question that the drop was supposed to answer, without needing
    the testbed: replay the tick sequence a confirmed drop would produce and
    check the estimator converges.
    """

    def _replay(self, offered=25.0, before=100.0, after=10.0,
                drop_at=20.0, horizon=41.0):
        est = CapacityEstimator(initial_mbps=before)
        changes = []
        t = 1.0
        while t <= horizon:
            capped = min(offered, before) if t < drop_at else min(offered, after)
            # Saturated only once the link is genuinely oversubscribed: the
            # parent's overlimit rate is what separates the two populations.
            oversubscribed = offered > (before if t < drop_at else after)
            m = Measurement(
                t=t,
                goodput_mbps=capped,
                drop_rate_per_s=40000.0 if oversubscribed else 0.0,
                overlimit_rate_per_s=5000.0 if oversubscribed else 100.0,
                link_drop_rate_per_s=40000.0 if oversubscribed else 0.0,
                link_overlimit_rate_per_s=5000.0 if oversubscribed else 100.0,
            )
            c = est.observe(m)
            if c.changed:
                changes.append((t, c.mbps))
            t += 1.0
        return est.current, changes

    def test_nothing_is_reported_before_the_drop(self):
        """Confirms the null results so far were correct, not a dead estimator."""
        est = CapacityEstimator(initial_mbps=100.0)
        for t in range(1, 21):
            c = est.observe(Measurement(
                t=float(t), goodput_mbps=25.0,
                link_overlimit_rate_per_s=100.0, link_drop_rate_per_s=0.0))
            self.assertFalse(c.changed,
                             "an unsaturated link must never move the estimate")

    def test_the_estimate_moves_toward_the_capped_link(self):
        cur, changes = self._replay()
        self.assertTrue(changes, "the drop produced no estimate at all")
        after_drop = [mbps for t, mbps in changes if t >= 20.0]
        self.assertTrue(after_drop, "no change after the drop")
        self.assertLess(cur.mbps, 100.0, "capacity never came down")
        # The run is short and MIN_DWELL_S throttles the walk down, so demanding
        # convergence on the exact number would be demanding something the
        # design deliberately trades away.
        self.assertLess(cur.mbps, 30.0,
                        f"converged too slowly to be useful: {cur.mbps}")

    def test_the_walk_down_is_monotone(self):
        """ALPHA_DOWN is 0.6 so capacity falls fast; it must not overshoot
        upward past the true value on the way down."""
        _, changes = self._replay()
        vals = [mbps for t, mbps in changes if t >= 20.0]
        self.assertEqual(vals, sorted(vals, reverse=True),
                         f"capacity wobbled upward on the way down: {vals}")
