"""Phase 4: six intelligence modules (pure, no kernel)."""
import tempfile
import unittest
from pathlib import Path

from aciq.intelligence.candidates import CandidateGenerator
from aciq.intelligence.config import IntelligenceConfig
from aciq.intelligence.contracts import (
    DecisionAction,
    Experience,
    ExperienceStatus,
    HistoricalResult,
    NetworkState,
    PolicyHealth,
    Prediction,
    PredictionStatus,
    Reliability,
    ValidationResult,
)
from aciq.intelligence.decide import DecisionEngine
from aciq.intelligence.evaluator import PolicyEvaluator
from aciq.intelligence.experience import ExperienceStore
from aciq.intelligence.historical import HistoricalComparer
from aciq.intelligence.predictor import DegradationPredictor
from aciq.intelligence.state import NetworkStateObserver
from aciq.intelligence.validate import AcceptanceGate
from aciq.model import Capacity, TrafficClass
from aciq.policy import build_plan

NOW = 1_700_000_000.0


def _capacity(mbps=100.0, conf=0.9):
    return Capacity(mbps=mbps, confidence=conf, saturated=False, changed=False)


def _state(**kw):
    base = dict(capacity=_capacity(), per_class_demand={TrafficClass.VIDEO_CALL: 1.0},
                active_flows=2, latency_ms=5.0, jitter_ms=1.0, loss_ratio=0.0,
                freshness={"capacity": 0.5}, reliability=Reliability.RELIABLE,
                recorded_at=NOW)
    base.update(kw)
    return NetworkState(**base)


def _hist(capacity=100.0, n=5):
    return [{"latency_ms": 5.0, "backlog_bytes": 100.0,
             "capacity_mbps": capacity, "per_class": {"x": 1}} for _ in range(n)]


class TestStateObserver(unittest.TestCase):
    def test_full_sample_reliable(self):
        obs = NetworkStateObserver(_capacity(), now_s=NOW, freshness_limit_s=5.0)
        sample = {"t": NOW, "per_class": {"video_call_voice": {"goodput_mbps": 0.1}},
                  "latency_ms": 5.0, "jitter_ms": 1.0, "loss_ratio": 0.0,
                  "throughput_mbps": 50.0, "bottleneck_backlog_bytes": 100,
                  "verdicts": {"f": {"confidence": 0.9}}}
        st = obs.observe(sample, per_class_demand={TrafficClass.VIDEO_CALL: 1.0})
        self.assertTrue(st.is_valid())
        self.assertEqual(st.reliability, Reliability.RELIABLE)
        self.assertLessEqual(len(st.missing), 1)

    def test_empty_sample_missing_not_zero(self):
        obs = NetworkStateObserver(_capacity(), now_s=NOW)
        st = obs.observe({})
        self.assertIn("latency_ms", st.missing)
        self.assertIsNone(st.latency_ms)

    def test_stale_capacity_unknown(self):
        obs = NetworkStateObserver(_capacity(), now_s=NOW + 100.0)
        st = obs.observe({"t": NOW, "per_class": {}}, per_class_demand={})
        self.assertEqual(st.reliability, Reliability.UNKNOWN)


class TestEvaluator(unittest.TestCase):
    def setUp(self):
        self.ev = PolicyEvaluator()

    def test_healthy(self):
        ev = self.ev.evaluate(_state(), build_plan(100.0), "c1", now=NOW)
        self.assertEqual(ev.health, PolicyHealth.HEALTHY)
        self.assertTrue(ev.is_valid())

    def test_degraded_latency(self):
        ev = self.ev.evaluate(_state(latency_ms=90.0), build_plan(100.0), "c1", now=NOW)
        self.assertIn(ev.health, (PolicyHealth.MONITOR, PolicyHealth.CONFIRMED_DEGRADATION))

    def test_over_capacity_plan_invalid(self):
        from aciq.model import RatePlan
        plan = RatePlan(capacity_mbps=20.0,
                        rates={TrafficClass.BULK_DOWNLOAD: 50.0},
                        ceils={TrafficClass.BULK_DOWNLOAD: 20.0})
        ev = self.ev.evaluate(_state(capacity=_capacity(20.0)), plan, "c1", now=NOW)
        self.assertEqual(ev.health, PolicyHealth.INVALID)

    def test_no_capacity_confidence_unknown(self):
        ev = self.ev.evaluate(_state(capacity=_capacity(100.0, 0.0)),
                              build_plan(100.0), "c1", now=NOW)
        self.assertEqual(ev.health, PolicyHealth.UNKNOWN)


