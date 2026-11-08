"""Phase 2: intelligence contract validation (pure types, no I/O)."""
import unittest

from aciq.intelligence import (
    SCHEMA_VERSION,
    ApplicationResult,
    Candidate,
    DecisionAction,
    DecisionResult,
    Experience,
    ExperienceStatus,
    HistoricalResult,
    NetworkState,
    Outcome,
    OutcomeClass,
    PolicyEvaluation,
    Prediction,
    PredictionStatus,
    ReadbackResult,
    RecoveryEvent,
    Reliability,
    ValidationResult,
)
from aciq.model import Capacity, RatePlan, TrafficClass
from aciq.policy import build_plan

NOW = 1_700_000_000.0


def _capacity():
    return Capacity(mbps=100.0, confidence=0.9, saturated=False, changed=False)


def _state():
    return NetworkState(
        capacity=_capacity(),
        per_class_demand={TrafficClass.VIDEO_CALL: 1.0},
        active_flows=3,
        latency_ms=5.0, jitter_ms=1.0, loss_ratio=0.0,
        freshness={"capacity": 0.5}, missing=(),
        reliability=Reliability.RELIABLE,
        recorded_at=NOW,
    )


class TestStateContract(unittest.TestCase):
    def test_valid_state(self):
        s = _state()
        self.assertTrue(s.is_valid())

    def test_missing_never_zero(self):
        s = NetworkState(capacity=_capacity(), recorded_at=NOW,
                         missing=("latency_ms",), reliability=Reliability.UNKNOWN)
        self.assertTrue(s.is_valid())

    def test_invalid_loss_caught(self):
        s = NetworkState(capacity=_capacity(), loss_ratio=9.0, recorded_at=NOW)
        self.assertFalse(s.is_valid())
        with self.assertRaises(ValueError):
            s.validate()

    def test_roundtrip(self):
        s = _state()
        d = s.to_dict()
        back = NetworkState.from_dict(d)
        self.assertEqual(back.capacity, s.capacity)
        self.assertTrue(back.is_valid())


class TestEvaluationPrediction(unittest.TestCase):
    def test_evaluation_requires_policy_and_correlation(self):
        e = PolicyEvaluation(current_policy_id="p1", health="healthy",
                             correlation_id="c1", recorded_at=NOW)
        self.assertTrue(e.is_valid())
        bad = PolicyEvaluation(current_policy_id="", health="healthy",
                               correlation_id="", recorded_at=NOW)
        self.assertFalse(bad.is_valid())

    def test_high_prediction_requires_confidence(self):
        p = Prediction(horizon_s=30.0, status=PredictionStatus.HIGH,
                       confidence=None, correlation_id="c1", recorded_at=NOW)
        self.assertFalse(p.is_valid())
        ok = Prediction(horizon_s=30.0, status=PredictionStatus.HIGH,
                        confidence=0.8, correlation_id="c1", recorded_at=NOW)
        self.assertTrue(ok.is_valid())

    def test_prediction_bad_horizon(self):
        p = Prediction(horizon_s=0.0, status=PredictionStatus.NONE,
                       confidence=None, recorded_at=NOW)
        self.assertFalse(p.is_valid())


class TestExperienceStatusSeparation(unittest.TestCase):
    def test_success_requires_measured(self):
        bad = Experience(status=ExperienceStatus.SUCCESS,
                         outcome_context={}, recorded_at=NOW)
        self.assertFalse(bad.is_valid())
        ok = Experience(status=ExperienceStatus.SUCCESS,
                        outcome_context={"measured": {"latency_ms": 5.0}},
                        recorded_at=NOW)
        self.assertTrue(ok.is_valid())

    def test_simulation_only_must_not_carry_measured(self):
        bad = Experience(status=ExperienceStatus.SIMULATION_ONLY,
                         outcome_context={"measured": {"latency_ms": 5.0}},
                         recorded_at=NOW)
        self.assertFalse(bad.is_valid())

    def test_rejected_needs_no_measured(self):
        ok = Experience(status=ExperienceStatus.REJECTED,
                        outcome_context={"reason": "capacity"}, recorded_at=NOW)
        self.assertTrue(ok.is_valid())

    def test_roundtrip(self):
        ok = Experience(status=ExperienceStatus.FAILED,
                        outcome_context={"measured": {"loss_ratio": 0.2}},
                        correlation_id="c1", recorded_at=NOW)
        back = Experience.from_dict(ok.to_dict())
        self.assertEqual(back.status, ExperienceStatus.FAILED)
        self.assertTrue(back.is_valid())


