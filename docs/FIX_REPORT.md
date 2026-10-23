# Fix round report (2026-10-23) — CLOSE VERIFIED GAPS T1–T10

Audit baseline: `docs/evidence/verification/VERIFICATION_REPORT.md`
(21 PASS / 22 PARTIAL / 5 FAIL / 9 NOT VERIFIED). This round closes the
gaps it found, with no new features. Every claim below names its commit.

## Per-task status

| Task | Fix | Commit(s) | Status |
|---|---|---|---|
| T1 evidence preservation | `!data/experiments/**` unignored; all 60 phase-6 run artefacts + comparison committed; audit `s3_program` incomplete-run gap left DOCUMENTED (dir is root-owned, note below) | `38233a1`, `268ec29`, `c9b6dbb` | done (offline) |
| T2 fair CAKE baseline | `SystemSpec.B1_ORACLE`: post-drop rate from t=0, recorded as `oracle_from_start` in config.json; label forbids ORACLE for operator-real claims; `tests/test_cake_arms.py` 5 tests | `38233a1` | done (offline) |
| T3 fair fairness metric | `aciq/fairness.py`: Jain over GENERATOR per-flow rates (works across tree shapes); per-class series stay ACIQ-only; starved-ticks phrasing from real timestamps | `578aa89` | done (offline) |
| T4 S5 failed-apply | `TransactionManager.inject_failed_apply_once`: one-shot kernel-level failure (`class add`), rollback through live commands; `--inject-fail-apply` on the CLI triggers at mid-run and notes it | `cdf8943` | code done; live prove in `run_all_live.sh` s5 step, `tools/verify_s5c.py` checks 3 witnesses from artefacts |
| T5 resources | decision-latency ring + `resources` block (cpu_mean_frac, decision_ms n/p50/p95/max, rss_max) on every RunResult; `tests/test_resources.py` | `7504964` | done (offline) |
| T6 classifier corpus | `tools/gen_corpus.py` (router vantage, conntrack-only) + `tools/eval_corpus.py` (tuple split, thresholds FIXED pre-corpus, strict + abstention tables + confusion) + `tests/test_eval_corpus.py` 7 tests | `4c0ddbc` | offline done; corpus itself needs the live step (`make corpus-collect`) |
| T7 report generator | `tools/build_report.py`: reads ONLY raw run artefacts; t(9)=2.262 CIs; adaptation measured on the APPLIED tree (capacity_mbps), estimate-error table, resources table, where-ACIQ-is-worse table, classification and safe-state sections from the live steps' own outputs | `34db975`, `c9b6dbb` | done (offline); reproduces S2 trio 248.96/89.55/98.11 exactly |
| T7 entry points | `Makefile` (test/lint/secret-scan/corpus/report/demo-light/demo/setup/teardown/safe-reset/phase5/phase6/s5/live) + `testbed/demo.sh` | `4c0ddbc` | done |
| T8 dashboard evidence | `testbed/dashboard_evidence.sh` -> writes `dashboard.html` + copied samples INTO `data/experiments/dashboard/` (a live-only artefact, audit-exempt); page audit: zero external URLs | `c6acf90` | needs live run (in `run_all_live.sh`) |
| T9 docs accuracy | `docs/modules.md` written from the actual FSMs (4-state controller + 3-state shield; 7-state policy-engine doc explicitly de-scoped); `docs/setup.md` host versions (kernel 7.1.5-76070105, iproute2 6.1.0, nft 1.0.9, iperf3 3.16, pyroute2 0.9.6); oracle-arm CLI; `docs/limitations.md` CAKE-static-does-not-adapt-by-design + S3-dir note; family-prefix citation bug found and FIXED in `tools/audit_claims.py` itself | `7cd5cb3` | done |
| T10 this report | full suite + citation audit + secret scan green before commit, per-task commits | this round | done |

## What still needs the USER (one command)

```
sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_all_live.sh
```

Runs, in order, resuming on re-invocation via `data/live_status/`. All ~3 h:
1. gate
2. four-arm matrices (b0, cake95, cake-ORACLE, aciq) x 10 seeds — s2/s4
   baseline runs already exist, so only the ORACLE arm + s1/s3 with full
   seed counts
3. S4 intent+expiry (TTL 15 s inside the 60 s run), which also collects
   the starvation-under-intent evidence T3 lacked
4. S5 live (SIGTERM residue, SIGKILL residue then cleanup, injected
   failed apply with `verify_s5c.py` witnesses, watchdog starvation
   though real tc) — `data/experiments/s5/s5_summary.json`
5. classifier corpus gen + offline eval (thresholds fixed pre-corpus)
6. dashboard evidence
7. clean teardown + offline `data/experiments/RESULTS.md` and citation audit

## Known-not-fixed (honest)

- S3 `aciq` seed-42 run dir has no result.json/samples.jsonl; because the
  dir is owned by `nfsnobody`, no note file can be placed IN the dir.
- Command injection / actual kernel interference with the oracle arm CAN
  NOT be proved before real runs; all oracle-arm artefacts labelled above
  must be re-read after the live step.
- `tests/test_fairness_live.py` and `tests/test_rollback_live.py` remain
  skipped offline (skipped=10 whole suite) — they are 'live kernel test'
  by design.
- EMULATION framing: all numbers come from a three-namespace netem model;
  nothing here is a deployment measurement (`data/experiments/RESULTS.md`
  says this in the EMULATION section it prints on every run).
