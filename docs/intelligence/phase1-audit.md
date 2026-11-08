# Phase 1 — Repository Audit (ACIQ Intelligence Layer)

Branch: `master` (from `main` at `5f044485`). This document records the codebase
**as found**, before Phase 2 design. No behavior is claimed here without a
file/line reference. Decisions locked by the project author: Experience
Repository = **append-only JSONL** (Q1-A), comparison = **historical measured
results only, no new simulator** (Q2-A). Decisions log lives in a **new file**
`data/intelligence/decisions.jsonl` (separate from `samples.jsonl`).

## 1. Architecture summary

ACIQ is a layered tick loop + per-flow steering + transactional kernel apply:

```
generators (testbed/workloads, netns wan)
 → observer/flowtrack (header-only, conntrack counters, no payload)
 → classify() + corrections + leases (ClosedLoop)
 → Bridge (nft → tc fw marks)
 → metrics collector (M5, kept separate from capacity inputs)
 → controller + CapacityEstimator (M2) + RateGovernor (M2.5) + BoardGuard
 → policy.build_plan → TransactionManager (M4 apply + M9 rollback + Shield)
 → tc HTB tree + netem bottleneck (wan/veth-w, out-of-band)
 → readback (qdisc parsers) → result.json / samples.jsonl / REPORT
```

Tick: `ExperimentRunner.run` (`aciq/experiment.py:367`) seeds estimator
recovery target (`seed_high_water`), reconciles restart state, applies uplink
cap, then per second: fault-injection → intent → probe ingest → `collector.poll()`
→ `harness.adapt_step` (estimate → govern → bound → `build_plan` → `txn.apply`)
→ `harness.enforce` per-flow steering → sample row → capacity events
(drop/recover/ramp, out-of-band link only).

`RatePlan` (`aciq/model.py:157`): `capacity_mbps`, `rates`, `ceils`, `lease_id`,
`degraded`. Invariants (enforced in `policy.build_plan`): `sum(rates) ≤ capacity`,
`ceil ≤ capacity`, `ceil ≥ rate`.

## 2. Existing capability inventory (verified — reuse as-is)

| Capability | Where | Notes |
|---|---|---|
| Header-only observation | `observer.py:138 HeaderObserver` | Payload slices stop before transport payload; sentinel-proven |
| Feature tracking | `flowtrack.py:148 FlowTracker`, `features.py:35 FlowFeatures` | conntrack counters → rates, no payload |
| Classification + confidence | `classify.py:351 classify()` → `Classification(cls,confidence,evidence)` | Corpus 0.917 held-out |
| Corrections (audit) | `corrections.py:252 CorrectionStore` | **Append-only JSONL**, `data/corrections.jsonl`, `SCHEMA=1`, fsync, malformed-count, last-wins, TTL — the pattern Experience Repository copies |
| Capacity estimation | `capacity.py:320 CapacityEstimator` (`observe:366`, `seed_high_water:553`) | Only saturated readings move it; ALPHA_UP 0.35, release-to-high-water |
| Rate governor | `ratecap.py:427 RateGovernor` | `applied ≤ cap_fraction × belief` + delay ratchet |
| Policy compiler (pure) | `policy.py:94 build_plan(capacity,lease)` | The ONLY compiler; floors, weights, lease `LEASED` class |
| Enforcement (sole path) | `harness.py:572 Harness` (`apply_system:1017`, `set_capacity:857`, `enforce:772`, `set_uplink_capacity:811`, `reconcile_after_restart:826`) + `txn.py:239 TransactionManager` | Shield veto → rebuild → readback → rollback → `force_safe` ladder |
| Rollback + safety | `txn.py`, `shield.py:93 Shield`, `controller.py:43 Controller`, `watchdog.py:45` | Bounded backoff, safe-held |
| Fairness/starvation | `fairness.py:140 jain`, `governor` floors | Cross-mode comparable (generator reports only) |
| Intent (temporary) | `intent.py:330 LeaseBook`, `api.py:128 IntentService` (`POST /intent`) | TTL-bound, validated, audited; live s6 grid 10/10 |
| Dashboard (read-only) | `dashboard.py:118 panels_from_samples`, `:365 summary_tiles`, `:590 render_page` | No kernel imports; inline SVG |
| Report | `report.py:413 build_report` | Reads raw artefacts only |
| Scenarios | `harness.py`: 15 (`s1,s2,s3` + `s4,s5,s6,s6_intent_grid,s2b×4,s7×5,s8,s3_stress`) | Live-proven |
| Restart reconcile | `restart.py:10 describe_applied`, `harness.py:826` | Live kill-9 cycle PASS ×3 |
| Uplink shaping | `uplink.py:9 uplink_rates`, `harness.set_uplink_capacity` | Live ×10 seeds |

Baseline verification (today): `tests.test_acceptance + tests.test_gates` **117 OK**;
full suite **1605 OK (10 skipped)** previously recorded; `verify_round3` **140 PASS, 0 FAIL**;
secret scan **clean**. No existing tests were weakened.

## 3. Missing inventory (the build)

