# Results (generated, no summarised files consulted)

Runs root: `data/runs_final3` | runs used: 840 | scenarios: s1_iso_during_call, s2_wan_drop, s2b_ramp_100to30, s2b_step_10, s2b_step_50, s2b_step_up_20to100, s3_stress, s3_tv_and_gaming, s4_capacity_recovery, s7_down_100to15, s7_down_100to8, s7_rampup_30to100, s7_up_20to60, s7_up_30to100

Generated from engine commit `7c6c7235780a`. Every section header below stamps the commit(s) of the runs it renders; a frozen final band may ONLY claim PASS/FAIL if every run in it carries this same hash — any mismatch is flagged per band and per scenario, never pooled silently.

## Delay and throughput, every scenario x arm (mean +/- 95% CI over seeds; t(9)=2.262 for n=10)

Every block below carries an explicit band label, derived from the seed family recorded at load time: `POST-FIX` (seeds 200-209, the controller after the redesign commits), `PRE-FIX` (legacy seeds 0-9/42-51), `DEV` and `EVAL` (the task-2 protocol: parameters were fixed on the DEV band seeds 400-409 BEFORE the EVAL band seeds 500-509 was run ONCE; nothing between them was tuned). A reader never inherits a number of unknown provenance: the label sits directly above the table. The comparison sections further down use the primary band only.

Bulk has TWO columns on purpose (TASK 5a): `sender` is what the generator pushed, `receiver/sink` is what the receiver's sink log totalled -- the delivered number, used for any bulk claim. The post-drop column stays on the TREE counters and is named so: the three are different instruments and are never blended.

### s1_iso_during_call (primary band: EVAL (1100-1109))

- commit provenance: `7c6c7235780a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.68 +/- 0.02 | 3.10 +/- 0.02 | 0.760 +/- 0.025 | NOT AVAILABLE | 96.29 +/- 0.00 | 95.49 +/- 0.00 | (no drop scenario) | 0.909 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.43 +/- 0.02 | 0.45 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 90.96 +/- 0.00 | 90.74 +/- 0.00 | (no drop scenario) | 0.922 +/- 0.000 | NOT AVAILABLE |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 1.42 +/- 0.02 | 0.46 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 90.96 +/- 0.00 | 90.74 +/- 0.00 | (no drop scenario) | 0.922 +/- 0.000 | NOT AVAILABLE |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.04 +/- 0.01 | 0.27 +/- 0.00 | 0.000 +/- 0.000 | NOT AVAILABLE | 47.80 +/- 0.01 | 47.71 +/- 0.00 | (no drop scenario) | 0.999 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 5.21 +/- 5.91 | 0.36 +/- 0.04 | 0.047 +/- 0.032 | NOT AVAILABLE | 71.49 +/- 8.18 | 71.13 +/- 8.09 | (no drop scenario) | 0.967 +/- 0.016 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 11.11 +/- 4.27 | 0.40 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 76.77 +/- 2.60 | 76.47 +/- 2.59 | (no drop scenario) | 0.957 +/- 0.006 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s2_wan_drop (primary band: EVAL (1100-1109))

- commit provenance: `7c6c7235780a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 251.25 +/- 0.06 | 4.29 +/- 0.02 | 8.870 +/- 0.137 | NOT AVAILABLE | 79.68 +/- 0.07 | 77.38 +/- 0.01 | 22.21 +/- 0.05 | 0.950 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 69.93 +/- 1.38 | 0.52 +/- 0.01 | 0.155 +/- 0.011 | NOT AVAILABLE | 75.18 +/- 0.02 | 74.42 +/- 0.02 | 20.12 +/- 0.01 | 0.961 +/- 0.000 | NOT AVAILABLE |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 2.31 +/- 0.04 | 0.32 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.09 +/- 0.00 | 18.06 +/- 0.00 | 18.68 +/- 0.08 | 0.820 +/- 0.000 | NOT AVAILABLE |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 65.21 +/- 1.46 | 0.39 +/- 0.00 | 0.150 +/- 0.000 | NOT AVAILABLE | 41.60 +/- 0.01 | 41.19 +/- 0.02 | 20.06 +/- 0.01 | 0.992 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 19.46 +/- 8.63 | 0.45 +/- 0.02 | 0.035 +/- 0.038 | NOT AVAILABLE | 57.89 +/- 4.60 | 57.16 +/- 4.56 | 21.28 +/- 1.00 | 0.992 +/- 0.005 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 24.96 +/- 11.32 | 0.48 +/- 0.02 | 0.015 +/- 0.024 | NOT AVAILABLE | 62.63 +/- 1.88 | 61.75 +/- 1.83 | 19.34 +/- 0.27 | 0.987 +/- 0.003 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s2b_ramp_100to30 (primary band: EVAL (1100-1109))

- commit provenance: `7c6c7235780a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 822.36 +/- 0.16 | 19.29 +/- 0.12 | 1.327 +/- 0.031 | NOT AVAILABLE | 53.36 +/- 0.01 | 52.63 +/- 0.01 | (no drop scenario) | 0.999 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 132.54 +/- 1.35 | 0.85 +/- 0.01 | 0.497 +/- 0.082 | NOT AVAILABLE | 52.03 +/- 0.01 | 51.33 +/- 0.01 | (no drop scenario) | 1.000 +/- 0.000 | NOT AVAILABLE |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 2.29 +/- 0.02 | 0.48 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 27.16 +/- 0.00 | 27.14 +/- 0.00 | (no drop scenario) | 0.919 +/- 0.000 | NOT AVAILABLE |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 111.29 +/- 3.32 | 0.81 +/- 0.36 | 0.477 +/- 0.329 | NOT AVAILABLE | 38.02 +/- 0.00 | 37.63 +/- 0.00 | (no drop scenario) | 0.982 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 15.61 +/- 5.24 | 0.51 +/- 0.02 | 0.093 +/- 0.037 | NOT AVAILABLE | 37.60 +/- 1.84 | 37.32 +/- 1.81 | (no drop scenario) | 0.979 +/- 0.006 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 24.69 +/- 1.30 | 0.52 +/- 0.02 | 0.003 +/- 0.007 | NOT AVAILABLE | 45.34 +/- 0.97 | 44.99 +/- 1.03 | (no drop scenario) | 0.997 +/- 0.001 | NOT AVAILABLE |

### s2b_step_10 (primary band: EVAL (1100-1109))

- commit provenance: `7c6c7235780a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 246.44 +/- 0.41 | 3.06 +/- 0.39 | 15.325 +/- 0.972 | NOT AVAILABLE | 34.23 +/- 0.02 | NOT AVAILABLE | 10.76 +/- 0.02 | 0.966 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 82.94 +/- 0.62 | 1.05 +/- 0.02 | 1.345 +/- 0.305 | NOT AVAILABLE | 32.05 +/- 0.02 | 31.53 +/- 0.02 | 10.04 +/- 0.01 | 0.954 +/- 0.000 | NOT AVAILABLE |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 5.13 +/- 0.04 | 1.07 +/- 0.03 | 0.000 +/- 0.000 | NOT AVAILABLE | 8.99 +/- 0.00 | 8.97 +/- 0.00 | 9.46 +/- 0.01 | 0.674 +/- 0.000 | NOT AVAILABLE |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 82.52 +/- 0.54 | 1.04 +/- 0.03 | 1.380 +/- 0.303 | NOT AVAILABLE | 20.11 +/- 0.02 | 19.93 +/- 0.02 | 10.02 +/- 0.00 | 0.846 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 74.43 +/- 1.88 | 1.03 +/- 0.05 | 0.430 +/- 0.128 | NOT AVAILABLE | 28.97 +/- 1.06 | 28.48 +/- 1.04 | 1.14 +/- 0.74 | 0.933 +/- 0.008 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 80.84 +/- 1.14 | 1.11 +/- 0.02 | 0.545 +/- 0.122 | NOT AVAILABLE | 29.35 +/- 0.43 | 28.89 +/- 0.43 | 3.35 +/- 0.82 | 0.937 +/- 0.003 | NOT AVAILABLE |

### s2b_step_50 (primary band: EVAL (1100-1109))

- commit provenance: `7c6c7235780a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 496.42 +/- 0.09 | 16.05 +/- 0.12 | 1.150 +/- 0.017 | NOT AVAILABLE | 61.77 +/- 0.01 | 61.01 +/- 0.01 | 50.42 +/- 0.01 | 0.989 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 134.70 +/- 1.76 | 0.81 +/- 0.01 | 0.575 +/- 0.103 | NOT AVAILABLE | 60.20 +/- 0.01 | 59.48 +/- 0.01 | 50.03 +/- 0.00 | 0.992 +/- 0.000 | NOT AVAILABLE |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 1.81 +/- 0.02 | 0.44 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 45.38 +/- 0.00 | 45.32 +/- 0.00 | 47.06 +/- 0.01 | 0.998 +/- 0.000 | NOT AVAILABLE |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 169.28 +/- 2.67 | 0.55 +/- 0.01 | 0.705 +/- 0.074 | NOT AVAILABLE | 48.29 +/- 0.00 | 47.71 +/- 0.00 | 50.00 +/- 0.00 | 1.000 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 12.27 +/- 3.98 | 0.42 +/- 0.03 | 0.085 +/- 0.038 | NOT AVAILABLE | 40.43 +/- 1.20 | 40.07 +/- 1.12 | 22.85 +/- 2.77 | 0.988 +/- 0.003 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 13.62 +/- 2.48 | 0.44 +/- 0.01 | 0.010 +/- 0.015 | NOT AVAILABLE | 47.39 +/- 1.66 | 47.09 +/- 1.71 | 37.68 +/- 2.25 | 0.999 +/- 0.001 | NOT AVAILABLE |

### s2b_step_up_20to100 (primary band: EVAL (1100-1109))

- commit provenance: `7c6c7235780a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 584.50 +/- 0.94 | 1.09 +/- 0.10 | 1.887 +/- 0.144 | NOT AVAILABLE | 19.37 +/- 0.00 | 19.02 +/- 0.00 | 20.00 +/- 0.00 | 0.837 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 2.33 +/- 0.03 | 0.31 +/- 0.00 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.10 +/- 0.00 | 18.06 +/- 0.00 | 18.88 +/- 0.01 | 0.820 +/- 0.000 | NOT AVAILABLE |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 85.63 +/- 1.73 | 0.71 +/- 0.12 | 0.087 +/- 0.072 | NOT AVAILABLE | 76.39 +/- 0.01 | 76.23 +/- 0.01 | 92.48 +/- 0.07 | 0.958 +/- 0.000 | NOT AVAILABLE |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.87 +/- 0.03 | 0.59 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.47 +/- 0.01 | 9.45 +/- 0.00 | 9.93 +/- 0.02 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.85 +/- 0.04 | 0.39 +/- 0.04 | 0.010 +/- 0.011 | NOT AVAILABLE | 14.21 +/- 0.80 | 14.17 +/- 0.80 | 14.50 +/- 1.01 | 0.763 +/- 0.012 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 2.05 +/- 0.18 | 0.34 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 42.38 +/- 1.40 | 42.30 +/- 1.39 | 47.90 +/- 1.67 | 0.993 +/- 0.003 | NOT AVAILABLE |

### s3_stress (primary band: EVAL (1100-1109))

- commit provenance: `7c6c7235780a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 321.45 +/- 1.49 | 82.14 +/- 0.12 | 81.62 +/- 0.11 | (no drop scenario) | 0.416 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 3.70 +/- 0.43 | 76.86 +/- 0.12 | 76.78 +/- 0.12 | (no drop scenario) | 0.429 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 3.44 +/- 0.40 | 76.86 +/- 0.13 | 76.78 +/- 0.12 | (no drop scenario) | 0.429 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 1.94 +/- 0.17 | 33.79 +/- 0.12 | 33.76 +/- 0.11 | (no drop scenario) | 0.581 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 4.18 +/- 2.98 | 53.52 +/- 8.21 | 53.43 +/- 8.21 | (no drop scenario) | 0.503 +/- 0.030 | 1.000 +/- 0.000 |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 18.88 +/- 2.16 | 69.82 +/- 2.15 | 69.56 +/- 2.17 | (no drop scenario) | 0.448 +/- 0.006 | 1.000 +/- 0.000 |

### s3_tv_and_gaming (primary band: EVAL (1100-1109))

- commit provenance: `7c6c7235780a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 3.06 +/- 0.17 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.37 +/- 0.11 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.42 +/- 0.14 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.42 +/- 0.18 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.43 +/- 0.16 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.31 +/- 0.22 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |

#### Per-TV delivered goodput (receiver sampler, mean inst Mbps whole-run / final third)

