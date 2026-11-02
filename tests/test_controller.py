"""Tests for the FSM controller and the rate law.

Everything offline: a fake `Measurement` needs only its fields, the rollback
function is a recording closure, the clock is controlled by the test.

The tests concentrate on the CONTRACTS the docstrings promise:

- no verdict before an after-window is complete (insufficient never becomes
  a keep masquerading with confidence),
- a rollback verdict actually reaches `rollback_fn` — and its FAILURE does
  not take the controller down,
- three consecutive rollbacks stand the controller down: it stops acting,
  and it comes back after the sentence is served,
- the law: dwell, step, floor, and the emergency exception behave exactly as
  the constants are documented (and nothing clamps silently).
"""

from __future__ import annotations

import unittest

from aciq.capacity import Measurement
from aciq.controller import Controller, Phase
from aciq.verifier import (BoardGuard, LANDING_HEADROOM_FRAC,
                           MAX_CONSECUTIVE_ROLLBACKS, MIN_DWELL_S,
                           MIN_RATE_MBPS, Verdict, bound_rate_change,
                           timeline_verdict, with_landing_headroom)


def m(t=0.0, goodput=20.0, drop=0.0, backlog=0, over=0.0) -> Measurement:
    return Measurement(t=t, goodput_mbps=goodput, drop_rate_per_s=drop,
                       overlimit_rate_per_s=over,
                       link_drop_rate_per_s=None, link_overlimit_rate_per_s=None,
                       child_backlog_bytes=backlog,
                       bottleneck_drop_rate_per_s=drop,
                       bottleneck_backlog_bytes=0)


class TestRateLaw(unittest.TestCase):
    def test_first_rate_is_free(self):
        r = bound_rate_change(None, 20.0, now=100.0, last_change_t=None)
        self.assertTrue(r)
        self.assertEqual(r.rate, 20.0)

    def test_small_step_passes_through_unchanged(self):
        r = bound_rate_change(20.0, 22.0, now=100.0, last_change_t=90.0)
        self.assertEqual(r.rate, 22.0)   # +10% stays
        self.assertEqual(r.reason, "within step bound")

    def test_big_step_is_clamped_not_refused(self):
        r = bound_rate_change(20.0, 60.0, now=200.0, last_change_t=150.0)
        self.assertEqual(r.rate, 25.0)   # +25% is the law's step
        self.assertEqual(r.reason, "step-clamped")

    def test_dwell_window_refuses(self):
        r = bound_rate_change(20.0, 21.0, now=100.0, last_change_t=97.0)
        self.assertFalse(r)              # inside the dwell, no emergency
        self.assertEqual(r.reason, "dwell window not elapsed")
        self.assertIsNone(r.rate)

    def test_dwell_after_elapsed_allows(self):
        r = bound_rate_change(20.0, 21.0, now=100.0 + MIN_DWELL_S,
                              last_change_t=100.0)
        self.assertTrue(r)

    def test_emergency_skips_dwell_and_widens_step(self):
        # inside dwell, emergency drop-rate skips it and widens the step to 50%
        r = bound_rate_change(20.0, 35.0, now=100.0, last_change_t=99.0,
                              drop_rate_per_s=500.0)
        self.assertTrue(r)
        self.assertEqual(r.rate, 30.0)
        self.assertTrue(r.emergency)

    def test_floor_clamps(self):
        r = bound_rate_change(1.2, 0.5, now=100.0, last_change_t=90.0)
        self.assertEqual(r.rate, MIN_RATE_MBPS)
        self.assertEqual(r.reason, "clamped at floor")

    def test_downward_steps_are_steps_too(self):
        r = bound_rate_change(20.0, 2.0, now=200.0, last_change_t=1.0)
        self.assertEqual(r.rate, 15.0)   # -25% bound holds for decreases too

    def test_a_landing_skips_the_dwell(self):
        """Round 7: the overshoot landing may sit a hair above the applied
        (32.29 -> 32.86 inside the 33.0 band); the 5 s dwell deferred it
        past the 8 s ramp landing budget, seeds 1004/1007."""
        r = bound_rate_change(32.29, 32.86, now=100.0,
                              last_change_t=95.5, landing=True)
        self.assertTrue(r)
        self.assertEqual(r.rate, 32.86)
        self.assertEqual(r.reason, "within step bound")
        self.assertEqual(bound_rate_change(32.29, 60.0, now=100.0,
                                           last_change_t=95.5,
                                           landing=True).rate, 40.3625)

    def test_a_normal_up_move_still_waits_for_the_dwell(self):
        r = bound_rate_change(32.29, 32.86, now=100.0, last_change_t=95.5)
        self.assertFalse(r)
        self.assertEqual(r.reason, "dwell window not elapsed")


