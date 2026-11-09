"""Phase 5: controller integration gateway (FakeRunner, no kernel)."""
import unittest

from aciq.harness import CapacityMode, Harness, SystemSpec
from aciq.intelligence.candidates import CandidateGenerator
from aciq.intelligence.config import IntelligenceConfig
from aciq.intelligence.contracts import (
    DecisionAction,
    DecisionResult,
    NetworkState,
    Reliability,
)
from aciq.intelligence.integration import ControllerGateway
from aciq.intelligence.validate import AcceptanceGate
from aciq.model import Capacity, TrafficClass
from aciq.policy import build_plan
from aciq.txn import FakeRunner

NOW = 1_700_000_000.0


def _harness():
    return Harness(runner=FakeRunner(auto_readback=True))


def _state(cap=100.0, recorded=NOW, reliability=Reliability.RELIABLE):
    return NetworkState(
        capacity=Capacity(mbps=cap, confidence=0.9, saturated=False, changed=False),
        per_class_demand={TrafficClass.VIDEO_CALL: 1.0}, active_flows=2,
        freshness={"capacity": 0.5}, reliability=reliability,
        recorded_at=recorded)


def _approved():
    h = _harness()
    h._current_plan = build_plan(100.0)
    state = _state()
    cands = CandidateGenerator().generate(state, h._current_plan, "plan@100",
                                          correlation_id="c1")
    v = AcceptanceGate().validate(cands[0], state, h._current_plan)
    dec = DecisionResult(action=DecisionAction.SELECT, current_policy_id="plan@100",
                         selected_candidate_id=cands[0].record_id, reason="test",
                         correlation_id="c1", recorded_at=NOW)
    return h, state, cands[0], v, dec


class TestGateway(unittest.TestCase):
    def test_submit_applies_and_readback_verifies(self):
        h, state, cand, v, dec = _approved()
        gw = ControllerGateway(h)
        app, rb = gw.submit(dec, cand, v, state, now=NOW)
        self.assertTrue(app.applied)
        self.assertTrue(app.readback_verified)
        self.assertTrue(rb.verified)

    def test_gate_rejected_never_reaches_kernel(self):
        h, state, cand, v, dec = _approved()
        from aciq.intelligence.contracts import ValidationResult
        bad = ValidationResult(candidate_id=cand.record_id, accepted=False,
                               failed_constraints=("capacity",),
                               correlation_id="c1", recorded_at=NOW)
        app, rb = ControllerGateway(h).submit(dec, cand, bad, state, now=NOW)
        self.assertFalse(app.submitted)
        self.assertFalse(app.applied)

    def test_stale_state_refused(self):
        h, state, cand, v, dec = _approved()
        app, rb = ControllerGateway(h).submit(dec, cand, v, state, now=NOW + 600.0)
        self.assertFalse(app.applied)
        self.assertIn("stale", app.failure)

    def test_superseded_parent_refused(self):
        h, state, cand, v, dec = _approved()
        # controller moved on to a different plan since evaluation
        h._current_plan = build_plan(50.0)
        app, rb = ControllerGateway(h).submit(dec, cand, v, state, now=NOW)
        self.assertFalse(app.applied)
        self.assertIn("superseded", app.failure)

    def test_failed_apply_not_reported_as_success(self):
        h, state, cand, v, dec = _approved()
        # the real S5 injection path: one tc apply fails transiently, txn
        # rolls back to last-good => candidate must NOT read as applied.
        h.txn.inject_failed_apply_once()
        app, rb = ControllerGateway(h).submit(dec, cand, v, state, now=NOW)
        self.assertFalse(app.applied or app.readback_verified)
        self.assertIn("rolled back", (app.failure or ""))

    def test_experiment_hook_never_crashes_loop(self):
        from aciq.experiment import DryLauncher, ExperimentRunner
        import tempfile
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            class NullSource:
                def snapshot(self):
                    import time as _t
                    from aciq.metrics import CounterSnapshot
                    return CounterSnapshot(t=_t.monotonic(), by_class={})

            runner = ExperimentRunner(
                launcher=DryLauncher(),
                harness=Harness(runner=FakeRunner(auto_readback=True)),
                results_dir=Path(d), real_time=False, source=NullSource())
            res = runner.run("s1_iso_during_call", SystemSpec.ACIQ,
                             CapacityMode.ADAPTIVE, 42, intelligence=True)
            self.assertIsNotNone(res)
            summary = getattr(runner, "_last_intel_summary", None)
            self.assertTrue(summary and "action" in summary)

    def test_intelligence_flag_default_off(self):
        from aciq.experiment import ExperimentRunner
        import inspect
        sig = inspect.signature(ExperimentRunner.run)
        self.assertIn("intelligence", sig.parameters)
        self.assertFalse(sig.parameters["intelligence"].default)


if __name__ == "__main__":
    unittest.main()
