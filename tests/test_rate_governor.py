"""M2.5 -- the rate governor.

Every test is written against the measured defect from the fix 17 diagnosis:

* applied == belief left the tree ABOVE the link (102.45 on a 100 Mbps
  link with bulk saturating it) and the out-of-band bottleneck queue
  carried call packets for ~240 ms;
* after a real capacity drop the tree sat at the step-clamped 78.4 Mbps
  for the rest of the run because the only commits came from the estimator
  itself, which is rate-limited by the law at 5 s per commit.

The contracts proven here:
- the ceiling: the rate never exceeds cap_fraction x belief, whatever the
  delay says;
- the ratchet: expressed bottleneck delay shrinks the applied rate even
  when the estimate has stopped moving;
- the probe: after a sustained clear plus real demand, the applied rate
  rises; without demand or clarity, it never does;
- the budget: the governor cannot generate more changes per minute than
  its configuration allows;
- the honesty: every decision carries a reason, and an unreadable delay probe
  produces no ratchet, never an invented rate.

Round-3 tests (docs/evidence/round3-params.md; the two S2b failures were
diagnosed per-tick in docs/evidence/round3-diagnosis.md):
- the demand probe: pipe-limited demand (offered riding at the applied
  rate on a clear delay) pierces a stale ceiling in bounded steps;
- the overshoot backoff: a probe that inflates delay lands at known-good
  and blocks fresh probes for the backoff window;
- the severe drop: a confident saturated ceiling far below the applied
  rate lands in ONE commit at max(ceiling, floor) -- the seed-800
  step_10 ledger where the plan floor 14.0 vetoed the old emergency and
  the law walked 25% per 5 s commit, 8/10 seeds failing to bind.
"""

from __future__ import annotations

import unittest

from aciq.ratecap import GovernorConfig, RateGovernor


def gov(**kw) -> RateGovernor:
    """A governor with the mission's default tunables, deliberately explicit
    where a test needs speed (hold_clear_s is shortened below unless a test
    is specifically about the hold)."""
    kw.setdefault("hold_clear_s", 10.0)
    return RateGovernor(config=GovernorConfig(**kw))


def delay_for(backlog_bytes: float, delivered_mbps: float) -> float:
    """Backlog / delivered in ms, the same formula the governor uses."""
    return backlog_bytes / (delivered_mbps * 125.0)


class TestCeiling(unittest.TestCase):
    """The headline failure: applied 102.45 on a 100 Mbps link."""

    def test_rate_is_never_above_the_ceiling(self):
        """0.90 x 102.45 = 92.2, not 102.45."""
        g = gov()
        d = g.observe(belief=102.45, applied=None, delivered=102.0,
                      backlog_bytes=0, offered=99.0, now=0.0, min_rate=16.0)
        self.assertEqual(d.rate, 92.205)
        self.assertEqual(d.reason, "first rate: ceiling (0.9 x belief)")

    def test_ceiling_tracks_the_belief_down(self):
        g = gov()
        d = g.observe(belief=20.0, applied=None, delivered=20.0,
                      backlog_bytes=0, offered=99.0, now=0.0, min_rate=14.0)
        self.assertEqual(d.rate, 18.0)

    def test_no_belief_means_no_rate(self):
        g = gov()
        d = g.observe(belief=None, applied=None, delivered=None,
                      backlog_bytes=None, offered=None, now=0.0, min_rate=None)
        self.assertIsNone(d.rate)
        self.assertEqual(d.reason, "no estimate and nothing applied yet")

    def test_the_ceiling_binds_every_branch(self):
        """A fall in the belief must pull the tree even while delay is quiet."""
        g = gov()
        g.observe(belief=100.0, applied=90.0, delivered=90.0,
                  backlog_bytes=0, offered=99.0, now=0.0, min_rate=16.0)
        # belief collapsed from 100 to 40: ceiling is 36 < applied 90
        d = g.observe(belief=40.0, applied=90.0, delivered=40.0,
                      backlog_bytes=0, offered=99.0, now=1.0, min_rate=16.0)
        self.assertEqual(d.rate, 36.0)
        self.assertEqual(d.reason, "belief fell below applied: ceiling binds")


