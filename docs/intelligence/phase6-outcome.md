# Phase 6 — Outcome Verification & Recovery

Implemented in `aciq/intelligence/outcome.py` (tests:
`tests/test_intelligence_outcome.py`, 10 tests).

## OutcomeVerifier (Module 9)
Classifies a lifecycle from **real post-apply measurements only**:
- Not applied → `APPLICATION_FAILED` (metrics describe nothing).
- Readback mismatch → `DEGRADED` (enforcement ≠ performance, both measured).
- No measurements → `INCONCLUSIVE` (never upgraded).
- Latency > 50 ms, loss > 1%, or fairness < 0.5 → `DEGRADED`; else `SUCCESSFUL`.
- Prediction/simulation divergence > 20 is recorded in `limitations` —
  it explains, it never evidences.

## RecoveryEngine (Module 10)
Bounded and verified:
- Attempts capped (`recovery_attempt_limit`, default 3) + cooldown
  (`recovery_cooldown_s`, default 30). Exhausted ⇒ `INCONCLUSIVE` + deferred,
  no apply attempted.
- **Previous policy is revalidated against current capacity**: total ≤ capacity
  and not degraded ⇒ `ROLLBACK`; else `SAFE_FALLBACK` (`build_plan` at current
  capacity). Never blind-restores an over-capacity plan.
- Recovery goes through the *same* gate + gateway as any candidate (no bypass),
  and is only `SUCCESS` when applied **and** readback-verified.
- Every attempt appends a `RecoveryEvent` (trigger, previous policy, action,
  evidence, duration, remaining uncertainty).

## Realism note
Tests run on `FakeRunner` via the existing transaction path (including the
injected-failure rollback). Live kernel recovery is exercised by the existing
restart/stability harness scenarios; this layer adds the *decision* to recover,
boundedly.
