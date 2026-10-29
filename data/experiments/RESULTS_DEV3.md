# Results (generated, no summarised files consulted)

Runs root: `data/runs_dev3` | runs used: 300 | scenarios: s2b_ramp_100to30, s2b_step_10, s2b_step_50, s2b_step_up_20to100, s3_stress, s7_down_100to15, s7_down_100to8, s7_rampup_30to100, s7_up_20to60, s7_up_30to100

Generated from engine commit `753f2840c8ba`. Every section header below stamps the commit(s) of the runs it renders; a frozen final band may ONLY claim PASS/FAIL if every run in it carries this same hash — any mismatch is flagged per band and per scenario, never pooled silently.

## Delay and throughput, every scenario x arm (mean +/- 95% CI over seeds; t(9)=2.262 for n=10)

Every block below carries an explicit band label, derived from the seed family recorded at load time: `POST-FIX` (seeds 200-209, the controller after the redesign commits), `PRE-FIX` (legacy seeds 0-9/42-51), `DEV` and `EVAL` (the task-2 protocol: parameters were fixed on the DEV band seeds 400-409 BEFORE the EVAL band seeds 500-509 was run ONCE; nothing between them was tuned). A reader never inherits a number of unknown provenance: the label sits directly above the table. The comparison sections further down use the primary band only.

Bulk has TWO columns on purpose (TASK 5a): `sender` is what the generator pushed, `receiver/sink` is what the receiver's sink log totalled -- the delivered number, used for any bulk claim. The post-drop column stays on the TREE counters and is named so: the three are different instruments and are never blended.

### s2b_ramp_100to30 (primary band: EVAL (1000-1009))

- commit provenance: `5865fe0d0dc6` — provenance only (pre-round-3 artefact or an older engine): shows nothing about the current engine.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 108.80 +/- 1.93 | 0.76 +/- 0.05 | 0.307 +/- 0.040 | NOT AVAILABLE | 38.01 +/- 0.01 | 37.61 +/- 0.01 | (no drop scenario) | 0.982 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 84.96 +/- 10.42 | 0.85 +/- 0.06 | 0.160 +/- 0.066 | NOT AVAILABLE | 49.14 +/- 0.26 | 48.76 +/- 0.21 | (no drop scenario) | 1.000 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 57.56 +/- 8.21 | 0.79 +/- 0.09 | 0.017 +/- 0.020 | NOT AVAILABLE | 44.08 +/- 0.42 | 43.71 +/- 0.42 | (no drop scenario) | 0.996 +/- 0.001 | NOT AVAILABLE |

### s2b_ramp_100to30 (DEV, seeds 1000-1009)

- commit provenance: `5865fe0d0dc6`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 108.80 +/- 1.93 | 0.76 +/- 0.05 | 0.307 +/- 0.040 | NOT AVAILABLE | 38.01 +/- 0.01 | 37.61 +/- 0.01 | (no drop scenario) | 0.982 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 84.96 +/- 10.42 | 0.85 +/- 0.06 | 0.160 +/- 0.066 | NOT AVAILABLE | 49.14 +/- 0.26 | 48.76 +/- 0.21 | (no drop scenario) | 1.000 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 57.56 +/- 8.21 | 0.79 +/- 0.09 | 0.017 +/- 0.020 | NOT AVAILABLE | 44.08 +/- 0.42 | 43.71 +/- 0.42 | (no drop scenario) | 0.996 +/- 0.001 | NOT AVAILABLE |

### s2b_step_10 (primary band: EVAL (1000-1009))

- commit provenance: `5865fe0d0dc6` — provenance only (pre-round-3 artefact or an older engine): shows nothing about the current engine.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 82.25 +/- 0.63 | 1.22 +/- 0.11 | 1.160 +/- 0.298 | NOT AVAILABLE | 20.11 +/- 0.04 | 19.94 +/- 0.04 | 10.01 +/- 0.04 | 0.846 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 80.57 +/- 0.47 | 1.04 +/- 0.03 | 0.945 +/- 0.288 | NOT AVAILABLE | 29.73 +/- 0.22 | 29.25 +/- 0.22 | 10.07 +/- 0.05 | 0.939 +/- 0.002 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 77.83 +/- 1.20 | 0.97 +/- 0.01 | 0.100 +/- 0.045 | NOT AVAILABLE | 26.86 +/- 0.47 | 26.39 +/- 0.46 | 8.80 +/- 0.07 | 0.917 +/- 0.004 | NOT AVAILABLE |

### s2b_step_10 (DEV, seeds 1000-1009)

- commit provenance: `5865fe0d0dc6`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 82.25 +/- 0.63 | 1.22 +/- 0.11 | 1.160 +/- 0.298 | NOT AVAILABLE | 20.11 +/- 0.04 | 19.94 +/- 0.04 | 10.01 +/- 0.04 | 0.846 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 80.57 +/- 0.47 | 1.04 +/- 0.03 | 0.945 +/- 0.288 | NOT AVAILABLE | 29.73 +/- 0.22 | 29.25 +/- 0.22 | 10.07 +/- 0.05 | 0.939 +/- 0.002 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 77.83 +/- 1.20 | 0.97 +/- 0.01 | 0.100 +/- 0.045 | NOT AVAILABLE | 26.86 +/- 0.47 | 26.39 +/- 0.46 | 8.80 +/- 0.07 | 0.917 +/- 0.004 | NOT AVAILABLE |

### s2b_step_50 (primary band: EVAL (1000-1009))

- commit provenance: `5865fe0d0dc6` — provenance only (pre-round-3 artefact or an older engine): shows nothing about the current engine.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 169.46 +/- 2.31 | 0.55 +/- 0.01 | 0.695 +/- 0.096 | NOT AVAILABLE | 48.29 +/- 0.00 | 47.71 +/- 0.00 | 50.00 +/- 0.00 | 1.000 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 54.21 +/- 10.51 | 0.57 +/- 0.02 | 0.030 +/- 0.056 | NOT AVAILABLE | 56.92 +/- 0.18 | 56.51 +/- 0.16 | 48.02 +/- 0.35 | 0.996 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 26.76 +/- 2.57 | 0.49 +/- 0.02 | 0.025 +/- 0.019 | NOT AVAILABLE | 51.76 +/- 0.72 | 51.52 +/- 0.72 | 45.32 +/- 0.84 | 1.000 +/- 0.000 | NOT AVAILABLE |

### s2b_step_50 (DEV, seeds 1000-1009)

