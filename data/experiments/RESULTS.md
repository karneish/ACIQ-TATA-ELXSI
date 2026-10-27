# Results (generated, no summarised files consulted)

Runs root: `data/experiments/bands_merge` | runs used: 190 | scenarios: s1_iso_during_call, s2_wan_drop, s3_tv_and_gaming, s4_capacity_recovery, s6_intent_expire

Skipped 1 incomplete-only directory names: `s2_wan_drop__aciq__adaptive__seed555 (special-condition run: inject_fail_apply)`

**Skipped directories (summary):**
- special-condition run: 1
- total skipped: 1

## Delay and throughput, every scenario x arm (mean +/- 95% CI over seeds; t(9)=2.262 for n=10)

Every block below carries an explicit band label, derived from the seed family recorded at load time: `POST-FIX` (seeds 200-209, the controller after the redesign commits), `PRE-FIX` (legacy seeds 0-9/42-51), `DEV` and `EVAL` (the task-2 protocol: parameters were fixed on the DEV band seeds 400-409 BEFORE the EVAL band seeds 500-509 was run ONCE; nothing between them was tuned). A reader never inherits a number of unknown provenance: the label sits directly above the table. The comparison sections further down use the primary band only.

Bulk has TWO columns on purpose (TASK 5a): `sender` is what the generator pushed, `receiver/sink` is what the receiver's sink log totalled -- the delivered number, used for any bulk claim. The post-drop column stays on the TREE counters and is named so: the three are different instruments and are never blended.

### s1_iso_during_call (primary band: POST-FIX (200-209))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.67 +/- 0.03 | 3.09 +/- 0.03 | 0.766 +/- 0.025 | NOT AVAILABLE | 96.29 +/- 0.00 | 95.49 +/- 0.00 | (no drop scenario) | 0.909 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.45 +/- 0.01 | 0.45 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 90.96 +/- 0.00 | 90.74 +/- 0.00 | (no drop scenario) | 0.922 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 1.45 +/- 0.01 | 0.44 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 90.96 +/- 0.00 | 90.74 +/- 0.00 | (no drop scenario) | 0.922 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 82.49 +/- 0.49 | 0.61 +/- 0.05 | 0.180 +/- 0.060 | NOT AVAILABLE | 86.22 +/- 0.93 | 85.41 +/- 0.93 | (no drop scenario) | 0.934 +/- 0.002 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s1_iso_during_call (EVAL, seeds 500-509)

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.69 +/- 0.02 | 3.09 +/- 0.03 | 0.766 +/- 0.025 | NOT AVAILABLE | 96.29 +/- 0.00 | 95.49 +/- 0.00 | (no drop scenario) | 0.909 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.47 +/- 0.01 | 0.45 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 90.96 +/- 0.00 | 90.74 +/- 0.00 | (no drop scenario) | 0.922 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 1.46 +/- 0.01 | 0.45 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 90.96 +/- 0.00 | 90.74 +/- 0.00 | (no drop scenario) | 0.922 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 88.58 +/- 10.87 | 0.57 +/- 0.04 | 0.200 +/- 0.045 | NOT AVAILABLE | 89.15 +/- 0.12 | 88.34 +/- 0.12 | (no drop scenario) | 0.927 +/- 0.000 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s1_iso_during_call (DEV, seeds 400-409)

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ACIQ (controller) | 10 | 93.21 +/- 14.44 | 0.59 +/- 0.05 | 0.180 +/- 0.055 | NOT AVAILABLE | 89.13 +/- 0.10 | 88.32 +/- 0.10 | (no drop scenario) | 0.927 +/- 0.000 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s1_iso_during_call (PRE-FIX, seeds 0-9,42-51)

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.71 +/- 0.03 | 3.16 +/- 0.00 | 0.740 +/- 0.015 | NOT AVAILABLE | 96.29 +/- 0.00 | 95.49 +/- 0.00 | (no drop scenario) | 0.909 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.55 +/- 0.07 | 0.48 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 90.96 +/- 0.00 | 90.74 +/- 0.00 | (no drop scenario) | 0.922 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 1.74 +/- 0.33 | 0.50 +/- 0.06 | 0.000 +/- 0.000 | NOT AVAILABLE | 90.97 +/- 0.01 | 90.74 +/- 0.00 | (no drop scenario) | 0.922 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 238.89 +/- 0.37 | 1.13 +/- 0.08 | 0.873 +/- 0.061 | NOT AVAILABLE | 96.30 +/- 0.00 | 95.50 +/- 0.01 | (no drop scenario) | 0.909 +/- 0.000 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s2_wan_drop (primary band: POST-FIX (200-209))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 251.28 +/- 0.09 | 4.36 +/- 0.06 | 8.710 +/- 0.323 | NOT AVAILABLE | 79.58 +/- 0.01 | NOT AVAILABLE | 22.16 +/- 0.05 | 0.950 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 70.31 +/- 1.73 | 0.51 +/- 0.01 | 0.160 +/- 0.015 | NOT AVAILABLE | 75.17 +/- 0.04 | 74.41 +/- 0.04 | 20.12 +/- 0.01 | 0.961 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 2.33 +/- 0.03 | 0.31 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.09 +/- 0.00 | 18.06 +/- 0.00 | 18.71 +/- 0.06 | 0.820 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 73.60 +/- 2.48 | 0.63 +/- 0.03 | 0.265 +/- 0.041 | NOT AVAILABLE | 71.69 +/- 0.58 | 69.54 +/- 0.56 | 20.15 +/- 0.01 | 0.969 +/- 0.001 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s2_wan_drop (EVAL, seeds 500-509)

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 251.30 +/- 0.05 | 4.30 +/- 0.02 | 8.985 +/- 0.168 | NOT AVAILABLE | 79.63 +/- 0.05 | 77.38 +/- 0.25 | 22.22 +/- 0.04 | 0.950 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 70.20 +/- 2.07 | 0.51 +/- 0.01 | 0.165 +/- 0.017 | NOT AVAILABLE | 75.19 +/- 0.04 | 74.42 +/- 0.04 | 20.12 +/- 0.01 | 0.961 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 2.33 +/- 0.04 | 0.31 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.09 +/- 0.00 | 18.06 +/- 0.00 | 18.66 +/- 0.08 | 0.820 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 64.14 +/- 2.15 | 0.61 +/- 0.01 | 0.135 +/- 0.038 | NOT AVAILABLE | 74.14 +/- 0.07 | 71.68 +/- 0.11 | 19.54 +/- 0.22 | 0.964 +/- 0.000 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s2_wan_drop (DEV, seeds 400-409)

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ACIQ (controller) | 10 | 64.38 +/- 2.52 | 0.62 +/- 0.01 | 0.135 +/- 0.038 | NOT AVAILABLE | 74.15 +/- 0.07 | 71.71 +/- 0.10 | 19.59 +/- 0.17 | 0.964 +/- 0.000 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s2_wan_drop (PRE-FIX, seeds 0-9,42-51)

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 248.96 +/- 0.73 | 2.89 +/- 0.25 | 9.095 +/- 0.197 | NOT AVAILABLE | 41.18 +/- 0.03 | 39.95 +/- 0.02 | 20.70 +/- 0.02 | 0.991 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 89.55 +/- 0.96 | 0.69 +/- 0.02 | 0.380 +/- 0.081 | NOT AVAILABLE | 39.06 +/- 0.03 | 38.58 +/- 0.02 | 20.05 +/- 0.00 | 0.985 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 2.38 +/- 0.05 | 0.34 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.09 +/- 0.00 | 18.06 +/- 0.00 | 18.55 +/- 0.07 | 0.820 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 11 | 111.60 +/- 30.10 | 1.10 +/- 0.49 | 0.945 +/- 1.264 | NOT AVAILABLE | 43.20 +/- 8.28 | 41.92 +/- 8.03 | 20.36 +/- 0.77 | 0.983 +/- 0.008 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s3_tv_and_gaming (primary band: POST-FIX (200-209))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 3.19 +/- 0.13 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.33 +/- 0.25 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.41 +/- 0.17 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.37 +/- 0.11 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |

#### Per-TV delivered goodput (receiver sampler, mean inst Mbps whole-run / final third)

| arm | n | tv1 | tv2 | tv3 | which band carries the sampler |
| --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | whole-run total only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | whole-run total only |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | whole-run total only |
| ACIQ (controller) | 10 | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | whole-run total only |
- each TV cell is the label's own receiver series; TV streams share the streaming sheet in the controller's tree, so the SPLIT between them is a receiver-side fact and the arm-table's streaming-class counters are the router-side view.


### s3_tv_and_gaming (EVAL, seeds 500-509)

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 3.26 +/- 0.16 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.509 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.46 +/- 0.21 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.509 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.34 +/- 0.19 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.509 +/- 0.000 | 1.000 +/- 0.000 |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.24 +/- 0.17 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.509 +/- 0.000 | 1.000 +/- 0.000 |

#### Per-TV delivered goodput (receiver sampler, mean inst Mbps whole-run / final third)

| arm | n | tv1 | tv2 | tv3 | which band carries the sampler |
| --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 4.53 +/- 0.05 / 5.14 +/- 0.15 | 4.53 +/- 0.05 / 5.36 +/- 0.13 | 4.53 +/- 0.05 / 5.47 +/- 0.16 | per-second (n_sampler=10/10) |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 4.53 +/- 0.05 / 5.13 +/- 0.15 | 4.53 +/- 0.05 / 5.35 +/- 0.13 | 4.53 +/- 0.05 / 5.46 +/- 0.16 | per-second (n_sampler=10/10) |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 4.53 +/- 0.05 / 5.14 +/- 0.15 | 4.53 +/- 0.05 / 5.35 +/- 0.12 | 4.53 +/- 0.05 / 5.46 +/- 0.16 | per-second (n_sampler=10/10) |
| ACIQ (controller) | 10 | 4.46 +/- 0.05 / 4.67 +/- 0.20 | 4.46 +/- 0.05 / 4.94 +/- 0.18 | 4.46 +/- 0.05 / 5.08 +/- 0.21 | per-second (n_sampler=10/10) |
- each TV cell is the label's own receiver series; TV streams share the streaming sheet in the controller's tree, so the SPLIT between them is a receiver-side fact and the arm-table's streaming-class counters are the router-side view.


### s3_tv_and_gaming (DEV, seeds 400-409)

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.27 +/- 0.19 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.509 +/- 0.000 | 1.000 +/- 0.000 |

#### Per-TV delivered goodput (receiver sampler, mean inst Mbps whole-run / final third)

| arm | n | tv1 | tv2 | tv3 | which band carries the sampler |
| --- | --- | --- | --- | --- | --- |
| ACIQ (controller) | 10 | 4.45 +/- 0.04 / 4.62 +/- 0.16 | 4.45 +/- 0.04 / 4.98 +/- 0.16 | 4.44 +/- 0.04 / 5.19 +/- 0.13 | per-second (n_sampler=10/10) |
- each TV cell is the label's own receiver series; TV streams share the streaming sheet in the controller's tree, so the SPLIT between them is a receiver-side fact and the arm-table's streaming-class counters are the router-side view.


### s3_tv_and_gaming (PRE-FIX, seeds 0-9,42-51)

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 3.30 +/- 0.29 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.509 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.47 +/- 0.13 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.23 +/- 0.17 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.13 +/- 0.25 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |

#### Per-TV delivered goodput (receiver sampler, mean inst Mbps whole-run / final third)

| arm | n | tv1 | tv2 | tv3 | which band carries the sampler |
| --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | whole-run total only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | whole-run total only |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | whole-run total only |
| ACIQ (controller) | 10 | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | NOT AVAILABLE (no per-second sampler total line) | whole-run total only |
- each TV cell is the label's own receiver series; TV streams share the streaming sheet in the controller's tree, so the SPLIT between them is a receiver-side fact and the arm-table's streaming-class counters are the router-side view.


