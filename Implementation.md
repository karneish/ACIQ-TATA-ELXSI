# ACIQ — Implementation Tracker

## What has been done so far (in `main`, frozen)

- **Frozen acceptance band**: 840 runs, engine `7c6c7235780a` — **140 judged PASS, 0 FAIL**.
- **TATA Case Study 3 (brief)**: all 34 mandatory lines implemented and live-proven.
  - S1 ISO+call, S2 WAN 100→20, S3 TVs+gaming (`PASS(interactive)`, starvation 0).
  - Classifier: corpus **0.917** held-out (frozen stamp 61% preserved honestly).
  - Capacity: live up-step **80.48**, s4 recovery **77.85** (was 17.44).
  - Dashboard: **840 runs / 41,040 samples** (`dashboard_final3/`).
  - Intent/fairness/starvation: verifier gates + 5-device `s6_intent_grid` **10/10 seeds** live.
  - Uplink shaping: **10 seeds** live (`--uplink 20 --enforce`).
  - Crash-restart: **3 kill-9 cycles PASS**.
  - Update/backup/voice (s5 ×5) + IPv6 (s8 ×3) live.
- **Suite**: 1605 tests OK (10 skipped); secret scan clean; S3 judged PASS via `tools/verify_round3.py`.
- **Branches**: `main` = frozen acceptance. `master` (this branch) = new unique-idea work. `main` must not be touched until the unique implementation is complete.

---

## The new unique idea (complete)

**Real-Time Experience-Driven Predictive QoS Intelligence with Confidence-Aware Policy Selection, Unified Safety Validation, and Verified Automatic Recovery.**

ACIQ today reacts to *current* congestion. The new layer adds a **brain on top** (existing controller still enforces):

1. **Observe** — collect network state (capacity, demand per class, latency/jitter/loss, queue, policy, timestamps). Never fabricate; missing ≠ healthy.
2. **Evaluate current policy** — healthy / monitor / degrading / confirmed / invalid / unknown. No change unless justified.
3. **Predict** — deterministic trends (queue/latency/capacity slopes) → degradation status + severity + horizon + confidence. Prediction is never a fact.
4. **Remember** — Experience Memory (`data/experiences.jsonl`, schema v1, JSON per Q1 decision): stores context → policy → prediction → simulated → actual outcome. Statuses: SUCCESS / FAILED / INCONCLUSIVE / SIMULATION_ONLY / REJECTED / RECOVERY / PREDICTION_ONLY / INCOMPLETE. Retrieval by similarity, always explained, prefers MEASURED, never bypasses validation.
5. **Generate candidates** — bounded (≤5): RETAIN + `build_plan` variants; each with reason, trade-offs, risks.
6. **Validate (unified gate)** — capacity, fairness, interactive protection, stability, enforcement compatibility, IPv4/IPv6, operational safety, evidence quality. Any violation → REJECT, recorded. No bypass.
7. **Compare — historical only (Q2 decision: no new simulator)** — candidates vs current policy using *real past runs only*. Similar conditions required, differences explained. No history → say so, rely on current measurements + safety.
8. **Decide with confidence** — separate dims (measurement, capacity, classification, prediction, similarity, enforcement). Outcomes: RETAIN / SELECT / REJECT_ALL / DEFER / RECOVER. Every decision has a structured `DecisionRecord` → `data/intelligence/decisions.jsonl` (new file, chosen).
9. **Enforce via existing controller only** — intelligence never runs `tc` directly; version/freshness checked; submission + readback recorded.
10. **Verify actual outcome** — SUCCESS / DEGRADED / INCONCLUSIVE / APPLICATION_FAILED / RECOVERED. Applied ≠ improved.
11. **Recover (bounded, verified)** — only on verified deterioration; revalidate old policy against *current* capacity; else safe fallback. Attempt/cooldown limits.
12. **Learn** — write the real outcome back to Experience Memory for next decision.

**Golden rules (from spec §§4, 25):** safety before optimization · prediction ≠ outcome · simulation ≠ outcome · applied ≠ improved · recovery must be evidence-based · never claim unmeasured success · deterministic first, no LLM/RL controller.

