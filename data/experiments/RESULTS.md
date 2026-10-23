# Results (generated, no summarised files consulted)

Runs root: `/home/mekarz/Desktop/Full-projects/TATA-ELXSI/data/runs` | runs used: 65 | scenarios: s1_iso_during_call, s2_wan_drop, s3_tv_and_gaming, s4_capacity_recovery

Skipped 1 incomplete-only directory names: `s3_tv_and_gaming__aciq__adaptive__seed42 (missing config.json or workloads.json)`

- skipped dir: s3_tv_and_gaming__aciq__adaptive__seed42 (missing config.json or workloads.json)

## Delay and throughput, every scenario x arm (mean +/- 95% CI over seeds; t(9)=2.262 for n=10)

### s1_iso_during_call

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps | jain (workload-rate Jain) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 1 | 120.26 | 0.56 | 0.333 | NOT AVAILABLE | 96.30 | 0.909 |
| CAKE-static (95% of pre-drop link, set and forget) | 1 | 0.43 | 0.32 | 0.000 | NOT AVAILABLE | 90.90 | 0.922 |
| ACIQ (controller) | 1 | 0.36 | 0.09 | 0.000 | NOT AVAILABLE | 95.73 | 0.910 |

### s2_wan_drop

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps | jain (workload-rate Jain) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 248.96 +/- 0.73 | 2.89 +/- 0.25 | 9.095 +/- 0.197 | NOT AVAILABLE | 41.18 +/- 0.03 | 0.991 +/- 0.000 |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 89.55 +/- 0.96 | 0.69 +/- 0.02 | 0.380 +/- 0.081 | NOT AVAILABLE | 39.06 +/- 0.03 | 0.985 +/- 0.000 |
| ACIQ (controller) | 10 | 98.11 +/- 1.70 | 0.88 +/- 0.04 | 0.380 +/- 0.113 | NOT AVAILABLE | 39.48 +/- 0.07 | 0.986 +/- 0.000 |

### s3_tv_and_gaming

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps | jain (workload-rate Jain) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 1 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 33.46 | NOT AVAILABLE | 0.508 |
| CAKE-static (95% of pre-drop link, set and forget) | 1 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 0.67 | NOT AVAILABLE | 0.508 |

### s4_capacity_recovery

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps | jain (workload-rate Jain) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 245.07 +/- 0.18 | 2.06 +/- 0.01 | 6.127 +/- 0.088 | NOT AVAILABLE | 33.78 +/- 0.01 | 0.964 +/- 0.000 |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 89.95 +/- 0.46 | 0.84 +/- 0.29 | 0.407 +/- 0.367 | NOT AVAILABLE | 32.38 +/- 0.01 | 0.956 +/- 0.000 |
| ACIQ (controller) | 10 | 96.87 +/- 1.09 | 0.88 +/- 0.02 | 0.363 +/- 0.054 | NOT AVAILABLE | 32.65 +/- 0.05 | 0.958 +/- 0.000 |

## ACIQ vs every arm (positive % is better ACIQ on the metric at the head of the column)

| scenario | vs arm | call p95 delta % | CI overlap? | bulk delta % | CI overlap? |
| --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | B0 (default router, pfifo) | +99.7 | no CI (n<2) | -0.6 | no CI (n<2) |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | +16.3 | no CI (n<2) | +5.3 | no CI (n<2) |
| s2_wan_drop | B0 (default router, pfifo) | +60.6 | disjoint | -4.1 | disjoint |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | -9.5 | disjoint | +1.1 | disjoint |
| s3_tv_and_gaming | B0 (default router, pfifo) | NOT AVAILABLE |  | NOT AVAILABLE |  |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | NOT AVAILABLE |  | NOT AVAILABLE |  |
| s4_capacity_recovery | B0 (default router, pfifo) | +60.5 | disjoint | -3.3 | disjoint |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | -7.7 | disjoint | +0.8 | disjoint |

## Where ACIQ is worse (the honest column)

Every row above where ACIQ's signed delta is negative, collected so a CAKE win cannot hide behind the aggregate. Empty means no such pair exists in the runs found.

| scenario | vs arm | metric where ACIQ is worse |
| --- | --- | --- |
| s1_iso_during_call | B0 (default router, pfifo) | bulk Mbps |
| s2_wan_drop | B0 (default router, pfifo) | bulk Mbps |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | call p95 |
| s4_capacity_recovery | B0 (default router, pfifo) | bulk Mbps |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | call p95 |

## ACIQ adaptation and capacity accuracy (from the same runs above)

| scenario | n | adaptation: drop -> first applied <=1.25x post-drop (s) | final estimate | configured end link | estimate error % |
| --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | 1 | no post-drop applied tree at/below 1.25x post-drop link in any seed | 100.75 | 100.0 | mean abs 0.8% (seed0: 100.75/100.0 (0.8% off)) |
| s2_wan_drop | 10 | 1.68 (n=10) | 23.59 +/- 0.17 | 20.0 +/- 0.0 | mean abs 17.9% (seed0: 23.33/20.0 (16.6% off)) |
| s4_capacity_recovery | 10 | 1.67 (n=10) | 23.55 +/- 0.24 | 20.0 +/- 0.0 | mean abs 17.8% (seed0: 23.23/20.0 (16.2% off)) |

Adaptation is defined on the applied tree (`capacity_mbps` in samples.jsonl), not on the estimator's belief, so a controller that estimates right but applies slow counts as slow.

## Controller resources (ACIQ adaptive runs only; from each result's resources block)

| scenario | n | cpu mean frac | decision p95 ms | decision max ms | max RSS bytes |
| --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | 1 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s2_wan_drop | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s4_capacity_recovery | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |

NOT AVAILABLE (no run in this root carries a resources block; resources appear with the live four-arm matrix)

## Fairness detail (workload-rate Jain; per-class series from ACIQ samples where present)

| scenario | arm | n | jain mean +/- CI | flows used | min over time (classes+ticks) |
| --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | B0 (default router, pfifo) | 1 | 0.909 | 2.0 | NOT AVAILABLE (no samples in run dirs) |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | 1 | 0.922 | 2.0 | NOT AVAILABLE (no samples in run dirs) |
| s1_iso_during_call | ACIQ (controller) | 1 | 0.910 | 2.0 | adaptive_video=0; bulk_transfer=0; realtime_interactive=0 |
| s2_wan_drop | B0 (default router, pfifo) | 10 | 0.991 +/- 0.000 | 2.0 +/- 0.0 | software_update=0; software_update=0; software_update=0; software_update=0; software_update=0; software_update=0 |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.985 +/- 0.000 | 2.0 +/- 0.0 | software_update=0; software_update=0; software_update=0; software_update=0; software_update=0; software_update=0 |
| s2_wan_drop | ACIQ (controller) | 10 | 0.986 +/- 0.000 | 2.0 +/- 0.0 | adaptive_video_streaming=0; bulk_download=0; cloud_backup=0; interactive_gaming=0; software_update=0; unknown=0 |
| s3_tv_and_gaming | B0 (default router, pfifo) | 1 | 0.508 | 4.0 | NOT AVAILABLE (no samples in run dirs) |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | 1 | 0.508 | 4.0 | NOT AVAILABLE (no samples in run dirs) |
| s4_capacity_recovery | B0 (default router, pfifo) | 10 | 0.964 +/- 0.000 | 2.0 +/- 0.0 | software_update=0; software_update=0; software_update=0; software_update=0; software_update=0; software_update=0 |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.956 +/- 0.000 | 2.0 +/- 0.0 | software_update=0; software_update=0; software_update=0; software_update=0; software_update=0; software_update=0 |
| s4_capacity_recovery | ACIQ (controller) | 10 | 0.958 +/- 0.000 | 2.0 +/- 0.0 | adaptive_video_streaming=0; bulk_download=0; cloud_backup=0; interactive_gaming=0; software_update=0; unknown=0 |

Starvation: a class starved in tick t if its per-tick goodput fell below 20% of its own run median (threshold computed from the run's own series); the cell lists the starved timestamps.

| scenario | arm | starved ticks per class |
| --- | --- | --- |
| s1_iso_during_call | B0 (default router, pfifo) | (none) |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | (none) |
| s1_iso_during_call | ACIQ (controller) | adaptive_video: 31 ticks (first t=0.0); bulk_transfer: 2 ticks (first t=0.0); realtime_interactive: 2 ticks (first t=0.0) |
| s2_wan_drop | B0 (default router, pfifo) | software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0) |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | software_update: 1 ticks (first t=0.0); software_update: 2 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 2 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 2 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0) |
| s2_wan_drop | ACIQ (controller) | adaptive_video_streaming: 41 ticks (first t=0.0); bulk_download: 5 ticks (first t=0.0); cloud_backup: 41 ticks (first t=0.0); interactive_gaming: 41 ticks (first t=0.0); software_update: 41 ticks (first t=0.0); unknown: 37 ticks (first t=0.0); video_call_voice: 6 ticks (first t=0.0); adaptive_video_streaming: 41 ticks (first t=0.0) |
| s3_tv_and_gaming | B0 (default router, pfifo) | (none) |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | (none) |
| s4_capacity_recovery | B0 (default router, pfifo) | software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0); software_update: 1 ticks (first t=0.0) |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | software_update: 2 ticks (first t=0.0); software_update: 2 ticks (first t=0.0); software_update: 2 ticks (first t=0.0); software_update: 2 ticks (first t=0.0); software_update: 2 ticks (first t=0.0); software_update: 2 ticks (first t=0.0); software_update: 2 ticks (first t=0.0); software_update: 2 ticks (first t=0.0) |
| s4_capacity_recovery | ACIQ (controller) | adaptive_video_streaming: 61 ticks (first t=0.0); bulk_download: 6 ticks (first t=0.0); cloud_backup: 61 ticks (first t=0.0); interactive_gaming: 61 ticks (first t=0.0); software_update: 61 ticks (first t=0.0); unknown: 56 ticks (first t=0.0); video_call_voice: 7 ticks (first t=0.0); adaptive_video_streaming: 61 ticks (first t=0.0) |

## Classifier (router-vantage corpus, thresholds fixed before held-out)

- NOT AVAILABLE: no corpus file at /home/mekarz/Desktop/Full-projects/TATA-ELXSI/data/experiments/classifier_corpus/corpus.jsonl — run the live corpus step (make corpus-collect) first

Source: `/home/mekarz/Desktop/Full-projects/TATA-ELXSI/data/experiments/classifier_corpus/eval.json` (written by the corpus evaluator, whose failure table is copied verbatim).

## Safe-state and failure injection (S5)

NOT AVAILABLE (no live S5 evidence at `/home/mekarz/Desktop/Full-projects/TATA-ELXSI/data/experiments/s5/s5_summary.json`; the live script writes it)

## EMULATION statement (what is modelled, what is not)

All runs on this host are emulation: one router namespace, its LAN/WAN veth pair, an out-of-band bottleneck (netem with a token bucket limiter on the WAN side) and workload generators in their own netns. There are no physical links, no real video stacks and no third-party traffic; delay/jitter/loss via probes are generator-reported for the transmission path only. No number in this report should be read as an ISP deployment result; the controller's own classification, control loop and translation through tc are the subsystems under test.