- commit provenance: `5865fe0d0dc6`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 169.46 +/- 2.31 | 0.55 +/- 0.01 | 0.695 +/- 0.096 | NOT AVAILABLE | 48.29 +/- 0.00 | 47.71 +/- 0.00 | 50.00 +/- 0.00 | 1.000 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 54.21 +/- 10.51 | 0.57 +/- 0.02 | 0.030 +/- 0.056 | NOT AVAILABLE | 56.92 +/- 0.18 | 56.51 +/- 0.16 | 48.02 +/- 0.35 | 0.996 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 26.76 +/- 2.57 | 0.49 +/- 0.02 | 0.025 +/- 0.019 | NOT AVAILABLE | 51.76 +/- 0.72 | 51.52 +/- 0.72 | 45.32 +/- 0.84 | 1.000 +/- 0.000 | NOT AVAILABLE |

### s2b_step_up_20to100 (primary band: EVAL (1000-1009))

- commit provenance: `5865fe0d0dc6` — provenance only (pre-round-3 artefact or an older engine): shows nothing about the current engine.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 2.14 +/- 0.10 | 0.63 +/- 0.05 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.47 +/- 0.01 | 9.45 +/- 0.00 | 9.94 +/- 0.02 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 2.18 +/- 0.05 | 0.44 +/- 0.04 | 0.005 +/- 0.011 | NOT AVAILABLE | 15.89 +/- 0.57 | 15.83 +/- 0.57 | 16.22 +/- 0.86 | 0.788 +/- 0.008 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 1.53 +/- 0.02 | 0.26 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 20.34 +/- 0.86 | 20.32 +/- 0.86 | 22.46 +/- 1.08 | 0.849 +/- 0.011 | NOT AVAILABLE |

### s2b_step_up_20to100 (DEV, seeds 1000-1009)

- commit provenance: `5865fe0d0dc6`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 2.14 +/- 0.10 | 0.63 +/- 0.05 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.47 +/- 0.01 | 9.45 +/- 0.00 | 9.94 +/- 0.02 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 2.18 +/- 0.05 | 0.44 +/- 0.04 | 0.005 +/- 0.011 | NOT AVAILABLE | 15.89 +/- 0.57 | 15.83 +/- 0.57 | 16.22 +/- 0.86 | 0.788 +/- 0.008 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 1.53 +/- 0.02 | 0.26 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 20.34 +/- 0.86 | 20.32 +/- 0.86 | 22.46 +/- 1.08 | 0.849 +/- 0.011 | NOT AVAILABLE |

### s3_stress (primary band: EVAL (1000-1009))

- commit provenance: `753f2840c8ba` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.23 +/- 0.16 | 34.39 +/- 1.09 | 34.36 +/- 1.09 | (no drop scenario) | 0.573 +/- 0.015 | 0.979 +/- 0.047 |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 19.89 +/- 1.23 | 65.47 +/- 1.33 | 65.21 +/- 1.33 | (no drop scenario) | 0.457 +/- 0.010 | 0.979 +/- 0.047 |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 37.54 +/- 35.07 | 67.43 +/- 1.58 | 67.10 +/- 1.59 | (no drop scenario) | 0.451 +/- 0.010 | 0.979 +/- 0.047 |

### s3_stress (DEV, seeds 1000-1009)

- commit provenance: `753f2840c8ba`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.23 +/- 0.16 | 34.39 +/- 1.09 | 34.36 +/- 1.09 | (no drop scenario) | 0.573 +/- 0.015 | 0.979 +/- 0.047 |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 19.89 +/- 1.23 | 65.47 +/- 1.33 | 65.21 +/- 1.33 | (no drop scenario) | 0.457 +/- 0.010 | 0.979 +/- 0.047 |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 37.54 +/- 35.07 | 67.43 +/- 1.58 | 67.10 +/- 1.59 | (no drop scenario) | 0.451 +/- 0.010 | 0.979 +/- 0.047 |

### s7_down_100to15 (primary band: EVAL (1000-1009))

- commit provenance: `753f2840c8ba` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 86.81 +/- 0.68 | 0.78 +/- 0.02 | 0.425 +/- 0.078 | NOT AVAILABLE | 23.67 +/- 0.01 | 23.39 +/- 0.01 | 15.02 +/- 0.00 | 0.887 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 83.97 +/- 1.87 | 0.90 +/- 0.09 | 0.365 +/- 0.127 | NOT AVAILABLE | 33.54 +/- 0.60 | 33.11 +/- 0.57 | 14.79 +/- 0.11 | 0.962 +/- 0.003 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 67.29 +/- 11.06 | 0.81 +/- 0.06 | 0.095 +/- 0.088 | NOT AVAILABLE | 30.41 +/- 0.88 | 30.02 +/- 0.88 | 13.89 +/- 0.60 | 0.944 +/- 0.006 | NOT AVAILABLE |

### s7_down_100to15 (DEV, seeds 1000-1009)

- commit provenance: `753f2840c8ba`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 86.81 +/- 0.68 | 0.78 +/- 0.02 | 0.425 +/- 0.078 | NOT AVAILABLE | 23.67 +/- 0.01 | 23.39 +/- 0.01 | 15.02 +/- 0.00 | 0.887 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 83.97 +/- 1.87 | 0.90 +/- 0.09 | 0.365 +/- 0.127 | NOT AVAILABLE | 33.54 +/- 0.60 | 33.11 +/- 0.57 | 14.79 +/- 0.11 | 0.962 +/- 0.003 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 67.29 +/- 11.06 | 0.81 +/- 0.06 | 0.095 +/- 0.088 | NOT AVAILABLE | 30.41 +/- 0.88 | 30.02 +/- 0.88 | 13.89 +/- 0.60 | 0.944 +/- 0.006 | NOT AVAILABLE |

### s7_down_100to8 (primary band: EVAL (1000-1009))

- commit provenance: `753f2840c8ba` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 79.24 +/- 1.05 | 1.32 +/- 0.11 | 0.820 +/- 0.291 | NOT AVAILABLE | 18.68 +/- 0.03 | 18.51 +/- 0.03 | 8.01 +/- 0.01 | 0.828 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 79.61 +/- 0.55 | 1.38 +/- 0.09 | 1.075 +/- 0.215 | NOT AVAILABLE | 28.53 +/- 0.25 | 27.92 +/- 0.24 | 8.11 +/- 0.01 | 0.930 +/- 0.002 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 77.94 +/- 2.11 | 1.21 +/- 0.02 | 0.405 +/- 0.281 | NOT AVAILABLE | 26.50 +/- 0.76 | 25.85 +/- 0.79 | 7.43 +/- 0.30 | 0.913 +/- 0.006 | NOT AVAILABLE |

