# Round-2 close-out: claims -> receipts (2026-10-27)

This document ties the six round-2 tasks to committed artefacts. Every
number here is either in a report on disk or in a run dir; nothing is a
promise to measure. Where a claim failed, the failure is the result.

## Task 1 — launch-tree shaping verdict (backlog burst)

Claim: the launch burst was caused by the router's WAN qdisc not being
shaped until the first post-launch tick, not by netem or workload.

Admitted:
- task `testbed/deep_trace.sh` (commit 1aeecbc parent commit 857ce7b family)
  ran three scenarios with concurrent `tc -s qdisc` sweeps on the WAN veth:
  12 one-per-second dumps per run (`*_deep_tcstats.log`, 3 files, 48 sweep
  blocks). At every launch tick the sweep shows `backlog 0b` under the
  corrected launch order — the old 1.25–1.89 MB pre-shaping burst is gone
  (the dumps are the byte-level receipt).
- `aciq/experiment.py` honors INITIAL_PARENT_FRACTION at launch (commit
  eaae0ae), covered by
  `tests/test_experiment.py::TestLaunchShaping` family tests that name the
  dead-code condition this commit removed.

## Task 2 — declared params + provisional classification + fair-leaf guard

Commit eaae0ae. Params for the launch/adaptive paths live in
`docs/evidence/task2-params.md` (declared before the runs that tuned on
them). Regression tests run in the default suite (1483 tests); the audit's
test-name scan enforces cited tests exist.

## Task 3 — S6 two protocol generations, never pooled

Commit 7021797. `tools/build_report.py` splits the legacy (300-309) and
2026 (310-319) S6 generations into separate blocks (`s6_groups`), n=10
t-CIs per generation, per-window before/during/after table, per-arm bulk
recovery, verdicts via `ci_overlap`, and the prose line the reader sees:
the two protocols are never pooled, every cell computed inside one
generation (rendered text is quoted verbatim in
`data/experiments/RESULTS.md`).

## Task 4 — S2b generalization band, evaluation-only

Commit 857ce7b declared scenarios before any run:
`docs/evidence/s2b-params.md` wrote the protocols (100→50, 100→10,
20→100, ramp 100→30 over 20 s), arms, seeds 800→809, metrics, bind rule
and honesty rule BEFORE the first run script existed. The engine shipped
a ramp (`ramp_at_s`/`ramp_duration_s`/`ramp_to_mbps`), and
`run_experiments.py`'s `S2B_PROTOCOLS` is the single source of the
band's protocols. Units 800–809 ran ONCE as evaluation (never tuning).

Defect found by the first band + repair commits (81cd80d, df7a5c4,
31c05ec):

- `oracle_from_start` covered only drop-protocoled scenarios, so the
  20→100 oracle shaped 95% x LAUNCH (19) and the ramp oracle 95% x
  launch (95) — neither is the declared "0.95 x the true FINAL
  capacity, from t=0". Fixed by making the final-capacity chain
  recover_to > drop > ramp_to, and the 20 mis-protocol runs were
  re-taken (`testbed/s2b_repair.sh`, repair log
  `data/live_status_round2/s2b_fix_verify.log`: "rate matches the
  declared final rate on all except 0").
- `samples.jsonl` capacity_mbps carries the LAUNCH link for the CAKE
  arms; the report's applied-error read them for every arm, so CAKE
  rows inherited B0's number. Fixed in the report; CAKE rows read
  `cake_rate_at_apply` (commit 81cd80d).
- ramp bind window: judged AFTER ramp_at + duration (declared rule),
  not from ramp_at.
- `data/runs_s2b` was still gitignored: the band's 160 run dirs
  entered the tree with commit 31c05ec.

Result rows this defect can't be read from anywhere but the live band
(see `data/experiments/RESULTS_S2B.md`, quoted in chat): the up-step is
the honest deploy-relevant failure — 0/10 binds, 84% off truth,
confidence 0.00; the ramp has the best tracking error (3.88±0.83) but
still 0/10 binds.

## Task 5 — S3 per-TV goodput; estimator confidence in the artefact; S5

Commit d12b5a5.

- S3 per-TV delivered goodput per arm (`tv1/tv2/tv3`) comes from each
  TV's own per-second receiver sampler; bands without sampler lines say
  NOT AVAILABLE rather than reusing the sender's pushed rate. Gaming
  p95 remains the dedicated column.
- `estimator_confidence` recorded per tick in `samples.jsonl` (the
  low-confidence claim is checkable from the artefact), surfaced in the
  S2b honesty rows ("confidence 0.10 (n=4)" style).
- S5: `testbed/s5_live.sh` runs the injected-apply case on THREE fresh
  seeds (555-557: arm->rollback 1.03 / 1.03 / 1.02 s, per-seed
  last-good/rollback/recommit stamps), tc/nft dumps under
  `data/experiments/s5/`, real tool versions quoted verbatim in
  `s5_summary.json`, and the summary verdict only passes with 3/3.

## Task 6 — report hygiene

Commit d12b5a5: broad-taxonomy held-out accuracy is the classifier
headline with the narrow figure beside it; the stray empty trailing
`CI overlap?` cells print NOT AVAILABLE; "Where CAKE-static wins" is
driven by the delta arrow so S1's 57.0x appears; `emit_call_obs` gives
a time-resolved per-packet call latency table for bands with --observe
traces (deep runs seeds 210-211) and honest NOT AVAILABLE elsewhere.

## Residual, fixed post-commit (the last artifact repair)

`s5_summary.json` lost a comma because the run that wrote it predates
the renderer fix (the round-2 batch's S5 step ran the pre-commit
script; the comma fix landed AFTER). The root-owned artefact is
repaired syntactically and the S2b report regenerated from the fixed
summary. Audit trail: the DIFF is one character ("," after the
c_repeats array); the content (a/b/c/d verdicts, three repeats, tool
versions) is identical pre/post.

## Verification commands the reader can run offline

    python3 -m unittest discover -s tests -q       # 1483 tests
    make lint                                       # constants + citations
    grep -A9 "### s2b_step_up_20to100" data/experiments/RESULTS_S2B.md
    grep -A9 "### s2b_ramp_100to30"    data/experiments/RESULTS_S2B.md
    ls data/runs_diag/*_deep_tcstats.log
    cat  docs/evidence/s2b-params.md                 # declared BEFORE runs