| arm | n | tv1 | tv2 | tv3 | which band carries the sampler |
| --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 4.54 +/- 0.05 / 5.18 +/- 0.13 | 4.54 +/- 0.05 / 5.42 +/- 0.16 | 4.54 +/- 0.05 / 5.56 +/- 0.16 | per-second (n_sampler=10/10) |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 4.54 +/- 0.05 / 5.18 +/- 0.13 | 4.54 +/- 0.05 / 5.42 +/- 0.16 | 4.54 +/- 0.05 / 5.56 +/- 0.16 | per-second (n_sampler=10/10) |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 4.54 +/- 0.05 / 5.18 +/- 0.14 | 4.54 +/- 0.05 / 5.41 +/- 0.16 | 4.54 +/- 0.05 / 5.56 +/- 0.16 | per-second (n_sampler=10/10) |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 4.53 +/- 0.05 / 5.18 +/- 0.13 | 4.53 +/- 0.05 / 5.42 +/- 0.16 | 4.53 +/- 0.05 / 5.55 +/- 0.16 | per-second (n_sampler=10/10) |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 4.45 +/- 0.05 / 4.93 +/- 0.15 | 4.45 +/- 0.05 / 5.20 +/- 0.17 | 4.45 +/- 0.05 / 5.36 +/- 0.17 | per-second (n_sampler=10/10) |
| ACIQ (controller) | 10 | 4.32 +/- 0.05 / 4.08 +/- 0.17 | 4.32 +/- 0.04 / 4.40 +/- 0.24 | 4.33 +/- 0.04 / 4.61 +/- 0.26 | per-second (n_sampler=10/10) |
- each TV cell is the label's own receiver series; TV streams share the streaming sheet in the controller's tree, so the SPLIT between them is a receiver-side fact and the arm-table's streaming-class counters are the router-side view.


### s4_capacity_recovery (primary band: EVAL (1100-1109))

- commit provenance: `7c6c7235780a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.44 +/- 0.06 | 3.05 +/- 0.03 | 5.953 +/- 0.128 | NOT AVAILABLE | 59.45 +/- 0.01 | 58.26 +/- 0.01 | 20.68 +/- 0.01 | 0.993 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 88.93 +/- 0.98 | 0.61 +/- 0.01 | 0.197 +/- 0.040 | NOT AVAILABLE | 56.51 +/- 0.02 | 56.03 +/- 0.03 | 20.04 +/- 0.00 | 0.996 +/- 0.000 | NOT AVAILABLE |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 2.71 +/- 0.02 | 0.48 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.08 +/- 0.00 | 18.06 +/- 0.00 | 18.78 +/- 0.01 | 0.820 +/- 0.000 | NOT AVAILABLE |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 90.97 +/- 0.86 | 0.53 +/- 0.01 | 0.213 +/- 0.048 | NOT AVAILABLE | 34.13 +/- 0.01 | 33.83 +/- 0.01 | 20.01 +/- 0.00 | 0.966 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 13.99 +/- 8.37 | 0.53 +/- 0.03 | 0.050 +/- 0.023 | NOT AVAILABLE | 43.73 +/- 4.39 | 43.19 +/- 4.22 | 12.30 +/- 1.34 | 0.991 +/- 0.008 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 15.61 +/- 7.90 | 0.52 +/- 0.03 | 0.000 +/- 0.000 | NOT AVAILABLE | 46.45 +/- 2.10 | 45.94 +/- 2.06 | 15.62 +/- 0.61 | 0.998 +/- 0.001 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s7_down_100to15 (primary band: EVAL (1100-1109))

- commit provenance: `7c6c7235780a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 246.15 +/- 0.17 | 2.41 +/- 0.11 | 9.740 +/- 0.157 | NOT AVAILABLE | 37.76 +/- 0.04 | NOT AVAILABLE | 15.72 +/- 0.01 | 0.981 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 86.10 +/- 0.53 | 0.80 +/- 0.05 | 0.440 +/- 0.104 | NOT AVAILABLE | 35.55 +/- 0.02 | 35.14 +/- 0.02 | 15.04 +/- 0.01 | 0.972 +/- 0.000 | NOT AVAILABLE |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 3.62 +/- 0.03 | 0.82 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 13.54 +/- 0.00 | 13.52 +/- 0.00 | 14.18 +/- 0.01 | 0.752 +/- 0.000 | NOT AVAILABLE |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 87.04 +/- 0.58 | 0.77 +/- 0.01 | 0.460 +/- 0.159 | NOT AVAILABLE | 23.66 +/- 0.02 | 23.37 +/- 0.01 | 15.02 +/- 0.00 | 0.887 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 26.60 +/- 3.97 | 0.75 +/- 0.01 | 0.075 +/- 0.048 | NOT AVAILABLE | 31.54 +/- 0.16 | 31.14 +/- 0.16 | 12.31 +/- 0.49 | 0.951 +/- 0.001 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 44.50 +/- 5.55 | 0.71 +/- 0.01 | 0.015 +/- 0.017 | NOT AVAILABLE | 30.90 +/- 0.73 | 30.48 +/- 0.72 | 12.54 +/- 0.17 | 0.947 +/- 0.005 | NOT AVAILABLE |

### s7_down_100to8 (primary band: EVAL (1100-1109))

- commit provenance: `7c6c7235780a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 246.58 +/- 0.16 | 3.69 +/- 0.48 | 19.020 +/- 0.299 | NOT AVAILABLE | 32.84 +/- 0.07 | NOT AVAILABLE | 8.77 +/- 0.01 | 0.959 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 81.09 +/- 1.35 | 1.22 +/- 0.01 | 1.405 +/- 0.484 | NOT AVAILABLE | 30.63 +/- 0.04 | 30.01 +/- 0.04 | 8.04 +/- 0.00 | 0.945 +/- 0.000 | NOT AVAILABLE |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 6.23 +/- 0.05 | 1.31 +/- 0.03 | 0.000 +/- 0.000 | NOT AVAILABLE | 7.17 +/- 0.00 | 7.16 +/- 0.00 | 7.57 +/- 0.01 | 0.641 +/- 0.000 | NOT AVAILABLE |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 78.39 +/- 0.68 | 1.30 +/- 0.14 | 0.630 +/- 0.175 | NOT AVAILABLE | 18.68 +/- 0.01 | 18.51 +/- 0.02 | 8.02 +/- 0.00 | 0.828 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 76.03 +/- 1.10 | 1.16 +/- 0.03 | 0.630 +/- 0.183 | NOT AVAILABLE | 27.36 +/- 0.83 | 26.80 +/- 0.81 | 0.61 +/- 0.55 | 0.921 +/- 0.007 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 81.07 +/- 0.91 | 1.20 +/- 0.03 | 0.830 +/- 0.193 | NOT AVAILABLE | 28.08 +/- 0.23 | 27.53 +/- 0.22 | 2.68 +/- 0.94 | 0.927 +/- 0.002 | NOT AVAILABLE |

### s7_rampup_30to100 (primary band: EVAL (1100-1109))

- commit provenance: `7c6c7235780a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 383.70 +/- 3.71 | 0.92 +/- 0.05 | 1.233 +/- 0.105 | NOT AVAILABLE | 28.95 +/- 0.00 | 28.58 +/- 0.00 | (no drop scenario) | 0.934 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.99 +/- 0.05 | 0.48 +/- 0.36 | 0.000 +/- 0.000 | NOT AVAILABLE | 27.19 +/- 0.01 | 27.14 +/- 0.00 | (no drop scenario) | 0.920 +/- 0.000 | NOT AVAILABLE |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 187.62 +/- 6.37 | 0.77 +/- 0.02 | 0.340 +/- 0.070 | NOT AVAILABLE | 69.49 +/- 0.01 | 69.19 +/- 0.01 | (no drop scenario) | 0.974 +/- 0.000 | NOT AVAILABLE |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.41 +/- 0.03 | 0.44 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | (no drop scenario) | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.79 +/- 0.09 | 0.38 +/- 0.06 | 0.027 +/- 0.019 | NOT AVAILABLE | 21.83 +/- 2.62 | 21.79 +/- 2.62 | (no drop scenario) | 0.863 +/- 0.031 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 9.06 +/- 5.32 | 0.53 +/- 0.08 | 0.007 +/- 0.010 | NOT AVAILABLE | 54.33 +/- 2.35 | 54.22 +/- 2.34 | (no drop scenario) | 0.998 +/- 0.002 | NOT AVAILABLE |

### s7_up_20to60 (primary band: EVAL (1100-1109))

- commit provenance: `7c6c7235780a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 584.32 +/- 0.50 | 1.12 +/- 0.10 | 1.763 +/- 0.124 | NOT AVAILABLE | 19.37 +/- 0.00 | 19.02 +/- 0.00 | 20.00 +/- 0.00 | 0.837 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 2.29 +/- 0.03 | 0.34 +/- 0.00 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.10 +/- 0.00 | 18.06 +/- 0.00 | 18.88 +/- 0.00 | 0.820 +/- 0.000 | NOT AVAILABLE |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 86.80 +/- 1.40 | 0.73 +/- 0.25 | 0.060 +/- 0.031 | NOT AVAILABLE | 47.41 +/- 0.00 | 47.25 +/- 0.00 | 55.86 +/- 0.07 | 0.999 +/- 0.000 | NOT AVAILABLE |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.80 +/- 0.05 | 0.57 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.46 +/- 0.00 | 9.45 +/- 0.00 | 9.94 +/- 0.00 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.84 +/- 0.04 | 0.39 +/- 0.04 | 0.010 +/- 0.011 | NOT AVAILABLE | 14.72 +/- 0.93 | 14.69 +/- 0.93 | 15.18 +/- 1.19 | 0.771 +/- 0.014 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 8.71 +/- 2.55 | 0.43 +/- 0.01 | 0.007 +/- 0.010 | NOT AVAILABLE | 34.69 +/- 0.92 | 34.59 +/- 0.93 | 38.75 +/- 0.78 | 0.968 +/- 0.005 | NOT AVAILABLE |

### s7_up_30to100 (primary band: EVAL (1100-1109))

- commit provenance: `7c6c7235780a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 391.19 +/- 0.34 | 1.00 +/- 0.09 | 1.007 +/- 0.088 | NOT AVAILABLE | 28.95 +/- 0.00 | 28.58 +/- 0.00 | 30.00 +/- 0.00 | 0.934 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.99 +/- 0.02 | 0.28 +/- 0.00 | 0.000 +/- 0.000 | NOT AVAILABLE | 27.19 +/- 0.01 | 27.14 +/- 0.00 | 28.27 +/- 0.01 | 0.920 +/- 0.000 | NOT AVAILABLE |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 94.79 +/- 6.13 | 0.71 +/- 0.15 | 0.123 +/- 0.057 | NOT AVAILABLE | 78.46 +/- 0.01 | 78.17 +/- 0.01 | 92.98 +/- 0.03 | 0.953 +/- 0.000 | NOT AVAILABLE |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.28 +/- 0.02 | 0.44 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | 14.90 +/- 0.00 | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.59 +/- 0.04 | 0.33 +/- 0.06 | 0.010 +/- 0.016 | NOT AVAILABLE | 19.72 +/- 3.07 | 19.67 +/- 3.08 | 19.77 +/- 4.12 | 0.836 +/- 0.038 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 9.20 +/- 5.14 | 0.37 +/- 0.01 | 0.003 +/- 0.007 | NOT AVAILABLE | 55.62 +/- 1.26 | 55.52 +/- 1.24 | 63.67 +/- 3.52 | 0.997 +/- 0.001 | NOT AVAILABLE |

## ACIQ vs every arm (positive % is better ACIQ on the metric at the head of the column; a cell like `41.0x` is the multiplicative factor when the baseline is so close to zero that a percentage would mislead)

| scenario | vs arm | call p95 delta % | CI overlap? | bulk delta % | CI overlap? |
| --- | --- | --- | --- | --- | --- |
Bulk compares are POST-DROP ONLY in scenarios with a capacity drop (same `bulk_mbps` whole-run mean otherwise): the whole-run number dilutes the post-drop regime with a saturated prefix, which is the opposite of the decision those scenarios exist to measure.

