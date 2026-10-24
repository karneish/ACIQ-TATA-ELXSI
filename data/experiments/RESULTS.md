# Results (generated, no summarised files consulted)

Runs root: `/home/mekarz/Desktop/Full-projects/TATA-ELXSI/data/runs` | runs used: 160 | scenarios: s1_iso_during_call, s2_wan_drop, s3_tv_and_gaming, s4_capacity_recovery

## Delay and throughput, every scenario x arm (mean +/- 95% CI over seeds; t(9)=2.262 for n=10)

### s1_iso_during_call

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.67 +/- 0.03 | 3.09 +/- 0.03 | 0.766 +/- 0.025 | NOT AVAILABLE | 96.29 +/- 0.00 | (no drop scenario) | 0.909 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.45 +/- 0.01 | 0.45 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 90.96 +/- 0.00 | (no drop scenario) | 0.922 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 1.45 +/- 0.01 | 0.44 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 90.96 +/- 0.00 | (no drop scenario) | 0.922 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 82.49 +/- 0.49 | 0.61 +/- 0.05 | 0.180 +/- 0.060 | NOT AVAILABLE | 86.22 +/- 0.93 | (no drop scenario) | 0.934 +/- 0.002 | NOT AVAILABLE |

### s2_wan_drop

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 251.28 +/- 0.09 | 4.36 +/- 0.06 | 8.710 +/- 0.323 | NOT AVAILABLE | 79.58 +/- 0.01 | 29.04 +/- 0.04 | 0.950 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 70.31 +/- 1.73 | 0.51 +/- 0.01 | 0.160 +/- 0.015 | NOT AVAILABLE | 75.17 +/- 0.04 | 25.37 +/- 0.05 | 0.961 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 2.33 +/- 0.03 | 0.31 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.09 +/- 0.00 | 17.03 +/- 0.05 | 0.820 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 73.60 +/- 2.48 | 0.63 +/- 0.03 | 0.265 +/- 0.041 | NOT AVAILABLE | 71.69 +/- 0.58 | 0.00 +/- 0.00 | 0.969 +/- 0.001 | NOT AVAILABLE |

### s3_tv_and_gaming

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 3.19 +/- 0.13 | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.33 +/- 0.25 | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.41 +/- 0.17 | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.37 +/- 0.11 | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |

### s4_capacity_recovery

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.43 +/- 0.06 | 3.05 +/- 0.02 | 6.017 +/- 0.155 | NOT AVAILABLE | 59.45 +/- 0.01 | 23.10 +/- 0.02 | 0.993 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 89.73 +/- 1.08 | 0.63 +/- 0.02 | 0.197 +/- 0.052 | NOT AVAILABLE | 56.51 +/- 0.02 | 21.84 +/- 0.01 | 0.996 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 2.74 +/- 0.03 | 0.48 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.08 +/- 0.00 | 18.18 +/- 0.00 | 0.820 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 95.74 +/- 0.90 | 0.73 +/- 0.01 | 0.280 +/- 0.023 | NOT AVAILABLE | 53.88 +/- 0.08 | 0.00 +/- 0.00 | 0.999 +/- 0.000 | NOT AVAILABLE |

## ACIQ vs every arm (positive % is better ACIQ on the metric at the head of the column; a cell like `41.0x` is the multiplicative factor when the baseline is so close to zero that a percentage would mislead)

| scenario | vs arm | call p95 delta % | CI overlap? | bulk delta % | CI overlap? |
| --- | --- | --- | --- | --- | --- |
Bulk compares are POST-DROP ONLY in scenarios with a capacity drop (same `bulk_mbps` whole-run mean otherwise): the whole-run number dilutes the post-drop regime with a saturated prefix, which is the opposite of the decision those scenarios exist to measure.

