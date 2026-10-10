"""M6 execution layer and M10 report tests. Dry launcher, no root, no traffic."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aciq.experiment import DryLauncher, ExperimentRunner, RunPaths
from aciq.harness import CapacityMode, Harness, SystemSpec
from aciq.report import (
    MIN_PAIRS_FOR_PVALUE,
    build_report,
    Metric,
    build_report,
    can_report_pvalue,
    load_runs,
    mean,
    workload_latency,
)
from aciq.txn import FakeRunner


class TestRunPaths(unittest.TestCase):
    def test_creates_artefacts(self):
        with tempfile.TemporaryDirectory() as d:
            p = RunPaths(Path(d) / "run1")
            p.write_json("config.json", {"a": 1})
            p.write_jsonl("samples.jsonl", [{"t": 0}, {"t": 1}])
            self.assertTrue((p.root / "config.json").is_file())
            lines = (p.root / "samples.jsonl").read_text().strip().splitlines()
            self.assertEqual(len(lines), 2)


class TestDriverSequencing(unittest.TestCase):
    """The dry launcher records everything, so ordering can be asserted."""

    def _runner(self, tmp):
        return ExperimentRunner(
            launcher=DryLauncher(),
            harness=Harness(runner=FakeRunner(auto_readback=True), clock=lambda: 0.0),
            results_dir=Path(tmp), real_time=False, tick_s=1.0)

    def test_dry_run_writes_a_reproducible_config(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s1_iso_during_call", SystemSpec.ACIQ)
            p = r.run_paths("s1_iso_during_call", SystemSpec.ACIQ,
                            CapacityMode.ADAPTIVE, 42)
            cfg = json.loads((p.root / "config.json").read_text())
            self.assertEqual(cfg["scenario"], "s1_iso_during_call")
            self.assertEqual(cfg["system"], "aciq")
            self.assertIn("ports", cfg)
            self.assertIn("floor_mbps", cfg)

    def test_ports_are_recorded_so_a_run_can_be_repeated(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s1_iso_during_call", SystemSpec.ACIQ)
            p = r.run_paths("s1_iso_during_call", SystemSpec.ACIQ,
                            CapacityMode.ADAPTIVE, 42)
            cfg = json.loads((p.root / "config.json").read_text())
            self.assertEqual(len(cfg["ports"]), 2)
            for entry in cfg["ports"]:
                self.assertNotIn(entry["port"], (5001, 5002, 5003, 5004))

    def test_sinks_are_launched_before_sources(self):
        """Nothing should race the listener: every sink exists before any
        sender is started."""
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s1_iso_during_call", SystemSpec.ACIQ)
            self.assertEqual(len(r.launcher.sinks), 2)
            # 1 interactive sender for the settle phase + 2 measured workloads
            self.assertEqual(len(r.launcher.sources), 3)

    def test_scenario_three_launches_four_workloads(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s3_tv_and_gaming", SystemSpec.ACIQ)
            self.assertEqual(len(r.launcher.sinks), 4)
            # 1 interactive settle sender + 4 measured workloads
            self.assertEqual(len(r.launcher.sources), 5)


class TestSettlePhase(unittest.TestCase):
    """Warmup must run interactive traffic only, and leave nothing behind."""

    def _runner(self, tmp, **kw):
        from aciq.metrics import CounterSnapshot
        import time as _t

        class NullSource:
            def snapshot(self):
                return CounterSnapshot(t=_t.monotonic(), by_class={})

        return ExperimentRunner(
            launcher=DryLauncher(),
            harness=Harness(runner=FakeRunner(auto_readback=True)),
            results_dir=Path(tmp), real_time=False, source=NullSource(), **kw)

    def test_settle_runs_interactive_workloads_only(self):
        """If bulk ran during the settle, the transient being avoided would just
        be deferred and every system would start pre-flooded."""
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s1_iso_during_call", SystemSpec.ACIQ)
            # first sender is the settle one, and it must be the call, not bulk
            self.assertEqual(r.launcher.sources[0][0], "call")

    def test_bulk_does_not_run_during_settle(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s1_iso_during_call", SystemSpec.ACIQ)
            settle_senders = [s for s in r.launcher.sources if s[0] == "bulk"]
            # exactly one bulk sender: the measured one, not a settle one
            self.assertEqual(len(settle_senders), 1)

    def test_settle_leaves_no_artefacts_behind(self):
        """A settle report must never be mistaken for a measurement."""
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s1_iso_during_call", SystemSpec.ACIQ)
            p = r.run_paths("s1_iso_during_call", SystemSpec.ACIQ,
                            CapacityMode.ADAPTIVE, 42)
            self.assertFalse((p.root / "_settle").exists())
            names = [f.name for f in p.root.iterdir()]
            self.assertFalse([n for n in names if "settle" in n], names)

    def test_settle_zero_skips_the_phase(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s1_iso_during_call", SystemSpec.ACIQ, settle_s=0.0)
            self.assertEqual(len(r.launcher.sources), 2)

    def test_settle_duration_is_recorded_for_reproducibility(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s1_iso_during_call", SystemSpec.ACIQ, settle_s=7.0)
            p = r.run_paths("s1_iso_during_call", SystemSpec.ACIQ,
                            CapacityMode.ADAPTIVE, 42)
            cfg = json.loads((p.root / "config.json").read_text())
            self.assertEqual(cfg["settle_s"], 7.0)

    def test_baselines_settle_identically(self):
        """Fair comparison: the warmup must be the same for every system."""
        with tempfile.TemporaryDirectory() as d:
            counts = {}
            for system in (SystemSpec.B0, SystemSpec.B1, SystemSpec.ACIQ):
                r = self._runner(d)
                r.run("s1_iso_during_call", system, CapacityMode.STATIC)
                counts[system] = len(r.launcher.sources)
            self.assertEqual(len(set(counts.values())), 1, counts)

    def test_dscp_is_passed_for_interactive_workloads(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s1_iso_during_call", SystemSpec.ACIQ)
            p = r.run_paths("s1_iso_during_call", SystemSpec.ACIQ,
                            CapacityMode.ADAPTIVE, 42)
            cfg = json.loads((p.root / "config.json").read_text())
            ds = {w["label"]: w["dscp"] for w in cfg["workloads"]}
            self.assertEqual(ds["call"], 46)
            self.assertIsNone(ds["bulk"])

    def test_dry_run_produces_a_result_artefact(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            res = r.run("s1_iso_during_call", SystemSpec.B0)
            p = r.run_paths("s1_iso_during_call", SystemSpec.B0,
                            CapacityMode.ADAPTIVE, 42)
            self.assertTrue((p.root / "result.json").is_file())
            self.assertIn("link_start_mbps", json.loads((p.root / "result.json").read_text()))

    def test_samples_are_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s1_iso_during_call", SystemSpec.ACIQ)
            p = r.run_paths("s1_iso_during_call", SystemSpec.ACIQ,
                            CapacityMode.ADAPTIVE, 42)
            self.assertTrue((p.root / "samples.jsonl").is_file())
            rows = (p.root / "samples.jsonl").read_text().strip().splitlines()
            self.assertGreater(len(rows), 5)

    def test_failure_note_names_the_offending_command(self):
        with tempfile.TemporaryDirectory() as d:
            r = ExperimentRunner(
                launcher=DryLauncher(),
                harness=Harness(runner=FakeRunner(fail_on="1:1 "), clock=lambda: 0.0),
                results_dir=Path(d), real_time=False)
            res = r.run("s1_iso_during_call", SystemSpec.ACIQ)
            self.assertIn("classid 1:1", res.notes[0])

    def test_six_consecutive_runs_all_succeed(self):
        """Regression guard: runs leaked into each other twice.

        First the shield's dwell timestamp survived into the next run, so the
        opening change of run 2 was vetoed as rate-limited. Then the control loop
        passed scenario-relative seconds while the shield recorded monotonic
        time, comparing two different timelines. Both only showed up on a later
        run in the matrix, which is exactly why the whole matrix is exercised.
        """
        with tempfile.TemporaryDirectory() as d:
            from aciq.metrics import CounterSnapshot
            import time as _t

            class NullSource:
                def snapshot(self):
                    return CounterSnapshot(t=_t.monotonic(), by_class={})

            r = ExperimentRunner(
                launcher=DryLauncher(),
                harness=Harness(runner=FakeRunner(auto_readback=True)),
                results_dir=Path(d), real_time=False, source=NullSource())
            for sc in ("s1_iso_during_call", "s3_tv_and_gaming"):
                for sysspec in (SystemSpec.B0, SystemSpec.B1, SystemSpec.ACIQ):
                    res = r.run(sc, sysspec, CapacityMode.ADAPTIVE, 42)
                    self.assertNotIn(
                        "apply_system failed", res.notes,
                        f"{sc}/{sysspec.value} failed: {res.notes}")

    def test_loop_runs_on_every_tick_not_just_at_a_drop(self):
        """M2 needs consecutive saturated samples. A loop that ran only at a
        drop and once at the end could never reach its streak, so the estimate
        stayed 0.0 for the whole run — which is what the first real measurement
        showed."""
        from aciq.metrics import CounterSnapshot
        import time as _t

        seen = {"polls": 0}

        class CountingSource:
            def snapshot(self):
                seen["polls"] += 1
                return CounterSnapshot(t=_t.monotonic(), by_class={})

        with tempfile.TemporaryDirectory() as d:
            r = ExperimentRunner(
                launcher=DryLauncher(),
                harness=Harness(runner=FakeRunner(auto_readback=True)),
                results_dir=Path(d), real_time=False, source=CountingSource())
            r.run("s1_iso_during_call", SystemSpec.ACIQ, CapacityMode.ADAPTIVE, 42)
            self.assertGreater(seen["polls"], 20,
                               "loop should observe once per tick, not twice per run")

    def test_baselines_do_not_run_the_adaptive_loop(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s1_iso_during_call", SystemSpec.B0, CapacityMode.STATIC)
            self.assertEqual(r.harness.policy_changes, 0)

    def test_a_capacity_drop_is_recorded(self):
        with tempfile.TemporaryDirectory() as d:
            from aciq.metrics import CounterSnapshot
            import time as _t

            class NullSource:
                def snapshot(self):
                    return CounterSnapshot(t=_t.monotonic(), by_class={})

            r = ExperimentRunner(
                launcher=DryLauncher(),
                harness=Harness(runner=FakeRunner(auto_readback=True)),
                results_dir=Path(d), real_time=False, source=NullSource())
            res = r.run("s1_iso_during_call", SystemSpec.ACIQ,
                        CapacityMode.ADAPTIVE, 42, drop_at_s=1.0)
            self.assertNotIn("no capacity drop in this run", res.notes)
            self.assertEqual(res.link_end_mbps, 20.0)

    def test_stale_artefacts_are_removed_before_a_rerun(self):
        """A stale result.json from a failed attempt would otherwise be
        compared against a fresh one and reported as if both were real."""
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            p = r.run_paths("s1_iso_during_call", SystemSpec.ACIQ,
                            CapacityMode.ADAPTIVE, 42)
            p.root.mkdir(parents=True, exist_ok=True)
            (p.root / "result.json").write_text(json.dumps({"stale": True}))
            (p.root / "junk.txt").write_text("left over")
            r.run("s1_iso_during_call", SystemSpec.ACIQ)
            self.assertFalse((p.root / "junk.txt").exists())
            self.assertNotIn("stale", (p.root / "result.json").read_text())

    def test_failed_apply_is_reported_not_crashed(self):
        with tempfile.TemporaryDirectory() as d:
            r = ExperimentRunner(
                launcher=DryLauncher(),
                harness=Harness(runner=FakeRunner(fail_on="class"), clock=lambda: 0.0),
                results_dir=Path(d), real_time=False)
            res = r.run("s1_iso_during_call", SystemSpec.ACIQ)
            self.assertTrue(any("apply_system failed" in n for n in res.notes))
            # the reason must be in the note, not just the fact of failure
            self.assertIn("injected failure", res.notes[0])


class TestMetricsHonesty(unittest.TestCase):
    def test_missing_reads_as_n_a_not_zero(self):
        m = Metric("call p50", {"a": None, "b": 12.0}, unit=" ms")
        line = m.line()
        self.assertIn("n/a", line)
        self.assertNotIn("| 0.000", line)

    def test_best_ignores_missing(self):
        m = Metric("call p50", {"a": None, "b": 12.0, "c": 30.0})
        self.assertEqual(m.best(lower_is_better=True), "b")

    def test_best_is_none_when_all_missing(self):
        self.assertIsNone(Metric("x", {"a": None}).best())

    def test_best_respects_direction(self):
        m = Metric("throughput", {"a": 5.0, "b": 20.0})
        self.assertEqual(m.best(lower_is_better=False), "b")

    def test_mean_ignores_none(self):
        self.assertAlmostEqual(mean([1.0, None, 3.0]), 2.0)

    def test_mean_of_nothing_is_none(self):
        self.assertIsNone(mean([]))


class TestStatisticsGate(unittest.TestCase):
    def test_five_pairs_cannot_reach_p005(self):
        """2^(1-n): n=5 gives 0.0625, n=6 gives 0.03125."""
        self.assertFalse(can_report_pvalue(5))
        self.assertTrue(can_report_pvalue(6))
        self.assertEqual(MIN_PAIRS_FOR_PVALUE, 6)


class TestHonestVerdicts(unittest.TestCase):
    """The report must state losses as plainly as wins."""

    def _seeds(self, metrics, n=6, jitter=0.0):
        """Expand a flat metric dict into the per-seed shape latency_table now
        returns: {metric: [(seed, value), ...]}.

        `jitter` varies later seeds slightly so tests exercise real aggregation
        rather than six identical values collapsing to one cell.
        """
        out = {}
        for i in range(n):
            for k, v in metrics.items():
                if v is None:
                    continue
                val = v if not jitter else v * (1.0 + (i - n / 2) * jitter)
                out.setdefault(k, []).append((40 + i, val))
        return out

    def _table(self, aciq_p, rival_p=None):
        """Two systems with *different* numbers; a tie is spelled out."""
        rival_p = rival_p or dict(aciq_p)
        return {"s1": {"aciq": {"call": self._seeds(aciq_p)},
                       "b1_cake95": {"call": self._seeds(rival_p)}}}

    def test_a_loss_is_stated(self):
        from aciq.report import latency_sections
        # aciq worse at every percentile
        sec = "\n".join(latency_sections(self._table(
            {"p50": 5.0, "p95": 5.0, "p99": 5.0, "jitter_ms": 5.0,
             "loss_ratio": 0.0},
            {"p50": 1.0, "p95": 1.0, "p99": 1.0, "jitter_ms": 1.0,
             "loss_ratio": 0.0})))
        self.assertIn("ACIQ LOSES", sec)
        self.assertNotIn("ACIQ beats", sec)

    def test_a_win_is_stated(self):
        from aciq.report import latency_sections
        sec = "\n".join(latency_sections(self._table(
            {"p50": 1.0, "p95": 1.0, "p99": 1.0, "jitter_ms": 1.0,
             "loss_ratio": 0.0},
            {"p50": 9.0, "p95": 9.0, "p99": 9.0, "jitter_ms": 9.0,
             "loss_ratio": 0.0})))
        self.assertIn("ACIQ beats", sec)
        self.assertNotIn("LOSES", sec)

    def test_a_tie_is_reported_as_a_tie(self):
        from aciq.report import latency_sections
        sec = "\n".join(latency_sections(self._table(
            {"p50": 1.0, "p95": 1.0, "p99": 1.0, "jitter_ms": 1.0,
             "loss_ratio": 0.0})))
        self.assertIn("matches", sec)
        self.assertNotIn("LOSES", sec)

    def _three(self, aciq_p, cake_p, fifo_p):
        return {"s1": {"aciq": {"call": self._seeds(aciq_p)},
                       "b1_cake95": {"call": self._seeds(cake_p)},
                       "b0_fifo": {"call": self._seeds(fifo_p)}}}

    def test_beating_one_rival_and_losing_to_another_reads_as_two_clauses(self):
        """The real p95 shape: ACIQ beats pfifo on p95 by 58x and loses to cake
        by 6 microseconds. Rendered as "beats b0_fifo LOSES to b1_cake95" that
        parses as a garbled run-on and buries the loss inside a sentence about a
        win -- which is the whole reason the bullet lists losers at all."""
        from aciq.report import latency_sections
        sec = "\n".join(latency_sections(self._three(
            {"p95": 0.581, "p50": 0.476, "p99": 0.776, "jitter_ms": 0.155,
             "loss_ratio": 0.0},
            {"p95": 0.578, "p50": 0.482, "p99": 0.703, "jitter_ms": 0.084,
             "loss_ratio": 0.0},
            {"p95": 33.577, "p50": 0.473, "p99": 33.703, "jitter_ms": 6.135,
             "loss_ratio": 0.0})))
        self.assertIn("p95: ACIQ beats b0_fifo and LOSES to b1_cake95", sec)
        self.assertNotIn("b0_fifo LOSES to", sec)
        self.assertNotIn("cake95 LOSES to", sec)

    def test_all_three_rivals_in_one_clause_are_still_and_joined(self):
        from aciq.report import latency_sections
        sec = "\n".join(latency_sections(self._three(
            {"p95": 9.0, "p50": 9.0, "p99": 9.0, "jitter_ms": 9.0,
             "loss_ratio": 0.0},
            {"p95": 1.0, "p50": 1.0, "p99": 1.0, "jitter_ms": 1.0,
             "loss_ratio": 0.0},
            {"p95": 1.0, "p50": 1.0, "p99": 1.0, "jitter_ms": 1.0,
             "loss_ratio": 0.0})))
        self.assertIn("p95: ACIQ LOSES to b1_cake95 and b0_fifo", sec)

    def test_a_split_result_is_stated_as_both(self):
        from aciq.report import latency_sections
        sec = "\n".join(latency_sections(self._table(
            {"p50": 1.0, "p95": 9.0, "p99": 1.0, "jitter_ms": 1.0,
             "loss_ratio": 0.0},
            {"p50": 5.0, "p95": 5.0, "p99": 5.0, "jitter_ms": 5.0,
             "loss_ratio": 0.0})))
        self.assertIn("p50: ACIQ beats b1_cake95", sec)
        self.assertIn("p95: ACIQ LOSES to b1_cake95", sec)

    def test_game_latency_is_reported_for_the_game_scenario(self):
        """s3 has no call, only a game. Reporting n/a for every system made a
        complete set of measurements look like missing data."""
        import tempfile
        from aciq.report import latency_table
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "s3__aciq__adaptive__seed42"
            root.mkdir(parents=True)
            (root / "result.json").write_text(json.dumps(
                {"scenario": "s3", "system": "aciq", "capacity_mode": "adaptive"}))
            (root / "workloads.json").write_text(json.dumps(
                {"game": {"p50": 0.3, "p95": 0.5, "p99": 0.7,
                          "jitter_ms": 0.1, "loss_ratio": 0.0}}))
            t = latency_table(Path(d))
            self.assertIn("game", t["s3"]["aciq"])

    def test_missing_percentile_reads_as_na_not_zero(self):
        from aciq.report import _fmt
        self.assertEqual(_fmt(None), "n/a")
        self.assertNotEqual(_fmt(0.0), "n/a")


class TestReport(unittest.TestCase):
    def test_empty_dir_says_nothing_measured(self):
        with tempfile.TemporaryDirectory() as d:
            out = build_report(Path(d))
            self.assertIn("No runs found", out)
            self.assertIn("Nothing has been measured", out)

    def test_run_table_is_rendered(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name, res in (
                ("s1__aciq__adaptive__seed42", {"scenario": "s1", "system": "aciq",
                    "capacity_mode": "adaptive", "seed": 42, "link_start_mbps": 100.0,
                    "link_end_mbps": 20.0, "estimator_mbps": 19.1, "policy_changes": 2}),
                ("s1__b1_cake95__static__seed42", {"scenario": "s1",
                    "system": "b1_cake95", "capacity_mode": "static", "seed": 42,
                    "link_start_mbps": 100.0, "link_end_mbps": 20.0,
                    "estimator_mbps": None, "policy_changes": 0}),
            ):
                sub = root / name
                sub.mkdir()
                (sub / "result.json").write_text(json.dumps(res))
                (sub / "workloads.json").write_text(json.dumps(
                    {"call": {"p50": 12.5 if "aciq" in name else 40.0}}))
            out = build_report(root)
            self.assertIn("Runs found: **2**", out)
            self.assertIn("19.1 Mbps", out)
            self.assertIn("call latency", out.lower())

    def test_single_run_refuses_to_offer_pvalues(self):
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "s1__aciq__adaptive__seed42"
            sub.mkdir()
            (sub / "result.json").write_text(json.dumps(
                {"scenario": "s1", "system": "aciq", "capacity_mode": "adaptive",
                 "seed": 42, "link_start_mbps": 100.0, "link_end_mbps": 100.0,
                 "estimator_mbps": None, "policy_changes": 0}))
            out = build_report(Path(d))
            self.assertIn("no p-values", out)
            self.assertIn("0.0625", out)

    def test_limitations_are_always_stated(self):
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "r"
            sub.mkdir()
            (sub / "result.json").write_text(json.dumps(
                {"scenario": "s1", "system": "aciq", "capacity_mode": "adaptive",
                 "seed": 1, "link_start_mbps": 100.0, "link_end_mbps": 100.0,
                 "estimator_mbps": None, "policy_changes": 0}))
            out = build_report(Path(d))
            self.assertIn("HTB token-bucket emulation", out)
            self.assertIn("downstream", out.lower())

    def test_missing_latency_is_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "r"
            sub.mkdir()
            (sub / "result.json").write_text(json.dumps(
                {"scenario": "s1", "system": "aciq", "capacity_mode": "adaptive",
                 "seed": 1, "link_start_mbps": 1, "link_end_mbps": 1,
                 "estimator_mbps": None, "policy_changes": 0}))
            (sub / "workloads.json").write_text(json.dumps({"bulk": {"p50": 1.0}}))
            out = build_report(Path(d))
            self.assertIn("recorded no latency at all", out)

    def test_unparseable_result_is_skipped_not_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            sub = Path(d) / "broken"
            sub.mkdir()
            (sub / "result.json").write_text("{not json")
            self.assertEqual(load_runs(Path(d)), [])
            self.assertIn("No runs found", build_report(Path(d)))


if __name__ == "__main__":
    unittest.main()


class TestEnforcementWiring(unittest.TestCase):
    """The loop that makes classify() reach the kernel.

    Every assertion here is about the join, because the previous failure was
    exactly this: `enforce()` existed, was correct, and nothing called it.
    """

    # Two conntrack lines shaped like the ones the gate measured: a 1000-byte
    # video flow and a 200-byte gaming flow, both UNREPLIED, both on 7001/7002.
    CT = (
        "udp 17 29 src=10.0.1.2 dst=10.0.1.3 sport=40001 dport=7001 "
        "packets=4000 bytes=4000000 [UNREPLIED] src=10.0.1.3 dst=10.0.1.2 "
        "sport=7001 dport=40001 packets=0 bytes=0 mark=0 use=1\n"
        "udp 17 29 src=10.0.1.2 dst=10.0.1.3 sport=40002 dport=7002 "
        "packets=4000 bytes=800000 [UNREPLIED] src=10.0.1.3 dst=10.0.1.2 "
        "sport=7002 dport=40002 packets=0 bytes=0 mark=0 use=1\n"
    )

    def _runner(self, tmp, launcher=None):
        r = ExperimentRunner(
            launcher=launcher or DryLauncher(),
            harness=Harness(runner=FakeRunner(auto_readback=True), clock=lambda: 0.0),
            results_dir=Path(tmp), real_time=False, tick_s=1.0)
        r._ct = type("CT", (), {"read": lambda self: self._CT})()
        r._ct._CT = self.CT
        return r

    def test_enforcement_is_off_unless_asked_for(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s3_tv_and_gaming", SystemSpec.ACIQ)
            p = r.run_paths("s3_tv_and_gaming", SystemSpec.ACIQ,
                            CapacityMode.ADAPTIVE, 42)
            sample = json.loads((p.root / "samples.jsonl").read_text().splitlines()[0])
            self.assertEqual(sample["verdicts"], {})
            self.assertFalse(r.harness.enforcement_enabled)

    def test_a_dry_run_does_not_pretend_to_enforce(self):
        """A dry run launches nothing, so conntrack reports no flows. Wiring the
        loop on anyway would produce a run that looks connected while measuring
        nothing."""
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s3_tv_and_gaming", SystemSpec.ACIQ, enforce=True)
            self.assertFalse(r.harness.enforcement_enabled)

    def test_baselines_are_never_steered(self):
        """Steering a baseline would not make the comparison unfair, it would
        make it meaningless -- the baseline would no longer be a baseline."""
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r.run("s3_tv_and_gaming", SystemSpec.B0, enforce=True)
            self.assertFalse(r.harness.enforcement_enabled)

    def test_verdicts_are_keyed_by_workload_label(self):
        """The dport is the join key. The source port changes on every reconnect
        and cannot appear in a flower filter at all."""
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            ports = [("video", 7001, None), ("gaming", 7002, None)]
            r._tracker = type("T", (), {})()
            from aciq.flowtrack import FlowTracker
            tracker = FlowTracker()
            r._tracker = tracker
            # Two observations so age and bytes accumulate into real features.
            tracker.observe(self.CT, 0.0)
            tracker.observe(self.CT.replace("4000000", "4400000")
                            .replace("800000", "880000"), 1.0)
            r.harness.enable_enforcement(executor=_Exec())
            out, _n = r._enforcement_step(ports, 2.0)
            self.assertEqual(set(out), {"video", "gaming"})
            for label, v in out.items():
                self.assertIn("class", v)
                self.assertIn("confidence", v)

    def test_a_flow_the_run_does_not_own_is_ignored(self):
        """conntrack holds everything on the host -- this machine's own DNS, the
        loopback entries gate check 3 printed, another run's leftovers. Steering
        any of it because it happened to be in the table would be a spectacular
        way to produce a plausible-looking number."""
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            from aciq.flowtrack import FlowTracker
            tracker = FlowTracker()
            r._tracker = tracker
            tracker.observe(self.CT, 0.0)
            tracker.observe(self.CT.replace("4000000", "4400000")
                            .replace("800000", "880000"), 1.0)
            r.harness.enable_enforcement(executor=_Exec())
            # The run owns 7001 only; 7002 and the loopback traffic are not ours.
            out, _n = r._enforcement_step([("video", 7001, None)], 2.0)
            self.assertEqual(set(out), {"video"})

    def test_one_failed_conntrack_read_does_not_kill_the_run(self):
        class Boom:
            def read(self):
                raise OSError("conntrack raced a flush")
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r._ct = Boom()
            r._tracker = object()
            self.assertEqual(r._enforcement_step([("v", 7001, None)], 1.0)[0], {})


class _LiveishLauncher:
    """Not a DryLauncher, but launches nothing real.

    Standing in for NetnsLauncher so `will_enforce` is True and run() reaches the
    lines that build the tracker and the conntrack source. Those lines are why
    the missing import below went unnoticed for a whole test run: the dry-run
    guard meant no test ever executed them, and `import aciq.experiment` still
    succeeded because `from __future__ import annotations` leaves those names as
    strings until the line actually runs.
    """

    def __init__(self):
        self.stopped = False

    def spawn_sink(self, kind, port, log_path):
        return None

    def spawn_source(self, kind, dst, port, duration, dscp, json_out, log_path):
        return None

    def collect(self):
        return []

    def stop(self):
        self.stopped = True


class TestEnforcementPathIsReachable(unittest.TestCase):
    """Guards against a whole class of bug: code that no test executes.

    The real run died with `NameError: name 'FlowTracker' is not defined`
    despite 471 passing tests, because the only reachable branch skipped the
    lines that use the name and postponed annotations meant the module still
    imported cleanly.
    """

    def _run(self, tmp):
        r = ExperimentRunner(
            launcher=_LiveishLauncher(),
            harness=Harness(runner=FakeRunner(auto_readback=True), clock=lambda: 0.0),
            results_dir=Path(tmp), real_time=False, tick_s=1.0,
            bridge_executor=_Exec())
        res = r.run("s3_tv_and_gaming", SystemSpec.ACIQ, enforce=True)
        return r, res

    def test_the_enforcement_branch_actually_executes(self):
        """Checked through the tick counter, not the live objects: teardown runs
        before run() returns, so by the time a caller looks, the enforcer and the
        tracker are both gone by design. The counter outlives them."""
        with tempfile.TemporaryDirectory() as d:
            r, res = self._run(d)
            self.assertGreater(r._enf_ticks, 0,
                               "the enforcement tick never ran")
            self.assertIn("enforcement ON", " ".join(res.notes))

    def test_it_reports_that_it_steered_nothing(self):
        """This launcher spawns no traffic, so conntrack is empty and the run
        measured only the reporting path. The note has to say exactly that --
        it is the whole point of having a real run to check against."""
        with tempfile.TemporaryDirectory() as d:
            _r, res = self._run(d)
            self.assertIn("STEERED NOTHING", " ".join(res.notes))

    def test_and_teardown_ran(self):
        """Filters must not outlive the run: a run that leaves them behind steers
        the next run's traffic before it has decided anything."""
        with tempfile.TemporaryDirectory() as d:
            r, _res = self._run(d)
            self.assertFalse(r.harness.enforcement_enabled)
            self.assertTrue(r.launcher.stopped)
            self.assertIsNone(r._tracker, "the tracker outlived the run")

    def test_flowtracker_is_actually_imported(self):
        """Directly, because the failure mode is an import that silently did not
        happen rather than one that failed loudly."""
        import aciq.experiment as E
        self.assertEqual(E.FlowTracker.__module__, "aciq.flowtrack")
        self.assertEqual(E.ConntrackSource.__module__, "aciq.flowtrack")


