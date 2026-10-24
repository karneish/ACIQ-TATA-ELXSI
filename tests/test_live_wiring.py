"""Wiring of the live-only shell steps, pinned from their source.

These are text contracts, not behaviour: the scripts need root and a kernel
to actually run, but two live failures taught lessons that a text test can
hold onto:

* dashboard_evidence.sh once ran its capture ACIQ run into data/runs and
  overwrote a COMMITTED result directory in place (T1's no-in-place rule).
  The capture must target the dashboard evidence directory instead.
* the corpus step lives its own file (corpus_live.sh) and is wired from
  run_all_live.sh so a single sudo command covers it; the last step must
  always be the cleanup so namespaces cannot leak.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "testbed/dashboard_evidence.sh"
ALL = ROOT / "testbed/run_all_live.sh"


def _src(path: Path) -> str:
    return path.read_text()


class TestDashboardCapture(unittest.TestCase):
    def test_capture_run_targets_the_evidence_dir(self):
        s = _src(DASH)
        self.assertIn('RUNDATA="$DEST/dashboard_run"', s)
        self.assertIn('--results-dir "$RUNDATA"', s)

    def test_capture_report_also_stays_inside_the_evidence_dir(self):
        # the driver's DEFAULT report target is data/REPORT.md; a capture
        # without --report overwrote the matrix-wide report with a 1-run
        # version once (2026-10-24 10:50, AFTER the --results-dir fix) —
        # so the report target is pinned alongside the results target.
        s = _src(DASH)
        self.assertIn('--report "$DEST/dashboard_run/REPORT.md"', s)

    def test_capture_never_selects_from_committed_data_runs(self):
        s = _src(DASH)
        self.assertNotIn("ls -td data/runs/", s)


class TestRunAllLive(unittest.TestCase):
    def test_corpus_step_wired_and_cleanup_is_last_step(self):
        s = _src(ALL)
        self.assertIn("step corpus", s)
        self.assertIn("step cleanup", s)
        self.assertLess(s.index("step corpus"), s.rindex("step cleanup"))

    def test_resume_markers_used_for_every_step(self):
        s = _src(ALL)
        self.assertIn("$STATUS_DIR/$id.done", s)


if __name__ == "__main__":
    unittest.main()
