# Results (generated, no summarised files consulted)

Runs root: `data/runs_dev3` | runs used: 300 | scenarios: s2b_ramp_100to30, s2b_step_10, s2b_step_50, s2b_step_up_20to100, s3_stress, s7_down_100to15, s7_down_100to8, s7_rampup_30to100, s7_up_20to60, s7_up_30to100

Generated from engine commit `19e9e8a5e0cc`. Every section header below stamps the commit(s) of the runs it renders; a frozen final band may ONLY claim PASS/FAIL if every run in it carries this same hash — any mismatch is flagged per band and per scenario, never pooled silently.

## Delay and throughput, every scenario x arm (mean +/- 95% CI over seeds; t(9)=2.262 for n=10)

Every block below carries an explicit band label, derived from the seed family recorded at load time: `POST-FIX` (seeds 200-209, the controller after the redesign commits), `PRE-FIX` (legacy seeds 0-9/42-51), `DEV` and `EVAL` (the task-2 protocol: parameters were fixed on the DEV band seeds 400-409 BEFORE the EVAL band seeds 500-509 was run ONCE; nothing between them was tuned). A reader never inherits a number of unknown provenance: the label sits directly above the table. The comparison sections further down use the primary band only.

Bulk has TWO columns on purpose (TASK 5a): `sender` is what the generator pushed, `receiver/sink` is what the receiver's sink log totalled -- the delivered number, used for any bulk claim. The post-drop column stays on the TREE counters and is named so: the three are different instruments and are never blended.

### s2b_ramp_100to30 (primary band: EVAL (1000-1009))

- commit provenance: `19e9e8a5e0cc` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 109.46 +/- 1.31 | 0.67 +/- 0.01 | 0.313 +/- 0.060 | NOT AVAILABLE | 38.02 +/- 0.01 | 37.62 +/- 0.01 | (no drop scenario) | 0.982 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 17.81 +/- 4.93 | 0.54 +/- 0.04 | 0.083 +/- 0.028 | NOT AVAILABLE | 43.58 +/- 1.66 | 43.26 +/- 1.65 | (no drop scenario) | 0.995 +/- 0.002 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 36.41 +/- 9.22 | 0.56 +/- 0.03 | 0.000 +/- 0.000 | NOT AVAILABLE | 46.64 +/- 0.66 | 46.32 +/- 0.66 | (no drop scenario) | 0.999 +/- 0.000 | NOT AVAILABLE |

### s2b_ramp_100to30 (DEV, seeds 1000-1009)

- commit provenance: `19e9e8a5e0cc`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 109.46 +/- 1.31 | 0.67 +/- 0.01 | 0.313 +/- 0.060 | NOT AVAILABLE | 38.02 +/- 0.01 | 37.62 +/- 0.01 | (no drop scenario) | 0.982 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 17.81 +/- 4.93 | 0.54 +/- 0.04 | 0.083 +/- 0.028 | NOT AVAILABLE | 43.58 +/- 1.66 | 43.26 +/- 1.65 | (no drop scenario) | 0.995 +/- 0.002 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 36.41 +/- 9.22 | 0.56 +/- 0.03 | 0.000 +/- 0.000 | NOT AVAILABLE | 46.64 +/- 0.66 | 46.32 +/- 0.66 | (no drop scenario) | 0.999 +/- 0.000 | NOT AVAILABLE |

### s2b_step_10 (primary band: EVAL (1000-1009))

- commit provenance: `19e9e8a5e0cc` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 81.84 +/- 0.81 | 1.04 +/- 0.02 | 0.935 +/- 0.213 | NOT AVAILABLE | 20.10 +/- 0.01 | 19.92 +/- 0.02 | 10.02 +/- 0.00 | 0.846 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 74.64 +/- 2.21 | 1.02 +/- 0.02 | 0.450 +/- 0.114 | NOT AVAILABLE | 29.79 +/- 0.20 | 29.30 +/- 0.19 | 1.58 +/- 1.05 | 0.940 +/- 0.001 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 77.47 +/- 1.95 | 0.97 +/- 0.02 | 0.175 +/- 0.103 | NOT AVAILABLE | 27.84 +/- 0.72 | 27.21 +/- 0.69 | 8.54 +/- 0.17 | 0.925 +/- 0.006 | NOT AVAILABLE |

### s2b_step_10 (DEV, seeds 1000-1009)

- commit provenance: `19e9e8a5e0cc`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 81.84 +/- 0.81 | 1.04 +/- 0.02 | 0.935 +/- 0.213 | NOT AVAILABLE | 20.10 +/- 0.01 | 19.92 +/- 0.02 | 10.02 +/- 0.00 | 0.846 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 74.64 +/- 2.21 | 1.02 +/- 0.02 | 0.450 +/- 0.114 | NOT AVAILABLE | 29.79 +/- 0.20 | 29.30 +/- 0.19 | 1.58 +/- 1.05 | 0.940 +/- 0.001 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 77.47 +/- 1.95 | 0.97 +/- 0.02 | 0.175 +/- 0.103 | NOT AVAILABLE | 27.84 +/- 0.72 | 27.21 +/- 0.69 | 8.54 +/- 0.17 | 0.925 +/- 0.006 | NOT AVAILABLE |

### s2b_step_50 (primary band: EVAL (1000-1009))

- commit provenance: `19e9e8a5e0cc` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 168.64 +/- 1.46 | 0.57 +/- 0.03 | 0.780 +/- 0.121 | NOT AVAILABLE | 48.29 +/- 0.00 | 47.71 +/- 0.00 | 50.00 +/- 0.00 | 1.000 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 10.10 +/- 6.20 | 0.43 +/- 0.02 | 0.050 +/- 0.041 | NOT AVAILABLE | 42.38 +/- 1.98 | 41.97 +/- 2.02 | 25.75 +/- 3.18 | 0.992 +/- 0.004 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 14.20 +/- 4.07 | 0.53 +/- 0.02 | 0.005 +/- 0.011 | NOT AVAILABLE | 49.71 +/- 0.82 | 49.46 +/- 0.82 | 39.49 +/- 0.80 | 1.000 +/- 0.000 | NOT AVAILABLE |

### s2b_step_50 (DEV, seeds 1000-1009)

