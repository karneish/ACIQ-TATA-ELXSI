"""Tests for the cross-mode fairness and starvation metrics (T3 fix).

The contract: the fairness number must be a function of the SCENARIO's
assigned flows and their generator-reported rates only. Kernel-counter
attribution differences between systems must not be able to change it, and
starvation must be visible in a minimum-over-time that a mean cannot hide.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aciq import fairness as F  # noqa: E402


S1_CALL_BULK = {
    "call": {"label": "call", "pps_achieved": 50.0, "sender_mbps": None},
    "bulk": {"label": "bulk", "sender_mbps": 39.0},
}
# The SAME scenario, some other system: identical input by construction, but
# written from a different artefact to prove nothing about the module knows
# which system produced it.
S1_CALL_BULK_OTHER_MODE = {
    "call": {"label": "call", "pps_achieved": 50.0},
    "bulk": {"label": "bulk", "sender_mbps": 39.0},
}
# A rate metric list that is maximally unequal still gets a bounded score.
THREE_FLOWS = {"tv1": {"kind": "video", "sender_mbps": 1.0},
               "tv2": {"kind": "video", "sender_mbps": 2.0},
               "tv3": {"kind": "video", "sender_mbps": 3.0}}


class TestFlowRates(unittest.TestCase):
    def test_only_assigned_flows(self):
        # six classes exist in the policy, but S1 assigns two: the other four
        # must not enter the fairness input as zeroes.
        rates = F.flow_rates(S1_CALL_BULK)
        self.assertEqual(sorted(rates), ["bulk", "call"])
        self.assertEqual(rates["call"], 50.0)
        self.assertEqual(rates["bulk"], 39.0)

    def test_missing_report_is_skipped_not_zeroed(self):
        wl = dict(S1_CALL_BULK)
        wl["call"] = {"label": "call"}          # no rate reported at all
        rates = F.flow_rates(wl)
        self.assertEqual(list(rates), ["bulk"])

    def test_tv_flows_are_per_stream_flows(self):
        wl = dict(THREE_FLOWS)
        wl["tv4"] = {"kind": "video", "sender_mbps": 4.0}
        self.assertEqual(len(F.flow_rates(wl)), 4)

    def test_call_rate_is_pps_not_a_mbps_mixup(self):
        wl = {"call": {"label": "call", "pps_achieved": 50.0,
                       "sender_mbps": 9.9}}
        self.assertEqual(F.flow_rates(wl)["call"], 50.0)


class TestCrossModeComparability(unittest.TestCase):
    def test_identical_flows_identical_fairness(self):
        """The whole point: two systems that ran the same flows with the same
        outcome produce the SAME number, even though one wrote a single-class
        kernel sheet and the other seven classes."""
        a = F.run_fairness(S1_CALL_BULK)
        b = F.run_fairness(S1_CALL_BULK_OTHER_MODE)
        self.assertEqual(a, b)

    def test_artefact_attribution_cannot_change_the_number(self):
        # Feed a single-class B0-style per-class sheet next to a 7-class ACIQ
        # sheet: the run fairness must come from the flows, not the sheets.
        s0 = {"t": 0.0, "per_class": {"software_update": {"goodput_mbps": 20.0}}}
        sa = {"t": 0.0, "per_class": {
            "video_call_voice": {"goodput_mbps": 0.12},
            "bulk_download": {"goodput_mbps": 19.9},
            "interactive_gaming": {"goodput_mbps": 0.0},
            "adaptive_video_streaming": {"goodput_mbps": 0.0}}}
        self.assertEqual(F.run_fairness(S1_CALL_BULK),
                         F.run_fairness(S1_CALL_BULK_OTHER_MODE))
        # and the sheets themselves are exposed but never mixed in:
        self.assertEqual(F.per_class_series([s0], "software_update"),
                         [(0.0, 20.0)])
        self.assertEqual(len(F.per_class_series([sa], "bulk_download")), 1)

    def test_single_flow_is_not_fairness(self):
        # one flow = nothing to be fair about; returning 1.0 here was how the
        # old per-tick sheet claimed single-class systems were fair.
        self.assertIsNone(F.run_fairness({"bulk": {"sender_mbps": 5.0}}))


class TestJainDefinition(unittest.TestCase):
    def test_equal_flows_score_one(self):
        self.assertEqual(F.jain([10.0, 10.0, 10.0]), 1.0)

    def test_unequal_flows_score_below_one_and_above_bound(self):
        got = F.jain(THREE_FLOWS and [1.0, 2.0, 3.0])
        self.assertIsNotNone(got)
        self.assertLess(got, 1.0)
        self.assertGreater(got, 1.0 / 3)   # bounded below by 1/n

    def test_empty_is_none_not_zero(self):
        self.assertIsNone(F.jain([]))
        self.assertIsNone(F.run_fairness({}))


class TestStarvation(unittest.TestCase):
    SERIES = [(0.0, 10.0), (1.0, 10.0), (2.0, 0.0), (3.0, 0.0),
              (4.0, 10.0), (5.0, 10.0)]

    def test_minimum_catches_what_the_mean_hides(self):
        # mean 10*4/6 ≈ 6.67 over six ticks still LOOKS healthy; the flow was
        # hard-stopped for two seconds and the minimum says 0.0 -- starvation
        # cannot hide in the mean.
        self.assertEqual(F.mean_over_time(self.SERIES), 10.0 * 4 / 6)
        self.assertEqual(F.minimum_over_time(self.SERIES), 0.0)

    def test_starved_ticks_are_quoted_with_timestamps(self):
        self.assertEqual(F.starved_ticks(self.SERIES), [2.0, 3.0])

    def test_never_measured_is_not_zero(self):
        self.assertIsNone(F.minimum_over_time([]))
        self.assertIsNone(F.mean_over_time([]))
        self.assertEqual(F.starved_ticks([]), [])

    def test_gap_is_not_a_zero(self):
        # a class that is not recorded at t=3 is a GAP, not a starved tick.
        s = [(0.0, 10.0), (1.0, 10.0), (2.0, 10.0), (4.0, 10.0)]
        self.assertEqual(F.minimum_over_time(s), 10.0)
        self.assertEqual(F.starved_ticks(s), [])

    def test_series_only_counts_reported_ticks(self):
        samples = [{"t": 0.0, "per_class": {"bulk_download": {
                        "goodput_mbps": 9.0}}},
                   {"t": 1.0, "per_class": {}},                    # no row
                   {"t": 2.0, "per_class": {"bulk_download": {
                        "goodput_mbps": None}}},                   # no metric
                   {"t": 3.0, "per_class": {"bulk_download": {
                        "goodput_mbps": 1.0}}}]
        self.assertEqual(F.per_class_series(samples, "bulk_download"),
                         [(0.0, 9.0), (3.0, 1.0)])
        self.assertEqual(F.per_class_tick_cover(samples, "bulk_download"), 2)


if __name__ == "__main__":
    unittest.main()


class TestAssignedClasses(unittest.TestCase):
    """T3 wording: per-class series restricted to classes the scenario
    actually assigned, identically for every mode."""

    def test_s1_assigns_exactly_call_and_bulk(self):
        got = F.assigned_classes(S1_CALL_BULK)
        self.assertEqual(got, ["bulk_download", "video_call_voice"])

    def test_absent_classes_are_not_reported_as_starved(self):
        got = F.assigned_classes(S1_CALL_BULK)
        self.assertNotIn("software_update", got)
        self.assertNotIn("adaptive_video_streaming", got)
        # every mode derives the SAME scope from its own artefact
        self.assertEqual(got, F.assigned_classes(S1_CALL_BULK_OTHER_MODE))

    def test_tv_labels_count_as_streaming(self):
        self.assertEqual(F.assigned_classes(THREE_FLOWS),
                         ["adaptive_video_streaming"])

    def test_empty_workloads_assign_nothing(self):
        self.assertEqual(F.assigned_classes({}), [])
        self.assertEqual(F.assigned_classes(None), [])

    def test_update_and_backup_kinds_map_to_their_classes(self):
        self.assertEqual(
            F.assigned_classes({"update": {"kind": "update"},
                                "backup": {"kind": "backup"}}),
            ["cloud_backup", "software_update"])
