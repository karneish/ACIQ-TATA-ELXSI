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
    def test_dormant_ceiling_ladder_seven_rungs_in_one_window(self):
        """Retune #9: the rise budget must not plateau-lock a pierce ladder
        whose estimator ceiling never moves (dev band 2026-10-31, seed1000
        s2b_step_up: six rungs to 56.32 then 28 s of refusals at overlimit
        4092-4217/s with util stuck at 0.56; the passing seeds ran 7-10
        rungs only because their ceiling stepped up and each step's
        law-refused no-op bypass refunded a stamp). The shipped default
        (MAX_CHANGES_PER_MIN 12) must let all seven rungs pierce inside
        one 60 s window; the six-budget rung 7 is the regression."""
        g = RateGovernor(config=GovernorConfig())  # the shipped default
        applied = 17.0
        # room: the ceiling states the first rate; the demand window starts
        g.observe(belief=16.40, belief_conf=0.0, belief_saturated=False,
                  applied=None, delivered=15.0, backlog_bytes=0,
                  offered=None, now=0.0, min_rate=14.0,
                  tree_overlimit_per_s=None)
        g.observe(belief=16.40, belief_conf=0.0, belief_saturated=False,
                  applied=17.0, delivered=15.0, backlog_bytes=0,
                  offered=None, now=0.1, min_rate=14.0,
                  tree_overlimit_per_s=None)
        # hold the demand signature for the full probe window without ever
        # moving the belief: the ceiling stays 0.9 x 16.40 forever
        for t in (1.1, 2.2, 3.3, 4.4, 5.5):
            g.observe(belief=16.40, belief_conf=0.0, belief_saturated=False,
                      applied=17.0, delivered=15.0, backlog_bytes=0,
                      offered=15.7, now=t, min_rate=14.0,
                      tree_overlimit_per_s=4200.0)
        # seven rungs at the law's dwell floor (>= 5 s between commits),
        # each a fresh higher target: 17.0 x 1.25^7
        t = 6.4
        for rung in range(7):
            d = g.observe(belief=16.40, belief_conf=0.0, belief_saturated=False,
                          applied=applied, delivered=applied, backlog_bytes=0,
                          offered=applied * 0.90, now=t, min_rate=14.0,
                          tree_overlimit_per_s=4200.0)
            self.assertTrue(
                d.reason.startswith("demand-probe up"),
                f"rung {rung + 1} did not pierce: {d.reason}")
            applied = d.rate
            t += 5.3
        self.assertAlmostEqual(applied, 17.0 * 1.25 ** 7, delta=0.01)

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
        # round 5: a COLLAPSE (ceiling <= 0.5x applied) bypasses the shared
        # cooldown -- the first clearance may already be spent when the
        # belief later snaps to the true link (s7 100->8 smoke: the first
        # severe landing at 65 was stale, and the collapse to 7.5 arrived
        # 2 s later inside the cooldown, otherwise walked out past 8 s).
        # keep the delay EMA under 100 ms so this is the COLLAPSE path, not
        # the delay-shock path
        d = g.observe(belief=21.5914, applied=48.0, delivered=100.0,
                      backlog_bytes=750_000, offered=99.0, now=15.0,
                      min_rate=16.0)
        self.assertTrue(d.delay_emergency)
        self.assertIn("capacity", d.reason)
        # ...but a plain severe drop (above the collapse line) still obeys
        # the cooldown: ceiling 27 > 0.5x48 and the belief is RISING, so it
        # is neither a collapse nor a falling-belief severe landing.
        d = g.observe(belief=30.0, applied=48.0, delivered=100.0,
                      backlog_bytes=750_000, offered=99.0, now=16.0,
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


class TestPierceSurvivesTheStaleCeiling(unittest.TestCase):
    """Round 3 dev band, s2b_step_up_20to100 (seed1000): the pierce committed
    43.9 at t+5.1s and the bind tick held the PRE-probe ceiling 41.0 at
    t+8.9s -- the probe was wiped 3.8 s in, never reached known-good, and
    the ladder restarted each time (0/10 seeds). The ceiling is 0.9 x a
    belief that can only lag a pierce, so the bind must not stand in for
    the probe's own hold window, and a probe that survived promotion
    becomes the climb floor."""

    def _pierce(self, g: RateGovernor, start: float = 0.0) -> float:
        """Drive a full pierce commit from the seed-800 pipe regime and
        return the pierce's want."""
        d = None
        for t in (start, start + 6.0, start + 12.0):
            d = g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                          applied=16.52, delivered=16.0, backlog_bytes=0,
                          offered=15.7, now=t, min_rate=14.0,
                          tree_overlimit_per_s=200.0)
        d = g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                      applied=16.52, delivered=16.0, backlog_bytes=0,
                      offered=15.7, now=start + 13.0, min_rate=14.0,
                      tree_overlimit_per_s=200.0)
        self.assertTrue(d.reason.startswith("demand-probe up"))
        return d.rate

    def test_the_bind_cannot_wipe_a_pierce_inside_its_window(self):
        g = gov()
        want = self._pierce(g)
        # the tree committed the pierce; the next tick is a bind against
        # the stale pre-probe ceiling -- inside probe_hold_s it must hold
        # the pierce rate, not the 0.9 x belief stamp
        self.assertAlmostEqual(g.observe(belief=18.36, belief_conf=0.0,
                                         belief_saturated=False,
                                         applied=want, delivered=want,
                                         backlog_bytes=0, offered=None,
                                         now=13.5, min_rate=14.0,
                                         tree_overlimit_per_s=None).rate,
                               want)

    def test_a_survived_pierce_promotes_and_the_bind_honours_it(self):
        g = gov()
        want = self._pierce(g)
        # the pierce rate survives the FULL hold window clear: promotion
        g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                  applied=want, delivered=want, backlog_bytes=0,
                  offered=want * 0.99, now=13.0, min_rate=14.0,
                  tree_overlimit_per_s=None)
        promoted = g.observe(belief=18.36, belief_conf=0.0,
                             belief_saturated=False, applied=want,
                             delivered=want, backlog_bytes=0,
                             offered=want * 0.99, now=21.0, min_rate=14.0,
                             tree_overlimit_per_s=None)
        # by now the window has passed; a bind tick may no longer drop
        # below the verified pierce rate while the delay stays clear
        bind = g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                         applied=want, delivered=want, backlog_bytes=0,
                         offered=None, now=25.0, min_rate=14.0,
                         tree_overlimit_per_s=None)
        # the verified pierce rate is now the lowest stop: the stale
        # pre-probe ceiling cannot pull the tree underneath it
        self.assertGreaterEqual(bind.rate, want - 0.01)
        self.assertGreater(g.log[-1].get("probe_known_good") or 0.0, 0.0)
        del promoted

    def test_bind_lands_on_the_verified_rate_when_applied_runs_higher(self):
        """A later pierce above the verified rate, inside its window held;
        once the window lapses the bind returns to the VERIFIED floor, not
        the stale pre-probe ceiling (the dev band measured 44.9 held back
        to 41.0 = 0.9 x the stale belief)."""
        g = gov()
        want = self._pierce(g)
        g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                  applied=want, delivered=want, backlog_bytes=0,
                  offered=want * 0.99, now=13.0, min_rate=14.0,
                  tree_overlimit_per_s=None)
        # promote (survived the window), then run higher on a second pierce
        g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                  applied=want, delivered=want, backlog_bytes=0,
                  offered=want * 0.99, now=21.0, min_rate=14.0,
                  tree_overlimit_per_s=None)
        # second pierce requires the overlimit witness again
        for t in (21.5, 27.5, 33.5):
            g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                      applied=want, delivered=want, backlog_bytes=0,
                      offered=want * 0.99, now=t, min_rate=14.0,
                      tree_overlimit_per_s=200.0)
        d2 = g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                       applied=want, delivered=want, backlog_bytes=0,
                       offered=want * 0.99, now=34.5, min_rate=14.0,
                       tree_overlimit_per_s=200.0)
        if not d2.reason.startswith("demand-probe up"):
            self.skipTest("second pierce did not arm in this timeline")
        self.assertAlmostEqual(d2.rate, want * (1.0 + GovernorConfig.probe_up_frac))
        # inside the window: held
        held = g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                         applied=d2.rate, delivered=d2.rate, backlog_bytes=0,
                         offered=None, now=35.0, min_rate=14.0,
                         tree_overlimit_per_s=None)
        self.assertAlmostEqual(held.rate, d2.rate)
        # a partial descent outruns the pierce: the bind still cannot land
        # below the verified rate (promotions need the full window and a
        # survived pierce; a fell-short pierce only saves its own rung).
        # MAX_CHANGES_PER_MIN 12 lets this second pierce arm, so its
        # survival promotes the verified rate to d2.rate; the bind's hold
        # is then min(applied, d2.rate) = applied exactly, which answers
        # through the delay-hold branch -- the rate band, not the branch
        # text, carries the law.
        bound = g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                          applied=d2.rate * 0.85, delivered=d2.rate * 0.85,
                          backlog_bytes=0, offered=None, now=36.0,
                          min_rate=14.0, tree_overlimit_per_s=None)
        self.assertGreaterEqual(bound.rate, want - 0.01)
        self.assertLess(bound.rate, d2.rate)

    def test_the_climb_may_reach_a_verified_rate_past_the_ceiling(self):
        g = gov()
        want = self._pierce(g)
        g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                  applied=want, delivered=want, backlog_bytes=0,
                  offered=want * 0.99, now=13.0, min_rate=14.0,
                  tree_overlimit_per_s=None)
        climb = g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                          applied=want, delivered=want, backlog_bytes=0,
                          offered=want, now=23.0, min_rate=14.0,
                          tree_overlimit_per_s=None)
        # clear-and-demanded: the climb is bounded by the verified rate,
        # not left stranded under the stale 0.9 x belief ceiling
        self.assertGreater(climb.rate, 18.36 * 0.9)

    def test_delay_inflation_still_beats_the_verify_hold(self):
        """The overshoot landing outranks the hold: a pierce that inflates
        the bottleneck lands at known-good regardless of a pending
        window."""
        g = gov()
        want = self._pierce(g)
        delivered = 0.9 * want
        d = g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                      applied=want, delivered=delivered,
                      backlog_bytes=int(60.0 * delivered * 125.0),
                      offered=want, now=13.5, min_rate=14.0,
                      tree_overlimit_per_s=None)
        self.assertIn("probe overshoot", d.reason)
        self.assertLessEqual(d.rate, delivered)
        self.assertTrue(d.delay_emergency)

    def test_the_overshoot_clearance_costs_one_commit_per_cooldown(self):
        """Retune #10: a free delay-emergency clearance buys the overshoot
        landing its one-commit fast track (dev seed1005 ramp_100to30: the
        31.37 landing wanted one commit at rel 31.3 but fell back to the
        law's 25 % step clamp, landing the <= 33.0 commit 9.7 s after the
        ramp END against an 8.0 s budget). The clearance is spent only on
        a committed landing; inside the cooldown the branch answers with
        the same landing value but no flag, and once the cooldown lapses
        the flag returns."""
        g = gov()
        want = self._pierce(g)
        delivered = 0.9 * want

        def observe(applied, t):
            return g.observe(belief=18.36, belief_conf=0.0,
                             belief_saturated=False, applied=applied,
                             delivered=min(0.9 * applied, applied),
                             backlog_bytes=int(60.0 * delivered * 125.0),
                             offered=applied, now=t, min_rate=14.0,
                             tree_overlimit_per_s=None)

        d = observe(want, 13.5)
        self.assertIn("probe overshoot", d.reason)
        self.assertLessEqual(d.rate, delivered)
        self.assertTrue(d.delay_emergency)
        # inside the 20 s cooldown: same landing value, no clearance spent
        d2 = observe(d.rate, 14.0)
        self.assertIn("probe overshoot", d2.reason)
        self.assertFalse(d2.delay_emergency)
        self.assertLessEqual(d2.rate, delivered)
        # past the cooldown the clearance is free again
        d3 = observe(d2.rate, 40.0)
        self.assertIn("probe overshoot", d3.reason)
        self.assertTrue(d3.delay_emergency)

    def test_a_failed_clearance_refunds_its_cooldown(self):
        """refund_delay_emergency buys back a clearance that never reached
        the tree; a real landing keeps its cooldown (dev band: the deferred
        severe-drop spent 30 s of cooldown on a commit that never was)."""
        g = gov()
        g._delay_emergency_last = None
        g._delay_emergency_prev = None
        self.assertFalse(g.refund_delay_emergency())
        g._delay_emergency_last = 100.0        # simulate the spend
        self.assertTrue(g.refund_delay_emergency())
        self.assertIsNone(g._delay_emergency_last)   # refunded to the None
        self.assertIsNone(g._delay_emergency_prev)
        self.assertFalse(g.refund_delay_emergency())     # nothing left
        g._delay_emergency_last = 100.0
        g._delay_emergency_prev = 40.0        # a previous clearance exists
        self.assertTrue(g.refund_delay_emergency())
        self.assertEqual(g._delay_emergency_last, 40.0)
        self.assertIsNone(g._delay_emergency_prev)


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
        d = self._pipecase(4.0)   # round 4: the window is one law slot (5 s)
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

    def test_a_stale_low_belief_never_clears_a_severe_landing(self):
        """The confidence-less severe branch needs a FALLING belief on a
        saturated link. A belief that merely SITS low (the up shapes park
        it below the applied rate because a sub-link tree never saturates
        the external link) must not be read as a drop."""
        g = gov()
        g.observe(belief=11.056144, belief_conf=0.2, belief_saturated=True,
                  applied=18.0, delivered=11.0,
                  backlog_bytes=int(60.0 * 11.0 * 125.0),
                  offered=11.0, now=0.0, min_rate=14.0)
        d = g.observe(belief=11.056144, belief_conf=0.2,
                      belief_saturated=True,
                      applied=18.0, delivered=11.0,
                      backlog_bytes=int(60.0 * 11.0 * 125.0),
                      offered=11.0, now=1.0, min_rate=14.0)
        # ceiling 9.95 < 0.9x18, but the belief did not FALL and the
        # confidence is below the declared 0.45 threshold: no clearance.
        self.assertFalse(d.delay_emergency)
        self.assertIn("ratchet down one step", d.reason)