- commit provenance: `19e9e8a5e0cc`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 168.64 +/- 1.46 | 0.57 +/- 0.03 | 0.780 +/- 0.121 | NOT AVAILABLE | 48.29 +/- 0.00 | 47.71 +/- 0.00 | 50.00 +/- 0.00 | 1.000 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 10.10 +/- 6.20 | 0.43 +/- 0.02 | 0.050 +/- 0.041 | NOT AVAILABLE | 42.38 +/- 1.98 | 41.97 +/- 2.02 | 25.75 +/- 3.18 | 0.992 +/- 0.004 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 14.20 +/- 4.07 | 0.53 +/- 0.02 | 0.005 +/- 0.011 | NOT AVAILABLE | 49.71 +/- 0.82 | 49.46 +/- 0.82 | 39.49 +/- 0.80 | 1.000 +/- 0.000 | NOT AVAILABLE |

### s2b_step_up_20to100 (primary band: EVAL (1000-1009))

- commit provenance: `19e9e8a5e0cc` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.87 +/- 0.06 | 0.59 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.47 +/- 0.00 | 9.45 +/- 0.00 | 9.94 +/- 0.01 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.92 +/- 0.05 | 0.36 +/- 0.06 | 0.010 +/- 0.016 | NOT AVAILABLE | 15.20 +/- 0.85 | 15.17 +/- 0.85 | 15.69 +/- 1.10 | 0.778 +/- 0.013 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 8.16 +/- 5.44 | 0.35 +/- 0.01 | 0.007 +/- 0.010 | NOT AVAILABLE | 45.33 +/- 0.80 | 45.24 +/- 0.79 | 51.54 +/- 1.40 | 0.997 +/- 0.001 | NOT AVAILABLE |

### s2b_step_up_20to100 (DEV, seeds 1000-1009)

- commit provenance: `19e9e8a5e0cc`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.87 +/- 0.06 | 0.59 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.47 +/- 0.00 | 9.45 +/- 0.00 | 9.94 +/- 0.01 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.92 +/- 0.05 | 0.36 +/- 0.06 | 0.010 +/- 0.016 | NOT AVAILABLE | 15.20 +/- 0.85 | 15.17 +/- 0.85 | 15.69 +/- 1.10 | 0.778 +/- 0.013 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 8.16 +/- 5.44 | 0.35 +/- 0.01 | 0.007 +/- 0.010 | NOT AVAILABLE | 45.33 +/- 0.80 | 45.24 +/- 0.79 | 51.54 +/- 1.40 | 0.997 +/- 0.001 | NOT AVAILABLE |

### s3_stress (primary band: EVAL (1000-1009))

- commit provenance: `19e9e8a5e0cc` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.66 +/- 0.46 | 34.40 +/- 1.11 | 34.37 +/- 1.10 | (no drop scenario) | 0.573 +/- 0.016 | 0.979 +/- 0.047 |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 17.78 +/- 5.51 | 62.73 +/- 3.37 | 62.45 +/- 3.43 | (no drop scenario) | 0.466 +/- 0.016 | 0.979 +/- 0.047 |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 18.36 +/- 3.20 | 71.70 +/- 2.44 | 71.46 +/- 2.44 | (no drop scenario) | 0.440 +/- 0.012 | 0.979 +/- 0.047 |

### s3_stress (DEV, seeds 1000-1009)

- commit provenance: `19e9e8a5e0cc`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.66 +/- 0.46 | 34.40 +/- 1.11 | 34.37 +/- 1.10 | (no drop scenario) | 0.573 +/- 0.016 | 0.979 +/- 0.047 |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 17.78 +/- 5.51 | 62.73 +/- 3.37 | 62.45 +/- 3.43 | (no drop scenario) | 0.466 +/- 0.016 | 0.979 +/- 0.047 |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 18.36 +/- 3.20 | 71.70 +/- 2.44 | 71.46 +/- 2.44 | (no drop scenario) | 0.440 +/- 0.012 | 0.979 +/- 0.047 |

### s7_down_100to15 (primary band: EVAL (1000-1009))

- commit provenance: `19e9e8a5e0cc` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 86.30 +/- 0.49 | 0.78 +/- 0.01 | 0.410 +/- 0.101 | NOT AVAILABLE | 23.72 +/- 0.01 | 23.44 +/- 0.01 | 14.93 +/- 0.02 | 0.887 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 48.07 +/- 8.97 | 0.81 +/- 0.03 | 0.175 +/- 0.061 | NOT AVAILABLE | 33.88 +/- 0.83 | 33.46 +/- 0.82 | 2.49 +/- 3.35 | 0.964 +/- 0.005 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 59.79 +/- 6.28 | 0.79 +/- 0.03 | 0.045 +/- 0.090 | NOT AVAILABLE | 31.14 +/- 0.59 | 30.70 +/- 0.60 | 13.18 +/- 0.37 | 0.949 +/- 0.004 | NOT AVAILABLE |

### s7_down_100to15 (DEV, seeds 1000-1009)

- commit provenance: `19e9e8a5e0cc`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 86.30 +/- 0.49 | 0.78 +/- 0.01 | 0.410 +/- 0.101 | NOT AVAILABLE | 23.72 +/- 0.01 | 23.44 +/- 0.01 | 14.93 +/- 0.02 | 0.887 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 48.07 +/- 8.97 | 0.81 +/- 0.03 | 0.175 +/- 0.061 | NOT AVAILABLE | 33.88 +/- 0.83 | 33.46 +/- 0.82 | 2.49 +/- 3.35 | 0.964 +/- 0.005 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 59.79 +/- 6.28 | 0.79 +/- 0.03 | 0.045 +/- 0.090 | NOT AVAILABLE | 31.14 +/- 0.59 | 30.70 +/- 0.60 | 13.18 +/- 0.37 | 0.949 +/- 0.004 | NOT AVAILABLE |

### s7_down_100to8 (primary band: EVAL (1000-1009))

- commit provenance: `19e9e8a5e0cc` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 78.03 +/- 0.82 | 1.22 +/- 0.02 | 0.495 +/- 0.175 | NOT AVAILABLE | 18.75 +/- 0.02 | 18.57 +/- 0.01 | 7.99 +/- 0.01 | 0.829 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 76.71 +/- 0.74 | 1.18 +/- 0.03 | 0.490 +/- 0.047 | NOT AVAILABLE | 29.39 +/- 0.33 | 28.75 +/- 0.27 | 1.59 +/- 2.51 | 0.937 +/- 0.002 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 80.62 +/- 1.23 | 1.33 +/- 0.04 | 0.440 +/- 0.161 | NOT AVAILABLE | 27.42 +/- 0.42 | 26.71 +/- 0.40 | 7.90 +/- 0.12 | 0.922 +/- 0.004 | NOT AVAILABLE |