class TestDelayRatchet(unittest.TestCase):
    """The queue that carried call packets for 240 ms must shrink the tree
    even when the estimate says nothing new."""

    def test_inflated_delay_ratchets_down(self):
        g = gov()
        # 1.9 MB behind a 100 Mbps delivery ~= 152 ms: the s1 startup state.
        d = g.observe(belief=102.45, applied=92.205, delivered=100.0,
                      backlog_bytes=1_900_000, offered=99.0, now=5.0,
                      min_rate=16.0)
        self.assertLess(d.rate, 92.25)
        self.assertIn("delay inflated", d.reason)
        self.assertLessEqual(d.rate, 92.25)

    def test_ratchet_rate_is_bounded_by_down_step(self):
        g = gov()
        d = g.observe(belief=102.45, applied=92.205, delivered=100.0,
                      backlog_bytes=1_900_000, offered=99.0, now=5.0,
                      min_rate=16.0)
        self.assertAlmostEqual(
            d.rate, 92.205 * (1.0 - GovernorConfig.down_step_frac), places=6)

    def test_ratchet_never_goes_below_the_floor(self):
        g = gov()
        d = g.observe(belief=20.0, applied=17.0, delivered=20.0,
                      backlog_bytes=2_000_000, offered=99.0, now=5.0,
                      min_rate=16.0)
        # 17 x 0.9 = 15.3 < floor 16: the floor binds, not zero.
        self.assertEqual(d.rate, 16.0)

    def test_no_delivered_rate_means_no_ratchet(self):
        """An unreadable probe is no evidence, not an emergency."""
        g = gov()
        # no ema at all: the ceiling-only path is named as such
        d = g.observe(belief=102.45, applied=92.205, delivered=None,
                      backlog_bytes=None, offered=99.0, now=5.0,
                      min_rate=16.0)
        self.assertEqual(d.rate, 92.205)
        self.assertEqual(d.reason, "no delay telemetry: ceiling only")
        # once an ema exists, missing telemetry cannot silently ratchet:
        # the previous reading's decayed value holds the rate still
        g2 = gov()
        g2.observe(belief=102.45, applied=92.205, delivered=100.0,
                   backlog_bytes=0, offered=99.0, now=0.0, min_rate=16.0)
        d2 = g2.observe(belief=102.45, applied=92.205, delivered=None,
                        backlog_bytes=None, offered=99.0, now=5.0,
                        min_rate=16.0)
        self.assertEqual(d2.rate, 92.205)
        self.assertFalse(d2.changed)

    def test_delay_between_thresholds_holds(self):
        g = gov()
        g.observe(belief=102.45, applied=92.205, delivered=100.0,
                  backlog_bytes=0, offered=99.0, now=0.0, min_rate=16.0)
        # 2000 bytes at 100 Mbps = 0.016 ms; 1200 bytes = 0.12 ms; pick a
        # backlog that lands in (10, 20] ms: 15 ms at 100 Mbps = 187_500 B.
        d = g.observe(belief=102.45, applied=92.205, delivered=100.0,
                      backlog_bytes=375_000, offered=99.0, now=5.0,
                      min_rate=16.0)
        self.assertEqual(d.rate, 92.205)
        self.assertIn("between clear and inflation thresholds", d.reason)


