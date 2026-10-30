# Results (generated, no summarised files consulted)

Runs root: `data/runs_dev3` | runs used: 300 | scenarios: s2b_ramp_100to30, s2b_step_10, s2b_step_50, s2b_step_up_20to100, s3_stress, s7_down_100to15, s7_down_100to8, s7_rampup_30to100, s7_up_20to60, s7_up_30to100

Generated from engine commit `fdfd2cf62a1a`. Every section header below stamps the commit(s) of the runs it renders; a frozen final band may ONLY claim PASS/FAIL if every run in it carries this same hash — any mismatch is flagged per band and per scenario, never pooled silently.

## Delay and throughput, every scenario x arm (mean +/- 95% CI over seeds; t(9)=2.262 for n=10)

Every block below carries an explicit band label, derived from the seed family recorded at load time: `POST-FIX` (seeds 200-209, the controller after the redesign commits), `PRE-FIX` (legacy seeds 0-9/42-51), `DEV` and `EVAL` (the task-2 protocol: parameters were fixed on the DEV band seeds 400-409 BEFORE the EVAL band seeds 500-509 was run ONCE; nothing between them was tuned). A reader never inherits a number of unknown provenance: the label sits directly above the table. The comparison sections further down use the primary band only.

Bulk has TWO columns on purpose (TASK 5a): `sender` is what the generator pushed, `receiver/sink` is what the receiver's sink log totalled -- the delivered number, used for any bulk claim. The post-drop column stays on the TREE counters and is named so: the three are different instruments and are never blended.

### s2b_ramp_100to30 (primary band: EVAL (1000-1009))

- commit provenance: `fdfd2cf62a1a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 110.55 +/- 2.71 | 0.68 +/- 0.03 | 0.307 +/- 0.050 | NOT AVAILABLE | 38.02 +/- 0.00 | 37.62 +/- 0.00 | (no drop scenario) | 0.982 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 25.93 +/- 2.22 | 0.65 +/- 0.07 | 0.100 +/- 0.077 | NOT AVAILABLE | 47.91 +/- 0.81 | 47.58 +/- 0.78 | (no drop scenario) | 0.999 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 33.93 +/- 4.15 | 0.55 +/- 0.03 | 0.007 +/- 0.010 | NOT AVAILABLE | 45.77 +/- 0.99 | 45.47 +/- 0.98 | (no drop scenario) | 0.998 +/- 0.001 | NOT AVAILABLE |

### s2b_ramp_100to30 (DEV, seeds 1000-1009)

- commit provenance: `fdfd2cf62a1a`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 110.55 +/- 2.71 | 0.68 +/- 0.03 | 0.307 +/- 0.050 | NOT AVAILABLE | 38.02 +/- 0.00 | 37.62 +/- 0.00 | (no drop scenario) | 0.982 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 25.93 +/- 2.22 | 0.65 +/- 0.07 | 0.100 +/- 0.077 | NOT AVAILABLE | 47.91 +/- 0.81 | 47.58 +/- 0.78 | (no drop scenario) | 0.999 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 33.93 +/- 4.15 | 0.55 +/- 0.03 | 0.007 +/- 0.010 | NOT AVAILABLE | 45.77 +/- 0.99 | 45.47 +/- 0.98 | (no drop scenario) | 0.998 +/- 0.001 | NOT AVAILABLE |

### s2b_step_10 (primary band: EVAL (1000-1009))

- commit provenance: `fdfd2cf62a1a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 82.56 +/- 0.57 | 1.06 +/- 0.03 | 1.100 +/- 0.241 | NOT AVAILABLE | 20.11 +/- 0.01 | 19.93 +/- 0.02 | 10.02 +/- 0.00 | 0.846 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 73.03 +/- 1.51 | 1.00 +/- 0.02 | 0.445 +/- 0.110 | NOT AVAILABLE | 29.42 +/- 0.45 | 28.93 +/- 0.44 | 0.88 +/- 1.09 | 0.937 +/- 0.003 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 75.40 +/- 1.95 | 0.96 +/- 0.02 | 0.080 +/- 0.045 | NOT AVAILABLE | 27.94 +/- 0.73 | 27.32 +/- 0.72 | 8.46 +/- 0.14 | 0.926 +/- 0.006 | NOT AVAILABLE |

### s2b_step_10 (DEV, seeds 1000-1009)

- commit provenance: `fdfd2cf62a1a`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 82.56 +/- 0.57 | 1.06 +/- 0.03 | 1.100 +/- 0.241 | NOT AVAILABLE | 20.11 +/- 0.01 | 19.93 +/- 0.02 | 10.02 +/- 0.00 | 0.846 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 73.03 +/- 1.51 | 1.00 +/- 0.02 | 0.445 +/- 0.110 | NOT AVAILABLE | 29.42 +/- 0.45 | 28.93 +/- 0.44 | 0.88 +/- 1.09 | 0.937 +/- 0.003 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 75.40 +/- 1.95 | 0.96 +/- 0.02 | 0.080 +/- 0.045 | NOT AVAILABLE | 27.94 +/- 0.73 | 27.32 +/- 0.72 | 8.46 +/- 0.14 | 0.926 +/- 0.006 | NOT AVAILABLE |

### s2b_step_50 (primary band: EVAL (1000-1009))

