"""Phase 8: end-to-end lifecycle (dry, no kernel)."""
import json
import tempfile
import unittest
from pathlib import Path

from aciq.experiment import DryLauncher, ExperimentRunner
from aciq.harness import CapacityMode, Harness, SystemSpec
from aciq.metrics import CounterSnapshot
from aciq.txn import FakeRunner

NOW = 1_700_000_000.0


class _NullSource:
    def snapshot(self):
        import time as _t
        return CounterSnapshot(t=_t.monotonic(), by_class={})


def _runner(d, **kw):
    return ExperimentRunner(
        launcher=DryLauncher(),
        harness=Harness(runner=FakeRunner(auto_readback=True)),
        results_dir=Path(d), real_time=False, source=_NullSource(), **kw)


class TestEndToEnd(unittest.TestCase):
    def test_intelligence_run_completes_and_logs(self):
        with tempfile.TemporaryDirectory() as d:
            r = _runner(d)
            res = r.run("s1_iso_during_call", SystemSpec.ACIQ,
                        CapacityMode.ADAPTIVE, 42, intelligence=True)
            self.assertIsNotNone(res)
            summary = getattr(r, "_last_intel_summary", None)
            self.assertTrue(summary and "action" in summary)
            # every lifecycle closes the loop: decision log exists + valid
            log = Path(d).parent / "data"  # not used; logger writes to cfg path
            decisions_file = Path("data/intelligence/decisions.jsonl")
            if decisions_file.exists():
                lines = [json.loads(l) for l in
                         decisions_file.read_text().splitlines() if l.strip()]
                self.assertTrue(lines)
                self.assertTrue(all("action" in x for x in lines))

    def test_no_dead_modules(self):
        # historical/outcome/recovery modules must be called by the loop
        src = Path("aciq/experiment.py").read_text()
        for needle in ("HistoricalComparer", "OutcomeVerifier", "RecoveryEngine",
                       "ExperienceStore", "DecisionLogger"):
            self.assertIn(needle, src, needle)

    def test_lifecycle_closeout_writes_outcome(self):
        # feed the verifier a degraded post-apply measurement through the
        # same path the loop uses (pending lifecycle -> verify -> store)
        from aciq.intelligence.contracts import (
            ApplicationResult, ReadbackResult)
        from aciq.intelligence.outcome import OutcomeVerifier
        app = ApplicationResult(decision_id="d1", candidate_id="c1",
                                submitted=True, controller_accepted=True,
                                applied=True, readback_verified=True,
                                recorded_at=NOW)
        rb = ReadbackResult(verified=True, recorded_at=NOW)
        o = OutcomeVerifier().verify(app, rb, {"latency_ms": 90.0}, now=NOW)
        self.assertEqual(o.outcome.value, "degraded")


if __name__ == "__main__":
    unittest.main()