class TestProbeUp(unittest.TestCase):
    """Recovery without the whole link bouncing."""

    def _warmed(self, g: RateGovernor, start=92.25):
        """Prime the clock and the clear streak: repeated clear ticks from
        t=0 establish the delay EMA and start the clear timer at t=0."""
        g.observe(belief=102.45, applied=start, delivered=100.0,
                  backlog_bytes=0, offered=99.0, now=0.0, min_rate=16.0)

    def test_clear_without_demand_never_probes(self):
        g = gov()
        self._warmed(g)
        d = g.observe(belief=102.45, applied=92.205, delivered=100.0,
                      backlog_bytes=0, offered=50.0, now=30.0, min_rate=16.0)
        self.assertEqual(d.rate, 92.205)
        self.assertIn("does not demand", d.reason)

    def test_clear_inside_hold_never_probes(self):
        g = gov()
        self._warmed(g)
        # 9 s of clear: the hold is 10 s.
        d = g.observe(belief=102.45, applied=92.205, delivered=100.0,
                      backlog_bytes=0, offered=99.0, now=9.0, min_rate=16.0)
        self.assertEqual(d.rate, 92.205)
        self.assertIn("between clear and inflation", d.reason)

    def test_clear_plus_demand_probes_up_bounded(self):
        g = gov()
        self._warmed(g)
        d = g.observe(belief=102.45, applied=90.0, delivered=100.0,
                      backlog_bytes=0, offered=99.0, now=30.0, min_rate=16.0)
        self.assertAlmostEqual(d.rate, 90.0 * (1.0 + GovernorConfig.up_step_frac))
        # and bounded by the ceiling on an already-high belief
        self.assertLessEqual(d.rate, 92.25)

    def test_probe_cannot_pass_the_ceiling(self):
        cfg = GovernorConfig(hold_clear_s=10.0)
        g = RateGovernor(config=cfg)
        self._warmed(g, start=90.0)
        d = g.observe(belief=102.45, applied=90.0, delivered=100.0,
                      backlog_bytes=0, offered=99.0, now=30.0, min_rate=16.0)
        self.assertAlmostEqual(d.rate, 91.8)   # 2% step, ceiling above it

    def test_a_probe_that_inflates_delay_is_ratcheted_back(self):
        """The cycle must be bounded: up cannot outrun down by more than one
        ratchet width."""
        g = gov()
        self._warmed(g)
        d_up = g.observe(belief=102.45, applied=90.0, delivered=100.0,
                         backlog_bytes=0, offered=99.0, now=30.0,
                         min_rate=16.0)
        self.assertEqual(d_up.changed, True)
        # the probe overshot: the queue grew to the inflation threshold
        d_down = g.observe(belief=102.45, applied=d_up.rate, delivered=100.0,
                           backlog_bytes=1_900_000, offered=99.0, now=30.5,
                           min_rate=16.0)
        self.assertLess(d_down.rate, d_up.rate)
        self.assertIn("ratchet down one step", d_down.reason)