### s7_down_100to8 (DEV, seeds 1000-1009)

- commit provenance: `19e9e8a5e0cc`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 78.03 +/- 0.82 | 1.22 +/- 0.02 | 0.495 +/- 0.175 | NOT AVAILABLE | 18.75 +/- 0.02 | 18.57 +/- 0.01 | 7.99 +/- 0.01 | 0.829 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 76.71 +/- 0.74 | 1.18 +/- 0.03 | 0.490 +/- 0.047 | NOT AVAILABLE | 29.39 +/- 0.33 | 28.75 +/- 0.27 | 1.59 +/- 2.51 | 0.937 +/- 0.002 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 80.62 +/- 1.23 | 1.33 +/- 0.04 | 0.440 +/- 0.161 | NOT AVAILABLE | 27.42 +/- 0.42 | 26.71 +/- 0.40 | 7.90 +/- 0.12 | 0.922 +/- 0.004 | NOT AVAILABLE |

### s7_rampup_30to100 (primary band: EVAL (1000-1009))

- commit provenance: `19e9e8a5e0cc` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.56 +/- 0.03 | 0.43 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | (no drop scenario) | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.91 +/- 0.03 | 0.31 +/- 0.02 | 0.007 +/- 0.010 | NOT AVAILABLE | 24.75 +/- 0.41 | 24.71 +/- 0.40 | (no drop scenario) | 0.898 +/- 0.004 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 10.40 +/- 3.94 | 0.43 +/- 0.01 | 0.007 +/- 0.010 | NOT AVAILABLE | 56.14 +/- 1.25 | 56.03 +/- 1.24 | (no drop scenario) | 0.996 +/- 0.001 | NOT AVAILABLE |

### s7_rampup_30to100 (DEV, seeds 1000-1009)

- commit provenance: `19e9e8a5e0cc`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.56 +/- 0.03 | 0.43 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | (no drop scenario) | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.91 +/- 0.03 | 0.31 +/- 0.02 | 0.007 +/- 0.010 | NOT AVAILABLE | 24.75 +/- 0.41 | 24.71 +/- 0.40 | (no drop scenario) | 0.898 +/- 0.004 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 10.40 +/- 3.94 | 0.43 +/- 0.01 | 0.007 +/- 0.010 | NOT AVAILABLE | 56.14 +/- 1.25 | 56.03 +/- 1.24 | (no drop scenario) | 0.996 +/- 0.001 | NOT AVAILABLE |

### s7_up_20to60 (primary band: EVAL (1000-1009))

- commit provenance: `19e9e8a5e0cc` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.97 +/- 0.05 | 0.58 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.47 +/- 0.00 | 9.45 +/- 0.00 | 10.00 +/- 0.00 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 2.18 +/- 0.03 | 0.38 +/- 0.06 | 0.013 +/- 0.012 | NOT AVAILABLE | 16.01 +/- 0.31 | 15.97 +/- 0.31 | 16.46 +/- 0.40 | 0.790 +/- 0.005 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 9.96 +/- 2.88 | 0.47 +/- 0.02 | 0.007 +/- 0.010 | NOT AVAILABLE | 35.11 +/- 1.87 | 35.03 +/- 1.87 | 38.82 +/- 1.92 | 0.969 +/- 0.009 | NOT AVAILABLE |

### s7_up_20to60 (DEV, seeds 1000-1009)

- commit provenance: `19e9e8a5e0cc`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.97 +/- 0.05 | 0.58 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.47 +/- 0.00 | 9.45 +/- 0.00 | 10.00 +/- 0.00 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 2.18 +/- 0.03 | 0.38 +/- 0.06 | 0.013 +/- 0.012 | NOT AVAILABLE | 16.01 +/- 0.31 | 15.97 +/- 0.31 | 16.46 +/- 0.40 | 0.790 +/- 0.005 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 9.96 +/- 2.88 | 0.47 +/- 0.02 | 0.007 +/- 0.010 | NOT AVAILABLE | 35.11 +/- 1.87 | 35.03 +/- 1.87 | 38.82 +/- 1.92 | 0.969 +/- 0.009 | NOT AVAILABLE |

### s7_up_30to100 (primary band: EVAL (1000-1009))

- commit provenance: `19e9e8a5e0cc` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.47 +/- 0.03 | 0.42 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | 14.99 +/- 0.00 | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.89 +/- 0.04 | 0.28 +/- 0.02 | 0.023 +/- 0.020 | NOT AVAILABLE | 25.59 +/- 0.70 | 25.55 +/- 0.70 | 26.61 +/- 0.87 | 0.905 +/- 0.006 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 11.37 +/- 4.77 | 0.39 +/- 0.02 | 0.003 +/- 0.007 | NOT AVAILABLE | 56.76 +/- 1.53 | 56.66 +/- 1.52 | 64.38 +/- 2.64 | 0.996 +/- 0.002 | NOT AVAILABLE |

### s7_up_30to100 (DEV, seeds 1000-1009)

- commit provenance: `19e9e8a5e0cc`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.47 +/- 0.03 | 0.42 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | 14.99 +/- 0.00 | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.89 +/- 0.04 | 0.28 +/- 0.02 | 0.023 +/- 0.020 | NOT AVAILABLE | 25.59 +/- 0.70 | 25.55 +/- 0.70 | 26.61 +/- 0.87 | 0.905 +/- 0.006 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 11.37 +/- 4.77 | 0.39 +/- 0.02 | 0.003 +/- 0.007 | NOT AVAILABLE | 56.76 +/- 1.53 | 56.66 +/- 1.52 | 64.38 +/- 2.64 | 0.996 +/- 0.002 | NOT AVAILABLE |

## ACIQ vs every arm (positive % is better ACIQ on the metric at the head of the column; a cell like `41.0x` is the multiplicative factor when the baseline is so close to zero that a percentage would mislead)

| scenario | vs arm | call p95 delta % | CI overlap? | bulk delta % | CI overlap? |
| --- | --- | --- | --- | --- | --- |
Bulk compares are POST-DROP ONLY in scenarios with a capacity drop (same `bulk_mbps` whole-run mean otherwise): the whole-run number dilutes the post-drop regime with a saturated prefix, which is the opposite of the decision those scenarios exist to measure.

| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +66.7 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -104.4 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +5.3 | disjoint | -14.8 | disjoint |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -3.8 | overlap | +439.5 | disjoint |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +91.6 | disjoint | -21.0 | disjoint |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -40.6 | overlap | +53.4 | disjoint |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -335.6 | disjoint | +418.7 | disjoint |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -324.7 | disjoint | +228.4 | disjoint |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +30.7 | disjoint | -11.7 | disjoint |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -24.4 | overlap | +429.5 | disjoint |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -3.3 | disjoint | -1.1 | overlap |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -5.1 | disjoint | +397.7 | disjoint |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -565.2 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -445.9 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -405.2 | disjoint | +288.3 | disjoint |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -357.5 | disjoint | +135.8 | disjoint |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -675.0 | disjoint | +329.6 | disjoint |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -500.5 | disjoint | +141.9 | disjoint |

## Where ACIQ is worse (the honest column)

Every row above where ACIQ's signed delta is negative, collected so a CAKE win cannot hide behind the aggregate. Empty means no such pair exists in the runs found.

| scenario | vs arm | metric where ACIQ is worse |
| --- | --- | --- |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -104.4 |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -14.8 |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -3.8 |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -21.0 |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -40.6 |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -335.6 |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -324.7 |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -11.7 |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -24.4 |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -3.3 and post-drop bulk Mbps -1.1 |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -5.1 |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -565.2 |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -445.9 |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -405.2 |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -357.5 |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -675.0 |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -500.5 |

## Where CAKE-static wins

The honest column above lists every rival; this one isolates the set-and-forget rival that matters for the design claim. A CAKE win on a metric is stated here verbatim; nothing is re-derived and nothing is argued away. CI overlap of the underlying seed samples is in the table above (`CI overlap?` column).

| scenario | metric where CAKE-static beats ACIQ | see column in the ACIQ-vs-every table |
| --- | --- | --- |
(none in these runs)

## ACIQ adaptation and capacity accuracy (from the same runs above)

| scenario | n | bind: drop -> first applied <=1.05x post-drop (s) | bind: drop -> first applied <=1.25x post-drop (s) | final estimate | configured end link | estimate error % |
| --- | --- | --- | --- | --- | --- | --- |
| s2b_ramp_100to30 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 25.94 +/- 1.31 | 30.0 +/- 0.0 | mean abs 13.5% (seed0: 22.98/30.0 (23.4% off)) |
| s2b_step_10 | 10 | 7.11 (n=10) | 7.11 (n=10) | 8.48 +/- 0.39 | 10.0 +/- 0.0 | mean abs 15.2% (seed0: 8.06/10.0 (19.4% off)) |
| s2b_step_50 | 10 | 2.81 (n=10) | 2.27 (n=10) | 43.51 +/- 1.25 | 50.0 +/- 0.0 | mean abs 13.0% (seed0: 43.59/50.0 (12.8% off)) |
| s2b_step_up_20to100 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 41.35 +/- 1.17 | 100.0 +/- 0.0 | mean abs 58.7% (seed0: 41.58/100.0 (58.4% off)) |
| s3_stress | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 92.91 +/- 4.72 | 100.0 +/- 0.0 | mean abs 7.3% (seed0: 99.48/100.0 (0.5% off)) |
| s7_down_100to15 | 10 | 8.22 (n=9) | 3.51 (n=10) | 14.52 +/- 0.53 | 15.0 +/- 0.0 | mean abs 5.1% (seed0: 14.09/15.0 (6.1% off)) |
| s7_down_100to8 | 10 | 18.27 (n=10) | 15.39 (n=10) | 7.83 +/- 0.46 | 8.0 +/- 0.0 | mean abs 6.9% (seed0: 7.91/8.0 (1.1% off)) |
| s7_rampup_30to100 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 55.26 +/- 2.73 | 100.0 +/- 0.0 | mean abs 44.7% (seed0: 52.68/100.0 (47.3% off)) |
| s7_up_20to60 | 10 | 0.27 (n=1) | 3.33 (n=3) | 33.99 +/- 2.40 | 60.0 +/- 0.0 | mean abs 43.4% (seed0: 34.18/60.0 (43.0% off)) |
| s7_up_30to100 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | 3.84 (n=2) | 54.63 +/- 3.09 | 100.0 +/- 0.0 | mean abs 45.4% (seed0: 53.53/100.0 (46.5% off)) |
## Controller resources (ACIQ adaptive runs only; from each result's resources block)

| scenario | n | cpu mean frac | decision p95 ms | decision max ms | max RSS bytes |
| --- | --- | --- | --- | --- | --- |
| s2b_ramp_100to30 | 10 | 0.0084 +/- 0.0006 | 76.61 +/- 0.91 | 109.25 +/- 52.26 | 30057267 +/- 726465 |
| s2b_step_10 | 10 | 0.0076 +/- 0.0001 | 74.81 +/- 1.51 | 82.71 +/- 3.92 | 29096755 +/- 569519 |
| s2b_step_50 | 10 | 0.0083 +/- 0.0003 | 93.58 +/- 8.59 | 157.29 +/- 39.61 | 29696000 +/- 410465 |
| s2b_step_up_20to100 | 10 | 0.0079 +/- 0.0003 | 83.51 +/- 5.34 | 124.45 +/- 33.98 | 30115430 +/- 753612 |
| s3_stress | 10 | 0.0167 +/- 0.0002 | 179.23 +/- 6.21 | 194.97 +/- 5.58 | 29415424 +/- 640735 |
| s7_down_100to15 | 10 | 0.0145 +/- 0.0002 | 181.09 +/- 9.01 | 205.24 +/- 6.79 | 29097165 +/- 493127 |
| s7_down_100to8 | 10 | 0.0142 +/- 0.0003 | 176.42 +/- 8.46 | 194.67 +/- 9.43 | 28941107 +/- 533224 |
| s7_rampup_30to100 | 10 | 0.0157 +/- 0.0002 | 184.20 +/- 3.58 | 201.18 +/- 5.35 | 29830758 +/- 737708 |
| s7_up_20to60 | 10 | 0.0153 +/- 0.0002 | 190.82 +/- 3.24 | 216.68 +/- 16.73 | 29902438 +/- 771920 |
| s7_up_30to100 | 10 | 0.0152 +/- 0.0003 | 185.52 +/- 6.31 | 203.05 +/- 5.49 | 29933978 +/- 695570 |
- CPU context (adaptive vs adaptive): CAKE-adaptive runs at 0.51x the ACIQ CPU fraction on the shared scenario(s): s2b_ramp_100to30 0.63x, s2b_step_10 0.59x, s2b_step_50 0.47x, s2b_step_up_20to100 0.43x, s3_stress 0.45x, s7_down_100to15 0.57x, s7_down_100to8 0.57x, s7_rampup_30to100 0.48x, s7_up_20to60 0.46x, s7_up_30to100 0.47x. The cause must be read from the artifacts (CPU profile, decision cadence), not assumed.