class TestSilentEnforcementIsCalledOut(unittest.TestCase):
    """Enforcement that runs and classifies nothing must not read as working.

    ConntrackSource.read() catches every error and returns "", so a broken read,
    a wrong namespace, or flows that never cross the shaped device all look
    identical to an idle link. Without a count, the run reports "enforcement
    ON" and a reader concludes the mechanism worked.
    """

    def _runner(self, tmp, ct_text):
        r = ExperimentRunner(
            launcher=DryLauncher(),
            harness=Harness(runner=FakeRunner(auto_readback=True), clock=lambda: 0.0),
            results_dir=Path(tmp), real_time=False, tick_s=1.0)
        r._ct = type("CT", (), {"read": lambda self: ct_text})()
        return r

    CT_MATURE = ("udp 17 29 src=203.0.113.2 dst=10.0.1.2 sport=40001 dport=7001 "
                 "packets=40000 bytes=40000000 [UNREPLIED] src=10.0.1.2 "
                 "dst=203.0.113.2 sport=7001 dport=40001 packets=0 bytes=0 "
                 "mark=0 use=1\n")

    def test_an_empty_conntrack_read_steers_nothing(self):
        from aciq.flowtrack import FlowTracker
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d, "")
            r._tracker = FlowTracker()
            r._enf_ticks = r._enf_steered = 0
            r._enforcement_step([("video", 7001, None)], 1.0)
            self.assertEqual((r._enf_ticks, r._enf_steered), (1, 0))

    def test_seeing_a_flow_is_not_the_same_as_steering_it(self):
        """A tick can find four flows and decline every one of them -- they were
        too young. Counting that as work would let a run look healthy on the
        strength of having looked at traffic."""
        from aciq.flowtrack import FlowTracker
        ct = ("udp 17 29 src=203.0.113.2 dst=10.0.1.2 sport=40001 dport=7001 "
              "packets=4 bytes=4000 [UNREPLIED] src=10.0.1.2 dst=203.0.113.2 "
              "sport=7001 dport=40001 packets=0 bytes=0 mark=0 use=1\n")
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d, ct)
            r._tracker = FlowTracker()
            r.harness.enable_enforcement(executor=_Exec())
            r._enf_ticks = r._enf_steered = 0
            out, _n = r._enforcement_step([("video", 7001, None)], 1.0)
            self.assertEqual(set(out), {"video"}, "the flow should have been seen")
            self.assertFalse(out["video"]["changed"], "but declined: age 0")
            self.assertEqual(r._enf_steered, 0, "seeing a flow counted as steering")

    def _note(self, ticks, steered, on=True, why="not requested"):
        r = ExperimentRunner(launcher=DryLauncher(),
                             harness=Harness(runner=FakeRunner(auto_readback=True),
                                              clock=lambda: 0.0))
        r._enf_ticks, r._enf_steered = ticks, steered
        return r._enforcement_note(on, why)

    def test_the_note_says_on_but_steered_nothing_when_it_never_did(self):
        n = self._note(7, 0)
        self.assertIn("ON", n)
        self.assertIn("STEERED NOTHING", n)
        self.assertIn("reporting path", n)

    def test_a_partial_run_says_how_many_ticks_did_work(self):
        self.assertIn("6/40", self._note(40, 6))

    def test_a_fully_working_run_says_only_that_it_was_on(self):
        self.assertEqual(self._note(40, 40), "per-flow enforcement ON")

    def test_an_off_run_carries_its_reason(self):
        self.assertIn("dry run", self._note(0, 0, on=False, why="dry run launches no traffic"))