class TestChangeBudget(unittest.TestCase):
    def test_budget_exhaustion_holds(self):
        """max_changes_per_min bounds the RISES the governor generates; falls
        are not rationed (docs/evidence/task2-params.md #3): the post-fix
        evidence shows a drop-tick descent starved behind the ledger that its
        own refused attempts filled."""
        g = RateGovernor(config=GovernorConfig(max_changes_per_min=2,
                                               hold_clear_s=0.001))
        # room 0: first rate (the ceiling); does not spend the budget
        d1 = g.observe(belief=102.45, applied=None, delivered=100.0,
                       backlog_bytes=0, offered=99.0, now=0.0, min_rate=16.0)
        self.assertTrue(d1.changed)
        self.assertAlmostEqual(d1.rate, 92.205)
        # a clear tick anchors the clear-tracking clock
        g.observe(belief=102.45, applied=92.205, delivered=100.0,
                  backlog_bytes=0, offered=99.0, now=5.0, min_rate=16.0)
        # from below the ceiling, two probe-ups spend the whole budget
        r1 = g.observe(belief=102.45, applied=80.55, delivered=100.0,
                       backlog_bytes=0, offered=99.0, now=5.01, min_rate=16.0)
        self.assertGreater(r1.rate, 80.55)
        self.assertIn("probe up", r1.reason)
        r2 = g.observe(belief=102.45, applied=r1.rate, delivered=100.0,
                       backlog_bytes=0, offered=99.0, now=5.02, min_rate=16.0)
        self.assertGreater(r2.rate, r1.rate)
        # rise 3 inside the minute: the budget refuses, the rate holds
        r3 = g.observe(belief=102.45, applied=r2.rate, delivered=100.0,
                       backlog_bytes=0, offered=99.0, now=5.03, min_rate=16.0)
        self.assertEqual(r3.rate, r2.rate)
        self.assertFalse(r3.changed)
        self.assertIn("rise budget exhausted", r3.reason)

    def test_descent_never_rations_the_budget(self):
        """Falls are dwell-bound, not budget-bound (task2-params.md #3): with
        a fully spent rise budget an inflating link still ratchets down."""
        g = RateGovernor(config=GovernorConfig(max_changes_per_min=1,
                                               hold_clear_s=0.001))
        g.observe(belief=102.45, applied=None, delivered=100.0,
                  backlog_bytes=0, offered=99.0, now=0.0, min_rate=16.0)
        g.observe(belief=102.45, applied=92.205, delivered=100.0,
                  backlog_bytes=0, offered=99.0, now=5.0, min_rate=16.0)
        r1 = g.observe(belief=102.45, applied=80.55, delivered=100.0,
                       backlog_bytes=0, offered=99.0, now=5.01, min_rate=16.0)
        self.assertGreater(r1.rate, 80.55)      # the one rise of the minute
        held = g.observe(belief=102.45, applied=r1.rate, delivered=100.0,
                         backlog_bytes=0, offered=99.0, now=5.02,
                         min_rate=16.0)
        self.assertIn("rise budget exhausted", held.reason)
        d = g.observe(belief=102.45, applied=held.rate, delivered=100.0,
                      backlog_bytes=2_500_000, offered=99.0, now=5.5,
                      min_rate=16.0)
        self.assertLess(d.rate, held.rate)
        self.assertIn("ratchet down one step", d.reason)

    def test_delay_emergency_descends_to_ceiling_once_per_cooldown(self):
        """>=100 ms EMA clears one full-descent commitment (task2-params.md
        #1-2). The post-fix drop window never got under 3.23x the link
        because each commit was step-clamped at the law and every refused
        attempt still spent the ledger; the flag certifies the law to land
        at the ceiling in one commit."""
        g = RateGovernor()
        g.observe(belief=102.45, applied=None, delivered=100.0,
                  backlog_bytes=0, offered=99.0, now=0.0, min_rate=16.0)
        # the drop: belief falls to the new deliverable while the queue backs
        # up (raw 320 ms seeds the EMA straight over the line): clearance
        d1 = g.observe(belief=21.5914, applied=92.205, delivered=100.0,
                       backlog_bytes=4_000_000, offered=99.0, now=1.0,
                       min_rate=16.0)
        self.assertTrue(d1.delay_emergency)
        self.assertIn("delay emergency", d1.reason)
        self.assertAlmostEqual(d1.rate, 19.4322, places=3)
        # inside the cooldown: normal step only
        d2 = g.observe(belief=21.5914, applied=d1.rate, delivered=100.0,
                       backlog_bytes=4_000_000, offered=99.0, now=2.0,
                       min_rate=16.0)
        self.assertFalse(d2.delay_emergency)
        self.assertIn("ratchet down one step", d2.reason)
        # after the cooldown and applied above the ceiling (the post-fix
        # 64.67-on-20 shape, measured), one further clearance is available
        d3 = g.observe(belief=21.5914, applied=64.666, delivered=100.0,
                       backlog_bytes=4_000_000, offered=99.0, now=22.0,
                       min_rate=16.0)
        self.assertTrue(d3.delay_emergency)
        self.assertAlmostEqual(d3.rate, 19.4322, places=3)

    def test_capacity_collapse_emergency_descends_to_ceiling(self):
        """ceiling <= 0.5x applied with delay EMA BELOW the delay emergency
        line still clears one full-descent commitment (task2-params.md #6,
        declared from the DEV gate FAIL 2026-10-26): the delay EMA at
        37-72 ms post-drop cannot fire #1, the law's walk-down (0.25x per
        commit, one per 5 s dwell) cannot finish in s2's ~10-14 s post-drop
        window, and the kernel stayed at 2.57x the link on dev band."""
        g = RateGovernor()
        g.observe(belief=102.45, applied=None, delivered=100.0,
                  backlog_bytes=0, offered=99.0, now=0.0, min_rate=16.0)
        # collapse with a MILD delay: EMA ~60 ms, ceiling far under half
        d = g.observe(belief=21.5914, applied=51.632, delivered=100.0,
                      backlog_bytes=2_000_000, offered=99.0, now=10.0,
                      min_rate=16.0)
        self.assertTrue(d.delay_emergency)
        self.assertIn("capacity emergency", d.reason)
        self.assertAlmostEqual(d.rate, 19.4322, places=3)
        # cooldown shared with the delay emergency: inside it, no clearance
        d = g.observe(belief=21.5914, applied=48.0, delivered=100.0,
                      backlog_bytes=2_000_000, offered=99.0, now=15.0,
                      min_rate=16.0)
        self.assertFalse(d.delay_emergency)
        self.assertIn("ratchet down one step", d.reason)

    def test_emergency_never_claimed_without_a_real_descent(self):
        """No clearance when the ceiling is not below the applied rate, or
        when the floor pins the rate: the cooldown stays available."""
        g = RateGovernor()
        g.observe(belief=102.45, applied=None, delivered=100.0,
                  backlog_bytes=0, offered=99.0, now=0.0, min_rate=16.0)
        # belief steady: the ceiling sits exactly at the applied rate
        d = g.observe(belief=102.45, applied=92.205, delivered=100.0,
                      backlog_bytes=1_900_000, offered=99.0, now=1.0,
                      min_rate=16.0)
        self.assertFalse(d.delay_emergency)
        # the floor pins the descent above the ceiling
        d = g.observe(belief=21.5922, applied=25.4977, delivered=100.0,
                      backlog_bytes=4_000_000, offered=99.0, now=2.0,
                      min_rate=26.0)
        self.assertFalse(d.delay_emergency)
        self.assertIn("held at ceiling", d.reason)

    def test_refund_gives_the_budget_back_after_a_spin(self):
        """A rise attempt that never committed did not change the kernel, so
        its stamp is refunded (the budget's currency is real change). This
        is what makes an injected failed apply re-probeable within the same
        minute instead of locking the post-drop plan out for 60 s."""
        g = RateGovernor(config=GovernorConfig(max_changes_per_min=1,
                                               hold_clear_s=0.001))
        g.observe(belief=102.45, applied=None, delivered=100.0,
                  backlog_bytes=0, offered=99.0, now=0.0, min_rate=16.0)
        g.observe(belief=102.45, applied=92.205, delivered=100.0,
                  backlog_bytes=0, offered=99.0, now=5.0, min_rate=16.0)
        d = g.observe(belief=102.45, applied=80.55, delivered=100.0,
                      backlog_bytes=0, offered=99.0, now=5.01, min_rate=16.0)
        self.assertTrue(d.changed)          # the only rise of the minute
        held = g.observe(belief=102.45, applied=d.rate, delivered=100.0,
                         backlog_bytes=0, offered=99.0, now=5.02,
                         min_rate=16.0)
        self.assertIn("rise budget exhausted", held.reason)
        # the rise for d never committed: refund it, and a further rise
        # becomes affordable immediately (same second, no expiry needed)
        self.assertTrue(g.refund_last_change())
        self.assertFalse(g.refund_last_change())     # nothing pending
        next_ = g.observe(belief=102.45, applied=held.rate, delivered=100.0,
                          backlog_bytes=0, offered=99.0, now=5.03,
                          min_rate=16.0)
        self.assertTrue(next_.changed)

