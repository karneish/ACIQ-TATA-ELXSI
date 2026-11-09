# Phase 8 — End-to-End Integration

The full lifecycle is now wired in `ExperimentRunner._intelligence_step`
(opt-in `--intelligence`, default off). One tick at `t ≥ 30 s` cycles:

```
sample → observer → evaluator → predictor → retrieve
  → generate → validate → historical compare → decide
  → (SELECT ? gateway.submit : record)
  → NEXT tick: OutcomeVerifier → (DEGRADED ? RecoveryEngine : store) → Experience
```

## What's connected (no dead modules)
- **HistoricalComparer** — compares the first accepted candidate against
  `data/runs_final3` *measured* runs within ±20 Mbps, cached per runner.
- **DecisionLogger** — every decision appended to `data/intelligence/decisions.jsonl`
  with correlation ID `scenario:seed:t`.
- **Pending lifecycle** — after a SELECT applies, the next intelligence tick
  measures the real outcome (`OutcomeVerifier`), triggers `RecoveryEngine`
  on `DEGRADED`, and writes the measured Experience (SUCCESS/FAILED/INCONCLUSIVE/
  RECOVERY) back to `data/experiences.jsonl`.
- Sample rows carry an `"intelligence"` summary (action/reason/correlation);
  `result.json` notes record the last decision.

## Verified (dry, no kernel)
- `tests/test_intelligence_e2e.py`: intelligence run completes, decisions logged,
  historical/outcome/recovery classes are *called by the loop* (no dead code),
  degraded measurement classifies as such.
- Empty dry samples correctly produce `DEFER` (unknown state), never a guess.
- One real bug found & fixed: two different `Capacity` classes exist
  (`model.py` vs `capacity.py`) — observer now duck-types fields.

## Live note
Kernel verification of the wired loop happens via the existing live harness
(`tools/run_live_closeout.sh` pattern with `--intelligence`). Dry certification
is the Phase 8 gate; live evidence accumulates in Phase 9.