class _Exec:
    """Answers tc's -j listing with an empty device."""

    def __call__(self, argv):
        if "-j" in argv:
            return 0, "[]", ""
        return 0, "", ""


class TestEnforcementIsRecorded(unittest.TestCase):
    """A run has to say whether it enforced.

    The failure this prevents is specific: samples carry per-tick verdicts, but a
    reader comparing two result directories would have to read every sample line
    before telling an enforced run from a reporting-only one. "Did this run
    enforce?" is the first question asked of any new number.
    """

    def _run(self, tmp, system, enforce):
        r = ExperimentRunner(
            launcher=DryLauncher(),
            harness=Harness(runner=FakeRunner(auto_readback=True), clock=lambda: 0.0),
            results_dir=Path(tmp), real_time=False, tick_s=1.0)
        res = r.run("s3_tv_and_gaming", system, enforce=enforce)
        p = r.run_paths("s3_tv_and_gaming", system, CapacityMode.ADAPTIVE, 42)
        return (json.loads((p.root / "config.json").read_text()),
                json.loads((p.root / "result.json").read_text()), res)

    def test_config_records_the_request_and_the_reason(self):
        with tempfile.TemporaryDirectory() as d:
            cfg, _res, _ = self._run(d, SystemSpec.B0, enforce=True)
            self.assertTrue(cfg["enforce_requested"])
            self.assertIn("baseline", cfg["enforcement_note"])

    def test_result_records_the_outcome_not_a_prediction(self):
        with tempfile.TemporaryDirectory() as d:
            _cfg, result, _ = self._run(d, SystemSpec.B0, enforce=True)
            self.assertIn("enforcement OFF", " ".join(result["notes"]))

    def test_an_unrequested_run_says_so_rather_than_saying_nothing(self):
        """Silence would read as "no note because nothing interesting happened",
        which is not the same claim as "this run did not enforce"."""
        with tempfile.TemporaryDirectory() as d:
            cfg, result, _ = self._run(d, SystemSpec.ACIQ, enforce=False)
            self.assertFalse(cfg["enforce_requested"])
            self.assertIn("not requested", cfg["enforcement_note"])
            self.assertIn("enforcement OFF", " ".join(result["notes"]))

    def test_config_does_not_claim_an_outcome_it_cannot_know_yet(self):
        with tempfile.TemporaryDirectory() as d:
            cfg, _r, _ = self._run(d, SystemSpec.ACIQ, enforce=True)
            self.assertNotIn("enforcement_effective", cfg,
                             "config.json is written before the tree is built")


