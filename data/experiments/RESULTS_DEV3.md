# Results (generated, no summarised files consulted)

Runs root: `data/runs_dev3` | runs used: 300 | scenarios: s2b_ramp_100to30, s2b_step_10, s2b_step_50, s2b_step_up_20to100, s3_stress, s7_down_100to15, s7_down_100to8, s7_rampup_30to100, s7_up_20to60, s7_up_30to100

Generated from engine commit `912a6e2ec9dd`. Every section header below stamps the commit(s) of the runs it renders; a frozen final band may ONLY claim PASS/FAIL if every run in it carries this same hash — any mismatch is flagged per band and per scenario, never pooled silently.

## Delay and throughput, every scenario x arm (mean +/- 95% CI over seeds; t(9)=2.262 for n=10)

Every block below carries an explicit band label, derived from the seed family recorded at load time: `POST-FIX` (seeds 200-209, the controller after the redesign commits), `PRE-FIX` (legacy seeds 0-9/42-51), `DEV` and `EVAL` (the task-2 protocol: parameters were fixed on the DEV band seeds 400-409 BEFORE the EVAL band seeds 500-509 was run ONCE; nothing between them was tuned). A reader never inherits a number of unknown provenance: the label sits directly above the table. The comparison sections further down use the primary band only.

Bulk has TWO columns on purpose (TASK 5a): `sender` is what the generator pushed, `receiver/sink` is what the receiver's sink log totalled -- the delivered number, used for any bulk claim. The post-drop column stays on the TREE counters and is named so: the three are different instruments and are never blended.

### s2b_ramp_100to30 (primary band: DEV (1000-1009))

- commit provenance: `912a6e2ec9dd` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 109.47 +/- 1.37 | 0.66 +/- 0.01 | 0.287 +/- 0.023 | NOT AVAILABLE | 38.02 +/- 0.00 | 37.62 +/- 0.00 | (no drop scenario) | 0.982 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 18.57 +/- 5.03 | 0.52 +/- 0.03 | 0.100 +/- 0.045 | NOT AVAILABLE | 38.88 +/- 0.87 | 38.50 +/- 0.85 | (no drop scenario) | 0.984 +/- 0.003 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 24.13 +/- 1.20 | 0.56 +/- 0.03 | 0.003 +/- 0.007 | NOT AVAILABLE | 45.80 +/- 0.81 | 45.45 +/- 0.86 | (no drop scenario) | 0.998 +/- 0.001 | NOT AVAILABLE |

### s2b_step_10 (primary band: DEV (1000-1009))

- commit provenance: `912a6e2ec9dd` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 81.51 +/- 0.90 | 1.05 +/- 0.03 | 0.980 +/- 0.403 | NOT AVAILABLE | 20.10 +/- 0.02 | 19.93 +/- 0.02 | 10.02 +/- 0.01 | 0.846 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 73.61 +/- 1.80 | 1.01 +/- 0.02 | 0.465 +/- 0.113 | NOT AVAILABLE | 29.21 +/- 0.21 | 28.73 +/- 0.21 | 0.59 +/- 0.93 | 0.936 +/- 0.002 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 81.07 +/- 0.89 | 1.10 +/- 0.02 | 0.540 +/- 0.168 | NOT AVAILABLE | 29.24 +/- 0.15 | 28.78 +/- 0.14 | 2.65 +/- 0.53 | 0.936 +/- 0.001 | NOT AVAILABLE |

### s2b_step_50 (primary band: DEV (1000-1009))

- commit provenance: `912a6e2ec9dd` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 167.19 +/- 1.61 | 0.56 +/- 0.01 | 0.840 +/- 0.089 | NOT AVAILABLE | 48.29 +/- 0.00 | 47.71 +/- 0.00 | 50.00 +/- 0.00 | 1.000 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 15.09 +/- 4.49 | 0.46 +/- 0.03 | 0.070 +/- 0.038 | NOT AVAILABLE | 43.19 +/- 2.30 | 42.72 +/- 2.29 | 29.71 +/- 4.59 | 0.993 +/- 0.003 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 7.52 +/- 4.11 | 0.46 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 48.61 +/- 1.15 | 48.37 +/- 1.15 | 38.79 +/- 1.15 | 1.000 +/- 0.001 | NOT AVAILABLE |

### s2b_step_up_20to100 (primary band: DEV (1000-1009))

- commit provenance: `912a6e2ec9dd` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.83 +/- 0.03 | 0.58 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.47 +/- 0.01 | 9.45 +/- 0.00 | 9.94 +/- 0.01 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.90 +/- 0.05 | 0.36 +/- 0.04 | 0.017 +/- 0.017 | NOT AVAILABLE | 14.85 +/- 0.97 | 14.81 +/- 0.97 | 15.32 +/- 1.23 | 0.772 +/- 0.015 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 3.50 +/- 3.16 | 0.34 +/- 0.02 | 0.003 +/- 0.007 | NOT AVAILABLE | 41.94 +/- 2.73 | 41.88 +/- 2.71 | 47.95 +/- 2.94 | 0.990 +/- 0.006 | NOT AVAILABLE |

### s3_stress (primary band: DEV (1000-1009))

- commit provenance: `912a6e2ec9dd` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.10 +/- 0.27 | 34.37 +/- 1.11 | 34.33 +/- 1.11 | (no drop scenario) | 0.573 +/- 0.016 | 0.979 +/- 0.047 |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 6.17 +/- 4.67 | 59.47 +/- 5.48 | 59.31 +/- 5.51 | (no drop scenario) | 0.478 +/- 0.023 | 0.979 +/- 0.047 |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 17.77 +/- 1.92 | 70.52 +/- 1.25 | 70.26 +/- 1.28 | (no drop scenario) | 0.443 +/- 0.009 | 0.979 +/- 0.047 |