## Fairness detail (workload-rate Jain; per-class minima over ASSIGNED classes only, same scope for every mode)

| scenario | arm | n | jain mean +/- CI | demand-jain mean +/- CI | flows used | min over time (per label, via carrying class) |
| --- | --- | --- | --- | --- | --- | --- |
demand-jain: Jain over per-flow satisfied-demand ratios (achieved/demand, demand self-reported by the generator; elastic flows without a declared demand are excluded by definition -- see aciq/fairness.py). A scenario flows all-elastic has no such index and prints NOT AVAILABLE rather than a substitute.

Per-tick counter attribution (fix 18): ACIQ's tree has one leaf per class; the baselines' single-class tree carries the WHOLE link on the 1:50 leaf. New artefacts sample that aggregate under `unknown` (an aggregate can no longer masquerade as a software_update class); artefacts from before this change stored the same aggregate under `software_update`, and consumers that fall back to the legacy label must name it -- the post-drop bulk column does exactly that.

| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.982 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=29.9; call via unknown=29.9 |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.995 +/- 0.002 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=13.3; call via unknown=13.3; bulk via unknown=13.3; call via unknown=13.3; bulk via unknown=14.1; call via unknown=14.1 |
| s2b_ramp_100to30 | ACIQ (controller) | 10 | 0.999 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.846 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.97; call via unknown=9.97 |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.940 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=0.0117; call via unknown=0.0117; bulk via unknown=0.00939; call via unknown=0.00939; bulk via unknown=0; call via unknown=0 |
| s2b_step_10 | ACIQ (controller) | 10 | 0.925 +/- 0.006 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.000 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=49.5; call via unknown=49.5; bulk via unknown=49.8; call via unknown=49.8; bulk via unknown=49.7; call via unknown=49.7 |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.992 +/- 0.004 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=18.6; call via unknown=18.6; bulk via unknown=21.1; call via unknown=21.1; bulk via unknown=21; call via unknown=21 |
| s2b_step_50 | ACIQ (controller) | 10 | 1.000 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.683 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.99; call via unknown=9.99; bulk via unknown=9.97; call via unknown=9.97; bulk via unknown=9.96; call via unknown=9.96 |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.778 +/- 0.013 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=16.1; call via unknown=16.1; bulk via unknown=15.2; call via unknown=15.2; bulk via unknown=13.2; call via unknown=13.2 |
| s2b_step_up_20to100 | ACIQ (controller) | 10 | 0.997 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.573 +/- 0.016 | 0.979 +/- 0.047 | 5.0 +/- 0.0 | bulk via unknown=49.9; game via unknown=49.9; tv1 via unknown=49.9; tv2 via unknown=49.9; tv3 via unknown=49.9; bulk via unknown=50 |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.466 +/- 0.016 | 0.979 +/- 0.047 | 5.0 +/- 0.0 | bulk via unknown=78.8; game via unknown=78.8; tv1 via unknown=78.8; tv2 via unknown=78.8; tv3 via unknown=78.8; bulk via unknown=79 |
| s3_stress | ACIQ (controller) | 10 | 0.440 +/- 0.012 | 0.979 +/- 0.047 | 5.0 +/- 0.0 | bulk=0; game via unknown=0; tv1=0; tv2=0; tv3=0; bulk=0 |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.887 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15 |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.964 +/- 0.005 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=0.0461; call via unknown=0.0461; bulk via unknown=0; call via unknown=0; bulk via unknown=0; call via unknown=0 |
| s7_down_100to15 | ACIQ (controller) | 10 | 0.949 +/- 0.004 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.829 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=7.97; call via unknown=7.97; bulk via unknown=7.98; call via unknown=7.98; bulk via unknown=7.98; call via unknown=7.98 |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.937 +/- 0.002 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=0.0333; call via unknown=0.0333; bulk via unknown=0.0112; call via unknown=0.0112; bulk via unknown=11.2; call via unknown=11.2 |
| s7_down_100to8 | ACIQ (controller) | 10 | 0.922 +/- 0.004 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.764 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15 |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.898 +/- 0.004 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=25.6; call via unknown=25.6; bulk via unknown=25.6; call via unknown=25.6; bulk via unknown=23.9; call via unknown=23.9 |
| s7_rampup_30to100 | ACIQ (controller) | 10 | 0.996 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.683 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.99; call via unknown=9.99; bulk via unknown=9.99; call via unknown=9.99; bulk via unknown=9.98; call via unknown=9.98 |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.790 +/- 0.005 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=17.2; call via unknown=17.2; bulk via unknown=16.1; call via unknown=16.1; bulk via unknown=16.1; call via unknown=16.1 |
| s7_up_20to60 | ACIQ (controller) | 10 | 0.969 +/- 0.009 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.764 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15 |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.905 +/- 0.006 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=25.5; call via unknown=25.5; bulk via unknown=25.5; call via unknown=25.5; bulk via unknown=24.1; call via unknown=24.1 |
| s7_up_30to100 | ACIQ (controller) | 10 | 0.996 +/- 0.002 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |

Starvation (TASK 5b, fixed basis): per LABEL, over the class the data says carried the traffic (assigned class, or the router's `unknown`/legacy aggregate when the label's traffic rode there -- chosen by highest mean, and the carrying class is named). A label starved in tick t if its per-tick goodput fell below 20% of its REGIME median -- in a drop scenario the median is the POST-DROP regime's own median, so the shaped link rate can never masquerade as starvation; without a drop it is the whole window's. The cell lists the starved timestamps counted over seeds. With no series at all the cell prints NOT AVAILABLE, never an empty claim.