### s7_down_100to8 (DEV, seeds 1000-1009)

- commit provenance: `753f2840c8ba`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 79.24 +/- 1.05 | 1.32 +/- 0.11 | 0.820 +/- 0.291 | NOT AVAILABLE | 18.68 +/- 0.03 | 18.51 +/- 0.03 | 8.01 +/- 0.01 | 0.828 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 79.61 +/- 0.55 | 1.38 +/- 0.09 | 1.075 +/- 0.215 | NOT AVAILABLE | 28.53 +/- 0.25 | 27.92 +/- 0.24 | 8.11 +/- 0.01 | 0.930 +/- 0.002 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 77.94 +/- 2.11 | 1.21 +/- 0.02 | 0.405 +/- 0.281 | NOT AVAILABLE | 26.50 +/- 0.76 | 25.85 +/- 0.79 | 7.43 +/- 0.30 | 0.913 +/- 0.006 | NOT AVAILABLE |

### s7_rampup_30to100 (primary band: EVAL (1000-1009))

- commit provenance: `753f2840c8ba` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.44 +/- 0.03 | 0.45 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | (no drop scenario) | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.82 +/- 0.18 | 0.36 +/- 0.06 | 0.010 +/- 0.016 | NOT AVAILABLE | 25.21 +/- 0.90 | 25.17 +/- 0.90 | (no drop scenario) | 0.902 +/- 0.009 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 14.78 +/- 3.49 | 0.45 +/- 0.10 | 0.007 +/- 0.010 | NOT AVAILABLE | 49.94 +/- 1.66 | 49.82 +/- 1.64 | (no drop scenario) | 0.999 +/- 0.001 | NOT AVAILABLE |

### s7_rampup_30to100 (DEV, seeds 1000-1009)

- commit provenance: `753f2840c8ba`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.44 +/- 0.03 | 0.45 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | (no drop scenario) | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.82 +/- 0.18 | 0.36 +/- 0.06 | 0.010 +/- 0.016 | NOT AVAILABLE | 25.21 +/- 0.90 | 25.17 +/- 0.90 | (no drop scenario) | 0.902 +/- 0.009 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 14.78 +/- 3.49 | 0.45 +/- 0.10 | 0.007 +/- 0.010 | NOT AVAILABLE | 49.94 +/- 1.66 | 49.82 +/- 1.64 | (no drop scenario) | 0.999 +/- 0.001 | NOT AVAILABLE |

### s7_up_20to60 (primary band: EVAL (1000-1009))

- commit provenance: `210bd09f84be`, `5865fe0d0dc6` — MIXED COMMITS: not one frozen run; do not mix these numbers into a single claim.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 2.08 +/- 0.07 | 0.64 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.46 +/- 0.00 | 9.45 +/- 0.00 | 9.91 +/- 0.01 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 2.29 +/- 0.35 | 0.50 +/- 0.09 | 0.010 +/- 0.011 | NOT AVAILABLE | 16.61 +/- 0.66 | 16.58 +/- 0.66 | 17.48 +/- 0.85 | 0.799 +/- 0.010 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 20.32 +/- 1.96 | 0.54 +/- 0.06 | 0.010 +/- 0.011 | NOT AVAILABLE | 29.60 +/- 0.76 | 29.48 +/- 0.75 | 33.72 +/- 0.89 | 0.938 +/- 0.006 | NOT AVAILABLE |

### s7_up_20to60 (DEV, seeds 1000-1009)

- commit provenance: `210bd09f84be`, `5865fe0d0dc6` — MIXED COMMITS: not one frozen run.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 2.08 +/- 0.07 | 0.64 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.46 +/- 0.00 | 9.45 +/- 0.00 | 9.91 +/- 0.01 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 2.29 +/- 0.35 | 0.50 +/- 0.09 | 0.010 +/- 0.011 | NOT AVAILABLE | 16.61 +/- 0.66 | 16.58 +/- 0.66 | 17.48 +/- 0.85 | 0.799 +/- 0.010 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 20.32 +/- 1.96 | 0.54 +/- 0.06 | 0.010 +/- 0.011 | NOT AVAILABLE | 29.60 +/- 0.76 | 29.48 +/- 0.75 | 33.72 +/- 0.89 | 0.938 +/- 0.006 | NOT AVAILABLE |

### s7_up_30to100 (primary band: EVAL (1000-1009))

- commit provenance: `753f2840c8ba` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.31 +/- 0.02 | 0.43 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | 14.90 +/- 0.00 | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.70 +/- 0.06 | 0.28 +/- 0.02 | 0.007 +/- 0.010 | NOT AVAILABLE | 24.90 +/- 1.20 | 24.85 +/- 1.20 | 26.06 +/- 1.46 | 0.898 +/- 0.011 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 16.86 +/- 0.47 | 0.45 +/- 0.08 | 0.007 +/- 0.010 | NOT AVAILABLE | 49.88 +/- 0.66 | 49.74 +/- 0.65 | 56.46 +/- 1.10 | 1.000 +/- 0.000 | NOT AVAILABLE |

### s7_up_30to100 (DEV, seeds 1000-1009)

- commit provenance: `753f2840c8ba`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.31 +/- 0.02 | 0.43 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | 14.90 +/- 0.00 | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.70 +/- 0.06 | 0.28 +/- 0.02 | 0.007 +/- 0.010 | NOT AVAILABLE | 24.90 +/- 1.20 | 24.85 +/- 1.20 | 26.06 +/- 1.46 | 0.898 +/- 0.011 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 16.86 +/- 0.47 | 0.45 +/- 0.08 | 0.007 +/- 0.010 | NOT AVAILABLE | 49.88 +/- 0.66 | 49.74 +/- 0.65 | 56.46 +/- 1.10 | 1.000 +/- 0.000 | NOT AVAILABLE |

## ACIQ vs every arm (positive % is better ACIQ on the metric at the head of the column; a cell like `41.0x` is the multiplicative factor when the baseline is so close to zero that a percentage would mislead)

| scenario | vs arm | call p95 delta % | CI overlap? | bulk delta % | CI overlap? |
| --- | --- | --- | --- | --- | --- |
Bulk compares are POST-DROP ONLY in scenarios with a capacity drop (same `bulk_mbps` whole-run mean otherwise): the whole-run number dilutes the post-drop regime with a saturated prefix, which is the opposite of the decision those scenarios exist to measure.

| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +47.1 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | +32.3 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +5.4 | disjoint | -12.1 | disjoint |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | +3.4 | disjoint | -12.6 | disjoint |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +84.2 | disjoint | -9.4 | disjoint |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | +50.6 | disjoint | -5.6 | disjoint |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +28.5 | disjoint | +125.9 | disjoint |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | +29.5 | disjoint | +38.4 | disjoint |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +22.5 | disjoint | -7.5 | disjoint |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | +19.9 | disjoint | -6.1 | disjoint |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +1.6 | overlap | -7.2 | disjoint |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | +2.1 | overlap | -8.4 | disjoint |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -929.6 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -711.2 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -875.0 | disjoint | +240.0 | disjoint |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -787.0 | disjoint | +92.9 | disjoint |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -1191.4 | disjoint | +278.9 | disjoint |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -893.2 | disjoint | +116.6 | disjoint |

## Where ACIQ is worse (the honest column)

Every row above where ACIQ's signed delta is negative, collected so a CAKE win cannot hide behind the aggregate. Empty means no such pair exists in the runs found.

| scenario | vs arm | metric where ACIQ is worse |
| --- | --- | --- |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -12.1 |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | post-drop bulk Mbps -12.6 |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -9.4 |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | post-drop bulk Mbps -5.6 |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -7.5 |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | post-drop bulk Mbps -6.1 |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -7.2 |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | post-drop bulk Mbps -8.4 |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -929.6 |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -711.2 |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -875.0 |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -787.0 |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -1191.4 |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -893.2 |

## Where CAKE-static wins

The honest column above lists every rival; this one isolates the set-and-forget rival that matters for the design claim. A CAKE win on a metric is stated here verbatim; nothing is re-derived and nothing is argued away. CI overlap of the underlying seed samples is in the table above (`CI overlap?` column).

| scenario | metric where CAKE-static beats ACIQ | see column in the ACIQ-vs-every table |
| --- | --- | --- |
(none in these runs)

## ACIQ adaptation and capacity accuracy (from the same runs above)

| scenario | n | bind: drop -> first applied <=1.05x post-drop (s) | bind: drop -> first applied <=1.25x post-drop (s) | final estimate | configured end link | estimate error % |
| --- | --- | --- | --- | --- | --- | --- |
| s2b_ramp_100to30 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 26.37 +/- 0.67 | 30.0 +/- 0.0 | mean abs 12.1% (seed0: 26.48/30.0 (11.7% off)) |
| s2b_step_10 | 10 | 8.46 (n=10) | 8.46 (n=10) | 8.67 +/- 0.21 | 10.0 +/- 0.0 | mean abs 13.3% (seed0: 8.66/10.0 (13.4% off)) |
| s2b_step_50 | 10 | 8.90 (n=10) | 3.48 (n=10) | 47.37 +/- 1.86 | 50.0 +/- 0.0 | mean abs 5.6% (seed0: 44.56/50.0 (10.9% off)) |
| s2b_step_up_20to100 | 10 | 2.60 (n=9) | 2.61 (n=10) | 18.44 +/- 1.35 | 100.0 +/- 0.0 | mean abs 81.6% (seed0: 16.82/100.0 (83.2% off)) |
| s3_stress | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 82.70 +/- 3.43 | 100.0 +/- 0.0 | mean abs 17.3% (seed0: 85.19/100.0 (14.8% off)) |
| s7_down_100to15 | 10 | 11.57 (n=10) | 8.99 (n=10) | 14.28 +/- 0.74 | 15.0 +/- 0.0 | mean abs 7.0% (seed0: 15.72/15.0 (4.8% off)) |
| s7_down_100to8 | 10 | 16.31 (n=10) | 15.77 (n=10) | 7.23 +/- 0.67 | 8.0 +/- 0.0 | mean abs 13.6% (seed0: 6.92/8.0 (13.5% off)) |
| s7_rampup_30to100 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 46.07 +/- 1.56 | 100.0 +/- 0.0 | mean abs 53.9% (seed0: 48.04/100.0 (52.0% off)) |
| s7_up_20to60 | 10 | 2.72 (n=10) | 2.72 (n=10) | 28.19 +/- 0.83 | 60.0 +/- 0.0 | mean abs 53.0% (seed0: 29.29/60.0 (51.2% off)) |
| s7_up_30to100 | 10 | 1.65 (n=9) | 1.65 (n=9) | 47.79 +/- 2.99 | 100.0 +/- 0.0 | mean abs 52.2% (seed0: 43.41/100.0 (56.6% off)) |
## Controller resources (ACIQ adaptive runs only; from each result's resources block)

| scenario | n | cpu mean frac | decision p95 ms | decision max ms | max RSS bytes |
| --- | --- | --- | --- | --- | --- |
| s2b_ramp_100to30 | 10 | 0.0094 +/- 0.0006 | 114.27 +/- 11.91 | 221.77 +/- 59.70 | 30185062 +/- 794576 |
| s2b_step_10 | 10 | 0.0076 +/- 0.0002 | 77.98 +/- 5.24 | 92.51 +/- 11.48 | 28942336 +/- 539989 |
| s2b_step_50 | 10 | 0.0078 +/- 0.0001 | 77.01 +/- 2.17 | 106.28 +/- 26.77 | 29025075 +/- 533987 |
| s2b_step_up_20to100 | 10 | 0.0074 +/- 0.0001 | 82.67 +/- 5.68 | 116.50 +/- 30.58 | 28986982 +/- 545896 |
| s3_stress | 10 | 0.0111 +/- 0.0005 | 132.36 +/- 15.12 | 229.82 +/- 69.01 | 29256499 +/- 572387 |
| s7_down_100to15 | 10 | 0.0081 +/- 0.0002 | 83.70 +/- 5.63 | 115.03 +/- 26.88 | 29068493 +/- 530772 |
| s7_down_100to8 | 10 | 0.0095 +/- 0.0003 | 112.03 +/- 8.52 | 206.37 +/- 52.89 | 29035315 +/- 565721 |
| s7_rampup_30to100 | 10 | 0.0084 +/- 0.0002 | 88.69 +/- 4.18 | 142.55 +/- 32.97 | 29926605 +/- 741723 |
| s7_up_20to60 | 10 | 0.0091 +/- 0.0004 | 110.97 +/- 10.06 | 206.30 +/- 39.27 | 29731635 +/- 738199 |
| s7_up_30to100 | 10 | 0.0088 +/- 0.0008 | 98.63 +/- 15.48 | 194.67 +/- 83.80 | 30119936 +/- 777420 |
- CPU context (adaptive vs adaptive): CAKE-adaptive runs at 0.47x the ACIQ CPU fraction on the shared scenario(s): s2b_ramp_100to30 0.49x, s2b_step_10 0.52x, s2b_step_50 0.48x, s2b_step_up_20to100 0.49x, s3_stress 0.43x, s7_down_100to15 0.56x, s7_down_100to8 0.45x, s7_rampup_30to100 0.47x, s7_up_20to60 0.38x, s7_up_30to100 0.44x. The cause must be read from the artifacts (CPU profile, decision cadence), not assumed.

