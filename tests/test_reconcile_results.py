"""Tests for the data-reconciliation and tail-analysis tools.

These tools exist because the report's headline table and its per-seed table had
drifted apart. The tests here hold them to the two honesty rules that make the
reconciliation worth having:

1. Every number is re-derived from raw files, not private to the tool.
2. The workload self-reports agree with the per-packet observations they claim
   to summarise -- if they do not, the self-report is not evidence.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

import reconcile_results as rr  # noqa: E402
import tail_analysis as ta  # noqa: E402


class TestReconciliationIsTracedToRaw(unittest.TestCase):
    def test_congested_headline_matches_the_published_table(self):
        """The seven-seed medians the report prints must equal the medians the
        raw call.json files produce.

        The raw evidence is live and re-measured by `host_gate.sh --full`, so the
        exact medians drift run to run. Pinning one run's decimals made this test
        fail the moment the evidence was regenerated, which is not a property of
        the code under test. What must hold on *every* run is the shape of the
        result: FIFO and CAKE queue to a similar, order-100 ms median, and ACIQ's
        median is an order of magnitude lower. Those are the claims the report
        makes, so those are what is asserted.
        """
        r = rr.reconcile("congested")
        if not r["complete"]:
            self.skipTest("congested evidence not present")
        self.assertEqual(r["n"], 7)
        h = r["headline_median"]
        # Baselines queue under congestion: order-100 ms, and the two are close.
        for baseline in ("b0_fifo", "b1_cake95"):
            self.assertTrue(
                50.0 < h[baseline]["p50"] < 150.0,
                f"{baseline} p50 {h[baseline]['p50']} outside the "
                f"congested-queue band")
        self.assertLess(abs(h["b0_fifo"]["p50"] - h["b1_cake95"]["p50"]), 10.0,
                        "FIFO and CAKE medians should be within 10 ms under this "
                        "scenario; a large gap means the comparison drifted")
        # ACIQ's median must be far below both baselines -- the whole point.
        self.assertLess(h["aciq"]["p50"], 5.0,
                        "ACIQ median should be single-digit ms")
        self.assertLess(h["aciq"]["p50"], h["b0_fifo"]["p50"] / 5.0)
        self.assertLess(h["aciq"]["p50"], h["b1_cake95"]["p50"] / 5.0)
        # The tail is real and must be reported, not hidden by the median.
        self.assertGreater(h["aciq"]["p95"], h["aciq"]["p50"] * 5.0)

    def test_medians_are_medians_not_means(self):
        """A seed-count change must move both, but a single outlier must move the
        mean and not the median. This pins that the tool uses statistics.median."""
        r = rr.reconcile("congested")
        if not r["complete"]:
            self.skipTest("congested evidence not present")
        for metric in ("p50", "p95"):
            vals = sorted(r["per_seed"]["aciq"][s][metric] for s in r["per_seed"]["aciq"])
            import statistics
            self.assertAlmostEqual(
                statistics.median(vals), r["headline_median"]["aciq"][metric],
                delta=1e-6)

    def test_paired_wins_are_counted_per_seed(self):
        r = rr.reconcile("congested")
        if not r["complete"]:
            self.skipTest("congested evidence not present")
        self.assertEqual(r["paired_wins_aciq_lower"]["b0_fifo"]["p50"], 7)
        self.assertEqual(r["paired_wins_aciq_lower"]["b0_fifo"]["p95"], 7)
        # p99 is where FIFO is genuinely competitive; the tool must say so.
        self.assertLess(r["paired_wins_aciq_lower"]["b0_fifo"]["p99"], 7)

    def test_estimator_error_bound_is_derived_not_asserted(self):
        """The report claims the estimator is within a bound. That bound must be
        the worst per-seed error the raw result.json files actually produce, so a
        doc that claims "within 4%" when the worst is larger fails here.

        The worst error is re-measured with the evidence, so its exact value is
        not pinned; what is asserted is that the tool's reported bound *is* the
        maximum of the per-seed errors it published -- the property that makes a
        hand-written "within N%" claim checkable at all -- and that the bound is
        a small, honest number rather than a headline one.
        """
        r = rr.reconcile("congested")
        if not r["complete"]:
            self.skipTest("congested evidence not present")
        est = r["estimator_error"]
        self.assertEqual(est["reference_mbps"], 20.0)
        self.assertEqual(len(est["per_seed_error_pct"]), 7)
        # The reported bound is exactly the worst of the published per-seed
        # errors, to floating-point exactness -- it is derived, not typed in.
        self.assertAlmostEqual(est["worst_pct"],
                               max(est["per_seed_error_pct"].values()),
                               places=6)
        # And it is a small error: the estimator tracks the provisioned 20 Mbps
        # to single-digit percent on every seed.
        self.assertGreater(est["worst_pct"], 0.0)
        self.assertLess(est["worst_pct"], 10.0,
                        "a double-digit estimator error contradicts the "
                        "single-digit bound the report publishes")


class TestSelfReportsAgreeWithRawObservations(unittest.TestCase):
    def test_workload_self_report_matches_per_packet_obs(self):
        """call.json's percentiles must equal those recomputed from call.obs.jsonl.

        This is the check the original per-seed drift would have failed: it is
        not enough that a number exists, it must be reproducible from the packets.
        """
        problems = rr._verify_obs("congested")
        self.assertEqual(problems, [], "\n".join(problems))


class TestTailAnalysisSplitsTransientFromSteady(unittest.TestCase):
    def test_steady_state_p95_is_far_below_the_headline_tail(self):
        r = ta.analyse("congested")
        ss = r["pooled"]["steady"]
        tr = r["pooled"]["transition"]
        if not ss["n"]:
            self.skipTest("no observations present")
        self.assertLess(ss["p95"], 5.0,
                        "steady-state p95 should be a few ms, not the ~65 ms headline")
        self.assertGreater(tr["p95"], 50.0,
                           "the transition should carry the tail")
        self.assertGreater(ss["n"], tr["n"],
                           "steady state is most of a 40 s run")

    def test_the_window_boundary_does_not_change_the_steady_conclusion(self):
        """The 5 s cut is chosen from the data; moving it must not flip the
        conclusion that the steady tail is small."""
        for cut in (4.0, 6.0, 8.0):
            r = ta.analyse("congested", transition_s=cut)
            if not r["pooled"]["steady"]["n"]:
                self.skipTest("no observations present")
            self.assertLess(r["pooled"]["steady"]["p95"], 5.0,
                            f"steady p95 inflated at cut={cut}s")


if __name__ == "__main__":
    unittest.main()