| s1_iso_during_call | B0 (default router, pfifo) | +67.1 | disjoint | NOT AVAILABLE |  |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | 57.0x | disjoint | NOT AVAILABLE |  |
| s1_iso_during_call | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 56.7x | disjoint | NOT AVAILABLE |  |
| s2_wan_drop | B0 (default router, pfifo) | +70.7 | disjoint | -100.0% | disjoint |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | -4.7 | overlap | -100.0% | disjoint |
| s2_wan_drop | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 31.6x | disjoint | -100.0% | disjoint |
| s3_tv_and_gaming | B0 (default router, pfifo) | NOT AVAILABLE |  | NOT AVAILABLE |  |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | NOT AVAILABLE |  | NOT AVAILABLE |  |
| s3_tv_and_gaming | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | NOT AVAILABLE |  | NOT AVAILABLE |  |
| s4_capacity_recovery | B0 (default router, pfifo) | +61.8 | disjoint | -100.0% | disjoint |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | -6.7 | disjoint | -100.0% | disjoint |
| s4_capacity_recovery | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 35.0x | disjoint | -100.0% | disjoint |

## Where ACIQ is worse (the honest column)

Every row above where ACIQ's signed delta is negative, collected so a CAKE win cannot hide behind the aggregate. Empty means no such pair exists in the runs found.

| scenario | vs arm | metric where ACIQ is worse |
| --- | --- | --- |
| s2_wan_drop | B0 (default router, pfifo) | post-drop bulk Mbps |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | call p95 and post-drop bulk Mbps |
| s2_wan_drop | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | post-drop bulk Mbps |
| s4_capacity_recovery | B0 (default router, pfifo) | post-drop bulk Mbps |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | call p95 and post-drop bulk Mbps |
| s4_capacity_recovery | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | post-drop bulk Mbps |

## ACIQ adaptation and capacity accuracy (from the same runs above)

| scenario | n | bind: drop -> first applied <=1.05x post-drop (s) | bind: drop -> first applied <=1.25x post-drop (s) | final estimate | configured end link | estimate error % |
| --- | --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 95.73 +/- 0.08 | 100.0 +/- 0.0 | mean abs 4.3% (seed0: 95.61/100.0 (4.4% off)) |
| s2_wan_drop | 10 | 1.72 (n=10) | 1.72 (n=10) | 21.45 +/- 0.11 | 20.0 +/- 0.0 | mean abs 7.3% (seed0: 21.59/20.0 (7.9% off)) |
| s3_tv_and_gaming | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 56.23 +/- 13.96 | 100.0 +/- 0.0 | mean abs 43.8% (seed0: 59.04/100.0 (41.0% off)) |
| s4_capacity_recovery | 10 | 1.85 (n=10) | 1.85 (n=10) | 21.35 +/- 0.25 | 20.0 +/- 0.0 | mean abs 6.7% (seed0: 21.52/20.0 (7.6% off)) |
## Controller resources (ACIQ adaptive runs only; from each result's resources block)

| scenario | n | cpu mean frac | decision p95 ms | decision max ms | max RSS bytes |
| --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | 10 | 0.0042 +/- 0.0001 | 37.29 +/- 18.57 | 76.59 +/- 2.65 | 20649574 +/- 384796 |
| s2_wan_drop | 10 | 0.0043 +/- 0.0001 | 59.97 +/- 17.01 | 75.82 +/- 2.43 | 20893286 +/- 406731 |
| s3_tv_and_gaming | 10 | 0.0043 +/- 0.0002 | 74.32 +/- 1.15 | 77.82 +/- 2.49 | 20952678 +/- 397623 |
| s4_capacity_recovery | 10 | 0.0045 +/- 0.0001 | 14.88 +/- 2.76 | 80.21 +/- 1.23 | 21629338 +/- 590585 |

## Fairness detail (workload-rate Jain; per-class minima over ASSIGNED classes only, same scope for every mode)

| scenario | arm | n | jain mean +/- CI | demand-jain mean +/- CI | flows used | min over time (classes+ticks) |
| --- | --- | --- | --- | --- | --- | --- |
demand-jain: Jain over per-flow satisfied-demand ratios (achieved/demand, demand self-reported by the generator; elastic flows without a declared demand are excluded by definition -- see aciq/fairness.py). A scenario flows all-elastic has no such index and prints NOT AVAILABLE rather than a substitute.