## Fairness detail (workload-rate Jain; per-class minima over ASSIGNED classes only, same scope for every mode)

| scenario | arm | n | jain mean +/- CI | demand-jain mean +/- CI | flows used | min over time (per label, via carrying class) |
| --- | --- | --- | --- | --- | --- | --- |
demand-jain: Jain over per-flow satisfied-demand ratios (achieved/demand, demand self-reported by the generator; elastic flows without a declared demand are excluded by definition -- see aciq/fairness.py). A scenario flows all-elastic has no such index and prints NOT AVAILABLE rather than a substitute.

Per-tick counter attribution (fix 18): ACIQ's tree has one leaf per class; the baselines' single-class tree carries the WHOLE link on the 1:50 leaf. New artefacts sample that aggregate under `unknown` (an aggregate can no longer masquerade as a software_update class); artefacts from before this change stored the same aggregate under `software_update`, and consumers that fall back to the legacy label must name it -- the post-drop bulk column does exactly that.

| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.982 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=29.8; call via unknown=29.8 |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.000 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=27.5; call via unknown=27.5; bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=29.9; call via unknown=29.9 |
| s2b_ramp_100to30 | ACIQ (controller) | 10 | 0.996 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.846 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.97; call via unknown=9.97; bulk via unknown=9.96; call via unknown=9.96 |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.939 +/- 0.002 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.98; call via unknown=9.98 |
| s2b_step_10 | ACIQ (controller) | 10 | 0.917 +/- 0.004 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.000 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=49.9; call via unknown=49.9; bulk via unknown=50; call via unknown=50; bulk via unknown=50; call via unknown=50 |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.996 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=45.6; call via unknown=45.6; bulk via unknown=45.6; call via unknown=45.6; bulk via unknown=45.6; call via unknown=45.6 |
| s2b_step_50 | ACIQ (controller) | 10 | 1.000 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.683 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.93; call via unknown=9.93; bulk via unknown=9.99; call via unknown=9.99; bulk via unknown=9.94; call via unknown=9.94 |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.788 +/- 0.008 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=16.6; call via unknown=16.6; bulk via unknown=15.4; call via unknown=15.4; bulk via unknown=16.6; call via unknown=16.6 |
| s2b_step_up_20to100 | ACIQ (controller) | 10 | 0.849 +/- 0.011 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.573 +/- 0.015 | 0.979 +/- 0.047 | 5.0 +/- 0.0 | bulk via unknown=49.6; game via unknown=49.6; tv1 via unknown=49.6; tv2 via unknown=49.6; tv3 via unknown=49.6; bulk via unknown=49.3 |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.457 +/- 0.010 | 0.979 +/- 0.047 | 5.0 +/- 0.0 | bulk via unknown=70.9; game via unknown=70.9; tv1 via unknown=70.9; tv2 via unknown=70.9; tv3 via unknown=70.9; bulk via unknown=69.8 |
| s3_stress | ACIQ (controller) | 10 | 0.451 +/- 0.010 | 0.979 +/- 0.047 | 5.0 +/- 0.0 | bulk=0; game via unknown=0; tv1 via unknown=0; tv2 via unknown=0; tv3 via unknown=0; bulk=0 |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.887 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15 |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.962 +/- 0.003 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=13.5; call via unknown=13.5; bulk via unknown=13.9; call via unknown=13.9; bulk via unknown=13.1; call via unknown=13.1 |
| s7_down_100to15 | ACIQ (controller) | 10 | 0.944 +/- 0.006 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.828 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=7.98; call via unknown=7.98; bulk via unknown=7.97; call via unknown=7.97; bulk via unknown=7.96; call via unknown=7.96 |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.930 +/- 0.002 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=7.98; call via unknown=7.98; bulk via unknown=7.95; call via unknown=7.95; bulk via unknown=7.96; call via unknown=7.96 |
| s7_down_100to8 | ACIQ (controller) | 10 | 0.913 +/- 0.006 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.764 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15; call via unknown=15; bulk via unknown=14.6; call via unknown=14.6; bulk via unknown=15; call via unknown=15 |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.902 +/- 0.009 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=25.1; call via unknown=25.1; bulk via unknown=24.9; call via unknown=24.9; bulk via unknown=22.9; call via unknown=22.9 |
| s7_rampup_30to100 | ACIQ (controller) | 10 | 0.999 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.683 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.94; call via unknown=9.94; bulk via unknown=9.89; call via unknown=9.89; bulk via unknown=9.97; call via unknown=9.97 |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.799 +/- 0.010 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15.2; call via unknown=15.2; bulk via unknown=15.3; call via unknown=15.3; bulk via unknown=16.2; call via unknown=16.2 |
| s7_up_20to60 | ACIQ (controller) | 10 | 0.938 +/- 0.006 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.764 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15; call via unknown=15; bulk via unknown=14.8; call via unknown=14.8; bulk via unknown=14.7; call via unknown=14.7 |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.898 +/- 0.011 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=24; call via unknown=24; bulk via unknown=25; call via unknown=25; bulk via unknown=22.5; call via unknown=22.5 |
| s7_up_30to100 | ACIQ (controller) | 10 | 1.000 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |

Starvation (TASK 5b, fixed basis): per LABEL, over the class the data says carried the traffic (assigned class, or the router's `unknown`/legacy aggregate when the label's traffic rode there -- chosen by highest mean, and the carrying class is named). A label starved in tick t if its per-tick goodput fell below 20% of its REGIME median -- in a drop scenario the median is the POST-DROP regime's own median, so the shaped link rate can never masquerade as starvation; without a drop it is the whole window's. The cell lists the starved timestamps counted over seeds. With no series at all the cell prints NOT AVAILABLE, never an empty claim.

