# Phase 3 — Foundation and Persistence

Implemented in `aciq/intelligence/config.py`, `experience.py` (repository +
audit log). All tests in `tests/test_intelligence_foundation.py` (temp dirs only —
no real data touched).

## Experience Repository — `data/experiences.jsonl`
Append-only JSONL (corrections.py pattern): single `write` + `fsync`, no locking,
concurrent readers never block. Stateless — every read hits disk, so **restart
loses nothing** and mid-write kills leave at most one partial line.

- `append(experience)` — validates the contract first; invalid records are
  **rejected, never written**.
- `load_all()` — malformed / wrong-schema / invalid lines are **quarantined**
  (counted + listed in `LoadStats`), never raised, never promoted.
- `retrieve(query, limit)` — similarity over capacity, latency, jitter, loss,
  demand overlap, intent. Returns `RetrievedExperience(score, explanation)`;
  below `similarity_threshold` (0.6) returns **empty = insufficient evidence**.
  MEASURED (SUCCESS/FAILED/RECOVERY) always outranks SIMULATION_ONLY /
  PREDICTION_ONLY; corrupt/incomplete never returned as evidence.
- `prune(keep)` — newest N kept; remainder archived to
  `experiences.jsonl.bak-<ts>.jsonl` (atomic temp+rename).

## Decision Audit Log — `data/intelligence/decisions.jsonl` (new file)
`DecisionLogger.append(DecisionResult)` — same atomic-append pattern, one line
per lifecycle. `load_all()` tolerates corrupt lines (audit must never crash
the loop).

## Configuration — `IntelligenceConfig`
| Parameter | Default | Meaning |
|---|---|---|
| `prediction_horizon_s` | 60 | How far ahead the predictor may look |
| `freshness_limit_s` | 5 | Older measurements cannot justify a change |
| `max_candidates` | 5 (≤20) | Bounded candidate set |
| `min_hold_s` | 30 | Minimum hold before next change |
| `verification_window_s` | 30 | Outcome measurement window |
| `recovery_attempt_limit` | 3 (≤10) | Bounded retries |
| `recovery_cooldown_s` | 30 | Backoff between recoveries |
| `retention_max_records` | 5000 | Experience retention cap |
| `similarity_threshold` | 0.6 | Retrieval gate |
| `capacity_margin_fraction` | 0.05 | Headroom kept under estimated capacity |

`from_file()` rejects unknown keys and bad JSON with clear errors; `from_dict()`
does the same. No secrets, no env vars, safe startup validation.

## Tests (15)
Config defaults/bounds/round-trip/unknown keys/bad JSON · append→restart read ·
invalid rejected-not-written · corrupt quarantine (malformed+version+invalid) ·
SIM vs MEASURED ranking · poor match → empty · explanation content ·
retention archive+newest-kept · prune no-op · audit append/reload ·
corrupt audit line tolerated · invalid decision rejected.