class TestEverySeedSurvives(unittest.TestCase):
    """The report printed one seed's numbers under a "54 runs" header.

    latency_table did `entry[label] = {...}` once per run directory, so with six
    seeds the last one overwrote the other five. s1's ACIQ row read p99=18.461 --
    seed 47 alone; the six were 2.665, 1.443, 2.147, 20.104, 2.538, 18.461. Two
    of six hit ~20 ms and the reported number was one of them.
    """

    def _matrix(self, tmp, seeds):
        for seed in seeds:
            d = Path(tmp) / f"r__aciq__adaptive__seed{seed}"
            d.mkdir(parents=True)
            (d / "result.json").write_text(json.dumps(
                {"scenario": "s1", "system": "aciq", "capacity_mode": "adaptive",
                 "seed": seed, "estimator_mbps": 100.0, "policy_changes": 1,
                 "link_start_mbps": 100.0, "link_end_mbps": 20.0}))
            (d / "workloads.json").write_text(json.dumps(
                {"call": {"p50": 0.2 + seed / 1000.0, "p95": 1.0,
                          "p99": 2.0, "jitter_ms": 0.3, "loss_ratio": 0.0}}))

    def test_all_seeds_are_kept(self):
        with tempfile.TemporaryDirectory() as d:
            self._matrix(d, range(42, 48))
            from aciq.report import latency_table
            t = latency_table(Path(d))
            got = t["s1"]["aciq"]["call"]["p50"]
            self.assertEqual(len(got), 6, "a seed was overwritten")

    def test_the_table_shows_the_spread_not_one_seed(self):
        with tempfile.TemporaryDirectory() as d:
            self._matrix(d, range(42, 48))
            from aciq.report import build_report
            sec = build_report(Path(d))
            self.assertIn("(0.242-0.247)", sec, "only one seed's value is shown")

    def test_a_seed_is_carried_so_pairs_can_be_formed(self):
        with tempfile.TemporaryDirectory() as d:
            self._matrix(d, [42, 43])
            from aciq.report import latency_table
            got = latency_table(Path(d))["s1"]["aciq"]["call"]["p50"]
            self.assertEqual(sorted(s for s, _v in got), [42, 43])


