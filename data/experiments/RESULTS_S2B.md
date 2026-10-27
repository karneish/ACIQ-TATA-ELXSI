# Results (generated, no summarised files consulted)

Runs root: `data/runs_s2b` | runs used: 160 | scenarios: s2b_ramp_100to30, s2b_step_10, s2b_step_50, s2b_step_up_20to100

## Delay and throughput, every scenario x arm (mean +/- 95% CI over seeds; t(9)=2.262 for n=10)

Every block below carries an explicit band label, derived from the seed family recorded at load time: `POST-FIX` (seeds 200-209, the controller after the redesign commits), `PRE-FIX` (legacy seeds 0-9/42-51), `DEV` and `EVAL` (the task-2 protocol: parameters were fixed on the DEV band seeds 400-409 BEFORE the EVAL band seeds 500-509 was run ONCE; nothing between them was tuned). A reader never inherits a number of unknown provenance: the label sits directly above the table. The comparison sections further down use the primary band only.

Bulk has TWO columns on purpose (TASK 5a): `sender` is what the generator pushed, `receiver/sink` is what the receiver's sink log totalled -- the delivered number, used for any bulk claim. The post-drop column stays on the TREE counters and is named so: the three are different instruments and are never blended.

### s2b_ramp_100to30 (primary band: EVAL (800-809))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 822.54 +/- 0.13 | 19.25 +/- 0.09 | 1.303 +/- 0.017 | NOT AVAILABLE | 53.35 +/- 0.01 | 52.63 +/- 0.01 | (no drop scenario) | 0.999 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 134.62 +/- 2.18 | 0.86 +/- 0.01 | 0.570 +/- 0.097 | NOT AVAILABLE | 52.03 +/- 0.01 | 51.33 +/- 0.01 | (no drop scenario) | 1.000 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 132.80 +/- 1.55 | 0.86 +/- 0.01 | 0.477 +/- 0.089 | NOT AVAILABLE | 52.03 +/- 0.01 | 51.33 +/- 0.00 | (no drop scenario) | 1.000 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 69.40 +/- 5.42 | 0.56 +/- 0.02 | 0.080 +/- 0.042 | NOT AVAILABLE | 43.35 +/- 0.48 | 42.88 +/- 0.51 | (no drop scenario) | 0.995 +/- 0.001 | NOT AVAILABLE |

### s2b_step_10 (primary band: EVAL (800-809))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 246.63 +/- 0.19 | 3.38 +/- 0.15 | 15.040 +/- 0.208 | NOT AVAILABLE | 34.48 +/- 0.02 | NOT AVAILABLE | 10.78 +/- 0.01 | 0.967 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 84.22 +/- 0.39 | 1.07 +/- 0.01 | 1.065 +/- 0.191 | NOT AVAILABLE | 32.15 +/- 0.02 | 31.62 +/- 0.02 | 10.07 +/- 0.01 | 0.955 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 5.29 +/- 0.02 | 1.08 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 8.99 +/- 0.00 | 8.97 +/- 0.00 | 9.33 +/- 0.01 | 0.674 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 83.20 +/- 1.31 | 1.12 +/- 0.03 | 0.650 +/- 0.204 | NOT AVAILABLE | 27.74 +/- 0.47 | 27.28 +/- 0.49 | 10.08 +/- 0.20 | 0.924 +/- 0.004 | NOT AVAILABLE |

### s2b_step_50 (primary band: EVAL (800-809))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 496.35 +/- 0.08 | 15.96 +/- 0.11 | 1.145 +/- 0.036 | NOT AVAILABLE | 61.85 +/- 0.01 | 61.09 +/- 0.01 | 50.12 +/- 0.04 | 0.989 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 137.35 +/- 1.87 | 0.84 +/- 0.02 | 0.490 +/- 0.110 | NOT AVAILABLE | 60.25 +/- 0.01 | 59.52 +/- 0.01 | 49.70 +/- 0.04 | 0.991 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 2.02 +/- 0.12 | 0.47 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 45.39 +/- 0.00 | 45.32 +/- 0.00 | 46.46 +/- 0.03 | 0.998 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 39.97 +/- 12.56 | 0.62 +/- 0.06 | 0.055 +/- 0.076 | NOT AVAILABLE | 53.03 +/- 0.99 | 52.65 +/- 0.91 | 45.76 +/- 1.41 | 0.999 +/- 0.001 | NOT AVAILABLE |

