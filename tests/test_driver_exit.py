"""run_experiments.main exit contract, offline (dry-run + --no-setup).

The 2026-10-24 live rerun aborted the intent step at apply_system -- and the
driver RECORDED the dead run and returned 0, so the pipeline skipped ahead as
if nothing happened. This pins the fixed contract:

  - a healthy run exits 0 and leaves its run dir in place;
  - a run whose apply fails exits 1, removes its own incomplete run dir
    (so no pair of config+result masquerading under a later report as data),
    and the pipeline step then kills the pipeline properly.
"""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class DriverExit(unittest.TestCase):
    def _run(self, results_dir: Path, report: Path, *extra: str):
        cmd = [sys.executable, str(ROOT / "run_experiments.py"),
               "--scenario", "s1_iso_during_call", "--system", "aciq",
               "--seed", "99", "--seeds", "1", "--dry-run", "--no-setup",
               "--results-dir", str(results_dir),
               "--report", str(report), *extra]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT))

    def run_dir(self, results_dir: Path) -> Path:
        return results_dir / "s1_iso_during_call__aciq__adaptive__seed99"

    def test_healthy_run_exits_zero_and_keeps_its_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            p = self._run(r, r / "REPORT.md")
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertTrue(self.run_dir(r).joinpath("result.json").exists())
            report = (r / "REPORT.md").read_text()
            self.assertIn("estimator", report.lower())

    def test_failed_apply_exits_nonzero_and_removes_the_dead_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            p = self._run(r, r / "REPORT.md", "--inject-fail-apply")
            self.assertNotEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("removed incomplete run dir", p.stdout)
            # the poisoned pair (config+result, no samples, estimator=None)
            # does not survive: a directory listing with it would read as data
            self.assertFalse(self.run_dir(r).exists())
            # and the failure is machine-readable: the report written from
            # that dir says zero runs, not one dead run repackaged as data
            self.assertTrue((r / "REPORT.md").exists())
            rep = (r / "REPORT.md").read_text()
            self.assertIn("No runs found", rep)

    def test_report_only_never_leaves_a_clobbered_report(self):
        # --report-only is the unprivileged rebuild path: it must not shell out
        # to sudo (the driver used to get there without setup only where the
        # flag was given first). No kernel, no teardown, exit 0.
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            p = subprocess.run(
                [sys.executable, str(ROOT / "run_experiments.py"),
                 "--report-only", "--results-dir", str(r),
                 "--report", str(r / "REPORT.md")],
                capture_output=True, text=True, cwd=str(ROOT))
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertIn("No runs found", (r / "REPORT.md").read_text())
            # and the report build did NOT sneak a result dir into place
            self.assertEqual(sorted(x.name for x in r.iterdir()),
                             ["REPORT.md"])


if __name__ == "__main__":
    unittest.main()