class TestEvidence(unittest.TestCase):
    def test_every_decision_logs_a_reason_and_the_numbers(self):
        g = gov()
        d = g.observe(belief=102.45, applied=92.205, delivered=100.0,
                      backlog_bytes=1_900_000, offered=99.0, now=0.0,
                      min_rate=16.0)
        self.assertTrue(d.reason)
        e = g.log[-1]
        for key in ("rate", "delay_ms", "delay_ema_ms", "ceiling_mbps",
                    "changed", "t"):
            self.assertIn(key, e)
        self.assertAlmostEqual(e["delay_ms"],
                               1_900_000 / (100.0 * 125.0), places=4)

    def test_delay_ema_smooths_noise(self):
        cfg = GovernorConfig(hold_clear_s=10.0)
        g = RateGovernor(config=cfg)
        g.observe(belief=100.0, applied=90.0, delivered=100.0,
                  backlog_bytes=0, offered=99.0, now=0.0, min_rate=16.0)
        d = g.observe(belief=100.0, applied=90.0, delivered=100.0,
                      backlog_bytes=1_900_000, offered=99.0, now=1.0,
                      min_rate=16.0)
        # alpha 0.5: one burst may fire the ratchet, but the reason must
        # name the smoothed value it acted on, not the raw spike.
        self.assertEqual(d.delay_ema_ms,
                         0.5 * (1_900_000 / (100.0 * 125.0))
                         + 0.5 * 0.0)