- commit provenance: `fdfd2cf62a1a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 167.74 +/- 1.67 | 0.55 +/- 0.01 | 0.750 +/- 0.100 | NOT AVAILABLE | 48.30 +/- 0.00 | 47.71 +/- 0.00 | 50.00 +/- 0.00 | 1.000 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 10.60 +/- 2.59 | 0.48 +/- 0.01 | 0.090 +/- 0.053 | NOT AVAILABLE | 51.78 +/- 1.24 | 51.49 +/- 1.27 | 38.72 +/- 9.92 | 0.999 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 7.12 +/- 3.44 | 0.43 +/- 0.01 | 0.005 +/- 0.011 | NOT AVAILABLE | 50.73 +/- 1.25 | 50.50 +/- 1.26 | 41.72 +/- 1.31 | 1.000 +/- 0.000 | NOT AVAILABLE |

### s2b_step_50 (DEV, seeds 1000-1009)

- commit provenance: `fdfd2cf62a1a`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 167.74 +/- 1.67 | 0.55 +/- 0.01 | 0.750 +/- 0.100 | NOT AVAILABLE | 48.30 +/- 0.00 | 47.71 +/- 0.00 | 50.00 +/- 0.00 | 1.000 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 10.60 +/- 2.59 | 0.48 +/- 0.01 | 0.090 +/- 0.053 | NOT AVAILABLE | 51.78 +/- 1.24 | 51.49 +/- 1.27 | 38.72 +/- 9.92 | 0.999 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 7.12 +/- 3.44 | 0.43 +/- 0.01 | 0.005 +/- 0.011 | NOT AVAILABLE | 50.73 +/- 1.25 | 50.50 +/- 1.26 | 41.72 +/- 1.31 | 1.000 +/- 0.000 | NOT AVAILABLE |

### s2b_step_up_20to100 (primary band: EVAL (1000-1009))

- commit provenance: `fdfd2cf62a1a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.79 +/- 0.02 | 0.58 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.46 +/- 0.01 | 9.45 +/- 0.00 | 9.94 +/- 0.01 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.93 +/- 0.05 | 0.35 +/- 0.05 | 0.003 +/- 0.007 | NOT AVAILABLE | 15.87 +/- 0.71 | 15.84 +/- 0.72 | 16.57 +/- 0.94 | 0.788 +/- 0.011 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 1.80 +/- 0.28 | 0.30 +/- 0.02 | 0.010 +/- 0.011 | NOT AVAILABLE | 39.69 +/- 4.19 | 39.64 +/- 4.18 | 45.93 +/- 4.15 | 0.981 +/- 0.013 | NOT AVAILABLE |

### s2b_step_up_20to100 (DEV, seeds 1000-1009)

- commit provenance: `fdfd2cf62a1a`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.79 +/- 0.02 | 0.58 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.46 +/- 0.01 | 9.45 +/- 0.00 | 9.94 +/- 0.01 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.93 +/- 0.05 | 0.35 +/- 0.05 | 0.003 +/- 0.007 | NOT AVAILABLE | 15.87 +/- 0.71 | 15.84 +/- 0.72 | 16.57 +/- 0.94 | 0.788 +/- 0.011 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 1.80 +/- 0.28 | 0.30 +/- 0.02 | 0.010 +/- 0.011 | NOT AVAILABLE | 39.69 +/- 4.19 | 39.64 +/- 4.18 | 45.93 +/- 4.15 | 0.981 +/- 0.013 | NOT AVAILABLE |

### s3_stress (primary band: EVAL (1000-1009))

- commit provenance: `fdfd2cf62a1a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.03 +/- 0.32 | 34.39 +/- 1.10 | 34.36 +/- 1.10 | (no drop scenario) | 0.573 +/- 0.016 | 0.979 +/- 0.047 |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 9.21 +/- 7.05 | 62.70 +/- 3.40 | 62.57 +/- 3.36 | (no drop scenario) | 0.467 +/- 0.016 | 0.979 +/- 0.047 |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 15.47 +/- 4.28 | 64.99 +/- 2.91 | 64.73 +/- 2.91 | (no drop scenario) | 0.459 +/- 0.010 | 0.979 +/- 0.047 |

### s3_stress (DEV, seeds 1000-1009)

- commit provenance: `fdfd2cf62a1a`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.03 +/- 0.32 | 34.39 +/- 1.10 | 34.36 +/- 1.10 | (no drop scenario) | 0.573 +/- 0.016 | 0.979 +/- 0.047 |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 9.21 +/- 7.05 | 62.70 +/- 3.40 | 62.57 +/- 3.36 | (no drop scenario) | 0.467 +/- 0.016 | 0.979 +/- 0.047 |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 15.47 +/- 4.28 | 64.99 +/- 2.91 | 64.73 +/- 2.91 | (no drop scenario) | 0.459 +/- 0.010 | 0.979 +/- 0.047 |

### s7_down_100to15 (primary band: EVAL (1000-1009))

- commit provenance: `fdfd2cf62a1a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 87.21 +/- 0.55 | 0.79 +/- 0.03 | 0.385 +/- 0.124 | NOT AVAILABLE | 23.65 +/- 0.01 | 23.37 +/- 0.01 | 15.02 +/- 0.00 | 0.886 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 27.70 +/- 7.01 | 0.76 +/- 0.02 | 0.075 +/- 0.045 | NOT AVAILABLE | 32.28 +/- 0.22 | 31.86 +/- 0.21 | 11.19 +/- 0.66 | 0.956 +/- 0.001 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 34.99 +/- 29.20 | 0.72 +/- 0.04 | 0.040 +/- 0.050 | NOT AVAILABLE | 31.11 +/- 0.73 | 30.64 +/- 0.71 | 12.77 +/- 0.49 | 0.948 +/- 0.005 | NOT AVAILABLE |

### s7_down_100to15 (DEV, seeds 1000-1009)

- commit provenance: `fdfd2cf62a1a`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 87.21 +/- 0.55 | 0.79 +/- 0.03 | 0.385 +/- 0.124 | NOT AVAILABLE | 23.65 +/- 0.01 | 23.37 +/- 0.01 | 15.02 +/- 0.00 | 0.886 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 27.70 +/- 7.01 | 0.76 +/- 0.02 | 0.075 +/- 0.045 | NOT AVAILABLE | 32.28 +/- 0.22 | 31.86 +/- 0.21 | 11.19 +/- 0.66 | 0.956 +/- 0.001 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 34.99 +/- 29.20 | 0.72 +/- 0.04 | 0.040 +/- 0.050 | NOT AVAILABLE | 31.11 +/- 0.73 | 30.64 +/- 0.71 | 12.77 +/- 0.49 | 0.948 +/- 0.005 | NOT AVAILABLE |

### s7_down_100to8 (primary band: EVAL (1000-1009))