### s4_capacity_recovery (primary band: POST-FIX (200-209))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.43 +/- 0.06 | 3.05 +/- 0.02 | 6.017 +/- 0.155 | NOT AVAILABLE | 59.45 +/- 0.01 | 58.26 +/- 0.01 | 20.68 +/- 0.01 | 0.993 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 89.73 +/- 1.08 | 0.63 +/- 0.02 | 0.197 +/- 0.052 | NOT AVAILABLE | 56.51 +/- 0.02 | 56.04 +/- 0.02 | 20.04 +/- 0.00 | 0.996 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 2.74 +/- 0.03 | 0.48 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.08 +/- 0.00 | 18.06 +/- 0.00 | 18.78 +/- 0.01 | 0.820 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 95.74 +/- 0.90 | 0.73 +/- 0.01 | 0.280 +/- 0.023 | NOT AVAILABLE | 53.88 +/- 0.08 | 52.79 +/- 0.08 | 19.95 +/- 0.00 | 0.999 +/- 0.000 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s4_capacity_recovery (EVAL, seeds 500-509)

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.41 +/- 0.05 | 3.06 +/- 0.04 | 5.957 +/- 0.130 | NOT AVAILABLE | 59.46 +/- 0.00 | 58.26 +/- 0.00 | 20.68 +/- 0.01 | 0.993 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 90.05 +/- 0.64 | 0.61 +/- 0.01 | 0.193 +/- 0.047 | NOT AVAILABLE | 56.52 +/- 0.02 | 56.04 +/- 0.03 | 20.04 +/- 0.00 | 0.996 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 2.74 +/- 0.02 | 0.48 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.08 +/- 0.00 | 18.06 +/- 0.00 | 18.78 +/- 0.01 | 0.820 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 59.56 +/- 15.64 | 0.81 +/- 0.26 | 0.087 +/- 0.030 | NOT AVAILABLE | 55.45 +/- 0.32 | 54.22 +/- 0.35 | 18.82 +/- 0.58 | 0.997 +/- 0.000 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s4_capacity_recovery (DEV, seeds 400-409)

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ACIQ (controller) | 10 | 50.92 +/- 7.97 | 0.65 +/- 0.02 | 0.097 +/- 0.017 | NOT AVAILABLE | 55.27 +/- 0.27 | 54.02 +/- 0.32 | 18.53 +/- 0.62 | 0.997 +/- 0.000 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s4_capacity_recovery (PRE-FIX, seeds 0-9,42-51)

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 245.07 +/- 0.18 | 2.06 +/- 0.01 | 6.127 +/- 0.088 | NOT AVAILABLE | 33.78 +/- 0.01 | 33.10 +/- 0.01 | 20.40 +/- 0.01 | 0.964 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 89.95 +/- 0.46 | 0.84 +/- 0.29 | 0.407 +/- 0.367 | NOT AVAILABLE | 32.38 +/- 0.01 | 32.12 +/- 0.01 | 20.02 +/- 0.00 | 0.956 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 2.75 +/- 0.03 | 0.49 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.08 +/- 0.00 | 18.06 +/- 0.00 | 18.79 +/- 0.01 | 0.820 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 96.87 +/- 1.09 | 0.88 +/- 0.02 | 0.363 +/- 0.054 | NOT AVAILABLE | 32.65 +/- 0.05 | 31.99 +/- 0.05 | 19.95 +/- 0.01 | 0.958 +/- 0.000 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s6_intent_expire (primary band: POST-FIX (200-209))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.91 +/- 0.03 | 3.32 +/- 0.02 | 0.380 +/- 0.012 | 250.92 +/- 0.02 | 95.86 +/- 0.00 | 95.46 +/- 0.00 | (no drop scenario) | 0.819 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.44 +/- 0.02 | 0.45 +/- 0.01 | 0.000 +/- 0.000 | 1.46 +/- 0.02 | 90.82 +/- 0.00 | 90.71 +/- 0.00 | (no drop scenario) | 0.835 +/- 0.000 | 1.000 +/- 0.000 |
| ACIQ (controller) | 10 | 14.67 +/- 7.13 | 0.54 +/- 0.04 | 0.107 +/- 0.058 | 13.89 +/- 6.65 | 80.79 +/- 0.23 | 80.40 +/- 0.23 | (no drop scenario) | 0.868 +/- 0.001 | 1.000 +/- 0.000 |

## ACIQ vs every arm (positive % is better ACIQ on the metric at the head of the column; a cell like `41.0x` is the multiplicative factor when the baseline is so close to zero that a percentage would mislead)

| scenario | vs arm | call p95 delta % | CI overlap? | bulk delta % | CI overlap? |
| --- | --- | --- | --- | --- | --- |
Bulk compares are POST-DROP ONLY in scenarios with a capacity drop (same `bulk_mbps` whole-run mean otherwise): the whole-run number dilutes the post-drop regime with a saturated prefix, which is the opposite of the decision those scenarios exist to measure.

| s1_iso_during_call | B0 (default router, pfifo) | +67.1 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | 57.0x | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s1_iso_during_call | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 56.7x | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2_wan_drop | B0 (default router, pfifo) | +70.7 | disjoint | -9.1 | disjoint |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | -4.7 | overlap | +0.1 | disjoint |
| s2_wan_drop | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 31.6x | disjoint | +7.7 | disjoint |
| s3_tv_and_gaming | B0 (default router, pfifo) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_tv_and_gaming | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s4_capacity_recovery | B0 (default router, pfifo) | +61.8 | disjoint | -3.5 | disjoint |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | -6.7 | disjoint | -0.5 | disjoint |
| s4_capacity_recovery | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 35.0x | disjoint | +6.2 | disjoint |
| s6_intent_expire | B0 (default router, pfifo) | +94.2 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s6_intent_expire | CAKE-static (95% of pre-drop link, set and forget) | -916.3 | disjoint | NOT AVAILABLE | NOT AVAILABLE |

## Where ACIQ is worse (the honest column)

Every row above where ACIQ's signed delta is negative, collected so a CAKE win cannot hide behind the aggregate. Empty means no such pair exists in the runs found.

| scenario | vs arm | metric where ACIQ is worse |
| --- | --- | --- |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | call p95 57.0x |
| s1_iso_during_call | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | call p95 56.7x |
| s2_wan_drop | B0 (default router, pfifo) | post-drop bulk Mbps -9.1 |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | call p95 -4.7 |
| s2_wan_drop | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | call p95 31.6x |
| s4_capacity_recovery | B0 (default router, pfifo) | post-drop bulk Mbps -3.5 |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | call p95 -6.7 and post-drop bulk Mbps -0.5 |
| s4_capacity_recovery | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | call p95 35.0x |
| s6_intent_expire | CAKE-static (95% of pre-drop link, set and forget) | call p95 -916.3 |