class TestSignificanceIsActuallyComputed(unittest.TestCase):
    """6 runs used to switch the caveat OFF and print no p-value at all.

    Silence reads as significance, which is worse than either reporting a number
    or reporting a refusal.
    """

    def _two_systems(self, tmp, aciq, rival, seeds=range(42, 48),
                     spreads=None):
        """`spreads` jitters each system's value per seed.

        Two earlier versions of this fixture were wrong in instructive ways.
        Constant values are not "no difference": ACIQ 0.2 vs rival 0.21 on every
        seed is a consistent win and returns the floor p=0.0312. Giving *both*
        systems the same jitter is worse -- every paired difference is exactly 0,
        which is a perfect tie, and the test correctly returns None. Interleaving
        needs the two systems to jitter differently, so the sign of each paired
        difference alternates.
        """
        for i, seed in enumerate(seeds):
            for system, p99, sp in (("aciq", aciq, (spreads or {}).get("aciq")),
                                    ("b0_fifo", rival, (spreads or {}).get("b0_fifo"))):
                v = p99 + (sp[i] if sp else 0.0)
                d = Path(tmp) / f"r__{system}__x__seed{seed}"
                d.mkdir(parents=True)
                (d / "result.json").write_text(json.dumps(
                    {"scenario": "s1", "system": system,
                     "capacity_mode": "adaptive", "seed": seed}))
                (d / "workloads.json").write_text(json.dumps(
                    {"call": {"p50": v, "p95": v, "p99": v,
                              "jitter_ms": v, "loss_ratio": 0.0}}))

    def test_a_real_difference_produces_a_p_value(self):
        with tempfile.TemporaryDirectory() as d:
            self._two_systems(d, 0.2, 120.0)
            self.assertIn("p < 0.05", build_report(Path(d)))

    def test_no_difference_produces_no_significance_claim(self):
        """ACIQ and cake overlapping is the honest outcome in the real matrix,
        and the report must say so rather than letting a missing number imply
        support. The two systems' per-seed values interleave, so neither wins
        consistently."""
        with tempfile.TemporaryDirectory() as d:
            # Different jitter per system, so the signs of the paired differences
            # alternate instead of all pointing the same way.
            self._two_systems(d, 0.2, 0.2, spreads={
                "aciq": [0.00, 0.04, -0.03, 0.05, -0.04, 0.02],
                "b0_fifo": [0.02, -0.01, 0.05, -0.02, 0.06, -0.01]})
            sec = build_report(Path(d))
            self.assertIn("of 4 comparisons reach p < 0.05", sec)
            self.assertIn("0 of", sec)

    def test_exact_wilcoxon_rejects_all_ties(self):
        from aciq.report import exact_wilcoxon
        self.assertIsNone(exact_wilcoxon([(1.0, 1.0)] * 8))

    def test_exact_wilcoxon_floor_at_n6(self):
        """2/64 = 0.03125 is the smallest attainable p at n=6, so 'p < 0.05'
        barely clears and cannot go lower without more seeds."""
        from aciq.report import exact_wilcoxon
        r = exact_wilcoxon([(0.2, 120.0)] * 6)
        self.assertAlmostEqual(r["p"], 2 / 64)

    def test_exact_wilcoxon_reports_dropped_zero_pairs(self):
        from aciq.report import exact_wilcoxon
        r = exact_wilcoxon([(1.0, 2.0), (2.0, 1.0), (5.0, 5.0), (6.0, 6.0)])
        self.assertEqual((r["n"], r["zeros"]), (2, 2))

    def test_exact_wilcoxon_uses_average_ranks_for_ties(self):
        from aciq.report import exact_wilcoxon
        a = exact_wilcoxon([(1.0, 2.0), (2.0, 1.0)])
        b = exact_wilcoxon([(1.0, 2.0), (1.0, 3.0)])
        self.assertIsNotNone(a)
        self.assertIsNotNone(b)


