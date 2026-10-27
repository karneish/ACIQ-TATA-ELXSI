"""run_experiments.main exit contract, offline (dry-run + --no-setup).

The 2026-10-24 live rerun aborted the intent step at apply_system -- and the
driver RECORDED the dead run and returned 0, so the pipeline skipped ahead as
if nothing happened. This pins the fixed contract:

  - a healthy run exits 0 and leaves its run dir in place;
  - a run whose apply fails exits 1, removes its own incomplete run dir
    (so no pair of config+result masquerading under a later report as data),
    and the pipeline step then kills the pipeline properly;
  - an ARMED S5(c) injection note is NOT a failure: its word "failed" names
    the feature under test, and the driver once deleted the seed555 run
    dir -- the evidence -- before verify_s5c could read it. The armed run's
    dir stays; judging it belongs to tools/verify_s5c.py.
"""

import run_experiments
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

    def test_armed_s5_injection_note_keeps_the_evidence(self):
        # the injected run used to be DELETED by the driver (the ARMED note
        # contains the word "failed") -- verify_s5c then found no dir and
        # S5(c) reported NO for a run that had actually rolled back. The
        # armed run's dir is evidence; it must survive.
        with tempfile.TemporaryDirectory() as tmp:
            r = Path(tmp)
            p = self._run(r, r / "REPORT.md", "--inject-fail-apply")
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
            self.assertTrue(self.run_dir(r).joinpath("result.json").exists())

    def test_expected_s5_note_predicate(self):
        # only the success-part marker is carved out; "NOT armed" and plain
        # failure notes keep the destructive warning behaviour.
        armed = ("S5(c) injected failed apply ARMED at "
                 "t=19.0s")
        self.assertTrue(run_experiments.expected_s5_note(armed))
        self.assertFalse(run_experiments.expected_s5_note(
            "S5(c) injection NOT armed (re-called?)"))
        self.assertFalse(run_experiments.expected_s5_note(
            "apply failed: refused"))

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
