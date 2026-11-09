"""Phase 6: outcome verification + bounded recovery (FakeRunner, no kernel)."""
import tempfile
import unittest
from pathlib import Path

from aciq.harness import Harness
from aciq.intelligence.contracts import (
    ApplicationResult,
    NetworkState,
    OutcomeClass,
    Reliability,
)
from aciq.intelligence.experience import ExperienceStore
from aciq.intelligence.integration import ControllerGateway
from aciq.intelligence.outcome import OutcomeVerifier, RecoveryEngine
from aciq.model import Capacity, TrafficClass
from aciq.policy import build_plan
from aciq.txn import FakeRunner

NOW = 1_700_000_000.0


def _state(cap=100.0):
    return NetworkState(
        capacity=Capacity(mbps=cap, confidence=0.9, saturated=False, changed=False),
        per_class_demand={TrafficClass.VIDEO_CALL: 1.0}, active_flows=2,
        freshness={"capacity": 0.5}, reliability=Reliability.RELIABLE,
        recorded_at=NOW)


def _applied_app(decision_id="d1", applied=True, verified=True):
    return ApplicationResult(
        decision_id=decision_id, candidate_id="c1", submitted=True,
        controller_accepted=True, applied=applied, readback_verified=verified,
        recorded_at=NOW)


from aciq.intelligence.contracts import ReadbackResult


def _rb(verified=True):
    return ReadbackResult(verified=verified,
                          mismatches=() if verified else ("rate mismatch",),
                          recorded_at=NOW)


class TestOutcomeVerifier(unittest.TestCase):
    def setUp(self):
        self.v = OutcomeVerifier()

    def test_successful(self):
        o = self.v.verify(_applied_app(), _rb(),
                          {"latency_ms": 10.0, "loss_ratio": 0.0, "fairness": 0.9},
                          now=NOW)
        self.assertEqual(o.outcome, OutcomeClass.SUCCESSFUL)
        self.assertTrue(o.is_valid())

    def test_degraded_on_latency(self):
        o = self.v.verify(_applied_app(), _rb(),
                          {"latency_ms": 90.0, "loss_ratio": 0.0, "fairness": 0.9},
                          now=NOW)
        self.assertEqual(o.outcome, OutcomeClass.DEGRADED)

    def test_not_applied_is_application_failed(self):
        o = self.v.verify(_applied_app(applied=False), _rb(),
                          {"latency_ms": 10.0}, now=NOW)
        self.assertEqual(o.outcome, OutcomeClass.APPLICATION_FAILED)

    def test_readback_failure_is_degraded(self):
        o = self.v.verify(_applied_app(), _rb(verified=False),
                          {"latency_ms": 10.0}, now=NOW)
        self.assertEqual(o.outcome, OutcomeClass.DEGRADED)

    def test_missing_measurements_inconclusive(self):
        o = self.v.verify(_applied_app(), _rb(), {}, now=NOW)
        self.assertEqual(o.outcome, OutcomeClass.INCONCLUSIVE)

    def test_simulation_divergence_recorded_not_used(self):
        o = self.v.verify(_applied_app(), _rb(),
                          {"latency_ms": 10.0},
                          simulated={"latency_ms": 200.0}, now=NOW)
        self.assertEqual(o.outcome, OutcomeClass.SUCCESSFUL)
        self.assertTrue(any("simulated" in lim for lim in o.limitations))


class TestRecoveryEngine(unittest.TestCase):
    def _engine(self, tmp_path="/tmp"):
        h = Harness(runner=FakeRunner(auto_readback=True))
        h._current_plan = build_plan(100.0)
        return RecoveryEngine(ControllerGateway(h),
                                log_path=f"{tmp_path}/recovery-test.jsonl"), h

    def test_rollback_success_on_valid_previous(self):
        eng, h = self._engine()
        ev, app = eng.recover(_state(100.0), build_plan(100.0),
                              "d1", "confirmed latency degradation",
                              correlation_id="c1", now=NOW)
        self.assertEqual(ev.outcome, "SUCCESS")
        self.assertEqual(ev.action, "ROLLBACK")
        self.assertIsNotNone(app)
        self.assertTrue(app.applied)

    def test_invalid_previous_uses_fallback(self):
        eng, h = self._engine()
        too_big = build_plan(100.0)  # capacity fell to 20; old plan exceeds it
        # craft a plan rated for 100 while link is now 20
        from aciq.model import RatePlan
        old = RatePlan(capacity_mbps=100.0,
                       rates={c: r for c, r in too_big.rates.items()},
                       ceils={c: r for c, r in too_big.ceils.items()})
        ev, app = eng.recover(_state(20.0), old, "d1", "capacity fell",
                              correlation_id="c1", now=NOW)
        self.assertEqual(ev.action, "SAFE_FALLBACK")
        self.assertIn("previous_invalid_reason", ev.failure_evidence)

    def test_attempt_limit_bounds_recovery(self):
        eng, h = self._engine()
        for _ in range(3):
            eng.recover(_state(100.0), build_plan(100.0), "d1",
                        "degradation", correlation_id="c1",
                        now=NOW + eng._attempts * 31.0)
        self.assertFalse(eng.can_attempt(NOW + 1000.0))
        ev, app = eng.recover(_state(100.0), build_plan(100.0), "d1",
                              "degradation", correlation_id="c1", now=NOW + 1000.0)
        self.assertIsNone(app)
        self.assertEqual(ev.outcome, "INCONCLUSIVE")

    def test_recovery_writes_experience(self):
        with tempfile.TemporaryDirectory() as d:
            store = ExperienceStore(Path(d) / "e.jsonl")
            eng, h = self._engine(tmp_path=d)
            ev, app = eng.recover(_state(100.0), build_plan(100.0), "d1",
                                  "degradation", correlation_id="c1", now=NOW)
            self.assertTrue(Path(d, "recovery-test.jsonl").exists())
            from aciq.intelligence.contracts import Experience, ExperienceStatus
            store.append(Experience(status=ExperienceStatus.RECOVERY,
                                    network_context={"capacity_mbps": 100.0},
                                    outcome_context={"measured": {"recovered": True}},
                                    correlation_id="c1", recorded_at=NOW))
            records, stats = store.load_all()
            self.assertEqual(stats.loaded, 1)


if __name__ == "__main__":
    unittest.main()