## Where CAKE-static wins

The honest column above lists every rival; this one isolates the set-and-forget rival that matters for the design claim. A CAKE win on a metric is stated here verbatim; nothing is re-derived and nothing is argued away. CI overlap of the underlying seed samples is in the table above (`CI overlap?` column).

| scenario | metric where CAKE-static beats ACIQ | see column in the ACIQ-vs-every table |
| --- | --- | --- |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | call p95 57.0x |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | call p95 -4.7 |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | call p95 -6.7 and post-drop bulk Mbps -0.5 |
| s6_intent_expire | CAKE-static (95% of pre-drop link, set and forget) | call p95 -916.3 |

## ACIQ adaptation and capacity accuracy (from the same runs above)

| scenario | n | bind: drop -> first applied <=1.05x post-drop (s) | bind: drop -> first applied <=1.25x post-drop (s) | final estimate | configured end link | estimate error % |
| --- | --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 95.73 +/- 0.08 | 100.0 +/- 0.0 | mean abs 4.3% (seed0: 95.61/100.0 (4.4% off)) |
| s2_wan_drop | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 21.45 +/- 0.11 | 20.0 +/- 0.0 | mean abs 7.3% (seed0: 21.59/20.0 (7.9% off)) |
| s3_tv_and_gaming | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 56.23 +/- 13.96 | 100.0 +/- 0.0 | mean abs 43.8% (seed0: 59.04/100.0 (41.0% off)) |
| s4_capacity_recovery | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 21.35 +/- 0.25 | 20.0 +/- 0.0 | mean abs 6.7% (seed0: 21.52/20.0 (7.6% off)) |
| s6_intent_expire | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 92.98 +/- 1.56 | 100.0 +/- 0.0 | mean abs 7.0% (seed0: 92.31/100.0 (7.7% off)) |
## Controller resources (ACIQ adaptive runs only; from each result's resources block)

| scenario | n | cpu mean frac | decision p95 ms | decision max ms | max RSS bytes |
| --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | 10 | 0.0042 +/- 0.0001 | 37.29 +/- 18.57 | 76.59 +/- 2.65 | 20649574 +/- 384796 |
| s2_wan_drop | 10 | 0.0043 +/- 0.0001 | 59.97 +/- 17.01 | 75.82 +/- 2.43 | 20893286 +/- 406731 |
| s3_tv_and_gaming | 10 | 0.0043 +/- 0.0002 | 74.32 +/- 1.15 | 77.82 +/- 2.49 | 20952678 +/- 397623 |
| s4_capacity_recovery | 10 | 0.0045 +/- 0.0001 | 14.88 +/- 2.76 | 80.21 +/- 1.23 | 21629338 +/- 590585 |
| s6_intent_expire | 10 | 0.0092 +/- 0.0005 | 27.60 +/- 4.99 | 103.69 +/- 20.45 | 29630874 +/- 726063 |

## Fairness detail (workload-rate Jain; per-class minima over ASSIGNED classes only, same scope for every mode)

| scenario | arm | n | jain mean +/- CI | demand-jain mean +/- CI | flows used | min over time (per label, via carrying class) |
| --- | --- | --- | --- | --- | --- | --- |
demand-jain: Jain over per-flow satisfied-demand ratios (achieved/demand, demand self-reported by the generator; elastic flows without a declared demand are excluded by definition -- see aciq/fairness.py). A scenario flows all-elastic has no such index and prints NOT AVAILABLE rather than a substitute.

Per-tick counter attribution (fix 18): ACIQ's tree has one leaf per class; the baselines' single-class tree carries the WHOLE link on the 1:50 leaf. New artefacts sample that aggregate under `unknown` (an aggregate can no longer masquerade as a software_update class); artefacts from before this change stored the same aggregate under `software_update`, and consumers that fall back to the legacy label must name it -- the post-drop bulk column does exactly that.

| s1_iso_during_call | B0 (default router, pfifo) | 10 | 0.909 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=99.6; call via unknown=99.6; bulk via unknown=99.6; call via unknown=99.6; bulk via unknown=99.6; call via unknown=99.6 |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.922 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=95; call via unknown=95; bulk via unknown=95; call via unknown=95; bulk via unknown=94.9; call via unknown=94.9 |
| s1_iso_during_call | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.922 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=95; call via unknown=95; bulk via unknown=95; call via unknown=95; bulk via unknown=95; call via unknown=95 |
| s1_iso_during_call | ACIQ (controller) | 10 | 0.934 +/- 0.002 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=85.8; call via unknown=85.8; bulk via unknown=86; call via unknown=86; bulk via unknown=86; call via unknown=86 |
| s2_wan_drop | B0 (default router, pfifo) | 10 | 0.950 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19.9; call via unknown=19.9; bulk via unknown=19.9; call via unknown=19.9; bulk via unknown=19.9; call via unknown=19.9 |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.961 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20 |
| s2_wan_drop | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.820 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19; call via unknown=19; bulk via unknown=19; call via unknown=19; bulk via unknown=19; call via unknown=19 |
| s2_wan_drop | ACIQ (controller) | 10 | 0.969 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19.9; call via unknown=19.9; bulk via unknown=19.9; call via unknown=19.9; bulk via unknown=19.9; call via unknown=19.9 |
| s3_tv_and_gaming | B0 (default router, pfifo) | 10 | 0.510 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=4.64; tv1 via unknown=4.64; tv2 via unknown=4.64; tv3 via unknown=4.64; game via unknown=4.64; tv1 via unknown=4.64 |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.510 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=4.68; tv1 via unknown=4.68; tv2 via unknown=4.68; tv3 via unknown=4.68; game via unknown=4.64; tv1 via unknown=4.64 |
| s3_tv_and_gaming | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.510 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=4.66; tv1 via unknown=4.66; tv2 via unknown=4.66; tv3 via unknown=4.66; game via unknown=4.64; tv1 via unknown=4.64 |
| s3_tv_and_gaming | ACIQ (controller) | 10 | 0.510 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=4.65; tv1 via unknown=4.65; tv2 via unknown=4.65; tv3 via unknown=4.65; game via unknown=4.68; tv1 via unknown=4.68 |
| s4_capacity_recovery | B0 (default router, pfifo) | 10 | 0.993 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20; bulk via unknown=19.9; call via unknown=19.9 |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.996 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20; bulk via unknown=19.9; call via unknown=19.9 |
| s4_capacity_recovery | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.820 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19; call via unknown=19; bulk via unknown=19; call via unknown=19; bulk via unknown=19; call via unknown=19 |
| s4_capacity_recovery | ACIQ (controller) | 10 | 0.999 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19.8; call via unknown=19.8; bulk via unknown=19.9; call via unknown=19.9; bulk via unknown=19.8; call via unknown=19.8 |
| s6_intent_expire | B0 (default router, pfifo) | 10 | 0.819 +/- 0.000 | 1.000 +/- 0.000 | 3.0 +/- 0.0 | bulk via unknown=99.6; call via unknown=99.6; game via unknown=99.6; bulk via unknown=99.7; call via unknown=99.7; game via unknown=99.7 |
| s6_intent_expire | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.835 +/- 0.000 | 1.000 +/- 0.000 | 3.0 +/- 0.0 | bulk via unknown=95; call via unknown=95; game via unknown=95; bulk via unknown=94.9; call via unknown=94.9; game via unknown=94.9 |
| s6_intent_expire | ACIQ (controller) | 10 | 0.868 +/- 0.001 | 1.000 +/- 0.000 | 3.0 +/- 0.0 | bulk=0; call via unknown=0; game via unknown=0; bulk=0; call via unknown=0; game via unknown=0 |