### s2b_step_up_20to100 (primary band: EVAL (800-809))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 563.49 +/- 5.31 | 1.01 +/- 0.06 | 2.130 +/- 0.107 | NOT AVAILABLE | 19.49 +/- 0.07 | 19.02 +/- 0.00 | 19.99 +/- 0.02 | 0.838 +/- 0.001 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 2.63 +/- 0.02 | 0.38 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.12 +/- 0.01 | 18.06 +/- 0.00 | 18.63 +/- 0.02 | 0.820 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 2.65 +/- 0.03 | 0.39 +/- 0.02 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.12 +/- 0.00 | 18.06 +/- 0.00 | 18.67 +/- 0.08 | 0.820 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 1.72 +/- 0.08 | 0.29 +/- 0.04 | 0.005 +/- 0.011 | NOT AVAILABLE | 13.84 +/- 0.48 | 13.79 +/- 0.48 | 13.84 +/- 0.63 | 0.757 +/- 0.008 | NOT AVAILABLE |

## ACIQ vs every arm (positive % is better ACIQ on the metric at the head of the column; a cell like `41.0x` is the multiplicative factor when the baseline is so close to zero that a percentage would mislead)

| scenario | vs arm | call p95 delta % | CI overlap? | bulk delta % | CI overlap? |
| --- | --- | --- | --- | --- | --- |
Bulk compares are POST-DROP ONLY in scenarios with a capacity drop (same `bulk_mbps` whole-run mean otherwise): the whole-run number dilutes the post-drop regime with a saturated prefix, which is the opposite of the decision those scenarios exist to measure.

| s2b_ramp_100to30 | B0 (default router, pfifo) | +91.6 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_ramp_100to30 | CAKE-static (95% of pre-drop link, set and forget) | +48.4 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_ramp_100to30 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | +47.7 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2b_step_10 | B0 (default router, pfifo) | +66.3 | disjoint | -6.5 | disjoint |
| s2b_step_10 | CAKE-static (95% of pre-drop link, set and forget) | +1.2 | overlap | +0.2 | overlap |
| s2b_step_10 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | -1472.6 | disjoint | +8.1 | disjoint |
| s2b_step_50 | B0 (default router, pfifo) | +91.9 | disjoint | -8.7 | disjoint |
| s2b_step_50 | CAKE-static (95% of pre-drop link, set and forget) | +70.9 | disjoint | -7.9 | disjoint |
| s2b_step_50 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | -1879.1 | disjoint | -1.5 | overlap |
| s2b_step_up_20to100 | B0 (default router, pfifo) | 328.3x | disjoint | -30.7 | disjoint |
| s2b_step_up_20to100 | CAKE-static (95% of pre-drop link, set and forget) | +34.9 | disjoint | -25.7 | disjoint |
| s2b_step_up_20to100 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | +35.3 | disjoint | -25.9 | disjoint |

## Where ACIQ is worse (the honest column)

Every row above where ACIQ's signed delta is negative, collected so a CAKE win cannot hide behind the aggregate. Empty means no such pair exists in the runs found.

| scenario | vs arm | metric where ACIQ is worse |
| --- | --- | --- |
| s2b_step_10 | B0 (default router, pfifo) | post-drop bulk Mbps -6.5 |
| s2b_step_10 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | call p95 -1472.6 |
| s2b_step_50 | B0 (default router, pfifo) | post-drop bulk Mbps -8.7 |
| s2b_step_50 | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -7.9 |
| s2b_step_50 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | call p95 -1879.1 and post-drop bulk Mbps -1.5 |
| s2b_step_up_20to100 | B0 (default router, pfifo) | post-drop bulk Mbps -30.7 |
| s2b_step_up_20to100 | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -25.7 |
| s2b_step_up_20to100 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | post-drop bulk Mbps -25.9 |

## Where CAKE-static wins

The honest column above lists every rival; this one isolates the set-and-forget rival that matters for the design claim. A CAKE win on a metric is stated here verbatim; nothing is re-derived and nothing is argued away. CI overlap of the underlying seed samples is in the table above (`CI overlap?` column).

| scenario | metric where CAKE-static beats ACIQ | see column in the ACIQ-vs-every table |
| --- | --- | --- |
| s2b_step_50 | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -7.9 |
| s2b_step_up_20to100 | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -25.7 |

## ACIQ adaptation and capacity accuracy (from the same runs above)