| scenario | arm | starved ticks per label (via carrying class) |
| --- | --- | --- |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_ramp_100to30 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 315 ticks over 10 seed(s), first t=5.3 |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_10 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 202 ticks over 10 seed(s), first t=5.3 |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 195 ticks over 10 seed(s), first t=5.4 |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 196 ticks over 10 seed(s), first t=5.3 |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 49 seed x label series (regime-aware threshold, declared window) |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 49 seed x label series (regime-aware threshold, declared window) |
| s3_stress | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.2; game via unknown: 86 ticks over 10 seed(s), first t=19.8; tv1 via adaptive_video_streaming: 6 ticks over 1 seed(s), first t=2.1; tv1 via unknown: 76 ticks over 9 seed(s), first t=19.8; tv2 via adaptive_video_streaming: 6 ticks over 1 seed(s), first t=2.1; tv2 via unknown: 67 ticks over 8 seed(s), first t=19.8; tv3 via adaptive_video_streaming: 6 ticks over 1 seed(s), first t=2.1; tv3 via unknown: 76 ticks over 9 seed(s), first t=19.8 |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to15 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 190 ticks over 10 seed(s), first t=5.3 |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to8 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 186 ticks over 10 seed(s), first t=5.4 |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_rampup_30to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 301 ticks over 10 seed(s), first t=5.3 |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_20to60 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.2; call via unknown: 299 ticks over 10 seed(s), first t=5.5 |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_30to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 289 ticks over 10 seed(s), first t=5.3 |