class TestRound4SurvivalWindowAndIdleWire(unittest.TestCase):
    """Round 4 (docs/evidence/round3-params.md retune #4), measured on the
    dev smoke at 6917bd32:

    * the survival window was 7 s while the ladder's minimum spacing is the
      law's 5 s dwell, so a pierce was ALWAYS superseded before its window
      could conclude (seed1000: pierces at 7.4/12.7/18.1/23.4/28.7/34.0,
      promotions 0, terminal bind wiped the ladder to 0.57 utilization);
    * while the kernel apply lagged a pierce the governor re-proposed the
      SAME target for several ticks, and each re-proposal restarted the
      survival clock;
    * after the load stopped (an IDLE wire, not a shrinking link) the
      belief decayed and the bind committed a 25% descent inside the
      measured final third, costing ~0.08 utilization for nothing.
    """

    def _pierce(self, g, now):
        d = g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                      applied=16.52, delivered=16.0, backlog_bytes=0,
                      offered=15.7, now=now, min_rate=14.0,
                      tree_overlimit_per_s=200.0)
        self.assertTrue(d.reason.startswith("demand-probe up"))
        return d.rate

    def test_the_survival_window_fits_one_lawful_slot(self):
        """The structural guard: a survival window longer than the law's
        minimum dwell is unreachable at the pierce cadence it observes."""
        from aciq.ratecap import PROBE_HOLD_S
        from aciq.verifier import MIN_DWELL_S
        self.assertLessEqual(PROBE_HOLD_S, MIN_DWELL_S)

    def test_reproposing_a_pending_pierce_keeps_the_survival_clock(self):
        g = gov(hold_clear_s=2.0)
        g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                  applied=16.52, delivered=16.0, backlog_bytes=0,
                  offered=15.7, now=0.0, min_rate=14.0,
                  tree_overlimit_per_s=200.0)
        want = self._pierce(g, 6.0)
        # the kernel apply lags: the tree still reads the pre-pierce rate
        # and the governor re-proposes the SAME target for three ticks
        for t in (7.0, 8.0, 9.0):
            d = g.observe(belief=18.36, belief_conf=0.0,
                          belief_saturated=False, applied=16.52,
                          delivered=16.0, backlog_bytes=0, offered=15.7,
                          now=t, min_rate=14.0,
                          tree_overlimit_per_s=200.0)
            self.assertAlmostEqual(d.rate, want)
        # the apply lands one lawful slot after the pierce: the window has
        # run from the ORIGINAL stamp, so the pierce promotes
        d = g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                      applied=want, delivered=want, backlog_bytes=0,
                      offered=want, now=11.1, min_rate=14.0,
                      tree_overlimit_per_s=200.0)
        self.assertGreaterEqual(d.probe_known_good or 0.0, want - 0.01)

    def test_an_idle_wire_does_not_shrink_the_tree_on_a_decayed_belief(self):
        g = gov(hold_clear_s=2.0)
        g.observe(belief=66.0, belief_conf=0.7, belief_saturated=False,
                  applied=60.0, delivered=66.0, backlog_bytes=0,
                  offered=66.0, now=0.0, min_rate=14.0,
                  tree_overlimit_per_s=0.0)
        # the load stopped: nothing offered, nothing delivered, delay clear;
        # the belief decayed to 20 (ceiling 18). There is nothing to protect
        # and no evidence to shrink: hold the applied rate.
        d = g.observe(belief=20.0, belief_conf=0.7, belief_saturated=False,
                      applied=60.0, delivered=0.0, backlog_bytes=0,
                      offered=0.0, now=3.0, min_rate=14.0,
                      tree_overlimit_per_s=0.0)
        self.assertAlmostEqual(d.rate, 60.0)
        self.assertIn("idle wire", d.reason)

    def test_a_busy_wire_keeps_the_full_descent_on_a_decayed_belief(self):
        g = gov(hold_clear_s=2.0)
        g.observe(belief=93.0, belief_conf=0.7, belief_saturated=False,
                  applied=84.0, delivered=84.0, backlog_bytes=0,
                  offered=90.0, now=0.0, min_rate=35.0,
                  tree_overlimit_per_s=2000.0)
        # a small belief fall (93 -> 88.5, under the 10% severe line): the
        # wire still carries the flow, the delay sits between clear and
        # inflation, so the plain bind lands on the ceiling 79.65.
        d = g.observe(belief=88.5, belief_conf=0.7, belief_saturated=False,
                      applied=84.0, delivered=50.0, backlog_bytes=187_500,
                      offered=54.0, now=3.0, min_rate=35.0,
                      tree_overlimit_per_s=2000.0)
        self.assertAlmostEqual(d.rate, 79.65)
        self.assertIn("ceiling binds", d.reason)
        self.assertFalse(d.delay_emergency)

    def test_a_pending_pierce_survives_an_idle_wire(self):
        g = gov(hold_clear_s=2.0)
        g.observe(belief=18.36, belief_conf=0.0, belief_saturated=False,
                  applied=16.52, delivered=16.0, backlog_bytes=0,
                  offered=15.7, now=0.0, min_rate=14.0,
                  tree_overlimit_per_s=200.0)
        want = self._pierce(g, 6.0)
        # the load ended before the apply landed: the bind must keep the
        # pending probe alive, not cancel it to the decayed ceiling
        d = g.observe(belief=12.0, belief_conf=0.0, belief_saturated=False,
                      applied=16.52, delivered=0.0, backlog_bytes=0,
                      offered=0.0, now=7.0, min_rate=14.0,
                      tree_overlimit_per_s=0.0)
        self.assertAlmostEqual(d.rate, want)
        self.assertIn("pending on an idle wire", d.reason)