class TestLandingHeadroom(unittest.TestCase):
    """Round 7: a measured carry that lands ON the band edge is not inside it.

    s2b_ramp_100to30 seed1004 landed 33.121 against a 33.0 top; the target
    was the wire's own carry, so the fix is a small downward headroom, not
    a different target. Upward moves and the floor are untouched.
    """

    def test_a_down_landing_keeps_headroom(self):
        self.assertAlmostEqual(with_landing_headroom(33.121, 34.5),
                               33.121 * (1.0 - LANDING_HEADROOM_FRAC))
        self.assertLess(with_landing_headroom(33.121, 34.5), 33.0)
        self.assertEqual(LANDING_HEADROOM_FRAC, 0.02)

    def test_an_up_move_is_never_shaved(self):
        self.assertEqual(with_landing_headroom(40.0, 33.0), 40.0)

    def test_the_floor_still_wins(self):
        self.assertEqual(with_landing_headroom(14.1, 40.0, floor=14.0), 14.0)

    def test_no_previous_rate_means_no_headroom(self):
        self.assertEqual(with_landing_headroom(20.0, None), 20.0)


class TestVerdict(unittest.TestCase):
    def test_insufficient_windows_never_render(self):
        v = timeline_verdict([m(0, 20)] * 2, [m(1, 10)] * 2)
        self.assertEqual(v.outcome, "insufficient")

    def test_goodput_collapse_rolls_back(self):
        before = [m(0, 20.0, drop=0.0) for _ in range(4)]
        after = [m(1, 14.0, drop=0.0) for _ in range(4)]   # -30%
        v = timeline_verdict(before, after)
        self.assertEqual(v.outcome, "rollback")
        self.assertTrue(any("goodput" in r for r in v.reasons))

    def test_drop_collapse_rolls_back(self):
        before = [m(0, 19.0, drop=10.0) for _ in range(4)]
        after = [m(1, 19.0, drop=20.0) for _ in range(4)]  # 2x worse
        v = timeline_verdict(before, after)
        self.assertEqual(v.outcome, "rollback")
        self.assertTrue(any("drop" in r for r in v.reasons))

    def test_keep_when_equal(self):
        before = [m(0, 19.0, drop=2.0) for _ in range(4)]
        after = [m(1, 19.0, drop=2.0) for _ in range(4)]
        v = timeline_verdict(before, after)
        self.assertEqual(v.outcome, "keep")

    def test_drop_baseline_too_small_to_compare(self):
        before = [m(0, 19.0, drop=0.0) for _ in range(4)]
        after = [m(1, 19.0, drop=3.0) for _ in range(4)]
        v = timeline_verdict(before, after)
        self.assertEqual(v.outcome, "keep")

    def test_medians_resist_a_single_outlier(self):
        before = [m(0, 19.0)] * 4
        after = [m(1, 19.0)] * 4 + [m(2, 2.0)]  # one awful tick among four
        v = timeline_verdict(before, after)
        self.assertEqual(v.outcome, "keep")