- commit provenance: `fdfd2cf62a1a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 78.35 +/- 0.77 | 1.25 +/- 0.03 | 0.570 +/- 0.203 | NOT AVAILABLE | 18.67 +/- 0.02 | 18.50 +/- 0.02 | 8.02 +/- 0.00 | 0.828 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 75.94 +/- 1.36 | 1.16 +/- 0.02 | 0.500 +/- 0.153 | NOT AVAILABLE | 28.46 +/- 0.20 | 27.88 +/- 0.19 | 0.01 +/- 0.00 | 0.930 +/- 0.002 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 78.76 +/- 0.52 | 1.21 +/- 0.03 | 0.430 +/- 0.161 | NOT AVAILABLE | 27.15 +/- 0.74 | 26.50 +/- 0.69 | 7.37 +/- 0.13 | 0.919 +/- 0.006 | NOT AVAILABLE |

### s7_down_100to8 (DEV, seeds 1000-1009)

- commit provenance: `fdfd2cf62a1a`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 78.35 +/- 0.77 | 1.25 +/- 0.03 | 0.570 +/- 0.203 | NOT AVAILABLE | 18.67 +/- 0.02 | 18.50 +/- 0.02 | 8.02 +/- 0.00 | 0.828 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 75.94 +/- 1.36 | 1.16 +/- 0.02 | 0.500 +/- 0.153 | NOT AVAILABLE | 28.46 +/- 0.20 | 27.88 +/- 0.19 | 0.01 +/- 0.00 | 0.930 +/- 0.002 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 78.76 +/- 0.52 | 1.21 +/- 0.03 | 0.430 +/- 0.161 | NOT AVAILABLE | 27.15 +/- 0.74 | 26.50 +/- 0.69 | 7.37 +/- 0.13 | 0.919 +/- 0.006 | NOT AVAILABLE |

### s7_rampup_30to100 (primary band: EVAL (1000-1009))

- commit provenance: `fdfd2cf62a1a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.47 +/- 0.04 | 0.46 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | (no drop scenario) | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.75 +/- 0.07 | 0.30 +/- 0.02 | 0.007 +/- 0.010 | NOT AVAILABLE | 25.36 +/- 1.20 | 25.32 +/- 1.20 | (no drop scenario) | 0.903 +/- 0.012 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 12.91 +/- 4.66 | 0.42 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 53.85 +/- 3.19 | 53.68 +/- 3.21 | (no drop scenario) | 0.997 +/- 0.001 | NOT AVAILABLE |

### s7_rampup_30to100 (DEV, seeds 1000-1009)

- commit provenance: `fdfd2cf62a1a`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.47 +/- 0.04 | 0.46 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | (no drop scenario) | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.75 +/- 0.07 | 0.30 +/- 0.02 | 0.007 +/- 0.010 | NOT AVAILABLE | 25.36 +/- 1.20 | 25.32 +/- 1.20 | (no drop scenario) | 0.903 +/- 0.012 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 12.91 +/- 4.66 | 0.42 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 53.85 +/- 3.19 | 53.68 +/- 3.21 | (no drop scenario) | 0.997 +/- 0.001 | NOT AVAILABLE |

### s7_up_20to60 (primary band: EVAL (1000-1009))