if __name__ == "__main__":
    unittest.main()


class TestRound5SevereLanding(unittest.TestCase):
    """Round 5 (the 1-seed real smoke at 6917bd32, data/runs_smoke_r4a):

    * s2b_step_50 seed1000: pre-drop pierce 105.74 on a 100 link; at 1.7 s
      post-drop the belief had fallen 83 -> 64.6 but confidence had decayed
      on a link the pre-drop tree never saturated, so the severe gate
      refused and the law walked 79.3/59.5/52.2 = 11.7 s;
    * s7_down_100to8 seed1000: the first severe landing at 65 was stale,
      the belief then snapped to 8.3 two seconds later inside the emergency
      cooldown, and the 25 % walk needed 16.6 s.

    Both are a falling belief on a saturated bottleneck. Retune #5 admits
    that signature without the confidence gate and lets a COLLAPSE bypass
    the shared clearance cooldown.
    """

    def test_falling_saturated_belief_lands_in_one_commit(self):
        g = gov()
        # pre-drop: belief 94, tree 84.59, clear delay
        g.observe(belief=94.0, belief_conf=0.0, belief_saturated=False,
                  applied=84.59, delivered=94.0, backlog_bytes=0,
                  offered=75.2, now=0.0, min_rate=25.3,
                  tree_overlimit_per_s=200.0)
        # the pierce sits at 105.74 and the belief falls 94 -> 83 while the
        # delay is still clear (the link is 100, so the bottleneck is not
        # saturated yet): no clearance may fire pre-drop
        g.observe(belief=83.0, belief_conf=0.0, belief_saturated=False,
                  applied=105.74, delivered=75.6, backlog_bytes=5_000,
                  offered=75.6, now=1.0, min_rate=25.3,
                  tree_overlimit_per_s=200.0)
        # 1.7 s post-drop: belief 64.6, delay 15.9 ms (below the ratchet),
        # confidence 0.3 (< 0.45) -> must still land in ONE commit
        d = g.observe(belief=64.6, belief_conf=0.3, belief_saturated=True,
                      applied=105.74, delivered=52.4,
                      backlog_bytes=int(15.9 * 52.4 * 125.0),
                      offered=55.6, now=2.0, min_rate=25.3,
                      tree_overlimit_per_s=0.0)
        self.assertTrue(d.delay_emergency)
        # Round 6: the landing is clamped to what the wire actually carries
        # (52.4), never the stale ceiling (58.14) -- on a 50 Mbps link the
        # ceiling alone would sit above the gate band (top 55.0). Retune
        # #11: this sample is the drop tick itself (nothing has drained
        # yet), so the landing takes the ratchet's 10 % hysteresis below
        # it: 52.4 -> 47.16, still inside the 55.0 band.
        self.assertAlmostEqual(d.rate, 47.16)
        self.assertIn("severe drop", d.reason)

    def test_collapse_bypasses_the_clearance_cooldown(self):
        g = gov(delay_emergency_cooldown_s=30.0)
        g.observe(belief=92.0, belief_conf=1.0, belief_saturated=True,
                  applied=92.0, delivered=92.0, backlog_bytes=0,
                  offered=90.0, now=0.0, min_rate=14.0,
                  tree_overlimit_per_s=200.0)
        # first severe landing at 65: spends the one clearance
        d = g.observe(belief=72.2, belief_conf=1.0, belief_saturated=True,
                      applied=92.12, delivered=11.0,
                      backlog_bytes=int(25.4 * 11.0 * 125.0),
                      offered=11.0, now=1.0, min_rate=14.0,
                      tree_overlimit_per_s=200.0)
        self.assertTrue(d.delay_emergency)
        # 2 s later the belief snaps to the true 8.3 while the cooldown is
        # still running: the COLLAPSE (7.47 < 0.5 x 58.52) must still land
        d = g.observe(belief=8.3, belief_conf=1.0, belief_saturated=True,
                      applied=58.52, delivered=8.3,
                      backlog_bytes=int(42.9 * 8.3 * 125.0),
                      offered=8.3, now=3.0, min_rate=14.0,
                      tree_overlimit_per_s=200.0)
        self.assertTrue(d.delay_emergency)
        self.assertAlmostEqual(d.rate, 14.0)
        self.assertIn("cooldown bypassed", d.reason)

    def test_a_stale_low_belief_does_not_clear_on_a_busy_up_tree(self):
        """The up shapes must keep climbing: a constant low belief under a
        sub-link tree is not a drop and never clears a landing."""
        g = gov()
        g.observe(belief=18.5, belief_conf=0.0, belief_saturated=False,
                  applied=55.53, delivered=39.5, backlog_bytes=0,
                  offered=50.0, now=0.0, min_rate=14.0,
                  tree_overlimit_per_s=200.0)
        d = g.observe(belief=18.5, belief_conf=0.0, belief_saturated=False,
                      applied=55.53, delivered=39.5, backlog_bytes=0,
                      offered=50.0, now=1.0, min_rate=14.0,
                      tree_overlimit_per_s=200.0)
        self.assertFalse(d.delay_emergency)