class TestPredictor(unittest.TestCase):
    def setUp(self):
        self.pred = DegradationPredictor()

    def test_short_history_uncertain(self):
        p = self.pred.predict([{"latency_ms": 1.0}], _state(), "c1")
        self.assertEqual(p.status, PredictionStatus.UNCERTAIN)
        self.assertIsNone(p.confidence)

    def test_rising_latency_potential(self):
        h = [{"latency_ms": 5.0 + i * 3.0, "backlog_bytes": 1000.0,
              "capacity_mbps": 100.0, "per_class": {"x": 1}} for i in range(5)]
        p = self.pred.predict(h, _state(), "c1")
        self.assertIn(p.status, (PredictionStatus.POTENTIAL, PredictionStatus.HIGH))
        self.assertTrue(p.evidence)

    def test_stable_history_none(self):
        h = [{"latency_ms": 5.0, "backlog_bytes": 100.0,
              "capacity_mbps": 100.0, "per_class": {"x": 1}} for _ in range(5)]
        p = self.pred.predict(h, _state(), "c1")
        self.assertEqual(p.status, PredictionStatus.NONE)

    def test_falling_capacity_evidence(self):
        h = [{"latency_ms": 5.0, "backlog_bytes": 100.0,
              "capacity_mbps": 100.0 - i * 10.0, "per_class": {"x": 1}} for i in range(5)]
        p = self.pred.predict(h, _state(), "c1")
        self.assertTrue(any("capacity" in e for e in p.evidence))


class TestCandidatesAndGate(unittest.TestCase):
    def setUp(self):
        self.gen = CandidateGenerator()
        self.gate = AcceptanceGate()

    def test_bounded_candidates_from_real_build_plan(self):
        cands = self.gen.generate(_state(), build_plan(100.0), "p0", correlation_id="c1")
        self.assertGreaterEqual(len(cands), 2)
        self.assertLessEqual(len(cands), 5)
        for c in cands:
            self.assertTrue(c.is_valid())
            self.assertLessEqual(c.plan.total(), c.plan.capacity_mbps + 1e-9)

    def test_gate_accepts_valid_candidate(self):
        cands = self.gen.generate(_state(), build_plan(100.0), "p0", correlation_id="c1")
        v = self.gate.validate(cands[0], _state())
        self.assertTrue(v.is_valid())
        self.assertTrue(v.accepted, v.failed_constraints)

    def test_gate_rejects_over_capacity(self):
        from aciq.model import RatePlan
        from aciq.intelligence.contracts import Candidate
        plan = RatePlan(capacity_mbps=20.0,
                        rates={TrafficClass.BULK_DOWNLOAD: 50.0},
                        ceils={TrafficClass.BULK_DOWNLOAD: 50.0})
        c = Candidate(plan=plan, parent_policy_id="p0", reason="test",
                      correlation_id="c1", recorded_at=NOW)
        # candidate itself is invalid (over capacity) — gate must also reject
        self.assertFalse(c.is_valid())

    def test_gate_rejects_starved_bulk(self):
        from aciq.model import RatePlan
        from aciq.intelligence.contracts import Candidate
        plan = RatePlan(capacity_mbps=100.0,
                        rates={TrafficClass.VIDEO_CALL: 95.0,
                               TrafficClass.BULK_DOWNLOAD: 0.0},
                        ceils={TrafficClass.VIDEO_CALL: 100.0,
                               TrafficClass.BULK_DOWNLOAD: 0.0})
        c = Candidate(plan=plan, parent_policy_id="p0", reason="test",
                      correlation_id="c1", recorded_at=NOW)
        v = self.gate.validate(c, _state())
        self.assertFalse(v.accepted)
        self.assertTrue(any("bulk" in f for f in v.failed_constraints))

    def test_unknown_state_rejected(self):
        cands = self.gen.generate(_state(), build_plan(100.0), "p0", correlation_id="c1")
        st = _state(reliability=Reliability.UNKNOWN)
        v = self.gate.validate(cands[0], st)
        self.assertFalse(v.accepted)


