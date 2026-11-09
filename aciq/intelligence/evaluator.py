"""Module 2 — Current Policy Evaluator (Phase 4).

Answers "is the active plan still the right plan?" from a NetworkState and the
current RatePlan. Read-only; introduces no new universal thresholds — limits
come from IntelligenceConfig (documented, configurable) and existing policy
invariants (floors, fairness) already in `policy.py` / `fairness.py`.
"""
from __future__ import annotations

import time

from ..model import RatePlan, TrafficClass
from .config import IntelligenceConfig
from .contracts import NetworkState, PolicyEvaluation, PolicyHealth


class PolicyEvaluator:
    def __init__(self, config: IntelligenceConfig | None = None):
        self.config = config or IntelligenceConfig()

    def evaluate(self, state: NetworkState, current_plan: RatePlan | None,
                 correlation_id: str, latency_limit_ms: float = 50.0,
                 loss_limit: float = 0.01,
                 now: float | None = None) -> PolicyEvaluation:
        evidence: dict[str, float] = {}
        missing = list(state.missing)

        if state.reliability.value == "unknown":
            return self._out(current_plan, PolicyHealth.UNKNOWN, evidence,
                             missing + ["network_state"], "state unknown", correlation_id, now)

        if current_plan is None:
            return self._out(current_plan, PolicyHealth.INVALID, evidence,
                             missing, "no current plan", correlation_id, now)

        # validity: does the active plan still satisfy capacity invariants?
        if current_plan.total() > current_plan.capacity_mbps + 1e-9:
            return self._out(current_plan, PolicyHealth.INVALID,
                             {"total": current_plan.total(),
                              "capacity": current_plan.capacity_mbps},
                             missing, "plan exceeds capacity", correlation_id, now)
        for cls, ceil in current_plan.ceils.items():
            if ceil > current_plan.capacity_mbps + 1e-9:
                return self._out(current_plan, PolicyHealth.INVALID,
                                 {"ceil": ceil, "capacity": current_plan.capacity_mbps},
                                 missing, f"ceil[{cls.value}] exceeds capacity",
                                 correlation_id, now)

        # health triage with config limits
        degraded = False
        if state.latency_ms is not None:
            evidence["latency_ms"] = float(state.latency_ms)
            if float(state.latency_ms) > latency_limit_ms:
                degraded = True
        if state.loss_ratio is not None:
            evidence["loss_ratio"] = float(state.loss_ratio)
            if float(state.loss_ratio) > loss_limit:
                degraded = True
        if state.queue_backlog_bytes is not None:
            evidence["backlog_bytes"] = float(state.queue_backlog_bytes)
            if float(state.queue_backlog_bytes) > 200_000:
                degraded = True
        if state.congestion:
            evidence["congested"] = 1.0

        if state.capacity.confidence <= 0.0:
            # estimator never learned anything: cannot judge
            return self._out(current_plan, PolicyHealth.UNKNOWN, evidence,
                             missing + ["capacity_confidence"], "no capacity confidence",
                             correlation_id, now)

        # interactive protection: interactive rate share must be non-trivial
        interactive = (current_plan.rates.get(TrafficClass.VIDEO_CALL, 0.0)
                       + current_plan.rates.get(TrafficClass.GAMING, 0.0))
        if state.per_class_demand.get(TrafficClass.VIDEO_CALL, 0) > 0 and interactive <= 0:
            return self._out(current_plan, PolicyHealth.INVALID,
                             {"interactive_rate": interactive}, missing,
                             "interactive demand with zero protection", correlation_id, now)

        if degraded:
            # hysteresis: confirmed degradation only when state is RELIABLE;
            # otherwise MONITOR so we don't thrash on noisy data.
            health = (PolicyHealth.CONFIRMED_DEGRADATION
                      if state.reliability.value == "reliable"
                      else PolicyHealth.MONITOR)
            why = "latency/loss/backlog beyond limits"
        elif len(missing) >= 4:
            health = PolicyHealth.MONITOR
            why = "limited evidence"
        else:
            health = PolicyHealth.HEALTHY
            why = "all checks within limits"

        return self._out(current_plan, health, evidence, missing, why, correlation_id, now)

    @staticmethod
    def _out(plan: RatePlan | None, health: PolicyHealth, evidence, missing, why,
             correlation_id: str, now: float | None = None) -> PolicyEvaluation:
        pid = "unknown"
        if plan is not None:
            pid = f"plan@{plan.capacity_mbps:g}"
        return PolicyEvaluation(current_policy_id=pid, health=health,
                                evidence=evidence, missing=tuple(missing),
                                explanation=why, correlation_id=correlation_id,
                                recorded_at=now if now is not None else time.time())