class TestRound6DownRegime(unittest.TestCase):
    """Round 6 (real 1-seed smoke at ed34fa3e, data/runs_smoke_r5).

    Two defects the down family still carried after retune #5:

    * s2b_step_50 seed1000/1002 landed 8.1/8.0 s after the drop, because the
      first post-drop bind proposed the stale ceiling (58.2) which the law
      clamped to a 56.4/69.0 step -- still above the 55.0 band top -- and the
      landing only arrived via the belief's slow decay. The wire was already
      carrying 52.2 of the tree's 75-92 (0.69-0.57), i.e. the ceiling is
      stale-HIGH, not low.
    * after landing, the demand probe kept re-piercing 41.3 -> 51.6 -> 64.5
      -> 71.6 on a 50 Mbps link: the derived offered (= 0.85 x applied)
      always satisfies the demand test and the shielded call's delay never
      sees the parent queue, so the probe ran every window.
    """

    def _prime(self, g, applied: float) -> None:
        g.observe(belief=83.5, belief_conf=0.0, belief_saturated=False,
                  applied=applied, delivered=67.2, backlog_bytes=0,
                  offered=67.2, now=0.0, min_rate=14.0,
                  tree_overlimit_per_s=5000.0)

    def test_falling_belief_above_a_stale_ceiling_lands_at_the_delivered(self):
        g = gov()
        self._prime(g, applied=75.15)
        # drop at t=10: belief 83.5 -> 64.7, ceiling 58.24 (stale-high: the
        # wire carries 52.18), confidence 0.3, bottleneck not flagged
        # saturated -- the falling belief + under-delivery is the signal
        # A 32 ms raw queue (the measured 15.9-24 ms EMA band) is not clear,
        # so the bind branch -- where the drop landing lives -- is reached.
        d = g.observe(belief=64.7, belief_conf=0.3, belief_saturated=False,
                      applied=75.15, delivered=52.18,
                      backlog_bytes=int(32.0 * 52.18 * 125.0),
                      offered=52.0, now=10.0, min_rate=14.0,
                      tree_overlimit_per_s=3886.0)
        self.assertTrue(d.delay_emergency)
        # Retune #11: the drop tick is the window minimum (fresh drain),
        # so the landing sits 10 % under the carried 52.18.
        self.assertAlmostEqual(d.rate, 46.962)
        self.assertIn("severe drop", d.reason)

    def test_a_pierce_that_overshot_a_healthy_link_is_not_a_drop(self):
        """The pre-drop tick of the same smoke: applied 105.74 (a pierce) on
        the still-100 Mbps link, delivered 75.6 -- above the ceiling (74.7),
        so the wire is carrying what the estimate says it can: no landing."""
        g = gov()
        g.observe(belief=94.0, belief_conf=0.0, belief_saturated=False,
                  applied=105.74, delivered=95.0, backlog_bytes=0,
                  offered=75.2, now=0.0, min_rate=14.0,
                  tree_overlimit_per_s=200.0)
        d = g.observe(belief=83.0, belief_conf=0.0, belief_saturated=False,
                      applied=105.74, delivered=75.6, backlog_bytes=5_000,
                      offered=75.6, now=1.0, min_rate=14.0,
                      tree_overlimit_per_s=200.0)
        self.assertFalse(d.delay_emergency)

    def test_drop_lands_in_one_commit_inside_the_emergency_cooldown(self):
        """The real seed1000 sequence: a pre-drop severe at t=7.5 spent the
        20 s clearance, so the 12.8 s drop bind was law-clamped to 56.36
        (band top 55.0) and the gate only passed at 8.13 s. A wire carrying
        52.18 of 75.15 is under-delivery evidence strong enough to land now.
        """
        g = RateGovernor()
        pre = g.observe(belief=83.5, belief_conf=0.5, belief_saturated=True,
                        applied=105.92, delivered=83.5, backlog_bytes=0,
                        offered=90.0, now=7.5, min_rate=29.2,
                        tree_overlimit_per_s=3600.0)
        self.assertTrue(pre.delay_emergency)
        d = g.observe(belief=64.7, belief_conf=0.3, belief_saturated=False,
                      applied=75.15, delivered=52.18,
                      backlog_bytes=int(21.7 * 75.15 * 125.0),
                      offered=63.9, now=12.83, min_rate=29.2,
                      tree_overlimit_per_s=3700.0)
        self.assertTrue(d.delay_emergency)
        # Retune #11: the drop tick itself is the only sub-applied sample,
        # so the landing takes the 10 % transient margin: 52.18 -> 46.96.
        self.assertAlmostEqual(d.rate, 46.962, delta=0.1)
        self.assertIn("severe drop", d.reason)
        self.assertLess(d.rate, 56.36)  # not the law's 25% step from 75.15

    def test_landing_uses_the_drained_rate_not_the_drain_transient(self):
        """s2b_step_50 seed1002: at the drop tick the 1 s delivered sample was
        55.69 (0.69 above the 55.0 band top) because the pre-drop queue was
        still draining; the tick before had carried 52.39. Land on the
        drained rate, or the follow-up bind misses the 8 s budget.
        """
        g = RateGovernor()
        first = g.observe(belief=70.3, belief_conf=0.3,
                          belief_saturated=False, applied=105.54,
                          delivered=52.39, backlog_bytes=0, offered=89.7,
                          now=11.67, min_rate=29.2,
                          tree_overlimit_per_s=3700.0)
        self.assertFalse(first.delay_emergency)
        d = g.observe(belief=70.3, belief_conf=0.5, belief_saturated=False,
                      applied=79.15, delivered=55.69,
                      backlog_bytes=int(20.3 * 79.15 * 125.0),
                      offered=67.3, now=12.79, min_rate=29.2,
                      tree_overlimit_per_s=3700.0)
        self.assertTrue(d.delay_emergency)
        self.assertAlmostEqual(d.rate, 52.39, delta=0.1)
        self.assertIn("severe drop", d.reason)

    def test_a_fresh_drain_transient_lands_inside_the_band(self):
        """s2b_step_50 seed1001 (dev band 2026-11-01): the drop tick's FIRST
        sample was 55.38 -- the pre-drop queue still draining -- while the
        new truth was 50.0, so landing on it sat 0.38 ABOVE the 55.0 band
        top; the tree then held 55.38 until the belief fell at t+9.5 s
        (budget 8.0 s). No earlier sample had drained below the carry, so
        this is the fresh-drain case retune #11 covers: land 10 % under
        the carried rate, inside the band by construction.
        """
        g = RateGovernor()
        g.observe(belief=85.0111008, belief_conf=1.0, belief_saturated=True,
                  applied=107.23, delivered=96.56,
                  backlog_bytes=int(1.0 * 96.56 * 125.0),
                  offered=96.6, now=9.81, min_rate=29.2,
                  tree_overlimit_per_s=1000.0)
        d = g.observe(belief=85.0111008, belief_conf=1.0,
                      belief_saturated=True, applied=107.23,
                      delivered=55.38,
                      backlog_bytes=int(20.4 * 55.38 * 125.0),
                      offered=55.4, now=10.88, min_rate=29.2,
                      tree_overlimit_per_s=1000.0)
        self.assertTrue(d.delay_emergency)
        self.assertIn("severe drop", d.reason)
        self.assertAlmostEqual(d.rate, 49.842, delta=0.1)
        self.assertLessEqual(d.rate, 55.0)   # the judge's 1.10x band top
        self.assertGreaterEqual(d.rate, 29.2)  # never under the plan floor

    def test_no_pierce_while_the_belief_is_in_a_drop_regime(self):
        """After the landing the belief sits at 41-46 while its recent
        maximum was 81.7: not a stale-low ceiling. The tree holds at the
        ceiling instead of re-piercing above the dropped link."""
        g = gov()
        g.observe(belief=81.7, belief_conf=0.0, belief_saturated=False,
                  applied=91.97, delivered=52.2, backlog_bytes=0,
                  offered=52.0, now=0.0, min_rate=14.0,
                  tree_overlimit_per_s=3000.0)
        applied = 41.29
        g.observe(belief=41.3, belief_conf=0.0, belief_saturated=False,
                  applied=applied, delivered=36.85, backlog_bytes=0,
                  offered=36.8, now=6.0, min_rate=14.0,
                  tree_overlimit_per_s=3400.0)
        d = g.observe(belief=40.6, belief_conf=0.0, belief_saturated=False,
                      applied=applied, delivered=36.85, backlog_bytes=0,
                      offered=36.8, now=12.0, min_rate=14.0,
                      tree_overlimit_per_s=3400.0)
        self.assertNotIn("demand-probe up", d.reason)
        # Round 7: a wire carrying 36.85 of 41.29 with the tree overlimit
        # is the sustained-shortfall landing, not a hold. What this test
        # forbids is the PIERCE, so the rate may only move DOWN.
        self.assertLessEqual(d.rate, applied)

    def test_a_pending_pierce_is_held_on_a_clear_wire(self):
        """The first-up-shape rung: the pierce 17.14 -> 21.42 at t+1.1 s was
        undone by the bind branch because the 10 s climb clock had not
        matured. One rung of a budget-bound ladder is not expendable."""
        g = gov()
        g.observe(belief=19.04, belief_conf=0.0, belief_saturated=False,
                  applied=None, delivered=16.4, backlog_bytes=0,
                  offered=15.4, now=0.0, min_rate=14.0,
                  tree_overlimit_per_s=0.0)
        g.observe(belief=17.45, belief_conf=0.0, belief_saturated=False,
                  applied=17.14, delivered=16.4, backlog_bytes=0,
                  offered=15.4, now=3.0, min_rate=14.0,
                  tree_overlimit_per_s=0.0)
        d = g.observe(belief=17.45, belief_conf=0.0, belief_saturated=False,
                      applied=17.14, delivered=16.4, backlog_bytes=0,
                      offered=15.4, now=8.0, min_rate=14.0,
                      tree_overlimit_per_s=1250.0)
        self.assertIn("demand-probe up", d.reason)
        probe = d.rate
        # 1.1 s later: delay clear, belief flat (17.45), ceiling 15.7 below
        # the applied probe. The stale ceiling must NOT undo the pierce.
        d = g.observe(belief=17.45, belief_conf=0.0, belief_saturated=False,
                      applied=probe, delivered=16.4, backlog_bytes=0,
                      offered=15.4, now=9.1, min_rate=14.0,
                      tree_overlimit_per_s=0.0)
        self.assertGreaterEqual(d.rate, probe)
        self.assertIn("verifying", d.reason)



