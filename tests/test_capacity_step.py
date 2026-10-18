"""A capacity step change must not be smoothed like noise.

Measured on the host before this change: with ALPHA_DOWN 0.6 the EWMA needed six
ticks to walk a 100 Mbps estimate down to a true 20 --

    52.0 -> 32.8 -> 25.1 -> 22.1 -> 20.8 -> 20.3

-- which is the 5.4 s convergence observed in the congested runs and the source
of the residual latency tail. For that whole window the controller is serving an
estimate roughly three to five times larger than the real link.

Smoothing is correct for noise and wrong for a step. These tests pin both
directions: a genuine step is adopted at once, and ordinary jitter is still
smoothed, so the fix does not buy speed by reintroducing flapping.
"""
import unittest

from aciq.capacity import (ALPHA_DOWN, ALPHA_UP, FAST_DROP_RATIO,
                           CapacityEstimator, Measurement)


def _sat(t, mbps, **kw):
    """A saturated reading.

    `saturated` is a derived property, not a field: it is true when the link is
    overlimit, dropping, or -- the common case on this testbed -- when the
    out-of-band bottleneck has a queue it cannot drain. Backlog is the signal
    used here.
    """
    # The property bails out early unless the PARENT counters are present --
    # with both None it treats the reader as blind and refuses to declare
    # saturation, which is the safe direction. So a saturated reading has to
    # supply them.
    kw.setdefault("link_overlimit_rate_per_s", 3000.0)
    kw.setdefault("bottleneck_backlog_bytes", 40000)
    return Measurement(t=t, goodput_mbps=mbps, **kw)


def _idle(t, mbps, **kw):
    kw.setdefault("bottleneck_backlog_bytes", 0)
    kw.setdefault("link_overlimit_rate_per_s", 0.0)
    return Measurement(t=t, goodput_mbps=mbps, **kw)


class TestCapacityStepIsNotSmoothed(unittest.TestCase):
    def _estimator_at(self, start_mbps):
        e = CapacityEstimator()
        e.observe(_sat(0.0, start_mbps))
        e.observe(_sat(1.0, start_mbps))
        return e

    def test_a_five_fold_drop_is_adopted_in_one_tick(self):
        e = self._estimator_at(100.0)
        before = e.current.mbps
        e.observe(_sat(10.0, 20.0))
        after = e.current.mbps
        self.assertGreater(before, 50.0, "precondition: the estimate was high")
        self.assertAlmostEqual(after, 20.0, delta=1.0,
                               msg=f"one tick should land on the truth, got {after}")

    def test_convergence_ticks_drop_sharp(self):
        """The number the host run measured, pinned."""
        e = self._estimator_at(100.0)
        ticks = 0
        for t in range(10, 20):
            e.observe(_sat(float(t), 20.0))
            ticks += 1
            if abs(e.current.mbps - 20.0) <= 0.5:
                break
        self.assertLessEqual(ticks, 2,
                             f"took {ticks} ticks to converge on a 5x step")

    def test_a_drop_inside_the_fast_band_is_still_smoothed(self):
        """25% is well outside HYSTERESIS so the estimator does move, but it is
        above FAST_DROP_RATIO so it must be approached gradually, not snapped.
        """
        e = self._estimator_at(100.0)
        e.observe(_sat(10.0, 75.0))
        after = e.current.mbps
        self.assertLess(after, 100.0, "a 25% drop should move the estimate")
        self.assertGreater(after, 75.0,
                           "a 25% drop is not a step and must not be snapped")

    def test_a_sub_hysteresis_wobble_does_not_move_it_at_all(self):
        """HYSTERESIS is 0.10, so a 5% dip is deliberately ignored."""
        e = self._estimator_at(100.0)
        e.observe(_sat(10.0, 95.0))
        self.assertAlmostEqual(e.current.mbps, 100.0, places=6)

    def test_repeated_small_dips_do_not_flap(self):
        """Alternate +/-4% for a minute; the estimate must not track every wobble."""
        e = self._estimator_at(100.0)
        t = 10.0
        for i in range(24):
            e.observe(_sat(t, 104.0 if i % 2 else 96.0))
            t += 2.5
        final = e.current.mbps
        self.assertGreater(final, 97.0)
        self.assertLess(final, 103.0)

    def test_rising_link_is_never_snapped(self):
        """ALPHA_UP stays slow: a link that frees up must not be jumped to."""
        e = self._estimator_at(20.0)
        e.observe(_sat(10.0, 100.0))
        self.assertLess(e.current.mbps, 40.0,
                        "an increase must still be approached gradually")

    def test_the_threshold_is_a_majority_drop(self):
        self.assertLessEqual(FAST_DROP_RATIO, 0.7)
        self.assertGreater(FAST_DROP_RATIO, 0.4)

    def test_saturated_readings_are_still_required(self):
        """A single unsaturated sample must not be able to snap the estimate."""
        e = self._estimator_at(100.0)
        e.observe(_idle(10.0, 1.0))
        self.assertGreater(e.current.mbps, 90.0)


if __name__ == "__main__":
    unittest.main()