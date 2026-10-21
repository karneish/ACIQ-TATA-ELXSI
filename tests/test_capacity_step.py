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

from aciq.capacity import (FAST_DROP_RATIO,
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
    # Genuine external congestion: the out-of-band queue is non-empty. Option A
    # makes that the authority, so parent overlimits alone must NOT be used to
    # fake saturation here.
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

class TestCapacityCanRecover(unittest.TestCase):
    """A saturation-driven estimator can only learn that a link got SLOWER.

    A saturated link has no spare capacity by definition, so once the estimate
    has collapsed it holds forever: nothing in a non-saturated sample carries
    information about capacity.

    That was not theorised. A recovery run restored the link to 100 Mbps and the
    steady goodput afterwards was 17.33 Mbps -- exactly the degraded ceiling of
    0.85 x 20. The controller never walked back up, and a user whose ISP
    restored their line would stay throttled indefinitely.
    """

    @staticmethod
    def _drop_then_recover(e):
        """100 Mbps saturated, then a 20 Mbps drop, then the link opens up."""
        t = 0.0
        for _ in range(4):
            e.observe(_sat(t, 100.0)); t += 1.0
        for _ in range(4):
            e.observe(_sat(t, 20.0)); t += 1.0
        return t

    def test_the_estimate_falls_on_a_drop(self):
        e = CapacityEstimator()
        self._drop_then_recover(e)
        self.assertLess(e.current.mbps, 40.0, "precondition: the drop landed")

    def test_the_estimate_recovers_toward_the_high_water_mark(self):
        e = CapacityEstimator()
        t = self._drop_then_recover(e)
        degraded = e.current.mbps
        # The link opens up: unsaturated, and carrying much more than the
        # degraded estimate says exists.
        for _ in range(60):
            e.observe(Measurement(t=t, goodput_mbps=70.0,
                                  bottleneck_backlog_bytes=0))
            t += 1.0
        self.assertGreater(e.current.mbps, degraded * 1.5,
                           "the estimate never recovered after the link did")
        self.assertGreater(e.current.mbps, 40.0)

    def test_recovery_never_exceeds_the_high_water_mark(self):
        e = CapacityEstimator()
        t = self._drop_then_recover(e)
        for _ in range(200):
            e.observe(Measurement(t=t, goodput_mbps=90.0,
                                  bottleneck_backlog_bytes=0))
            t += 1.0
        self.assertLessEqual(e.current.mbps, 100.0 + 1e-6,
                             "the release invented capacity above anything "
                             "ever observed")

    def test_a_brief_lull_does_not_release(self):
        """A burst-sized gap between congested samples must not undo a drop.

        This is the anti-oscillation property that matters. Sustained
        non-congestion IS grounds for release now -- the controller throttles
        itself below the link, so throughput evidence is unreachable -- but only
        after IDLE_STREAK_RELEASE samples of it. A short gap must not qualify,
        or the recorded-run suite wobbles upward on the way down.
        """
        from aciq.capacity import IDLE_STREAK_RELEASE
        e = CapacityEstimator()
        t = self._drop_then_recover(e)
        before = e.current.mbps
        for _ in range(IDLE_STREAK_RELEASE - 3):
            e.observe(Measurement(t=t, goodput_mbps=12.0,
                                  bottleneck_backlog_bytes=0))
            t += 1.0
        self.assertAlmostEqual(
            e.current.mbps, before, delta=0.5,
            msg="a lull shorter than IDLE_STREAK_RELEASE triggered a release")

    def test_an_incorrect_release_self_corrects(self):
        """The whole safety argument: rising is slow, falling is fast.

        A release that turns out to be wrong must not persist. Genuine external
        congestion -- a NON-EMPTY bottleneck queue -- has to collapse the
        estimate again, because that is what makes bounded optimism acceptable.

        Simulated through `bottleneck_backlog_bytes`, not through parent
        overlimits: under Option A a parent overlimit is no longer evidence of
        anything external, so using it here would test the wrong path.
        """
        e = CapacityEstimator()
        t = self._drop_then_recover(e)
        for _ in range(60):
            e.observe(Measurement(t=t, goodput_mbps=70.0,
                                  bottleneck_backlog_bytes=0))
            t += 1.0
        self.assertGreater(e.current.mbps, 40.0, "precondition: it released")
        # The link was never that wide after all: its queue fills.
        for _ in range(6):
            e.observe(Measurement(t=t, goodput_mbps=20.0,
                                  bottleneck_backlog_bytes=40000))
            t += 1.0
        self.assertLess(e.current.mbps, 40.0,
                        "an incorrect release did not self-correct")

    def test_an_idle_run_never_exceeds_the_high_water_mark(self):
        """The release is bounded above by what was actually observed."""
        e = CapacityEstimator()
        t = self._drop_then_recover(e)
        for _ in range(300):
            e.observe(Measurement(t=t, goodput_mbps=0.0,
                                  bottleneck_backlog_bytes=0))
            t += 1.0
        self.assertLessEqual(e.current.mbps, 100.0 + 1e-6)

    def test_release_is_bounded_because_falling_is_fast(self):
        """An incorrect release must be self-correcting, not sticky."""
        from aciq.capacity import FAST_DROP_RATIO, RELEASE_ALPHA
        self.assertGreater(FAST_DROP_RATIO, RELEASE_ALPHA,
                           "rising must be slower than falling, or a bad "
                           "release would persist instead of self-correcting")


class TestASingleBlipDoesNotCancelRecovery(unittest.TestCase):
    """A rate limiter's queue is briefly non-empty all the time.

    Measured on the host after a real recovery: 3028 bytes -- about two packets
    -- on ticks scattered through an otherwise completely clear link, while the
    netem state read `limit 416 rate 100Mbit dropped 0 backlog 0b 0p` on the
    ticks around it.

    Each blip cleared `_idle_streak`, so ten consecutive clear ticks never
    accumulated and capacity stayed pinned at the degraded rate for the 30 s
    after the link came back.

    This is the same "one burst is not a reading" principle the saturation
    streak already encodes, applied consistently: a single sample must not
    cancel a recovery any more than it may trigger an adaptation.
    """

    @staticmethod
    def _dropped_then_clear(e, t):
        for _ in range(4):
            e.observe(_sat(t, 100.0)); t += 1.0
        for _ in range(4):
            e.observe(_sat(t, 20.0)); t += 1.0
        return t

    def test_one_isolated_backlog_sample_does_not_cancel_the_streak(self):
        from aciq.capacity import IDLE_STREAK_RELEASE
        e = CapacityEstimator()
        t = self._dropped_then_clear(e, 0.0)
        low = e.current.mbps
        # Alternate clear/blip for enough ticks that IDLE_STREAK_RELEASE clear
        # samples DO accumulate. Half the ticks are clear, so twice the
        # threshold in iterations is the minimum that can possibly qualify.
        for _ in range(IDLE_STREAK_RELEASE * 2):
            e.observe(Measurement(t=t, goodput_mbps=20.0,
                                  bottleneck_backlog_bytes=0))
            t += 1.0
            e.observe(Measurement(t=t, goodput_mbps=20.0,
                                  bottleneck_backlog_bytes=3028))
            t += 1.0
        self.assertGreater(e.current.mbps, low,
                           "isolated backlog blips cancelled the release; a "
                           "two-packet residual queue is not congestion")

    def test_sustained_backlog_still_cancels_the_streak(self):
        """The fix must not weaken genuine congestion detection."""
        e = CapacityEstimator()
        t = self._dropped_then_clear(e, 0.0)
        low = e.current.mbps
        for _ in range(20):
            e.observe(Measurement(t=t, goodput_mbps=20.0,
                                  bottleneck_backlog_bytes=40000))
            t += 1.0
        self.assertAlmostEqual(e.current.mbps, low, places=6,
                               msg="a genuinely congested link still allowed "
                                   "the estimate to rise")


class TestEmergencyFirstSampleAdoption(unittest.TestCase):
    """The transition-tail fix: a 5x step need not wait for the streak.

    SAT_STREAK_REQUIRED costs a full tick before a drop is adopted; during
    that tick policy still shapes bulk against the old estimate, the
    bottleneck queue fills, and interactive packets queue behind it -- the
    documented p95 spike at the start of each run.
    """

    def test_external_congestion_adopts_the_step_on_the_first_sample(self):
        from aciq.capacity import SAT_STREAK_REQUIRED
        e = CapacityEstimator()
        t = 0.0
        for _ in range(2):
            e.observe(_sat(t, 100.0)); t += 1.0
        self.assertAlmostEqual(e.current.mbps, 100.0)
        # the link goes idle: the streak resets, so the NEXT congested sample
        # is sample #1 of a new streak
        # long enough that the dwell window (MIN_DWELL_S) has also passed --
        # the emergency lifts the streak gate, it does not bypass dwell
        for _ in range(6):
            e.observe(_idle(t, 100.0)); t += 1.0
        self.assertEqual(e._sat_streak, 0)
        # ...and the step lands: full bottleneck queue, delivered rate a fifth
        # of the estimate. Without the emergency this would wait a tick at the
        # old 100 Mbps policy.
        c = e.observe(_sat(t, 20.0))
        self.assertTrue(c.changed,
                        "a 5x drop behind a full external queue must not wait "
                        f"for {SAT_STREAK_REQUIRED} samples")
        self.assertAlmostEqual(e.current.mbps, 20.0)

    def test_without_bottleneck_evidence_the_streak_still_gates(self):
        """The streak still guards the controller's own signals."""
        from aciq.capacity import SAT_STREAK_REQUIRED
        e = CapacityEstimator()
        t = 0.0
        for _ in range(2):
            e.observe(_sat(t, 100.0)); t += 1.0
        for _ in range(6):
            e.observe(_idle(t, 100.0)); t += 1.0
        # No bottleneck telemetry (both None = unreadable), so saturation comes
        # from the parent fallback alone; goodput is a fifth of the estimate.
        # Low throughput alone is a reason to wait, not to snap: the emergency
        # requires evidence the CONTROLLER cannot produce.
        c = e.observe(Measurement(t=t, goodput_mbps=20.0,
                                  link_overlimit_rate_per_s=5000.0,
                                  link_drop_rate_per_s=0.0))
        self.assertTrue(c.saturated, "the sample must actually be saturated "
                                     "or this tests the wrong path")
        self.assertFalse(c.changed)
        self.assertLess(e._sat_streak, SAT_STREAK_REQUIRED + 1)
        self.assertAlmostEqual(e.current.mbps, 100.0)

    def test_two_packet_blip_never_triggers_the_emergency(self):
        """The residue the host measured: 3028 bytes, dropped 0.

        During a release in progress (estimate climbing toward high water,
        delivered rate momentarily still at the old degraded value) a blip
        this size satisfied the original emergency condition and snapped the
        estimate straight back down -- the oscillation the single-blip tests
        exist to prevent. Depth or drops: never residue.
        """
        from aciq.capacity import IDLE_STREAK_RELEASE
        e = CapacityEstimator()
        t = 0.0
        for _ in range(4):
            e.observe(_sat(t, 100.0)); t += 1.0
        for _ in range(4):
            e.observe(_sat(t, 20.0)); t += 1.0
        low = e.current.mbps
        for _ in range(IDLE_STREAK_RELEASE * 2):
            e.observe(Measurement(t=t, goodput_mbps=20.0,
                                  bottleneck_backlog_bytes=0)); t += 1.0
            e.observe(Measurement(t=t, goodput_mbps=20.0,
                                  bottleneck_backlog_bytes=3028)); t += 1.0
        self.assertGreater(e.current.mbps, low,
                           "a two-packet residual queue during recovery must "
                           "not snap the estimate back down")

    def test_bottleneck_drops_alone_are_enough(self):
        """Drops cannot be produced by the controller's own counters."""
        e = CapacityEstimator()
        t = 0.0
        for _ in range(2):
            e.observe(_sat(t, 100.0)); t += 1.0
        for _ in range(6):
            e.observe(_idle(t, 100.0)); t += 1.0
        c = e.observe(Measurement(
            t=t, goodput_mbps=20.0, bottleneck_drop_rate_per_s=5.0,
            bottleneck_backlog_bytes=0))
        self.assertTrue(c.changed)
        self.assertAlmostEqual(e.current.mbps, 20.0)


class TestRecoveryNeedsATarget(unittest.TestCase):
    """Option A means capacity is learned ONLY from congestion -- so without a
    seeded target the release has nothing to climb toward.

    Measured on the host before the drop:

        t=1.0 .. 9.5   saturated False   backlog 0   goodput 85.12

    85 Mbps on a 100 Mbps link leaves the queue empty, so the link is correctly
    judged uncongested and the estimator never learns 100. It starts at 0, so
    `_high_water` stayed 0 until the drop, where it became exactly 20 -- the same
    as `_ewma`. `_release_idle` then returns immediately, every tick, forever.

    The structural consequence: the highest capacity ever observed is the LOWEST
    capacity that ever caused congestion.
    """

    def _dropped(self, e):
        """Reproduce the host run EXACTLY.

        The pre-drop phase carries 85 Mbps on a 100 Mbps link, so the netem
        queue stays EMPTY and the link is correctly judged uncongested --
        `backlog=0`. An earlier draft of this helper used a saturated 100 Mbps
        reading, which seeds `_high_water` implicitly and therefore tested
        nothing: the estimator recovered, and the "no target" case never
        occurred.
        """
        t = 0.0
        for _ in range(8):
            e.observe(Measurement(t=t, goodput_mbps=85.0,
                                  bottleneck_backlog_bytes=0))
            t += 1.0
        for _ in range(4):
            e.observe(_sat(t, 20.0)); t += 1.0
        return t

    def test_without_a_seeded_target_the_estimate_can_never_rise(self):
        """The defect, isolated and deterministic."""
        e = CapacityEstimator()
        t = self._dropped(e)
        low = e.current.mbps
        for _ in range(200):
            e.observe(Measurement(t=t, goodput_mbps=20.0,
                                  bottleneck_backlog_bytes=0))
            t += 1.0
        self.assertAlmostEqual(e.current.mbps, low, places=6,
                               msg="precondition: no release target exists")

    def test_a_seeded_target_makes_recovery_possible(self):
        e = CapacityEstimator()
        e.seed_high_water(100.0)
        t = self._dropped(e)
        low = e.current.mbps
        for _ in range(200):
            e.observe(Measurement(t=t, goodput_mbps=20.0,
                                  bottleneck_backlog_bytes=0))
            t += 1.0
        self.assertGreater(e.current.mbps, low,
                           "a seeded recovery target did not enable recovery")

    def test_seeding_does_not_change_the_estimate_itself(self):
        """The boundary: the configured rate seeds the TARGET, not the estimate.

        If seeding fed the estimate, the estimator could report a capacity it
        never observed, which is exactly what the Measurement docstring forbids.
        """
        a = CapacityEstimator()
        b = CapacityEstimator()
        b.seed_high_water(100.0)
        t = 0.0
        for _ in range(6):
            a.observe(_sat(t, 20.0))
            b.observe(_sat(t, 20.0))
            t += 1.0
        self.assertAlmostEqual(a.current.mbps, b.current.mbps, places=9,
                               msg="seeding leaked into the estimate")

    def test_a_drop_is_still_detected_and_still_snaps(self):
        """A seeded high-water must not slow the FALLING edge."""
        e = CapacityEstimator()
        e.seed_high_water(100.0)
        t = 0.0
        # A genuinely saturated wide link first, so 100 is observed, not seeded.
        for _ in range(6):
            e.observe(_sat(t, 100.0)); t += 1.0
        # Then the real drop, with enough samples to clear the dwell window.
        for _ in range(12):
            e.observe(_sat(t, 20.0)); t += 1.0
        self.assertLess(e.current.mbps, 30.0,
                        "a seeded high-water delayed the drop detection")


class TestAReleaseMustSignalAChange(unittest.TestCase):
    """A moved estimate that is not reported as changed rebuilds nothing.

    Measured on the host after `seed_high_water`:

        estimator 68.28      policy_changes 1     goodput 19.3 Mbps

    The estimator had climbed from 20 to 68 -- the release mechanism was
    working -- while the applied policy stayed exactly where the drop had left
    it. The cause was one word:

        return self._emit(mbps=self._release_idle(...), changed=False)

    `_release_idle` mutates `self._ewma` internally, so the estimate really did
    move, but `_emit` was told `changed=False` unconditionally. The harness
    checks `cap.changed`, returned early, and never rebuilt the plan.

    An estimate the policy does not consume is not an estimate.
    """

    def test_a_release_reports_changed(self):
        from aciq.capacity import IDLE_STREAK_RELEASE
        e = CapacityEstimator()
        e.seed_high_water(100.0)
        t = 0.0
        for _ in range(8):
            e.observe(_sat(t, 100.0)); t += 1.0
        for _ in range(4):
            e.observe(_sat(t, 20.0)); t += 1.0
        low = e.current.mbps
        released = False
        for _ in range(IDLE_STREAK_RELEASE * 3):
            cap = e.observe(Measurement(t=t, goodput_mbps=20.0,
                                        bottleneck_backlog_bytes=0))
            t += 1.0
            if cap.changed and cap.mbps > low:
                released = True
                break
        self.assertTrue(released,
                        "the release moved the estimate but reported "
                        "changed=False, so no policy would be rebuilt")

    def test_idle_ticks_without_a_release_report_no_change(self):
        """The signal must mean something: no movement, no changed flag."""
        e = CapacityEstimator()
        e.seed_high_water(100.0)
        t = 0.0
        for _ in range(8):
            e.observe(_sat(t, 100.0)); t += 1.0
        for _ in range(4):
            e.observe(_sat(t, 20.0)); t += 1.0
        cap = e.observe(Measurement(t=t, goodput_mbps=20.0,
                                    bottleneck_backlog_bytes=0))
        self.assertFalse(cap.changed,
                         "a single idle tick claimed a change")
