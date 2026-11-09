# Phase 4 — Intelligence Modules

Six modules in `aciq/intelligence/`, each pure and independently tested
(`tests/test_intelligence_modules.py`, 21 tests). None touches the kernel.

## 1. `state.py` — Network State Observer (Module 1)
Wraps the existing per-tick sample + `Capacity` into a `NetworkState`.
Freshness from the sample's own tick time; missing fields listed in `missing`
(never zero-filled). Reliability triage: missing capacity timestamp or class
confidence ⇒ `UNKNOWN`; ≤2 missing ⇒ `RELIABLE`; else `DEGRADED`.

## 2. `evaluator.py` — Current Policy Evaluator (Module 2)
Triage over the active `RatePlan`: capacity/ceil violations ⇒ `INVALID`;
latency > 50 ms, loss > 1%, backlog > 200 KB, or congestion ⇒ degraded
(`CONFIRMED_DEGRADATION` only when state is RELIABLE, else `MONITOR` — this is
the anti-thrash hysteresis); no capacity confidence ⇒ `UNKNOWN`; else `HEALTHY`.
Limits are constructor parameters (config-backed), never new universal thresholds.

## 3. `predictor.py` — Predictive Degradation Engine (Module 3)
Deterministic least-squares slopes over recent samples: latency, queue, capacity,
demand growth. `severity` 0–1, `evidence[]` quotes the slopes. Missing signals
lower confidence; `HIGH` requires a confidence value; `UNCERTAIN` carries
`confidence=None` (unknown, not zero). No ML, no lookahead, no model files.
Prediction informs decisions; it never authorises an unsafe change alone.

## 4. `candidates.py` — Candidate Generator (Module 5)
≤ `max_candidates` (default 5) candidates, all variants of
`policy.build_plan(capacity, lease)` with weight tweaks only:
retain-equivalent, interactive-boost, bulk-fair, streaming-heavy, conservative.
Every candidate carries reason/experience refs/trade-offs/risks/constraints,
and **must pass `Candidate.is_valid()`** (including `sum(rates) ≤ capacity`).

## 5. `validate.py` — Unified Safety Gate (Module 6)
One entry point, A–H checks: parameter validity, capacity compliance (+ margin
under low confidence), Shield veto, fairness (bulk never zero, interactive
protected, unknown never below floor), evidence quality (stale/unknown state
rejected), stability (large-change warning), operational safety (shield fault),
enforcement/IPv6 compatibility. Returns structured `ValidationResult`;
**accepted ⇒ zero failed constraints; rejected ⇒ reason stated**. No bypass.

## 6. `historical.py` + `decide.py` — What-if + Decision (Modules 7–8)
- **Historical**: compares a candidate against *real* `result.json` runs within
  20 Mbps of current capacity; outputs `HistoricalResult` with metrics +
  explicit limitations ("historical only, not a live prediction"). No comparable
  history ⇒ `complete=False` + stated limitation (never fabricated numbers).
- **Decision**: separate confidence dims (measurement, capacity,
  classification, prediction, similarity, enforcement — never one aggregate).
  Priority: confirmed degradation + reliable evidence ⇒ `RECOVER`; no accepted
  candidate ⇒ `RETAIN`/`DEFER`/`REJECT_ALL`; healthy + no forecast ⇒ `RETAIN`;
  any decisive confidence < 0.3 ⇒ `DEFER`; else `SELECT` first gate-approved
  candidate. Every decision records reason, rejected candidates, mandatory
  checks, retrieved experiences, trade-offs.

## Tests (21)
Observer: reliable / empty-sample / stale. Evaluator: healthy / degraded /
over-capacity / no-confidence. Predictor: short-history / rising / stable /
capacity-fall. Candidates+gate: bounded+real-builder / accept / over-capacity /
starved-bulk / unknown-state. Historical+decision: no-history / retain /
recover-on-confirmed / defer-on-unknown / experience-feeds-decision.