| scenario | n | bind: drop -> first applied <=1.05x post-drop (s) | bind: drop -> first applied <=1.25x post-drop (s) | final estimate | configured end link | estimate error % |
| --- | --- | --- | --- | --- | --- | --- |
| s2b_ramp_100to30 | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 25.62 +/- 1.31 | 30.0 +/- 0.0 | mean abs 14.6% (seed0: 24.12/30.0 (19.6% off)) |
| s2b_step_10 | 10 | 17.34 (n=2) | 11.61 (n=2) | 10.83 +/- 0.37 | 10.0 +/- 0.0 | mean abs 9.0% (seed0: 11.06/10.0 (10.6% off)) |
| s2b_step_50 | 10 | 17.34 (n=10) | 7.93 (n=10) | 49.56 +/- 2.52 | 50.0 +/- 0.0 | mean abs 5.5% (seed0: 55.99/50.0 (12.0% off)) |
| s2b_step_up_20to100 | 10 | 5.04 (n=5) | 5.04 (n=5) | 17.54 +/- 0.76 | 100.0 +/- 0.0 | mean abs 82.5% (seed0: 18.36/100.0 (81.6% off)) |
## Controller resources (ACIQ adaptive runs only; from each result's resources block)

| scenario | n | cpu mean frac | decision p95 ms | decision max ms | max RSS bytes |
| --- | --- | --- | --- | --- | --- |
| s2b_ramp_100to30 | 10 | 0.0079 +/- 0.0001 | 73.28 +/- 0.50 | 77.96 +/- 3.09 | 29705011 +/- 729680 |
| s2b_step_10 | 10 | 0.0141 +/- 0.0003 | 179.79 +/- 4.27 | 203.04 +/- 11.05 | 28755968 +/- 539344 |
| s2b_step_50 | 10 | 0.0145 +/- 0.0004 | 198.80 +/- 13.13 | 216.45 +/- 24.37 | 28908749 +/- 550290 |
| s2b_step_up_20to100 | 10 | 0.0133 +/- 0.0004 | 102.85 +/- 52.67 | 184.61 +/- 21.73 | 28719514 +/- 537457 |

## Fairness detail (workload-rate Jain; per-class minima over ASSIGNED classes only, same scope for every mode)

| scenario | arm | n | jain mean +/- CI | demand-jain mean +/- CI | flows used | min over time (per label, via carrying class) |
| --- | --- | --- | --- | --- | --- | --- |
demand-jain: Jain over per-flow satisfied-demand ratios (achieved/demand, demand self-reported by the generator; elastic flows without a declared demand are excluded by definition -- see aciq/fairness.py). A scenario flows all-elastic has no such index and prints NOT AVAILABLE rather than a substitute.

Per-tick counter attribution (fix 18): ACIQ's tree has one leaf per class; the baselines' single-class tree carries the WHOLE link on the 1:50 leaf. New artefacts sample that aggregate under `unknown` (an aggregate can no longer masquerade as a software_update class); artefacts from before this change stored the same aggregate under `software_update`, and consumers that fall back to the legacy label must name it -- the post-drop bulk column does exactly that.

| s2b_ramp_100to30 | B0 (default router, pfifo) | 10 | 0.999 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=29.9; call via unknown=29.9 |
| s2b_ramp_100to30 | CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.000 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=30; call via unknown=30; bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=29.9; call via unknown=29.9 |
| s2b_ramp_100to30 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 1.000 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=29.9; call via unknown=29.9; bulk via unknown=29.9; call via unknown=29.9 |
| s2b_ramp_100to30 | ACIQ (controller) | 10 | 0.995 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_10 | B0 (default router, pfifo) | 10 | 0.967 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.87; call via unknown=9.87; bulk via unknown=9.94; call via unknown=9.94; bulk via unknown=9.87; call via unknown=9.87 |
| s2b_step_10 | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.955 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.98; call via unknown=9.98; bulk via unknown=9.98; call via unknown=9.98 |
| s2b_step_10 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.674 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=9.49; call via unknown=9.49; bulk via unknown=9.49; call via unknown=9.49; bulk via unknown=9.48; call via unknown=9.48 |
| s2b_step_10 | ACIQ (controller) | 10 | 0.924 +/- 0.004 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_50 | B0 (default router, pfifo) | 10 | 0.989 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=49.8; call via unknown=49.8; bulk via unknown=49.8; call via unknown=49.8; bulk via unknown=49.8; call via unknown=49.8 |
| s2b_step_50 | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.991 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=49.9; call via unknown=49.9; bulk via unknown=49.9; call via unknown=49.9; bulk via unknown=49.9; call via unknown=49.9 |
| s2b_step_50 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.998 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=47.4; call via unknown=47.4; bulk via unknown=47.5; call via unknown=47.5; bulk via unknown=47.4; call via unknown=47.4 |
| s2b_step_50 | ACIQ (controller) | 10 | 0.999 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |
| s2b_step_up_20to100 | B0 (default router, pfifo) | 10 | 0.838 +/- 0.001 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=19.9; call via unknown=19.9; bulk via unknown=19.9; call via unknown=19.9 |
| s2b_step_up_20to100 | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.820 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19; call via unknown=19; bulk via unknown=18.9; call via unknown=18.9; bulk via unknown=19; call via unknown=19 |
| s2b_step_up_20to100 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.820 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=18.9; call via unknown=18.9; bulk via unknown=19; call via unknown=19; bulk via unknown=18.9; call via unknown=18.9 |
| s2b_step_up_20to100 | ACIQ (controller) | 10 | 0.757 +/- 0.008 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk=0; call via unknown=0; bulk=0; call via unknown=0; bulk=0; call via unknown=0 |

