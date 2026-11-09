"""Module 9/10 — Outcome Verification + Bounded Recovery (Phase 6).

The only code allowed to say "this policy made the network better". It works
from *real* measurements taken after application — predictions and historical
comparisons are recorded alongside, never as evidence of outcome.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any

from ..model import RatePlan
from ..policy import build_plan
from .config import IntelligenceConfig
from .contracts import (
    SCHEMA_VERSION,
    ApplicationResult,
    Candidate,
    DecisionAction,
    DecisionResult,
    NetworkState,
    Outcome,
    OutcomeClass,
    ReadbackResult,
    RecoveryEvent,
)

# outcome thresholds: reuse existing project objectives, not new universals
_LATENCY_LIMIT_MS = 50.0
_LOSS_LIMIT = 0.01
_FAIRNESS_MIN = 0.5


class OutcomeVerifier:
    """Classify a lifecycle's real outcome from post-apply measurements."""

    def __init__(self, config: IntelligenceConfig | None = None):
        self.config = config or IntelligenceConfig()

    def verify(self, application: ApplicationResult, readback: ReadbackResult,
               measurements: dict[str, float],
               predicted: dict[str, float] | None = None,
               simulated: dict[str, float] | None = None,
               limitations: tuple[str, ...] = (),
               correlation_id: str = "", now: float | None = None) -> Outcome:
        now = now if now is not None else time.time()
        applied_id = application.candidate_id or "applied"
        lims = list(limitations)

        # Application never landed: outcome is APPLICATION_FAILED regardless
        # of what metrics happen to look like.
        if not application.applied:
            return Outcome(
                decision_id=application.decision_id, applied_policy_id=applied_id,
                outcome=OutcomeClass.APPLICATION_FAILED, measurements=measurements,
                predicted=predicted or {}, simulated=simulated or {},
                limitations=tuple(lims + ["policy not applied; metrics do not "
                                           "describe the candidate"]),
                correlation_id=correlation_id, recorded_at=now)

        if not readback.verified:
            return Outcome(
                decision_id=application.decision_id, applied_policy_id=applied_id,
                outcome=OutcomeClass.DEGRADED, measurements=measurements,
                predicted=predicted or {}, simulated=simulated or {},
                limitations=tuple(lims + [f"readback mismatches: {readback.mismatches}"]),
                correlation_id=correlation_id, recorded_at=now)

        if not measurements:
            return Outcome(
                decision_id=application.decision_id, applied_policy_id=applied_id,
                outcome=OutcomeClass.INCONCLUSIVE, measurements={},
                predicted=predicted or {}, simulated=simulated or {},
                limitations=tuple(lims + ["no post-apply measurements"]),
                correlation_id=correlation_id, recorded_at=now)

        degraded = (
            measurements.get("latency_ms", 0.0) > _LATENCY_LIMIT_MS
            or measurements.get("loss_ratio", 0.0) > _LOSS_LIMIT
            or measurements.get("fairness", 1.0) < _FAIRNESS_MIN)

        # Prediction/sim divergence is recorded, never used as evidence.
        for name, expected in (("predicted", predicted or {}),
                               ("simulated", simulated or {})):
            if expected and measurements:
                drift = {k: round(measurements.get(k, 0.0) - float(v), 4)
                         for k, v in expected.items() if k in measurements}
                if any(abs(d) > 20.0 for d in drift.values()):
                    lims.append(f"{name} diverged from actual: {drift}")

        return Outcome(
            decision_id=application.decision_id, applied_policy_id=applied_id,
            outcome=(OutcomeClass.DEGRADED if degraded else OutcomeClass.SUCCESSFUL),
            measurements=measurements, predicted=predicted or {},
            simulated=simulated or {}, limitations=tuple(lims),
            correlation_id=correlation_id, recorded_at=now)


