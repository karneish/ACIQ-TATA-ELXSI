# Complete TODO list (T1–T9) — ACIQ verified audit closure

Last updated: after fix 18 (72527c5), full suite 1442 OK (skipped=10), make lint clean.

## Status overview
- T1: DONE — docs/evidence/fix/diagnosis.md (committed ba7636a)
- T2: DONE — RateGovernor + hysteresis gap fix + harness wiring + floor_total_mbps (committed 2ea4718), 19 tests
- T3: DONE — demand-normalized fairness, 1.05× bind on applied tree, post-drop-only bulk, baseline aggregate relabel + warm-up exclusion + seeded start offsets (committed 72527c5), metrics tests added
- T4–T8: SCRIPT READY — testbed/run_live_fix.sh (batched privileged, resume via data/live_status_fix/*.done, cleanup/netns check). Requires sudo + kernel/netns on target host.
- T9: PENDING (live evidence + final regen + runbook)

## Detailed checklist

### T1 — Offline diagnosis
- [x] Reproduce mismatch: applied==belief, headroom never used (harness.py:996 path traced)
- [x] Bottleneck: netem backlog/GRO burst -> 238 ms; overhead ~0.937; estimator caps/bias
- [x] Hysteresis/step/clamp/dwell/min-rate/eemrgency traced
- [x] S1 0.36ms (CAKE95) vs 238ms (ACIQ) explanation documented (topology/class mapping)
- [x] Deliver docs/evidence/fix/diagnosis.md

### T2 — Controller fix
- [x] Implement RateGovernor (aciq/ratecap.py) with cap_fraction 0.90, delay probe 20ms up / 10ms clear, hold 10s, down 10% min-vs-applied, up 2% gated, budget 6/min, delay None => ceiling-only, first ceiling free
- [x] Fix hysteresis to judge falls on raw TARGET gap (aciq/capacity.py)
- [x] Wire governor in harness (_adapt_step_inner), log to policy_change_log, expose RunResult.governor, sample governor evidence
- [x] floor_total_mbps (aciq/policy.py) for governor min
- [x] Unit tests tests/test_rate_governor.py (19), full suite green
- [x] Commit fix 17 (2ea4718)

### T3 — Metrics
- [x] Bind-time: bind_time() 1.05× on applied tree (tools/build_report.py), replace loose 1.25×, report regen
- [x] Post-drop-only bulk: post_drop_bulk_mbps with per-class counters (ACIQ bulk_download, baselines aggregate leaf with legacy fallback), delta in drop scenarios
- [x] Demand-normalized fairness: flow_satisfactions/run_demand_fairness (video ladder + pps_requested), elastic excluded, Jain over satisfactions; columns added
- [x] Symmetric per-class series: BASELINE_HANDLE_MAP labels 1:50 as unknown (aciq/metrics.py), experiment wired, legacy fallback declared
- [x] Warm-up exclusion t<2.0s (WARMUP_S) applied to per-tick minima/starvation/post-drop + declared
- [x] Seed variance: per-flow 0–1s start offsets from seed (aciq/experiment.py), recorded in result notes; UDP loss/jitter unseeded (documented)
- [x] Tests + report regen + commit fix 18 (72527c5)

### T4 — Rerun S1–S4 ACIQ (10 new seeds)
- [ ] Execute testbed/run_live_fix.sh (or equivalent) to add S1–S4 all four arms with seeds 200–209
- [ ] Verify ACIQ binds post-drop: bind_time ≤ 1.05× post-drop on new runs
- [ ] Compare S1 call p95 vs CAKE-static, S2/S4 post-drop vs CAKE-oracle (report honestly)
- [ ] Regenerate data/experiments/RESULTS.md/html + update FIX_REPORT

### T5 — S6 intent scenario live
- [ ] Run intent_starvation or equivalent with enforcement + lease (TTL expiry) via batched script
- [ ] Verify auto-revert/safe floors; record time-to-safe and policy_change_log
- [ ] ARM comparison included in report

### T6 — S3 realism
- [ ] Apply S3 scenario changes (3 TV + gaming + background) if not already done
- [ ] Rerun S3 all four arms post-change (batch step t6_s3_*_rerun)
- [ ] Verify B0 visible gaming delay, unsaturated estimator low confidence documented

### T7 — Classifier metrics
- [ ] Apply DEV-split fixes; run fresh held-out corpus (testbed/corpus_live.sh)
- [ ] Ensure per-class P/R/F1, calibration bins, confidently-wrong, unknown class reported
- [ ] Split evidence/docs + corpus eval sets as required
- [ ] No tuning on held-out; weak classes declared

### T7b — Report classifier from evidence
- [ ] tools/build_report.py reads classifier_corpus/eval.json + counts.json verbatim (already implemented) and declares gaps

### T8 — S5 + resources + dashboard
- [ ] S5: SIGTERM/SIGKILL/injected failed apply, tc/nft dumps, time-to-safe, 3 repeats
- [ ] Resources filled for S2/S4/S6 adaptive runs
- [ ] Dashboard snapshot + no-external-URLs check (dashboard_evidence.sh)

### T9 — Final report + runbook
- [ ] Regenerate RESULTS.md/html from all new runs
- [ ] Update docs/FIX_REPORT.md with T4–T8 evidence (numbers, pass/fail, oracle caveat)
- [ ] Add runbook / exact user command block (copy/paste) showing how to reproduce verified flow
- [ ] Final git commit of live artefacts + report updates
