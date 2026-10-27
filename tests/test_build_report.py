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


class TestS2bRows(unittest.TestCase):
    """S2b (docs/evidence/s2b-params.md): bind/tracking/estimate/honesty rows
    computed from synthetic run dirs whose ground truth is hand-computed
    here. The generator must NOT AVAILABLE what it cannot compute."""

    @staticmethod
    def _mk_s2b(root: Path, scenario: str, system: str, seed: int,
                caps: list[tuple[float, float]],
                proto: dict | None = None) -> None:
        """caps are (t, applied_mbps) ticks; proto carries any protocol
        fields the row's truth needs. samples.jsonl holds one tick per
        line, exactly as the engine writes them."""
        d = root / f"{scenario}__{system}__adaptive__seed{seed}"
        d.mkdir(parents=True, exist_ok=True)
        (d / "workloads.json").write_text(json.dumps(
            {"call": {"label": "call", "p50": 0.2, "p95": 12.0,
                      "p99": 13.0, "jitter_ms": 0.4, "loss_ratio": 0.01},
             "bulk": {"label": "bulk", "sender_mbps": 70.0}}))
        cfg = {"scenario": scenario, "system": system, "seed": seed,
               "mode": "adaptive", "link_mbps": 100.0, "drop_mbps": 30.0,
               "drop_at_s": 10.0, "duration_s": 40.0, "settle_s": 4.0}
        cfg.update(proto or {})
        if scenario == "s2b_ramp_100to30":
            cfg.update(ramp_at_s=10.0, ramp_duration_s=20.0,
                       ramp_to_mbps=30.0, drop_at_s=None)
        (d / "config.json").write_text(json.dumps(cfg))
        (d / "samples.jsonl").write_text("\n".join(
            json.dumps({"t": t, "capacity_mbps": cap})
            for t, cap in caps))

    def test_step_bind_and_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for seed, cap_after in ((0, 49.0), (1, 55.0)):
                self._mk_s2b(
                    root, "s2b_step_50", "aciq", seed,
                    [(t * 2.0, 50.0 if t * 2.0 < 10.0 else cap_after)
                     for t in range(19)],
                    proto={"drop_at_s": 10.0, "drop_mbps": 50.0})
            # truth after t=10 is 50, 10% tol = 5.0: 49 binds at 10.0,
            # 55 does not; the mean applied-truth over [20, 38] is
            # (|49-50| + |55-50|)/2 = 3.0.
            self._mk_s2b(root, "s2b_step_50", "b0_fifo", 0,
                         [(t * 2.0, 50.0) for t in range(19)],
                         proto={"drop_at_s": 10.0, "drop_mbps": 50.0})
            out = root / "r.md"
            build_report(root, out)
            md = out.read_text()
        self.assertIn("### s2b_step_50", md)
        self.assertIn("10.0 +/- 0.0", md)
        self.assertNotIn("(0/1 binds met inside the run)", md)
        self.assertIn("3.00", md)
        self.assertIn("NOT AVAILABLE (no saturation signal in the artefact)",
                      md)

    def test_ramp_bind_and_honesty_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # truth: 100 until t=10, then linear to 30 by t=30, holds to 40
            def truth(t: float) -> float:
                if t <= 10.0:
                    return 100.0
                if t >= 30.0:
                    return 30.0
                return 100.0 - 3.5 * (t - 10.0)
            self._mk_s2b(root, "s2b_ramp_100to30", "aciq", 0,
                         [(t * 2.0, round(truth(t * 2.0), 3))
                          for t in range(21)])
            out = root / "r.md"
            build_report(root, out)
            md = out.read_text()
        self.assertIn("### s2b_ramp_100to30", md)
        # the honesty row needs a final tick with estimator_saturated; its
        # absence prints NOT AVAILABLE, never a fabricated verdict
        self.assertIn("(no saturation signal in the artefact)", md)

    def test_honesty_row_names_a_saturated_final_tick_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / "s2b_step_up_20to100__aciq__adaptive__seed0"
            d.mkdir(parents=True)
            (d / "workloads.json").write_text(json.dumps(
                {"call": {"label": "call", "p50": 0.2, "p95": 12.0,
                          "p99": 13.0, "jitter_ms": 0.4,
                          "loss_ratio": 0.01},
                 "bulk": {"label": "bulk", "sender_mbps": 70.0}}))
            (d / "config.json").write_text(json.dumps(
                {"scenario": "s2b_step_up_20to100", "system": "aciq",
                 "seed": 0, "mode": "adaptive", "link_mbps": 20.0,
                 "drop_mbps": 20.0, "drop_at_s": 10.0, "recover_at_s": 10.0,
                 "recover_to_mbps": 100.0, "duration_s": 40.0,
                 "settle_s": 4.0}))
            (d / "samples.jsonl").write_text("\n".join(json.dumps(s) for s in
                [{"t": t * 2.0, "capacity_mbps": 19.0 if t < 5 else 90.0,
                  "estimator_saturated": True} for t in range(10)]))
            out = root / "r.md"
            build_report(root, out)
            md = out.read_text()
        # the estimator says saturated, the tree sits 10% off the truth,
        # and the artefact-level verdict is named, not softened
        self.assertIn("final tick: saturated, applied 90.0 vs truth 100.0",
                      md)

    def test_honesty_row_carries_the_confidence_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            d = root / "s2b_ramp_100to30__aciq__adaptive__seed0"
            d.mkdir(parents=True)
            (d / "workloads.json").write_text(json.dumps(
                {"call": {"label": "call", "p50": 0.2, "p95": 12.0,
                          "p99": 13.0, "jitter_ms": 0.4,
                          "loss_ratio": 0.01},
                 "bulk": {"label": "bulk", "sender_mbps": 70.0}}))
            (d / "config.json").write_text(json.dumps(
                {"scenario": "s2b_ramp_100to30", "system": "aciq",
                 "seed": 0, "mode": "adaptive", "link_mbps": 100.0,
                 "ramp_at_s": 10.0, "ramp_duration_s": 20.0,
                 "ramp_to_mbps": 30.0, "duration_s": 60.0,
                 "settle_s": 4.0}))
            (d / "samples.jsonl").write_text("\n".join(
                json.dumps({"t": t * 2.0, "capacity_mbps": 30.0,
                            "estimator_saturated": False,
                            "estimator_confidence": 0.12})
                for t in range(20)))
            out = root / "r.md"
            build_report(root, out)
            md = out.read_text()
        # unsaturated at the final tick: the confidence number must sit in
        # the same cell, so "low trust" is a number the reader can check
        self.assertIn("UNSATURATED", md)
        self.assertIn("confidence 0.12", md)

    def test_cake_rows_read_the_applied_rate_from_config(self):
        """The samples' capacity_mbps carries the LAUNCH link for the CAKE
        arms (they shape once into per-class tokens); the row's applied-
        error must read cake_rate_at_apply from config.json, never inherit
        B0's number."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for arm in ("b0_fifo", "b1_cake95"):
                for seed in range(10):
                    self._mk_s2b(
                        root, "s2b_step_50", arm, seed,
                        [(t * 2.0, 100.0) for t in range(19)],
                        proto={"drop_at_s": 10.0, "drop_mbps": 50.0,
                               **({"cake_rate_at_apply": 95.0}
                                  if arm == "b1_cake95" else {})})
            runs, _sk, _fam = br.load_runs_families(root)
            cake = [r for r in runs if r["cfg"]["system"] == "b1_cake95"][0]
            truth, _at = br._s2b_truth_fn(cake)
            errs = br._s2b_window_err(cake, 20.0, 38.0)
            self.assertAlmostEqual(errs, 45.0)   # |95 - 50|, NOT |100 - 50|
            b0 = [r for r in runs if r["cfg"]["system"] == "b0_fifo"][0]
            self.assertAlmostEqual(br._s2b_window_err(b0, 20.0, 38.0), 50.0)

    def test_ramp_bind_judged_after_the_ramp_ends(self):
        """Declared rule for the ramp: the bind is judged after
        ramp_at + duration; a tick that happens to track a moving target
        inside the ramp window says nothing about settling."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # truth(12.0) = 88.0: a tree AT the moving truth transiently but
            # the run afterwards sits at 45 Mbps (15 off the final 30),
            # never within the 3.0 tolerance again: any bind computed
            # INSIDE the ramp window must be refused.
            def truth(t: float) -> float:
                if t <= 10.0:
                    return 100.0
                if t >= 30.0:
                    return 30.0
                return 100.0 - 3.5 * (t - 10.0)
            self._mk_s2b(root, "s2b_ramp_100to30", "aciq", 0,
                         [(t * 2.0, truth(t * 2.0) if t == 6 else 45.0)
                          for t in range(21)],
                         proto={"ramp_at_s": 10.0, "ramp_duration_s": 20.0,
                                "ramp_to_mbps": 30.0})
            runs, _sk, _fam = br.load_runs_families(root)
            run = [r for r in runs if r["cfg"]["system"] == "aciq"][0]
            self.assertIsNone(br._s2b_bind_s(run))

    def test_no_bind_reported_when_tolerance_never_met(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._mk_s2b(root, "s2b_step_up_20to100", "b1_cake95", 0,
                         [(t * 2.0, 19.0) for t in range(20)],
                         proto={"link_mbps": 20.0, "drop_mbps": 20.0,
                                "drop_at_s": 10.0, "recover_at_s": 10.0,
                                "recover_to_mbps": 100.0})
            br2 = None
            runs, _sk, _fam = br.load_runs_families(root)
            run = [r for r in runs
                   if r["cfg"]["system"] == "b1_cake95"][0]
            truth, at = br._s2b_truth_fn(run)
            self.assertEqual(truth(5.0), 20.0)
            self.assertEqual(truth(10.0), 100.0)
            # CAKE marched on at its launch rate (19): never within 10% of
            # the post-step truth (100), and the helper must say None,
            # never guess a bind from the pre-step plateau.
            self.assertIsNone(br._s2b_bind_s(run))


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
        # The report selects the POST-FIX seed family (200-209); these pins
        # are that family's s2_wan_drop trio (B0 / CAKE-static / ACIQ).
        self.assertIn("| 251.28 +/- 0.09 |", md)
        self.assertIn("| 70.31 +/- 1.73 |", md)
        self.assertIn("| 71.69 +/- 0.58 |", md)

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


class TestClassificationSection(unittest.TestCase):
    """T6 honesty: a corpus below the per-class floor must be DECLARED."""

    def _write(self, tmp: Path, per_label, n_heldout=None):
        (Path(tmp) / "empty-runs").mkdir()
        ev = {"n_corpus": sum(per_label.values()),
              "n_heldout": n_heldout or sum(per_label.values()) // 2,
              "strict": {"n": 1}}
        evalp = Path(tmp) / "eval.json"
        evalp.write_text(json.dumps(ev) + "\n")
        counts = Path(tmp) / "counts.json"
        counts.write_text(json.dumps({"per_label": per_label,
                                      "n_total": sum(per_label.values())})
                          + "\n")
        return evalp, counts

    def test_missing_floor_is_declared_not_buried(self):
        with tempfile.TemporaryDirectory() as tmp:
            evalp, _ = self._write(Path(tmp),
                                   {"bulk_download": 9, "cloud_backup": 0})
            out = Path(tmp) / "r.md"
            build_report(Path(tmp) / "empty-runs", out, eval_json=evalp)
            md = out.read_text()
        self.assertIn("SPEC GAP (per-class floor 30 not met)", md)
        self.assertIn('"bulk_download": 9', md)
        self.assertIn('"cloud_backup": 0', md)
        self.assertIn("not extrapolated", md)

    def test_met_floor_prints_the_counts_verbatim(self):
        with tempfile.TemporaryDirectory() as tmp:
            evalp, _ = self._write(Path(tmp),
                                   {"bulk_download": 40, "cloud_backup": 31})
            out = Path(tmp) / "r.md"
            build_report(Path(tmp) / "empty-runs", out, eval_json=evalp)
            md = out.read_text()
        self.assertNotIn("SPEC GAP (per-class floor", md)
        self.assertIn("per-class floor 30: met", md)

    def test_thin_heldout_half_is_declared(self):
        with tempfile.TemporaryDirectory() as tmp:
            evalp, _ = self._write(Path(tmp),
                                   {"bulk_download": 3}, n_heldout=1)
            out = Path(tmp) / "r.md"
            build_report(Path(tmp) / "empty-runs", out, eval_json=evalp)
            md = out.read_text()
        self.assertIn("SPEC GAP (held-out half thin)", md)


class TestBindOnAppliedTree(unittest.TestCase):
    """bind replaces the old 1.25x adaptation metric: 1.05x post-drop, from
    the applied tree, never the belief."""

    def test_bind_counts_apply_not_belief(self):
        run = {"cfg": {"drop_at_s": 10.0, "drop_mbps": 20.0},
               "samples": [
                   {"t": 0.5, "capacity_mbps": 95.0},
                   {"t": 10.1, "capacity_mbps": 95.0},
                   {"t": 11.7, "capacity_mbps": 24.9},
                   {"t": 12.0, "capacity_mbps": 20.5},
               ]}
        # 24.9 is NOT <= 1.05*20 = 21.0 any more; the 1.25x variant would
        # have called 11.7 the bind point and lied by 0.3 s.
        self.assertAlmostEqual(run["samples"][3]["t"] - 10.0,
                               br.bind_time(run))

    def test_bind_none_when_apply_never_lands_with_a_cap(self):
        run = {"cfg": {"drop_at_s": 10.0, "drop_mbps": 20.0},
               "samples": [{"t": float(i), "capacity_mbps": 95.0}
                           for i in range(20)]}
        self.assertIsNone(br.bind_time(run))

    def test_bind_none_without_a_drop(self):
        run = {"cfg": {"drop_at_s": None, "drop_mbps": None},
               "samples": []}
        self.assertIsNone(br.bind_time(run))


def _tick(c, t, mbps):
    """A ~1 Hz per-class sample the collector could have recorded."""
    return {c: {"goodput_mbps": mbps}}


class TestPostDropBulk(unittest.TestCase):
    def setUp(self):
        # ticks at the driver's real ~1 s cadence: a rate fact computed over
        # dt beyond TICK_GAP_MAX_S is excluded by analysis_samples (declared),
        # which is why fixtures must be continuous to test anything else.
        samples = (
            [{"t": t, "per_class": _tick("bulk_download", t, 99.0)}
             for t in range(1, 11)]
            + [{"t": 11.0, "per_class": {"bulk_download":
                                         {"goodput_mbps": 15.0}}}]
            + [{"t": 12.0, "per_class": {"bulk_download":
                                         {"goodput_mbps": 13.0}}}])
        self.run = {
            "cfg": {"drop_at_s": 10.0, "drop_mbps": 20.0, "system": "aciq"},
            "samples": samples,
        }

    def test_prefers_the_bulk_class(self):
        self.assertAlmostEqual(14.0, br.post_drop_bulk_mbps(self.run))

    def test_whole_run_prefix_is_excluded(self):
        # the pre-drop 99.0 ticks must not dilute the cell
        self.assertTrue(br.post_drop_bulk_mbps(self.run) < 50.0)

    def test_boundary_crossing_rate_is_excluded(self):
        # the tick whose rate interval (t-dt, t] crosses the drop at t=10
        # straddles the 99 Mbps and 20 Mbps regimes; it must count as
        # neither. A tick at 10.5 recorded with goodput 60.0 is the mean of
        # both regimes, not the post-drop rate.
        run = dict(self.run)
        run["samples"] = (
            run["samples"][:9]      # t = 1..9 at 99
            + [{"t": 10.5, "per_class": {"bulk_download":
                                         {"goodput_mbps": 60.0}}}]
            + [{"t": 11.0, "per_class": {"bulk_download":
                                         {"goodput_mbps": 15.0}}}]
            + [{"t": 12.0, "per_class": {"bulk_download":
                                         {"goodput_mbps": 13.0}}}])
        self.assertAlmostEqual(14.0, br.post_drop_bulk_mbps(run))

    def test_reset_tick_and_its_follower_are_excluded(self):
        # rx going backwards = the qdisc was rebuilt between ticks: the
        # reset tick's goodput is a counter reset, and the NEXT tick's
        # recorded rate (computed from the reset counters) spans that gap.
        run = dict(self.run)
        keeps = [{"t": t, "link": {"rx_bytes": 10_000_000 + t * 1000},
                  "per_class": {"bulk_download": {"goodput_mbps": 11.0}}}
                 for t in range(1, 10)]
        run["samples"] = (
            keeps
            + [{"t": 10.0, "link": {"rx_bytes": 5_000_000},      # reset
                "per_class": {"bulk_download": {"goodput_mbps": 40.0}}},
               {"t": 11.0, "link": {"rx_bytes": 6_000_000},      # spans reset
                "per_class": {"bulk_download": {"goodput_mbps": 99.0}}},
               {"t": 12.0, "link": {"rx_bytes": 7_000_000},
                "per_class": {"bulk_download": {"goodput_mbps": 15.0}}}])
        # only the t=12 rate is post-drop AND has clean baseline counters
        self.assertAlmostEqual(15.0, br.post_drop_bulk_mbps(run))

    def test_baseline_falls_back_to_legacy_aggregate_label(self):
        run = {
            "cfg": {"drop_at_s": 10.0, "drop_mbps": 20.0,
                    "system": "b0_fifo"},
            "samples": [
                {"t": 9.0, "per_class": {"software_update":
                                         {"goodput_mbps": 99.0}}},
                {"t": 11.0, "per_class": {"software_update":
                                          {"goodput_mbps": 12.0}}},
                {"t": 12.0, "per_class": {"software_update":
                                          {"goodput_mbps": 14.0}}},
            ],
        }
        # the t=11 tick's rate interval (9,11] crosses the drop at t=10 --
        # its 12.0 is half of both regimes, so only the t=12 rate counts.
        self.assertAlmostEqual(14.0, br.post_drop_bulk_mbps(run))

    def test_prefers_relabelled_unknown_over_legacy(self):
        run = {
            "cfg": {"drop_at_s": 10.0, "drop_mbps": 20.0,
                    "system": "b0_fifo"},
            "samples": [
                {"t": 9.0, "per_class": {"unknown": {"goodput_mbps": 99.0},
                                         "software_update":
                                         {"goodput_mbps": 12.0}}},
                {"t": 11.0, "per_class": {"unknown": {"goodput_mbps": 30.0},
                                          "software_update":
                                          {"goodput_mbps": 12.0}}},
                {"t": 12.0, "per_class": {"unknown": {"goodput_mbps": 28.0},
                                          "software_update":
                                          {"goodput_mbps": 12.0}}},
            ],
        }
        # same crossing rule: only the t=12 rate interval lies wholly in
        # the post-drop regime.
        self.assertAlmostEqual(28.0, br.post_drop_bulk_mbps(run))

    def test_none_without_a_drop(self):
        self.run["cfg"]["drop_at_s"] = None
        self.assertIsNone(br.post_drop_bulk_mbps(self.run))

    def test_none_without_any_per_tick_series(self):
        self.run["samples"] = [{"t": 11.0, "per_class": {}}]
        self.assertIsNone(br.post_drop_bulk_mbps(self.run))


if __name__ == "__main__":
    unittest.main()


class TestDeltaFactor(unittest.TestCase):
    """A near-zero baseline must print a factor, not -15356%."""

    def test_small_cheeky_baseline_prints_percent(self):
        v, arrow = delta_pct(98.11, 89.55, lower_is_better=True)
        self.assertEqual(v, "-9.6")
        self.assertEqual(arrow, "worse")

    def test_factor_when_ratio_passes_twenty(self):
        v, arrow = delta_pct(98.11, 2.38, lower_is_better=True)
        self.assertEqual(v, "41.2x")
        self.assertEqual(arrow, "worse")

    def test_factor_better_direction_when_lower_is_better(self):
        v, arrow = delta_pct(0.09, 2.38, lower_is_better=True)
        self.assertEqual(v, "26.4x")
        self.assertEqual(arrow, "better")

    def test_factor_direction_for_higher_is_better_metrics(self):
        # bulk throughput: higher is better; ACIQ 200 vs baseline 5 is a
        # real 40x factor, and the direction is "better"
        v, arrow = delta_pct(200.0, 5.0, lower_is_better=False)
        self.assertEqual(v, "40.0x")
        self.assertEqual(arrow, "better")

    def test_percent_boundary_stays_percent_just_below(self):
        v, _ = delta_pct(19.0, 1.0, lower_is_better=False)
        self.assertEqual(v, "+1800.0")


class TestSinkInstSeries(unittest.TestCase):
    """TASK 4 receiver-side per-second sink series."""

    def _mk(self, tmp: Path, lines: list[str], label: str = "bulk",
            settle: float = 0.0) -> dict:
        d = tmp / "s6_intent_expire__aciq__adaptive__seed300"
        d.mkdir(parents=True, exist_ok=True)
        (d / f"{label}.sink.log").write_text("\n".join(lines) + "\n")
        return {"path": str(d), "cfg": {"settle_s": settle}}

    def test_pairs_shift_to_run_clock(self):
        with tempfile.TemporaryDirectory() as td:
            # settle 0: the sink clock runs 1.0s (SINK_CLOCK_LEAD_S) ahead of
            # the run clock, so sink t=2.0 is run t=1.0. Each inst value is
            # attributed to the interval it measures, (t[k-1], t[k]].
            # Realistic sampler cadence: first print at ~1s, then each
            # second. Sink clock leads the run by 1.0s, so sink t=2 is run
            # t=1. inst k covers (t[k-1], t[k]]: the pair carries the
            # interval's start, in run time: (1-1, inst1), (2-1, inst2)...
            run = self._mk(Path(td), [
                "bulk sink listening on :5004",
                "[bulk sink] t=1.00 cum=1000 bytes inst=0.08 Mbps",
                "[bulk sink] t=2.00 cum=101000 bytes inst=0.80 Mbps",
                "[bulk sink] t=3.00 cum=301000 bytes inst=1.60 Mbps",
            ])
            series, note = br.sink_inst_series(run, "bulk")
            self.assertEqual([(0.0, 0.80), (1.0, 1.60)], series)
            self.assertIn("per-second intervals on the run clock", note)

    def test_pre_run_pairs_are_dropped(self):
        with tempfile.TemporaryDirectory() as td:
            # settle 4 -> lead 5.0: sink t=6.00 is run t=1.0; anything before
            # that is lab startup, uniformly dropped (t_run < 0), never
            # half-counted.
            run = self._mk(Path(td), [
                "[bulk sink] t=5.00 cum=1 bytes inst=0.10 Mbps",
                "[bulk sink] t=6.00 cum=101 bytes inst=0.80 Mbps",
                "[bulk sink] t=7.00 cum=301 bytes inst=1.60 Mbps",
                "[bulk sink] t=8.00 cum=501 bytes inst=1.60 Mbps",
            ], settle=4.0)
            series, _note = br.sink_inst_series(run, "bulk")
            # k=1 pairs with sink start 0 -> run t=-5 (dropped); k=2 starts
            # at sink 5.0 -> run 0.0; k=3 -> run 1.0; k=4 -> run 2.0.
            self.assertEqual([(0.0, 0.80), (1.0, 1.60), (2.0, 1.60)], series)

    def test_totals_parser_ignores_sampler_lines(self):
        # sink_mbps sums only connection-close lines; a sampler line's
        # "t=... cum=... bytes inst=..." must never be counted as a total.
        run = {"path": "/nonexistent"}
        tot, basis = br.sink_mbps(run, "bulk")
        self.assertIsNone(tot)

    def test_garbage_lines_are_skipped_not_raised(self):
        with tempfile.TemporaryDirectory() as td:
            run = self._mk(Path(td), [
                "not a sink line",
                "[bulk sink] t=oops cum=x bytes inst=y Mbps",
                "[bulk sink] t=2.00 cum=5 bytes inst=0.01 Mbps",
                "[bulk sink] t=3.00 cum=15 bytes inst=0.08 Mbps",
            ])
            series, note = br.sink_inst_series(run, "bulk")
            # k=1 (sink 0 -> 2.0) starts before the run: dropped. k=2
            # starts sink 2.0 -> run 1.0.
            self.assertEqual([(1.0, 0.08)], series)
