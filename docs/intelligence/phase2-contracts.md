# Phase 2 — Architecture and Data Contracts

Implemented in `aciq/intelligence/contracts.py` (pure types, no I/O, no kernel).
Existing ACIQ types are **reused, never duplicated**: `Capacity`, `RatePlan`,
`TrafficClass`, `Lease` from `aciq/model.py`. Candidates carry the exact
`RatePlan` `policy.build_plan` produced, so an unsupported parameter cannot exist.

## Global rules (all 12 records)

| Rule | Detail |
|---|---|
| `schema` | Always `1` (`SCHEMA_VERSION`). Readers reject unknown schemas; never coerce. |
| `record_id` | Non-empty string (UUID hex from producer). |
| `recorded_at` | Finite epoch seconds > 0 (wall-clock evidence time; never tick time). |
| `correlation_id` | Ties one lifecycle together; records with different IDs are never compared. |
| Confidence | Float in [0,1]; `None` = *unknown*, never 0. |
| Enums | Serialise by value (`str` enums) — JSONL stays human-readable. |
| Serialisation | `to_dict()` / `from_dict()` is the *only* path. Invalid records are rejected (quarantine), never repaired silently. |
| Missing ≠ zero | Every numeric field can be `None`; a `missing` list names what was absent. |

## The 12 objects

### 1. `NetworkState` (Module 1 — observer)
Required: `capacity: Capacity`, `recorded_at`. Optional: `per_class_demand`, `active_flows`,
`latency_ms/jitter_ms/loss_ratio/throughput_mbps/queue_backlog_bytes` (each `None` when
unmeasured), `congestion`, `classification_confidence`, `enforcement_state`,
`current_policy_id`, `freshness{name: age_s}`, `missing[]`, `reliability`
(`reliable/degraded/unknown`). Validation: loss ≤ 1, freshness ages ≥ 0, confidence in range.

### 2. `PolicyEvaluation` (Module 2 — evaluator)
Required: `current_policy_id`, `health` (`healthy/monitor/degrading/confirmed_degradation/invalid/unknown`),
`correlation_id`. Evidence dict + missing + explanation. Means: *is the active plan still right?*

### 3. `Prediction` (Module 3 — predictor)
Required: `horizon_s > 0`, `status` (`none/potential/high/uncertain`), `confidence` (required when
`high`). Optional: `severity`, `evidence[]`, `missing_inputs[]`, `predicted_metrics{}`. A prediction is
never stored as a success and never authorises an unsafe change on its own.

### 4. `Experience` (Module 4 — repository row, one JSON line)
Required: `status` (8 values: `success/failed/inconclusive/simulation_only/rejected/recovery/
prediction_only/incomplete`). Contexts (all dicts): `network_context`, `policy_context`,
`decision_context`, `outcome_context`. Hard separation rules, tested in
`tests/test_intelligence_contracts.py`:
- `SUCCESS/FAILED/RECOVERY` → `outcome_context["measured"]` **must** be present.
- `SIMULATION_ONLY` → `measured` **must be absent**.
- `INCOMPLETE` → `measured` **must be absent** (quarantined, never promoted).
Retrieval (Phase 4) must explain similarity and prefer MEASURED over SIMULATION_ONLY.

### 5. `Candidate` (Module 5 — generator)
Required: `plan: RatePlan` (with `sum(rates) ≤ capacity`, `ceil ≤ capacity` — reusing the
`build_plan` invariants), `parent_policy_id`, `reason`. Optional: `experience_refs`,
`expected_benefits`, `trade_offs`, `risks`, `constraints_to_validate`, `required_capabilities`.
Generation never applies anything.

### 6. `ValidationResult` (Module 6 — unified gate)
Required: `candidate_id`, `accepted`. Checks performed, `failed_constraints[]`,
`warnings[]`, `missing_evidence[]`, `explanation`, `corrective_action`. Rules:
accepted ⇒ no failed constraints; rejected ⇒ must state why. The only entry to the controller.