Starvation (TASK 5b, fixed basis): per LABEL, over the class the data says carried the traffic (assigned class, or the router's `unknown`/legacy aggregate when the label's traffic rode there -- chosen by highest mean, and the carrying class is named). A label starved in tick t if its per-tick goodput fell below 20% of its REGIME median -- in a drop scenario the median is the POST-DROP regime's own median, so the shaped link rate can never masquerade as starvation; without a drop it is the whole window's. The cell lists the starved timestamps counted over seeds. With no series at all the cell prints NOT AVAILABLE, never an empty claim.

| scenario | arm | starved ticks per label (via carrying class) |
| --- | --- | --- |
| s1_iso_during_call | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s1_iso_during_call | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s1_iso_during_call | ACIQ (controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2_wan_drop | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2_wan_drop | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2_wan_drop | ACIQ (controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s3_tv_and_gaming | B0 (default router, pfifo) | no starving tick in 40 seed x label series (regime-aware threshold, declared window) |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 40 seed x label series (regime-aware threshold, declared window) |
| s3_tv_and_gaming | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | no starving tick in 40 seed x label series (regime-aware threshold, declared window) |
| s3_tv_and_gaming | ACIQ (controller) | no starving tick in 40 seed x label series (regime-aware threshold, declared window) |
| s4_capacity_recovery | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s4_capacity_recovery | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s4_capacity_recovery | ACIQ (controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s6_intent_expire | B0 (default router, pfifo) | no starving tick in 30 seed x label series (regime-aware threshold, declared window) |
| s6_intent_expire | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 30 seed x label series (regime-aware threshold, declared window) |
| s6_intent_expire | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 428 ticks over 10 seed(s), first t=5.3; game via unknown: 428 ticks over 10 seed(s), first t=5.3 |

Warm-up exclusion (declared): every per-tick window above starts at t >= 2.0 s. The diagnosis round (fix 17's diagnosis.md) shows the first ~2 s of per-tick counter rates are a transmit/counter ramp artefact, not traffic behaviour; dropping those ticks removes nothing else. The window boundary is a declared constant in this generator, not a per-run choice.

Further declared exclusions (TASK 5b): (1) ticks at or beyond the label generator's own measured lifetime (`elapsed_s`, capped by the scenario duration) -- a verdict about a label after its traffic stopped describes nothing about the label; (2) ticks whose link counters went BACKWARDS -- a qdisc del/re-add resets every counter on the device, so that tick's per-class goodput is a reset artefact, not a delivery gap. Stars and minima are computed over what remains; nothing is excluded silently.

## S6 intent scenario (real API intent, TTL expiry inside the run, auto-revert)

One intent is requested at the run's declared --intent-at on the operator's real surface (IntentService, the exact upstream-declared code path the HTTP handler calls: POST /intent, target device, weight 0.5). Both endpoints of the intent's life are measured: held while live, auto-reverted at expiry (LeaseBook's implicit sweep plus the per-tick sync_lease), and the recovery window after expiry. The two S6 protocol generations are SEPARATE (legacy: 40s run, intent at t~1s, TTL 15s; current: 60s run, intent at t=10s, TTL 20s) -- no pooling, and with n=10 per arm every CI is a real t-table interval. Receiver evidence is the per-second sink sampler; the floors line is a FLOOR line, not a preference claim: on a healthy link a reserve must not starve the other classes, and the reserved device must actually receive bytes. The s6 summary file is quoted when present; the table never infers what the verifier measured.

- verifier verdict (tools/verify_s6.py, via `/home/mekarz/Desktop/Full-projects/TATA-ELXSI/data/experiments/s6/s6_summary.json`): `{"intent_granted": "PASS", "auto_reverted_at_expiry": "PASS", "floors_held": "PASS", "baselines_declare_unsupported": "PASS", "run_rc": 0, "host": "live step verdict; floors include the absolute fallback floor (verifier re-run over the committed artefacts confirms the same verdict)", "notes": "values PASS/FAIL/NA from verify_s6.py over the 300-309 and 310-319 bands; recovery 17/17 (3 runs N/A: no pre-drop median), declared in the verifier itself", "recovery": "PASS", "verifier": "data/experiments/s6/verify_s6_310_band.out", "protocol": "intent at t=10s, TTL 20s (declared task3-params.md)"}`

### S6 protocol: current protocol: 60s run, intent at t=10, TTL 20s (n=30 across 3 arms)

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.91 +/- 0.03 | 3.32 +/- 0.02 | 0.380 +/- 0.012 | 250.92 +/- 0.02 | 95.86 +/- 0.00 | 95.46 +/- 0.00 | (no drop scenario) | 0.819 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.44 +/- 0.02 | 0.45 +/- 0.01 | 0.000 +/- 0.000 | 1.46 +/- 0.02 | 90.82 +/- 0.00 | 90.71 +/- 0.00 | (no drop scenario) | 0.835 +/- 0.000 | 1.000 +/- 0.000 |
| ACIQ (controller) | 10 | 14.67 +/- 7.13 | 0.54 +/- 0.04 | 0.107 +/- 0.058 | 13.89 +/- 6.65 | 80.79 +/- 0.23 | 80.40 +/- 0.23 | (no drop scenario) | 0.868 +/- 0.001 | 1.000 +/- 0.000 |

#### Intent life (grant / auto-revert / floors) — same protocol generation

| arm | intent (verdict from result.json) | auto-revert (lease_active evidence, ticks) | receiver inst in window: game min / bulk min (floors) | declared |
| --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | declared: no intent surface (n=10 seeds) | - (n=10 seeds) | - (n=10 seeds) | declared intent-incapable |
| CAKE-static (95% of pre-drop link, set and forget) | declared: no intent surface (n=10 seeds) | - (n=10 seeds) | - (n=10 seeds) | declared intent-incapable |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | NOT AVAILABLE (no s6 run in this protocol) | - | - | declared intent-incapable |
| ACIQ (controller) | granted t=10.7s, in-effect 17s (TTL 20s); granted t=10.7s, in-effect 17s (TTL 20s); granted t=10.7s, in-effect 17s (TTL 20s); granted t=10.9s, in-effect 16s (TTL 20s); granted t=10.7s, in-effect 17s (TTL 20s); granted t=10.7s, in-effect 15s (TTL 20s); granted t=10.8s, in-effect 17s (TTL 20s); granted t=10.8s, in-effect 17s (TTL 20s); granted t=11.0s, in-effect 17s (TTL 20s); granted t=11.0s, in-effect 17s (TTL 20s) | ok: last active t=30s, clear after 31s (n=10 seeds) | game 0.03 Mbps (>0: PASS); bulk 67.14 Mbps (>=10% of pre-median 76.39: PASS); game 0.03 Mbps (>0: PASS); bulk 65.59 Mbps (>=10% of pre-median 73.15: PASS); game 0.03 Mbps (>0: PASS); bulk 67.57 Mbps (>=10% of pre-median 77.12: PASS); game 0.03 Mbps (>0: PASS); bulk 68.58 Mbps (>=10% of pre-median 76.50: PASS); game 0.03 Mbps (>0: PASS); bulk 65.10 Mbps (>=10% of pre-median 72.98: PASS); game 0.03 Mbps (>0: PASS); bulk 67.13 Mbps (>=10% of pre-median 76.17: PASS); game 0.03 Mbps (>0: PASS); bulk 68.35 Mbps (>=10% of pre-median 77.39: PASS); game 0.03 Mbps (>0: PASS); bulk 70.41 Mbps (>=10% of pre-median 79.93: PASS); game 0.03 Mbps (>0: PASS); bulk 68.79 Mbps (>=10% of pre-median 77.51: PASS); game 0.03 Mbps (>0: PASS); bulk 69.21 Mbps (>=10% of pre-median 77.40: PASS) | ACIQ: intent surface |

#### Before / during / after windows (per-window mean +/- t-CI over the arm's runs; goodput = per-class RECEIVER sheet median per run, Mbps; probes = the ROUTER's own per-class rtt-p95 sheet median per run, ms; recovery target 90% of the pre-intent receiver median inside 5s of expiry)

**B0 (default router, pfifo)**

| - | - | - | - | - | no intent surface: windows not applicable |

**CAKE-static (95% of pre-drop link, set and forget)**

| - | - | - | - | - | no intent surface: windows not applicable |

**ACIQ (controller)**

| window | call goodput | game goodput | bulk goodput | unknown goodput | probe rtt p95 (attached sheet) |
| before | 0.16 +/- 0.00 | 0.00 +/- 0.00 | 79.74 +/- 1.67 | 0.00 +/- 0.00 | 112.7 +/- 29.4 |
| during | 0.12 +/- 0.00 | 0.00 +/- 0.00 | 84.76 +/- 0.02 | 0.00 +/- 0.00 | 111.3 +/- 29.1 |
| after | 0.16 +/- 0.00 | 0.00 +/- 0.00 | 84.78 +/- 0.03 | 0.00 +/- 0.00 | 109.7 +/- 28.7 |
| bulk recovery from expiry (s), 90%/5s target, when met | 0.22 +/- 0.09 |

- per-window END-TO-END call/game p95/jitter/loss is NOT AVAILABLE here: the S6 flow jsons store one whole-run distribution each (the sender prints a single json at exit); per-window end-to-end latency arrives with the live instrumented trace, not from these artefacts.
- 'consumed' deliberately dropped as a duplicate of the bulk sheet; the pre-intent receiver median is already in the verifier's floor line above.

#### Verdict (this protocol, whole-run figures)

- B0 (default router, pfifo): call p95 250.91 +/- 0.03 ms; game p95 250.92 +/- 0.02 ms
- CAKE-static (95% of pre-drop link, set and forget): call p95 1.44 +/- 0.02 ms; game p95 1.46 +/- 0.02 ms
- ACIQ (controller): call p95 14.67 +/- 7.13 ms; game p95 13.89 +/- 6.65 ms
- ACIQ vs CAKE-static call p95 CIs: disjoint; ACIQ vs B0: disjoint.
- caveat: whole-run distributions include each arm's own launch prefix; the steady-window separation is the S1 section's job (declared prefix, one number, not tuned per run).

### S6 protocol: protocol: 40s run, intent at 1s, TTL 15s (n=30 across 3 arms)

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.85 +/- 0.03 | 3.18 +/- 0.03 | 0.555 +/- 0.011 | 250.88 +/- 0.03 | 96.06 +/- 0.00 | 95.46 +/- 0.00 | (no drop scenario) | 0.818 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.39 +/- 0.01 | 0.44 +/- 0.01 | 0.000 +/- 0.000 | 1.41 +/- 0.01 | 90.85 +/- 0.01 | 90.69 +/- 0.01 | (no drop scenario) | 0.835 +/- 0.000 | 1.000 +/- 0.000 |
| ACIQ (controller) | 10 | 39.00 +/- 20.30 | 0.43 +/- 0.01 | 0.035 +/- 0.029 | 38.68 +/- 20.00 | 76.72 +/- 1.12 | 76.14 +/- 1.12 | (no drop scenario) | 0.882 +/- 0.004 | 1.000 +/- 0.000 |

#### Intent life (grant / auto-revert / floors) — same protocol generation

| arm | intent (verdict from result.json) | auto-revert (lease_active evidence, ticks) | receiver inst in window: game min / bulk min (floors) | declared |
| --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | declared: no intent surface (n=10 seeds) | - (n=10 seeds) | - (n=10 seeds) | declared intent-incapable |
| CAKE-static (95% of pre-drop link, set and forget) | declared: no intent surface (n=10 seeds) | - (n=10 seeds) | - (n=10 seeds) | declared intent-incapable |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | NOT AVAILABLE (no s6 run in this protocol) | - | - | declared intent-incapable |
| ACIQ (controller) | granted t=1.0s, in-effect 13s (TTL 15s); granted t=1.0s, in-effect 13s (TTL 15s); granted t=1.0s, in-effect 14s (TTL 15s); granted t=1.0s, in-effect 13s (TTL 15s); granted t=1.0s, in-effect 13s (TTL 15s); granted t=1.0s, in-effect 13s (TTL 15s); granted t=1.0s, in-effect 13s (TTL 15s); granted t=1.0s, in-effect 13s (TTL 15s); granted t=1.1s, in-effect 13s (TTL 15s); granted t=1.0s, in-effect 13s (TTL 15s) | ok: last active t=15s, clear after 16s; ok: last active t=15s, clear after 16s; ok: last active t=16s, clear after 16s; ok: last active t=15s, clear after 16s; ok: last active t=15s, clear after 16s; ok: last active t=15s, clear after 16s; ok: last active t=15s, clear after 16s; ok: last active t=15s, clear after 16s; ok: last active t=15s, clear after 16s; ok: last active t=15s, clear after 16s | game 0.03 Mbps (>0: PASS); bulk 71.43 Mbps (>=10% of pre-median 21.04: PASS); game 0.03 Mbps (>0: PASS); bulk 56.48 Mbps (>=10% of pre-median 0.00: PASS); game 0.03 Mbps (>0: PASS); bulk 59.25 Mbps (>=10% of pre-median 67.92: PASS); game 0.03 Mbps (>0: PASS); bulk 58.93 Mbps (>=10% of pre-median 34.33: PASS); game 0.03 Mbps (>0: PASS); bulk 57.24 Mbps (>=10% of pre-median 20.25: PASS); game 0.03 Mbps (>0: PASS); bulk 71.75 Mbps (>=10% of pre-median 17.83: PASS); game 0.03 Mbps (>0: PASS); bulk 58.85 Mbps (>=10% of pre-median 17.16: PASS); game 0.03 Mbps (>0: PASS); bulk 63.65 Mbps (>=10% of pre-median 0.00: PASS); game 0.03 Mbps (>0: PASS); bulk 55.23 Mbps (>=10% of pre-median 0.00: PASS); game 0.03 Mbps (>0: PASS); bulk 57.35 Mbps (>=10% of pre-median 33.24: PASS) | ACIQ: intent surface |

#### Before / during / after windows (per-window mean +/- t-CI over the arm's runs; goodput = per-class RECEIVER sheet median per run, Mbps; probes = the ROUTER's own per-class rtt-p95 sheet median per run, ms; recovery target 90% of the pre-intent receiver median inside 5s of expiry)

**B0 (default router, pfifo)**

| - | - | - | - | - | no intent surface: windows not applicable |

**CAKE-static (95% of pre-drop link, set and forget)**

| - | - | - | - | - | no intent surface: windows not applicable |

**ACIQ (controller)**

| window | call goodput | game goodput | bulk goodput | unknown goodput | probe rtt p95 (attached sheet) |
| before | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE (probe sheet has no rtt samples) |
| during | 0.12 +/- 0.00 | 0.00 +/- 0.00 | 68.58 +/- 5.35 | 0.00 +/- 0.00 | 72.8 +/- 17.3 |
| after | 0.16 +/- 0.00 | 0.00 +/- 0.00 | 81.86 +/- 3.29 | 0.00 +/- 0.00 | 70.9 +/- 17.1 |
| bulk recovery from expiry (s), 90%/5s target, when met | 1.11 +/- 0.35 |

- per-window END-TO-END call/game p95/jitter/loss is NOT AVAILABLE here: the S6 flow jsons store one whole-run distribution each (the sender prints a single json at exit); per-window end-to-end latency arrives with the live instrumented trace, not from these artefacts.
- 'consumed' deliberately dropped as a duplicate of the bulk sheet; the pre-intent receiver median is already in the verifier's floor line above.

#### Verdict (this protocol, whole-run figures)

- B0 (default router, pfifo): call p95 250.85 +/- 0.03 ms; game p95 250.88 +/- 0.03 ms
- CAKE-static (95% of pre-drop link, set and forget): call p95 1.39 +/- 0.01 ms; game p95 1.41 +/- 0.01 ms
- ACIQ (controller): call p95 39.00 +/- 20.30 ms; game p95 38.68 +/- 20.00 ms
- ACIQ vs CAKE-static call p95 CIs: disjoint; ACIQ vs B0: disjoint.
- caveat: whole-run distributions include each arm's own launch prefix; the steady-window separation is the S1 section's job (declared prefix, one number, not tuned per run).


- the two protocols are never pooled: every cell above is computed inside one generation (2 generation(s) on disk).

## Classifier (router-vantage corpus, thresholds fixed before held-out)

- HEADLINE (fresh held-out, tuple-split by flow, no threshold tuned on this half): broad-taxonomy accuracy 0.75 on n=120 (90 correct, 0 abstained); narrow-taxonomy accuracy 0.65 on the same rows (78 correct, 0 abstained). The FULL-corpus figures below are context, not the verdict: the held-out half is the one the classifier never shaped.
- broad_heldout: `{"n": 120, "correct": 90, "abstained": 0, "confident_or_wrong": 30, "accuracy_strict": 0.75, "accuracy_excl_abstain": 0.75}`
- broad_accept_abstain_heldout: `{"n": 120, "correct": 90, "abstained": 0, "confident_or_wrong": 30, "accuracy_strict": 0.75, "accuracy_excl_abstain": 0.75}`
- calibration_heldout: `[{"lo": 0.0, "hi": 0.2, "n": 0, "correct": 0, "empirical_accuracy": null, "mean_predicted": null}, {"lo": 0.2, "hi": 0.4, "n": 0, "correct": 0, "empirical_accuracy": null, "mean_predicted": null}, {"lo": 0.4, "hi": 0.6, "n": 27, "correct": 15, "empirical_accuracy": 0.5556, "mean_predicted": 0.55}, {"lo": 0.6, "hi": 0.8, "n": 93, "correct": 63, "empirical_accuracy": 0.6774, "mean_predicted": 0.629}, {"lo": 0.8, "hi": 1.0, "n": 0, "correct": 0, "empirical_accuracy": null, "mean_predicted": null}]`
- confidently_wrong_heldout: `[]`
- strict: `{"n": 228, "correct": 139, "abstained": 0, "confident_or_wrong": 89, "accuracy_strict": 0.6096491228070176, "accuracy_excl_abstain": 0.6096491228070176}`
- strict_fixed: `{"n": 108, "correct": 61, "abstained": 0, "confident_or_wrong": 47, "accuracy_strict": 0.5648148148148148, "accuracy_excl_abstain": 0.5648148148148148}`
- strict_heldout: `{"n": 120, "correct": 78, "abstained": 0, "confident_or_wrong": 42, "accuracy_strict": 0.65, "accuracy_excl_abstain": 0.65}`
- accept_abstain: `{"n": 228, "correct": 139, "abstained": 0, "confident_or_wrong": 89, "accuracy_strict": 0.6096491228070176, "accuracy_excl_abstain": 0.6096491228070176}`
- accept_abstain_heldout: `{"n": 120, "correct": 78, "abstained": 0, "confident_or_wrong": 42, "accuracy_strict": 0.65, "accuracy_excl_abstain": 0.65}`
- confusion_heldout: `{"classes": ["adaptive_video_streaming", "bulk_download", "cloud_backup", "interactive_gaming", "software_update", "video_call_voice"], "matrix": {"adaptive_video_streaming": {"bulk_download": 0, "cloud_backup": 0, "interactive_gaming": 0, "software_update": 0, "video_call_voice": 0, "adaptive_video_streaming": 32, "?abstain": 0}, "bulk_download": {"adaptive_video_streaming": 6, "cloud_backup": 0, "interactive_gaming": 0, "software_update": 0, "video_call_voice": 0, "bulk_download": 18, "?abstain": 0}, "cloud_backup": {"adaptive_video_streaming": 0, "bulk_download": 0, "interactive_gaming": 0, "software_update": 0, "video_call_voice": 0, "cloud_backup": 13, "?abstain": 0}, "interactive_gaming": {"adaptive_video_streaming": 0, "bulk_download": 0, "cloud_backup": 0, "software_update": 0, "video_call_voice": 12, "interactive_gaming": 0, "?abstain": 0}, "software_update": {"adaptive_video_streaming": 24, "bulk_download": 0, "cloud_backup": 0, "interactive_gaming": 0, "video_call_voice": 0, "software_update": 0, "?abstain": 0}, "video_call_voice": {"adaptive_video_streaming": 0, "bulk_download": 0, "cloud_backup": 0, "interactive_gaming": 0, "software_update": 0, "video_call_voice": 15, "?abstain": 0}}, "per_class": {"adaptive_video_streaming": {"tp": 32, "fp": 30, "fn": 0, "support": 32, "precision": 0.5161290322580645, "recall": 1.0, "f1": 0.6808510638297872}, "bulk_download": {"tp": 18, "fp": 0, "fn": 6, "support": 24, "precision": 1.0, "recall": 0.75, "f1": 0.8571428571428571}, "cloud_backup": {"tp": 13, "fp": 0, "fn": 0, "support": 13, "precision": 1.0, "recall": 1.0, "f1": 1.0}, "interactive_gaming": {"tp": 0, "fp": 0, "fn": 12, "support": 12, "precision": null, "recall": 0.0, "f1": null}, "software_update": {"tp": 0, "fp": 0, "fn": 24, "support": 24, "precision": null, "recall": 0.0, "f1": null}, "video_call_voice": {"tp": 15, "fp": 12, "fn": 0, "support": 15, "precision": 0.5555555555555556, "recall": 1.0, "f1": 0.7142857142857143}}}`
- paths_fixed: `["aciq/classify.py", "aciq/features.py", "aciq/model.py:BROAD_TAXONOMY"]`
- n_corpus: `228`
- n_heldout: `120`
- per-class floor 30: met (counts: `{"video_call_voice": 30, "interactive_gaming": 30, "adaptive_video_streaming": 49, "bulk_download": 40, "software_update": 49, "cloud_backup": 30}`)

Source: `data/experiments/classifier_corpus_fresh/eval.json` (written by the corpus evaluator, whose failure table is copied verbatim).

## Safe-state and failure injection (S5)

- a_sigterm_no_filter_residue: `"PASS"`
- b_sigkill_residue_then_cleanup: `"PASS"`
- c_injected_failed_apply_rollbacks: `"PASS"`
- d_watchdog_starve_reaches_safe: `"PASS"`
- host: `"/home/mekarz/aciq-venv/bin/python -V"`
- notes: `"values PASS/FAIL only; the report quotes this file verbatim"`

**Time to safe state (S5c injected failed apply; rollback = the kernel back on last-good):**
- s2_wan_drop__aciq__adaptive__seed555: 26.680 s (arm->rollback)

## EMULATION statement (what is modelled, what is not)

All runs on this host are emulation: one router namespace, its LAN/WAN veth pair, an out-of-band bottleneck (netem with a token bucket limiter on the WAN side) and workload generators in their own netns. There are no physical links, no real video stacks and no third-party traffic; delay/jitter/loss via probes are generator-reported for the transmission path only. No number in this report should be read as an ISP deployment result; the controller's own classification, control loop and translation through tc are the subsystems under test.

