# Project Completion Inventory (ACIQ)

Generated: Stage 1 of the completion/validation effort. Read-only audit of the live repository; nothing was rewritten to produce it.

| Field | Value (inspected) |
|---|---|
| Repository root | `/home/mekarz/Desktop/Full-projects/TATA-ELXSI` |
| Branch | `main` |
| HEAD | `5865fe0d0dc6ce3e0cfdb75b1bd2d5e03b474452` (regen claim-audit stamp after dev-band retune) |
| Working tree | Uncommitted: `M data/REPORT.md` (band-generated output) and deletion of ~85 stale `testbed/logs/gate-2026100*/` logs (prior hygiene pass, not yet committed). No source files modified. |
| Language / runtime | Python 3 stdlib-only runtime (no external runtime deps); `run_experiments.py` CLI |
| Venv | `~/aciq-venv` (holds ruff + pytest tooling) |
| Active process | **DEV band `round3` running in tmux on the user machine** (launched 2026-10-29 19:25:46 IST, `testbed/run_round3_batch.sh dev`). This inventory must not interfere with it. |

## 1. Architecture (actual modules)

| Component | Existing implementation | Evidence | Missing work |
|---|---|---|---|
| Traffic observation | Header-only capture (snaplen 96) | `aciq/observer.py`-family; unchanged-at-HEAD; gate logs | IPv6 classification path (REQ-015 residual) |
| Classification | Feature/header classifier + confidence + correction | `aciq/classify.py:117`, `aciq/corrections.py`; corpus eval artifacts | Stamped eval provenance (REQ-032) |
| Capacity estimation | Replay/estimator chain | `aciq/capacity.py`; unit tests; newest e2e = replay-only (`docs/gap-closure/final-validation-report.md:16`) | Fresh end-to-end estimation evidence (REQ-002/033) |
| Adaptive governor | Pierce gate (overlimit witness) + severe-drop landing | `aciq/ratecap.py` (SEVERE_DROP_FRAC=0.9, PROBE_OVERLIMIT_MIN=50.0); commit `fa9f27f9` | Fresh-band verdicts (REQ-038/039) |
| Policy engine | Floors, shield (Σ≤capacity), scaling | `aciq/policy.py`; invariant tests incl. floor-scaling | Measured live fairness (REQ-037) |
| Enforcement | tc htb/tbf/fq_codel netns tree + readback verification | `aciq/harness.py`; `WIRING_AUDIT.md:388` quote | none for mechanism |
| Rollback/failure | txn FAULT ladder, watchdog, known-safe scratch qdisc | `aciq/txn.py`; live root run once (`docs/evidence/rollback-live-20261013.log:14`) | periodic re-validation optional |
| Temporary intent | M7 lease + API/UI | `aciq/intent.py` family; live-lease-in-kernel quote (`WIRING_AUDIT.md:338–345`) | fairness-under-intent outcome (REQ-005 gap) |
| Dashboard | Offline rendering from stored runs; snapshot HTML | `data/experiments/dashboard/dashboard.html` (six metric panels, provenance line; latency series "no data" in snapshot) | populated fresh metrics (REQ-026) |
| Experiment system | Paired-arm runner + results dir + status markers | `run_experiments.py`, `testbed/run_round3_batch.sh`, `aciq/experiment.py` | semantic validation of outputs (Phase 4) |
| Validation tooling | `tools/verify_round3.py`, `verify_dev_band.py`, `reconcile_results.py`, `acceptance.py`, `audit_claims.py`, `secret_scan.py` | committed | dedicated run-artifact validator (ARTIFACT/VALID/PASSING split) does not exist yet — to be built |
| Demo harness | **`tools/host_gate.sh` (405 lines)** + `testbed/demo.sh` | committed; `docs/ACIQ_COMPLETE.md:435–1323` cites committed `data/host_gate_*` runs at revs `ce53da12`, `fc65349e`, `c5da3fd9` | full `demo.sh` end-to-end execution evidence absent (no `demo-*.log`) |

Note for prior audits: "host_gate.sh does not exist" was **wrong** — the file exists at `tools/host_gate.sh`; earlier audits searched `testbed/` only.

## 2. Experiment infrastructure — authoritative census

Band definition (`testbed/run_round3_batch.sh`): dev = 10 scenarios × 3 arms = **30 cells**, 10 seeds each (1000–1009) = 300 seed-runs. Final band (not started, not authorized): 14 sc × 6 arms = **84 cells**, seeds 1100–1109 = 840 seed-runs. No additional dimension exists.

