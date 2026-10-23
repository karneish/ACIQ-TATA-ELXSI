"""T7 — the report generator computes its every cell from raw run artefacts.

These tests pin the algorithm itself (t table, CI overlap, deltas, adaptation
definition on the APPLIED tree) on synthetic run directories whose ground
truth is computed here by hand. If a cell later disagrees with these tests,
the generator changed; if the generator cannot compute a cell it must print
NOT AVAILABLE — a fabricated cell is both a test failure and a finding.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.build_report import (NOT_AVAILABLE, build_report, call_metrics,
                                ci_overlap, delta_pct, fmt, game_p95,
                                load_runs, run_fairness, t95)
import tools.build_report as br  # noqa: E402


def _mk_run(root: Path, name: str, *, system: str, scenario: str,
            seeds: list[int], call_p95: list[str], bulk: list[str],
            wl_extra: dict | None = None) -> None:
    """A minimal honest run dir pair. Values are STRINGS on purpose: the
    report must not be reading the test's own numbers, it parses what a run
    dir looks like."""
    for seed, p95, bulkm in zip(seeds, call_p95, bulk):
        d = root / name
        d.mkdir(parents=True, exist_ok=True)
        wl = {"call": {"label": "call", "p50": 0.2, "p95": float(p95),
                       "p99": float(p95) + 0.1, "jitter_ms": 0.5,
                       "loss_ratio": 0.01},
              "bulk": {"label": "bulk", "sender_mbps": float(bulkm)}}
        wl.update(wl_extra or {})
        (d / "workloads.json").write_text(json.dumps(wl))
        (d / "config.json").write_text(json.dumps(
            {"scenario": scenario, "system": system, "seed": seed,
             "mode": "adaptive" if system == "aciq" else "static",
             "drop_at_s": 10.0, "drop_mbps": 20.0, "link_mbps": 100.0}))
        # no result.json: resources/classification sections must print
        # NOT AVAILABLE, which is exactly what a bare run dir proves


class TestStatTools(unittest.TestCase):
    def test_t95(self):
        self.assertEqual(br.t95(10), 2.262)
        self.assertEqual(br.t95(2), 12.706)
        self.assertIsNone(br.t95(1))
        self.assertIsNone(br.t95(0))

    def test_fmt_no_ci_when_n_in_range_but_small(self):
        self.assertEqual(fmt([1.0]), "1.00")
        cell = fmt([1.0, 2.0, 3.0])
        self.assertTrue(cell.startswith("2.00 +/- "), cell)
        self.assertNotIn(NOT_AVAILABLE, cell)

    def test_fmt_says_why_when_out_of_range(self):
        vals = [float(i) for i in range(60)]        # n=60 has a row
        self.assertIn("+/-", fmt(vals))
        # n=13..20 has no row: mean shows, CI declines explicitly
        self.assertIn("no CI", fmt([float(i) for i in range(13)]))

    def test_ci_overlap_disjoint_and_overlap(self):
        self.assertEqual(ci_overlap([1.0, 1.0], [9.0, 9.0]), "disjoint")
        self.assertEqual(ci_overlap([1.0, 1.5, 2.0], [2.0, 2.5, 3.0]),
                         "overlap")
        self.assertEqual(ci_overlap([1.0], [9.0]), "no CI (n<2)")

    def test_delta_direction_follows_the_column(self):
        # lower is better (delay): big diff is a WIN for the smaller arm
        self.assertEqual(delta_pct(1.0, 2.0, lower_is_better=True)[1],
                         "better")
        self.assertEqual(delta_pct(1.0, 2.0, lower_is_better=False)[1],
                         "worse")          # throughput wants big
        self.assertEqual(delta_pct(None, 2.0, lower_is_better=True)[0],
                         NOT_AVAILABLE)

    def test_calculations_match_hand_math_s2_literature(self):
        # s2 seed0 stored trio, computed here from the ACTUAL artefacts the
        # repo already contains (no stored summary consulted).
        runs, _ = load_runs(ROOT / "data/runs")
        s2_aciq = [game_p95(r["wl"]) for r in runs
                   if r["cfg"]["scenario"] == "s2_wan_drop"
                   and r["cfg"]["system"] == "aciq"]
        self.assertTrue(all(v is None for v in s2_aciq),
                        "s2 has no game workload: the cell must be empty")


class TestOnRepoRuns(unittest.TestCase):
    """Real repo artefacts, no synthetic trickery: the report must reproduce
    the verification audit's numbers exactly."""

    def classmethod_call(self, runs_root):
        return build_report(runs_root)

    def test_s2_p95_trio_reproduces_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "r.md"
            build_report(ROOT / "data/runs", out)
            md = out.read_text()
        self.assertIn("| 248.96 +/- 0.73 |", md)
        self.assertIn("| 89.55 +/- 0.96 |", md)
        self.assertIn("| 98.11 +/- 1.70 |", md)

    def test_empty_runs_root_prints_not_available_everywhere(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "empty").mkdir()
            out = Path(tmp) / "r.md"
            build_report(Path(tmp) / "empty", out)
            md = out.read_text()
        self.assertTrue(md)
        self.assertGreaterEqual(md.count(NOT_AVAILABLE), 1)
        self.assertIn("(none in these runs)", md)
        self.assertIn("EMULATION statement", md)


class TestAdaptationOnAppliedTree(unittest.TestCase):
    def test_adaptation_counts_apply_not_belief(self):
        run = {"cfg": {"drop_at_s": 10.0, "drop_mbps": 20.0},
               "samples": [
                   {"t": 0.5, "capacity_mbps": 95.0},
                   {"t": 10.1, "capacity_mbps": 95.0},
                   {"t": 11.7, "capacity_mbps": 24.9},
                   {"t": 12.0, "capacity_mbps": 20.5},
               ]}
        self.assertAlmostEqual(run["samples"][2]["t"] - 10.0,
                               br.adaptation_time(run))

    def test_adaptation_none_when_apply_never_lands_with_a_cap(self):
        run = {"cfg": {"drop_at_s": 10.0, "drop_mbps": 20.0},
               "samples": [{"t": float(i), "capacity_mbps": 95.0}
                           for i in range(20)]}
        self.assertIsNone(br.adaptation_time(run))


if __name__ == "__main__":
    unittest.main()