| s1_iso_during_call | B0 (default router, pfifo) | 22.6x | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | -677.7 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s1_iso_during_call | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | -683.1 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s1_iso_during_call | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -973.0 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s1_iso_during_call | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -113.2 | overlap | NOT AVAILABLE | NOT AVAILABLE |
| s2_wan_drop | B0 (default router, pfifo) | +90.1 | disjoint | -12.9 | disjoint |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | +64.3 | disjoint | -3.9 | disjoint |
| s2_wan_drop | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | -978.4 | disjoint | +3.6 | disjoint |
| s2_wan_drop | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +61.7 | disjoint | -3.6 | disjoint |
| s2_wan_drop | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -28.2 | overlap | -9.1 | disjoint |
| s2b_ramp_100to30 | B0 (default router, pfifo) | 33.3x | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_ramp_100to30 | CAKE-static (95% of pre-drop link, set and forget) | +81.4 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_ramp_100to30 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | -978.5 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +77.8 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -58.2 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_step_10 | B0 (default router, pfifo) | +67.2 | disjoint | -68.9 | disjoint |
| s2b_step_10 | CAKE-static (95% of pre-drop link, set and forget) | +2.5 | disjoint | -66.6 | disjoint |
| s2b_step_10 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | -1475.9 | disjoint | -64.6 | disjoint |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +2.0 | overlap | -66.6 | disjoint |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -8.6 | disjoint | +195.1 | disjoint |
| s2b_step_50 | B0 (default router, pfifo) | 36.5x | disjoint | -25.3 | disjoint |
| s2b_step_50 | CAKE-static (95% of pre-drop link, set and forget) | +89.9 | disjoint | -24.7 | disjoint |
| s2b_step_50 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | -651.3 | disjoint | -19.9 | disjoint |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +92.0 | disjoint | -24.6 | disjoint |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -11.0 | overlap | +64.9 | disjoint |
| s2b_step_up_20to100 | B0 (default router, pfifo) | 284.5x | disjoint | +139.5 | disjoint |
| s2b_step_up_20to100 | CAKE-static (95% of pre-drop link, set and forget) | +11.6 | disjoint | +153.8 | disjoint |
| s2b_step_up_20to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 41.7x | disjoint | -48.2 | disjoint |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -9.8 | overlap | +382.4 | disjoint |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -10.8 | overlap | +230.4 | disjoint |
| s3_stress | B0 (default router, pfifo) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_stress | CAKE-static (95% of pre-drop link, set and forget) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_stress | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_tv_and_gaming | B0 (default router, pfifo) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_tv_and_gaming | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_tv_and_gaming | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_tv_and_gaming | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s4_capacity_recovery | B0 (default router, pfifo) | +93.8 | disjoint | -24.5 | disjoint |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | +82.5 | disjoint | -22.0 | disjoint |
| s4_capacity_recovery | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | -476.7 | disjoint | -16.8 | disjoint |
| s4_capacity_recovery | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +82.8 | disjoint | -21.9 | disjoint |
| s4_capacity_recovery | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -11.5 | overlap | +27.1 | disjoint |
| s7_down_100to15 | B0 (default router, pfifo) | +81.9 | disjoint | -20.3 | disjoint |
| s7_down_100to15 | CAKE-static (95% of pre-drop link, set and forget) | +48.3 | disjoint | -16.7 | disjoint |
| s7_down_100to15 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | -1128.0 | disjoint | -11.6 | disjoint |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +48.9 | disjoint | -16.5 | disjoint |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -67.3 | disjoint | +1.9 | overlap |
| s7_down_100to8 | B0 (default router, pfifo) | +67.1 | disjoint | -69.4 | disjoint |
| s7_down_100to8 | CAKE-static (95% of pre-drop link, set and forget) | +0.0 | overlap | -66.6 | disjoint |
| s7_down_100to8 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | -1201.1 | disjoint | -64.5 | disjoint |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -3.4 | disjoint | -66.5 | disjoint |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -6.6 | disjoint | +342.2 | disjoint |
| s7_rampup_30to100 | B0 (default router, pfifo) | 42.3x | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s7_rampup_30to100 | CAKE-static (95% of pre-drop link, set and forget) | -355.3 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s7_rampup_30to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 20.7x | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -542.8 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -406.3 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s7_up_20to60 | B0 (default router, pfifo) | 67.1x | disjoint | +93.8 | disjoint |
| s7_up_20to60 | CAKE-static (95% of pre-drop link, set and forget) | -279.5 | disjoint | +105.3 | disjoint |
| s7_up_20to60 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | +90.0 | disjoint | -30.6 | disjoint |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -383.5 | disjoint | +289.9 | disjoint |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -373.6 | disjoint | +155.3 | disjoint |
| s7_up_30to100 | B0 (default router, pfifo) | 42.5x | disjoint | +112.2 | disjoint |
| s7_up_30to100 | CAKE-static (95% of pre-drop link, set and forget) | -363.1 | disjoint | +125.2 | disjoint |
| s7_up_30to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | +90.3 | disjoint | -31.5 | disjoint |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -621.3 | disjoint | +327.2 | disjoint |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -479.4 | disjoint | +222.1 | disjoint |

## Where ACIQ is worse (the honest column)

Every row above where ACIQ's signed delta is negative, collected so a CAKE win cannot hide behind the aggregate. Empty means no such pair exists in the runs found.

| scenario | vs arm | metric where ACIQ is worse |
| --- | --- | --- |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | call p95 -677.7 |
| s1_iso_during_call | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | call p95 -683.1 |
| s1_iso_during_call | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -973.0 |
| s1_iso_during_call | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -113.2 |
| s2_wan_drop | B0 (default router, pfifo) | post-drop bulk Mbps -12.9 |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -3.9 |
| s2_wan_drop | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | call p95 -978.4 |
| s2_wan_drop | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -3.6 |
| s2_wan_drop | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -28.2 and post-drop bulk Mbps -9.1 |
| s2b_ramp_100to30 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | call p95 -978.5 |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -58.2 |
| s2b_step_10 | B0 (default router, pfifo) | post-drop bulk Mbps -68.9 |
| s2b_step_10 | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -66.6 |
| s2b_step_10 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | call p95 -1475.9 and post-drop bulk Mbps -64.6 |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -66.6 |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -8.6 |
| s2b_step_50 | B0 (default router, pfifo) | post-drop bulk Mbps -25.3 |
| s2b_step_50 | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -24.7 |
| s2b_step_50 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | call p95 -651.3 and post-drop bulk Mbps -19.9 |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -24.6 |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -11.0 |
| s2b_step_up_20to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | post-drop bulk Mbps -48.2 |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -9.8 |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -10.8 |
| s4_capacity_recovery | B0 (default router, pfifo) | post-drop bulk Mbps -24.5 |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -22.0 |
| s4_capacity_recovery | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | call p95 -476.7 and post-drop bulk Mbps -16.8 |
| s4_capacity_recovery | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -21.9 |
| s4_capacity_recovery | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -11.5 |
| s7_down_100to15 | B0 (default router, pfifo) | post-drop bulk Mbps -20.3 |
| s7_down_100to15 | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -16.7 |
| s7_down_100to15 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | call p95 -1128.0 and post-drop bulk Mbps -11.6 |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -16.5 |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -67.3 |
| s7_down_100to8 | B0 (default router, pfifo) | post-drop bulk Mbps -69.4 |
| s7_down_100to8 | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -66.6 |
| s7_down_100to8 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | call p95 -1201.1 and post-drop bulk Mbps -64.5 |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -3.4 and post-drop bulk Mbps -66.5 |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -6.6 |
| s7_rampup_30to100 | CAKE-static (95% of pre-drop link, set and forget) | call p95 -355.3 |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -542.8 |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -406.3 |
| s7_up_20to60 | CAKE-static (95% of pre-drop link, set and forget) | call p95 -279.5 |
| s7_up_20to60 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | post-drop bulk Mbps -30.6 |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -383.5 |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -373.6 |
| s7_up_30to100 | CAKE-static (95% of pre-drop link, set and forget) | call p95 -363.1 |
| s7_up_30to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | post-drop bulk Mbps -31.5 |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -621.3 |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -479.4 |

## Where CAKE-static wins

The honest column above lists every rival; this one isolates the set-and-forget rival that matters for the design claim. A CAKE win on a metric is stated here verbatim; nothing is re-derived and nothing is argued away. CI overlap of the underlying seed samples is in the table above (`CI overlap?` column).

| scenario | metric where CAKE-static beats ACIQ | see column in the ACIQ-vs-every table |
| --- | --- | --- |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | call p95 -677.7 |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -3.9 |
| s2b_step_10 | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -66.6 |
| s2b_step_50 | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -24.7 |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -22.0 |
| s7_down_100to15 | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -16.7 |
| s7_down_100to8 | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -66.6 |
| s7_rampup_30to100 | CAKE-static (95% of pre-drop link, set and forget) | call p95 -355.3 |
| s7_up_20to60 | CAKE-static (95% of pre-drop link, set and forget) | call p95 -279.5 |
| s7_up_30to100 | CAKE-static (95% of pre-drop link, set and forget) | call p95 -363.1 |

## ACIQ adaptation and capacity accuracy (from the same runs above)

| scenario | n | bind: drop -> first applied <=1.05x post-drop (s) | bind: drop -> first applied <=1.25x post-drop (s) | final estimate | configured end link | estimate error % |
| --- | --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 78.63 +/- 3.02 | 100.0 +/- 0.0 | mean abs 21.4% (seed0: 75.39/100.0 (24.6% off)) |
| s2_wan_drop | 10 | 5.80 (n=7) | 1.37 (n=10) | 21.44 +/- 1.73 | 20.0 +/- 0.0 | mean abs 10.5% (seed0: 20.69/20.0 (3.5% off)) |
| s2b_ramp_100to30 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 25.26 +/- 1.22 | 30.0 +/- 0.0 | mean abs 15.8% (seed0: 27.46/30.0 (8.5% off)) |
| s2b_step_10 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 11.61 +/- 0.27 | 10.0 +/- 0.0 | mean abs 16.1% (seed0: 11.98/10.0 (19.8% off)) |
| s2b_step_50 | 10 | 2.03 (n=10) | 1.91 (n=10) | 40.79 +/- 4.60 | 50.0 +/- 0.0 | mean abs 20.4% (seed0: 42.27/50.0 (15.5% off)) |
| s2b_step_up_20to100 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | 3.44 (n=3) | 38.82 +/- 1.89 | 100.0 +/- 0.0 | mean abs 61.2% (seed0: 41.80/100.0 (58.2% off)) |
| s3_stress | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 84.47 +/- 3.41 | 100.0 +/- 0.0 | mean abs 15.5% (seed0: 81.18/100.0 (18.8% off)) |
| s3_tv_and_gaming | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 40.46 +/- 14.40 | 100.0 +/- 0.0 | mean abs 59.5% (seed0: 32.86/100.0 (67.1% off)) |
| s4_capacity_recovery | 10 | 7.11 (n=10) | 1.27 (n=10) | 16.25 +/- 1.03 | 20.0 +/- 0.0 | mean abs 18.7% (seed0: 18.30/20.0 (8.5% off)) |
| s7_down_100to15 | 10 | 4.95 (n=10) | 1.97 (n=10) | 13.56 +/- 0.26 | 15.0 +/- 0.0 | mean abs 9.6% (seed0: 13.60/15.0 (9.3% off)) |
| s7_down_100to8 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 9.03 +/- 0.25 | 8.0 +/- 0.0 | mean abs 12.9% (seed0: 8.91/8.0 (11.4% off)) |
| s7_rampup_30to100 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 52.25 +/- 3.06 | 100.0 +/- 0.0 | mean abs 47.8% (seed0: 52.51/100.0 (47.5% off)) |
| s7_up_20to60 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | 4.78 (n=1) | 32.79 +/- 2.13 | 60.0 +/- 0.0 | mean abs 45.3% (seed0: 36.22/60.0 (39.6% off)) |
| s7_up_30to100 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 51.69 +/- 2.47 | 100.0 +/- 0.0 | mean abs 48.3% (seed0: 49.94/100.0 (50.1% off)) |
## Controller resources (ACIQ adaptive runs only; from each result's resources block)

