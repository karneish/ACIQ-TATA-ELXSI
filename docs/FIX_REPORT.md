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
| T4 S1/S3 full-strength + S5 | live: s1/s3 x 4 arms x 10 seeds committed; S4 intent TTL-15s inside 60 s run; S5 live (SIGTERM, SIGKILL, injected failed apply with `verify_s5c.py` witnesses, real-tc watchdog starvation) — `data/experiments/s5/s5_summary.json` says `{"first_apply": true, "mode": "safe_held", "safe_in_force": true, "classes_after_safe": 0}` | `109667c` + live | PASS (live artefacts); the intent run is re-run INTO its own dir (fix 13c) with a real lease series, and the seed7 matrix cell is restored from `a2639c0` and unpolluted (n=10) |
| T5 resources | decision-latency ring + `resources` block on every RunResult; live values in the report table (s1 cpu frac 0.0038, s3 0.0043); s2 cell re-fills after the queued rerun regenerates the report | `7504964` | PASS (s1/s3 live); s2/s4 cells honestly `NOT AVAILABLE` — those committed runs predate the instrumentation; a re-run of the s2/s4 ACIQ arms would fill them |
| T6 classifier corpus | collector redesigned: one generator pair PER FLOW, distinct dport per flow, 30/class floor ENFORCED (exit non-zero), 3 ambiguous windows; evaluator adds support + plan-universe tables; report declares SPEC GAP verbatim | `24cb91a`, `f12dbec` | **PASS with declared weakness** — real corpus ran 2026-10-24: 228 flows, per-class floor met; strict held-out accuracy 0.595 over 121 (60.9% full); strong: backup 1.00, bulk 0.87, streaming 0.62, voice 0.60; gaming + software_update NEVER predicted — declared in `eval.json`/`RESULTS.md` as measured (WEAK CLASSES), not tuned around |
| T7 report generator | `tools/build_report.py`: reads ONLY raw artefacts; CIs; adaptation measured on the APPLIED tree; resources; honest columns; **delta cells ≥20x print factors, not `−3414%`**; **class-scope fix**; reproduces the audit trio exactly | `34db975`, `c9b6dbb`, this round | PASS (`make report` regenerates bit-identical) |
| T7 entry points | `Makefile` (test/lint/secret-scan/corpus/report/demo-light/demo/setup/teardown/safe-reset/phase5/phase6/s5/live) + `testbed/demo.sh` | `4c0ddbc` | PASS |
| T8 dashboard evidence | `testbed/dashboard_evidence.sh` writes `dashboard.html` + copied samples INTO `data/experiments/dashboard/`; **capture run relocated out of `data/runs` after it clobbered a committed dir**; page audit: zero external URLs | `c6acf90`, `164372b` | PASS (`data/experiments/dashboard/dashboard.html` committed) |
| T9 docs accuracy | `docs/modules.md` real FSMs; `docs/setup.md` host versions; `docs/limitations.md` updated with THIS round's findings (both clobber incidents, class-scope fix, factor display, corpus redesign) | `7cd5cb3`, this round | PASS |
| T10 this report | 1382 tests OK (skipped=10 live-kernel), citation audit 0 broken, secret-scan clean at commit time | this round | PASS |

## What still needs the USER (one command)

```
sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_all_live.sh
```

Run once after the Owner prelude (delete stale resume markers, restore the
matrix seed7 that the intent step once overwrote, and remove the poisoned
intent dir left by the one aborted attempt): the aborted attempt happened
exactly because deleting only the intent marker let the pipeline SKIP setup
while the testbed was still DOWN; the intent step now builds the testbed
itself and keeps its report inside its own results dir, so neither failure
can recur -- but the stale setup/reset markers must GO for the strict
matrix steps' testbed assumption to hold on this machine too:

```
sudo chown -R "$USER:$USER" .   # the live runs left root-owned artefacts
git checkout -- data/runs/s2_wan_drop__aciq__adaptive__seed42 testbed/logs/dashboard-evidence.log
git checkout a2639c0 -- data/runs/s4_capacity_recovery__aciq__adaptive__seed7
rm -rf data/experiments/intent_starvation
git checkout -- data/REPORT.md  # 1-run rebuild left by the aborted attempt
rm -f data/live_status/reset.done data/live_status/setup.done \
      data/live_status/cleanup.done
rm -f data/live_status/corpus.done data/live_status/intent_starvation.done \
      data/live_status/dashboard.done
```

After the live run (no sudo needed; new intent step keeps its own 1-run
report inside its results dir, so regenerate the matrix REPORT):

