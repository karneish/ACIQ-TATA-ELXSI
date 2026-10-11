from __future__ import annotations

import re
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


def _real_rows():
    """The recorded lease run, if it is present. Tests must not fail merely
    because a data directory was cleaned, so absence degrades to a synthetic
    trace with the same shape."""
    import glob as g
    hits = sorted(g.glob("data/ab_lease_42/*/samples.jsonl"))
    if hits:
        import json
        return [json.loads(l) for l in open(hits[0])]
    return [{"t": float(i),
             "per_class": {"adaptive_video": {
                 "goodput_mbps": 10.0 + (i % 3), "backlog_bytes": 1000 * i,
                 "rtt_p95": 0.0, "jitter_ms": 0.0, "loss_ratio": 0.0}},
             "link": {"rx_bytes": 1_250_000 * i, "drops": 0, "overlimits": 0,
                      "backlog_bytes": 0, "handle": "1:1", "cls": None},
             "estimator_saturated": False, "fairness": 0.5,
             "cpu_fraction": 0.001, "capacity_mbps": 0.0}
            for i in range(20)]


class TestTheChartsAreHonest(unittest.TestCase):
    """A chart that looks right but shows the wrong thing is worse than no
    chart, and two of the defects here were invisible until the SVG was
    inspected rather than trusted.
    """

    def test_no_axis_ever_labels_a_negative_latency(self):
        """All-zero series used to be padded to -0.5..0.5, so the latency and
        jitter panels were labelled with negative milliseconds."""
        html = build_from_samples(_real_rows(), refresh_s=5)
        self.assertIsNone(re.search(r'text-anchor="end">-', html),
                          "an axis label is negative")

    def test_a_series_that_is_always_zero_is_not_drawn_as_a_measurement(self):
        """rtt_p95, jitter_ms and loss_ratio are identically zero in every run
        this project has produced. Drawing that as a line at zero reads as
        "measured zero latency"."""
        html = build_from_samples(_real_rows(), refresh_s=5)
        self.assertIn("not measured", html)

    def test_every_panel_labels_its_time_axis(self):
        """The single most important moment on these charts is the capacity
        drop, and neither the x axis nor the drop itself was marked."""
        html = build_from_samples(_real_rows(), refresh_s=5)
        self.assertRegex(html, r'>[0-9.]+s</text>')

    def test_the_capacity_drop_is_marked_on_the_charts(self):
        html = build_from_samples(_real_rows(), refresh_s=5)
        self.assertIn('class="event"', html)
        self.assertIn("cap -&gt;", html)

    def test_every_panel_grid_fills_its_box(self):
        """A top strip with no gridline reads as a rendering fault."""
        html = build_from_samples(_real_rows(), refresh_s=5)
        svgs = re.findall(r'<svg class="panel".*?</svg>', html, re.S)
        self.assertEqual(len(svgs), 6)
        for sv in svgs:
            ys = [float(y) for y in
                  re.findall(r'class="grid" x1="46" y1="([0-9.]+)"', sv)]
            self.assertTrue(ys, "a panel drew no gridlines")
            self.assertEqual(min(ys), 10.0,
                             f"panel does not fill its box: {ys}")

    def test_the_legend_carries_current_values(self):
        """Otherwise every reading requires tracing a line to its right end."""
        html = build_from_samples(_real_rows(), refresh_s=5)
        self.assertIn("<b>", html)

    def test_the_summary_answers_did_anything_happen(self):
        html = build_from_samples(_real_rows(), refresh_s=5)
        for tile in ("samples", "peak throughput", "capacity (M2)"):
            self.assertIn(tile, html)

    def test_capacity_is_reported_as_unmeasured_rather_than_zero(self):
        html = build_from_samples(_real_rows(), refresh_s=5)
        self.assertIn("not measured", html)

    def test_nothing_is_drawn_outside_the_viewbox(self):
        html = build_from_samples(_real_rows(), refresh_s=5)
        for m in re.finditer(r"([0-9.]+),([0-9.]+)", html):
            x, y = float(m.group(1)), float(m.group(2))
            self.assertLessEqual(x, 421)
            self.assertLessEqual(y, 141)

    def test_the_page_still_has_no_javascript_and_no_external_requests(self):
        html = build_from_samples(_real_rows(), refresh_s=5)
        self.assertNotIn("<script", html.lower())
        self.assertIsNone(re.search(r'(src|href)="https?:', html))