class TestRound7DevBand(unittest.TestCase):
    """Round 7 (real dev band at fdfd2cf6, data/runs_dev3).

    Two defects the up shapes still carried after retune #6 -- six judged
    FAILs. The one fixed here: s7_rampup_30to100 seed1008 and s7_up_20to60
    seed1002 committed a severe drop at the STALE-LOW ceiling in one commit
    while the wire's own evidence said the link was healthy: ceiling
    40.78 < 0.90x applied 121.33 with the wire carrying 104.58 (0.86x
    applied), and ceiling 27.38 < 0.90x applied 82.10 with the wire
    carrying 63.00. wire_dropped is false in exactly those ticks (the
    carried 63.00 sits ABOVE the stale 27.38 ceiling), so the round-6 min()
    left the stale ceiling owning the landing and the final-third
    utilization failed.

    The second family (s2b_step_up_20to100 seeds 1001/1002/1003/1008
    stalling at the top of the recovery shape) was diagnosed to a
    change-budget starvation during this round's analysis, but the
    recording contradicts the hypothesis: the budget was left at 6 (see
    docs/evidence/round3-params.md round 7). Those seeds re-run in the next
    dev band with the landing fixed; the diagnosis resumes if they fail
    again.

    The fixtures reproduce the recorded ticks with SUSTAINED state: the
    delay EMA seeds at the first observation's raw delay (DELAY_ALPHA=0.5)
    and 20 ms must be crossed by the land tick itself, so every fixture
    primes with a mid-band (10-20 ms, breaks clear, not inflating) tick
    whose ceiling sits above the applied rate (no bind), then lands.
    """

    def test_stale_low_ceiling_lands_at_the_wire_rate(self):
        """s7_rampup seed1008, rel 42.8: a rising ladder (121.33 applied,
        wire 104.58, estimate still 45.31 because the release dwell feeds
        the estimate once per MIN_DWELL_S) must land at the wire's drained
        rate, not at the 40.78 ceiling the stale estimate produced."""
        g = gov()
        g.observe(belief=140.0, belief_conf=0.5, belief_saturated=True,
                  applied=121.33, delivered=104.58,
                  backlog_bytes=int(15.0 * 104.58 * 125.0),
                  offered=104.58, now=39.0, min_rate=14.0,
                  tree_overlimit_per_s=4700.0)
        d = g.observe(belief=45.31, belief_conf=0.5, belief_saturated=True,
                      applied=121.33, delivered=104.58,
                      backlog_bytes=int(40.0 * 104.58 * 125.0),
                      offered=104.58, now=42.5, min_rate=14.0,
                      tree_overlimit_per_s=4800.0)
        self.assertTrue(d.delay_emergency)
        self.assertIn("severe drop", d.reason)
        self.assertAlmostEqual(d.rate, 104.58, msg=d.reason)

    def test_drained_carried_rate_not_the_transient_owns_the_floor(self):
        """s7_up seed1002, rel 43.1: ceiling 27.38 below a wire carrying
        63.00 of 82.10. The landing window still holds the earlier
        delivered sample (59.1), so the drained carried rate -- not the
        stale ceiling -- is the landing."""
        g = gov()
        g.observe(belief=95.0, belief_conf=0.5, belief_saturated=True,
                  applied=82.10, delivered=59.1,
                  backlog_bytes=int(15.0 * 59.1 * 125.0),
                  offered=63.0, now=38.3, min_rate=14.0,
                  tree_overlimit_per_s=3300.0)
        d = g.observe(belief=30.42, belief_conf=0.5, belief_saturated=True,
                      applied=82.10, delivered=63.0,
                      backlog_bytes=int(40.0 * 63.0 * 125.0),
                      offered=63.0, now=42.0, min_rate=14.0,
                      tree_overlimit_per_s=3400.0)
        self.assertTrue(d.delay_emergency)
        self.assertIn("severe drop", d.reason)
        self.assertAlmostEqual(d.rate, 59.1, msg=d.reason)

    def test_wire_dropped_landing_keeps_the_round6_anchor(self):
        """The round-6 anchor: a stale-HIGH ceiling over a collapsed wire
        still lands at min(ceiling, delivered, drained) -- 52.18 of 75.15,
        delivered below both the 0.8x bound and the ceiling -- with retune
        #11's 10 % transient margin when the drop tick is the only sample
        (46.96). The prime keeps the EMA mid-band so the land tick itself
        crosses the 20 ms threshold (the recorded run's delay rose through
        the same path)."""
        g = gov()
        g.observe(belief=83.5, belief_conf=0.0, belief_saturated=False,
                  applied=75.15, delivered=67.2,
                  backlog_bytes=int(12.0 * 67.2 * 125.0),
                  offered=67.2, now=6.0, min_rate=14.0,
                  tree_overlimit_per_s=5000.0)
        d = g.observe(belief=64.7, belief_conf=0.3, belief_saturated=False,
                      applied=75.15,                       delivered=52.18,
                      backlog_bytes=int(32.0 * 52.18 * 125.0),
                      offered=52.0, now=10.0, min_rate=14.0,
                      tree_overlimit_per_s=3886.0)
        self.assertTrue(d.delay_emergency)
        self.assertIn("severe drop", d.reason)
        self.assertAlmostEqual(d.rate, 46.962)