class TestHistoricalAndDecision(unittest.TestCase):
    def test_historical_no_history(self):
        with tempfile.TemporaryDirectory() as d:
            comp = HistoricalComparer(Path(d))
            cands = CandidateGenerator().generate(_state(), build_plan(100.0), "p0",
                                                  correlation_id="c1")
            h = comp.compare(cands[0], "p0", _state(), "c1")
            self.assertFalse(h.complete)
            self.assertTrue(h.limitations)

    def test_decide_retain_when_healthy(self):
        ev = PolicyEvaluator().evaluate(_state(), build_plan(100.0), "c1", now=NOW)
        pred = DegradationPredictor().predict(_hist(), _state(), "c1")
        cands = CandidateGenerator().generate(_state(), build_plan(100.0), "p0",
                                              correlation_id="c1")
        gate = AcceptanceGate()
        vals = [gate.validate(c, _state()) for c in cands]
        dec = DecisionEngine().decide(_state(), ev, pred, cands, vals, [], [], "c1", now=NOW)
        self.assertTrue(dec.is_valid())
        self.assertEqual(dec.action, DecisionAction.RETAIN)

    def test_decide_select_when_degraded(self):
        ev = PolicyEvaluator().evaluate(_state(latency_ms=90.0), build_plan(100.0),
                                        "c1", now=NOW)
        h = [{"latency_ms": 5.0 + i * 3.0, "capacity_mbps": 100.0,
              "per_class": {"x": 1}} for i in range(5)]
        pred = DegradationPredictor().predict(h, _state(), "c1")
        cands = CandidateGenerator().generate(_state(), build_plan(100.0), "p0",
                                              correlation_id="c1")
        gate = AcceptanceGate()
        vals = [gate.validate(c, _state()) for c in cands]
        dec = DecisionEngine().decide(_state(), ev, pred, cands, vals, [], [], "c1", now=NOW)
        self.assertTrue(dec.is_valid())
        # confirmed degradation + reliable evidence => RECOVER (Module 8 D)
        self.assertEqual(dec.action, DecisionAction.RECOVER)

    def test_decide_defer_on_unknown_state(self):
        ev = PolicyEvaluator().evaluate(
            _state(reliability=Reliability.UNKNOWN), build_plan(100.0), "c1", now=NOW)
        cands = CandidateGenerator().generate(_state(), build_plan(100.0), "p0",
                                              correlation_id="c1")
        gate = AcceptanceGate()
        vals = [gate.validate(c, _state(reliability=Reliability.UNKNOWN)) for c in cands]
        dec = DecisionEngine().decide(_state(reliability=Reliability.UNKNOWN),
                                      ev, None, cands, vals, [], [], "c1", now=NOW)
        self.assertTrue(dec.is_valid())

    def test_experience_feeds_decision(self):
        with tempfile.TemporaryDirectory() as d:
            store = ExperienceStore(Path(d) / "e.jsonl")
            store.append(Experience(
                status=ExperienceStatus.SUCCESS,
                network_context={"capacity_mbps": 100.0, "latency_ms": 5.0,
                                 "jitter_ms": 1.0, "loss_ratio": 0.0,
                                 "demand": {"video_call_voice": 1.0}},
                outcome_context={"measured": {"latency_ms": 5.0}},
                recorded_at=NOW))
            got = store.retrieve({"capacity_mbps": 100.0, "latency_ms": 5.0,
                                  "jitter_ms": 1.0, "loss_ratio": 0.0,
                                  "demand": {"video_call_voice": 1.0}})
            self.assertTrue(got)


if __name__ == "__main__":
    unittest.main()
