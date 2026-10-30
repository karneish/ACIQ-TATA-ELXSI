"""verify_round3 gate tests: the rules are frozen, so the tool must judge
them exactly as docs/FIX_REPORT.md declares — including the honest skip
for shapes it makes no controller claim about."""

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

    def test_ramp_down_makes_no_controller_claim(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = write_run(Path(tmp), "s2b_ramp__aciq__seed1104",
                          {"scenario": "s2b_ramp_100to30",
                           "link_mbps": 100.0, "ramp_at_s": 10.0,
                           "ramp_duration_s": 20.0, "ramp_to_mbps": 30.0},
                          {"governor": {"decisions": [{"t": 0.0}]},
                           "policy_change_log": []})
            self.assertEqual(check_run(d), {"no_controller_claim": "skip"})


UP_PASS = "0.967"  # 58.0/60.0, the frozen landed-probe shape


if __name__ == "__main__":
    unittest.main()