### 7. `HistoricalResult` (Module 7 — what-if, historical-only per Q2 decision)
Required: `candidate_id`, `baseline_policy_id`, `limitations[]` (always stated), `metrics{}` finite.
`ranking[]`, `complete`. Source is **real past runs only** (`data/runs/*`); a future simulator must
produce this same shape and stay labeled `SIMULATION_ONLY` in the Experience.

### 8. `DecisionResult` (Module 8 — decision)
Required: `action` (`retain/select/reject_all/defer/recover/safe_fallback`), `current_policy_id`,
`reason`, `correlation_id`. Rules: `SELECT` requires `selected_candidate_id`;
`RETAIN/REJECT_ALL/DEFER` must not carry one; every confidence dim in [0,1] or None.
Also: `confidence{dim: value}`, `rejected_candidate_ids[]`, `mandatory_checks[]`,
`relevant_experiences[]`, `expected_trade_offs[]`.

### 9. `ApplicationResult` (integration)
`decision_id`, `candidate_id`, `submitted`, `controller_accepted`, `applied`,
`readback_verified`, `intended_cfg{}`, `actual_cfg{}`, `failure`. Rules: applied ⇒ accepted;
verified ⇒ applied. **Selected ≠ accepted ≠ applied ≠ verified** — four different states, four fields.

### 10. `ReadbackResult` (verification)
`verified`, `expected_cfg{}`, `actual_cfg{}`, `mismatches[]`. Failed ⇒ must name mismatches.
Independent of outcome measurement (enforcement ≠ performance).

### 11. `Outcome` (outcome verification)
`decision_id`, `applied_policy_id`, `outcome` (`successful/degraded/inconclusive/application_failed/
recovered`), `measurements{}` (real only), `predicted{}`, `simulated{}` (kept separate),
`limitations[]`. Successful/degraded/recovered **require measured evidence**.

### 12. `RecoveryEvent` (bounded recovery audit)
`trigger`, `previous_policy_id`, `action` (`ROLLBACK/SAFE_FALLBACK`), `outcome`
(`SUCCESS/FAILED/INCONCLUSIVE`), `failure_evidence{}`, `duration_s`, `remaining_uncertainty`.
Successful recovery requires failure evidence; limits/cooldown live in `config` (Phase 3).

## End-to-end sequence

```
NetworkState ──→ PolicyEvaluation ──→ Prediction ──→ Experience(retrieve)
                                                        │
      ┌───────────────── Candidate[] ◄──────────────────┘
      ▼
  ValidationResult (gate, one per candidate)
      ▼
  HistoricalResult (vs current, measured only) ──→ DecisionResult
      ▼
  ApplicationResult ──→ ReadbackResult ──→ Outcome ──→ RecoveryEvent (if degraded)
      ▼
  Experience (new, measured) + DecisionRecord  →  data/intelligence/decisions.jsonl
```

Module ownership: `state`→1, `evaluator`→2, `predictor`→3, `experience`→4, `candidates`→5,
`validate`→6, `historical`→7, `decide`→8, `outcome`→9/10/11, `dashboard`→15. Existing controller
(`Harness.apply_system`) is the only enforcement entry; intelligence never issues `tc` calls.

## Error states (uniform)

Every module returns either its record (valid) or raises `ValueError` listing *all* field errors
(`validate()`), or returns the record's `errors()` list where a non-throwing verdict is needed
(gate). Nothing coerces, guesses, or silently repairs.

## Tests (this phase)
`tests/test_intelligence_contracts.py` — 27 tests: valid/invalid per object, status separation
(SIM never measured, SUCCESS requires measured), RatePlan invariants reused, decision rules
(SELECT needs candidate, RETAIN must not carry one), application chain rules, recovery rules,
historical limitations, JSON round-trips.
