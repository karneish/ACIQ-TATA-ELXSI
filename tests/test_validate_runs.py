"""Unit rules for tools/validate_runs.py.

The validator is the tool that classifies every band run before the reports
quote it, so each rule here is checked against a purpose-built run directory
rather than against whatever happens to live in data/runs_dev3 today.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tools.validate_runs as vr  # noqa: E402


def build(dirstem, conf=None, res=None):
    """A run directory with fibbed-but-well-formed result.json by default."""
    d = Path(tempfile.mkdtemp(prefix="vr_"))
    rd = d / dirstem
    rd.mkdir()
    conf = conf if conf is not None else {
        "scenario": "s1_iso_during_call", "system": "aciq", "seed": 1000,
        "mode": "adaptive", "link_mbps": 100.0,
    }
    res = res if res is not None else {
        "scenario": "s1_iso_during_call", "system": "aciq", "seed": 1000,
        "mode": "adaptive", "link_start_mbps": 100.0,
        "commit_hash": "753f2840abcdef01234567890123456789abcdef",
        "duration_s": 30.0, "bottleneck_state": "shape_one",
        "samples": [{"t": float(i), "per_class": {}} for i in range(30)],
        "capacity_change_error": "",
    }
    (rd / "config.json").write_text(json.dumps(conf))
    (rd / "result.json").write_text(json.dumps(res))
    return rd


class TestStages(unittest.TestCase):
    def test_a_well_formed_run_passes(self):
        stage, _ = vr.check_run(build("s1_iso_during_call__aciq__adaptive__seed1000"))
        self.assertEqual(stage, "passing")

    def test_missing_result_is_an_incomplete_artifact(self):
        rd = build("s1_iso_during_call__aciq__adaptive__seed1000")
        os.remove(rd / "result.json")
        stage, _ = vr.check_run(rd)
        self.assertEqual(stage, "artifact-missing")

    def test_an_unparsable_result_is_artifact_invalid(self):
        rd = build("s1_iso_during_call__aciq__adaptive__seed1000")
        (rd / "result.json").write_text("{not json")
        stage, info = vr.check_run(rd)
        self.assertEqual(stage, "artifact-invalid")
        self.assertIn("parse", info["error"])

    def test_a_dir_that_is_not_sceded_is_not_validated(self):
        rd = build("just_a_name")
        stage, _ = vr.check_run(rd)
        self.assertEqual(stage, "artifact-invalid")


class TestIdentityRules(unittest.TestCase):
    def test_result_identity_must_agree_with_the_directory(self):
        rd = build("s1_iso_during_call__aciq__adaptive__seed1000")
        stage, _ = vr.check_run(rd)
        self.assertEqual(stage, "passing")
        # flip the scenario only, in place: the rule reads the dir name from
        # the path, so the write can stay where it is
        res = json.loads((rd / "result.json").read_text())
        res["scenario"] = "s2_wan_drop"
        (rd / "result.json").write_text(json.dumps(res))
        stage, info = vr.check_run(rd)
        self.assertEqual(stage, "invalid")
        self.assertTrue(any("result.scenario" in r for r in info["failures"]))

    def test_config_identity_must_agree_with_result(self):
        d = build("s1_iso_during_call__aciq__adaptive__seed1000")
        conf = json.loads((d / "config.json").read_text())
        conf["seed"] = 1001
        (d / "config.json").write_text(json.dumps(conf))
        stage, info = vr.check_run(d)
        self.assertEqual(stage, "invalid")
        self.assertTrue(any("config.seed" in r for r in info["failures"]))

    def test_link_start_must_match_the_configured_link(self):
        d = build("s1_iso_during_call__aciq__adaptive__seed1000")
        conf = json.loads((d / "config.json").read_text())
        conf["link_mbps"] = 40.0
        (d / "config.json").write_text(json.dumps(conf))
        stage, info = vr.check_run(d)
        self.assertEqual(stage, "invalid")
        self.assertTrue(any("link_start_mbps" in r for r in info["failures"]))


class TestProvenanceRules(unittest.TestCase):
    def test_missing_commit_hash_is_invalid(self):
        rd = build("s1_iso_during_call__aciq__adaptive__seed1000")
        res = json.loads((rd / "result.json").read_text())
        res.pop("commit_hash")
        (rd / "result.json").write_text(json.dumps(res))
        stage, info = vr.check_run(rd)
        self.assertEqual(stage, "invalid")
        self.assertTrue(any("commit_hash" in r for r in info["failures"]))

    def test_config_and_result_commits_must_agree(self):
        d = build("s1_iso_during_call__aciq__adaptive__seed1000")
        conf = json.loads((d / "config.json").read_text())
        conf["commit_hash"] = "fa9f27f9d03c8b5f6a1e2b4c9d0e7f8a1b2c3d4e"
        (d / "config.json").write_text(json.dumps(conf))
        stage, info = vr.check_run(d)
        self.assertEqual(stage, "invalid")
        self.assertTrue(any("commit_hash" in r for r in info["failures"]))


class TestNumericsAndCoverage(unittest.TestCase):
    def test_non_finite_goodput_is_invalid(self):
        rd = build("s1_iso_during_call__aciq__adaptive__seed1000")
        res = json.loads((rd / "result.json").read_text())
        res["samples"] = [{"t": 0.0, "per_class": {
            "adaptive_video": {"goodput_mbps": float("inf")}}}]
        (rd / "result.json").write_text(json.dumps(res))
        stage, info = vr.check_run(rd)
        self.assertEqual(stage, "invalid")
        self.assertTrue(any("goodput" in r.split(";")[0][:60]
                            for r in info["failures"]))

    def test_negative_goodput_is_invalid(self):
        rd = build("s1_iso_during_call__aciq__adaptive__seed1000")
        res = json.loads((rd / "result.json").read_text())
        res["samples"] = [{"t": 0.0, "per_class": {
            "adaptive_video": {"goodput_mbps": -1.0}}}]
        (rd / "result.json").write_text(json.dumps(res))
        self.assertEqual(vr.check_run(rd)[0], "invalid")

    def test_a_sample_span_under_half_the_duration_is_invalid(self):
        rd = build("s1_iso_during_call__aciq__adaptive__seed1000")
        res = json.loads((rd / "result.json").read_text())
        res["samples"] = [{"t": float(i)} for i in range(8)]  # 0..7s vs 30
        (rd / "result.json").write_text(json.dumps(res))
        stage, info = vr.check_run(rd)
        self.assertEqual(stage, "invalid")
        self.assertTrue(any("span" in r for r in info["failures"]))

    def test_empty_samples_are_invalid(self):
        rd = build("s1_iso_during_call__aciq__adaptive__seed1000")
        res = json.loads((rd / "result.json").read_text())
        res["samples"] = []
        (rd / "result.json").write_text(json.dumps(res))
        self.assertEqual(vr.check_run(rd)[0], "invalid")


class TestExecutionFailureIndications(unittest.TestCase):
    def test_a_recording_of_capacity_error_is_valid_but_not_passing(self):
        rd = build("s1_iso_during_call__aciq__adaptive__seed1000")
        res = json.loads((rd / "result.json").read_text())
        res["capacity_change_error"] = "tc: RTNETLINK answers: Invalid argument"
        (rd / "result.json").write_text(json.dumps(res))
        stage, info = vr.check_run(rd)
        self.assertEqual(stage, "valid-with-execution-error")

    def test_missing_bottleneck_state_is_invalid(self):
        rd = build("s1_iso_during_call__aciq__adaptive__seed1000")
        res = json.loads((rd / "result.json").read_text())
        res.pop("bottleneck_state")
        (rd / "result.json").write_text(json.dumps(res))
        self.assertEqual(vr.check_run(rd)[0], "invalid")

    def test_an_inject_failure_run_passes_as_a_drill_band(self):
        rd = build("s1_iso_during_call__aciq__adaptive__seed1000")
        conf = json.loads((rd / "config.json").read_text())
        conf["inject_fail_apply"] = True
        (rd / "config.json").write_text(json.dumps(conf))
        self.assertEqual(vr.check_run(rd)[0], "passing-failure-drill")


if __name__ == "__main__":
    unittest.main()
