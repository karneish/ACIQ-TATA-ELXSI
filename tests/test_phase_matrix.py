"""Tests for the phase 5/6 matrix tool: multi-scenario grouping, pairing by
seed across systems, and the report writer.

The grouping contract: a recovery-edge number NEVER ends up in a drop-edge
comparison; every output row carries its scenario. Pairing contract quirks
from aciq.compare are reused and not re-tested here.

All fixture files live in a temp directory; nothing real runs.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.phase_matrix import (load_workload_metrics, paired_table,
                                render_report)


def write_run(root: Path, scenario: str, system: str, seed: int,
              call: dict | None, bulk: dict | None) -> str:
    stem = f"{scenario}__{system}__{'static' if system != 'aciq' else 'adaptive'}__seed{seed}"
    d = root / stem
    d.mkdir(parents=True)
    wl = {}
    if call is not None:
        wl["call"] = call
    if bulk is not None:
        wl["bulk"] = bulk
    (d / "workloads.json").write_text(json.dumps(wl))
    return stem


class TestGrouping(unittest.TestCase):
    def _matrix(self, root: Path):
        rows = []
        for scen in ("s2_wan_drop", "s4_capacity_recovery"):
            for seed in (0, 1):
                for sys_name in ("b0_fifo", "aciq"):
                    # the engine's call probe performs differently BY DESIGN of
                    # the fixture: identical numbers would be zero diffs and
                    # legitimately rank nothing (the pipeline is honest about
                    # that; we want RANKS here).
                    call = ({"p95": 40.0 + seed * 10,
                             "loss_ratio": 0.01 + seed * 0.01,
                             "jitter_ms": 2.0 + seed} if sys_name == "b0_fifo"
                            else {"p95": 20.0 + seed * 5,
                                  "loss_ratio": 0.001 + seed * 0.001,
                                  "jitter_ms": 0.4 + seed * 0.1})
                    stem = write_run(root, scen, sys_name, seed, call,
                                     {"sender_mbps": 40.0 + seed})
                    rows.append({"seed": seed, "system": sys_name,
                                 "scenario": scen, "path": stem})
        return rows

    def test_rows_carry_their_scenario(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = self._matrix(root)
            out = paired_table(rows, baseline="b0_fifo", runs_dir=root)
            scen_opts = {r["scenario"] for r in out}
            self.assertEqual(scen_opts, {"s2_wan_drop", "s4_capacity_recovery"})
            self.assertTrue(all("scenario" in r for r in out))

    def test_drop_and_recovery_numbers_stay_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = self._matrix(root)
            out = paired_table(rows, baseline="b0_fifo", runs_dir=root)
            p95 = {r["scenario"]: r for r in out
                   if r["metric"] == "probe_p95_ms" and r["engine"] == "aciq"}
            self.assertEqual(len(p95), 2)   # two scenarios, each paired
            for r in p95.values():
                self.assertEqual(r["wilcoxon_n"], 2)
                self.assertEqual(r["pairs"], 2)

    def test_missing_workload_marked_not_hidden(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            stem_ok = write_run(root, "s2_wan_drop", "b0_fifo", 0,
                                {"p95": 40.0}, None)
            stem_bad = write_run(root, "s2_wan_drop", "aciq", 0, None, None)
            out = paired_table([
                {"seed": 0, "system": "b0_fifo", "scenario": "s2_wan_drop",
                 "path": stem_ok},
                {"seed": 0, "system": "aciq", "scenario": "s2_wan_drop",
                 "path": stem_bad},
            ], baseline="b0_fifo", runs_dir=root)
            self.assertTrue(all(r.get("error") or r["missing"] or r["pairs"] == 0
                                for r in out))

    def test_report_writes_only_honest_cells(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rows = self._matrix(root)
            out = paired_table(rows, baseline="b0_fifo", runs_dir=root)
            md = render_report(out)
            self.assertIn("| aciq", md)
            self.assertNotIn("NaN", md)
            self.md = md

    def test_empty_report_is_explicit(self):
        md = render_report([])
        self.assertIn("no paired rows", md)


class TestLoadMetrics(unittest.TestCase):
    def test_definitions_recorded_as_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            (d / "workloads.json").write_text(json.dumps({
                "call": {"p95": 41.0, "p99": 90.0, "loss_ratio": 0.02,
                         "jitter_ms": 0.7},
                "bulk": {"sender_mbps": 39.5}}))
            m = load_workload_metrics(d)
            self.assertEqual(m["call"]["probe_p95_ms"], 41.0)
            self.assertAlmostEqual(m["call"]["probe_loss_pct"], 2.0)
            self.assertEqual(m["bulk"]["sender_mbps"], 39.5)

    def test_missing_file_returns_empty(self):
        m = load_workload_metrics(Path("/nonexistent/path"))
        self.assertEqual(m, {})


if __name__ == "__main__":
    unittest.main()
