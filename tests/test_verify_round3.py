"""verify_round3 gate tests: the rules are frozen, so the tool must judge
them exactly as docs/FIX_REPORT.md declares. Retune #8 closed the last two
skip classes: the ramp-down and stress lanes are judged, and an
unclassified shape fails rather than hiding."""

import json
import tempfile
import unittest
from pathlib import Path

from tools.verify_round3 import check_run


def write_run(root, name, cfg, result, sink_lines=None):
    d = root / name
    d.mkdir(parents=True)
    (d / "config.json").write_text(json.dumps(cfg))
    (d / "result.json").write_text(json.dumps(result))
    if sink_lines is not None:
        (d / "bulk.sink.log").write_text(
            "bulk sink listening on :1\n" + "".join(sink_lines))
    return d


class TestRound3Gate(unittest.TestCase):
    def test_up_run_passes_on_landed_probe(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s7_up__aciq__adaptive__seed1100",
                          {"scenario": "s7_up_20to60", "link_mbps": 20.0,
                           "recover_at_s": 10.0, "recover_to_mbps": 60.0},
                          {"governor": {"decisions": [{"t": 5.0}]},
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 16.0,
                                "delay_emergency": False,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 58.0}}}}]},
                          sink_lines=["[bulk sink] t=12.00 cum=0 bytes "
                                      "inst=45.00 Mbps\n"])
            verdict = check_run(d)
            self.assertEqual(round(verdict["up_util_applied"], 3), 0.967)

    def test_up_run_fails_when_the_tree_never_climbed(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s7_up__aciq__adaptive__seed1101",
                          {"scenario": "s7_up_20to60", "link_mbps": 20.0,
                           "recover_at_s": 10.0, "recover_to_mbps": 60.0},
                          {"governor": {"decisions": [{"t": 5.0}]},
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 16.0,
                                "delay_emergency": False,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 20.0}}}}]},
                          sink_lines=["[bulk sink] t=12.00 cum=0 bytes "
                                      "inst=15.00 Mbps\n"])
            verdict = check_run(d)
            self.assertIn("FAILED", verdict["up_util_applied"])

    def test_down_floor_bound_run_passes_on_one_emergency_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s2b_step_10__aciq__seed1102",
                          {"scenario": "s2b_step_10", "link_mbps": 100.0,
                           "drop_at_s": 10.0, "drop_mbps": 10.0},
                          {"governor": {"decisions": [
                              {"t": 0.0},
                              {"t": 14.0, "changed": True,
                               "delay_emergency": True}]},
                           "samples": [{"t": 39.0, "capacity_mbps": 95.0}],
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 14.0,
                                "delay_emergency": None,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 13.9}}}}]})
            verdict = check_run(d)
            # landed 4.0 s after the drop, inside the floor-bound band
            self.assertEqual(verdict["down_emergency_landing"], 4.0)
            self.assertEqual(verdict["landing_mbps"], 13.9)
            # ...and the descent used the delay clearance: recorded, not asked
            self.assertEqual(verdict["delay_emergency_s"], 4.0)

    def test_down_decision_without_a_commit_is_not_a_landing(self):
        """A clearance that never reaches the kernel is a refused proposal.
        Round 4 judges the OUTCOME: the commit at 55.0 on a 10 Mbps link
        (floor-bound band 36.6) never lands, so the run fails even though a
        delay_emergency decision exists."""
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s2b_step_10__aciq__seed1105",
                          {"scenario": "s2b_step_10", "link_mbps": 100.0,
                           "drop_at_s": 10.0, "drop_mbps": 10.0},
                          {"governor": {"decisions": [
                              {"t": 0.0},
                              {"t": 14.0, "changed": False,
                               "delay_emergency": True}]},
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 17.0,
                                "delay_emergency": None,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 55.0}}}}]})
            verdict = check_run(d)
            self.assertIn("FAILED", verdict["down_emergency_landing"])

    def test_down_run_passes_on_a_legal_landing_without_the_flag(self):
        """Round 4 (dev smoke seed1000 s2b_step_50): the belief-fall bind
        landed 51.03 on a 50 Mbps link 7.0 s after the drop with NO
        delay_emergency flag. The case-study requirement is "recalculates
        shaping rather than building a queue"; the landing IS that, and the
        descent route is recorded evidence, not the pass condition."""
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s2b_step_50__aciq__seed1106",
                          {"scenario": "s2b_step_50", "link_mbps": 100.0,
                           "drop_at_s": 10.0, "drop_mbps": 50.0},
                          {"governor": {"decisions": [
                              {"t": 0.0},
                              {"t": 12.0, "changed": True,
                               "delay_emergency": False}]},
                           "samples": [{"t": 39.0, "capacity_mbps": 100.0}],
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 12.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 58.02}}}},
                               {"committed": True, "ok": True, "t": 17.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 51.03}}}},
                               {"committed": True, "ok": True, "t": 22.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 52.38}}}}]})
            verdict = check_run(d)
            self.assertEqual(verdict["down_emergency_landing"], 7.0)
            self.assertEqual(verdict["landing_mbps"], 51.03)
            self.assertIsNone(verdict["delay_emergency_s"])

    def test_down_run_fails_when_the_landing_is_late(self):
        """The seed1001 dev-smoke walk: 105.6 -> 79.2 -> 59.4 -> 52.2 took
        13.3 s to enter the band (limit 8.0 s). Straight from the artefact."""
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s2b_step_50__aciq__seed1107",
                          {"scenario": "s2b_step_50", "link_mbps": 100.0,
                           "drop_at_s": 10.0, "drop_mbps": 50.0},
                          {"governor": {"decisions": [{"t": 0.0}]},
                           "samples": [{"t": 39.0, "capacity_mbps": 100.0}],
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 12.69,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 79.162}}}},
                               {"committed": True, "ok": True, "t": 17.98,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 59.372}}}},
                               {"committed": True, "ok": True, "t": 23.28,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 52.159}}}}]})
            verdict = check_run(d)
            self.assertIn("FAILED", verdict["down_emergency_landing"])

    def test_down_run_fails_when_the_final_commit_rises_back(self):
        """A legal landing that drifts back above the band is not a bind:
        the tail is part of the contract (the tree must STAY put)."""
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s2b_step_50__aciq__seed1108",
                          {"scenario": "s2b_step_50", "link_mbps": 100.0,
                           "drop_at_s": 10.0, "drop_mbps": 50.0},
                          {"governor": {"decisions": [{"t": 0.0}]},
                           "samples": [{"t": 39.0, "capacity_mbps": 100.0}],
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 17.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 51.03}}}},
                               {"committed": True, "ok": True, "t": 30.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 63.79}}}}]})
            verdict = check_run(d)
            self.assertIn("FAILED", verdict["down_emergency_landing"])

    def test_down_run_fails_without_any_post_drop_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s2b_step_10__aciq__seed1103",
                          {"scenario": "s2b_step_10", "link_mbps": 100.0,
                           "drop_at_s": 10.0, "drop_mbps": 10.0},
                          {"governor": {"decisions": [{"t": 0.0}]},
                           "policy_change_log": []})
            verdict = check_run(d)
            self.assertIn("FAILED", verdict["down_emergency_landing"])

    def test_ramp_down_passes_on_an_in_band_landing(self):
        """Retune #8: the ramp-down lane is judged. Endpoint mirror of DOWN:
        the tree lands <= 33.0 (30 x 1.10) within 8.0 s of the ramp END,
        holds the tail, and delivers >= 0.50 of the 30 Mbps end truth."""
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s2b_ramp__aciq__seed1104",
                          {"scenario": "s2b_ramp_100to30",
                           "link_mbps": 100.0, "ramp_at_s": 10.0,
                           "ramp_duration_s": 20.0, "ramp_to_mbps": 30.0},
                          {"governor": {"decisions": [{"t": 0.0}]},
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 14.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 40.0}}}},
                               {"committed": True, "ok": True, "t": 31.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 31.0}}}},
                               {"committed": True, "ok": True, "t": 36.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 29.0}}}},
                               {"committed": True, "ok": True, "t": 40.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 29.0}}}}]},
                          sink_lines=["[bulk sink] t=20.00 cum=0 bytes "
                                      "inst=20.00 Mbps\n",
                                      "[bulk sink] t=30.00 cum=0 bytes "
                                      "inst=20.00 Mbps\n",
                                      "[bulk sink] t=38.00 cum=0 bytes "
                                      "inst=20.00 Mbps\n"])
            verdict = check_run(d)
            self.assertEqual(verdict["ramp_down_landing"], 1.0)
            self.assertEqual(verdict["landing_mbps"], 31.0)
            self.assertEqual(verdict["util_delivered"], 0.667)
            self.assertIsNone(verdict["overtrack_max"])

    def test_ramp_down_passes_when_the_band_was_entered_one_tick_early(self):
        """Retune #12, seed1003 (dev band 2026-11-01): the collapse
        emergency landed 29.17 at 29.83 -- 0.17 s before the nominal ramp
        end -- and the rate never moved again. The old strict
        `t > ramp_end` discarded it and charged the next same-rate commit
        at 41.40 (11.4 s); a rate inside the end-band at the end IS the
        landing."""
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s2b_ramp__aciq__seed1110",
                          {"scenario": "s2b_ramp_100to30",
                           "link_mbps": 100.0, "ramp_at_s": 10.0,
                           "ramp_duration_s": 20.0, "ramp_to_mbps": 30.0},
                          {"governor": {"decisions": [{"t": 0.0}]},
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 19.16,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 68.304}}}},
                               {"committed": True, "ok": True, "t": 24.49,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 46.745}}}},
                               {"committed": True, "ok": True, "t": 29.83,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 29.173}}}},
                               {"committed": True, "ok": True, "t": 41.40,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 29.173}}}},
                               {"committed": True, "ok": True, "t": 48.78,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 29.173}}}}]},
                          sink_lines=["[bulk sink] t=48.00 cum=0 bytes "
                                      "inst=20.00 Mbps\n"])
            verdict = check_run(d)
            self.assertEqual(verdict["ramp_down_landing"], 0.0)
            self.assertEqual(verdict["landing_mbps"], 29.17)
            self.assertEqual(verdict["util_delivered"], 0.667)

    def test_ramp_down_pre_end_band_does_not_count_if_it_rises_after(self):
        """The one-tick-early grace is not a blanket pass: if the first
        post-end commit rises back above the band, the pre-end rate was
        not the landing."""
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s2b_ramp__aciq__seed1111",
                          {"scenario": "s2b_ramp_100to30",
                           "link_mbps": 100.0, "ramp_at_s": 10.0,
                           "ramp_duration_s": 20.0, "ramp_to_mbps": 30.0},
                          {"governor": {"decisions": [{"t": 0.0}]},
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 29.83,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 29.0}}}},
                               {"committed": True, "ok": True, "t": 31.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 45.0}}}},
                               {"committed": True, "ok": True, "t": 42.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 29.0}}}}]},
                          sink_lines=["[bulk sink] t=40.00 cum=0 bytes "
                                      "inst=20.00 Mbps\n"])
            verdict = check_run(d)
            self.assertIn("FAILED", verdict["ramp_down_landing"])

    def test_ramp_down_fails_when_the_landing_misses_the_budget(self):
        """The seed1003 shape from the band before retune #8: the walk
        committed 39.5/35.5 out of band and only reached 31.62 at ramp
        END + 12.6 s, past the 8.0 s budget."""
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s2b_ramp__aciq__seed1105",
                          {"scenario": "s2b_ramp_100to30",
                           "link_mbps": 100.0, "ramp_at_s": 10.0,
                           "ramp_duration_s": 20.0, "ramp_to_mbps": 30.0},
                          {"governor": {"decisions": [{"t": 0.0}]},
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 32.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 39.48}}}},
                               {"committed": True, "ok": True, "t": 37.3,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 35.54}}}},
                               {"committed": True, "ok": True, "t": 42.6,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 31.62}}}}]},
                          sink_lines=["[bulk sink] t=35.00 cum=0 bytes "
                                      "inst=20.00 Mbps\n"])
            verdict = check_run(d)
            self.assertIn("FAILED", verdict["ramp_down_landing"])

    def test_ramp_down_fails_when_the_tail_rises_back_above_the_band(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s2b_ramp__aciq__seed1106",
                          {"scenario": "s2b_ramp_100to30",
                           "link_mbps": 100.0, "ramp_at_s": 10.0,
                           "ramp_duration_s": 20.0, "ramp_to_mbps": 30.0},
                          {"governor": {"decisions": [{"t": 0.0}]},
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 31.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 31.0}}}},
                               {"committed": True, "ok": True, "t": 44.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 45.0}}}}]},
                          sink_lines=["[bulk sink] t=35.00 cum=0 bytes "
                                      "inst=20.00 Mbps\n"])
            verdict = check_run(d)
            self.assertIn("FAILED", verdict["ramp_down_landing"])

    def test_ramp_down_fails_when_delivered_is_below_the_end_truth(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s2b_ramp__aciq__seed1107",
                          {"scenario": "s2b_ramp_100to30",
                           "link_mbps": 100.0, "ramp_at_s": 10.0,
                           "ramp_duration_s": 20.0, "ramp_to_mbps": 30.0},
                          {"governor": {"decisions": [{"t": 0.0}]},
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 31.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 31.0}}}},
                               {"committed": True, "ok": True, "t": 40.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 29.0}}}}]},
                          sink_lines=["[bulk sink] t=35.00 cum=0 bytes "
                                      "inst=5.00 Mbps\n"])
            verdict = check_run(d)
            self.assertIn("FAILED", verdict["ramp_down_landing"])
            self.assertIn("delivered", verdict["ramp_down_landing"])

    def test_ramp_down_fails_without_any_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s2b_ramp__aciq__seed1108",
                          {"scenario": "s2b_ramp_100to30",
                           "link_mbps": 100.0, "ramp_at_s": 10.0,
                           "ramp_duration_s": 20.0, "ramp_to_mbps": 30.0},
                          {"governor": {"decisions": [{"t": 0.0}]},
                           "policy_change_log": []})
            verdict = check_run(d)
            self.assertIn("FAILED", verdict["ramp_down_landing"])

    def test_stress_passes_when_the_tree_delivers_what_it_commits(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s3_stress__aciq__seed1109",
                          {"scenario": "s3_stress",
                           "link_mbps": 100.0},
                          {"governor": {"decisions": [{"t": 0.0}]},
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 10.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 80.0}}}},
                               {"committed": True, "ok": True, "t": 40.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 80.0}}}}]},
                          sink_lines=["[bulk sink] t=20.00 cum=0 bytes "
                                      "inst=60.00 Mbps\n",
                                      "[bulk sink] t=35.00 cum=0 bytes "
                                      "inst=60.00 Mbps\n"])
            verdict = check_run(d)
            self.assertEqual(verdict["stress_deliver"], 0.75)
            self.assertEqual(verdict["commits"], 2)

    def test_stress_fails_when_the_controller_never_commits(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s3_stress__aciq__seed1110",
                          {"scenario": "s3_stress",
                           "link_mbps": 100.0},
                          {"governor": {"decisions": [{"t": 0.0}]},
                           "policy_change_log": []})
            verdict = check_run(d)
            self.assertIn("FAILED", verdict["stress_deliver"])

    def test_stress_fails_when_the_delivered_stream_collapses(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s3_stress__aciq__seed1111",
                          {"scenario": "s3_stress",
                           "link_mbps": 100.0},
                          {"governor": {"decisions": [{"t": 0.0}]},
                           "policy_change_log": [
                               {"committed": True, "ok": True, "t": 10.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 80.0}}}},
                               {"committed": True, "ok": True, "t": 40.0,
                                "applied_state": {"classes": {
                                    "1:1": {"rate": 80.0}}}}]},
                          sink_lines=["[bulk sink] t=20.00 cum=0 bytes "
                                      "inst=20.00 Mbps\n",
                                      "[bulk sink] t=35.00 cum=0 bytes "
                                      "inst=20.00 Mbps\n"])
            verdict = check_run(d)
            self.assertIn("FAILED", verdict["stress_deliver"])


UP_PASS = "0.967"  # 58.0/60.0, the frozen landed-probe shape


if __name__ == "__main__":
    unittest.main()