| scenario | arm | starved ticks per label (via carrying class) |
| --- | --- | --- |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 14 ticks over 4 seed(s), first t=46.4; call via unknown: 14 ticks over 4 seed(s), first t=46.4 |
| s2b_ramp_100to30 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 307 ticks over 10 seed(s), first t=5.3 |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 6 ticks over 5 seed(s), first t=20.7; call via unknown: 6 ticks over 5 seed(s), first t=20.7 |
| s2b_step_10 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 197 ticks over 10 seed(s), first t=5.3 |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 217 ticks over 10 seed(s), first t=5.3 |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 287 ticks over 10 seed(s), first t=5.3 |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 49 seed x label series (regime-aware threshold, declared window) |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 49 seed x label series (regime-aware threshold, declared window) |
| s3_stress | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.2; game via unknown: 82 ticks over 10 seed(s), first t=21.8; tv1 via adaptive_video_streaming: 18 ticks over 4 seed(s), first t=2.2; tv1 via unknown: 49 ticks over 6 seed(s), first t=19.5; tv2 via adaptive_video_streaming: 18 ticks over 4 seed(s), first t=2.2; tv2 via unknown: 41 ticks over 5 seed(s), first t=19.5; tv3 via adaptive_video_streaming: 18 ticks over 4 seed(s), first t=2.2; tv3 via unknown: 49 ticks over 6 seed(s), first t=19.5 |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 18 ticks over 8 seed(s), first t=8.5; call via unknown: 18 ticks over 8 seed(s), first t=8.5 |
| s7_down_100to15 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.2; call via unknown: 183 ticks over 10 seed(s), first t=5.7 |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 3 ticks over 3 seed(s), first t=30.1; call via unknown: 3 ticks over 3 seed(s), first t=30.1 |
| s7_down_100to8 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.2; call via unknown: 159 ticks over 10 seed(s), first t=5.6 |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_rampup_30to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.2; call via unknown: 275 ticks over 10 seed(s), first t=6.8 |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_20to60 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.2; call via unknown: 267 ticks over 10 seed(s), first t=5.8 |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_30to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.2; call via unknown: 277 ticks over 10 seed(s), first t=5.8 |

