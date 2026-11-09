"""Regression tests for the two audit defects (historical field + similarity).

Defect 1: HistoricalComparer read `capacity_mbps` (never exists in
result.json) -> always incomplete. Fixed to `link_end_mbps` (true link rate)
with `estimator_mbps` fallback; metrics read from real workload reports.

Defect 2: experiment loop unwrapped RetrievedExperience before decide(),
discarding the similarity score -> confidence 0.0 -> forced DEFER whenever
retrieval hit. Fixed: full RetrievedExperience objects are passed.
"""
import json
import tempfile
import unittest
from pathlib import Path

from aciq.intelligence.candidates import CandidateGenerator
from aciq.intelligence.contracts import (
    DecisionAction,
    Experience,
    ExperienceStatus,
    NetworkState,
    Reliability,
)
from aciq.intelligence.decide import DecisionEngine
from aciq.intelligence.evaluator import PolicyEvaluator
from aciq.intelligence.experience import RetrievedExperience
from aciq.intelligence.historical import HistoricalComparer
from aciq.intelligence.predictor import DegradationPredictor
from aciq.intelligence.validate import AcceptanceGate
from aciq.model import Capacity, TrafficClass
from aciq.policy import build_plan

NOW = 1_700_000_000.0


def _capacity(mbps=100.0):
    return Capacity(mbps=mbps, confidence=0.9, saturated=False, changed=False)


def _state(**kw):
    base = dict(capacity=_capacity(), per_class_demand={TrafficClass.VIDEO_CALL: 1.0},
                active_flows=2, latency_ms=5.0, jitter_ms=1.0, loss_ratio=0.0,
                freshness={"capacity": 0.5}, reliability=Reliability.RELIABLE,
                recorded_at=NOW)
    base.update(kw)
    return NetworkState(**base)


def _write_run(root: Path, name: str, link_end: float, p95: float, bulk: float):
    d = root / name
    d.mkdir(parents=True)
    (d / "result.json").write_text(json.dumps({
        "scenario": name, "system": "aciq", "link_start_mbps": 100.0,
        "link_end_mbps": link_end, "estimator_mbps": link_end - 25.0}))
    (d / "call.json").write_text(json.dumps(
        {"p95": p95, "jitter_ms": 1.0, "loss_ratio": 0.0}))
    (d / "bulk.json").write_text(json.dumps({"sender_mbps": bulk}))


class TestHistoricalPositive(unittest.TestCase):
    def test_real_records_complete(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            _write_run(root, "s1__seed1", 100.0, 10.0, 80.0)
            _write_run(root, "s1__seed2", 100.0, 14.0, 84.0)
            _write_run(root, "s2__seed1", 20.0, 90.0, 15.0)
            st = _state()
            cands = CandidateGenerator().generate(st, build_plan(100.0), "p0",
                                                  correlation_id="c1")
            h = HistoricalComparer(root).compare(cands[0], "p0", st, "c1")
            self.assertTrue(h.complete)
            self.assertAlmostEqual(h.metrics["bulk_mbps"], 82.0, places=1)
            self.assertAlmostEqual(h.metrics["latency_p95_ms"], 12.0, places=1)
            self.assertIn(cands[0].record_id, h.ranking)
            self.assertTrue(h.limitations)  # historical-only caveat always stated

    def test_estimator_only_fallback(self):
        # no link_end (older artefacts): estimator used, never fabricated
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run = root / "legacy__seed1"
            run.mkdir()
            (run / "result.json").write_text(json.dumps(
                {"link_start_mbps": 100.0, "estimator_mbps": 95.0}))
            st = _state()
            cands = CandidateGenerator().generate(st, build_plan(100.0), "p0",
                                                  correlation_id="c1")
            h = HistoricalComparer(root).compare(cands[0], "p0", st, "c1")
            self.assertTrue(h.complete)  # estimator fallback, honest about it
            self.assertIn("historical only", h.limitations[0])

    def test_no_capacity_anywhere_incomplete(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            run = root / "broken__seed1"
            run.mkdir()
            (run / "result.json").write_text(json.dumps({"scenario": "x"}))
            st = _state()
            cands = CandidateGenerator().generate(st, build_plan(100.0), "p0",
                                                  correlation_id="c1")
            h = HistoricalComparer(root).compare(cands[0], "p0", st, "c1")
            self.assertFalse(h.complete)


class TestSimilarityReachesDecision(unittest.TestCase):
    def test_similarity_score_survives_to_decide(self):
        st = _state(latency_ms=90.0)  # degraded-looking: needs SELECT/RECOVER path
        ev = PolicyEvaluator().evaluate(st, build_plan(100.0), "c1", now=NOW)
        pred = DegradationPredictor().predict(
            [{"latency_ms": 5.0 + i * 3.0, "backlog_bytes": 100.0,
              "capacity_mbps": 100.0, "per_class": {"x": 1}} for i in range(5)],
            st, "c1")
        cands = CandidateGenerator().generate(st, build_plan(100.0), "plan@100",
                                              correlation_id="c1")
        gate = AcceptanceGate()
        vals = [gate.validate(c, st, build_plan(100.0)) for c in cands]
        exp = Experience(status=ExperienceStatus.SUCCESS,
                         network_context={"capacity_mbps": 100.0},
                         outcome_context={"measured": {"latency_ms": 5.0}},
                         recorded_at=NOW)
        retrieved = [RetrievedExperience(exp, 1.0, "test: identical context")]
        dec = DecisionEngine().decide(st, ev, pred, cands, vals, [], retrieved,
                                      "c1", now=NOW)
        self.assertTrue(dec.is_valid())
        # the similarity the store computed (1.0) is the similarity decide saw
        self.assertAlmostEqual(dec.confidence["similarity"], 1.0)
        # and it does not force a DEFER: a genuine change path stays open
        self.assertNotEqual(dec.action, DecisionAction.DEFER)

    def test_zero_similarity_still_deferrable(self):
        # genuinely unrelated history must still be able to defer
        st = _state(latency_ms=90.0, reliability=Reliability.DEGRADED)
        ev = PolicyEvaluator().evaluate(st, build_plan(100.0), "c1", now=NOW)
        cands = CandidateGenerator().generate(st, build_plan(100.0), "plan@100",
                                              correlation_id="c1")
        gate = AcceptanceGate()
        vals = [gate.validate(c, st, build_plan(100.0)) for c in cands]
        exp = Experience(status=ExperienceStatus.SUCCESS,
                         network_context={"capacity_mbps": 5.0},
                         outcome_context={"measured": {"latency_ms": 5.0}},
                         recorded_at=NOW)
        retrieved = [RetrievedExperience(exp, 0.09, "poor match")]
        dec = DecisionEngine().decide(st, ev, None, cands, vals, [], retrieved,
                                      "c1", now=NOW)
        self.assertAlmostEqual(dec.confidence["similarity"], 0.09)


if __name__ == "__main__":
    unittest.main()