class TestCandidateUsesRealRatePlan(unittest.TestCase):
    def test_build_plan_output_is_valid_candidate(self):
        plan = build_plan(100.0)
        c = Candidate(plan=plan, parent_policy_id="p0", reason="test",
                      correlation_id="c1", recorded_at=NOW)
        self.assertTrue(c.is_valid())

    def test_over_capacity_plan_rejected(self):
        plan = RatePlan(capacity_mbps=20.0,
                        rates={TrafficClass.BULK_DOWNLOAD: 50.0},
                        ceils={TrafficClass.BULK_DOWNLOAD: 50.0})
        c = Candidate(plan=plan, parent_policy_id="p0", reason="test",
                      recorded_at=NOW)
        self.assertFalse(c.is_valid())

    def test_ceil_above_capacity_rejected(self):
        plan = RatePlan(capacity_mbps=20.0,
                        rates={TrafficClass.VIDEO_CALL: 5.0},
                        ceils={TrafficClass.VIDEO_CALL: 99.0})
        c = Candidate(plan=plan, parent_policy_id="p0", reason="test",
                      recorded_at=NOW)
        self.assertFalse(c.is_valid())

    def test_roundtrip_preserves_rates(self):
        plan = build_plan(50.0)
        c = Candidate(plan=plan, parent_policy_id="p0", reason="test",
                      recorded_at=NOW)
        back = Candidate.from_dict(c.to_dict())
        self.assertEqual(back.plan.rates, plan.rates)
        self.assertTrue(back.is_valid())


class TestGateDecision(unittest.TestCase):
    def test_accepted_must_not_carry_failed_constraints(self):
        v = ValidationResult(candidate_id="c", accepted=True,
                             failed_constraints=("capacity",), recorded_at=NOW)
        self.assertFalse(v.is_valid())

    def test_rejected_must_state_reason(self):
        v = ValidationResult(candidate_id="c", accepted=False, recorded_at=NOW)
        self.assertFalse(v.is_valid())

    def test_select_requires_candidate(self):
        d = DecisionResult(action=DecisionAction.SELECT, current_policy_id="p0",
                           reason="x", recorded_at=NOW)
        self.assertFalse(d.is_valid())

    def test_retain_must_not_carry_candidate(self):
        d = DecisionResult(action=DecisionAction.RETAIN, current_policy_id="p0",
                           selected_candidate_id="c1", reason="x", recorded_at=NOW)
        self.assertFalse(d.is_valid())

    def test_decision_confidence_range(self):
        d = DecisionResult(action=DecisionAction.RETAIN, current_policy_id="p0",
                           confidence={"prediction": 9.0}, reason="x", recorded_at=NOW)
        self.assertFalse(d.is_valid())


class TestApplicationOutcomeRecovery(unittest.TestCase):
    def test_applied_implies_accepted(self):
        a = ApplicationResult(decision_id="d1", candidate_id="c1", submitted=True,
                              controller_accepted=False, applied=True,
                              readback_verified=False, recorded_at=NOW)
        self.assertFalse(a.is_valid())

    def test_readback_verified_implies_applied(self):
        a = ApplicationResult(decision_id="d1", candidate_id="c1", submitted=True,
                              controller_accepted=True, applied=False,
                              readback_verified=True, recorded_at=NOW)
        self.assertFalse(a.is_valid())

    def test_failed_readback_must_name_mismatches(self):
        r = ReadbackResult(verified=False, recorded_at=NOW)
        self.assertFalse(r.is_valid())

    def test_successful_outcome_requires_measurements(self):
        o = Outcome(decision_id="d1", applied_policy_id="p1",
                    outcome=OutcomeClass.SUCCESSFUL, recorded_at=NOW)
        self.assertFalse(o.is_valid())

    def test_recovery_bad_action(self):
        r = RecoveryEvent(trigger="t", previous_policy_id="p0", action="REBOOT",
                          outcome="SUCCESS", recorded_at=NOW)
        self.assertFalse(r.is_valid())


class TestHistoricalIsNeverMeasured(unittest.TestCase):
    def test_limitations_required(self):
        h = HistoricalResult(candidate_id="c", baseline_policy_id="p0",
                             metrics={"latency_ms": 5.0}, recorded_at=NOW)
        self.assertFalse(h.is_valid())

    def test_with_limitations_valid(self):
        h = HistoricalResult(candidate_id="c", baseline_policy_id="p0",
                             metrics={"latency_ms": 5.0},
                             limitations=("historical only, not live",),
                             recorded_at=NOW)
        self.assertTrue(h.is_valid())


if __name__ == "__main__":
    unittest.main()