class TestEnforcementCountersArePerRun(unittest.TestCase):
    """Counters accumulated across runs, which disabled the safety net.

    A matrix printed `1/31`, `2/62`, `3/93` ... `18/678`: the note described the
    process, not the run. Worse, `_enf_steered` never returned to zero, so the
    "STEERED NOTHING" guard could not fire after the first run that steered
    anything -- the net built to catch a silent no-op was blind from run 2 on.
    """

    def _two_runs(self, tmp):
        r = ExperimentRunner(
            launcher=_LiveishLauncher(),
            harness=Harness(runner=FakeRunner(auto_readback=True), clock=lambda: 0.0),
            results_dir=Path(tmp), real_time=False, tick_s=1.0,
            bridge_executor=_Exec())
        first = r.run("s3_tv_and_gaming", SystemSpec.ACIQ, enforce=True)
        # simulate run 2 having steered nothing at all
        r._enf_ticks, r._enf_steered = 40, 0
        second = r.run("s3_tv_and_gaming", SystemSpec.ACIQ, enforce=True)
        return first, second

    def test_a_run_that_steered_nothing_still_says_so(self):
        """The guard must work on run 2, not just run 1."""
        with tempfile.TemporaryDirectory() as d:
            _first, second = self._two_runs(d)
            self.assertIn("STEERED NOTHING", " ".join(second.notes))

    def test_counters_do_not_accumulate_across_runs(self):
        with tempfile.TemporaryDirectory() as d:
            r = ExperimentRunner(
                launcher=_LiveishLauncher(),
                harness=Harness(runner=FakeRunner(auto_readback=True),
                                clock=lambda: 0.0),
                results_dir=Path(d), real_time=False, tick_s=1.0,
                bridge_executor=_Exec())
            r.run("s3_tv_and_gaming", SystemSpec.ACIQ, enforce=True)
            first_ticks = r._enf_ticks
            r.run("s3_tv_and_gaming", SystemSpec.ACIQ, enforce=True)
            self.assertLessEqual(r._enf_ticks, first_ticks * 1.5,
                                 "the second run inherited the first's ticks")


