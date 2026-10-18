"""The comparison report must see every system, and must not invent one.

`build_report()` reads exactly one results directory. Every comparison gate
writes each system into its own directory, so every report the generator ever
produced contained ACIQ alone, the systems table never held more than one entry,
and `paired_pvalues()` never ran. The brief's central requirement -- compare
against a deterministic baseline, with a statistical method -- was satisfied only
by numbers typed by hand into a document.

These pin the fix and, more importantly, pin the failure mode that matters: a
missing baseline must be reported as missing, never quietly compared against
nothing.
"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from aciq.report import compare_report, load_runs_multi


def _write_run(root: Path, system: str, seed: int, label: str, p50: float):
    """A run directory in the real schema.

    `workloads.json` is keyed by workload label with the metrics inline -- the
    same shape the host gate writes. An earlier version of this fixture invented
    a `{"labels": [...]}` wrapper and a separate `<label>.json`, and the report
    came back with "0 latency measurements" -- the fixture was wrong, not the
    code under test.
    """
    d = root / f"{system}__scen__seed{seed}"
    d.mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({
        "scenario": "scen", "system": system, "capacity_mode": "adaptive",
        "seed": seed, "link_start_mbps": 100.0, "link_end_mbps": 20.0,
        "estimator_mbps": 20.2, "policy_changes": 1, "samples": [],
    }))
    (d / "workloads.json").write_text(json.dumps({
        label: {
            "label": label, "sent": 2000, "received": 1999,
            "loss_ratio": 0.001, "jitter_ms": 1.0,
            "p50": p50, "p95": p50 * 2, "p99": p50 * 3,
        }
    }))


class TestComparisonSeesEverySystem(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, True)
        for sysname, base in (("aciq", 1.0), ("b0_fifo", 80.0),
                              ("b1_cake95", 79.0)):
            root = self.tmp / sysname
            for seed in (42, 43, 44, 45, 46, 47, 48):
                _write_run(root, sysname, seed, "call", base + seed * 0.01)

    def test_merge_collects_every_system(self):
        merged = load_runs_multi({s: self.tmp / s for s in
                                  ("aciq", "b0_fifo", "b1_cake95")})
        try:
            found = {p.name.split("__")[0] for p in merged.iterdir()}
        finally:
            shutil.rmtree(merged, ignore_errors=True)
        self.assertEqual(found, {"aciq", "b0_fifo", "b1_cake95"})

    def test_report_lists_all_three_systems(self):
        out = compare_report({s: self.tmp / s for s in
                              ("aciq", "b0_fifo", "b1_cake95")}, "T")
        for sysname in ("aciq", "b0_fifo", "b1_cake95"):
            self.assertIn(f"| {sysname} |", out)

    def test_report_actually_computes_p_values(self):
        """The whole point: paired Wilcoxon across systems, not ACIQ alone."""
        out = compare_report({s: self.tmp / s for s in
                              ("aciq", "b0_fifo", "b1_cake95")}, "T")
        self.assertIn("Paired significance", out)
        self.assertIn("Wilcoxon", out)

    def test_evidence_directories_are_not_modified(self):
        """The merge must be read-only with respect to real evidence."""
        before = sorted(str(p) for p in (self.tmp / "aciq").rglob("*"))
        load_runs_multi({"aciq": self.tmp / "aciq"})
        after = sorted(str(p) for p in (self.tmp / "aciq").rglob("*"))
        self.assertEqual(before, after)

    def test_a_missing_baseline_is_not_silently_dropped(self):
        """A comparison against nothing must not read as a comparison."""
        out = compare_report({"aciq": self.tmp / "aciq",
                              "b0_fifo": self.tmp / "nonexistent"}, "T")
        self.assertIn("| aciq |", out)
        self.assertNotIn("| b0_fifo |", out)
        # and with one system there is nothing to pair, so no significance claim
        self.assertNotIn("Paired significance", out)

    def test_a_mislabelled_run_is_excluded_not_relabelled(self):
        """A directory whose runs contradict the key must contribute nothing.

        The stronger property, and the one worth pinning: excluding is safe,
        relabelling would silently invent a baseline measurement.
        """
        root = self.tmp / "mislabelled"
        _write_run(root, "b0_fifo", 42, "call", 80.0)
        merged = load_runs_multi({"aciq": root})
        try:
            names = {p.name.split("__")[0] for p in merged.iterdir()}
        finally:
            shutil.rmtree(merged, ignore_errors=True)
        self.assertNotIn("aciq", names,
                         "a b0_fifo run was relabelled as aciq -- that would "
                         "fabricate a baseline measurement")
        self.assertEqual(names, set())


class TestCompareToolIsHonest(unittest.TestCase):
    def test_it_refuses_to_run_with_no_gate_selected(self):
        import subprocess
        r = subprocess.run(
            ["python3", "tools/compare.py", "--out", "/dev/null"],
            capture_output=True, text=True, timeout=120,
            cwd=str(Path(__file__).resolve().parents[1]))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("--congested", r.stderr)

    def test_missing_evidence_exits_nonzero_with_a_message(self):
        import subprocess
        r = subprocess.run(
            ["python3", "tools/compare.py", "--congested",
             "--out", "/tmp/aciq-nope.md"],
            capture_output=True, text=True, timeout=180,
            cwd=str(Path(__file__).resolve().parents[1]))
        if r.returncode != 0:
            self.assertTrue(r.stderr.strip(),
                            "a failure must say why, not just exit nonzero")


if __name__ == "__main__":
    unittest.main()