class TestDemandProbe(unittest.TestCase):
    """Round 3: upward probing into a black box past the pinned ceiling.

    The measured failure (round3-diagnosis.md section 1, seed 800): applied
    pins at ceiling == 0.9 x last-saturated belief because no saturated
    observation can exist while the tree is the limiting pipe, and the old
    demand gate `offered > 1.05 x applied` is unsatisfiable for exactly the
    same reason: offered rides at the applied rate. The DEV-band retune
    (round3-params.md) replaces ceiling freshness with the overlimit
    witness: the probe may fire only while the tree is seen overlimiting.
    """

    def _pipecase(self, now: float, applied: float = 16.52,
                  offered: float | None = None,
                  overlimit: float | None = 200.0,
                  saturated: bool | None = None) -> object:
        """One tick of the seed-800 post-recovery regime: delay clear,
        bulk saturating the pipe (offered ~= applied), the tree
        overlimiting because it is the binder (overlimit witness on by
        default), belief frozen at its last saturated value."""
        g = getattr(self, "_gov", None)
        if g is None:
            g = self._gov = gov()
        offered = 15.7 if offered is None else offered
        saturated = bool(saturated)
        return g.observe(belief=18.36, belief_conf=0.0,
                         belief_saturated=saturated,
                         applied=applied, delivered=16.0,
                         backlog_bytes=0, offered=offered, now=now,
                         min_rate=14.0,
                         tree_overlimit_per_s=overlimit)

    def test_inside_the_window_no_probe(self):
        self._pipecase(0.0)
        d = self._pipecase(6.0)
        self.assertEqual(d.rate, 16.52)
        self.assertIn("hold", d.reason)

    def test_pipe_limited_demand_probes_past_a_stale_ceiling(self):
        self._pipecase(0.0)
        self._pipecase(6.0)
        d = self._pipecase(13.0)   # window of 13 s has held
        self.assertAlmostEqual(d.rate, 16.52 * (1.0 + GovernorConfig.probe_up_frac))
        self.assertIn("demand-probe up", d.reason)
        self.assertGreater(d.probe_known_good, 0.0)

    def test_the_window_skips_a_few_light_ticks(self):
        """One light tick must not restart the 12 s hold."""
        self._pipecase(0.0)
        self._pipecase(6.0, offered=5.0)     # light tick, inside the grace
        self._pipecase(7.0)
        d = self._pipecase(13.0)
        self.assertAlmostEqual(d.rate, 16.52 * (1.0 + GovernorConfig.probe_up_frac))

    def test_saturated_refresh_no_longer_blocks_the_pierce(self):
        """DEV-band root cause: a saturated sample refreshes the ceiling AT
        the pinned applied rate (dev seed 1004: sat ticks at rel 22.1-32.6
        all at applied 15.25 on a 100 Mbps link), so ceiling freshness
        could never lapse. The overlimit witness now decides; saturation
        must be irrelevant to the pierce."""
        self._pipecase(0.0, saturated=True)
        self._pipecase(6.0, saturated=True)
        d = self._pipecase(13.0, saturated=True)
        self.assertIn("demand-probe up", d.reason)

    def test_no_overlimit_witness_blocks_the_pierce(self):
        """The demand holding with a quiet overlimit counter is a bulk riding
        the LINK through the tree, not through a bottleneck under our tree;
        the counters are missing. Both refuse a step in the dark."""
        self._pipecase(0.0, overlimit=0.0)
        self._pipecase(6.0, overlimit=0.0)
        d = self._pipecase(13.0, overlimit=0.0)
        self.assertEqual(d.rate, 16.52)
        self.assertIn("drop demand", d.reason)
        # and with the counters entirely absent
        self._gov = gov()
        self._pipecase(0.0, overlimit=None)
        self._pipecase(6.0, overlimit=None)
        d = self._pipecase(13.0, overlimit=None)
        self.assertIn("drop demand", d.reason)

    def test_a_finished_source_never_probes(self):
        """Offered decaying below DEMAND_FRAC x applied (past the gap
        grace) is a source that is done, not demand."""
        self._pipecase(0.0)
        self._pipecase(6.0)
        self._pipecase(12.0)
        d = self._pipecase(20.0, offered=5.0)    # decayed: no signature
        self.assertEqual(d.rate, 16.52)
        self.assertIn("does not demand", d.reason)

    def test_probe_overshoot_lands_at_known_good(self):
        """A piercing probe that inflates the bottleneck lands at the last
        known-good rate, capped by what the wire actually carries, and
        blocks fresh probes for the backoff window."""
        from aciq.ratecap import PROBE_BACKOFF_S
        g = gov()
        # Launch state seeds known-good at the applied rate.
        d0 = g.observe(belief=None, applied=16.52, delivered=16.0,
                       backlog_bytes=0, offered=15.7, now=0.0, min_rate=14.0)
        self.assertEqual(d0.rate, 16.52)    # clearance-hold, no belief yet
        self.assertFalse(d0.changed)
        # demand window holds; the probe pierces (ceiling absent offline).
        d = None
        for t in (2.0, 6.0, 10.0):
            d = g.observe(belief=None, applied=16.52, delivered=16.0,
                          backlog_bytes=0, offered=15.7, now=t,
                          min_rate=14.0)
        d = g.observe(belief=None, applied=16.52, delivered=16.0,
                      backlog_bytes=0, offered=15.7, now=13.0,
                      min_rate=14.0, tree_overlimit_per_s=200.0)
        self.assertTrue(d.reason.startswith("demand-probe up"))
        probe_want = d.rate
        # the probe committed: the tree rises to the want; queue grows past
        # the inflation threshold with the wire still carrying most of the
        # applied rate (the overshoot signature).
        delivered = 0.9 * probe_want
        d1 = g.observe(belief=None,
                       applied=probe_want, delivered=delivered,
                       backlog_bytes=int(60.0 * delivered * 125.0),
                       offered=probe_want, now=13.5, min_rate=14.0)
        self.assertIn("probe overshoot", d1.reason)
        self.assertLessEqual(d1.rate, delivered)
        # fresh probes are blocked for the backoff window even though the
        # demand signature re-establishes: back-offs are prioritized.
        db = None
        for t in range(15, 29):
            db = g.observe(belief=None, applied=d1.rate, delivered=d1.rate,
                           backlog_bytes=0, offered=d1.rate, now=float(t),
                           min_rate=14.0)
        self.assertIn("does not demand", db.reason)
        self.assertGreater(db.probe_block_remaining_s, 0.0)
        self.assertLess(db.probe_block_remaining_s, PROBE_BACKOFF_S)


