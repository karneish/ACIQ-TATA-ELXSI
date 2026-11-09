"""Controller integration gateway (Phase 5).

The *only* path from the intelligence layer to the kernel. It submits a
gate-approved candidate through the existing controller (`Harness` +
`TransactionManager`) — mirroring `Harness._adapt_step_inner` bookkeeping so
`_current_plan`, capacity ledger and readback semantics stay identical to the
adaptive loop. The intelligence layer never issues `tc` itself.

Freshness + version checks run *before* submission: a stale or superseded
decision is recorded as a refusal, never applied.
"""
from __future__ import annotations

import time
from typing import Any

from .config import IntelligenceConfig
from .contracts import (
    ApplicationResult,
    Candidate,
    DecisionResult,
    NetworkState,
    ReadbackResult,
    ValidationResult,
)


class ControllerGateway:
    def __init__(self, harness, config: IntelligenceConfig | None = None):
        self.harness = harness
        self.config = config or IntelligenceConfig()

    @staticmethod
    def _plan_id(plan) -> str:
        return f"plan@{plan.capacity_mbps:g}"

    def submit(self, decision: DecisionResult, candidate: Candidate | None,
               gate: ValidationResult | None, state: NetworkState,
               now: float | None = None) -> tuple[ApplicationResult, ReadbackResult]:
        now = now if now is not None else time.time()
        cid = candidate.record_id if candidate else ""
        base: dict[str, Any] = dict(decision_id=decision.record_id,
                                    candidate_id=cid or None,
                                    correlation_id=decision.correlation_id,
                                    recorded_at=now)

        def _refuse(failure: str) -> tuple[ApplicationResult, ReadbackResult]:
            app = ApplicationResult(submitted=False, controller_accepted=False,
                                    applied=False, readback_verified=False,
                                    failure=failure, **base)
            readback = ReadbackResult(verified=False, mismatches=(failure,),
                                      correlation_id=decision.correlation_id,
                                      recorded_at=now)
            return app, readback

        # Gate first — invalid candidates never reach the controller.
        if gate is None or not gate.accepted:
            return _refuse("gate rejected or missing: "
                           + (gate.explanation if gate else "no gate result"))
        if candidate is None:
            return _refuse("no candidate to submit")

        # Freshness: decision must rest on fresh state.
        if state.recorded_at + self.config.freshness_limit_s < now:
            return _refuse(f"stale network state "
                           f"(age {now - state.recorded_at:.1f}s > "
                           f"{self.config.freshness_limit_s}s)")

        # Version: candidate must build on the plan currently installed.
        current = getattr(self.harness, "_current_plan", None)
        if current is not None and candidate.parent_policy_id != self._plan_id(current):
            return _refuse(f"superseded: parent {candidate.parent_policy_id} "
                           f"!= current {self._plan_id(current)}")

        plan = candidate.plan
        intended = {"capacity_mbps": plan.capacity_mbps,
                    "rates": {c.value: r for c, r in plan.rates.items()},
                    "ceils": {c.value: r for c, r in plan.ceils.items()},
                    "lease_id": plan.lease_id,
                    "degraded": plan.degraded}

        # Same bookkeeping as adapt_step: set current plan, remember capacity,
        # apply through the transaction manager (shield + readback inside).
        self.harness._current_plan = plan
        try:
            self.harness.txn.remember_capacity(plan.capacity_mbps)
        except Exception:
            pass
        outcome = self.harness.txn.apply(plan, now=now)

        actual: dict[str, Any] = {}
        try:
            actual = self.harness._read_applied_rates() or {}
        except Exception:
            actual = {}
        mismatches = tuple(str(m) for m in (getattr(outcome, "mismatches", None) or ()))
        # Critical (spec §22): a rollback to last-good restores the PREVIOUS
        # plan — the candidate was NOT applied. Outcome.ok covers both commit
        # and verified rollback, so "applied" must mean committed, not rolled back.
        rolled_back = bool(getattr(outcome, "rolled_back", False))
        committed = bool(getattr(outcome, "committed", outcome.ok))
        applied_candidate = bool(outcome.ok and committed and not rolled_back)
        verified = bool(applied_candidate and not mismatches)
        failure = None if applied_candidate else (
            "rolled back to last-good: candidate not applied" if rolled_back
            else (outcome.reason or "apply failed"))

        app = ApplicationResult(submitted=True,
                                controller_accepted=bool(outcome.ok),
                                applied=applied_candidate,
                                readback_verified=verified,
                                intended_cfg=intended,
                                actual_cfg=actual if isinstance(actual, dict) else {},
                                failure=failure,
                                **base)
        readback = ReadbackResult(verified=verified, expected_cfg=intended,
                                  actual_cfg=actual if isinstance(actual, dict) else {},
                                  mismatches=mismatches,
                                  correlation_id=decision.correlation_id,
                                  recorded_at=now)
        return app, readback
