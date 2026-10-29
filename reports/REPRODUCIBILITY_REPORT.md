# Reproducibility report

## What reproduction rests on (inspected, current revision)

| Layer | Evidence |
|---|---|
| Revision stamp per band | `data/runs_dev3/REVISION` = `5865fe0d0dc6…` (band of origin); the retuned band will stamp `210bd09f`; commit chain: `fa9f27f9` → `5865fe0d` → `210bd09f` |
| Revision stamp per run | every `result.json` carries `commit_hash` (validated on 128 runs — the earlier UNKNOWN is closed); `config.json` also carries `commit_hash` |
| Config identity | `config.json` per run stores the full scenario/system/mode/seed/ports/dscp/floors/lease/inject-fail configuration; validator asserts result↔config↔dir identity |
| Seeds | dev 1000–1009, planned final 1100–1109 (disjoint from all historical bands); fixed start offsets are seeded (visible in `result.notes`) |
| Checksums | `data/` carries committed `SHA256SUMS` for committed artifacts |
| Verified commands | full suite `~/aciq-venv/bin/python -m unittest discover -s tests -q` → 1498 OK / 10 skipped at `210bd09f`; ruff clean; `tools/audit_claims.py` |
| Validation | `tools/validate_runs.py` → `reports/experiment_validation_report.{json,md}` (128 valid/passing / 0 invalid at read) |
| End-to-end repeatability | 21-check kernel gate (`testbed/gate.sh`, 7 committed historical logs) — executed on host sessions with root |

## Reproducibility limits (stated explicitly)

- Seed-fixed does NOT imply output-identical: netem pacing and kernel timers
  vary between runs; the project's methodology treats seeds as a paired-sample
  design (means/CI over seeds), not as byte-identical replay.
- The fresh dev-band artifacts are validated for identity/provenance/coverage;
  semantic re-run equivalence (same numbers on re-execution at the same
  commit) has NOT been demonstrated — that requires the next host-session band.
- Old gate logs removed from the working tree (prior hygiene pass, uncommitted
  deletions) are recoverable from git history; the 7 newest `gate-2026-1*` logs
  remain.