- commit provenance: `fdfd2cf62a1a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.86 +/- 0.09 | 0.59 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.46 +/- 0.00 | 9.45 +/- 0.00 | 9.93 +/- 0.01 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.90 +/- 0.08 | 0.39 +/- 0.04 | 0.010 +/- 0.011 | NOT AVAILABLE | 16.50 +/- 0.83 | 16.46 +/- 0.83 | 17.40 +/- 1.08 | 0.797 +/- 0.012 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 12.41 +/- 6.20 | 0.45 +/- 0.02 | 0.003 +/- 0.007 | NOT AVAILABLE | 34.90 +/- 1.55 | 34.75 +/- 1.56 | 40.31 +/- 2.43 | 0.968 +/- 0.008 | NOT AVAILABLE |

### s7_up_20to60 (DEV, seeds 1000-1009)

- commit provenance: `fdfd2cf62a1a`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.86 +/- 0.09 | 0.59 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.46 +/- 0.00 | 9.45 +/- 0.00 | 9.93 +/- 0.01 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.90 +/- 0.08 | 0.39 +/- 0.04 | 0.010 +/- 0.011 | NOT AVAILABLE | 16.50 +/- 0.83 | 16.46 +/- 0.83 | 17.40 +/- 1.08 | 0.797 +/- 0.012 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 12.41 +/- 6.20 | 0.45 +/- 0.02 | 0.003 +/- 0.007 | NOT AVAILABLE | 34.90 +/- 1.55 | 34.75 +/- 1.56 | 40.31 +/- 2.43 | 0.968 +/- 0.008 | NOT AVAILABLE |

### s7_up_30to100 (primary band: EVAL (1000-1009))

- commit provenance: `fdfd2cf62a1a` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.27 +/- 0.02 | 0.43 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | 14.90 +/- 0.00 | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.70 +/- 0.04 | 0.26 +/- 0.02 | 0.003 +/- 0.007 | NOT AVAILABLE | 24.57 +/- 1.04 | 24.54 +/- 1.04 | 25.89 +/- 1.45 | 0.895 +/- 0.011 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 12.68 +/- 4.86 | 0.43 +/- 0.03 | 0.007 +/- 0.010 | NOT AVAILABLE | 53.86 +/- 2.26 | 53.66 +/- 2.26 | 61.71 +/- 3.11 | 0.998 +/- 0.001 | NOT AVAILABLE |

### s7_up_30to100 (DEV, seeds 1000-1009)

- commit provenance: `fdfd2cf62a1a`

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.27 +/- 0.02 | 0.43 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | 14.90 +/- 0.00 | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.70 +/- 0.04 | 0.26 +/- 0.02 | 0.003 +/- 0.007 | NOT AVAILABLE | 24.57 +/- 1.04 | 24.54 +/- 1.04 | 25.89 +/- 1.45 | 0.895 +/- 0.011 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 12.68 +/- 4.86 | 0.43 +/- 0.03 | 0.007 +/- 0.010 | NOT AVAILABLE | 53.86 +/- 2.26 | 53.66 +/- 2.26 | 61.71 +/- 3.11 | 0.998 +/- 0.001 | NOT AVAILABLE |

## ACIQ vs every arm (positive % is better ACIQ on the metric at the head of the column; a cell like `41.0x` is the multiplicative factor when the baseline is so close to zero that a percentage would mislead)

| scenario | vs arm | call p95 delta % | CI overlap? | bulk delta % | CI overlap? |
| --- | --- | --- | --- | --- | --- |
Bulk compares are POST-DROP ONLY in scenarios with a capacity drop (same `bulk_mbps` whole-run mean otherwise): the whole-run number dilutes the post-drop regime with a saturated prefix, which is the opposite of the decision those scenarios exist to measure.

| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +69.3 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -30.8 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +8.7 | disjoint | -15.5 | disjoint |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -3.2 | overlap | +866.2 | disjoint |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 23.6x | disjoint | -16.6 | disjoint |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | +32.8 | overlap | +7.7 | overlap |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -0.6 | overlap | +362.0 | disjoint |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | +6.8 | overlap | +177.2 | disjoint |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +59.9 | disjoint | -14.9 | disjoint |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -26.3 | overlap | +14.1 | disjoint |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -0.5 | overlap | -8.1 | disjoint |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -3.7 | disjoint | 675.4x | disjoint |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -777.9 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -639.8 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -566.3 | disjoint | +305.8 | disjoint |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -551.5 | disjoint | +131.6 | disjoint |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -899.1 | disjoint | +314.1 | disjoint |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -644.0 | disjoint | +138.4 | disjoint |

## Where ACIQ is worse (the honest column)

Every row above where ACIQ's signed delta is negative, collected so a CAKE win cannot hide behind the aggregate. Empty means no such pair exists in the runs found.

| scenario | vs arm | metric where ACIQ is worse |
| --- | --- | --- |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -30.8 |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -15.5 |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -3.2 |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -16.6 |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -0.6 |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -14.9 |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -26.3 |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -0.5 and post-drop bulk Mbps -8.1 |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -3.7 |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -777.9 |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -639.8 |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -566.3 |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -551.5 |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -899.1 |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -644.0 |

## Where CAKE-static wins

The honest column above lists every rival; this one isolates the set-and-forget rival that matters for the design claim. A CAKE win on a metric is stated here verbatim; nothing is re-derived and nothing is argued away. CI overlap of the underlying seed samples is in the table above (`CI overlap?` column).

| scenario | metric where CAKE-static beats ACIQ | see column in the ACIQ-vs-every table |
| --- | --- | --- |
(none in these runs)

## ACIQ adaptation and capacity accuracy (from the same runs above)

| scenario | n | bind: drop -> first applied <=1.05x post-drop (s) | bind: drop -> first applied <=1.25x post-drop (s) | final estimate | configured end link | estimate error % |
| --- | --- | --- | --- | --- | --- | --- |
| s2b_ramp_100to30 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 26.42 +/- 1.49 | 30.0 +/- 0.0 | mean abs 12.0% (seed0: 25.59/30.0 (14.7% off)) |
| s2b_step_10 | 10 | 7.00 (n=10) | 6.47 (n=10) | 8.40 +/- 0.30 | 10.0 +/- 0.0 | mean abs 16.0% (seed0: 8.29/10.0 (17.1% off)) |
| s2b_step_50 | 10 | 4.44 (n=10) | 1.26 (n=10) | 45.48 +/- 2.34 | 50.0 +/- 0.0 | mean abs 9.3% (seed0: 50.05/50.0 (0.1% off)) |
| s2b_step_up_20to100 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | 3.74 (n=3) | 34.64 +/- 5.17 | 100.0 +/- 0.0 | mean abs 65.4% (seed0: 41.50/100.0 (58.5% off)) |
| s3_stress | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 75.55 +/- 4.09 | 100.0 +/- 0.0 | mean abs 24.4% (seed0: 82.25/100.0 (17.8% off)) |
| s7_down_100to15 | 10 | 10.17 (n=10) | 4.87 (n=10) | 13.00 +/- 0.42 | 15.0 +/- 0.0 | mean abs 13.3% (seed0: 12.18/15.0 (18.8% off)) |
| s7_down_100to8 | 10 | 12.54 (n=10) | 12.01 (n=10) | 6.88 +/- 0.26 | 8.0 +/- 0.0 | mean abs 13.9% (seed0: 6.89/8.0 (13.9% off)) |
| s7_rampup_30to100 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 49.60 +/- 3.27 | 100.0 +/- 0.0 | mean abs 50.4% (seed0: 49.03/100.0 (51.0% off)) |
| s7_up_20to60 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | 2.83 (n=1) | 30.58 +/- 1.41 | 60.0 +/- 0.0 | mean abs 49.0% (seed0: 30.07/60.0 (49.9% off)) |
| s7_up_30to100 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | 3.85 (n=1) | 50.65 +/- 3.20 | 100.0 +/- 0.0 | mean abs 49.3% (seed0: 57.42/100.0 (42.6% off)) |
## Controller resources (ACIQ adaptive runs only; from each result's resources block)

| scenario | n | cpu mean frac | decision p95 ms | decision max ms | max RSS bytes |
| --- | --- | --- | --- | --- | --- |
| s2b_ramp_100to30 | 10 | 0.0082 +/- 0.0001 | 75.23 +/- 0.88 | 79.56 +/- 1.88 | 30094131 +/- 724965 |
| s2b_step_10 | 10 | 0.0075 +/- 0.0001 | 74.49 +/- 1.24 | 87.80 +/- 8.71 | 29048013 +/- 584065 |
| s2b_step_50 | 10 | 0.0075 +/- 0.0002 | 75.00 +/- 1.91 | 84.07 +/- 3.49 | 29085696 +/- 612054 |
| s2b_step_up_20to100 | 10 | 0.0075 +/- 0.0001 | 75.55 +/- 1.90 | 87.92 +/- 10.41 | 30178918 +/- 739876 |
| s3_stress | 10 | 0.0087 +/- 0.0002 | 79.83 +/- 1.74 | 89.57 +/- 7.29 | 29396582 +/- 623547 |
| s7_down_100to15 | 10 | 0.0075 +/- 0.0001 | 75.36 +/- 2.64 | 83.48 +/- 4.39 | 28933734 +/- 560665 |
| s7_down_100to8 | 10 | 0.0075 +/- 0.0002 | 75.51 +/- 0.57 | 87.15 +/- 9.68 | 28927181 +/- 541883 |
| s7_rampup_30to100 | 10 | 0.0080 +/- 0.0002 | 78.92 +/- 3.21 | 98.27 +/- 13.18 | 30017946 +/- 731014 |
| s7_up_20to60 | 10 | 0.0081 +/- 0.0006 | 84.92 +/- 7.48 | 114.31 +/- 23.43 | 30204314 +/- 762166 |
| s7_up_30to100 | 10 | 0.0082 +/- 0.0003 | 97.39 +/- 10.35 | 162.82 +/- 41.23 | 30150246 +/- 789872 |
- CPU context (adaptive vs adaptive): CAKE-adaptive runs at 0.51x the ACIQ CPU fraction on the shared scenario(s): s2b_ramp_100to30 0.62x, s2b_step_10 0.58x, s2b_step_50 0.57x, s2b_step_up_20to100 0.46x, s3_stress 0.46x, s7_down_100to15 0.55x, s7_down_100to8 0.60x, s7_rampup_30to100 0.46x, s7_up_20to60 0.42x, s7_up_30to100 0.43x. The cause must be read from the artifacts (CPU profile, decision cadence), not assumed.

## Fairness detail (workload-rate Jain; per-class minima over ASSIGNED classes only, same scope for every mode)

| scenario | arm | n | jain mean +/- CI | demand-jain mean +/- CI | flows used | min over time (per label, via carrying class) |
| --- | --- | --- | --- | --- | --- | --- |
demand-jain: Jain over per-flow satisfied-demand ratios (achieved/demand, demand self-reported by the generator; elastic flows without a declared demand are excluded by definition -- see aciq/fairness.py). A scenario flows all-elastic has no such index and prints NOT AVAILABLE rather than a substitute.

Per-tick counter attribution (fix 18): ACIQ's tree has one leaf per class; the baselines' single-class tree carries the WHOLE link on the 1:50 leaf. New artefacts sample that aggregate under `unknown` (an aggregate can no longer masquerade as a software_update class); artefacts from before this change stored the same aggregate under `software_update`, and consumers that fall back to the legacy label must name it -- the post-drop bulk column does exactly that.

| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.982 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=30; call via unknown=30; bulk via unknown=30; call via unknown=30 |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.999 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=73.7; call via unknown=73.7; bulk via unknown=23.5; call via unknown=23.5; bulk via unknown=28.5; call via unknown=28.5 |
| s2b_ramp_100to30 | ACIQ (controller) | 10 | 0.998 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.846 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.97; call via unknown=9.97; bulk via unknown=9.99; call via unknown=9.99 |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.937 +/- 0.003 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=0.0023; call via unknown=0.0023; bulk via unknown=0; call via unknown=0; bulk via unknown=0.00907; call via unknown=0.00907 |
| s2b_step_10 | ACIQ (controller) | 10 | 0.926 +/- 0.006 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.000 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=50; call via unknown=50; bulk via unknown=49.9; call via unknown=49.9; bulk via unknown=50; call via unknown=50 |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.999 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=32.2; call via unknown=32.2; bulk via unknown=82.6; call via unknown=82.6; bulk via unknown=50; call via unknown=50 |
| s2b_step_50 | ACIQ (controller) | 10 | 1.000 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.683 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.99; call via unknown=9.99; bulk via unknown=9.99; call via unknown=9.99; bulk via unknown=9.96; call via unknown=9.96 |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.788 +/- 0.011 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15.5; call via unknown=15.5; bulk via unknown=14.4; call via unknown=14.4; bulk via unknown=15.4; call via unknown=15.4 |
| s2b_step_up_20to100 | ACIQ (controller) | 10 | 0.981 +/- 0.013 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.573 +/- 0.016 | 0.979 +/- 0.047 | 5.0 +/- 0.0 | bulk via unknown=50; game via unknown=50; tv1 via unknown=50; tv2 via unknown=50; tv3 via unknown=50; bulk via unknown=50 |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.467 +/- 0.016 | 0.979 +/- 0.047 | 5.0 +/- 0.0 | bulk via unknown=76.2; game via unknown=76.2; tv1 via unknown=76.2; tv2 via unknown=76.2; tv3 via unknown=76.2; bulk via unknown=63.7 |
| s3_stress | ACIQ (controller) | 10 | 0.459 +/- 0.010 | 0.979 +/- 0.047 | 5.0 +/- 0.0 | bulk=0; game via unknown=0; tv1 via unknown=0; tv2 via unknown=0; tv3 via unknown=0; bulk=0 |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.886 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15 |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.956 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=0.0117; call via unknown=0.0117; bulk via unknown=0; call via unknown=0; bulk via unknown=0.0117; call via unknown=0.0117 |
| s7_down_100to15 | ACIQ (controller) | 10 | 0.948 +/- 0.005 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.828 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=7.99; call via unknown=7.99; bulk via unknown=7.98; call via unknown=7.98; bulk via unknown=7.97; call via unknown=7.97 |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.930 +/- 0.002 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=0; call via unknown=0; bulk via unknown=0.00741; call via unknown=0.00741; bulk via unknown=0; call via unknown=0 |
| s7_down_100to8 | ACIQ (controller) | 10 | 0.919 +/- 0.006 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.764 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=14.9; call via unknown=14.9; bulk via unknown=14.9; call via unknown=14.9; bulk via unknown=14.9; call via unknown=14.9 |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.903 +/- 0.012 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=23; call via unknown=23; bulk via unknown=23; call via unknown=23; bulk via unknown=23; call via unknown=23 |
| s7_rampup_30to100 | ACIQ (controller) | 10 | 0.997 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.683 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.87; call via unknown=9.87; bulk via unknown=9.99; call via unknown=9.99; bulk via unknown=9.9; call via unknown=9.9 |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.797 +/- 0.012 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=16.7; call via unknown=16.7; bulk via unknown=16.7; call via unknown=16.7; bulk via unknown=15.6; call via unknown=15.6 |
| s7_up_20to60 | ACIQ (controller) | 10 | 0.968 +/- 0.008 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.764 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15 |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.895 +/- 0.011 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=23; call via unknown=23; bulk via unknown=25; call via unknown=25; bulk via unknown=23; call via unknown=23 |
| s7_up_30to100 | ACIQ (controller) | 10 | 0.998 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |

Starvation (TASK 5b, fixed basis): per LABEL, over the class the data says carried the traffic (assigned class, or the router's `unknown`/legacy aggregate when the label's traffic rode there -- chosen by highest mean, and the carrying class is named). A label starved in tick t if its per-tick goodput fell below 20% of its REGIME median -- in a drop scenario the median is the POST-DROP regime's own median, so the shaped link rate can never masquerade as starvation; without a drop it is the whole window's. The cell lists the starved timestamps counted over seeds. With no series at all the cell prints NOT AVAILABLE, never an empty claim.

| scenario | arm | starved ticks per label (via carrying class) |
| --- | --- | --- |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 3 ticks over 2 seed(s), first t=43.7; call via unknown: 3 ticks over 2 seed(s), first t=43.7 |
| s2b_ramp_100to30 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 301 ticks over 10 seed(s), first t=5.3 |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 12 ticks over 8 seed(s), first t=23.8; call via unknown: 12 ticks over 8 seed(s), first t=23.8 |
| s2b_step_10 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 195 ticks over 10 seed(s), first t=5.3 |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 226 ticks over 10 seed(s), first t=5.3 |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 308 ticks over 10 seed(s), first t=5.3 |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 49 seed x label series (regime-aware threshold, declared window) |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 1 ticks over 1 seed(s), first t=10.3; game via unknown: 1 ticks over 1 seed(s), first t=10.3; tv1 via unknown: 1 ticks over 1 seed(s), first t=10.3; tv2 via unknown: 1 ticks over 1 seed(s), first t=10.3; tv3 via unknown: 1 ticks over 1 seed(s), first t=10.3 |
| s3_stress | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; game via unknown: 88 ticks over 10 seed(s), first t=13.8; tv1 via unknown: 88 ticks over 10 seed(s), first t=13.8; tv2 via unknown: 77 ticks over 9 seed(s), first t=13.8; tv3 via unknown: 88 ticks over 10 seed(s), first t=13.8 |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 25 ticks over 10 seed(s), first t=21.7; call via unknown: 25 ticks over 10 seed(s), first t=21.7 |
| s7_down_100to15 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 199 ticks over 10 seed(s), first t=5.3 |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 13 ticks over 8 seed(s), first t=24.8; call via unknown: 13 ticks over 8 seed(s), first t=24.8 |
| s7_down_100to8 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 185 ticks over 10 seed(s), first t=4.2 |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_rampup_30to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 314 ticks over 10 seed(s), first t=5.3 |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_20to60 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 291 ticks over 10 seed(s), first t=5.3 |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_30to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 292 ticks over 10 seed(s), first t=5.3 |

Warm-up exclusion (declared): every per-tick window above starts at t >= 2.0 s. The diagnosis round (fix 17's diagnosis.md) shows the first ~2 s of per-tick counter rates are a transmit/counter ramp artefact, not traffic behaviour; dropping those ticks removes nothing else. The window boundary is a declared constant in this generator, not a per-run choice.

Further declared exclusions (TASK 5b): (1) ticks at or beyond the label generator's own measured lifetime (`elapsed_s`, capped by the scenario duration) -- a verdict about a label after its traffic stopped describes nothing about the label; (2) ticks whose link counters went BACKWARDS -- a qdisc del/re-add resets every counter on the device, so that tick's per-class goodput is a reset artefact, not a delivery gap. Stars and minima are computed over what remains; nothing is excluded silently.

## Step/demand generalization band (evaluation-only; docs/evidence/s2b-params.md + docs/evidence/round3-params.md, declared BEFORE these runs)

The shipped controller runs unchanged on capacity changes it was never tuned on: two down-step magnitudes, a 5x up-step, and a continuous 20 s ramp -- plus the round-3 DEV shapes (s7_* up/down steps and ramps, s3_stress) and the two queue-discipline-only arms (CAKE-conservative / CAKE-adaptive). Seeds 800-809 configured per scenario (the DEV band, seed names in each run dir). CAKE-static is applied once at launch and never re-applied: that is its declared semantics, and this band exists to surface the consequences. Definitions: bind = first tick at which the applied tree sits within 10% of the link's truth and stays there (down-moves only; up-moves print `n/a (up-step)` and are judged by the utilization column: applied/truth and receiver delivered/truth over the final third); tracking error = mean |applied - truth| over the ramp window; estimate error = same over the final third. Where ACIQ fails, the row says so.

Engine commit at generation time: `fdfd2cf62a1a` — a run whose result carries a different commit_hash is SUPERSEDED, listed under 'commit provenance' below and never pooled into a numeric cell with a newer commit.

### s2b_step_50

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 50.00 +/- 0.00 | 167.74 +/- 1.67 | 47.66 +/- 0.13 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 50.00 +/- 0.00 | 10.60 +/- 2.59 | 33.05 +/- 4.09 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 12.0 +/- 0.6 | 4.10 +/- 1.76 | 7.12 +/- 3.44 | 33.11 +/- 1.33 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 51.2 vs truth 50.0, 2% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 45.1 vs truth 50.0, 10% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 42.7 vs truth 50.0, 15% off truth, confidence 0.35; final tick: UNSATURATED (estimator not saturated at the end regime), applied 48.3 vs truth 50.0, 3% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 44.0 vs truth 50.0, 12% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 46.4 vs truth 50.0, 7% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 42.5 vs truth 50.0, 15% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 48.3 vs truth 50.0, 3% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 44.6 vs truth 50.0, 11% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 51.6 vs truth 50.0, 3% off truth, confidence 0.55 |

### s2b_step_10

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 90.00 +/- 0.00 | 82.56 +/- 0.57 | 9.45 +/- 0.01 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 90.00 +/- 0.00 | 73.03 +/- 1.51 | 9.27 +/- 0.13 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 17.0 +/- 0.1 | 1.55 +/- 0.31 | 75.40 +/- 1.95 | 6.42 +/- 0.26 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.4 vs truth 10.0, 16% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.4 vs truth 10.0, 16% off truth, confidence 0.50; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.2 vs truth 10.0, 18% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.2 vs truth 10.0, 18% off truth, confidence 0.20; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.3 vs truth 10.0, 17% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.2 vs truth 10.0, 18% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 9.2 vs truth 10.0, 8% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.3 vs truth 10.0, 17% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 9.3 vs truth 10.0, 7% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.2 vs truth 10.0, 18% off truth, confidence 0.35 |

### s2b_step_up_20to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 80.00 +/- 0.00 | 1.79 +/- 0.02 | 9.36 +/- 0.07 | appl 0.20 +/- 0.00 / delv 0.09 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 80.00 +/- 0.00 | 1.93 +/- 0.05 | 15.56 +/- 1.21 | appl 0.20 +/- 0.00 / delv 0.16 +/- 0.01 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 21.89 +/- 11.24 | 1.80 +/- 0.28 | 56.02 +/- 9.39 | appl 0.83 +/- 0.15 / delv 0.56 +/- 0.09 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 101.1 vs truth 100.0, 1% off truth, confidence 0.25 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 64.9 vs truth 100.0, 35% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 69.2 vs truth 100.0, 31% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 64.6 vs truth 100.0, 35% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 102.4 vs truth 100.0, 2% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 110.6 vs truth 100.0, 11% off truth, confidence 0.20; final tick: UNSATURATED (estimator not saturated at the end regime), applied 64.7 vs truth 100.0, 35% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 55.6 vs truth 100.0, 44% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 101.6 vs truth 100.0, 2% off truth, confidence 0.10 |

### s2b_ramp_100to30

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 110.55 +/- 2.71 | 28.58 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 25.93 +/- 2.22 | 22.71 +/- 1.38 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 34.3 +/- 6.5 | 2.97 +/- 0.98 | 33.93 +/- 4.15 | 19.90 +/- 0.86 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 26.1 vs truth 30.0, 13% off truth, confidence 0.05; final tick: UNSATURATED (estimator not saturated at the end regime), applied 27.1 vs truth 30.0, 10% off truth, confidence 0.30; final tick: UNSATURATED (estimator not saturated at the end regime), applied 27.4 vs truth 30.0, 9% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 27.3 vs truth 30.0, 9% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 27.0 vs truth 30.0, 10% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 26.9 vs truth 30.0, 10% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 25.7 vs truth 30.0, 14% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 22.3 vs truth 30.0, 26% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 27.5 vs truth 30.0, 8% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 30.6 vs truth 30.0, 2% off truth, confidence 0.10 |

### s7_up_20to60

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 40.00 +/- 0.00 | 1.86 +/- 0.09 | 9.37 +/- 0.09 | appl 0.33 +/- 0.00 / delv 0.16 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 40.00 +/- 0.00 | 1.90 +/- 0.08 | 16.21 +/- 1.31 | appl 0.33 +/- 0.00 / delv 0.27 +/- 0.02 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 14.07 +/- 6.06 | 12.41 +/- 6.20 | 40.07 +/- 5.02 | appl 0.92 +/- 0.11 / delv 0.67 +/- 0.08 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 64.9 vs truth 60.0, 8% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 57.4 vs truth 60.0, 4% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 42.8 vs truth 60.0, 29% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 30.3 vs truth 60.0, 49% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 30.5 vs truth 60.0, 49% off truth, confidence 0.15; final tick: UNSATURATED (estimator not saturated at the end regime), applied 65.5 vs truth 60.0, 9% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 65.2 vs truth 60.0, 9% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 30.6 vs truth 60.0, 49% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 30.4 vs truth 60.0, 49% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 31.0 vs truth 60.0, 48% off truth, confidence 0.00 |

### s7_up_30to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 70.00 +/- 0.00 | 1.27 +/- 0.02 | 14.14 +/- 0.10 | appl 0.30 +/- 0.00 / delv 0.14 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 70.00 +/- 0.00 | 1.70 +/- 0.04 | 24.64 +/- 1.67 | appl 0.30 +/- 0.00 / delv 0.25 +/- 0.02 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 22.76 +/- 10.34 | 12.68 +/- 4.86 | 63.94 +/- 6.77 | appl 0.88 +/- 0.13 / delv 0.64 +/- 0.07 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 104.6 vs truth 100.0, 5% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 97.9 vs truth 100.0, 2% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 131.0 vs truth 100.0, 31% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 97.1 vs truth 100.0, 3% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 47.8 vs truth 100.0, 52% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 46.9 vs truth 100.0, 53% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 50.4 vs truth 100.0, 50% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 49.9 vs truth 100.0, 50% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 48.2 vs truth 100.0, 52% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 52.9 vs truth 100.0, 47% off truth, confidence 0.00 |

### s7_rampup_30to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 1.47 +/- 0.04 | 14.23 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 1.75 +/- 0.07 | 25.28 +/- 1.45 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 47.2 +/- 8.1 | 20.33 +/- 13.30 | 12.91 +/- 4.66 | 65.95 +/- 8.84 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 97.4 vs truth 100.0, 3% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 96.9 vs truth 100.0, 3% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 50.4 vs truth 100.0, 50% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 104.5 vs truth 100.0, 4% off truth, confidence 0.25 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 46.0 vs truth 100.0, 54% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 47.7 vs truth 100.0, 52% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 105.3 vs truth 100.0, 5% off truth, confidence 0.20; final tick: UNSATURATED (estimator not saturated at the end regime), applied 51.0 vs truth 100.0, 49% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 129.8 vs truth 100.0, 30% off truth, confidence 0.25 |

### s7_down_100to15

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 85.00 +/- 0.00 | 87.21 +/- 0.55 | 14.20 +/- 0.07 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 85.00 +/- 0.00 | 27.70 +/- 7.01 | 12.33 +/- 0.24 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 22.3 +/- 0.3 | 1.73 +/- 0.33 | 34.99 +/- 29.20 | 9.95 +/- 0.38 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 12.4 vs truth 15.0, 18% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 12.8 vs truth 15.0, 15% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 13.4 vs truth 15.0, 11% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 12.4 vs truth 15.0, 17% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 12.9 vs truth 15.0, 14% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 13.3 vs truth 15.0, 11% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 15.0, 7% off truth, confidence 0.55 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 13.4 vs truth 15.0, 11% off truth, confidence 0.45; final tick: UNSATURATED (estimator not saturated at the end regime), applied 13.2 vs truth 15.0, 12% off truth, confidence 0.50 |

### s7_down_100to8

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 92.00 +/- 0.00 | 78.35 +/- 0.77 | 7.54 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 92.00 +/- 0.00 | 75.94 +/- 1.36 | 7.47 +/- 0.10 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 37.1 | 0.98 +/- 0.18 | 78.76 +/- 0.52 | 5.88 +/- 0.19 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.6 vs truth 8.0, 8% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 6.7 vs truth 8.0, 16% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.9 vs truth 8.0, 11% off truth, confidence 0.55 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 6.4 vs truth 8.0, 19% off truth, confidence 0.45; final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.9 vs truth 8.0, 12% off truth, confidence 0.55; final tick: UNSATURATED (estimator not saturated at the end regime), applied 9.0 vs truth 8.0, 13% off truth, confidence 0.55 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 7.1 vs truth 8.0, 11% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 6.2 vs truth 8.0, 22% off truth, confidence 0.55 |

### s3_stress

| arm | n | call p95 whole-run (ms) | game p95 whole-run (ms) | bulk receiver mean inst (Mbps) | tv1 / tv2 / tv3 receiver mean inst (Mbps) | overload note (loaded vs capacity) |
| --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE | 2.03 +/- 0.32 | 31.78 +/- 0.95 | 4.40 / 4.40 / 4.40; 4.44 / 4.40; 4.40 / 4.40 / 4.40; 4.40 / 4.40 / 4.40; 4.50 / 4.50 / 4.50; 4.50 / 4.50 / 4.50; 4.61 / 4.61 / 4.61; 4.61 / 4.61 / 4.61; 4.40 / 4.40 / 4.40; 4.50 / 4.50 / 4.50 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE | 9.21 +/- 7.05 | 57.05 +/- 3.37 | 4.30 / 4.30 / 4.30; 4.44 / 4.40; 4.40 / 4.40 / 4.40; 4.30 / 4.30 / 4.30; 4.39 / 4.40 / 4.38; 4.40 / 4.40 / 4.40; 4.50 / 4.50 / 4.50; 4.50 / 4.48 / 4.50; 4.29 / 4.30 / 4.30; 4.50 / 4.50 / 4.50 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |
| ACIQ (controller) | 10 | NOT AVAILABLE | 15.47 +/- 4.28 | 57.04 +/- 2.82 | 4.21 / 4.22 / 4.22; 4.25 / 4.21; 4.21 / 4.21 / 4.21; 4.12 / 4.12 / 4.12; 4.31 / 4.30 / 4.30; 4.21 / 4.21 / 4.21; 4.40 / 4.41 / 4.41; 4.40 / 4.31 / 4.40; 4.12 / 4.12 / 4.12; 4.30 / 4.30 / 4.30 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |

## Starvation, receiver side (every arm, per-second sink logs)

| scenario | arm | label; starved inst ticks over seeds (longest streak) |
| --- | --- | --- |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 3 tick(s) over 10 seed(s), longest streak 1 s; call: 14 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 22 tick(s) over 10 seed(s), longest streak 4 s; call: 33 tick(s) over 10 seed(s), longest streak 5 s |
| s2b_ramp_100to30 | ACIQ (controller) | bulk: 35 tick(s) over 10 seed(s), longest streak 4 s; call: 46 tick(s) over 10 seed(s), longest streak 5 s |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 8 tick(s) over 10 seed(s), longest streak 1 s |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 8 tick(s) over 10 seed(s), longest streak 1 s; call: 19 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_10 | ACIQ (controller) | bulk: 14 tick(s) over 10 seed(s), longest streak 2 s; call: 29 tick(s) over 10 seed(s), longest streak 4 s |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 11 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 14 tick(s) over 10 seed(s), longest streak 2 s; call: 22 tick(s) over 10 seed(s), longest streak 3 s |
| s2b_step_50 | ACIQ (controller) | bulk: 24 tick(s) over 10 seed(s), longest streak 3 s; call: 31 tick(s) over 10 seed(s), longest streak 4 s |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 5 tick(s) over 10 seed(s), longest streak 1 s; call: 13 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 10 tick(s) over 10 seed(s), longest streak 1 s; call: 19 tick(s) over 10 seed(s), longest streak 3 s |
| s2b_step_up_20to100 | ACIQ (controller) | bulk: 34 tick(s) over 10 seed(s), longest streak 4 s; call: 42 tick(s) over 10 seed(s), longest streak 5 s |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 8 tick(s) over 10 seed(s), longest streak 1 s; game: 26 tick(s) over 10 seed(s), longest streak 3 s; tv1: 21 tick(s) over 10 seed(s), longest streak 3 s; tv2: 13 tick(s) over 9 seed(s), longest streak 2 s; tv3: 13 tick(s) over 10 seed(s), longest streak 2 s |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 14 tick(s) over 10 seed(s), longest streak 1 s; game: 33 tick(s) over 10 seed(s), longest streak 4 s; tv1: 28 tick(s) over 10 seed(s), longest streak 3 s; tv2: 20 tick(s) over 9 seed(s), longest streak 3 s; tv3: 20 tick(s) over 10 seed(s), longest streak 2 s |
| s3_stress | ACIQ (controller) | bulk: 30 tick(s) over 10 seed(s), longest streak 3 s; game: 49 tick(s) over 10 seed(s), longest streak 6 s; tv1: 45 tick(s) over 10 seed(s), longest streak 5 s; tv2: 35 tick(s) over 9 seed(s), longest streak 4 s; tv3: 36 tick(s) over 10 seed(s), longest streak 4 s |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 1 tick(s) over 10 seed(s), longest streak 1 s; call: 11 tick(s) over 10 seed(s), longest streak 2 s |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 7 tick(s) over 10 seed(s), longest streak 1 s; call: 19 tick(s) over 10 seed(s), longest streak 2 s |
| s7_down_100to15 | ACIQ (controller) | bulk: 20 tick(s) over 10 seed(s), longest streak 3 s; call: 32 tick(s) over 10 seed(s), longest streak 4 s |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 8 tick(s) over 10 seed(s), longest streak 1 s |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 2 tick(s) over 10 seed(s), longest streak 1 s; call: 18 tick(s) over 10 seed(s), longest streak 2 s |
| s7_down_100to8 | ACIQ (controller) | bulk: 13 tick(s) over 10 seed(s), longest streak 2 s; call: 29 tick(s) over 10 seed(s), longest streak 3 s |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 6 tick(s) over 10 seed(s), longest streak 1 s; call: 13 tick(s) over 10 seed(s), longest streak 2 s |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 14 tick(s) over 10 seed(s), longest streak 2 s; call: 22 tick(s) over 10 seed(s), longest streak 3 s |
| s7_rampup_30to100 | ACIQ (controller) | bulk: 35 tick(s) over 10 seed(s), longest streak 4 s; call: 44 tick(s) over 10 seed(s), longest streak 5 s |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 6 tick(s) over 10 seed(s), longest streak 1 s; call: 14 tick(s) over 10 seed(s), longest streak 2 s |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 11 tick(s) over 10 seed(s), longest streak 2 s; call: 20 tick(s) over 10 seed(s), longest streak 3 s |
| s7_up_20to60 | ACIQ (controller) | bulk: 40 tick(s) over 10 seed(s), longest streak 5 s; call: 48 tick(s) over 10 seed(s), longest streak 6 s |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 3 tick(s) over 10 seed(s), longest streak 1 s; call: 12 tick(s) over 10 seed(s), longest streak 2 s |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 11 tick(s) over 10 seed(s), longest streak 2 s; call: 20 tick(s) over 10 seed(s), longest streak 3 s |
| s7_up_30to100 | ACIQ (controller) | bulk: 39 tick(s) over 10 seed(s), longest streak 5 s; call: 48 tick(s) over 10 seed(s), longest streak 6 s |


## Commit provenance (declared; every run's engine hash)

| scenario | arm | n runs | commit_hash | verdict |
| --- | --- | --- | --- | --- |
| s2b_ramp_100to30 | ACIQ (controller) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s2b_step_10 | ACIQ (controller) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s2b_step_50 | ACIQ (controller) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | ACIQ (controller) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s3_stress | ACIQ (controller) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_down_100to15 | ACIQ (controller) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_down_100to8 | ACIQ (controller) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | ACIQ (controller) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_up_20to60 | ACIQ (controller) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_up_30to100 | ACIQ (controller) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `fdfd2cf62a1a` | current: trusted for a frozen final band claim |

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