Per-tick counter attribution (fix 18): ACIQ's tree has one leaf per class; the baselines' single-class tree carries the WHOLE link on the 1:50 leaf. New artefacts sample that aggregate under `unknown` (an aggregate can no longer masquerade as a software_update class); artefacts from before this change stored the same aggregate under `software_update`, and consumers that fall back to the legacy label must name it -- the post-drop bulk column does exactly that.

| s1_iso_during_call | B0 (default router, pfifo) | 10 | 0.909 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | NOT AVAILABLE (no assigned-class series in this arm's samples) |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.922 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | NOT AVAILABLE (no assigned-class series in this arm's samples) |
| s1_iso_during_call | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.922 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | NOT AVAILABLE (no assigned-class series in this arm's samples) |
| s1_iso_during_call | ACIQ (controller) | 10 | 0.934 +/- 0.002 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk_download=0; video_call_voice=0; bulk_download=0; video_call_voice=0; bulk_download=0; video_call_voice=0 |
| s2_wan_drop | B0 (default router, pfifo) | 10 | 0.950 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | NOT AVAILABLE (no assigned-class series in this arm's samples) |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.961 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | NOT AVAILABLE (no assigned-class series in this arm's samples) |
| s2_wan_drop | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.820 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | NOT AVAILABLE (no assigned-class series in this arm's samples) |
| s2_wan_drop | ACIQ (controller) | 10 | 0.969 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk_download=0; video_call_voice=0; bulk_download=0; video_call_voice=0; bulk_download=0; video_call_voice=0 |
| s3_tv_and_gaming | B0 (default router, pfifo) | 10 | 0.510 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | NOT AVAILABLE (no assigned-class series in this arm's samples) |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.510 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | NOT AVAILABLE (no assigned-class series in this arm's samples) |
| s3_tv_and_gaming | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.510 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | NOT AVAILABLE (no assigned-class series in this arm's samples) |
| s3_tv_and_gaming | ACIQ (controller) | 10 | 0.510 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | adaptive_video_streaming=0; interactive_gaming=0; adaptive_video_streaming=0; interactive_gaming=0; adaptive_video_streaming=0; interactive_gaming=0 |
| s4_capacity_recovery | B0 (default router, pfifo) | 10 | 0.993 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | NOT AVAILABLE (no assigned-class series in this arm's samples) |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.996 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | NOT AVAILABLE (no assigned-class series in this arm's samples) |
| s4_capacity_recovery | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.820 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | NOT AVAILABLE (no assigned-class series in this arm's samples) |
| s4_capacity_recovery | ACIQ (controller) | 10 | 0.999 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk_download=0; video_call_voice=0; bulk_download=0; video_call_voice=0; bulk_download=0; video_call_voice=0 |

Starvation: a class starved in tick t if its per-tick goodput fell below 20% of its own run median (threshold computed from the run's own series); the cell lists the starved timestamps. Only ASSIGNED classes are considered — a class the scenario never gave traffic to cannot be starved in it.

| scenario | arm | starved ticks per class |
| --- | --- | --- |
| s1_iso_during_call | B0 (default router, pfifo) | (none) |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | (none) |
| s1_iso_during_call | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | (none) |
| s1_iso_during_call | ACIQ (controller) | bulk_download: 29 ticks (first t=2.0); video_call_voice: 4 ticks (first t=3.1); bulk_download: 29 ticks (first t=2.0); video_call_voice: 4 ticks (first t=3.1); bulk_download: 29 ticks (first t=2.0); video_call_voice: 4 ticks (first t=3.1); bulk_download: 29 ticks (first t=2.0); video_call_voice: 4 ticks (first t=3.1) |
| s2_wan_drop | B0 (default router, pfifo) | (none) |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | (none) |
| s2_wan_drop | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | (none) |
| s2_wan_drop | ACIQ (controller) | bulk_download: 39 ticks (first t=2.0); video_call_voice: 5 ticks (first t=3.1); bulk_download: 39 ticks (first t=2.0); video_call_voice: 5 ticks (first t=3.1); bulk_download: 39 ticks (first t=2.0); video_call_voice: 5 ticks (first t=3.1); bulk_download: 39 ticks (first t=2.0); video_call_voice: 5 ticks (first t=3.1) |
| s3_tv_and_gaming | B0 (default router, pfifo) | (none) |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | (none) |
| s3_tv_and_gaming | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | (none) |
| s3_tv_and_gaming | ACIQ (controller) | adaptive_video_streaming: 39 ticks (first t=2.0); interactive_gaming: 39 ticks (first t=2.0); adaptive_video_streaming: 39 ticks (first t=2.0); interactive_gaming: 39 ticks (first t=2.0); adaptive_video_streaming: 39 ticks (first t=2.0); interactive_gaming: 39 ticks (first t=2.0); adaptive_video_streaming: 39 ticks (first t=2.0); interactive_gaming: 39 ticks (first t=2.0) |
| s4_capacity_recovery | B0 (default router, pfifo) | (none) |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | (none) |
| s4_capacity_recovery | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | (none) |
| s4_capacity_recovery | ACIQ (controller) | bulk_download: 59 ticks (first t=2.0); video_call_voice: 5 ticks (first t=3.1); bulk_download: 59 ticks (first t=2.0); video_call_voice: 5 ticks (first t=3.1); bulk_download: 59 ticks (first t=2.0); video_call_voice: 6 ticks (first t=3.1); bulk_download: 59 ticks (first t=2.0); video_call_voice: 6 ticks (first t=3.1) |

Warm-up exclusion (declared): every per-tick window above starts at t >= 2.0 s. The diagnosis round (fix 17's diagnosis.md) shows the first ~2 s of per-tick counter rates are a transmit/counter ramp artefact, not traffic behaviour; dropping those ticks removes nothing else. The window boundary is a declared constant in this generator, not a per-run choice.

## Classifier (router-vantage corpus, thresholds fixed before held-out)

- strict: `{"n": 228, "correct": 139, "abstained": 0, "confident_or_wrong": 89, "accuracy_strict": 0.6096491228070176, "accuracy_excl_abstain": 0.6096491228070176}`
- accept_abstain: `{"n": 228, "correct": 139, "abstained": 0, "confident_or_wrong": 89, "accuracy_strict": 0.6096491228070176, "accuracy_excl_abstain": 0.6096491228070176}`
- paths_fixed: `["aciq/classify.py", "aciq/features.py"]`
- n_corpus: `228`
- n_heldout: `106`
- per-class floor 30: met (counts: `{"video_call_voice": 30, "interactive_gaming": 30, "adaptive_video_streaming": 49, "bulk_download": 40, "software_update": 49, "cloud_backup": 30}`)

Source: `/home/mekarz/Desktop/Full-projects/TATA-ELXSI/data/experiments/classifier_corpus/eval.json` (written by the corpus evaluator, whose failure table is copied verbatim).

## Safe-state and failure injection (S5)

- a_sigterm_no_filter_residue: `"PASS"`
- b_sigkill_residue_then_cleanup: `"PASS"`
- c_injected_failed_apply_rollbacks: `"FAIL"`
- d_watchdog_starve_reaches_safe: `"PASS"`
- host: `"/home/mekarz/aciq-venv/bin/python -V"`
- notes: `"values PASS/FAIL only; the report quotes this file verbatim"`

## EMULATION statement (what is modelled, what is not)

All runs on this host are emulation: one router namespace, its LAN/WAN veth pair, an out-of-band bottleneck (netem with a token bucket limiter on the WAN side) and workload generators in their own netns. There are no physical links, no real video stacks and no third-party traffic; delay/jitter/loss via probes are generator-reported for the transmission path only. No number in this report should be read as an ISP deployment result; the controller's own classification, control loop and translation through tc are the subsystems under test.