class TestRetune12(unittest.TestCase):
    """Retune #12 (dev band 2026-11-01 at 19e9e8a5, 96 PASS / 4 FAIL).

    A. `s2b_ramp_100to30` seeds 1001/1007 walked 42.1 -> 37.9 -> 31.4 in
       10.4 s (budget 8.0 s): the 10 % ratchet plus the 5 s dwell needs
       three commits to cross a >22 % gap. When the wire has itself
       demonstrated it cannot carry the applied (`wire_dropped`), the
       ordinary ratchet takes the law's full 25 % envelope instead.
    B. `s2b_step_50` seed1008 landed at the drop tick's instantaneous
       delivered 55.897 on a 50 truth (band 55.0) and re-entered at 9.4 s.
       When the wire sits BELOW the belief at the overshoot tick (the
       drain, not the up lanes' stale-low probe), the landing is capped at
       the 4 s carried minimum.
    """

    def test_wire_dropped_ratchet_takes_the_full_law_step(self):
        g = gov()
        d = g.observe(belief=68.5, applied=46.823, delivered=32.40,
                      backlog_bytes=int(23.9 * 32.40 * 125.0),
                      offered=32.4, now=29.85, min_rate=14.0,
                      belief_conf=0.0, belief_saturated=False)
        self.assertEqual(
            d.reason,
            "delay inflated 23.9 ms > 20 ms: ratchet down one step")
        self.assertAlmostEqual(d.rate, 46.823 * 0.75, places=6)

    def test_ratchet_without_wire_evidence_keeps_the_gentle_step(self):
        """The full envelope is wire-evidence-only: a delay ratchet whose
        wire still carries >= 0.8x applied keeps the 10 % pace."""
        g = gov()
        d = g.observe(belief=68.5, applied=46.823, delivered=45.0,
                      backlog_bytes=int(23.9 * 45.0 * 125.0),
                      offered=45.0, now=29.85, min_rate=14.0,
                      belief_conf=0.0, belief_saturated=False)
        self.assertAlmostEqual(d.rate, 46.823 * 0.9, places=6)

    def test_overshoot_lands_at_the_drained_carry_below_the_belief(self):
        """seed1008's tick: wire 55.90 of applied 69.80 with the belief
        above (ceiling 65.40), the tick before carried 52.40. Land at the
        carried 52.40, inside the 55.0 band -- not the 55.90 transient."""
        g = gov()
        g._known_good = 93.07
        g._last_rise = (9.78, 116.34)
        g._delivered_hist.append((12.93, 52.40))
        d = g.observe(belief=72.667, applied=69.803, delivered=55.897,
                      backlog_bytes=int(22.9 * 55.897 * 125.0),
                      offered=55.9, now=14.05, min_rate=35.0)
        self.assertTrue(d.reason.startswith("probe overshoot"))
        self.assertAlmostEqual(d.rate, 52.40, places=6)
        self.assertLessEqual(d.rate, 55.0)   # the judge's band top

    def test_overshoot_at_a_stale_low_ceiling_keeps_the_wire_rate(self):
        """The up lanes' overshoot carries MORE than the belief (s7_rampup
        seed1008: wire 109.12, ceiling 36.0). That is the healthy wire the
        tree overshot, not a drain: no carried cap, the 109.12 landing
        stands."""
        g = gov()
        g._known_good = 128.75
        g._last_rise = (20385.0, 128.75)
        g._delivered_hist.append((20384.0, 96.04))
        d = g.observe(belief=40.0, applied=128.75, delivered=109.12,
                      backlog_bytes=int(21.5 * 109.12 * 125.0),
                      offered=109.1, now=20386.1, min_rate=14.0)
        self.assertTrue(d.reason.startswith("probe overshoot"))
        self.assertAlmostEqual(d.rate, 109.12, places=6)