class RecoveryEngine:
    """Bounded, verified recovery. Never blind-restores an invalid old policy.

    The previous policy is revalidated against *current* capacity: if it over-
    allocates now, the safe fallback (`build_plan` at current capacity) is used
    instead — through the same gate + gateway submit path as any candidate.
    """

    def __init__(self, gateway, config: IntelligenceConfig | None = None,
                 log_path: Path | str = "data/intelligence/recovery.jsonl"):
        self.gateway = gateway
        self.config = config or IntelligenceConfig()
        self.log_path = Path(log_path)
        self._attempts = 0
        self._last_attempt: float | None = None
        self.events: list[RecoveryEvent] = []

    def _persist(self, event: RecoveryEvent) -> None:
        """Audit every recovery attempt (success or not) to disk. Never crashes."""
        try:
            d = event.to_dict()
            d["schema"] = SCHEMA_VERSION
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(d, sort_keys=True) + "\n")
                f.flush()
                os.fsync(f.fileno())
        except Exception:
            pass  # audit must never break recovery itself

    def can_attempt(self, now: float) -> bool:
        if self._attempts >= self.config.recovery_attempt_limit:
            return False
        if self._last_attempt is not None and now - self._last_attempt < self.config.recovery_cooldown_s:
            return False
        return True

    def recover(self, state: NetworkState, previous_plan: RatePlan,
                decision_id: str, trigger: str,
                correlation_id: str = "",
                now: float | None = None) -> tuple[RecoveryEvent, ApplicationResult | None]:
        now = now if now is not None else time.time()
        prev_id = f"plan@{previous_plan.capacity_mbps:g}"
        failure_evidence: dict[str, Any] = {"trigger": trigger,
                                            "previous_policy": prev_id}

        if not self.can_attempt(now):
            ev = RecoveryEvent(trigger=trigger, previous_policy_id=prev_id,
                               action="SAFE_FALLBACK", outcome="INCONCLUSIVE",
                               failure_evidence={**failure_evidence,
                                                 "error": "attempt limit or cooldown"},
                               remaining_uncertainty="recovery deferred",
                               correlation_id=correlation_id, recorded_at=now)
            self.events.append(ev)
            self._persist(ev)
            return ev, None

        # Revalidate previous policy against CURRENT capacity. The margin
        # fraction governs *new* allocations (the gate checks it); a previous
        # plan that already ran at this capacity is restorable as-is.
        cap = state.capacity.mbps
        restorable = previous_plan.total() <= cap + 1e-9 and not previous_plan.degraded
        if restorable:
            plan, action = previous_plan, "ROLLBACK"
        else:
            plan, action = build_plan(cap), "SAFE_FALLBACK"
            failure_evidence["previous_invalid_reason"] = (
                f"previous total {previous_plan.total():.1f} exceeds safe "
                f"capacity {cap:.1f}")

        self._attempts += 1
        self._last_attempt = now

        candidate = Candidate(plan=plan, parent_policy_id=prev_id,
                              reason=f"recovery: {trigger}",
                              correlation_id=correlation_id, recorded_at=now)
        from .validate import AcceptanceGate
        gate = AcceptanceGate(self.config)
        validation = gate.validate(candidate, state, current_plan=None)
        dec = DecisionResult(action=DecisionAction.RECOVER,
                             current_policy_id=prev_id,
                             selected_candidate_id=candidate.record_id,
                             reason=f"verified deterioration: {trigger}",
                             correlation_id=correlation_id, recorded_at=now)
        app, readback = self.gateway.submit(dec, candidate, validation, state, now=now)

        # Recovery verdict: only SUCCESS when applied AND readback verified.
        outcome = ("SUCCESS" if (app.applied and readback.verified)
                   else ("FAILED" if not app.applied else "INCONCLUSIVE"))
        ev = RecoveryEvent(trigger=trigger, previous_policy_id=prev_id,
                           action=action, outcome=outcome,
                           failure_evidence=failure_evidence,
                           duration_s=0.0,
                           remaining_uncertainty=(
                               "" if outcome == "SUCCESS"
                               else f"application failure: {app.failure}"),
                           correlation_id=correlation_id, recorded_at=now)
        self.events.append(ev)
        self._persist(ev)
        return ev, app