Starvation (TASK 5b, fixed basis): per LABEL, over the class the data says carried the traffic (assigned class, or the router's `unknown`/legacy aggregate when the label's traffic rode there -- chosen by highest mean, and the carrying class is named). A label starved in tick t if its per-tick goodput fell below 20% of its REGIME median -- in a drop scenario the median is the POST-DROP regime's own median, so the shaped link rate can never masquerade as starvation; without a drop it is the whole window's. The cell lists the starved timestamps counted over seeds. With no series at all the cell prints NOT AVAILABLE, never an empty claim.

| scenario | arm | starved ticks per label (via carrying class) |
| --- | --- | --- |
| s2b_ramp_100to30 | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_ramp_100to30 | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_ramp_100to30 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_ramp_100to30 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.1; call via unknown: 326 ticks over 10 seed(s), first t=5.3 |
| s2b_step_10 | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_10 | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_10 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_10 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.2; call via unknown: 177 ticks over 10 seed(s), first t=5.6 |
| s2b_step_50 | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_50 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.2; call via unknown: 188 ticks over 10 seed(s), first t=5.8 |
| s2b_step_up_20to100 | B0 (default router, pfifo) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | CAKE-static (95% of pre-drop link, set and forget) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2b_step_up_20to100 | ACIQ (controller) | bulk via bulk_download: 10 ticks over 10 seed(s), first t=2.2; call via unknown: 269 ticks over 10 seed(s), first t=5.7 |

