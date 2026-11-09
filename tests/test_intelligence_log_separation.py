"""Task E: dry/test runs never pollute live audit destinations."""
import tempfile
import unittest
from pathlib import Path

from aciq.experiment import DryLauncher, ExperimentRunner
from aciq.harness import CapacityMode, Harness, SystemSpec
from aciq.metrics import CounterSnapshot
from aciq.txn import FakeRunner

REAL_DECISIONS = Path("data/intelligence/decisions.jsonl")


class _NullSource:
    def snapshot(self):
        import time as _t
        return CounterSnapshot(t=_t.monotonic(), by_class={})


class TestLogSeparation(unittest.TestCase):
    def test_dry_run_writes_nothing_to_live_logs(self):
        before = len(REAL_DECISIONS.read_text().splitlines()) if REAL_DECISIONS.exists() else 0
        with tempfile.TemporaryDirectory() as d:
            runner = ExperimentRunner(
                launcher=DryLauncher(),
                harness=Harness(runner=FakeRunner(auto_readback=True)),
                results_dir=Path(d), real_time=False, source=_NullSource())
            runner.run("s1_iso_during_call", SystemSpec.ACIQ,
                       CapacityMode.ADAPTIVE, 42, intelligence=True)
        after = len(REAL_DECISIONS.read_text().splitlines()) if REAL_DECISIONS.exists() else 0
        self.assertEqual(before, after,
                         "dry run polluted the live decisions log")

    def test_live_config_defaults_unchanged(self):
        from aciq.intelligence.config import IntelligenceConfig
        cfg = IntelligenceConfig()
        self.assertEqual(cfg.decisions_path, "data/intelligence/decisions.jsonl")
        self.assertEqual(cfg.experience_path, "data/experiences.jsonl")


if __name__ == "__main__":
    unittest.main()
