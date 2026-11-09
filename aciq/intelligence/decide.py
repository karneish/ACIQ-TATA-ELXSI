"""Module 8 — Confidence-Aware Policy Decision Engine (Phase 4).

Chooses RETAIN / SELECT / REJECT_ALL / DEFER / RECOVER from separate confidence
dimensions (never one misleading aggregate). A high score can never compensate
for a mandatory gate failure — the gate runs first and its verdict stands.
"""
from __future__ import annotations

import time

from .config import IntelligenceConfig
from .contracts import (
    Candidate,
    DecisionAction,
    DecisionResult,
    Experience,
    HistoricalResult,
    NetworkState,
    PolicyEvaluation,
    Prediction,
    ValidationResult,
)


class DecisionEngine:
    def __init__(self, config: IntelligenceConfig | None = None):
        self.config = config or IntelligenceConfig()

    def decide(self, state: NetworkState, evaluation: PolicyEvaluation,
               prediction: Prediction | None,
               candidates: list[Candidate],
               validations: list[ValidationResult],
               historical: list[HistoricalResult],
               retrieved: list[Experience],
               correlation_id: str,
               now: float | None = None) -> DecisionResult:
        accepted = [v for v in validations if v.accepted]
        rejected = [v for v in validations if not v.accepted]
        conf = {
            "measurement": 1.0 if state.reliability.value == "reliable" else (
                0.5 if state.reliability.value == "degraded" else 0.1),
            "capacity": float(state.capacity.confidence or 0.0),
            "classification": state.classification_confidence,
            "prediction": prediction.confidence if prediction else None,
            "similarity": max((float(getattr(r, "score", 0.0)) for r in retrieved), default=None),
            "enforcement": 1.0 if state.enforcement_state != "failed" else 0.0,
        }
        mandatory = tuple(dict.fromkeys(
            c for v in validations for c in v.checks))

        # 1. Recovery trigger beats everything: confirmed degradation + evidence.
        if (evaluation.health.value == "confirmed_degradation"
                and conf["measurement"] >= 0.5 and conf["capacity"] >= 0.3):
            return self._out(DecisionAction.RECOVER, state, evaluation,
                             selected=None, rejected=rejected, conf=conf,
                             mandatory=mandatory, retrieved=retrieved,
                             reason="confirmed degradation with reliable evidence",
                             correlation_id=correlation_id, now=now)

        # 2. No acceptable candidate → RETAIN or REJECT_ALL.
        if not accepted:
            if evaluation.health.value == "healthy":
                return self._out(DecisionAction.RETAIN, state, evaluation,
                                 selected=None, rejected=rejected, conf=conf,
                                 mandatory=mandatory, retrieved=retrieved,
                                 reason="no candidate passed the gate; current policy stands",
                                 correlation_id=correlation_id, now=now)
            action = (DecisionAction.DEFER if not retrieved else DecisionAction.REJECT_ALL)
            return self._out(action, state, evaluation,
                             selected=None, rejected=rejected, conf=conf,
                             mandatory=mandatory, retrieved=retrieved,
                             reason="all candidates rejected by the gate",
                             correlation_id=correlation_id, now=now)

        # 3. Current policy healthy + no strong degradation forecast → RETAIN.
        if (evaluation.health.value == "healthy"
                and (prediction is None or prediction.status.value not in ("high", "potential"))):
            return self._out(DecisionAction.RETAIN, state, evaluation,
                             selected=None, rejected=rejected, conf=conf,
                             mandatory=mandatory, retrieved=retrieved,
                             reason="current policy healthy; change not justified",
                             correlation_id=correlation_id, now=now)

        # 4. Low confidence → DEFER instead of guessing.
        decisive = [v for v in conf.values() if v is not None]
        if decisive and min(decisive) < 0.3:
            return self._out(DecisionAction.DEFER, state, evaluation,
                             selected=None, rejected=rejected, conf=conf,
                             mandatory=mandatory, retrieved=retrieved,
                             reason="confidence too low for aggressive change",
                             correlation_id=correlation_id, now=now)

        # 5. SELECT the first accepted candidate (bounded, gate-approved).
        winner = accepted[0]
        cand_id = winner.candidate_id
        return self._out(DecisionAction.SELECT, state, evaluation,
                         selected=cand_id, rejected=rejected, conf=conf,
                         mandatory=mandatory, retrieved=retrieved,
                         reason=f"first gate-approved candidate {cand_id!r}",
                         correlation_id=correlation_id, now=now)

    @staticmethod
    def _out(action, state, evaluation, selected, rejected, conf, mandatory,
             retrieved, reason, correlation_id, now) -> DecisionResult:
        return DecisionResult(
            action=action,
            current_policy_id=evaluation.current_policy_id,
            confidence={k: (float(v) if v is not None else None) for k, v in conf.items()},
            selected_candidate_id=selected,
            rejected_candidate_ids=tuple(v.candidate_id for v in rejected),
            mandatory_checks=tuple(mandatory),
            relevant_experiences=tuple(
                getattr(getattr(e, "experience", e), "record_id", "")
                for e in (retrieved or [])),
            expected_trade_offs=("change cost: stability",),
            reason=reason, correlation_id=correlation_id,
            recorded_at=now if now is not None else time.time())