Census **at read time** (marker = `.done` after exit-0; VALID = `result.json` present; contents not yet semantically validated):

| Cell | Dirs | Valid | Marker | Status |
|---|---|---|---|---|
| s2b_step_50 × {aciq, cake_cons, cake_auto} | 10 each | 10 | Y | COMPLETE (×3) |
| s2b_step_10 × {aciq, cake_cons, cake_auto} | 10 | 10 | Y | COMPLETE (×3) |
| s2b_step_up_20to100 × {aciq, cake_cons, cake_auto} | 10 | 10 | Y | COMPLETE (×3) |
| s2b_ramp_100to30 × {aciq, cake_cons} | 10 | 10 | Y | COMPLETE (×2) |
| s2b_ramp_100to30 × cake_auto | 10 | 10 | Y | **COMPLETE (was in-flight; finished since last read)** |
| s7_up_20to60 × aciq | 5 | 4 | – | IN PROGRESS |
| remaining 17 cells | 0 | 0 | – | PENDING |

Totals: **12/30 cells COMPLETE · 1 in progress · 17 pending · 120/300 seed-runs valid · 1 started-no-artifact**. Hygiene steps done: gate, reset_hub, setup_ub.

Resume mechanism: the batch script skips any cell with an existing `.done` marker (`run_round3_batch.sh:60–66`), so re-invoking `./testbed/run_round3_batch.sh dev` after completion of the current tmux run resumes ONLY pending cells; nothing is overwritten. **Do not run it while the current band is live.**

## 3. Documentation inventory

Existing: `docs/architecture.md`, `docs/modules.md`, `docs/limitaions`→`limitations.md`, `docs/setup.md` (Python-version conflict :17 vs :180), `docs/TRACEABILITY.md` (stale counts), `docs/WIRING_AUDIT.md`, `docs/FIX_REPORT.md`, `docs/ACIQ_COMPLETE.md`, `docs/ACIQ_EXPLAINED.md`, `docs/CONCEPTS.md`, `docs/PROJECT*.md`, `docs/licenses.md`, PHASE*_AUDIT/PLAN supplements. Known contradictions: `README.md:9` vs `:130–163` (latency claim), `:37` (stale test count), `:215/:274`; `WIRING_AUDIT.md:33–34` vs `:388`; `demo.sh:21` header ("4 arms", loop = 3).

## 4. Known audit findings carried forward

42 canonical requirements: 21 VERIFIED / 18 PARTIALLY VERIFIED / 2 IMPLEMENTED-BUT-UNVERIFIED (REQ-038, 039) / 1 NOT APPLICABLE (REQ-007) / 0 MISSING — before this effort's Phase 4 refresh (validation of fresh artifacts may move statuses).

Case-study parameters (from the brief): scenarios S1 (ISO download during video call), S2 (WAN drop ~100→~20 Mbps), S3 (TVs + gaming); constraints C1–C13; evaluation E1–E11 (latency/jitter/loss/fairness/stability/CPU/reproducibility/dashboard clarity). Repo thresholds (up-util ≥0.60, down ≤8.0 s, fairness/floor invariants) are ADDITIONAL AUDIT RECOMMENDATIONS, declared in `docs/evidence/round3-params.md` — not to be violated, not to be invented from scratch.

## 5. Remaining work (Stage list)

1. **Stage 2 — result validation (next)**: build `tools/validate_runs.py` (schema-derived: identity/scenario/system/seed match vs `config.json`; provenance; NaN/Inf/negative guards; duration/coverage; status fields) producing `reports/experiment_validation_report.{json,md}` with ARTIFACT-COMPLETE / VALID / PASSING separation.
2. Stage 3–5: fix genuine defects found by validation (if any); complete safe dev experiments (never intersect the live band; resume with the same script afterward); validate every output.
3. Stage 6/9: fresh dashboard metrics from validated runs (do not rebuild UI); bounded demo execution evidence (only in the isolated netns environment, with preflight).
4. Stage 7/8: scenario-based evaluation report (S1/S2/S3 + intent + failure/recovery) using existing arms only.
5. Stage 10: regression suite full run; record exact counts.
6. Stage 11: constants freeze ONLY after dev-band judgment (existing declared discipline).
7. Stage 12: final band (84 cells / 840 seed-runs) only after freeze; not authorized yet.
8. Stage 13/14: traceability + completion matrix refresh; final audit; honest final report.
