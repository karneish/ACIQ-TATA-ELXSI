# Phase 5 — Controller Integration

## What was built
- `aciq/intelligence/integration.py` — `ControllerGateway`: the **only** path
  from intelligence to the kernel. Mirrors `Harness._adapt_step_inner`
  bookkeeping (`_current_plan`, `remember_capacity`, `txn.apply(plan, now=now)`,
  `_read_applied_rates` readback) so the established enforcement semantics are
  preserved exactly. The intelligence layer never issues `tc`.
- **Freshness check** — decision older than `freshness_limit_s` ⇒ refused
  (`submitted=False`), never applied.
- **Version check** — `candidate.parent_policy_id` must equal the installed
  plan's id (`plan@<capacity>`); superseded ⇒ refused.
- **Gate check** — rejected/missing gate result ⇒ refused before any kernel touch.
- **Rollback semantics (critical)** — `Outcome.ok` covers both commit *and*
  verified rollback to last-good. `applied` therefore means
  `ok and committed and not rolled_back`. A rolled-back submit records
  `failure="rolled back to last-good: candidate not applied"` — it can never
  read as success (spec §22).
- `ExperimentRunner.run(..., intelligence=False)` + CLI `--intelligence`
  (default **off**). On decision ticks (every `min_hold_s`) the intelligence
  cycle runs *instead of* `adapt_step` for that tick (single apply per tick,
  no fight); every decision is appended to `data/intelligence/decisions.jsonl`,
  and a one-line summary lands in the sample row (`"intelligence"` key) and
  `result.json` notes. Dry-run safe (FakeRunner certifies the hook).

## Tests (7, `tests/test_intelligence_integration.py`)
Submit→readback verifies · gate-rejected never reaches kernel · stale refused ·
superseded refused · **injected failed apply → not reported as success** ·
dry experiment hook completes · `--intelligence` default off.
