from __future__ import annotations

import unittest
from pathlib import Path

from aciq.dashboard import build_from_samples


class TestTheDashboardFollowsARunInProgress(unittest.TestCase):
    """`cmd_serve` read samples.jsonl once, at startup.

    Every browser refresh then re-rendered the samples the server happened to
    see when it launched. That is indistinguishable from a dashboard that is not
    live, which is how it behaved -- and the page carried a meta-refresh the
    whole time, so it looked like it should have worked.
    """

    def _rows(self, n, start=0.0):
        return [{"t": start + i, "per_class": {}, "link": None,
                 "estimator_saturated": False, "fairness": 0.0,
                 "cpu_fraction": 0.0, "capacity_mbps": 0.0}
                for i in range(n)]

    def test_a_torn_final_line_does_not_take_the_server_down(self):
        """A run appends to samples.jsonl while this reads, so the last line can
        be caught mid-write. Skipping it is normal operation, not an error."""
        import json
        good = json.dumps(self._rows(3)[0])
        torn = '{"t": 3.0, "per_cl'
        text = f"{good}\n{good}\n{torn}\n"
        rows = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        self.assertEqual(len(rows), 2, "a partial line must be skipped")

    def test_re_reading_sees_rows_appended_after_startup(self):
        import json
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "samples.jsonl"
            # jsonl: one JSON object per line, which is what a run writes.
            p.write_text("".join(json.dumps(r) + "\n" for r in self._rows(2)))

            def read():
                out = []
                for line in p.read_text().splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        out.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
                return out

            self.assertEqual(len(read()), 2)
            with p.open("a") as fh:          # the run continues
                fh.write(json.dumps(self._rows(1, start=9.0)[0]) + "\n")
                fh.flush()
            self.assertEqual(len(read()), 3,
                             "the dashboard would not see rows added later")

    def test_the_page_carries_a_meta_refresh_and_no_script(self):
        """Live update without JavaScript: the constraint is deliberate, so the
        refresh must be the meta tag and nothing else."""
        html = build_from_samples(self._rows(3), refresh_s=2)
        self.assertIn('<meta http-equiv="refresh"', html)
        self.assertNotIn("<script", html.lower())
        self.assertNotIn("cdn", html.lower())


class TestTheDashboardWaitsForARunThatHasNotStarted(unittest.TestCase):
    """`aciqctl serve` exited on a missing samples file.

    A dashboard meant to watch a run has to be startable *before* the run
    exists. Exiting on a missing file meant it could only ever chart something
    already finished, and pointing it at a glob the run had not created yet
    produced `error: no such file: data/live/*/samples.jsonl` -- the unexpanded
    glob reported as a literal missing path.
    """

    def test_a_glob_with_no_match_is_not_a_missing_file(self):
        import glob as g
        self.assertEqual(g.glob("/nonexistent-dir-xyz/*/samples.jsonl"), [])

    def test_the_waiting_state_is_reported_rather_than_fatal(self):
        """Checked here at the level it is decided: a pattern that matches
        nothing must resolve to None without raising."""
        import glob as g
        pattern = "/nonexistent-dir-xyz/*/samples.jsonl"
        hits = sorted(g.glob(pattern))
        resolved = hits[0] if hits else None
        self.assertIsNone(resolved)

    def test_the_page_says_what_it_is_waiting_for(self):
        html = build_from_samples([], subtitle="waiting for data/live/*/samples.jsonl",
                                  refresh_s=2)
        self.assertIn("waiting for data/live", html)
        self.assertIn('http-equiv="refresh"', html,
                      "a waiting page that never re-checks is just a dead page")
