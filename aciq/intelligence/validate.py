"""Module 6 — Unified Constraint and Safety Validation Engine (Phase 4).

The *only* path to the controller. A candidate that violates any mandatory
constraint is REJECTED here and can never reach enforcement — no downstream
component may bypass this gate.
"""
from __future__ import annotations

from ..model import RatePlan, TrafficClass
from ..shield import Shield
from .config import IntelligenceConfig
from .contracts import Candidate, NetworkState, ValidationResult


class AcceptanceGate:
    def __init__(self, config: IntelligenceConfig | None = None,
                 shield: Shield | None = None):
        self.config = config or IntelligenceConfig()
        self.shield = shield or Shield()

    def validate(self, candidate: Candidate, state: NetworkState,
                 current_plan: RatePlan | None = None) -> ValidationResult:
        checks: list[str] = []
        failed: list[str] = []
        warnings: list[str] = []
        missing: list[str] = []

        plan = candidate.plan
        checks.append("parameter_validity")
        if plan.capacity_mbps <= 0:
            failed.append("capacity: non-positive")

        checks.append("capacity_compliance")
        if plan.total() > plan.capacity_mbps + 1e-9:
            failed.append(f"capacity: sum(rates)={plan.total():.2f} > {plan.capacity_mbps:.2f}")
        # margin: never plan right up to a shaky estimate
        if state.capacity.confidence < 0.3 and plan.total() > state.capacity.mbps * (1 - self.config.capacity_margin_fraction):
            failed.append("capacity: no margin under uncertain estimate")

        checks.append("shield")
        for v in self.shield.veto_plan(plan):
            failed.append(f"shield:{v.code}")

        checks.append("fairness")
        rates = plan.rates
        available = {c for c, r in rates.items() if r > 0}
        if TrafficClass.BULK_DOWNLOAD in rates and rates.get(TrafficClass.BULK_DOWNLOAD, 0) <= 0:
            failed.append("fairness: bulk starved (zero allocation)")
        if TrafficClass.UNKNOWN in rates and rates.get(TrafficClass.UNKNOWN, 0) < 0:
            failed.append("fairness: unknown below its floor")
        # interactive demand must keep protection when present
        if state.per_class_demand.get(TrafficClass.VIDEO_CALL, 0) > 0:
            if rates.get(TrafficClass.VIDEO_CALL, 0) <= 0:
                failed.append("fairness: interactive demand unprotected")

        checks.append("evidence_quality")
        if state.reliability.value == "unknown":
            missing.append("network_state")
            failed.append("evidence: state unknown")
        if state.freshness and max(state.freshness.values()) > self.config.freshness_limit_s:
            failed.append("evidence: stale measurements")
        if state.classification_confidence is not None and state.classification_confidence < 0.4:
            warnings.append(f"classification confidence low ({state.classification_confidence:.2f})")
            missing.append("classifier_confidence")

        checks.append("stability")
        if current_plan is not None:
            delta = abs(plan.total() - current_plan.total())
            scale = max(current_plan.total(), 1e-9)
            if delta / scale > 0.8:
                warnings.append(f"large change ({delta / scale:.0%}) — stability review")

        checks.append("operational_safety")
        if self.shield.state.in_fault:
            failed.append("safety: shield in fault")

        checks.append("enforcement_ipv4_ipv6")
        for c in plan.rates:
            if c is TrafficClass.LEASED and plan.lease_id is None:
                failed.append("enforcement: leased class without lease_id")

        accepted = not failed
        explanation = ("all mandatory checks passed" if accepted
                       else f"rejected: {', '.join(failed)}")
        return ValidationResult(
            candidate_id=candidate.record_id, accepted=accepted,
            checks=tuple(checks), failed_constraints=tuple(failed),
            warnings=tuple(warnings), missing_evidence=tuple(missing),
            explanation=explanation,
            corrective_action="" if accepted else "retain current policy or fix candidate",
            correlation_id=candidate.correlation_id,
            recorded_at=state.recorded_at)