Warm-up exclusion (declared): every per-tick window above starts at t >= 2.0 s. The diagnosis round (fix 17's diagnosis.md) shows the first ~2 s of per-tick counter rates are a transmit/counter ramp artefact, not traffic behaviour; dropping those ticks removes nothing else. The window boundary is a declared constant in this generator, not a per-run choice.

Further declared exclusions (TASK 5b): (1) ticks at or beyond the label generator's own measured lifetime (`elapsed_s`, capped by the scenario duration) -- a verdict about a label after its traffic stopped describes nothing about the label; (2) ticks whose link counters went BACKWARDS -- a qdisc del/re-add resets every counter on the device, so that tick's per-class goodput is a reset artefact, not a delivery gap. Stars and minima are computed over what remains; nothing is excluded silently.

## S2b generalization band (evaluation-only; docs/evidence/s2b-params.md, written before these runs)

The shipped controller runs unchanged on capacity changes it was never tuned on: two down-step magnitudes, a 5x up-step, and a continuous 20 s ramp. Seeds 800-809, one run, four arms. CAKE-static is applied once at launch and never re-applied: that is its declared semantics, and S2b exists to surface the consequences. Definitions: bind = first tick at which the applied tree sits within 10% of the link's truth and stays there; tracking error = mean |applied - truth| over the ramp window; estimate error = same over the final third. Where ACIQ fails, the row says so.

### s2b_step_50

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 50.00 +/- 0.00 | 496.35 +/- 0.08 | 47.70 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 50.00 +/- 0.00 | 137.35 +/- 1.87 | 47.71 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 50.00 +/- 0.00 | 2.02 +/- 0.12 | 45.12 +/- 0.32 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 28.9 +/- 13.1 | 3.47 +/- 1.03 | 39.97 +/- 12.56 | 27.90 +/- 2.13 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 50.4 vs truth 50.0, 1% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 41.4 vs truth 50.0, 17% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 42.1 vs truth 50.0, 16% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 43.3 vs truth 50.0, 13% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 45.2 vs truth 50.0, 10% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 44.7 vs truth 50.0, 11% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 41.3 vs truth 50.0, 17% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 49.5 vs truth 50.0, 1% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 42.9 vs truth 50.0, 14% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 45.5 vs truth 50.0, 9% off truth, confidence 0.00 |

### s2b_step_10

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 90.00 +/- 0.00 | 246.63 +/- 0.19 | 9.45 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 90.00 +/- 0.00 | 84.22 +/- 0.39 | 9.45 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 90.00 +/- 0.00 | 5.29 +/- 0.02 | 8.93 +/- 0.05 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | 22.8 | 8.01 +/- 2.83 | 83.20 +/- 1.31 | 6.64 +/- 0.38 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.2 vs truth 10.0, 42% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.5 vs truth 10.0, 45% off truth, confidence 0.10 (n=4); final tick: UNSATURATED (estimator not saturated at the end regime), applied 9.1 vs truth 10.0, 9% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.3 vs truth 10.0, 43% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 14.0 vs truth 10.0, 40% off truth, confidence 0.10 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 8.7 vs truth 10.0, 13% off truth, confidence 0.25 |

### s2b_step_up_20to100

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 80.00 +/- 0.00 | 563.49 +/- 5.31 | 18.85 +/- 0.22 | honesty row declared for ACIQ only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 80.00 +/- 0.00 | 2.63 +/- 0.02 | 18.01 +/- 0.11 | honesty row declared for ACIQ only |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 80.00 +/- 0.00 | 2.65 +/- 0.03 | 17.97 +/- 0.14 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 83.76 +/- 0.69 | 1.72 +/- 0.08 | 9.83 +/- 0.67 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 16.5 vs truth 100.0, 83% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 16.7 vs truth 100.0, 83% off truth, confidence 0.00 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 16.6 vs truth 100.0, 83% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 13.8 vs truth 100.0, 86% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 15.3 vs truth 100.0, 85% off truth, confidence 0.00 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 15.1 vs truth 100.0, 85% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 15.5 vs truth 100.0, 84% off truth, confidence 0.00; final tick: UNSATURATED (estimator not saturated at the end regime), applied 16.4 vs truth 100.0, 84% off truth, confidence 0.00 |

### s2b_ramp_100to30

| arm | n | bind_s | mean |applied-truth| final third (Mbps) | call p95 whole-run (ms) | bulk receiver mean, final third (Mbps) | ACIQ honesty (final tick) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 822.54 +/- 0.13 | 28.57 +/- 0.01 | honesty row declared for ACIQ only |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 134.62 +/- 2.18 | 28.58 +/- 0.00 | honesty row declared for ACIQ only |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 70.00 +/- 0.00 | 132.80 +/- 1.55 | 28.58 +/- 0.00 | honesty row declared for ACIQ only |
| ACIQ (controller) | 10 | NOT AVAILABLE (0/10 binds met inside the run) | 3.88 +/- 0.83 | 69.40 +/- 5.42 | 20.16 +/- 1.18 | final tick: UNSATURATED (estimator not saturated at the end regime), applied 21.7 vs truth 30.0, 28% off truth, confidence 0.10; final tick: UNSATURATED (estimator not saturated at the end regime), applied 22.0 vs truth 30.0, 27% off truth, confidence 0.25; final tick: UNSATURATED (estimator not saturated at the end regime), applied 21.6 vs truth 30.0, 28% off truth, confidence 0.35 (n=2); final tick: UNSATURATED (estimator not saturated at the end regime), applied 21.5 vs truth 30.0, 28% off truth, confidence 0.30; final tick: UNSATURATED (estimator not saturated at the end regime), applied 26.1 vs truth 30.0, 13% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 24.2 vs truth 30.0, 19% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 22.7 vs truth 30.0, 24% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 24.5 vs truth 30.0, 18% off truth, confidence 0.40; final tick: UNSATURATED (estimator not saturated at the end regime), applied 24.7 vs truth 30.0, 18% off truth, confidence 0.40 |


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

- NOT AVAILABLE: unreadable: Expecting ',' delimiter: line 32 column 2 (char 666)

## EMULATION statement (what is modelled, what is not)

All runs on this host are emulation: one router namespace, its LAN/WAN veth pair, an out-of-band bottleneck (netem with a token bucket limiter on the WAN side) and workload generators in their own netns. There are no physical links, no real video stacks and no third-party traffic; delay/jitter/loss via probes are generator-reported for the transmission path only. No number in this report should be read as an ISP deployment result; the controller's own classification, control loop and translation through tc are the subsystems under test.