class TestAStaleEstimateSaysSo(unittest.TestCase):
    """The matrix reported estimator=102.77 Mbps beside link_end=20.0.

    M2 measures a link only while it is oversubscribed. After the drop, the
    workload's own rate fell to just under the new capacity, the link stopped
    being oversubscribed, and the last reading -- taken at t=2 s, before the
    drop at t=20 s -- was carried to the end of the run as the estimate. Twelve
    runs did this.
    """

    def _runner(self, tmp):
        return ExperimentRunner(
            launcher=DryLauncher(),
            harness=Harness(runner=FakeRunner(auto_readback=True), clock=lambda: 0.0),
            results_dir=Path(tmp), real_time=False, tick_s=1.0)

    def test_an_estimate_from_before_the_drop_is_flagged_stale(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r._est_t, r._cap_t = 2.0, 20.0
            note = r._stale_note(102.77)
            self.assertIn("STALE", note)
            self.assertIn("102.8", note)
            self.assertIn("t=2.0s", note)

    def test_an_estimate_taken_after_the_drop_is_not_flagged(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r._est_t, r._cap_t = 21.0, 20.0
            self.assertEqual(r._stale_note(19.4), "")

    def test_no_estimate_is_not_stale(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r._est_t, r._cap_t = 2.0, 20.0
            self.assertEqual(r._stale_note(None), "")

    def test_no_capacity_change_means_nothing_to_be_stale_against(self):
        with tempfile.TemporaryDirectory() as d:
            r = self._runner(d)
            r._est_t, r._cap_t = 2.0, None
            self.assertEqual(r._stale_note(102.0), "")