| Spec need | Status | Gap |
|---|---|---|
| Network State Observer (§7/Module 1) | **Partial** | Snapshots exist (`samples.jsonl` rows) but no single `NetworkState` with freshness/completeness/uncertainty flags |
| Current Policy Evaluator (§11/Module 2) | **Partial** | `Controller` verifies *after* change; no pre-change HEALTHY/DEGRADING/INVALID triage with hysteresis |
| Prediction (§12/Module 3) | **Missing** | No trend predictor; `learned.py` is an offline classifier comparison only |
| Experience Repository (§13/Module 4) | **Missing** | No structured outcome store (only corrections JSONL) |
| Candidate Generator (§14/Module 5) | **Missing** | `build_plan` produces one plan; no alternative set with reasons/trade-offs |
| Unified Acceptance Gate (§15/§19/Module 6) | **Partial** | `Shield` vetos known invariants; no *single* mandatory-gate returning structured ACCEPT/REJECT/DEFER/RETAIN |
| Historical what-if (§17/Module 7) | **Missing** | No retrieval/comparison of past measured runs (Q2-A: use real `data/runs/*` only) |
| Confidence-aware decision (§18/Module 8) | **Partial** | Per-class confidences exist; no decision-level dimensions or RETAIN/SELECT/REJECT/DEFER/RECOVER enum |
| Outcome classifier + recovery verify (§24–25) | **Partial** | `Controller` + `verifier.py` verdicts exist; no SUCCESS/DEGRADED/INCONCLUSIVE/APPLICATION_FAILED/RECOVERED lifecycle record |
| Experience feedback (§26/§11) | **Missing** | Nothing writes outcomes back for reuse |
| Dashboard intelligence panels (§15/§28) | **Missing** | 6 base panels exist; 0 prediction/candidate/gate/experience panels |
| Decision audit log (§23) | **Missing** | No correlation-ID lifecycle log (new file decided) |

## 4. Integration map (actual interfaces only)

| New component | Existing interface | Integration approach |
|---|---|---|
| `state.NetworkStateObserver` | `collector.poll()` snapshot dict + `Current = estimator.current` | Wrap existing sample row; add freshness/missing flags |
| `evaluator.PolicyEvaluator` | `fairness` + `policy.build_plan` + objectives config | Read-only triage; hysteresis in config |
| `predictor.DegradationPredictor` | `samples.jsonl` series (queue/latency/capacity) | EWMA slopes; no new dependencies |
| `experience.ExperienceStore` | JSONL, `corrections.py` clone pattern | `data/experiences.jsonl`, schema v1, atomic append |
| `candidates.CandidateGenerator` | `policy.build_plan(capacity, lease)` | Bounded variants of its `RatePlan` output only |
| `validate.AcceptanceGate` | `shield.veto_plan/veto_rate` + `policy` invariants | One entry point; returns structured result |
| `historical.HistoricalComparer` | `data/runs/*/samples.jsonl` + `fairness` | MEASURED only; SIM labeled; similarity explained |
| `decide.DecisionEngine` | `Harness.apply_system` (submit) | Emits `DecisionRecord`; never `tc` directly |
| `outcome.OutcomeVerifier` | `qdisc.read_class_state` + `verifier.timeline_verdict` | Classify + bounded recovery via `txn` |
| Dashboard panels | `dashboard.panels_from_samples` | Additive panels; read-only preserved |

Flow: Observe → State → Classify(conf) → Capacity → Eval policy → Predict → Retrieve → Generate → Validate → Historical → Confidence → **Gate** → Stability → `Harness` → Readback → Outcome → Recover → Record → Monitor.

## 5. Conflicts / constraints found
1. `build_plan` is pure and sole compiler — candidates **must** be variants of its output; no new policy representation.
2. Capacity has **no configured-rate field by design** — predictor/experience must not leak it into decisions (seed target only, via `seed_high_water`).
3. Benchmarks/baselines must stay comparable: intelligence path is **opt-in** (`--intelligence` flag), default off, so 840-run frozen evidence stays reproducible.
4. `verify_round3` judges frozen bands only — new scenarios need their own verifier rows.
5. `data/` is huge (10k+ run dirs) — Experience retrieval indexes by (capacity band, scenario, policy hash), capped scan, never full-tree walks per tick.

## 6. Risks
- Prediction false-positives → unnecessary switching: gated by hysteresis + gate + verifier starvation.
- Experience poisoning by corrupted/sim-only records: schema validation + status separation + quarantine (copy `corrections.py` malformed handling).
- Storage growth: retention (≤5000 records, TTL) + index rebuild.
- Intelligence loop latency: run **per sample tick (1 s)**, not per packet; measure decision ms in Phase 9.
- Dashboard dishonesty: Predicted/Simulated never render as Verified.

## 7. Proposed file-level implementation plan
```
aciq/intelligence/__init__.py      # package, exports
aciq/intelligence/config.py        # Config (horizons, bounds, retention) + validation
aciq/intelligence/state.py         # Module 1 NetworkState + freshness
aciq/intelligence/evaluator.py     # Module 2 PolicyHealth triage + hysteresis
aciq/intelligence/predictor.py     # Module 3 deterministic trends
aciq/intelligence/experience.py    # Module 4 JSONL store + retrieval + quarantine
aciq/intelligence/candidates.py    # Module 5 bounded candidate set
aciq/intelligence/validate.py      # Module 6 unified gate (A-H)
aciq/intelligence/historical.py    # Module 7 historical what-if (measured only)
aciq/intelligence/decide.py        # Module 8 decision + DecisionRecord
aciq/intelligence/outcome.py       # Module 9/10 verify + bounded recovery
aciq/intelligence/dashboard.py     # Module 15 panels (additive)
data/intelligence/decisions.jsonl  # Decision audit log (new file)
docs/intelligence.md               # contracts, sequence, config, testing
tests/test_intelligence_*.py       # unit + integration + failure (Phase 9)
tools/measure_intelligence.py      # latency/overhead probe
```
No existing file is rewritten except additive hooks: `Harness.submit_decision()` (one method),
`run_experiments.py --intelligence` flag, `dashboard.py` panel registration.