**Modules (all new, in `aciq/intelligence/`):**
`state.py` (observer) · `evaluator.py` · `predictor.py` · `experience.py` (JSONL) · `candidates.py` · `validate.py` (gate) · `historical.py` (what-if) · `decide.py` · `outcome.py` (verify+recover) · `dashboard.py` (panels) · `config.py`

**Separation contract (existing ↔ new):**

| New | Existing interface | Integration |
|---|---|---|
| Network State Observer | `observer`/`features`/`metrics` | Reuse snapshots, never recreate estimators |
| Policy Evaluator | `policy.build_plan` + `fairness` | Evaluate current `RatePlan` |
| Predictor | `capacity`/`metrics` telemetry | Read-only trends |
| Experience Repository | JSONL (`corrections.py` pattern) | Append-only, atomic, versioned |
| Candidate Generator | `policy.build_plan` | Variants only — no unsupported params |
| Safety Gate | `shield`/`txn` constraints | Single pre-enforcement gate |
| Historical Comparison | `data/runs/*` + repository | MEASURED only, SIM labeled separately |
| Decision Engine | `Harness` interface | Submits via `apply_system`, never `tc` directly |
| Outcome/Recovery | `Harness` readback + txn rollback | Bounded, verified |
| Dashboard | `dashboard.render_page` | New panels, read-only |

---

## Sequential implementation checklist

- [x] Phase 1 — Repository Audit → `docs/intelligence/phase1-audit.md` (architecture summary, capability + gap inventory, integration map, risks, file plan)
- [x] Phase 2 — Architecture + Data Contracts → `aciq/intelligence/contracts.py` (12 records, tested) + `docs/intelligence/phase2-contracts.md` (sequence diagram, module ownership, error rules)
- [x] Phase 3 — Foundation & Persistence → `aciq/intelligence/config.py` + `experience.py` (ExperienceStore + DecisionLogger) + `docs/intelligence/phase3-foundation.md`; 15 foundation tests; `data/intelligence/decisions.jsonl`
- [x] Phase 4 — Intelligence Modules → `aciq/intelligence/{state,evaluator,predictor,candidates,validate,historical,decide}.py` + `docs/intelligence/phase4-modules.md`; 21 module tests
- [x] Phase 5 — Controller Integration → `aciq/intelligence/integration.py` (ControllerGateway) + `--intelligence` opt-in hook + `docs/intelligence/phase5-integration.md`; 7 integration tests
- [x] Phase 6 — Outcome Verification & Recovery → `aciq/intelligence/outcome.py` (OutcomeVerifier + RecoveryEngine) + `docs/intelligence/phase6-outcome.md`; 10 outcome tests
- [x] Phase 7 — Dashboard & Reporting → `aciq/intelligence/dashboard.py` (additive section, base 6 panels untouched) + `docs/intelligence/phase7-dashboard.md`; 7 panel tests
- [x] Phase 8 — End-to-End Integration → historical/outcome/recovery/experience wired in `_intelligence_step` + `docs/intelligence/phase8-e2e.md`; 3 e2e dry tests (no dead modules)
- [x] Phase 9 — Testing → 108 intelligence tests (scenarios A–R + perf probe ~1 ms/cycle) + `docs/intelligence/phase9-testing.md` + verifier 140 PASS
- [x] Phase 10 — Final Audit → `docs/intelligence/phase10-audit.md` (2 dead-code + 1 persistence defect fixed; repo lint clean; **1713 tests OK**) — intelligence lifecycle complete

## Test scenarios (intelligence-specific, A–R)
- [ ] A Healthy policy retained · B ISO during video conf · C WAN 100→20 · D 3 TVs + gaming
- [ ] E Temporary work-call intent (bounded, expires, fairness kept) · F Stale/unreliable measurement → defer
- [ ] G Prediction wrong (no auto-change, error recorded) · H Simulation ≠ actual → actual wins + recovery
- [ ] I Fairness violation → reject · J Capacity exceeded → reject · K Apply/readback failure → bounded recovery
- [ ] L Old policy invalid now → safe fallback (not blind restore) · M Recovery failure → safe state
- [ ] N Similar history used (explained) · O Misleading history down-weighted · P No history → say so, record new
- [ ] Q Fluctuation → hysteresis, no oscillation · R Unknown/low-confidence traffic → conservative handling

## Completion rule
Complete only when every box above is checked with **real test output** (`make test`, `verify_round3`, live runs). No arbitrary scores.