Warm-up exclusion (declared): every per-tick window above starts at t >= 2.0 s. The diagnosis round (fix 17's diagnosis.md) shows the first ~2 s of per-tick counter rates are a transmit/counter ramp artefact, not traffic behaviour; dropping those ticks removes nothing else. The window boundary is a declared constant in this generator, not a per-run choice.

Further declared exclusions (TASK 5b): (1) ticks at or beyond the label generator's own measured lifetime (`elapsed_s`, capped by the scenario duration) -- a verdict about a label after its traffic stopped describes nothing about the label; (2) ticks whose link counters went BACKWARDS -- a qdisc del/re-add resets every counter on the device, so that tick's per-class goodput is a reset artefact, not a delivery gap. Stars and minima are computed over what remains; nothing is excluded silently.

## Step/demand generalization band (evaluation-only; docs/evidence/s2b-params.md + docs/evidence/round3-params.md, declared BEFORE these runs)

The shipped controller runs unchanged on capacity changes it was never tuned on: two down-step magnitudes, a 5x up-step, and a continuous 20 s ramp -- plus the round-3 DEV shapes (s7_* up/down steps and ramps, s3_stress) and the two queue-discipline-only arms (CAKE-conservative / CAKE-adaptive). Seeds 800-809 configured per scenario (the DEV band, seed names in each run dir). CAKE-static is applied once at launch and never re-applied: that is its declared semantics, and this band exists to surface the consequences. Definitions: bind = first tick at which the applied tree sits within 10% of the link's truth and stays there (down-moves only; up-moves print `n/a (up-step)` and are judged by the utilization column: applied/truth and receiver delivered/truth over the final third); tracking error = mean |applied - truth| over the ramp window; estimate error = same over the final third. Where ACIQ fails, the row says so.

Engine commit at generation time: `19e9e8a5e0cc` — a run whose result carries a different commit_hash is SUPERSEDED, listed under 'commit provenance' below and never pooled into a numeric cell with a newer commit.

### s2b_step_50

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 50.00 +/- 0.00 | 168.64 +/- 1.46 | 47.61 +/- 0.23 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 50.00 +/- 0.00 | 10.10 +/- 6.20 | 23.00 +/- 4.30 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 12.6 +/- 1.1 | 5.49 +/- 1.44 | 14.20 +/- 4.07 | 31.39 +/- 1.28 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 44.5 vs truth 50.0, 11% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 47.5 vs truth 50.0, 5% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 44.4 vs truth 50.0, 11% off truth, confidence 0.05; final tick: UNSATURATED (estimator not saturated at the end regime), applied 46.1 vs truth 50.0, 8% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 41.5 vs truth 50.0, 17% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 42.1 vs truth 50.0, 16% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 42.9 vs truth 50.0, 14% off truth, confidence 0.35; final tick: UNSATURATED (estimator not saturated at the end regime), applied 47.1 vs truth 50.0, 6% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 44.4 vs truth 50.0, 11% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 44.7 vs truth 50.0, 11% off truth, confidence 0.35 |

### s2b_step_10

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 90.00 +/- 0.00 | 81.84 +/- 0.81 | 9.45 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 90.00 +/- 0.00 | 74.64 +/- 2.21 | 9.26 +/- 0.14 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 16.9 +/- 0.1 | 1.46 +/- 0.34 | 77.47 +/- 1.95 | 6.51 +/- 0.30 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.1 vs truth 10.0, 19% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 9.4 vs truth 10.0, 6% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.2 vs truth 10.0, 18% off truth, confidence 0.30; final tick: UNSATURATED (estimator not saturated at the end regime), applied 9.3 vs truth 10.0, 7% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.3 vs truth 10.0, 17% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.2 vs truth 10.0, 18% off truth, confidence 0.35 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.8 vs truth 10.0, 12% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.2 vs truth 10.0, 18% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.2 vs truth 10.0, 18% off truth, confidence 0.10 |

### s2b_step_up_20to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 80.00 +/- 0.00 | 1.87 +/- 0.06 | 9.36 +/- 0.07 | appl 0.20 +/- 0.00 / delv 0.09 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 80.00 +/- 0.00 | 1.92 +/- 0.05 | 14.51 +/- 1.29 | appl 0.20 +/- 0.00 / delv 0.15 +/- 0.01 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 10.50 +/- 0.70 | 8.16 +/- 5.44 | 67.90 +/- 2.90 | appl 1.01 +/- 0.05 / delv 0.68 +/- 0.03 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 104.3 vs truth 100.0, 4% off truth, confidence 0.25 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 89.9 vs truth 100.0, 10% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 104.3 vs truth 100.0, 4% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 90.4 vs truth 100.0, 10% off truth, confidence 0.20 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 90.2 vs truth 100.0, 10% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 104.2 vs truth 100.0, 4% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 89.8 vs truth 100.0, 10% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 89.7 vs truth 100.0, 10% off truth, confidence 0.25 |

### s2b_ramp_100to30

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 109.46 +/- 1.31 | 28.58 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 17.81 +/- 4.93 | 17.46 +/- 2.67 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 30.9 +/- 0.4 | 3.34 +/- 1.34 | 36.41 +/- 9.22 | 19.77 +/- 0.88 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 23.4 vs truth 30.0, 22% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 23.7 vs truth 30.0, 21% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 26.1 vs truth 30.0, 13% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 26.1 vs truth 30.0, 13% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 26.1 vs truth 30.0, 13% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 29.3 vs truth 30.0, 2% off truth, confidence 0.15; final tick: UNSATURATED (estimator not saturated at the end regime), applied 29.2 vs truth 30.0, 3% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 24.8 vs truth 30.0, 17% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 24.0 vs truth 30.0, 20% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 30.0, 53% off truth, confidence 0.25 |

### s7_up_20to60

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 40.00 +/- 0.00 | 1.97 +/- 0.05 | 9.09 +/- 0.17 | appl 0.33 +/- 0.00 / delv 0.15 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 40.00 +/- 0.00 | 2.18 +/- 0.03 | 14.61 +/- 0.71 | appl 0.33 +/- 0.00 / delv 0.25 +/- 0.01 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 8.15 +/- 1.71 | 9.96 +/- 2.88 | 34.75 +/- 1.37 | appl 1.13 +/- 0.04 / delv 0.58 +/- 0.02 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 68.7 vs truth 60.0, 14% off truth, confidence 0.00 (n=6); final tick: UNSATURATED (estimator not saturated at the end regime), applied 73.9 vs truth 60.0, 23% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 59.7 vs truth 60.0, 1% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 74.4 vs truth 60.0, 24% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 82.0 vs truth 60.0, 37% off truth, confidence 0.00 |

### s7_up_30to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 70.00 +/- 0.00 | 1.47 +/- 0.03 | 13.68 +/- 0.22 | appl 0.30 +/- 0.00 / delv 0.14 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 70.00 +/- 0.00 | 1.89 +/- 0.04 | 24.02 +/- 0.86 | appl 0.30 +/- 0.00 / delv 0.24 +/- 0.01 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 10.28 +/- 3.16 | 11.37 +/- 4.77 | 58.40 +/- 3.20 | appl 1.09 +/- 0.04 / delv 0.58 +/- 0.03 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 109.2 vs truth 100.0, 9% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 101.1 vs truth 100.0, 1% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 106.1 vs truth 100.0, 6% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 109.6 vs truth 100.0, 10% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 110.2 vs truth 100.0, 10% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 128.7 vs truth 100.0, 29% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 103.0 vs truth 100.0, 3% off truth, confidence 0.00 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 105.6 vs truth 100.0, 6% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 102.9 vs truth 100.0, 3% off truth, confidence 0.00 |

### s7_rampup_30to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 1.56 +/- 0.03 | 13.78 +/- 0.17 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 1.91 +/- 0.03 | 22.11 +/- 0.91 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 53.1 +/- 1.6 | 8.86 +/- 3.79 | 10.40 +/- 3.94 | 57.61 +/- 2.04 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 107.1 vs truth 100.0, 7% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 109.5 vs truth 100.0, 9% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 120.0 vs truth 100.0, 20% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 103.0 vs truth 100.0, 3% off truth, confidence 0.00 (n=5); final tick: UNSATURATED (estimator not saturated at the end regime), applied 109.1 vs truth 100.0, 9% off truth, confidence 0.00 (n=2) |

### s7_down_100to15

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 85.00 +/- 0.00 | 86.30 +/- 0.49 | 14.20 +/- 0.07 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 85.00 +/- 0.00 | 48.07 +/- 8.97 | 12.15 +/- 0.37 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 19.7 +/- 2.9 | 0.99 +/- 0.23 | 59.79 +/- 6.28 | 8.32 +/- 0.47 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 13.8 vs truth 15.0, 8% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 13.9 vs truth 15.0, 7% off truth, confidence 0.10 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 16.0 vs truth 15.0, 7% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 13.5 vs truth 15.0, 10% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 13.7 vs truth 15.0, 9% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.5 vs truth 15.0, 3% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.1 vs truth 15.0, 6% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.3 vs truth 15.0, 5% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.4 vs truth 15.0, 4% off truth, confidence 0.10 |

### s7_down_100to8

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 92.00 +/- 0.00 | 78.03 +/- 0.82 | 7.54 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 92.00 +/- 0.00 | 76.71 +/- 0.74 | 6.65 +/- 0.16 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 32.8 +/- 6.4 | 0.71 +/- 0.21 | 80.62 +/- 1.23 | 4.83 +/- 0.31 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 7.1 vs truth 8.0, 11% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 6.9 vs truth 8.0, 13% off truth, confidence 0.25 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 7.8 vs truth 8.0, 3% off truth, confidence 0.25 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 6.8 vs truth 8.0, 15% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 6.7 vs truth 8.0, 16% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 6.8 vs truth 8.0, 15% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 7.8 vs truth 8.0, 2% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 7.1 vs truth 8.0, 12% off truth, confidence 0.25 |

### s3_stress

| arm | n | call p95 whole-run (ms) | game p95 whole-run (ms) | bulk receiver mean inst (Mbps) | tv1 / tv2 / tv3 receiver mean inst (Mbps) | overload note (loaded vs capacity) |
| --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE | 2.66 +/- 0.46 | 31.36 +/- 1.07 | 4.30 / 4.30 / 4.30; 4.43 / 4.39; 4.39 / 4.40 / 4.39; 4.29 / 4.30 / 4.30; 4.50 / 4.50 / 4.50; 4.39 / 4.39 / 4.40; 4.50 / 4.49 / 4.50; 4.49 / 4.50 / 4.50; 4.30 / 4.30 / 4.30; 4.50 / 4.50 / 4.50 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE | 17.78 +/- 5.51 | 55.66 +/- 3.16 | 4.20 / 4.21 / 4.21; 4.33 / 4.30; 4.30 / 4.30 / 4.30; 4.21 / 4.21 / 4.21; 4.30 / 4.30 / 4.30; 4.30 / 4.30 / 4.30; 4.40 / 4.40 / 4.40; 4.40 / 4.40 / 4.40; 4.21 / 4.20 / 4.21; 4.30 / 4.30 / 4.30 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |
| ACIQ (controller) | 10 | NOT AVAILABLE | 18.36 +/- 3.20 | 58.81 +/- 2.37 | 3.95 / 3.95 / 3.95; 3.98 / 3.95; 3.95 / 3.95 / 3.95; 3.87 / 3.87 / 3.87; 3.95 / 3.95 / 3.95; 3.95 / 3.95 / 3.95; 4.12 / 4.12 / 4.12; 4.03 / 4.03 / 4.03; 3.87 / 3.87 / 3.95; 4.03 / 4.03 / 4.03 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |

## Starvation, receiver side (every arm, per-second sink logs)

| scenario | arm | label; starved inst ticks over seeds (longest streak) |
| --- | --- | --- |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 2 tick(s) over 10 seed(s), longest streak 1 s; call: 15 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 20 tick(s) over 10 seed(s), longest streak 4 s; call: 31 tick(s) over 10 seed(s), longest streak 5 s |
| s2b_ramp_100to30 | ACIQ (controller) | bulk: 35 tick(s) over 10 seed(s), longest streak 4 s; call: 48 tick(s) over 10 seed(s), longest streak 5 s |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 8 tick(s) over 10 seed(s), longest streak 1 s |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 9 tick(s) over 10 seed(s), longest streak 1 s; call: 20 tick(s) over 10 seed(s), longest streak 3 s |
| s2b_step_10 | ACIQ (controller) | bulk: 16 tick(s) over 10 seed(s), longest streak 2 s; call: 30 tick(s) over 10 seed(s), longest streak 4 s |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 11 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 9 tick(s) over 10 seed(s), longest streak 1 s; call: 19 tick(s) over 10 seed(s), longest streak 3 s |
| s2b_step_50 | ACIQ (controller) | bulk: 28 tick(s) over 10 seed(s), longest streak 3 s; call: 36 tick(s) over 10 seed(s), longest streak 4 s |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 5 tick(s) over 10 seed(s), longest streak 1 s; call: 13 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 12 tick(s) over 10 seed(s), longest streak 2 s; call: 19 tick(s) over 10 seed(s), longest streak 3 s |
| s2b_step_up_20to100 | ACIQ (controller) | bulk: 37 tick(s) over 10 seed(s), longest streak 4 s; call: 45 tick(s) over 10 seed(s), longest streak 6 s |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 14 tick(s) over 10 seed(s), longest streak 1 s; game: 32 tick(s) over 10 seed(s), longest streak 4 s; tv1: 27 tick(s) over 10 seed(s), longest streak 3 s; tv2: 19 tick(s) over 9 seed(s), longest streak 3 s; tv3: 19 tick(s) over 10 seed(s), longest streak 2 s |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 24 tick(s) over 10 seed(s), longest streak 3 s; game: 44 tick(s) over 10 seed(s), longest streak 5 s; tv1: 39 tick(s) over 10 seed(s), longest streak 4 s; tv2: 30 tick(s) over 9 seed(s), longest streak 4 s; tv3: 32 tick(s) over 10 seed(s), longest streak 4 s |
| s3_stress | ACIQ (controller) | bulk: 63 tick(s) over 10 seed(s), longest streak 6 s; game: 81 tick(s) over 10 seed(s), longest streak 9 s; tv1: 75 tick(s) over 10 seed(s), longest streak 8 s; tv2: 63 tick(s) over 9 seed(s), longest streak 8 s; tv3: 67 tick(s) over 10 seed(s), longest streak 7 s |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 3 tick(s) over 10 seed(s), longest streak 1 s; call: 14 tick(s) over 10 seed(s), longest streak 2 s |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 25 tick(s) over 10 seed(s), longest streak 3 s; call: 37 tick(s) over 10 seed(s), longest streak 4 s |
| s7_down_100to15 | ACIQ (controller) | bulk: 51 tick(s) over 10 seed(s), longest streak 6 s; call: 63 tick(s) over 10 seed(s), longest streak 7 s |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 8 tick(s) over 10 seed(s), longest streak 1 s; call: 17 tick(s) over 10 seed(s), longest streak 2 s |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 21 tick(s) over 10 seed(s), longest streak 3 s; call: 38 tick(s) over 10 seed(s), longest streak 4 s |
| s7_down_100to8 | ACIQ (controller) | bulk: 48 tick(s) over 10 seed(s), longest streak 5 s; call: 67 tick(s) over 10 seed(s), longest streak 7 s |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 16 tick(s) over 10 seed(s), longest streak 2 s; call: 23 tick(s) over 10 seed(s), longest streak 3 s |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 33 tick(s) over 10 seed(s), longest streak 4 s; call: 41 tick(s) over 10 seed(s), longest streak 5 s |
| s7_rampup_30to100 | ACIQ (controller) | bulk: 84 tick(s) over 10 seed(s), longest streak 9 s; call: 92 tick(s) over 10 seed(s), longest streak 10 s |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 13 tick(s) over 10 seed(s), longest streak 2 s; call: 21 tick(s) over 10 seed(s), longest streak 3 s |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 29 tick(s) over 10 seed(s), longest streak 3 s; call: 38 tick(s) over 10 seed(s), longest streak 4 s |
| s7_up_20to60 | ACIQ (controller) | bulk: 88 tick(s) over 10 seed(s), longest streak 9 s; call: 98 tick(s) over 10 seed(s), longest streak 11 s |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 11 tick(s) over 10 seed(s), longest streak 2 s; call: 20 tick(s) over 10 seed(s), longest streak 3 s |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 30 tick(s) over 10 seed(s), longest streak 3 s; call: 38 tick(s) over 10 seed(s), longest streak 4 s |
| s7_up_30to100 | ACIQ (controller) | bulk: 81 tick(s) over 10 seed(s), longest streak 9 s; call: 90 tick(s) over 10 seed(s), longest streak 10 s |


## Commit provenance (declared; every run's engine hash)

| scenario | arm | n runs | commit_hash | verdict |
| --- | --- | --- | --- | --- |
| s2b_ramp_100to30 | ACIQ (controller) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s2b_step_10 | ACIQ (controller) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s2b_step_50 | ACIQ (controller) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | ACIQ (controller) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s3_stress | ACIQ (controller) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_down_100to15 | ACIQ (controller) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_down_100to8 | ACIQ (controller) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | ACIQ (controller) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_up_20to60 | ACIQ (controller) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_up_30to100 | ACIQ (controller) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `19e9e8a5e0cc` | current: trusted for a frozen final band claim |

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