| scenario | n | cpu mean frac | decision p95 ms | decision max ms | max RSS bytes |
| --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | 10 | 0.0076 +/- 0.0002 | 76.14 +/- 1.79 | 93.00 +/- 12.80 | 28512666 +/- 411125 |
| s2_wan_drop | 10 | 0.0079 +/- 0.0001 | 76.27 +/- 1.49 | 96.77 +/- 8.95 | 29179085 +/- 601030 |
| s2b_ramp_100to30 | 10 | 0.0081 +/- 0.0001 | 76.24 +/- 1.08 | 86.62 +/- 6.20 | 30161715 +/- 755795 |
| s2b_step_10 | 10 | 0.0116 +/- 0.0005 | 116.44 +/- 9.16 | 180.34 +/- 32.02 | 29661184 +/- 693668 |
| s2b_step_50 | 10 | 0.0078 +/- 0.0002 | 75.80 +/- 2.65 | 103.98 +/- 42.17 | 29151232 +/- 552614 |
| s2b_step_up_20to100 | 10 | 0.0076 +/- 0.0001 | 76.31 +/- 1.43 | 101.35 +/- 30.61 | 30079795 +/- 745797 |
| s3_stress | 10 | 0.0086 +/- 0.0002 | 81.06 +/- 0.89 | 89.39 +/- 3.82 | 29502259 +/- 641549 |
| s3_tv_and_gaming | 10 | 0.0071 +/- 0.0004 | 70.18 +/- 1.11 | 75.64 +/- 2.70 | 29151642 +/- 551602 |
| s4_capacity_recovery | 10 | 0.0080 +/- 0.0001 | 75.45 +/- 1.04 | 91.93 +/- 8.79 | 30088806 +/- 757180 |
| s7_down_100to15 | 10 | 0.0082 +/- 0.0003 | 82.60 +/- 6.09 | 122.55 +/- 40.34 | 28931277 +/- 523732 |
| s7_down_100to8 | 10 | 0.0097 +/- 0.0001 | 79.26 +/- 3.37 | 107.13 +/- 28.29 | 29578035 +/- 651477 |
| s7_rampup_30to100 | 10 | 0.0091 +/- 0.0008 | 106.10 +/- 19.58 | 140.43 +/- 38.08 | 29890150 +/- 764145 |
| s7_up_20to60 | 10 | 0.0076 +/- 0.0001 | 76.49 +/- 1.04 | 92.55 +/- 13.32 | 30053990 +/- 799294 |
| s7_up_30to100 | 10 | 0.0077 +/- 0.0001 | 76.46 +/- 1.69 | 83.92 +/- 3.30 | 30070784 +/- 786386 |
- CPU context (adaptive vs adaptive): CAKE-adaptive runs at 0.49x the ACIQ CPU fraction on the shared scenario(s): s1_iso_during_call 0.49x, s2_wan_drop 0.53x, s2b_ramp_100to30 0.56x, s2b_step_10 0.43x, s2b_step_50 0.54x, s2b_step_up_20to100 0.44x, s3_stress 0.48x, s3_tv_and_gaming 0.52x, s4_capacity_recovery 0.51x, s7_down_100to15 0.51x, s7_down_100to8 0.45x, s7_rampup_30to100 0.48x, s7_up_20to60 0.47x, s7_up_30to100 0.48x. The cause must be read from the artifacts (CPU profile, decision cadence), not assumed.

## Fairness detail (workload-rate Jain; per-class minima over ASSIGNED classes only, same scope for every mode)

| scenario | arm | n | jain mean +/- CI | demand-jain mean +/- CI | flows used | min over time (per label, via carrying class) |
| --- | --- | --- | --- | --- | --- | --- |
demand-jain: Jain over per-flow satisfied-demand ratios (achieved/demand, demand self-reported by the generator; elastic flows without a declared demand are excluded by definition -- see aciq/fairness.py). A scenario flows all-elastic has no such index and prints NOT AVAILABLE rather than a substitute.

Per-tick counter attribution (fix 18): ACIQ's tree has one leaf per class; the baselines' single-class tree carries the WHOLE link on the 1:50 leaf. New artefacts sample that aggregate under `unknown` (an aggregate can no longer masquerade as a software_update class); artefacts from before this change stored the same aggregate under `software_update`, and consumers that fall back to the legacy label must name it -- the post-drop bulk column does exactly that.

| s1_iso_during_call | B0 (default router, pfifo) | 10 | 0.909 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=99.8; call via unknown=99.8; bulk via unknown=99.8; call via unknown=99.8; bulk via unknown=99.7; call via unknown=99.7 |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.922 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=94.5; call via unknown=94.5; bulk via unknown=95; call via unknown=95; bulk via unknown=95; call via unknown=95 |
| s1_iso_during_call | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 0.922 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=94.9; call via unknown=94.9; bulk via unknown=95; call via unknown=95; bulk via unknown=95; call via unknown=95 |
| s1_iso_during_call | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.999 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=49.9; call via unknown=49.9; bulk via unknown=49.9; call via unknown=49.9; bulk via unknown=49.9; call via unknown=49.9 |
| s1_iso_during_call | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.967 +/- 0.016 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=62.6; call via unknown=62.6; bulk via unknown=77; call via unknown=77; bulk via unknown=30; call via unknown=30 |
| s1_iso_during_call | ACIQ (controller) | 10 | 0.957 +/- 0.006 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2_wan_drop | B0 (default router, pfifo) | 10 | 0.950 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=19.7; call via unknown=19.7; bulk via unknown=19.9; call via unknown=19.9 |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.961 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20 |
| s2_wan_drop | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 0.820 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19; call via unknown=19; bulk via unknown=19; call via unknown=19; bulk via unknown=19; call via unknown=19 |
| s2_wan_drop | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.992 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20 |
| s2_wan_drop | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.992 +/- 0.005 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19; call via unknown=19; bulk via unknown=17.5; call via unknown=17.5; bulk via unknown=39.1; call via unknown=39.1 |
| s2_wan_drop | ACIQ (controller) | 10 | 0.987 +/- 0.003 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_ramp_100to30 | B0 (default router, pfifo) | 10 | 0.999 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=29.8; call via unknown=29.8; bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=29.9; call via unknown=29.9 |
| s2b_ramp_100to30 | CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.000 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=30; call via unknown=30; bulk via unknown=29.9; call via unknown=29.9 |
| s2b_ramp_100to30 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 0.919 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=28.5; call via unknown=28.5; bulk via unknown=28.5; call via unknown=28.5; bulk via unknown=28.5; call via unknown=28.5 |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.982 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=30; call via unknown=30; bulk via unknown=29.9; call via unknown=29.9 |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.979 +/- 0.006 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=13.3; call via unknown=13.3; bulk via unknown=13.3; call via unknown=13.3; bulk via unknown=13.3; call via unknown=13.3 |
| s2b_ramp_100to30 | ACIQ (controller) | 10 | 0.997 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_10 | B0 (default router, pfifo) | 10 | 0.966 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.85; call via unknown=9.85; bulk via unknown=9.86; call via unknown=9.86; bulk via unknown=9.69; call via unknown=9.69 |
| s2b_step_10 | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.954 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.99; call via unknown=9.99 |
| s2b_step_10 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 0.674 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.48; call via unknown=9.48; bulk via unknown=9.48; call via unknown=9.48; bulk via unknown=9.48; call via unknown=9.48 |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.846 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.97; call via unknown=9.97 |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.933 +/- 0.008 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=0.00229; call via unknown=0.00229; bulk via unknown=0.0116; call via unknown=0.0116; bulk via unknown=0; call via unknown=0 |
| s2b_step_10 | ACIQ (controller) | 10 | 0.937 +/- 0.003 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_50 | B0 (default router, pfifo) | 10 | 0.989 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=49.8; call via unknown=49.8; bulk via unknown=49.8; call via unknown=49.8; bulk via unknown=49.9; call via unknown=49.9 |
| s2b_step_50 | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.992 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=49.9; call via unknown=49.9; bulk via unknown=49.9; call via unknown=49.9; bulk via unknown=49.9; call via unknown=49.9 |
| s2b_step_50 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 0.998 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=47.5; call via unknown=47.5; bulk via unknown=47.4; call via unknown=47.4; bulk via unknown=47.4; call via unknown=47.4 |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.000 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=49.9; call via unknown=49.9; bulk via unknown=50; call via unknown=50; bulk via unknown=50; call via unknown=50 |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.988 +/- 0.003 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=13.3; call via unknown=13.3; bulk via unknown=13.3; call via unknown=13.3; bulk via unknown=13.3; call via unknown=13.3 |
| s2b_step_50 | ACIQ (controller) | 10 | 0.999 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_up_20to100 | B0 (default router, pfifo) | 10 | 0.837 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19.9; call via unknown=19.9; bulk via unknown=20; call via unknown=20; bulk via unknown=19.8; call via unknown=19.8 |
| s2b_step_up_20to100 | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.820 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19; call via unknown=19; bulk via unknown=18.9; call via unknown=18.9; bulk via unknown=19; call via unknown=19 |
| s2b_step_up_20to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 0.958 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20 |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.683 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.99; call via unknown=9.99; bulk via unknown=9.98; call via unknown=9.98 |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.763 +/- 0.012 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=13.3; call via unknown=13.3; bulk via unknown=15.5; call via unknown=15.5; bulk via unknown=13.3; call via unknown=13.3 |
| s2b_step_up_20to100 | ACIQ (controller) | 10 | 0.993 +/- 0.003 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s3_stress | B0 (default router, pfifo) | 10 | 0.416 +/- 0.000 | 1.000 +/- 0.000 | 5.0 +/- 0.0 | bulk via unknown=99.4; game via unknown=99.4; tv1 via unknown=99.4; tv2 via unknown=99.4; tv3 via unknown=99.4; bulk via unknown=99.7 |
| s3_stress | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.429 +/- 0.000 | 1.000 +/- 0.000 | 5.0 +/- 0.0 | bulk via unknown=95; game via unknown=95; tv1 via unknown=95; tv2 via unknown=95; tv3 via unknown=95; bulk via unknown=95 |
| s3_stress | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 0.429 +/- 0.000 | 1.000 +/- 0.000 | 5.0 +/- 0.0 | bulk via unknown=94.7; game via unknown=94.7; tv1 via unknown=94.7; tv2 via unknown=94.7; tv3 via unknown=94.7; bulk via unknown=95 |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.581 +/- 0.000 | 1.000 +/- 0.000 | 5.0 +/- 0.0 | bulk via unknown=50; game via unknown=50; tv1 via unknown=50; tv2 via unknown=50; tv3 via unknown=50; bulk via unknown=49.9 |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.503 +/- 0.030 | 1.000 +/- 0.000 | 5.0 +/- 0.0 | bulk via unknown=47.1; game via unknown=47.1; tv1 via unknown=47.1; tv2 via unknown=47.1; tv3 via unknown=47.1; bulk via unknown=62.9 |
| s3_stress | ACIQ (controller) | 10 | 0.448 +/- 0.006 | 1.000 +/- 0.000 | 5.0 +/- 0.0 | bulk=0; game via unknown=0; tv1 via unknown=0; tv2 via unknown=0; tv3 via unknown=0; bulk=0 |
| s3_tv_and_gaming | B0 (default router, pfifo) | 10 | 0.510 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=4.73; tv1 via unknown=4.73; tv2 via unknown=4.73; tv3 via unknown=4.73; game via unknown=4.63; tv1 via unknown=4.63 |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.510 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=4.64; tv1 via unknown=4.64; tv2 via unknown=4.64; tv3 via unknown=4.64; game via unknown=4.64; tv1 via unknown=4.64 |
| s3_tv_and_gaming | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 0.510 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=4.68; tv1 via unknown=4.68; tv2 via unknown=4.68; tv3 via unknown=4.68; game via unknown=4.64; tv1 via unknown=4.64 |
| s3_tv_and_gaming | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.510 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=4.74; tv1 via unknown=4.74; tv2 via unknown=4.74; tv3 via unknown=4.74; game via unknown=4.64; tv1 via unknown=4.64 |
| s3_tv_and_gaming | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.510 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=4.7; tv1 via unknown=4.7; tv2 via unknown=4.7; tv3 via unknown=4.7; game via unknown=4.7; tv1 via unknown=4.7 |
| s3_tv_and_gaming | ACIQ (controller) | 10 | 0.510 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=0; tv1 via unknown=0; tv2 via unknown=0; tv3 via unknown=0; game via unknown=0; tv1 via unknown=0 |
| s4_capacity_recovery | B0 (default router, pfifo) | 10 | 0.993 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20; bulk via unknown=19.9; call via unknown=19.9 |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.996 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20; bulk via unknown=19.9; call via unknown=19.9 |
| s4_capacity_recovery | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 0.820 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19; call via unknown=19; bulk via unknown=19; call via unknown=19; bulk via unknown=19; call via unknown=19 |
| s4_capacity_recovery | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.966 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19.9; call via unknown=19.9; bulk via unknown=20; call via unknown=20; bulk via unknown=19.9; call via unknown=19.9 |
| s4_capacity_recovery | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.991 +/- 0.008 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=13.3; call via unknown=13.3; bulk via unknown=13.3; call via unknown=13.3; bulk via unknown=0.0234; call via unknown=0.0234 |
| s4_capacity_recovery | ACIQ (controller) | 10 | 0.998 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_down_100to15 | B0 (default router, pfifo) | 10 | 0.981 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=14.9; call via unknown=14.9; bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15 |
| s7_down_100to15 | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.972 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15 |
| s7_down_100to15 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 0.752 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=14.2; call via unknown=14.2; bulk via unknown=14.2; call via unknown=14.2; bulk via unknown=14.2; call via unknown=14.2 |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.887 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15 |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.951 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=0; call via unknown=0; bulk via unknown=0.0117; call via unknown=0.0117; bulk via unknown=0.0023; call via unknown=0.0023 |
| s7_down_100to15 | ACIQ (controller) | 10 | 0.947 +/- 0.005 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_down_100to8 | B0 (default router, pfifo) | 10 | 0.959 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=7.83; call via unknown=7.83; bulk via unknown=7.83; call via unknown=7.83; bulk via unknown=7.78; call via unknown=7.78 |
| s7_down_100to8 | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.945 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=7.97; call via unknown=7.97; bulk via unknown=7.96; call via unknown=7.96; bulk via unknown=7.95; call via unknown=7.95 |
| s7_down_100to8 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 0.641 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=7.59; call via unknown=7.59; bulk via unknown=7.59; call via unknown=7.59; bulk via unknown=7.59; call via unknown=7.59 |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.828 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=7.97; call via unknown=7.97; bulk via unknown=7.97; call via unknown=7.97; bulk via unknown=7.97; call via unknown=7.97 |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.921 +/- 0.007 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=0; call via unknown=0; bulk via unknown=0.00936; call via unknown=0.00936; bulk via unknown=0; call via unknown=0 |
| s7_down_100to8 | ACIQ (controller) | 10 | 0.927 +/- 0.002 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_rampup_30to100 | B0 (default router, pfifo) | 10 | 0.934 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=30; call via unknown=30; bulk via unknown=29.7; call via unknown=29.7; bulk via unknown=30; call via unknown=30 |
| s7_rampup_30to100 | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.920 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=28.5; call via unknown=28.5; bulk via unknown=28.4; call via unknown=28.4; bulk via unknown=28.5; call via unknown=28.5 |
| s7_rampup_30to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 0.974 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=30; call via unknown=30; bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=29.9; call via unknown=29.9 |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.764 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15 |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.863 +/- 0.031 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15.1; call via unknown=15.1; bulk via unknown=23.1; call via unknown=23.1; bulk via unknown=17.2; call via unknown=17.2 |
| s7_rampup_30to100 | ACIQ (controller) | 10 | 0.998 +/- 0.002 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_up_20to60 | B0 (default router, pfifo) | 10 | 0.837 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20 |
| s7_up_20to60 | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.820 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19; call via unknown=19; bulk via unknown=19; call via unknown=19; bulk via unknown=19; call via unknown=19 |
| s7_up_20to60 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 0.999 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20 |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.683 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.99; call via unknown=9.99; bulk via unknown=9.99; call via unknown=9.99; bulk via unknown=9.98; call via unknown=9.98 |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.771 +/- 0.014 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=13.3; call via unknown=13.3; bulk via unknown=15.6; call via unknown=15.6; bulk via unknown=13.3; call via unknown=13.3 |
| s7_up_20to60 | ACIQ (controller) | 10 | 0.968 +/- 0.005 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_up_30to100 | B0 (default router, pfifo) | 10 | 0.934 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=30; call via unknown=30; bulk via unknown=30; call via unknown=30 |
| s7_up_30to100 | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.920 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=28.4; call via unknown=28.4; bulk via unknown=28.5; call via unknown=28.5; bulk via unknown=28.5; call via unknown=28.5 |
| s7_up_30to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 0.953 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=30; call via unknown=30; bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=29.9; call via unknown=29.9 |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.764 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15 |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.836 +/- 0.038 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=13.3; call via unknown=13.3; bulk via unknown=13.3; call via unknown=13.3; bulk via unknown=13.8; call via unknown=13.8 |
| s7_up_30to100 | ACIQ (controller) | 10 | 0.997 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |

Starvation (TASK 5b, fixed basis): per LABEL, over the class the data says carried the traffic (assigned class, or the router's `unknown`/legacy aggregate when the label's traffic rode there -- chosen by highest mean, and the carrying class is named). A label starved in tick t if its per-tick goodput fell below 20% of its REGIME median -- in a drop scenario the median is the POST-DROP regime's own median, so the shaped link rate can never masquerade as starvation; without a drop it is the whole window's. The cell lists the starved timestamps counted over seeds. With no series at all the cell prints NOT AVAILABLE, never an empty claim.

| scenario | arm | starved ticks per label (via carrying class) |
| --- | --- | --- |
| s1_iso_during_call | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s1_iso_during_call | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s1_iso_during_call | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s1_iso_during_call | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s1_iso_during_call | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 134 ticks over 10 seed(s), first t=5.3 |
| s2_wan_drop | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2_wan_drop | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2_wan_drop | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2_wan_drop | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2_wan_drop | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 171 ticks over 10 seed(s), first t=5.3 |
| s2b_ramp_100to30 | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_ramp_100to30 | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_ramp_100to30 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 2 ticks over 2 seed(s), first t=56.8; call via unknown: 2 ticks over 2 seed(s), first t=56.8 |
| s2b_ramp_100to30 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 308 ticks over 10 seed(s), first t=5.3 |
| s2b_step_10 | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_10 | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_10 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 10 ticks over 6 seed(s), first t=34.2; call via unknown: 10 ticks over 6 seed(s), first t=34.2 |
| s2b_step_10 | ACIQ (controller) | bulk via bulk_download: 26 ticks over 10 seed(s), first t=2.1; call via unknown: 48 ticks over 10 seed(s), first t=5.4 |
| s2b_step_50 | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 207 ticks over 10 seed(s), first t=5.3 |
| s2b_step_up_20to100 | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 295 ticks over 10 seed(s), first t=5.3 |
| s3_stress | B0 (default router, pfifo) | no starving tick in 50 seed x label series (regime-aware threshold, declared window) |
| s3_stress | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 50 seed x label series (regime-aware threshold, declared window) |
| s3_stress | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | no starving tick in 50 seed x label series (regime-aware threshold, declared window) |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 50 seed x label series (regime-aware threshold, declared window) |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 50 seed x label series (regime-aware threshold, declared window) |
| s3_stress | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; game via unknown: 93 ticks over 10 seed(s), first t=20.3; tv1 via adaptive_video_streaming: 8 ticks over 1 seed(s), first t=2.1; tv1 via unknown: 80 ticks over 9 seed(s), first t=20.3; tv2 via adaptive_video_streaming: 8 ticks over 1 seed(s), first t=2.1; tv2 via unknown: 80 ticks over 9 seed(s), first t=20.3; tv3 via adaptive_video_streaming: 8 ticks over 1 seed(s), first t=2.1; tv3 via unknown: 80 ticks over 9 seed(s), first t=20.3 |
| s3_tv_and_gaming | B0 (default router, pfifo) | no starving tick in 40 seed x label series (regime-aware threshold, declared window) |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 40 seed x label series (regime-aware threshold, declared window) |
| s3_tv_and_gaming | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | no starving tick in 40 seed x label series (regime-aware threshold, declared window) |
| s3_tv_and_gaming | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 40 seed x label series (regime-aware threshold, declared window) |
| s3_tv_and_gaming | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 40 seed x label series (regime-aware threshold, declared window) |
| s3_tv_and_gaming | ACIQ (controller) | game via unknown: 93 ticks over 10 seed(s), first t=20.0; tv1 via unknown: 93 ticks over 10 seed(s), first t=20.0; tv2 via unknown: 93 ticks over 10 seed(s), first t=20.0; tv3 via unknown: 93 ticks over 10 seed(s), first t=20.0 |
| s4_capacity_recovery | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s4_capacity_recovery | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s4_capacity_recovery | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s4_capacity_recovery | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 13 ticks over 7 seed(s), first t=35.9; call via unknown: 13 ticks over 7 seed(s), first t=35.9 |
| s4_capacity_recovery | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 309 ticks over 10 seed(s), first t=5.3 |
| s7_down_100to15 | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to15 | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to15 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 11 ticks over 8 seed(s), first t=21.6; call via unknown: 11 ticks over 8 seed(s), first t=21.6 |
| s7_down_100to15 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 203 ticks over 10 seed(s), first t=5.3 |
| s7_down_100to8 | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to8 | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to8 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 8 ticks over 7 seed(s), first t=30.9; call via unknown: 8 ticks over 7 seed(s), first t=30.9 |
| s7_down_100to8 | ACIQ (controller) | bulk via bulk_download: 35 ticks over 10 seed(s), first t=2.1; call via unknown: 55 ticks over 10 seed(s), first t=5.3 |
| s7_rampup_30to100 | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_rampup_30to100 | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_rampup_30to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_rampup_30to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 306 ticks over 10 seed(s), first t=5.4 |
| s7_up_20to60 | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_20to60 | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_20to60 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_20to60 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 287 ticks over 10 seed(s), first t=5.3 |
| s7_up_30to100 | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_30to100 | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_30to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_30to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 303 ticks over 10 seed(s), first t=5.3 |