Warm-up exclusion (declared): every per-tick window above starts at t >= 2.0 s. The diagnosis round (fix 17's diagnosis.md) shows the first ~2 s of per-tick counter rates are a transmit/counter ramp artefact, not traffic behaviour; dropping those ticks removes nothing else. The window boundary is a declared constant in this generator, not a per-run choice.

Further declared exclusions (TASK 5b): (1) ticks at or beyond the label generator's own measured lifetime (`elapsed_s`, capped by the scenario duration) -- a verdict about a label after its traffic stopped describes nothing about the label; (2) ticks whose link counters went BACKWARDS -- a qdisc del/re-add resets every counter on the device, so that tick's per-class goodput is a reset artefact, not a delivery gap. Stars and minima are computed over what remains; nothing is excluded silently.

## Step/demand generalization band (evaluation-only; docs/evidence/s2b-params.md + docs/evidence/round3-params.md, declared BEFORE these runs)

The shipped controller runs unchanged on capacity changes it was never tuned on: two down-step magnitudes, a 5x up-step, and a continuous 20 s ramp -- plus the round-3 DEV shapes (s7_* up/down steps and ramps, s3_stress) and the two queue-discipline-only arms (CAKE-conservative / CAKE-adaptive). Seeds 800-809 configured per scenario (the DEV band, seed names in each run dir). CAKE-static is applied once at launch and never re-applied: that is its declared semantics, and this band exists to surface the consequences. Definitions: bind = first tick at which the applied tree sits within 10% of the link's truth and stays there (down-moves only; up-moves print `n/a (up-step)` and are judged by the utilization column: applied/truth and receiver delivered/truth over the final third); tracking error = mean |applied - truth| over the ramp window; estimate error = same over the final third. Where ACIQ fails, the row says so.

Engine commit at generation time: `753f2840c8ba` — a run whose result carries a different commit_hash is SUPERSEDED, listed under 'commit provenance' below and never pooled into a numeric cell with a newer commit.

### s2b_step_50

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 50.00 +/- 0.00 | 169.46 +/- 2.31 | 47.66 +/- 0.11 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 50.00 +/- 0.00 | 54.21 +/- 10.51 | 45.42 +/- 1.17 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 40.5 +/- 1.9 | 9.36 +/- 1.42 | 26.76 +/- 2.57 | 37.75 +/- 1.65 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 53.1 vs truth 50.0, 6% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 45.3 vs truth 50.0, 9% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 52.7 vs truth 50.0, 5% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 53.5 vs truth 50.0, 7% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 44.6 vs truth 50.0, 11% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 65.3 vs truth 50.0, 31% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 49.1 vs truth 50.0, 2% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 53.0 vs truth 50.0, 6% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 53.3 vs truth 50.0, 7% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 52.8 vs truth 50.0, 6% off truth, confidence 0.40 |

### s2b_step_10

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 90.00 +/- 0.00 | 82.25 +/- 0.63 | 9.45 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 90.00 +/- 0.00 | 80.57 +/- 0.47 | 9.34 +/- 0.12 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 37.6 +/- 1.0 | 1.14 +/- 0.14 | 77.83 +/- 1.20 | 7.00 +/- 0.18 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.2 vs truth 10.0, 18% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 11.0 vs truth 10.0, 10% off truth, confidence 0.55 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 10.9 vs truth 10.0, 9% off truth, confidence 0.35; final tick: UNSATURATED (estimator not saturated at the end regime), applied 12.9 vs truth 10.0, 29% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.2 vs truth 10.0, 18% off truth, confidence 0.55 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 11.0 vs truth 10.0, 10% off truth, confidence 0.35; final tick: UNSATURATED (estimator not saturated at the end regime), applied 10.5 vs truth 10.0, 5% off truth, confidence 0.50; final tick: UNSATURATED (estimator not saturated at the end regime), applied 7.9 vs truth 10.0, 21% off truth, confidence 0.55 |

### s2b_step_up_20to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 80.00 +/- 0.00 | 2.14 +/- 0.10 | 9.34 +/- 0.10 | appl 0.20 +/- 0.00 / delv 0.09 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 80.00 +/- 0.00 | 2.18 +/- 0.05 | 15.59 +/- 0.81 | appl 0.20 +/- 0.00 / delv 0.16 +/- 0.01 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 60.40 +/- 2.35 | 1.53 +/- 0.02 | 25.95 +/- 1.37 | appl 0.40 +/- 0.02 / delv 0.26 +/- 0.01 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 51.9 vs truth 100.0, 48% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 34.8 vs truth 100.0, 65% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 34.7 vs truth 100.0, 65% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 38.8 vs truth 100.0, 61% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 51.8 vs truth 100.0, 48% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 34.6 vs truth 100.0, 65% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 27.6 vs truth 100.0, 72% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 34.5 vs truth 100.0, 66% off truth, confidence 0.00 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 35.1 vs truth 100.0, 65% off truth, confidence 0.00 |

### s2b_ramp_100to30

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 108.80 +/- 1.93 | 28.54 +/- 0.06 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 84.96 +/- 10.42 | 27.12 +/- 0.70 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 3.43 +/- 0.47 | 57.56 +/- 8.21 | 18.70 +/- 0.51 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 23.8 vs truth 30.0, 21% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 24.2 vs truth 30.0, 19% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 24.5 vs truth 30.0, 18% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 22.4 vs truth 30.0, 25% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 23.6 vs truth 30.0, 21% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 22.7 vs truth 30.0, 24% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 23.6 vs truth 30.0, 21% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 25.0 vs truth 30.0, 17% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 24.5 vs truth 30.0, 18% off truth, confidence 0.05; final tick: UNSATURATED (estimator not saturated at the end regime), applied 23.0 vs truth 30.0, 23% off truth, confidence 0.00 |

### s7_up_20to60

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 40.00 +/- 0.00 | 2.08 +/- 0.07 | 9.37 +/- 0.09 | appl 0.33 +/- 0.00 / delv 0.16 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 40.00 +/- 0.00 | 2.29 +/- 0.35 | 16.11 +/- 0.89 | appl 0.33 +/- 0.00 / delv 0.27 +/- 0.01 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 12.44 +/- 1.44 | 20.32 +/- 1.96 | 39.47 +/- 1.12 | appl 0.93 +/- 0.06 / delv 0.66 +/- 0.02 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 32.7 vs truth 60.0, 45% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 31.1 vs truth 60.0, 48% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 46.2 vs truth 60.0, 23% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 30.5 vs truth 60.0, 49% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 30.7 vs truth 60.0, 49% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 30.3 vs truth 60.0, 50% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 45.7 vs truth 60.0, 24% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 31.2 vs truth 60.0, 48% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 30.4 vs truth 60.0, 49% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 44.7 vs truth 60.0, 26% off truth, confidence 0.00 |

### s7_up_30to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 70.00 +/- 0.00 | 1.31 +/- 0.02 | 14.15 +/- 0.09 | appl 0.30 +/- 0.00 / delv 0.14 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 70.00 +/- 0.00 | 1.70 +/- 0.06 | 24.67 +/- 1.84 | appl 0.30 +/- 0.00 / delv 0.25 +/- 0.02 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 19.44 +/- 3.68 | 16.86 +/- 0.47 | 69.18 +/- 3.71 | appl 1.04 +/- 0.08 / delv 0.69 +/- 0.04 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 75.3 vs truth 100.0, 25% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 76.3 vs truth 100.0, 24% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 73.2 vs truth 100.0, 27% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 76.4 vs truth 100.0, 24% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 80.9 vs truth 100.0, 19% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 38.6 vs truth 100.0, 61% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 77.9 vs truth 100.0, 22% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 81.0 vs truth 100.0, 19% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 73.5 vs truth 100.0, 26% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 79.4 vs truth 100.0, 21% off truth, confidence 0.25 |

### s7_rampup_30to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 1.44 +/- 0.03 | 14.23 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 1.82 +/- 0.18 | 24.69 +/- 1.27 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 17.94 +/- 2.16 | 14.78 +/- 3.49 | 67.25 +/- 3.40 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 76.0 vs truth 100.0, 24% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 64.2 vs truth 100.0, 36% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 73.1 vs truth 100.0, 27% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 81.3 vs truth 100.0, 19% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 75.2 vs truth 100.0, 25% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 76.1 vs truth 100.0, 24% off truth, confidence 0.25 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 56.2 vs truth 100.0, 44% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 55.8 vs truth 100.0, 44% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 64.8 vs truth 100.0, 35% off truth, confidence 0.00 |

### s7_down_100to15

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 85.00 +/- 0.00 | 86.81 +/- 0.68 | 14.20 +/- 0.06 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 85.00 +/- 0.00 | 83.97 +/- 1.87 | 13.31 +/- 0.24 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 39.7 +/- 1.5 | 3.07 +/- 1.10 | 67.29 +/- 11.06 | 11.98 +/- 0.76 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.2 vs truth 15.0, 6% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 15.0, 7% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 13.2 vs truth 15.0, 12% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.3 vs truth 15.0, 4% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 11.8 vs truth 15.0, 22% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 12.5 vs truth 15.0, 17% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 15.0, 7% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 12.8 vs truth 15.0, 14% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 12.6 vs truth 15.0, 16% off truth, confidence 0.55 (n=2) |

### s7_down_100to8

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 92.00 +/- 0.00 | 79.24 +/- 1.05 | 7.52 +/- 0.03 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 92.00 +/- 0.00 | 79.61 +/- 0.55 | 7.52 +/- 0.06 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 40.4 +/- 0.5 | 2.14 +/- 1.76 | 77.94 +/- 2.11 | 5.55 +/- 0.41 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 6.5 vs truth 8.0, 19% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.2 vs truth 8.0, 3% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.2 vs truth 8.0, 3% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 6.8 vs truth 8.0, 15% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 7.9 vs truth 8.0, 2% off truth, confidence 0.40 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.0 vs truth 8.0, 1% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 6.8 vs truth 8.0, 15% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.3 vs truth 8.0, 3% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 7.9 vs truth 8.0, 2% off truth, confidence 0.10 |

### s3_stress

| arm | n | call p95 whole-run (ms) | game p95 whole-run (ms) | bulk receiver mean inst (Mbps) | tv1 / tv2 / tv3 receiver mean inst (Mbps) | overload note (loaded vs capacity) |
| --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE | 2.23 +/- 0.16 | 31.77 +/- 0.94 | 4.38 / 4.39 / 4.39; 4.43 / 4.39; 4.39 / 4.39 / 4.39; 4.39 / 4.39 / 4.38; 4.48 / 4.48 / 4.49; 4.50 / 4.49 / 4.39; 4.60 / 4.60 / 4.60; 4.59 / 4.59 / 4.49; 4.38 / 4.38 / 4.38; 4.48 / 4.48 / 4.48 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE | 19.89 +/- 1.23 | 58.98 +/- 1.13 | 4.29 / 4.29 / 4.29; 4.32 / 4.29; 4.27 / 4.28 / 4.29; 4.30 / 4.30 / 4.29; 4.38 / 4.38 / 4.38; 4.29 / 4.29 / 4.29; 4.49 / 4.48 / 4.49; 4.37 / 4.48 / 4.37; 4.29 / 4.29 / 4.28; 4.38 / 4.38 / 4.38 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |
| ACIQ (controller) | 10 | NOT AVAILABLE | 37.54 +/- 35.07 | 57.15 +/- 1.51 | 3.86 / 3.90 / 3.87; 4.12 / 4.09; 4.02 / 4.01 / 4.01; 4.02 / 4.02 / 4.02; 4.10 / 4.10 / 4.10; 4.10 / 4.10 / 4.10; 4.19 / 4.20 / 4.18; 4.20 / 4.19 / 4.19; 4.02 / 4.01 / 4.02; 4.20 / 4.20 / 4.20 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |

## Starvation, receiver side (every arm, per-second sink logs)

| scenario | arm | label; starved inst ticks over seeds (longest streak) |
| --- | --- | --- |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 6 tick(s) over 10 seed(s), longest streak 1 s; call: 16 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 16 tick(s) over 10 seed(s), longest streak 2 s; call: 29 tick(s) over 10 seed(s), longest streak 3 s |
| s2b_ramp_100to30 | ACIQ (controller) | bulk: 47 tick(s) over 10 seed(s), longest streak 6 s; call: 59 tick(s) over 10 seed(s), longest streak 7 s |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 3 tick(s) over 10 seed(s), longest streak 1 s; call: 11 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 6 tick(s) over 10 seed(s), longest streak 1 s; call: 17 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_10 | ACIQ (controller) | bulk: 19 tick(s) over 10 seed(s), longest streak 2 s; call: 32 tick(s) over 10 seed(s), longest streak 4 s |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 11 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 8 tick(s) over 10 seed(s), longest streak 1 s; call: 17 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_50 | ACIQ (controller) | bulk: 27 tick(s) over 10 seed(s), longest streak 3 s; call: 35 tick(s) over 10 seed(s), longest streak 4 s |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 4 tick(s) over 10 seed(s), longest streak 1 s; call: 12 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 9 tick(s) over 10 seed(s), longest streak 1 s; call: 17 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_up_20to100 | ACIQ (controller) | bulk: 26 tick(s) over 10 seed(s), longest streak 3 s; call: 34 tick(s) over 10 seed(s), longest streak 4 s |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 7 tick(s) over 10 seed(s), longest streak 1 s; game: 26 tick(s) over 10 seed(s), longest streak 4 s; tv1: 22 tick(s) over 10 seed(s), longest streak 3 s; tv2: 14 tick(s) over 9 seed(s), longest streak 2 s; tv3: 15 tick(s) over 10 seed(s), longest streak 2 s |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 18 tick(s) over 10 seed(s), longest streak 2 s; game: 37 tick(s) over 10 seed(s), longest streak 4 s; tv1: 34 tick(s) over 10 seed(s), longest streak 4 s; tv2: 23 tick(s) over 9 seed(s), longest streak 3 s; tv3: 25 tick(s) over 10 seed(s), longest streak 3 s |
| s3_stress | ACIQ (controller) | bulk: 45 tick(s) over 10 seed(s), longest streak 5 s; game: 64 tick(s) over 10 seed(s), longest streak 8 s; tv1: 55 tick(s) over 9 seed(s), longest streak 8 s; tv2: 55 tick(s) over 10 seed(s), longest streak 7 s; tv3: 53 tick(s) over 10 seed(s), longest streak 6 s |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 12 tick(s) over 10 seed(s), longest streak 2 s |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 10 tick(s) over 10 seed(s), longest streak 1 s; call: 21 tick(s) over 10 seed(s), longest streak 3 s |
| s7_down_100to15 | ACIQ (controller) | bulk: 23 tick(s) over 10 seed(s), longest streak 4 s; call: 35 tick(s) over 10 seed(s), longest streak 5 s |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 2 tick(s) over 10 seed(s), longest streak 1 s; call: 10 tick(s) over 10 seed(s), longest streak 2 s |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 4 tick(s) over 10 seed(s), longest streak 1 s; call: 19 tick(s) over 10 seed(s), longest streak 3 s |
| s7_down_100to8 | ACIQ (controller) | bulk: 26 tick(s) over 10 seed(s), longest streak 3 s; call: 42 tick(s) over 10 seed(s), longest streak 5 s |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 7 tick(s) over 10 seed(s), longest streak 1 s; call: 13 tick(s) over 10 seed(s), longest streak 2 s |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 17 tick(s) over 10 seed(s), longest streak 2 s; call: 23 tick(s) over 10 seed(s), longest streak 3 s |
| s7_rampup_30to100 | ACIQ (controller) | bulk: 47 tick(s) over 10 seed(s), longest streak 6 s; call: 55 tick(s) over 10 seed(s), longest streak 6 s |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 7 tick(s) over 10 seed(s), longest streak 1 s; call: 15 tick(s) over 10 seed(s), longest streak 2 s |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 16 tick(s) over 10 seed(s), longest streak 3 s; call: 25 tick(s) over 10 seed(s), longest streak 3 s |
| s7_up_20to60 | ACIQ (controller) | bulk: 49 tick(s) over 10 seed(s), longest streak 6 s; call: 58 tick(s) over 10 seed(s), longest streak 6 s |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 3 tick(s) over 10 seed(s), longest streak 1 s; call: 12 tick(s) over 10 seed(s), longest streak 2 s |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 12 tick(s) over 10 seed(s), longest streak 2 s; call: 20 tick(s) over 10 seed(s), longest streak 3 s |
| s7_up_30to100 | ACIQ (controller) | bulk: 45 tick(s) over 10 seed(s), longest streak 5 s; call: 54 tick(s) over 10 seed(s), longest streak 6 s |


## Commit provenance (declared; every run's engine hash)

| scenario | arm | n runs | commit_hash | verdict |
| --- | --- | --- | --- | --- |
| s2b_ramp_100to30 | ACIQ (controller) | 10 | `5865fe0d0dc6` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `5865fe0d0dc6` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `5865fe0d0dc6` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s2b_step_10 | ACIQ (controller) | 10 | `5865fe0d0dc6` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `5865fe0d0dc6` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `5865fe0d0dc6` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s2b_step_50 | ACIQ (controller) | 10 | `5865fe0d0dc6` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `5865fe0d0dc6` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `5865fe0d0dc6` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s2b_step_up_20to100 | ACIQ (controller) | 10 | `5865fe0d0dc6` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `5865fe0d0dc6` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `5865fe0d0dc6` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s3_stress | ACIQ (controller) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |
| s7_down_100to15 | ACIQ (controller) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |
| s7_down_100to8 | ACIQ (controller) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | ACIQ (controller) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |
| s7_up_20to60 | ACIQ (controller) | 10 | `5865fe0d0dc6` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `210bd09f84be` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `5865fe0d0dc6` | SUPERSEDED: different engine commit than this report; keep its numbers visibly apart (never mixed into one claim with a current run) |
| s7_up_30to100 | ACIQ (controller) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `753f2840c8ba` | current: trusted for a frozen final band claim |

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