class TestSustainedShortfall(unittest.TestCase):
    """Round 7: s2b_ramp_100to30 seed1003.

    The ramp ended at 30 Mbps at t=30. The estimator's ceiling sat at 42.8
    until t=38 and only entered the 33.0 band at t=44, so the bind branch
    could not land. The CLEAR branch held at 33.45 with "offered 32.0 does
    not demand it" while the wire carried 31.5 and the estimator's own
    saturation flag was true. The trees's deliver signal (saturated belief
    or overlimit) is the evidence the ceiling lags; three clear seconds of
    it land at the carry, never below.
    """

    def _ramp_context(self, g: RateGovernor) -> None:
        """One high-belief tick first: the drop regime needs a recent max."""
        g.observe(belief=100.0, belief_conf=1.0, belief_saturated=True,
                  applied=90.0, delivered=90.0, backlog_bytes=0,
                  offered=90.0, now=0.0, min_rate=14.0,
                  tree_overlimit_per_s=2500.0)

    def _shortfall_tick(self, g: RateGovernor, now: float, *,
                        saturated: bool = True, overlimit: float = 2500.0,
                        delivered: float = 31.5):
        return g.observe(belief=47.5, belief_conf=1.0,
                         belief_saturated=saturated,
                         applied=33.45, delivered=delivered,
                         backlog_bytes=6056, offered=31.5, now=now,
                         min_rate=14.0,
                         tree_overlimit_per_s=overlimit)

    def test_three_clear_seconds_land_at_the_carry(self):
        g = gov()
        self._ramp_context(g)
        for t in (1.0, 2.0, 3.0):
            d = self._shortfall_tick(g, t)
            self.assertFalse(d.changed)
        d = self._shortfall_tick(g, 4.0)
        self.assertAlmostEqual(d.rate, 31.5, places=6)
        self.assertIn("land at the carry", d.reason)
        self.assertLessEqual(d.rate, 33.0)

    def test_a_single_light_tick_does_not_restart_the_window(self):
        """seed1003 has one overlimit=0 tick at t=39.5; the 3 s window must
        survive it rather than wait another three seconds."""
        g = gov()
        self._ramp_context(g)
        for t in (1.0, 2.0):
            self._shortfall_tick(g, t)
        self._shortfall_tick(g, 3.0, overlimit=0.0, saturated=False)
        d = self._shortfall_tick(g, 4.0)
        self.assertAlmostEqual(d.rate, 31.5, places=6)

    def test_no_saturation_witness_is_under_demand_not_a_drop(self):
        """A healthy bulk rides at 0.89-0.96x applied without saturating;
        it must not ratchet the tree. Same numbers, no witness."""
        g = gov()
        self._ramp_context(g)
        for t in (1.0, 2.0, 3.0, 4.0, 5.0):
            d = self._shortfall_tick(g, t, saturated=False, overlimit=0.0)
        self.assertEqual(d.rate, 33.45)
        self.assertNotIn("land at the carry", d.reason)

    def test_a_healthy_rising_link_is_not_a_drop_regime(self):
        """The witness is present but the belief is at its recent maximum:
        that is a probe on a healthy link, not a capacity fall."""
        g = gov()
        for t in range(0, 7):
            d = g.observe(belief=40.0 + t, belief_conf=1.0,
                          belief_saturated=True,
                          applied=40.0, delivered=36.0,
                          backlog_bytes=6056, offered=36.0, now=float(t),
                          min_rate=14.0, tree_overlimit_per_s=2500.0)
            self.assertFalse(d.reason.startswith("wire carried"))

    def test_the_carry_lands_once_per_descent(self):
        """The full dev band re-fired the carry branch every hold window:
        seed1001 landed at 29.4, then 26, 21, 14 while the link stayed 30.
        Delivered rides below applied even when healthy, so the branch must
        not keep chasing it. One descent, one carry landing."""
        g = gov()
        self._ramp_context(g)
        for t in (1.0, 2.0, 3.0):
            self._shortfall_tick(g, t)
        d = self._shortfall_tick(g, 4.0)
        self.assertAlmostEqual(d.rate, 31.5, places=6)
        for t in (5.0, 6.0, 7.0, 8.0, 9.0):
            d = g.observe(belief=47.5, belief_conf=1.0,
                          belief_saturated=True, applied=31.5,
                          delivered=24.0, backlog_bytes=6056,
                          offered=24.0, now=t, min_rate=14.0,
                          tree_overlimit_per_s=2500.0)
            self.assertFalse(d.reason.startswith("wire carried"),
                             f"the carry branch fired twice: {d.reason}")
            self.assertAlmostEqual(d.rate, 31.5, places=6)

    def test_an_idle_wire_is_not_a_shortfall_landing(self):
        """A zero carry is no demand, not a drop. Landing at it would hit
        the floor and leave the tree half the truth."""
        g = gov()
        self._ramp_context(g)
        for t in (1.0, 2.0, 3.0, 4.0):
            d = g.observe(belief=47.5, belief_conf=1.0,
                          belief_saturated=True, applied=14.3,
                          delivered=0.0, backlog_bytes=0,
                          offered=0.0, now=t, min_rate=14.0,
                          tree_overlimit_per_s=2500.0)
            self.assertFalse(d.reason.startswith("wire carried"))
            self.assertAlmostEqual(d.rate, 14.3, places=6)