### s7_down_100to15 (primary band: DEV (1000-1009))

- commit provenance: `912a6e2ec9dd` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 87.56 +/- 0.49 | 0.78 +/- 0.01 | 0.325 +/- 0.080 | NOT AVAILABLE | 23.67 +/- 0.01 | 23.38 +/- 0.01 | 15.02 +/- 0.00 | 0.887 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 28.18 +/- 5.65 | 0.75 +/- 0.02 | 0.055 +/- 0.031 | NOT AVAILABLE | 31.67 +/- 0.29 | 31.27 +/- 0.28 | 12.49 +/- 0.70 | 0.952 +/- 0.002 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 41.23 +/- 6.26 | 0.71 +/- 0.01 | 0.005 +/- 0.011 | NOT AVAILABLE | 30.86 +/- 0.70 | 30.44 +/- 0.69 | 12.52 +/- 0.12 | 0.947 +/- 0.005 | NOT AVAILABLE |

### s7_down_100to8 (primary band: DEV (1000-1009))

- commit provenance: `912a6e2ec9dd` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 78.06 +/- 0.90 | 1.24 +/- 0.03 | 0.635 +/- 0.174 | NOT AVAILABLE | 18.73 +/- 0.03 | 18.55 +/- 0.02 | 8.02 +/- 0.00 | 0.828 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 76.86 +/- 0.65 | 1.18 +/- 0.02 | 0.525 +/- 0.120 | NOT AVAILABLE | 27.60 +/- 0.58 | 27.04 +/- 0.57 | 0.71 +/- 1.02 | 0.923 +/- 0.005 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 81.39 +/- 0.77 | 1.21 +/- 0.03 | 0.835 +/- 0.231 | NOT AVAILABLE | 27.86 +/- 0.49 | 27.31 +/- 0.48 | 3.67 +/- 2.11 | 0.925 +/- 0.004 | NOT AVAILABLE |

### s7_rampup_30to100 (primary band: DEV (1000-1009))

- commit provenance: `912a6e2ec9dd` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.47 +/- 0.05 | 0.47 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.01 | 14.23 +/- 0.00 | (no drop scenario) | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.73 +/- 0.07 | 0.34 +/- 0.02 | 0.020 +/- 0.012 | NOT AVAILABLE | 23.80 +/- 1.76 | 23.76 +/- 1.76 | (no drop scenario) | 0.887 +/- 0.020 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 8.94 +/- 4.82 | 0.48 +/- 0.04 | 0.007 +/- 0.010 | NOT AVAILABLE | 54.62 +/- 1.83 | 54.50 +/- 1.83 | (no drop scenario) | 0.998 +/- 0.002 | NOT AVAILABLE |

### s7_up_20to60 (primary band: DEV (1000-1009))

- commit provenance: `912a6e2ec9dd` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.86 +/- 0.10 | 0.59 +/- 0.03 | 0.000 +/- 0.000 | NOT AVAILABLE | 9.46 +/- 0.00 | 9.45 +/- 0.00 | 9.92 +/- 0.02 | 0.683 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.96 +/- 0.10 | 0.42 +/- 0.04 | 0.017 +/- 0.012 | NOT AVAILABLE | 15.07 +/- 0.72 | 15.04 +/- 0.72 | 15.65 +/- 1.02 | 0.776 +/- 0.011 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 10.09 +/- 3.74 | 0.45 +/- 0.01 | 0.007 +/- 0.010 | NOT AVAILABLE | 35.40 +/- 0.35 | 35.30 +/- 0.35 | 38.93 +/- 0.72 | 0.972 +/- 0.001 | NOT AVAILABLE |

### s7_up_30to100 (primary band: DEV (1000-1009))

- commit provenance: `912a6e2ec9dd` — matches this report's engine commit.

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.38 +/- 0.06 | 0.47 +/- 0.04 | 0.000 +/- 0.000 | NOT AVAILABLE | 14.25 +/- 0.00 | 14.23 +/- 0.00 | 14.88 +/- 0.01 | 0.764 +/- 0.000 | NOT AVAILABLE |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 1.71 +/- 0.08 | 0.36 +/- 0.06 | 0.010 +/- 0.016 | NOT AVAILABLE | 20.15 +/- 3.11 | 20.11 +/- 3.11 | 19.96 +/- 4.07 | 0.842 +/- 0.039 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 11.11 +/- 4.52 | 0.40 +/- 0.03 | 0.003 +/- 0.007 | NOT AVAILABLE | 56.03 +/- 1.34 | 55.92 +/- 1.33 | 63.88 +/- 3.18 | 0.997 +/- 0.001 | NOT AVAILABLE |

## ACIQ vs every arm (positive % is better ACIQ on the metric at the head of the column; a cell like `41.0x` is the multiplicative factor when the baseline is so close to zero that a percentage would mislead)

| scenario | vs arm | call p95 delta % | CI overlap? | bulk delta % | CI overlap? |
| --- | --- | --- | --- | --- | --- |
Bulk compares are POST-DROP ONLY in scenarios with a capacity drop (same `bulk_mbps` whole-run mean otherwise): the whole-run number dilutes the post-drop regime with a saturated prefix, which is the opposite of the decision those scenarios exist to measure.

| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +78.0 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -30.0 | overlap | NOT AVAILABLE | NOT AVAILABLE |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +0.5 | overlap | -73.5 | disjoint |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -10.1 | disjoint | +348.8 | disjoint |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 22.2x | disjoint | -22.4 | disjoint |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | +50.1 | overlap | +30.6 | disjoint |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -90.9 | overlap | +382.4 | disjoint |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -84.1 | overlap | +213.0 | disjoint |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | +52.9 | disjoint | -16.6 | disjoint |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -46.3 | disjoint | +0.3 | overlap |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -4.3 | disjoint | -54.3 | disjoint |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -5.9 | disjoint | +418.8 | overlap |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -510.2 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -416.9 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -443.7 | disjoint | +292.5 | disjoint |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -415.0 | disjoint | +148.7 | disjoint |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | -706.7 | disjoint | +329.3 | disjoint |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | -550.4 | disjoint | +220.0 | disjoint |

## Where ACIQ is worse (the honest column)

Every row above where ACIQ's signed delta is negative, collected so a CAKE win cannot hide behind the aggregate. Empty means no such pair exists in the runs found.

| scenario | vs arm | metric where ACIQ is worse |
| --- | --- | --- |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -30.0 |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -73.5 |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -10.1 |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -22.4 |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -90.9 |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -84.1 |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | post-drop bulk Mbps -16.6 |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -46.3 |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -4.3 and post-drop bulk Mbps -54.3 |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -5.9 |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -510.2 |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -416.9 |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -443.7 |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -415.0 |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | call p95 -706.7 |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | call p95 -550.4 |

## Where CAKE-static wins

The honest column above lists every rival; this one isolates the set-and-forget rival that matters for the design claim. A CAKE win on a metric is stated here verbatim; nothing is re-derived and nothing is argued away. CI overlap of the underlying seed samples is in the table above (`CI overlap?` column).

| scenario | metric where CAKE-static beats ACIQ | see column in the ACIQ-vs-every table |
| --- | --- | --- |
(none in these runs)

## ACIQ adaptation and capacity accuracy (from the same runs above)

| scenario | n | bind: drop -> first applied <=1.05x post-drop (s) | bind: drop -> first applied <=1.25x post-drop (s) | final estimate | configured end link | estimate error % |
| --- | --- | --- | --- | --- | --- | --- |
| s2b_ramp_100to30 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 26.21 +/- 2.03 | 30.0 +/- 0.0 | mean abs 13.3% (seed0: 21.55/30.0 (28.2% off)) |
| s2b_step_10 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 11.53 +/- 0.41 | 10.0 +/- 0.0 | mean abs 15.3% (seed0: 11.32/10.0 (13.2% off)) |
| s2b_step_50 | 10 | 1.45 (n=10) | 1.45 (n=10) | 42.35 +/- 1.31 | 50.0 +/- 0.0 | mean abs 15.3% (seed0: 41.02/50.0 (18.0% off)) |
| s2b_step_up_20to100 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | 13.05 (n=5) | 40.24 +/- 2.55 | 100.0 +/- 0.0 | mean abs 59.8% (seed0: 43.02/100.0 (57.0% off)) |
| s3_stress | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 81.06 +/- 2.18 | 100.0 +/- 0.0 | mean abs 18.9% (seed0: 86.44/100.0 (13.6% off)) |
| s7_down_100to15 | 10 | 4.30 (n=10) | 1.83 (n=10) | 13.58 +/- 0.08 | 15.0 +/- 0.0 | mean abs 9.5% (seed0: 13.69/15.0 (8.7% off)) |
| s7_down_100to8 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 9.00 +/- 0.40 | 8.0 +/- 0.0 | mean abs 12.5% (seed0: 9.58/8.0 (19.8% off)) |
| s7_rampup_30to100 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 50.94 +/- 3.18 | 100.0 +/- 0.0 | mean abs 49.1% (seed0: 44.11/100.0 (55.9% off)) |
| s7_up_20to60 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 33.91 +/- 1.17 | 60.0 +/- 0.0 | mean abs 43.5% (seed0: 35.67/60.0 (40.5% off)) |
| s7_up_30to100 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 52.77 +/- 2.05 | 100.0 +/- 0.0 | mean abs 47.2% (seed0: 51.08/100.0 (48.9% off)) |
## Controller resources (ACIQ adaptive runs only; from each result's resources block)

| scenario | n | cpu mean frac | decision p95 ms | decision max ms | max RSS bytes |
| --- | --- | --- | --- | --- | --- |
| s2b_ramp_100to30 | 10 | 0.0091 +/- 0.0002 | 82.71 +/- 4.29 | 118.68 +/- 32.83 | 30166221 +/- 756423 |
| s2b_step_10 | 10 | 0.0106 +/- 0.0002 | 145.39 +/- 28.90 | 214.75 +/- 57.29 | 29707469 +/- 674179 |
| s2b_step_50 | 10 | 0.0082 +/- 0.0002 | 82.37 +/- 4.67 | 105.88 +/- 7.20 | 29179494 +/- 426947 |
| s2b_step_up_20to100 | 10 | 0.0082 +/- 0.0003 | 88.86 +/- 4.97 | 133.11 +/- 34.27 | 30067507 +/- 757697 |
| s3_stress | 10 | 0.0094 +/- 0.0002 | 86.12 +/- 3.23 | 129.34 +/- 38.07 | 29404365 +/- 622379 |
| s7_down_100to15 | 10 | 0.0086 +/- 0.0002 | 82.08 +/- 3.42 | 100.62 +/- 8.02 | 28939469 +/- 533839 |
| s7_down_100to8 | 10 | 0.0111 +/- 0.0002 | 143.86 +/- 24.02 | 205.65 +/- 28.08 | 29563699 +/- 650330 |
| s7_rampup_30to100 | 10 | 0.0091 +/- 0.0002 | 92.63 +/- 7.50 | 143.95 +/- 30.55 | 30026547 +/- 759667 |
| s7_up_20to60 | 10 | 0.0085 +/- 0.0002 | 85.90 +/- 4.38 | 107.78 +/- 11.07 | 30119526 +/- 759219 |
| s7_up_30to100 | 10 | 0.0087 +/- 0.0002 | 87.68 +/- 4.63 | 133.80 +/- 37.47 | 30129357 +/- 753887 |
- CPU context (adaptive vs adaptive): CAKE-adaptive runs at 0.50x the ACIQ CPU fraction on the shared scenario(s): s2b_ramp_100to30 0.56x, s2b_step_10 0.46x, s2b_step_50 0.54x, s2b_step_up_20to100 0.47x, s3_stress 0.46x, s7_down_100to15 0.58x, s7_down_100to8 0.47x, s7_rampup_30to100 0.49x, s7_up_20to60 0.46x, s7_up_30to100 0.48x. The cause must be read from the artifacts (CPU profile, decision cadence), not assumed.

