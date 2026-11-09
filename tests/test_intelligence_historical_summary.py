"""Task A: historical_summary in DecisionResult (additive, backward-compatible).

- decisions computed with historical evidence carry the summary verbatim
- decisions computed without it carry historical=None (not run ≠ failed)
- records written before this field existed still load
"""
import json
import tempfile
import unittest
from pathlib import Path

from aciq.intelligence.candidates import CandidateGenerator
from aciq.intelligence.contracts import (
    DecisionResult,
    HistoricalResult,
    NetworkState,
    Reliability,
)
from aciq.intelligence.decide import DecisionEngine
from aciq.intelligence.evaluator import PolicyEvaluator
from aciq.intelligence.historical import HistoricalComparer
from aciq.intelligence.predictor import DegradationPredictor
from aciq.intelligence.validate import AcceptanceGate
from aciq.model import Capacity, TrafficClass
from aciq.policy import build_plan

NOW = 1_700_000_100.0


def _capacity(mbps=100.0):
    return Capacity(mbps=mbps, confidence=0.9, saturated=False, changed=False)


def _state():
    return NetworkState(
        capacity=_capacity(),
        per_class_demand={TrafficClass.VIDEO_CALL: 1.0}, active_flows=2,
        latency_ms=5.0, jitter_ms=1.0, loss_ratio=0.0,
        freshness={"capacity": 0.5}, reliability=Reliability.RELIABLE,
        recorded_at=NOW)


def _write_run(root: Path, name: str, link_end: float):
    d = root / name
    d.mkdir(parents=True)
    (d / "result.json").write_text(json.dumps(
        {"link_start_mbps": 100.0, "link_end_mbps": link_end,
         "estimator_mbps": link_end - 25.0}))
    (d / "call.json").write_text(json.dumps({"p95": 10.0, "jitter_ms": 1.0,
                                             "loss_ratio": 0.0}))
    (d / "bulk.json").write_text(json.dumps({"sender_mbps": 80.0}))


class TestHistoricalSummary(unittest.TestCase):
    def _decide(self, historical):
        st = _state()
        ev = PolicyEvaluator().evaluate(st, build_plan(100.0), "c1", now=NOW)
        pred = DegradationPredictor().predict(
            [{"latency_ms": 5.0, "backlog_bytes": 100.0,
              "capacity_mbps": 100.0, "per_class": {"x": 1}}] * 5, st, "c1")
        cands = CandidateGenerator().generate(st, build_plan(100.0), "p0",
                                              correlation_id="c1")
        gate = AcceptanceGate()
        vals = [gate.validate(c, st, build_plan(100.0)) for c in cands]
        return DecisionEngine().decide(st, ev, pred, cands, vals, historical, [],
                                       "c1", now=NOW)

    def test_summary_present_when_historical_given(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_run(root, "s1__seed1", 100.0)
            st = _state()
            cands = CandidateGenerator().generate(st, build_plan(100.0), "p0",
                                                  correlation_id="c1")
            h = HistoricalComparer(root).compare(cands[0], "p0", st, "c1")
            dec = self._decide([h])
            self.assertIsNotNone(dec.historical)
            self.assertTrue(dec.historical["executed"])
            self.assertTrue(dec.historical["complete"])
            self.assertEqual(dec.historical["n_comparable"], 1)
            self.assertAlmostEqual(dec.historical["metrics"]["latency_p95_ms"], 10.0)
            self.assertTrue(dec.historical["limitations"])

    def test_summary_none_when_not_run(self):
        dec = self._decide([])
        self.assertIsNone(dec.historical)

    def test_roundtrip_and_old_records_load(self):
        old = {"action": "retain", "current_policy_id": "plan@100",
               "confidence": {}, "reason": "x", "record_id": "old1",
               "recorded_at": NOW, "schema": 1}
        back = DecisionResult.from_dict(old)
        self.assertIsNone(back.historical)
        self.assertTrue(back.is_valid())

        dec = self._decide([HistoricalResult(
            candidate_id="c", baseline_policy_id="p",
            metrics={"latency_p95_ms": 12.0},
            limitations=("historical only",), complete=True,
            n_comparable=360, recorded_at=NOW)])
        rt = DecisionResult.from_dict(dec.to_dict())
        self.assertEqual(rt.historical, dec.historical)
        self.assertEqual(rt.historical["n_comparable"], 360)

    def test_incomplete_honesty(self):
        h = HistoricalResult(candidate_id="c", baseline_policy_id="p",
                             metrics={}, limitations=("no history",),
                             complete=False, n_comparable=0,
                             recorded_at=NOW)
        dec = self._decide([h])
        self.assertFalse(dec.historical["complete"])
        self.assertEqual(dec.historical["n_comparable"], 0)


if __name__ == "__main__":
    unittest.main()