class TestController(unittest.TestCase):
    def _ctl(self, rollbacks=None, window=4, cooldown_s=2.0, now0=100.0):
        c = Controller(rollback_fn=(lambda v: rollbacks.append(v)
                                    if rollbacks is not None else None),
                       window=window, cooldown_s=cooldown_s)
        return c

    def test_a_change_arms_and_a_keep_verdict_completes(self):
        rollbacks = []
        c = self._ctl(rollbacks)
        for i in range(4):
            self.assertIsNone(c.on_measurement(m(0, 19.0), now=i * 2.0))
        self.assertTrue(c.notify_change(now=10.0))
        self.assertEqual(c.state, Phase.ARMED)
        v = None
        for i in range(4):
            v = c.on_measurement(m(20 + i, 19.0), now=12.0 + i * 2.0)
        self.assertIsNotNone(v)
        self.assertEqual(v.outcome, "keep")
        self.assertEqual(rollbacks, [])
        self.assertEqual(c.state, Phase.STABLE)

    def test_regression_triggers_a_real_rollback_call(self):
        rollbacks = []
        c = self._ctl(rollbacks)
        for i in range(4):
            c.on_measurement(m(0, 19.0, drop=1.0), now=i * 2.0)
        c.notify_change(now=10.0)
        v = None
        for i in range(4):
            v = c.on_measurement(m(20 + i, 10.0, drop=30.0), now=12.0 + i * 2.0)
        self.assertEqual(v.outcome, "rollback")
        self.assertEqual(len(rollbacks), 1)   # called exactly once
        self.assertEqual(c.state, Phase.COOLDOWN)

    def test_no_change_means_no_verdeliberations(self):
        rollbacks = []
        c = self._ctl(rollbacks)
        for i in range(30):
            self.assertIsNone(c.on_measurement(m(i, 19.0), now=i))
        self.assertEqual(len(rollbacks), 0)
        self.assertEqual(len(c.before), c.window)   # bounded...

    def test_cooling_down_then_stable_again(self):
        rollbacks = []
        c = self._ctl(rollbacks, cooldown_s=2.0)
        for i in range(4):
            c.on_measurement(m(0, 19.0), now=i)
        c.notify_change(now=5.0)
        v = None
        for i in range(4):
            v = c.on_measurement(m(6 + i, 2.0), now=7.0 + i)  # collapse
        self.assertEqual(v.outcome, "rollback")
        self.assertEqual(c.state, Phase.COOLDOWN)
        self.assertIsNone(c.on_measurement(m(100, 19.0), now=11.0))
        self.assertEqual(c.state, Phase.COOLDOWN)   # 11-10 < 2.0
        self.assertIsNone(c.on_measurement(m(101, 19.0), now=12.5))
        self.assertEqual(c.state, Phase.STABLE)     # 12.5-10 >= 2.0

    def test_three_rollbacks_pull_the_plug_then_it_returns(self):
        rollbacks = []
        c = Controller(rollback_fn=rollbacks.append, window=2, cooldown_s=0.1)
        t = 0.0
        for _ in range(MAX_CONSECUTIVE_ROLLBACKS):
            for i in range(4):
                c.on_measurement(m(t, 19.0), now=t)
                t += 0.01
            c.notify_change(now=t)
            outs = []
            for i in range(4):
                outs.append(c.on_measurement(m(t, 1.0), now=t))
                t += 0.01
            self.assertEqual(outs[-1].outcome, "rollback")
            # burn the cooldown
            c.on_measurement(m(t, 19.0), now=t + c.cooldown_s)
            t += c.cooldown_s
        self.assertEqual(len(rollbacks), MAX_CONSECUTIVE_ROLLBACKS)
        self.assertEqual(c.state, Phase.SLEEPING)
        # while asleep, notify_change refuses and no verdict comes out
        self.assertFalse(c.notify_change(now=t))
        v = c.on_measurement(m(t, 1.0), now=t)
        self.assertIsNone(v)
        # sentence served: after STANDBY_S it is STABLE again
        c.on_measurement(m(t, 19.0), now=t + 61.0)
        self.assertTrue(c.notify_change(now=t + 61.5))

    def test_rollback_fn_raising_does_not_break_the_loop(self):
        def hostile(v):
            raise RuntimeError("txn exploded")
        c = Controller(rollback_fn=hostile, window=2, cooldown_s=0.1)
        for i in range(4):
            c.on_measurement(m(0, 19.0), now=i)
        c.notify_change(now=2.0)
        outs = [c.on_measurement(m(3 + i, 1.0), now=3.5 + i) for i in range(4)]
        self.assertEqual(outs[-1].outcome, "rollback")
        self.assertEqual(c.state, Phase.COOLDOWN)   # alive, cooled, degraded

    def test_teardown_is_idempotent_and_harmless(self):
        c = Controller(rollback_fn=lambda v: None, window=2)
        c.teardown()
        c.teardown()
        self.assertEqual(len(c.before), 0)


class TestBoardGuard(unittest.TestCase):
    def test_guard_only_counts_rollbacks(self):
        g = BoardGuard()
        g.note_verdict(Verdict("keep", (), None, None, None, None), 0.0)
        self.assertFalse(g.blocked(100.0))
        # three keeps in a row mean three ROLLBACK attempts stand: ONE repeat
        for i in range(MAX_CONSECUTIVE_ROLLBACKS):
            g.note_verdict(Verdict("rollback", (), None, None, None, None),
                           float(i))
        self.assertTrue(g.blocked(50.0))    # standby is 60 s from the third
        g.note_verdict(Verdict("keep", (), None, None, None, None), 100.0)
        self.assertFalse(g.blocked(300.0))


if __name__ == "__main__":
    unittest.main()


class TestHarnessIntegration(unittest.TestCase):
    def _harness(self):
        from aciq.harness import Harness
        return Harness()

    def test_enable_controller_opt_in_and_idempotent(self):
        h = self._harness()
        self.assertIsNone(h.controller)
        c = h.enable_controller(rollback=False)
        self.assertIs(h.enable_controller(), c)   # second call returns same

    def test_controller_verdict_from_harness_path(self):
        h = self._harness()
        h.enable_controller(rollback=False, window=2)
        from aciq.metrics import ClassCounters
        from aciq.model import TrafficClass
        empty = {k: ClassCounters(cls=k) for k in TrafficClass}
        self.assertEqual(h.adapt_step(empty, 1.0, 0.0), (None, False))  # primes
        self.assertEqual(len(h.controller_events), 0)

    def test_observe_flows_without_source_is_empty_not_fake(self):
        h = self._harness()
        self.assertEqual(h.observe_flows(), [])

    def test_observe_flows_with_attached_fakes(self):
        from aciq.features import FlowFeatures
        from aciq.model import Flow

        class FakeSource:
            def pump(self, t=0.0):
                return 0

            def refresh(self):
                return [FlowFeatures(flow=Flow(src="1.2.3.4", sport=1,
                                               dst="5.6.7.8", dport=2))]

        h = self._harness()
        src = FakeSource()
        h.attach_flow_source(src)
        feats = h.observe_flows()
        self.assertEqual(len(feats), 1)
        self.assertEqual(feats[0].flow.src, "1.2.3.4")