## Fairness detail (workload-rate Jain; per-class minima over ASSIGNED classes only, same scope for every mode)

| scenario | arm | n | jain mean +/- CI | demand-jain mean +/- CI | flows used | min over time (per label, via carrying class) |
| --- | --- | --- | --- | --- | --- | --- |
demand-jain: Jain over per-flow satisfied-demand ratios (achieved/demand, demand self-reported by the generator; elastic flows without a declared demand are excluded by definition -- see aciq/fairness.py). A scenario flows all-elastic has no such index and prints NOT AVAILABLE rather than a substitute.

Per-tick counter attribution (fix 18): ACIQ's tree has one leaf per class; the baselines' single-class tree carries the WHOLE link on the 1:50 leaf. New artefacts sample that aggregate under `unknown` (an aggregate can no longer masquerade as a software_update class); artefacts from before this change stored the same aggregate under `software_update`, and consumers that fall back to the legacy label must name it -- the post-drop bulk column does exactly that.

| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.982 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=30; call via unknown=30 |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.984 +/- 0.003 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=0.0716; call via unknown=0.0716; bulk via unknown=14.2; call via unknown=14.2; bulk via unknown=23.8; call via unknown=23.8 |
| s2b_ramp_100to30 | ACIQ (controller) | 10 | 0.998 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.846 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.96; call via unknown=9.96; bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.96; call via unknown=9.96 |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.936 +/- 0.002 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=0; call via unknown=0; bulk via unknown=0; call via unknown=0; bulk via unknown=0; call via unknown=0 |
| s2b_step_10 | ACIQ (controller) | 10 | 0.936 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 1.000 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=49.8; call via unknown=49.8; bulk via unknown=49.9; call via unknown=49.9; bulk via unknown=49.9; call via unknown=49.9 |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.993 +/- 0.003 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15.5; call via unknown=15.5; bulk via unknown=13.3; call via unknown=13.3; bulk via unknown=16.7; call via unknown=16.7 |
| s2b_step_50 | ACIQ (controller) | 10 | 1.000 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.683 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.98; call via unknown=9.98 |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.772 +/- 0.015 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15.8; call via unknown=15.8; bulk via unknown=14.6; call via unknown=14.6; bulk via unknown=15.8; call via unknown=15.8 |
| s2b_step_up_20to100 | ACIQ (controller) | 10 | 0.990 +/- 0.006 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.573 +/- 0.016 | 0.979 +/- 0.047 | 5.0 +/- 0.0 | bulk via unknown=49.9; game via unknown=49.9; tv1 via unknown=49.9; tv2 via unknown=49.9; tv3 via unknown=49.9; bulk via unknown=49.9 |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.478 +/- 0.023 | 0.979 +/- 0.047 | 5.0 +/- 0.0 | bulk via unknown=38.2; game via unknown=38.2; tv1 via unknown=38.2; tv2 via unknown=38.2; tv3 via unknown=38.2; bulk via unknown=64.3 |
| s3_stress | ACIQ (controller) | 10 | 0.443 +/- 0.009 | 0.979 +/- 0.047 | 5.0 +/- 0.0 | bulk=0; game via unknown=0; tv1 via unknown=0; tv2 via unknown=0; tv3 via unknown=0; bulk=0 |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.887 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15; bulk via unknown=15; call via unknown=15 |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.952 +/- 0.002 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=0; call via unknown=0; bulk via unknown=13.3; call via unknown=13.3; bulk via unknown=13.3; call via unknown=13.3 |
| s7_down_100to15 | ACIQ (controller) | 10 | 0.947 +/- 0.005 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.828 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=7.97; call via unknown=7.97; bulk via unknown=7.98; call via unknown=7.98; bulk via unknown=7.98; call via unknown=7.98 |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.923 +/- 0.005 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=0.0579; call via unknown=0.0579; bulk via unknown=0.0045; call via unknown=0.0045; bulk via unknown=0.012; call via unknown=0.012 |
| s7_down_100to8 | ACIQ (controller) | 10 | 0.925 +/- 0.004 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.764 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=14.9; call via unknown=14.9; bulk via unknown=15; call via unknown=15; bulk via unknown=14.9; call via unknown=14.9 |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.887 +/- 0.020 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=17.8; call via unknown=17.8; bulk via unknown=23.2; call via unknown=23.2; bulk via unknown=23.4; call via unknown=23.4 |
| s7_rampup_30to100 | ACIQ (controller) | 10 | 0.998 +/- 0.002 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.683 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.97; call via unknown=9.97; bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.99; call via unknown=9.99 |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.776 +/- 0.011 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=16.1; call via unknown=16.1; bulk via unknown=15.6; call via unknown=15.6; bulk via unknown=14.8; call via unknown=14.8 |
| s7_up_20to60 | ACIQ (controller) | 10 | 0.972 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | 0.764 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=14.9; call via unknown=14.9; bulk via unknown=14.9; call via unknown=14.9; bulk via unknown=15; call via unknown=15 |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | 0.842 +/- 0.039 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=23.4; call via unknown=23.4; bulk via unknown=13.8; call via unknown=13.8; bulk via unknown=21.9; call via unknown=21.9 |
| s7_up_30to100 | ACIQ (controller) | 10 | 0.997 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |

Starvation (TASK 5b, fixed basis): per LABEL, over the class the data says carried the traffic (assigned class, or the router's `unknown`/legacy aggregate when the label's traffic rode there -- chosen by highest mean, and the carrying class is named). A label starved in tick t if its per-tick goodput fell below 20% of its REGIME median -- in a drop scenario the median is the POST-DROP regime's own median, so the shaped link rate can never masquerade as starvation; without a drop it is the whole window's. The cell lists the starved timestamps counted over seeds. With no series at all the cell prints NOT AVAILABLE, never an empty claim.

| scenario | arm | starved ticks per label (via carrying class) |
| --- | --- | --- |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 1 ticks over 1 seed(s), first t=55.0; call via unknown: 1 ticks over 1 seed(s), first t=55.0 |
| s2b_ramp_100to30 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 312 ticks over 10 seed(s), first t=5.4 |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 7 ticks over 6 seed(s), first t=34.2; call via unknown: 7 ticks over 6 seed(s), first t=34.2 |
| s2b_step_10 | ACIQ (controller) | bulk via bulk_download: 33 ticks over 10 seed(s), first t=2.1; call via unknown: 55 ticks over 10 seed(s), first t=5.3 |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 220 ticks over 10 seed(s), first t=5.3 |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 295 ticks over 10 seed(s), first t=5.3 |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 49 seed x label series (regime-aware threshold, declared window) |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 49 seed x label series (regime-aware threshold, declared window) |
| s3_stress | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; game via unknown: 79 ticks over 10 seed(s), first t=19.3; tv1 via adaptive_video_streaming: 2 ticks over 1 seed(s), first t=2.1; tv1 via unknown: 71 ticks over 9 seed(s), first t=19.3; tv2 via adaptive_video_streaming: 2 ticks over 1 seed(s), first t=2.1; tv2 via unknown: 63 ticks over 8 seed(s), first t=19.3; tv3 via adaptive_video_streaming: 2 ticks over 1 seed(s), first t=2.1; tv3 via unknown: 71 ticks over 9 seed(s), first t=19.3 |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 10 ticks over 6 seed(s), first t=23.9; call via unknown: 10 ticks over 6 seed(s), first t=23.9 |
| s7_down_100to15 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 208 ticks over 10 seed(s), first t=5.4 |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 8 ticks over 8 seed(s), first t=22.8; call via unknown: 8 ticks over 8 seed(s), first t=22.8 |
| s7_down_100to8 | ACIQ (controller) | bulk via bulk_download: 27 ticks over 10 seed(s), first t=2.1; call via unknown: 50 ticks over 10 seed(s), first t=5.4 |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_rampup_30to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.2; call via unknown: 302 ticks over 10 seed(s), first t=5.4 |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk via unknown: 1 ticks over 1 seed(s), first t=9.3; call via unknown: 1 ticks over 1 seed(s), first t=9.3 |
| s7_up_20to60 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 278 ticks over 10 seed(s), first t=5.3 |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s7_up_30to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 300 ticks over 10 seed(s), first t=5.3 |