Warm-up exclusion (declared): every per-tick window above starts at t >= 2.0 s. The diagnosis round (fix 17's diagnosis.md) shows the first ~2 s of per-tick counter rates are a transmit/counter ramp artefact, not traffic behaviour; dropping those ticks removes nothing else. The window boundary is a declared constant in this generator, not a per-run choice.

Further declared exclusions (TASK 5b): (1) ticks at or beyond the label generator's own measured lifetime (`elapsed_s`, capped by the scenario duration) -- a verdict about a label after its traffic stopped describes nothing about the label; (2) ticks whose link counters went BACKWARDS -- a qdisc del/re-add resets every counter on the device, so that tick's per-class goodput is a reset artefact, not a delivery gap. Stars and minima are computed over what remains; nothing is excluded silently.

## Step/demand generalization band (evaluation-only; docs/evidence/s2b-params.md + docs/evidence/round3-params.md, declared BEFORE these runs)

The shipped controller runs unchanged on capacity changes it was never tuned on: two down-step magnitudes, a 5x up-step, and a continuous 20 s ramp -- plus the round-3 DEV shapes (s7_* up/down steps and ramps, s3_stress) and the two queue-discipline-only arms (CAKE-conservative / CAKE-adaptive). Seeds 800-809 configured per scenario (the DEV band, seed names in each run dir). CAKE-static is applied once at launch and never re-applied: that is its declared semantics, and this band exists to surface the consequences. Definitions: bind = first tick at which the applied tree sits within 10% of the link's truth and stays there (down-moves only; up-moves print `n/a (up-step)` and are judged by the utilization column: applied/truth and receiver delivered/truth over the final third); tracking error = mean |applied - truth| over the ramp window; estimate error = same over the final third. Where ACIQ fails, the row says so.

Engine commit at generation time: `7c6c7235780a` — a run whose result carries a different commit_hash is SUPERSEDED, listed under 'commit provenance' below and never pooled into a numeric cell with a newer commit.

### s2b_step_50

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 50.00 +/- 0.00 | 496.42 +/- 0.09 | 47.61 +/- 0.20 | - | honesty row declared for ACIQ only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 45.00 +/- 0.00 | 134.70 +/- 1.76 | 47.62 +/- 0.20 | - | honesty row declared for ACIQ only |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 10.1 +/- 0.0 | 2.50 +/- 0.00 | 1.81 +/- 0.02 | 44.71 +/- 0.54 | - | honesty row declared for ACIQ only |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 50.00 +/- 0.00 | 169.28 +/- 2.67 | 47.63 +/- 0.19 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 50.00 +/- 0.00 | 12.27 +/- 3.98 | 17.40 +/- 2.30 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 12.7 +/- 0.3 | 10.09 +/- 3.70 | 13.62 +/- 2.48 | 28.69 +/- 2.29 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 42.9 vs truth 50.0, 14% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 50.0, 72% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 45.9 vs truth 50.0, 8% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 38.6 vs truth 50.0, 23% off truth, confidence 0.05; final tick: UNSATURATED (estimator not saturated at the end regime), applied 44.6 vs truth 50.0, 11% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 31.6 vs truth 50.0, 37% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 40.3 vs truth 50.0, 19% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 35.1 vs truth 50.0, 30% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 28.0 vs truth 50.0, 44% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 46.0 vs truth 50.0, 8% off truth, confidence 0.05 |

### s2b_step_10

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 90.00 +/- 0.00 | 246.44 +/- 0.41 | 9.46 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 85.00 +/- 0.00 | 82.94 +/- 0.62 | 9.46 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 10.1 +/- 0.0 | 0.50 +/- 0.00 | 5.13 +/- 0.04 | 8.88 +/- 0.09 | - | honesty row declared for ACIQ only |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 90.00 +/- 0.00 | 82.52 +/- 0.54 | 9.44 +/- 0.04 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 90.00 +/- 0.00 | 74.43 +/- 1.88 | 9.09 +/- 0.28 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 4.00 +/- 0.00 | 80.84 +/- 1.14 | 7.03 +/- 0.33 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 10.0, 40% off truth, confidence 0.25 (n=9); final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 10.0, 40% off truth, confidence 0.05 |

### s2b_step_up_20to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | n/a (up-step) | 80.00 +/- 0.00 | 584.50 +/- 0.94 | 19.02 +/- 0.00 | appl 0.20 +/- 0.00 / delv 0.19 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | n/a (up-step) | 81.00 +/- 0.00 | 2.33 +/- 0.03 | 18.02 +/- 0.06 | appl 0.19 +/- 0.00 / delv 0.18 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | n/a (up-step) | 5.00 +/- 0.00 | 85.63 +/- 1.73 | 90.47 +/- 0.33 | appl 0.95 +/- 0.00 / delv 0.91 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 80.00 +/- 0.00 | 1.87 +/- 0.03 | 9.43 +/- 0.03 | appl 0.20 +/- 0.00 / delv 0.10 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 80.00 +/- 0.00 | 1.85 +/- 0.04 | 13.61 +/- 1.16 | appl 0.20 +/- 0.00 / delv 0.14 +/- 0.01 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 14.44 +/- 3.37 | 2.05 +/- 0.18 | 64.78 +/- 0.70 | appl 0.96 +/- 0.04 / delv 0.65 +/- 0.01 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 86.7 vs truth 100.0, 13% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 138.5 vs truth 100.0, 38% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 136.0 vs truth 100.0, 36% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 86.4 vs truth 100.0, 14% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 86.4 vs truth 100.0, 14% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 86.4 vs truth 100.0, 14% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 87.4 vs truth 100.0, 13% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 86.5 vs truth 100.0, 14% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 94.6 vs truth 100.0, 5% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 86.1 vs truth 100.0, 14% off truth, confidence 0.25 |

### s2b_ramp_100to30

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 822.36 +/- 0.16 | 28.57 +/- 0.01 | - | honesty row declared for ACIQ only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 65.00 +/- 0.00 | 132.54 +/- 1.35 | 28.58 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 30.4 +/- 0.0 | 1.50 +/- 0.00 | 2.29 +/- 0.02 | 26.90 +/- 0.27 | - | honesty row declared for ACIQ only |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 111.29 +/- 3.32 | 28.54 +/- 0.07 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 15.61 +/- 5.24 | 14.27 +/- 1.18 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 33.6 +/- 4.1 | 3.89 +/- 1.25 | 24.69 +/- 1.30 | 18.89 +/- 0.80 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 27.0 vs truth 30.0, 10% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 24.1 vs truth 30.0, 20% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 25.0 vs truth 30.0, 17% off truth, confidence 0.00 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 27.2 vs truth 30.0, 9% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 28.2 vs truth 30.0, 6% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 21.5 vs truth 30.0, 28% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 27.6 vs truth 30.0, 8% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 22.1 vs truth 30.0, 26% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 28.3 vs truth 30.0, 6% off truth, confidence 0.00 |

### s7_up_20to60

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | n/a (up-step) | 40.00 +/- 0.00 | 584.32 +/- 0.50 | 19.02 +/- 0.00 | appl 0.33 +/- 0.00 / delv 0.32 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | n/a (up-step) | 41.00 +/- 0.00 | 2.29 +/- 0.03 | 17.91 +/- 0.18 | appl 0.32 +/- 0.00 / delv 0.30 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | n/a (up-step) | 3.00 +/- 0.00 | 86.80 +/- 1.40 | 53.83 +/- 0.59 | appl 0.95 +/- 0.00 / delv 0.90 +/- 0.01 | honesty row declared for ACIQ only |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 40.00 +/- 0.00 | 1.80 +/- 0.05 | 9.37 +/- 0.09 | appl 0.33 +/- 0.00 / delv 0.16 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 40.00 +/- 0.00 | 1.84 +/- 0.04 | 14.34 +/- 1.27 | appl 0.33 +/- 0.00 / delv 0.24 +/- 0.02 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 6.82 +/- 1.63 | 8.71 +/- 2.55 | 41.57 +/- 1.51 | appl 1.00 +/- 0.04 / delv 0.69 +/- 0.03 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 53.8 vs truth 60.0, 10% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 53.9 vs truth 60.0, 10% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 86.3 vs truth 60.0, 44% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 54.3 vs truth 60.0, 9% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 65.6 vs truth 60.0, 9% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 54.3 vs truth 60.0, 10% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 54.1 vs truth 60.0, 10% off truth, confidence 0.25 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 54.2 vs truth 60.0, 10% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 51.6 vs truth 60.0, 14% off truth, confidence 0.25 |

### s7_up_30to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | n/a (up-step) | 70.00 +/- 0.00 | 391.19 +/- 0.34 | 28.58 +/- 0.00 | appl 0.30 +/- 0.00 / delv 0.29 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | n/a (up-step) | 71.50 +/- 0.00 | 1.99 +/- 0.02 | 27.01 +/- 0.15 | appl 0.28 +/- 0.00 / delv 0.27 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | n/a (up-step) | 5.00 +/- 0.00 | 94.79 +/- 6.13 | 90.50 +/- 0.32 | appl 0.95 +/- 0.00 / delv 0.91 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 70.00 +/- 0.00 | 1.28 +/- 0.02 | 14.16 +/- 0.08 | appl 0.30 +/- 0.00 / delv 0.14 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 70.00 +/- 0.00 | 1.59 +/- 0.04 | 19.75 +/- 4.30 | appl 0.30 +/- 0.00 / delv 0.20 +/- 0.04 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 11.92 +/- 4.65 | 9.20 +/- 5.14 | 70.02 +/- 3.89 | appl 1.04 +/- 0.03 / delv 0.70 +/- 0.04 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 93.4 vs truth 100.0, 7% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 145.5 vs truth 100.0, 45% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 145.2 vs truth 100.0, 45% off truth, confidence 0.25 (n=3); final tick: UNSATURATED (estimator not saturated at the end regime), applied 102.4 vs truth 100.0, 2% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 115.8 vs truth 100.0, 16% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 102.4 vs truth 100.0, 2% off truth, confidence 0.20; final tick: UNSATURATED (estimator not saturated at the end regime), applied 102.3 vs truth 100.0, 2% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 102.2 vs truth 100.0, 2% off truth, confidence 0.25 |

### s7_rampup_30to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 383.70 +/- 3.71 | 28.56 +/- 0.04 | - | honesty row declared for ACIQ only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 71.50 +/- 0.00 | 1.99 +/- 0.05 | 26.83 +/- 0.26 | - | honesty row declared for ACIQ only |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 30.4 +/- 0.0 | 5.00 +/- 0.00 | 187.62 +/- 6.37 | 90.22 +/- 0.72 | - | honesty row declared for ACIQ only |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 1.41 +/- 0.03 | 14.08 +/- 0.14 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 1.79 +/- 0.09 | 21.75 +/- 3.49 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 50.6 +/- 5.4 | 10.73 +/- 3.41 | 9.06 +/- 5.32 | 66.70 +/- 2.64 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 104.9 vs truth 100.0, 5% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 70.8 vs truth 100.0, 29% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 104.5 vs truth 100.0, 5% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 119.6 vs truth 100.0, 20% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 103.3 vs truth 100.0, 3% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 102.2 vs truth 100.0, 2% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 78.6 vs truth 100.0, 21% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 102.2 vs truth 100.0, 2% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 92.9 vs truth 100.0, 7% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 145.1 vs truth 100.0, 45% off truth, confidence 0.25 |

### s7_down_100to15

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 85.00 +/- 0.00 | 246.15 +/- 0.17 | 14.23 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 80.00 +/- 0.00 | 86.10 +/- 0.53 | 14.23 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 10.1 +/- 0.0 | 0.75 +/- 0.00 | 3.62 +/- 0.03 | 13.50 +/- 0.05 | - | honesty row declared for ACIQ only |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 85.00 +/- 0.00 | 87.04 +/- 0.58 | 14.23 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 85.00 +/- 0.00 | 26.60 +/- 3.97 | 12.32 +/- 0.17 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 14.3 +/- 1.6 | 0.96 +/- 0.10 | 44.50 +/- 5.55 | 10.38 +/- 0.20 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 15.0, 7% off truth, confidence 0.55 (n=6); final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 15.0, 7% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 15.0, 7% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.4 vs truth 15.0, 4% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 15.0, 7% off truth, confidence 0.40 |

### s7_down_100to8

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 92.00 +/- 0.00 | 246.58 +/- 0.16 | 7.54 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 87.00 +/- 0.00 | 81.09 +/- 1.35 | 7.54 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | 10.1 +/- 0.0 | 0.40 +/- 0.00 | 6.23 +/- 0.05 | 7.12 +/- 0.05 | - | honesty row declared for ACIQ only |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 92.00 +/- 0.00 | 78.39 +/- 0.68 | 7.54 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 92.00 +/- 0.00 | 76.03 +/- 1.10 | 7.45 +/- 0.08 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 6.00 +/- 0.00 | 81.07 +/- 0.91 | 6.34 +/- 0.17 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 8.0, 75% off truth, confidence 0.40 (n=9); final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 8.0, 75% off truth, confidence 0.35 |

### s3_stress

| arm | n | call p95 whole-run (ms) | game p95 whole-run (ms) | bulk receiver mean inst (Mbps) | tv1 / tv2 / tv3 receiver mean inst (Mbps) | overload note (loaded vs capacity) |
| --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE | 321.45 +/- 1.49 | 75.90 +/- 0.77 | 4.51 / 4.51 / 4.51; 4.51 / 4.51 / 4.51; 4.41 / 4.41 / 4.41; 4.51 / 4.51 / 4.51; 4.51 / 4.51 / 4.51; 4.41 / 4.41 / 4.41; 4.41 / 4.41 / 4.41; 4.41 / 4.41 / 4.41; 4.51 / 4.51 / 4.51; 4.62 / 4.62 / 4.62 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE | 3.70 +/- 0.43 | 71.02 +/- 0.71 | 4.51 / 4.51 / 4.51; 4.51 / 4.51 / 4.51; 4.40 / 4.40 / 4.40; 4.41 / 4.51 / 4.51; 4.51 / 4.51 / 4.51; 4.40 / 4.40 / 4.41; 4.41 / 4.41 / 4.41; 4.40 / 4.41 / 4.41; 4.50 / 4.51 / 4.51; 4.61 / 4.61 / 4.61 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |
| CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | NOT AVAILABLE | 3.44 +/- 0.40 | 71.01 +/- 0.71 | 4.51 / 4.51 / 4.51; 4.51 / 4.51 / 4.51; 4.40 / 4.41 / 4.41; 4.40 / 4.51 / 4.41; 4.51 / 4.51 / 4.51; 4.41 / 4.40 / 4.41; 4.41 / 4.41 / 4.41; 4.40 / 4.41 / 4.41; 4.51 / 4.51 / 4.51; 4.62 / 4.62 / 4.62 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE | 1.94 +/- 0.17 | 31.16 +/- 0.28 | 4.50 / 4.50 / 4.50; 4.51 / 4.50 / 4.51; 4.40 / 4.40 / 4.40; 4.50 / 4.40 / 4.50; 4.51 / 4.50 / 4.51; 4.40 / 4.40 / 4.40; 4.40 / 4.40 / 4.40; 4.40 / 4.40 / 4.40; 4.50 / 4.51 / 4.51; 4.62 / 4.61 / 4.61 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE | 4.18 +/- 2.98 | 48.56 +/- 7.44 | 4.41 / 4.41 / 4.38; 4.40 / 4.41 / 4.40; 4.41 / 4.41 / 4.41; 4.41 / 4.41 / 4.41; 4.41 / 4.41 / 4.41; 4.25 / 4.25 / 4.22; 4.40 / 4.40 / 4.40; 4.31 / 4.31 / 4.31; 4.21 / 4.19 / 4.14; 4.50 / 4.50 / 4.46 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |
| ACIQ (controller) | 10 | NOT AVAILABLE | 18.88 +/- 2.16 | 61.40 +/- 1.80 | 4.21 / 4.21 / 4.21; 4.31 / 4.31 / 4.31; 4.21 / 4.21 / 4.22; 4.21 / 4.21 / 4.22; 4.30 / 4.31 / 4.31; 4.21 / 4.22 / 4.22; 4.21 / 4.21 / 4.21; 4.21 / 4.21 / 4.12; 4.31 / 4.31 / 4.31; 4.41 / 4.41 / 4.41 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |

## Starvation, receiver side (every arm, per-second sink logs)

| scenario | arm | label; starved inst ticks over seeds (longest streak) |
| --- | --- | --- |
| s1_iso_during_call | B0 (default router, pfifo) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 8 tick(s) over 10 seed(s), longest streak 1 s |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | bulk: 2 tick(s) over 10 seed(s), longest streak 1 s; call: 8 tick(s) over 10 seed(s), longest streak 1 s |
| s1_iso_during_call | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | bulk: 2 tick(s) over 10 seed(s), longest streak 1 s; call: 8 tick(s) over 10 seed(s), longest streak 1 s |
| s1_iso_during_call | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 2 tick(s) over 10 seed(s), longest streak 1 s; call: 8 tick(s) over 10 seed(s), longest streak 1 s |
| s1_iso_during_call | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 5 tick(s) over 10 seed(s), longest streak 1 s; call: 12 tick(s) over 10 seed(s), longest streak 2 s |
| s1_iso_during_call | ACIQ (controller) | bulk: 18 tick(s) over 10 seed(s), longest streak 2 s; call: 25 tick(s) over 10 seed(s), longest streak 3 s |
| s2_wan_drop | B0 (default router, pfifo) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 22 tick(s) over 10 seed(s), longest streak 2 s |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | bulk: 1 tick(s) over 10 seed(s), longest streak 1 s; call: 10 tick(s) over 10 seed(s), longest streak 2 s |
| s2_wan_drop | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | bulk: 3 tick(s) over 10 seed(s), longest streak 1 s; call: 11 tick(s) over 10 seed(s), longest streak 2 s |
| s2_wan_drop | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 10 tick(s) over 10 seed(s), longest streak 2 s |
| s2_wan_drop | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 7 tick(s) over 10 seed(s), longest streak 1 s; call: 18 tick(s) over 10 seed(s), longest streak 2 s |
| s2_wan_drop | ACIQ (controller) | bulk: 21 tick(s) over 10 seed(s), longest streak 3 s; call: 31 tick(s) over 10 seed(s), longest streak 4 s |
| s2b_ramp_100to30 | B0 (default router, pfifo) | bulk: 1 tick(s) over 10 seed(s), longest streak 1 s; call: 7 tick(s) over 10 seed(s), longest streak 1 s |
| s2b_ramp_100to30 | CAKE-static (95% of pre-drop link, set and forget) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 14 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_ramp_100to30 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | bulk: 5 tick(s) over 10 seed(s), longest streak 1 s; call: 14 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 14 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 13 tick(s) over 10 seed(s), longest streak 2 s; call: 25 tick(s) over 10 seed(s), longest streak 3 s |
| s2b_ramp_100to30 | ACIQ (controller) | bulk: 32 tick(s) over 10 seed(s), longest streak 4 s; call: 44 tick(s) over 10 seed(s), longest streak 5 s |
| s2b_step_10 | B0 (default router, pfifo) | bulk: 1 tick(s) over 10 seed(s), longest streak 1 s; call: 56 tick(s) over 10 seed(s), longest streak 6 s |
| s2b_step_10 | CAKE-static (95% of pre-drop link, set and forget) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 7 tick(s) over 10 seed(s), longest streak 1 s |
| s2b_step_10 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | bulk: 3 tick(s) over 10 seed(s), longest streak 1 s; call: 9 tick(s) over 10 seed(s), longest streak 1 s |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 2 tick(s) over 10 seed(s), longest streak 1 s; call: 7 tick(s) over 10 seed(s), longest streak 1 s |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 13 tick(s) over 10 seed(s), longest streak 2 s; call: 22 tick(s) over 10 seed(s), longest streak 3 s |
| s2b_step_10 | ACIQ (controller) | bulk: 44 tick(s) over 10 seed(s), longest streak 5 s; call: 54 tick(s) over 10 seed(s), longest streak 6 s |
| s2b_step_50 | B0 (default router, pfifo) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 7 tick(s) over 10 seed(s), longest streak 1 s |
| s2b_step_50 | CAKE-static (95% of pre-drop link, set and forget) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 8 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_50 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | bulk: 6 tick(s) over 10 seed(s), longest streak 1 s; call: 11 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 7 tick(s) over 10 seed(s), longest streak 1 s |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 9 tick(s) over 10 seed(s), longest streak 1 s; call: 16 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_50 | ACIQ (controller) | bulk: 24 tick(s) over 10 seed(s), longest streak 3 s; call: 30 tick(s) over 10 seed(s), longest streak 4 s |
| s2b_step_up_20to100 | B0 (default router, pfifo) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 8 tick(s) over 10 seed(s), longest streak 1 s |
| s2b_step_up_20to100 | CAKE-static (95% of pre-drop link, set and forget) | bulk: 5 tick(s) over 10 seed(s), longest streak 1 s; call: 11 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_up_20to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | bulk: 7 tick(s) over 10 seed(s), longest streak 1 s; call: 12 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 5 tick(s) over 10 seed(s), longest streak 1 s; call: 11 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 12 tick(s) over 10 seed(s), longest streak 2 s; call: 18 tick(s) over 10 seed(s), longest streak 3 s |
| s2b_step_up_20to100 | ACIQ (controller) | bulk: 33 tick(s) over 10 seed(s), longest streak 4 s; call: 41 tick(s) over 10 seed(s), longest streak 5 s |
| s3_stress | B0 (default router, pfifo) | bulk: 5 tick(s) over 10 seed(s), longest streak 1 s; game: 22 tick(s) over 10 seed(s), longest streak 3 s; tv1: 17 tick(s) over 10 seed(s), longest streak 3 s; tv2: 13 tick(s) over 10 seed(s), longest streak 2 s; tv3: 11 tick(s) over 10 seed(s), longest streak 2 s |
| s3_stress | CAKE-static (95% of pre-drop link, set and forget) | bulk: 9 tick(s) over 10 seed(s), longest streak 1 s; game: 25 tick(s) over 10 seed(s), longest streak 3 s; tv1: 23 tick(s) over 10 seed(s), longest streak 3 s; tv2: 13 tick(s) over 10 seed(s), longest streak 2 s; tv3: 12 tick(s) over 10 seed(s), longest streak 2 s |
| s3_stress | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | bulk: 9 tick(s) over 10 seed(s), longest streak 1 s; game: 25 tick(s) over 10 seed(s), longest streak 3 s; tv1: 22 tick(s) over 10 seed(s), longest streak 3 s; tv2: 13 tick(s) over 10 seed(s), longest streak 2 s; tv3: 13 tick(s) over 10 seed(s), longest streak 2 s |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 9 tick(s) over 10 seed(s), longest streak 1 s; game: 24 tick(s) over 10 seed(s), longest streak 3 s; tv1: 22 tick(s) over 10 seed(s), longest streak 3 s; tv2: 14 tick(s) over 10 seed(s), longest streak 2 s; tv3: 11 tick(s) over 10 seed(s), longest streak 2 s |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 22 tick(s) over 10 seed(s), longest streak 9 s; game: 32 tick(s) over 10 seed(s), longest streak 4 s; tv1: 29 tick(s) over 10 seed(s), longest streak 3 s; tv2: 21 tick(s) over 10 seed(s), longest streak 3 s; tv3: 20 tick(s) over 10 seed(s), longest streak 2 s |
| s3_stress | ACIQ (controller) | bulk: 29 tick(s) over 10 seed(s), longest streak 3 s; game: 47 tick(s) over 10 seed(s), longest streak 6 s; tv1: 42 tick(s) over 10 seed(s), longest streak 5 s; tv2: 35 tick(s) over 10 seed(s), longest streak 4 s; tv3: 34 tick(s) over 10 seed(s), longest streak 4 s |
| s3_tv_and_gaming | B0 (default router, pfifo) | game: 18 tick(s) over 10 seed(s), longest streak 3 s; tv1: 12 tick(s) over 10 seed(s), longest streak 2 s; tv2: 11 tick(s) over 10 seed(s), longest streak 2 s; tv3: 4 tick(s) over 10 seed(s), longest streak 1 s |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | game: 18 tick(s) over 10 seed(s), longest streak 3 s; tv1: 12 tick(s) over 10 seed(s), longest streak 2 s; tv2: 10 tick(s) over 10 seed(s), longest streak 1 s; tv3: 5 tick(s) over 10 seed(s), longest streak 1 s |
| s3_tv_and_gaming | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | game: 18 tick(s) over 10 seed(s), longest streak 3 s; tv1: 12 tick(s) over 10 seed(s), longest streak 2 s; tv2: 10 tick(s) over 10 seed(s), longest streak 1 s; tv3: 5 tick(s) over 10 seed(s), longest streak 1 s |
| s3_tv_and_gaming | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | game: 18 tick(s) over 10 seed(s), longest streak 3 s; tv1: 13 tick(s) over 10 seed(s), longest streak 2 s; tv2: 11 tick(s) over 10 seed(s), longest streak 2 s; tv3: 6 tick(s) over 10 seed(s), longest streak 1 s |
| s3_tv_and_gaming | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | game: 26 tick(s) over 10 seed(s), longest streak 3 s; tv1: 20 tick(s) over 10 seed(s), longest streak 3 s; tv2: 18 tick(s) over 10 seed(s), longest streak 2 s; tv3: 13 tick(s) over 10 seed(s), longest streak 2 s |
| s3_tv_and_gaming | ACIQ (controller) | game: 40 tick(s) over 10 seed(s), longest streak 5 s; tv1: 33 tick(s) over 10 seed(s), longest streak 4 s; tv2: 31 tick(s) over 10 seed(s), longest streak 4 s; tv3: 25 tick(s) over 10 seed(s), longest streak 3 s |
| s4_capacity_recovery | B0 (default router, pfifo) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 32 tick(s) over 10 seed(s), longest streak 2 s |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 11 tick(s) over 10 seed(s), longest streak 2 s |
| s4_capacity_recovery | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | bulk: 4 tick(s) over 10 seed(s), longest streak 1 s; call: 13 tick(s) over 10 seed(s), longest streak 2 s |
| s4_capacity_recovery | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 11 tick(s) over 10 seed(s), longest streak 2 s |
| s4_capacity_recovery | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 8 tick(s) over 10 seed(s), longest streak 1 s; call: 23 tick(s) over 10 seed(s), longest streak 3 s |
| s4_capacity_recovery | ACIQ (controller) | bulk: 30 tick(s) over 10 seed(s), longest streak 3 s; call: 43 tick(s) over 10 seed(s), longest streak 5 s |
| s7_down_100to15 | B0 (default router, pfifo) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 41 tick(s) over 10 seed(s), longest streak 4 s |
| s7_down_100to15 | CAKE-static (95% of pre-drop link, set and forget) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 9 tick(s) over 10 seed(s), longest streak 1 s |
| s7_down_100to15 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | bulk: 3 tick(s) over 10 seed(s), longest streak 1 s; call: 12 tick(s) over 10 seed(s), longest streak 2 s |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 9 tick(s) over 10 seed(s), longest streak 1 s |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 7 tick(s) over 10 seed(s), longest streak 1 s; call: 19 tick(s) over 10 seed(s), longest streak 3 s |
| s7_down_100to15 | ACIQ (controller) | bulk: 19 tick(s) over 10 seed(s), longest streak 2 s; call: 31 tick(s) over 10 seed(s), longest streak 4 s |
| s7_down_100to8 | B0 (default router, pfifo) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 79 tick(s) over 10 seed(s), longest streak 7 s |
| s7_down_100to8 | CAKE-static (95% of pre-drop link, set and forget) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 10 tick(s) over 10 seed(s), longest streak 1 s |
| s7_down_100to8 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | bulk: 4 tick(s) over 10 seed(s), longest streak 1 s; call: 12 tick(s) over 10 seed(s), longest streak 2 s |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 10 tick(s) over 10 seed(s), longest streak 1 s |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 7 tick(s) over 10 seed(s), longest streak 1 s; call: 20 tick(s) over 10 seed(s), longest streak 2 s |
| s7_down_100to8 | ACIQ (controller) | bulk: 33 tick(s) over 10 seed(s), longest streak 4 s; call: 46 tick(s) over 10 seed(s), longest streak 5 s |
| s7_rampup_30to100 | B0 (default router, pfifo) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 10 tick(s) over 10 seed(s), longest streak 2 s |
| s7_rampup_30to100 | CAKE-static (95% of pre-drop link, set and forget) | bulk: 9 tick(s) over 10 seed(s), longest streak 1 s; call: 19 tick(s) over 10 seed(s), longest streak 2 s |
| s7_rampup_30to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | bulk: 7 tick(s) over 10 seed(s), longest streak 1 s; call: 17 tick(s) over 10 seed(s), longest streak 2 s |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 9 tick(s) over 10 seed(s), longest streak 1 s; call: 17 tick(s) over 10 seed(s), longest streak 2 s |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 19 tick(s) over 10 seed(s), longest streak 3 s; call: 26 tick(s) over 10 seed(s), longest streak 4 s |
| s7_rampup_30to100 | ACIQ (controller) | bulk: 47 tick(s) over 10 seed(s), longest streak 6 s; call: 56 tick(s) over 10 seed(s), longest streak 7 s |
| s7_up_20to60 | B0 (default router, pfifo) | bulk: 1 tick(s) over 10 seed(s), longest streak 1 s; call: 8 tick(s) over 10 seed(s), longest streak 1 s |
| s7_up_20to60 | CAKE-static (95% of pre-drop link, set and forget) | bulk: 7 tick(s) over 10 seed(s), longest streak 1 s; call: 13 tick(s) over 10 seed(s), longest streak 2 s |
| s7_up_20to60 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | bulk: 7 tick(s) over 10 seed(s), longest streak 1 s; call: 15 tick(s) over 10 seed(s), longest streak 3 s |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 7 tick(s) over 10 seed(s), longest streak 1 s; call: 13 tick(s) over 10 seed(s), longest streak 2 s |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 11 tick(s) over 10 seed(s), longest streak 2 s; call: 18 tick(s) over 10 seed(s), longest streak 3 s |
| s7_up_20to60 | ACIQ (controller) | bulk: 35 tick(s) over 10 seed(s), longest streak 4 s; call: 43 tick(s) over 10 seed(s), longest streak 5 s |
| s7_up_30to100 | B0 (default router, pfifo) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 9 tick(s) over 10 seed(s), longest streak 1 s |
| s7_up_30to100 | CAKE-static (95% of pre-drop link, set and forget) | bulk: 7 tick(s) over 10 seed(s), longest streak 1 s; call: 13 tick(s) over 10 seed(s), longest streak 2 s |
| s7_up_30to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | bulk: 5 tick(s) over 10 seed(s), longest streak 1 s; call: 13 tick(s) over 10 seed(s), longest streak 2 s |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 5 tick(s) over 10 seed(s), longest streak 1 s; call: 11 tick(s) over 10 seed(s), longest streak 2 s |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 12 tick(s) over 10 seed(s), longest streak 2 s; call: 19 tick(s) over 10 seed(s), longest streak 3 s |
| s7_up_30to100 | ACIQ (controller) | bulk: 36 tick(s) over 10 seed(s), longest streak 4 s; call: 43 tick(s) over 10 seed(s), longest streak 5 s |


## Commit provenance (declared; every run's engine hash)

| scenario | arm | n runs | commit_hash | verdict |
| --- | --- | --- | --- | --- |
| s1_iso_during_call | ACIQ (controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s1_iso_during_call | B0 (default router, pfifo) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s1_iso_during_call | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s1_iso_during_call | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s1_iso_during_call | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2_wan_drop | ACIQ (controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2_wan_drop | B0 (default router, pfifo) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2_wan_drop | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2_wan_drop | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2_wan_drop | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_ramp_100to30 | ACIQ (controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_ramp_100to30 | B0 (default router, pfifo) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_ramp_100to30 | CAKE-static (95% of pre-drop link, set and forget) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_ramp_100to30 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_10 | ACIQ (controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_10 | B0 (default router, pfifo) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_10 | CAKE-static (95% of pre-drop link, set and forget) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_10 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_50 | ACIQ (controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_50 | B0 (default router, pfifo) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_50 | CAKE-static (95% of pre-drop link, set and forget) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_50 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | ACIQ (controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | B0 (default router, pfifo) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | CAKE-static (95% of pre-drop link, set and forget) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s3_stress | ACIQ (controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s3_stress | B0 (default router, pfifo) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s3_stress | CAKE-static (95% of pre-drop link, set and forget) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s3_stress | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s3_tv_and_gaming | ACIQ (controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s3_tv_and_gaming | B0 (default router, pfifo) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s3_tv_and_gaming | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s3_tv_and_gaming | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s3_tv_and_gaming | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s4_capacity_recovery | ACIQ (controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s4_capacity_recovery | B0 (default router, pfifo) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s4_capacity_recovery | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s4_capacity_recovery | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s4_capacity_recovery | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_down_100to15 | ACIQ (controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_down_100to15 | B0 (default router, pfifo) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_down_100to15 | CAKE-static (95% of pre-drop link, set and forget) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_down_100to15 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_down_100to8 | ACIQ (controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_down_100to8 | B0 (default router, pfifo) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_down_100to8 | CAKE-static (95% of pre-drop link, set and forget) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_down_100to8 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | ACIQ (controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | B0 (default router, pfifo) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | CAKE-static (95% of pre-drop link, set and forget) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_up_20to60 | ACIQ (controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_up_20to60 | B0 (default router, pfifo) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_up_20to60 | CAKE-static (95% of pre-drop link, set and forget) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_up_20to60 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_up_30to100 | ACIQ (controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_up_30to100 | B0 (default router, pfifo) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_up_30to100 | CAKE-static (95% of pre-drop link, set and forget) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |
| s7_up_30to100 | CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller) | 10 | `7c6c7235780a` | current: trusted for a frozen final band claim |

- pooling rule (binding): a numeric cell in this report may mix runs across seeds of ONE band, but never across commit hashes; the section headers above flag mixed-commit scenarios so a mixed cell is traceable to its provenance lines.

## Classifier (router-vantage corpus, thresholds fixed before held-out)

- HEADLINE (fresh held-out, tuple-split by flow, no threshold tuned on this half): broad-taxonomy accuracy 0.7456140350877193 on n=114 (85 correct, 0 abstained); narrow-taxonomy accuracy 0.5877192982456141 on the same rows (67 correct, 0 abstained). The FULL-corpus figures below are context, not the verdict: the held-out half is the one the classifier never shaped.
- broad_heldout: `{"n": 114, "correct": 85, "abstained": 0, "confident_or_wrong": 29, "accuracy_strict": 0.7456140350877193, "accuracy_excl_abstain": 0.7456140350877193}`
- broad_accept_abstain_heldout: `{"n": 114, "correct": 85, "abstained": 0, "confident_or_wrong": 29, "accuracy_strict": 0.7456140350877193, "accuracy_excl_abstain": 0.7456140350877193}`
- calibration_heldout: `[{"lo": 0.0, "hi": 0.2, "n": 0, "correct": 0, "empirical_accuracy": null, "mean_predicted": null}, {"lo": 0.2, "hi": 0.4, "n": 0, "correct": 0, "empirical_accuracy": null, "mean_predicted": null}, {"lo": 0.4, "hi": 0.6, "n": 31, "correct": 13, "empirical_accuracy": 0.4194, "mean_predicted": 0.55}, {"lo": 0.6, "hi": 0.8, "n": 83, "correct": 54, "empirical_accuracy": 0.6506, "mean_predicted": 0.6235}, {"lo": 0.8, "hi": 1.0, "n": 0, "correct": 0, "empirical_accuracy": null, "mean_predicted": null}]`
- confidently_wrong_heldout: `[]`
- strict: `{"n": 228, "correct": 139, "abstained": 0, "confident_or_wrong": 89, "accuracy_strict": 0.6096491228070176, "accuracy_excl_abstain": 0.6096491228070176}`
- strict_fixed: `{"n": 114, "correct": 72, "abstained": 0, "confident_or_wrong": 42, "accuracy_strict": 0.631578947368421, "accuracy_excl_abstain": 0.631578947368421}`
- strict_heldout: `{"n": 114, "correct": 67, "abstained": 0, "confident_or_wrong": 47, "accuracy_strict": 0.5877192982456141, "accuracy_excl_abstain": 0.5877192982456141}`
- accept_abstain: `{"n": 228, "correct": 139, "abstained": 0, "confident_or_wrong": 89, "accuracy_strict": 0.6096491228070176, "accuracy_excl_abstain": 0.6096491228070176}`
- accept_abstain_heldout: `{"n": 114, "correct": 67, "abstained": 0, "confident_or_wrong": 47, "accuracy_strict": 0.5877192982456141, "accuracy_excl_abstain": 0.5877192982456141}`
- confusion_heldout: `{"classes": ["adaptive_video_streaming", "bulk_download", "cloud_backup", "interactive_gaming", "software_update", "video_call_voice"], "matrix": {"adaptive_video_streaming": {"bulk_download": 0, "cloud_backup": 0, "interactive_gaming": 0, "software_update": 0, "video_call_voice": 0, "adaptive_video_streaming": 26, "?abstain": 0}, "bulk_download": {"adaptive_video_streaming": 4, "cloud_backup": 0, "interactive_gaming": 0, "software_update": 0, "video_call_voice": 0, "bulk_download": 13, "?abstain": 0}, "cloud_backup": {"adaptive_video_streaming": 0, "bulk_download": 0, "interactive_gaming": 0, "software_update": 0, "video_call_voice": 0, "cloud_backup": 15, "?abstain": 0}, "interactive_gaming": {"adaptive_video_streaming": 0, "bulk_download": 0, "cloud_backup": 0, "software_update": 0, "video_call_voice": 18, "interactive_gaming": 0, "?abstain": 0}, "software_update": {"adaptive_video_streaming": 25, "bulk_download": 0, "cloud_backup": 0, "interactive_gaming": 0, "video_call_voice": 0, "software_update": 0, "?abstain": 0}, "video_call_voice": {"adaptive_video_streaming": 0, "bulk_download": 0, "cloud_backup": 0, "interactive_gaming": 0, "software_update": 0, "video_call_voice": 13, "?abstain": 0}}, "per_class": {"adaptive_video_streaming": {"tp": 26, "fp": 29, "fn": 0, "support": 26, "precision": 0.4727272727272727, "recall": 1.0, "f1": 0.6419753086419753}, "bulk_download": {"tp": 13, "fp": 0, "fn": 4, "support": 17, "precision": 1.0, "recall": 0.7647058823529411, "f1": 0.8666666666666666}, "cloud_backup": {"tp": 15, "fp": 0, "fn": 0, "support": 15, "precision": 1.0, "recall": 1.0, "f1": 1.0}, "interactive_gaming": {"tp": 0, "fp": 0, "fn": 18, "support": 18, "precision": null, "recall": 0.0, "f1": null}, "software_update": {"tp": 0, "fp": 0, "fn": 25, "support": 25, "precision": null, "recall": 0.0, "f1": null}, "video_call_voice": {"tp": 13, "fp": 18, "fn": 0, "support": 13, "precision": 0.41935483870967744, "recall": 1.0, "f1": 0.5909090909090909}}}`
- paths_fixed: `["aciq/classify.py", "aciq/features.py", "aciq/model.py:BROAD_TAXONOMY"]`
- n_corpus: `228`
- n_heldout: `114`
- per-class floor 30: met (counts: `{"video_call_voice": 30, "interactive_gaming": 30, "adaptive_video_streaming": 49, "bulk_download": 40, "software_update": 49, "cloud_backup": 30}`)

Source: `/home/mekarz/Desktop/Full-projects/TATA-ELXSI/data/experiments/classifier_corpus/eval.json` (written by the corpus evaluator, whose failure table is copied verbatim).

## Safe-state and failure injection (S5)

- a_sigterm_no_filter_residue: `"PASS"`
- b_sigkill_residue_then_cleanup: `"PASS"`
- c_injected_failed_apply_rollbacks: `"PASS"`
- c_repeats: `[{"seed": 555, "verify": "PASS", "last_good_t_s": 25.52, "rolled_back_at_t_s": 26.54, "first_recommit_t_s": 27.63, "arm_to_rollback_s": 1.02}, {"seed": 556, "verify": "PASS", "last_good_t_s": 25.53, "rolled_back_at_t_s": 26.56, "first_recommit_t_s": 27.65, "arm_to_rollback_s": 1.03}, {"seed": 557, "verify": "PASS", "last_good_t_s": 25.53, "rolled_back_at_t_s": 26.55, "first_recommit_t_s": 27.64, "arm_to_rollback_s": 1.02}]`
- d_watchdog_starve_reaches_safe: `"PASS"`
- host: `"/home/mekarz/aciq-venv/bin/python -V"`
- notes: `"values PASS/FAIL only; c_repeats carries the three injected seeds (last-good/rollback/recommit stamps and arm-to-rollback seconds from samples.jsonl policy_outcome), tools are the live host versions; the report quotes this file verbatim"`
- tools: `{"tc": "tc utility, iproute2-6.1.0, libbpf 1.3.0", "nft": "nftables v1.0.9 (Old Doc Yak #3)", "iproute2": "ip utility, iproute2-6.1.0, libbpf 1.3.0", "kernel": "7.2.6-76070206-generic", "python": "Python 3.12.3"}`

## EMULATION statement (what is modelled, what is not)

All runs on this host are emulation: one router namespace, its LAN/WAN veth pair, an out-of-band bottleneck (netem with a token bucket limiter on the WAN side) and workload generators in their own netns. There are no physical links, no real video stacks and no third-party traffic; delay/jitter/loss via probes are generator-reported for the transmission path only. No number in this report should be read as an ISP deployment result; the controller's own classification, control loop and translation through tc are the subsystems under test.