class TestSevereDrop(unittest.TestCase):
    """Round 3: the emergency that the plan floor vetoed.

    The measured ledger (round3-diagnosis.md section 2, seed 800 100->10):
    the recovery at t=13.6 saturates the belief at 11.056 (ceiling 9.95)
    while the applied rate is 60.03 and the plan floor is 14.0. The old
    veto `min_rate <= ceiling` refused the collapse emergency forever, and
    the law's 25%/5s envelope walked 7 commits over ~31 s.
    """

    def _post_drop_tick(self, g: RateGovernor, now: float, applied: float,
                        delivered: float = 11.0):
        return g.observe(belief=11.056144, belief_conf=1.0,
                         belief_saturated=True,
                         applied=applied, delivered=delivered,
                         backlog_bytes=int(60.0 * delivered * 125.0),
                         # 60 ms of queueing delay: inflated but below the
                         # delay emergency's 100 ms band
                         offered=11.0, now=now, min_rate=14.0)

    def test_severe_drop_lands_in_one_commit_despite_the_floor(self):
        """ceiling 9.95 < 0.6 x 60.03 at confidence 1.0 with the floor 14.0
        above the ceiling: ONE commit lands at max(ceiling, floor) = 14.0."""
        g = gov()
        # priming tick at the pre-drop regime (clear delay, live belief)
        g.observe(belief=97.63, belief_conf=0.3, belief_saturated=True,
                  applied=87.87, delivered=95.0, backlog_bytes=10_000,
                  offered=90.0, now=0.0, min_rate=35.0)
        d = self._post_drop_tick(g, now=5.0, applied=60.03)
        self.assertAlmostEqual(d.rate, 14.0)
        self.assertTrue(d.delay_emergency)
        self.assertIn("severe drop", d.reason)

    def test_severe_drop_needs_confidence(self):
        """In the (0.5x, 0.6x) band below the confidence threshold the
        trigger has no say: the ordinary ratchet (and its law bounds)
        decides, and no delay emergency fires."""
        g = gov()
        g.observe(belief=97.63, belief_conf=0.3, belief_saturated=True,
                  applied=87.87, delivered=95.0, backlog_bytes=10_000,
                  offered=90.0, now=0.0, min_rate=35.0)
        d = g.observe(belief=11.056144, belief_conf=0.2,
                      belief_saturated=True,
                      applied=18.0, delivered=11.0,
                      backlog_bytes=int(60.0 * 11.0 * 125.0),
                      offered=11.0, now=5.0, min_rate=14.0)
        # ceiling 9.95 < 0.6x18 = 10.8, but above the 0.5x collapse line;
        # confidence 0.2 blocks the severe trigger. The plain ratchet is
        # the decision (whose floor clamp still yields 14.0), but NO
        # emergency: the law then step-clamps this move instead of
        # landing it in one commit.
        self.assertAlmostEqual(d.rate, 14.0)
        self.assertFalse(d.delay_emergency)
        self.assertIn("ratchet down one step", d.reason)


if __name__ == "__main__":
    unittest.main()