Warm-up exclusion (declared): every per-tick window above starts at t >= 2.0 s. The diagnosis round (fix 17's diagnosis.md) shows the first ~2 s of per-tick counter rates are a transmit/counter ramp artefact, not traffic behaviour; dropping those ticks removes nothing else. The window boundary is a declared constant in this generator, not a per-run choice.

Further declared exclusions (TASK 5b): (1) ticks at or beyond the label generator's own measured lifetime (`elapsed_s`, capped by the scenario duration) -- a verdict about a label after its traffic stopped describes nothing about the label; (2) ticks whose link counters went BACKWARDS -- a qdisc del/re-add resets every counter on the device, so that tick's per-class goodput is a reset artefact, not a delivery gap. Stars and minima are computed over what remains; nothing is excluded silently.

## Step/demand generalization band (evaluation-only; docs/evidence/s2b-params.md + docs/evidence/round3-params.md, declared BEFORE these runs)

The shipped controller runs unchanged on capacity changes it was never tuned on: two down-step magnitudes, a 5x up-step, and a continuous 20 s ramp -- plus the round-3 DEV shapes (s7_* up/down steps and ramps, s3_stress) and the two queue-discipline-only arms (CAKE-conservative / CAKE-adaptive). Seeds 800-809 configured per scenario (the DEV band, seed names in each run dir). CAKE-static is applied once at launch and never re-applied: that is its declared semantics, and this band exists to surface the consequences. Definitions: bind = first tick at which the applied tree sits within 10% of the link's truth and stays there (down-moves only; up-moves print `n/a (up-step)` and are judged by the utilization column: applied/truth and receiver delivered/truth over the final third); tracking error = mean |applied - truth| over the ramp window; estimate error = same over the final third. Where ACIQ fails, the row says so.

Engine commit at generation time: `912a6e2ec9dd` — a run whose result carries a different commit_hash is SUPERSEDED, listed under 'commit provenance' below and never pooled into a numeric cell with a newer commit.

### s2b_step_50

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 50.00 +/- 0.00 | 167.19 +/- 1.61 | 47.66 +/- 0.11 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 50.00 +/- 0.00 | 15.09 +/- 4.49 | 22.34 +/- 5.67 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 12.5 +/- 1.5 | 6.60 +/- 2.17 | 7.52 +/- 4.11 | 31.20 +/- 1.91 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 41.2 vs truth 50.0, 18% off truth, confidence 0.15; final tick: UNSATURATED (estimator not saturated at the end regime), applied 39.0 vs truth 50.0, 22% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 47.8 vs truth 50.0, 4% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 35.9 vs truth 50.0, 28% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 46.2 vs truth 50.0, 8% off truth, confidence 0.30; final tick: UNSATURATED (estimator not saturated at the end regime), applied 43.9 vs truth 50.0, 12% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 46.1 vs truth 50.0, 8% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 44.3 vs truth 50.0, 11% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 41.5 vs truth 50.0, 17% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 44.8 vs truth 50.0, 10% off truth, confidence 0.25 |

### s2b_step_10

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 90.00 +/- 0.00 | 81.51 +/- 0.90 | 9.45 +/- 0.02 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 90.00 +/- 0.00 | 73.61 +/- 1.80 | 9.27 +/- 0.14 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 4.00 +/- 0.00 | 81.07 +/- 0.89 | 7.24 +/- 0.16 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 10.0, 40% off truth, confidence 0.40 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 10.0, 40% off truth, confidence 0.25 (n=8) |

### s2b_step_up_20to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 80.00 +/- 0.00 | 1.83 +/- 0.03 | 9.37 +/- 0.08 | appl 0.20 +/- 0.00 / delv 0.09 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 80.00 +/- 0.00 | 1.90 +/- 0.05 | 14.13 +/- 1.48 | appl 0.20 +/- 0.00 / delv 0.14 +/- 0.01 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 16.02 +/- 4.70 | 3.50 +/- 3.16 | 61.42 +/- 2.91 | appl 0.97 +/- 0.05 / delv 0.61 +/- 0.03 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 87.7 vs truth 100.0, 12% off truth, confidence 0.15; final tick: UNSATURATED (estimator not saturated at the end regime), applied 22.1 vs truth 100.0, 78% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 135.1 vs truth 100.0, 35% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 132.8 vs truth 100.0, 33% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 133.7 vs truth 100.0, 34% off truth, confidence 0.20; final tick: UNSATURATED (estimator not saturated at the end regime), applied 89.1 vs truth 100.0, 11% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 86.6 vs truth 100.0, 13% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 102.3 vs truth 100.0, 2% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 93.9 vs truth 100.0, 6% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 86.6 vs truth 100.0, 13% off truth, confidence 0.25 |

### s2b_ramp_100to30

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 109.47 +/- 1.37 | 28.58 +/- 0.00 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 18.57 +/- 5.03 | 14.95 +/- 2.04 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 32.8 +/- 3.5 | 3.15 +/- 1.45 | 24.13 +/- 1.20 | 19.02 +/- 1.04 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 21.6 vs truth 30.0, 28% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 28.2 vs truth 30.0, 6% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 23.7 vs truth 30.0, 21% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 31.1 vs truth 30.0, 4% off truth, confidence 0.20; final tick: UNSATURATED (estimator not saturated at the end regime), applied 27.6 vs truth 30.0, 8% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 23.5 vs truth 30.0, 22% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 28.3 vs truth 30.0, 6% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 27.7 vs truth 30.0, 8% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 31.3 vs truth 30.0, 4% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 22.7 vs truth 30.0, 24% off truth, confidence 0.10 |

### s7_up_20to60

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 40.00 +/- 0.00 | 1.86 +/- 0.10 | 9.37 +/- 0.09 | appl 0.33 +/- 0.00 / delv 0.16 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 40.00 +/- 0.00 | 1.96 +/- 0.10 | 14.84 +/- 1.40 | appl 0.33 +/- 0.00 / delv 0.25 +/- 0.02 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 5.49 +/- 0.24 | 10.09 +/- 3.74 | 40.75 +/- 1.85 | appl 0.99 +/- 0.03 / delv 0.68 +/- 0.03 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 55.4 vs truth 60.0, 8% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 55.0 vs truth 60.0, 8% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 55.2 vs truth 60.0, 8% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 61.8 vs truth 60.0, 3% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 54.7 vs truth 60.0, 9% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 54.4 vs truth 60.0, 9% off truth, confidence 0.25 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 54.0 vs truth 60.0, 10% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 54.2 vs truth 60.0, 10% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 52.8 vs truth 60.0, 12% off truth, confidence 0.25 |

### s7_up_30to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | n/a (up-step) | 70.00 +/- 0.00 | 1.38 +/- 0.06 | 14.14 +/- 0.08 | appl 0.30 +/- 0.00 / delv 0.14 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | n/a (up-step) | 70.00 +/- 0.00 | 1.71 +/- 0.08 | 20.11 +/- 4.03 | appl 0.30 +/- 0.00 / delv 0.20 +/- 0.04 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | n/a (up-step) | 12.26 +/- 5.08 | 11.11 +/- 4.52 | 69.02 +/- 4.61 | appl 1.06 +/- 0.04 / delv 0.69 +/- 0.05 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 145.8 vs truth 100.0, 46% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 102.7 vs truth 100.0, 3% off truth, confidence 0.25 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 146.5 vs truth 100.0, 47% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 102.3 vs truth 100.0, 2% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 118.5 vs truth 100.0, 19% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 146.7 vs truth 100.0, 47% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 95.7 vs truth 100.0, 4% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 102.4 vs truth 100.0, 2% off truth, confidence 0.15; final tick: UNSATURATED (estimator not saturated at the end regime), applied 146.4 vs truth 100.0, 46% off truth, confidence 0.25 |

### s7_rampup_30to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 1.47 +/- 0.05 | 14.22 +/- 0.01 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 1.73 +/- 0.07 | 24.19 +/- 2.31 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 53.2 +/- 4.6 | 10.60 +/- 2.60 | 8.94 +/- 4.82 | 66.71 +/- 4.79 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 90.8 vs truth 100.0, 9% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 102.4 vs truth 100.0, 2% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 104.0 vs truth 100.0, 4% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 91.0 vs truth 100.0, 9% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 94.5 vs truth 100.0, 6% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 144.7 vs truth 100.0, 45% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 103.4 vs truth 100.0, 3% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 103.6 vs truth 100.0, 4% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 93.6 vs truth 100.0, 6% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 92.1 vs truth 100.0, 8% off truth, confidence 0.00 |

### s7_down_100to15

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 85.00 +/- 0.00 | 87.56 +/- 0.49 | 14.20 +/- 0.07 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 85.00 +/- 0.00 | 28.18 +/- 5.65 | 12.34 +/- 0.24 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 13.8 +/- 1.2 | 1.00 +/- 0.00 | 41.23 +/- 6.26 | 10.39 +/- 0.25 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 15.0, 7% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 15.0, 7% off truth, confidence 0.55 (n=3); final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 15.0, 7% off truth, confidence 0.40 (n=3); final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 15.0, 7% off truth, confidence 0.45; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 15.0, 7% off truth, confidence 0.50; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 15.0, 7% off truth, confidence 0.35 |

### s7_down_100to8

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | up-step utilization final third (applied/truth, delivered/truth) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 92.00 +/- 0.00 | 78.06 +/- 0.90 | 7.53 +/- 0.02 | - | honesty row declared for ACIQ only |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 92.00 +/- 0.00 | 76.86 +/- 0.65 | 7.46 +/- 0.11 | - | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 6.00 +/- 0.00 | 81.39 +/- 0.77 | 5.87 +/- 0.20 | - | final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 8.0, 75% off truth, confidence 0.25 (n=8); final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 8.0, 75% off truth, confidence 0.40 (n=2) |

### s3_stress

| arm | n | call p95 whole-run (ms) | game p95 whole-run (ms) | bulk receiver mean inst (Mbps) | tv1 / tv2 / tv3 receiver mean inst (Mbps) | overload note (loaded vs capacity) |
| --- | --- | --- | --- | --- | --- | --- |
| CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | NOT AVAILABLE | 2.10 +/- 0.27 | 31.68 +/- 0.99 | 4.40 / 4.40 / 4.40; 4.44 / 4.40; 4.39 / 4.39 / 4.39; 4.40 / 4.40 / 4.40; 4.50 / 4.49 / 4.49; 4.40 / 4.40 / 4.40; 4.61 / 4.61 / 4.61; 4.61 / 4.61 / 4.61; 4.39 / 4.39 / 4.39; 4.50 / 4.50 / 4.50 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |
| CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | NOT AVAILABLE | 6.17 +/- 4.67 | 54.03 +/- 5.34 | 4.30 / 4.28 / 4.30; 4.44 / 4.40; 4.29 / 4.29 / 4.29; 4.30 / 4.30 / 4.30; 4.40 / 4.40 / 4.40; 4.40 / 4.40 / 4.39; 4.50 / 4.50 / 4.50; 4.50 / 4.50 / 4.50; 4.30 / 4.30 / 4.30; 4.50 / 4.50 / 4.50 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |
| ACIQ (controller) | 10 | NOT AVAILABLE | 17.77 +/- 1.92 | 60.95 +/- 1.45 | 4.12 / 4.12 / 4.12; 4.15 / 4.12; 4.13 / 4.13 / 4.13; 4.13 / 4.13 / 4.13; 4.21 / 4.21 / 4.21; 4.21 / 4.21 / 4.21; 4.31 / 4.31 / 4.31; 4.30 / 4.30 / 4.31; 4.12 / 4.12 / 4.12; 4.21 / 4.21 / 4.21 | flat link truth 100 Mbps; demand spans game + 3 tvs + bulk (see round3-params) |

## Starvation, receiver side (every arm, per-second sink logs)

| scenario | arm | label; starved inst ticks over seeds (longest streak) |
| --- | --- | --- |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 5 tick(s) over 10 seed(s), longest streak 1 s; call: 18 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 16 tick(s) over 10 seed(s), longest streak 2 s; call: 30 tick(s) over 10 seed(s), longest streak 4 s |
| s2b_ramp_100to30 | ACIQ (controller) | bulk: 39 tick(s) over 10 seed(s), longest streak 4 s; call: 51 tick(s) over 10 seed(s), longest streak 6 s |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 3 tick(s) over 10 seed(s), longest streak 1 s; call: 10 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 11 tick(s) over 10 seed(s), longest streak 2 s; call: 22 tick(s) over 10 seed(s), longest streak 3 s |
| s2b_step_10 | ACIQ (controller) | bulk: 44 tick(s) over 10 seed(s), longest streak 5 s; call: 55 tick(s) over 10 seed(s), longest streak 6 s |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 12 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 12 tick(s) over 10 seed(s), longest streak 2 s; call: 21 tick(s) over 10 seed(s), longest streak 3 s |
| s2b_step_50 | ACIQ (controller) | bulk: 27 tick(s) over 10 seed(s), longest streak 3 s; call: 35 tick(s) over 10 seed(s), longest streak 4 s |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 5 tick(s) over 10 seed(s), longest streak 1 s; call: 13 tick(s) over 10 seed(s), longest streak 2 s |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 13 tick(s) over 10 seed(s), longest streak 2 s; call: 21 tick(s) over 10 seed(s), longest streak 3 s |
| s2b_step_up_20to100 | ACIQ (controller) | bulk: 42 tick(s) over 10 seed(s), longest streak 5 s; call: 51 tick(s) over 10 seed(s), longest streak 6 s |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 9 tick(s) over 10 seed(s), longest streak 1 s; game: 27 tick(s) over 10 seed(s), longest streak 3 s; tv1: 22 tick(s) over 10 seed(s), longest streak 3 s; tv2: 14 tick(s) over 9 seed(s), longest streak 2 s; tv3: 14 tick(s) over 10 seed(s), longest streak 2 s |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 23 tick(s) over 10 seed(s), longest streak 7 s; game: 34 tick(s) over 10 seed(s), longest streak 4 s; tv1: 26 tick(s) over 9 seed(s), longest streak 4 s; tv2: 23 tick(s) over 10 seed(s), longest streak 3 s; tv3: 21 tick(s) over 10 seed(s), longest streak 3 s |
| s3_stress | ACIQ (controller) | bulk: 37 tick(s) over 10 seed(s), longest streak 4 s; game: 55 tick(s) over 10 seed(s), longest streak 6 s; tv1: 51 tick(s) over 10 seed(s), longest streak 6 s; tv2: 40 tick(s) over 9 seed(s), longest streak 5 s; tv3: 43 tick(s) over 10 seed(s), longest streak 5 s |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 0 tick(s) over 10 seed(s), longest streak 0 s; call: 12 tick(s) over 10 seed(s), longest streak 2 s |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 9 tick(s) over 10 seed(s), longest streak 1 s; call: 21 tick(s) over 10 seed(s), longest streak 3 s |
| s7_down_100to15 | ACIQ (controller) | bulk: 22 tick(s) over 10 seed(s), longest streak 3 s; call: 34 tick(s) over 10 seed(s), longest streak 4 s |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 1 tick(s) over 10 seed(s), longest streak 1 s; call: 9 tick(s) over 10 seed(s), longest streak 2 s |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 9 tick(s) over 10 seed(s), longest streak 2 s; call: 24 tick(s) over 10 seed(s), longest streak 3 s |
| s7_down_100to8 | ACIQ (controller) | bulk: 41 tick(s) over 10 seed(s), longest streak 5 s; call: 57 tick(s) over 10 seed(s), longest streak 6 s |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 7 tick(s) over 10 seed(s), longest streak 1 s; call: 14 tick(s) over 10 seed(s), longest streak 2 s |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 15 tick(s) over 10 seed(s), longest streak 2 s; call: 24 tick(s) over 10 seed(s), longest streak 3 s |
| s7_rampup_30to100 | ACIQ (controller) | bulk: 47 tick(s) over 10 seed(s), longest streak 6 s; call: 55 tick(s) over 10 seed(s), longest streak 6 s |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 8 tick(s) over 10 seed(s), longest streak 1 s; call: 16 tick(s) over 10 seed(s), longest streak 2 s |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 13 tick(s) over 10 seed(s), longest streak 2 s; call: 22 tick(s) over 10 seed(s), longest streak 3 s |
| s7_up_20to60 | ACIQ (controller) | bulk: 45 tick(s) over 10 seed(s), longest streak 5 s; call: 53 tick(s) over 10 seed(s), longest streak 6 s |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | bulk: 4 tick(s) over 10 seed(s), longest streak 1 s; call: 13 tick(s) over 10 seed(s), longest streak 2 s |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | bulk: 14 tick(s) over 10 seed(s), longest streak 2 s; call: 22 tick(s) over 10 seed(s), longest streak 3 s |
| s7_up_30to100 | ACIQ (controller) | bulk: 43 tick(s) over 10 seed(s), longest streak 5 s; call: 52 tick(s) over 10 seed(s), longest streak 6 s |


## Commit provenance (declared; every run's engine hash)

| scenario | arm | n runs | commit_hash | verdict |
| --- | --- | --- | --- | --- |
| s2b_ramp_100to30 | ACIQ (controller) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s2b_ramp_100to30 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s2b_ramp_100to30 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s2b_step_10 | ACIQ (controller) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s2b_step_10 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s2b_step_10 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s2b_step_50 | ACIQ (controller) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s2b_step_50 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s2b_step_50 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | ACIQ (controller) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s2b_step_up_20to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s3_stress | ACIQ (controller) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s3_stress | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s3_stress | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_down_100to15 | ACIQ (controller) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_down_100to15 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_down_100to15 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_down_100to8 | ACIQ (controller) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_down_100to8 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_down_100to8 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | ACIQ (controller) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_rampup_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_up_20to60 | ACIQ (controller) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_up_20to60 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_up_20to60 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_up_30to100 | ACIQ (controller) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_up_30to100 | CAKE-adaptive (same estimator/governor chain, single-class CAKE rebuild per decision; queue discipline is the only difference) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |
| s7_up_30to100 | CAKE-conservative (0.50x pre-change link, static; the declared undershoot probe arm - round-3 params) | 10 | `912a6e2ec9dd` | current: trusted for a frozen final band claim |

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