```
ACIQ_VENV=/home/mekarz/aciq-venv /home/mekarz/aciq-venv/bin/python \
  run_experiments.py --report-only --report data/REPORT.md
```

Then the run-all command. It resumes past the completed steps, re-runs the
corpus at full strength (~35–40 min), re-runs the intent step into its own
directory, re-captures dashboard evidence, tears down, and regenerates the
report. Estimated remaining runtime ~50 min. Afterward check `ip netns list` is EMPTY, paste back
the tail of `data/live_status/corpus.log` and
`data/experiments/classifier_corpus/eval.json` head, and commit the
evidence.

## Live rerun attempt log (2026-10-24, 09:51) — and its closure

The prelude ran, the rerun ran, and it half-failed in a way that exposed
two deeper defects. Both are now closed with offline tests:

1. The intent step had `--no-setup` while the pipeline (on resume) skips
   its own setup step — the testbed's namespaces were already DOWN, so
   the run aborted instantly at `apply_system` with "Cannot open network
   namespace router". WORSE: the driver recorded the dead run (config +
   result only) and returned **0**, so the pipeline treated the step as
   finished and marched on. Fix (`6412fc3`): the intent step builds the
   testbed itself and keeps its report inside its own results dir.
2. The driver then started corpus, which died within seconds and left
   ONLY `0` in the corpus log: `id -u` had leaked its stdout into the
   log, and Python's print buffering (the `2>&1 | tee` pipe) discarded
   the actual traceback silently. Fix (`94267e8`): failed runs now exit
   1 and REMOVE their incomplete run dir (pinned by
   `tests/test_driver_exit.py`), the corpus step logs setup and runs the
   collector unbuffered, and `id -u` no longer prints to stdout.
3. The driver was also made tolerant of a root-or-no-sudo split
   (`_safe_sudo` in `run_experiments.py`) so its offline dry-run works
   in environments without a sudo binary.
4. With those two fixed, the SECOND rerun (10:16) completed all live
   steps in 36 min — corpus 228 flows at/above the per-class floor
   (6 classes, strict held-out accuracy 0.595 over 121, gaming and
   software_update genuinely weak and so declared), intent run REAL
   (61 samples, lease held 8.0 s of the run, 3/61 enforcement ticks)
   and the s4 seed7 matrix cell unpolluted (n=10) — but it STILL
   clobbered data/REPORT.md once more: the DASHBOARD capture's driver
   call had no --report, so the default (data/REPORT.md) got the
   dashboard's 1-run version. Closed with the same one-line pattern
   (--report inside the evidence dir) and a wiring test pinning it
   (`tests/test_live_wiring.py`); data/REPORT.md was then rebuilt from
   the matrix unprivileged with `run_experiments.py --report-only`.

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

## Headline-failure round (2026-10-24, fix 17) — ACIQ's applied rate never bound

`docs/evidence/fix/diagnosis.md` (commit `ba7636a`) traced the headline
failure (ACIQ s1 call p95 238.89 ms ~ B0's 250.71 vs CAKE-static 1.55,
estimates of 23.8 stuck on a 20 Mbps link) to applied==estimator-belief in
`Harness._adapt_step_inner`, plus a hysteresis test that froze every fall
whose gap was under 0.10/0.6 ~= 16.7% forever. fix 17 closes it:

- `aciq/ratecap.py` (`RateGovernor`): the applied rate is capped at
  `cap_fraction x belief` (0.90 default, configurable 0.50-1.0, chosen
  because the s2/s4 residual estimate error is +9% and 0.90 x 1.09 < 1);
  bottleneck delay (backlog / delivered) above 20 ms ratchets the applied
  rate down 10% per decision even when the estimate is static; after 10 s
  of contiguous clear delay and offered demand > 1.05x applied it probes
  up 2% per decision, always inside the ceiling; at most 6 generated
  changes per rolling minute; every decision logs a reason into
  result.json (`governor.config` + `governor.decisions`) and per-sample
  (`samples.jsonl:governor`). The law is untouched: the governor proposes,
  `bound_rate_change` still disposes (dwell, step, floor, emergency,
  rollback/stand-down intact).
- `aciq/capacity.py`: the hysteresis band is measured against the TARGET
  gap on falls (a 10-16.7% fall now smooths instead of parking the
  estimate at +19% forever); ascents unchanged.
- 19 new tests (`tests/test_rate_governor.py`); suite 1418 OK
  (skipped=10 live-kernel by design). No thresholds were tuned on
  held-out live data; the cap fraction and thresholds are constants
  documented against the diagnosis's measured numbers.
