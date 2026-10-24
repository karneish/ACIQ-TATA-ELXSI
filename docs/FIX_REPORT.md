# Fix round report (2026-10-23, extended 2026-10-24) — CLOSE VERIFIED GAPS T1–T10

Audit baseline: `docs/evidence/verification/VERIFICATION_REPORT.md`
(21 PASS / 22 PARTIAL / 5 FAIL / 9 NOT VERIFIED). This round closes the
gaps it found, with no new features. Every claim below names its commit.
Status legend: **PASS** = evidence committed from the raw artefacts;
**BLOCKED** = needs the queued privileged step.

## Per-task status

| Task | Fix | Commit(s) | Status |
|---|---|---|---|
| T1 evidence preservation | `!data/experiments/**` unignored; ALL 60 phase-6 artefacts, s1/s3 live matrices, s2/s4 oracle arms, s5 summary, intent run, dashboard evidence committed; incomplete `s3 aciq seed42` dir left DOCUMENTED (root-owned; chown in the queued step repairs it) | `38233a1`, `268ec29`, `c9b6dbb`, live-round commits | PASS (evidence under `data/runs/`, `data/experiments/`) |
| T2 fair CAKE baseline | `SystemSpec.B1_ORACLE`: post-drop rate from t=0, recorded as `oracle_from_start` in config.json; label forbids ORACLE for operator-real claims; `tests/test_cake_arms.py` 5 tests. Live: all four scenarios x 10 seeds ran all four arms | `38233a1` + live | PASS (`data/experiments/RESULTS.md` tables) |
| T3 fair fairness metric | Jain over GENERATOR per-flow rates; **scope fix (this round): per-class minima/starvation restricted to `assigned_classes(workloads)`**, identically every mode — absent classes can no longer print starved-tick rows; baselines' misattributed single-class sheet named in the fallback cell | `578aa89`, `164372b..` | PASS (offline + live series) |
| T4 S1/S3 full-strength + S5 | live: s1/s3 x 4 arms x 10 seeds committed; S4 intent TTL-15s inside 60 s run; S5 live (SIGTERM, SIGKILL, injected failed apply with `verify_s5c.py` witnesses, real-tc watchdog starvation) — `data/experiments/s5/s5_summary.json` says `{"first_apply": true, "mode": "safe_held", "safe_in_force": true, "classes_after_safe": 0}` | `109667c` + live | PASS (live artefacts); intent run RELOCATED off the matrix dir (fix queued: restore seed7 from `a2639c0`) |
| T5 resources | decision-latency ring + `resources` block on every RunResult; live values in the report table (s1 cpu frac 0.0038, s3 0.0043); s2 cell re-fills after the queued rerun regenerates the report | `7504964` | PASS (s1/s3/s4 live); s2 from queued rerun |
| T6 classifier corpus | collector redesigned: one generator pair PER FLOW, distinct dport per flow, 30/class floor ENFORCED (exit non-zero), 3 ambiguous windows; evaluator adds support + plan-universe tables; report declares SPEC GAP verbatim | `24cb91a` | **BLOCKED** — corpus re-collection is the queued privileged step; current committed corpus is the 9-flow one, honestly labelled SPEC GAP |
| T7 report generator | `tools/build_report.py`: reads ONLY raw artefacts; CIs; adaptation measured on the APPLIED tree; resources; honest columns; **delta cells ≥20x print factors, not `−3414%`**; **class-scope fix**; reproduces the audit trio exactly | `34db975`, `c9b6dbb`, this round | PASS (`make report` regenerates bit-identical) |
| T7 entry points | `Makefile` (test/lint/secret-scan/corpus/report/demo-light/demo/setup/teardown/safe-reset/phase5/phase6/s5/live) + `testbed/demo.sh` | `4c0ddbc` | PASS |
| T8 dashboard evidence | `testbed/dashboard_evidence.sh` writes `dashboard.html` + copied samples INTO `data/experiments/dashboard/`; **capture run relocated out of `data/runs` after it clobbered a committed dir**; page audit: zero external URLs | `c6acf90`, `164372b` | PASS (`data/experiments/dashboard/dashboard.html` committed) |
| T9 docs accuracy | `docs/modules.md` real FSMs; `docs/setup.md` host versions; `docs/limitations.md` updated with THIS round's findings (both clobber incidents, class-scope fix, factor display, corpus redesign) | `7cd5cb3`, this round | PASS |
| T10 this report | 1382 tests OK (skipped=10 live-kernel), citation audit 0 broken, secret-scan clean at commit time | this round | PASS |

## What still needs the USER (one command)

```
sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_all_live.sh
```

Run once after the Owner prelude (delete stale resume markers + restore the
matrix seed7 that the intent step once overwrote):

```
sudo chown -R "$USER:$USER" .   # the live runs left root-owned artefacts
git checkout -- data/runs/s2_wan_drop__aciq__adaptive__seed42 testbed/logs/dashboard-evidence.log
git checkout a2639c0 -- data/runs/s4_capacity_recovery__aciq__adaptive__seed7
rm -f data/live_status/corpus.done data/live_status/cleanup.done \
      data/live_status/intent_starvation.done data/live_status/dashboard.done
```

Then the run-all command. It resumes past the completed steps, re-runs the
corpus at full strength (~35–40 min), re-runs the intent step into its own
directory, re-captures dashboard evidence, tears down, and regenerates the
report. Estimated remaining runtime ~50 min. Afterward check `ip netns list` is EMPTY, paste back
the tail of `data/live_status/corpus.log` and
`data/experiments/classifier_corpus/eval.json` head, and commit the
evidence.

## Known-not-fixed (honest)

- S3 `aciq` seed-42 run dir has no result.json/samples.jsonl (root-owned;
  the chown in the prelude repairs this; a note gets written once restorable).
- The s3 capacity estimate is honest-but-loose: the estimator overestimates
  link capacity for the TV+gaming scenario by ~50% in the live runs; the
  report prints it per seed rather than hiding it.
- `tests/test_fairness_live.py` and `tests/test_rollback_live.py` remain
  skipped offline (skipped=10 whole suite) — they are 'live kernel test'
  by design.
- EMULATION framing: all numbers come from a three-namespace netem model;
  nothing here is a deployment measurement (`data/experiments/RESULTS.md`
  says this in the EMULATION section it prints on every run).
