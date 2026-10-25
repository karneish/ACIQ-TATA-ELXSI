# Results (generated, no summarised files consulted)

Runs root: `/home/mekarz/Desktop/Full-projects/TATA-ELXSI/data/runs` | runs used: 190 | scenarios: s1_iso_during_call, s2_wan_drop, s3_tv_and_gaming, s4_capacity_recovery, s6_intent_expire

Skipped 1 incomplete-only directory names: `s2_wan_drop__aciq__adaptive__seed555 (special-condition run: inject_fail_apply)`

**Skipped directories (summary):**
- special-condition run: 1
- total skipped: 1

## Delay and throughput, every scenario x arm (mean +/- 95% CI over seeds; t(9)=2.262 for n=10)

Bulk has TWO columns on purpose (TASK 5a): `sender` is what the generator pushed, `receiver/sink` is what the receiver's sink log totalled -- the delivered number, used for any bulk claim. The post-drop column stays on the TREE counters and is named so: the three are different instruments and are never blended.

### s1_iso_during_call

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.67 +/- 0.03 | 3.09 +/- 0.03 | 0.766 +/- 0.025 | NOT AVAILABLE | 96.29 +/- 0.00 | 95.49 +/- 0.00 | (no drop scenario) | 0.909 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.45 +/- 0.01 | 0.45 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 90.96 +/- 0.00 | 90.74 +/- 0.00 | (no drop scenario) | 0.922 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 1.45 +/- 0.01 | 0.44 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 90.96 +/- 0.00 | 90.74 +/- 0.00 | (no drop scenario) | 0.922 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 82.49 +/- 0.49 | 0.61 +/- 0.05 | 0.180 +/- 0.060 | NOT AVAILABLE | 86.22 +/- 0.93 | 85.41 +/- 0.93 | (no drop scenario) | 0.934 +/- 0.002 | NOT AVAILABLE |

### s2_wan_drop

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 251.28 +/- 0.09 | 4.36 +/- 0.06 | 8.710 +/- 0.323 | NOT AVAILABLE | 79.58 +/- 0.01 | NOT AVAILABLE | 22.16 +/- 0.05 | 0.950 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 70.31 +/- 1.73 | 0.51 +/- 0.01 | 0.160 +/- 0.015 | NOT AVAILABLE | 75.17 +/- 0.04 | 74.41 +/- 0.04 | 20.12 +/- 0.01 | 0.961 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 2.33 +/- 0.03 | 0.31 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.09 +/- 0.00 | 18.06 +/- 0.00 | 18.71 +/- 0.06 | 0.820 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 73.60 +/- 2.48 | 0.63 +/- 0.03 | 0.265 +/- 0.041 | NOT AVAILABLE | 71.69 +/- 0.58 | 69.54 +/- 0.56 | 20.15 +/- 0.01 | 0.969 +/- 0.001 | NOT AVAILABLE |

### s3_tv_and_gaming

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 3.19 +/- 0.13 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.33 +/- 0.25 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.41 +/- 0.17 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.37 +/- 0.11 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.510 +/- 0.000 | 1.000 +/- 0.000 |

### s4_capacity_recovery

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.43 +/- 0.06 | 3.05 +/- 0.02 | 6.017 +/- 0.155 | NOT AVAILABLE | 59.45 +/- 0.01 | 58.26 +/- 0.01 | 20.68 +/- 0.01 | 0.993 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 89.73 +/- 1.08 | 0.63 +/- 0.02 | 0.197 +/- 0.052 | NOT AVAILABLE | 56.51 +/- 0.02 | 56.04 +/- 0.02 | 20.04 +/- 0.00 | 0.996 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 2.74 +/- 0.03 | 0.48 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.08 +/- 0.00 | 18.06 +/- 0.00 | 18.78 +/- 0.01 | 0.820 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 95.74 +/- 0.90 | 0.73 +/- 0.01 | 0.280 +/- 0.023 | NOT AVAILABLE | 53.88 +/- 0.08 | 52.79 +/- 0.08 | 19.95 +/- 0.00 | 0.999 +/- 0.000 | NOT AVAILABLE |

### s6_intent_expire

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.85 +/- 0.03 | 3.18 +/- 0.03 | 0.555 +/- 0.011 | 250.88 +/- 0.03 | 96.06 +/- 0.00 | 95.46 +/- 0.00 | (no drop scenario) | 0.818 +/- 0.000 | 1.000 +/- 0.000 |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.39 +/- 0.01 | 0.44 +/- 0.01 | 0.000 +/- 0.000 | 1.41 +/- 0.01 | 90.85 +/- 0.01 | 90.69 +/- 0.01 | (no drop scenario) | 0.835 +/- 0.000 | 1.000 +/- 0.000 |
| ACIQ (controller) | 10 | 39.00 +/- 20.30 | 0.43 +/- 0.01 | 0.035 +/- 0.029 | 38.68 +/- 20.00 | 76.72 +/- 1.12 | 76.14 +/- 1.12 | (no drop scenario) | 0.882 +/- 0.004 | 1.000 +/- 0.000 |

## ACIQ vs every arm (positive % is better ACIQ on the metric at the head of the column; a cell like `41.0x` is the multiplicative factor when the baseline is so close to zero that a percentage would mislead)

| scenario | vs arm | call p95 delta % | CI overlap? | bulk delta % | CI overlap? |
| --- | --- | --- | --- | --- | --- |
Bulk compares are POST-DROP ONLY in scenarios with a capacity drop (same `bulk_mbps` whole-run mean otherwise): the whole-run number dilutes the post-drop regime with a saturated prefix, which is the opposite of the decision those scenarios exist to measure.

| s1_iso_during_call | B0 (default router, pfifo) | +67.1 | disjoint | NOT AVAILABLE |  |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | 57.0x | disjoint | NOT AVAILABLE |  |
| s1_iso_during_call | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 56.7x | disjoint | NOT AVAILABLE |  |
| s2_wan_drop | B0 (default router, pfifo) | +70.7 | disjoint | -9.1 | disjoint |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | -4.7 | overlap | +0.1 | disjoint |
| s2_wan_drop | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 31.6x | disjoint | +7.7 | disjoint |
| s3_tv_and_gaming | B0 (default router, pfifo) | NOT AVAILABLE |  | NOT AVAILABLE |  |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | NOT AVAILABLE |  | NOT AVAILABLE |  |
| s3_tv_and_gaming | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | NOT AVAILABLE |  | NOT AVAILABLE |  |
| s4_capacity_recovery | B0 (default router, pfifo) | +61.8 | disjoint | -3.5 | disjoint |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | -6.7 | disjoint | -0.5 | disjoint |
| s4_capacity_recovery | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 35.0x | disjoint | +6.2 | disjoint |
| s6_intent_expire | B0 (default router, pfifo) | +84.5 | disjoint | NOT AVAILABLE |  |
| s6_intent_expire | CAKE-static (95% of pre-drop link, set and forget) | 28.1x | disjoint | NOT AVAILABLE |  |

## Where ACIQ is worse (the honest column)

Every row above where ACIQ's signed delta is negative, collected so a CAKE win cannot hide behind the aggregate. Empty means no such pair exists in the runs found.

| scenario | vs arm | metric where ACIQ is worse |
| --- | --- | --- |
| s2_wan_drop | B0 (default router, pfifo) | post-drop bulk Mbps |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | call p95 |
| s4_capacity_recovery | B0 (default router, pfifo) | post-drop bulk Mbps |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | call p95 and post-drop bulk Mbps |

## ACIQ adaptation and capacity accuracy (from the same runs above)

| scenario | n | bind: drop -> first applied <=1.05x post-drop (s) | bind: drop -> first applied <=1.25x post-drop (s) | final estimate | configured end link | estimate error % |
| --- | --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 95.73 +/- 0.08 | 100.0 +/- 0.0 | mean abs 4.3% (seed0: 95.61/100.0 (4.4% off)) |
| s2_wan_drop | 10 | 1.72 (n=10) | 1.72 (n=10) | 21.45 +/- 0.11 | 20.0 +/- 0.0 | mean abs 7.3% (seed0: 21.59/20.0 (7.9% off)) |
| s3_tv_and_gaming | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 56.23 +/- 13.96 | 100.0 +/- 0.0 | mean abs 43.8% (seed0: 59.04/100.0 (41.0% off)) |
| s4_capacity_recovery | 10 | 1.85 (n=10) | 1.85 (n=10) | 21.35 +/- 0.25 | 20.0 +/- 0.0 | mean abs 6.7% (seed0: 21.52/20.0 (7.6% off)) |
| s6_intent_expire | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 78.66 +/- 6.71 | 100.0 +/- 0.0 | mean abs 21.3% (seed0: 86.91/100.0 (13.1% off)) |
## Controller resources (ACIQ adaptive runs only; from each result's resources block)

| scenario | n | cpu mean frac | decision p95 ms | decision max ms | max RSS bytes |
| --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | 10 | 0.0042 +/- 0.0001 | 37.29 +/- 18.57 | 76.59 +/- 2.65 | 20649574 +/- 384796 |
| s2_wan_drop | 10 | 0.0043 +/- 0.0001 | 59.97 +/- 17.01 | 75.82 +/- 2.43 | 20893286 +/- 406731 |
| s3_tv_and_gaming | 10 | 0.0043 +/- 0.0002 | 74.32 +/- 1.15 | 77.82 +/- 2.49 | 20952678 +/- 397623 |
| s4_capacity_recovery | 10 | 0.0045 +/- 0.0001 | 14.88 +/- 2.76 | 80.21 +/- 1.23 | 21629338 +/- 590585 |
| s6_intent_expire | 10 | 0.0087 +/- 0.0002 | 77.78 +/- 12.80 | 120.93 +/- 22.76 | 29088563 +/- 559385 |

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
| s6_intent_expire | B0 (default router, pfifo) | 10 | 0.818 +/- 0.000 | 1.000 +/- 0.000 | 3.0 +/- 0.0 | bulk via unknown=99.6; call via unknown=99.6; game via unknown=99.6; bulk via unknown=99.6; call via unknown=99.6; game via unknown=99.6 |
| s6_intent_expire | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.835 +/- 0.000 | 1.000 +/- 0.000 | 3.0 +/- 0.0 | bulk via unknown=94.9; call via unknown=94.9; game via unknown=94.9; bulk via unknown=92.5; call via unknown=92.5; game via unknown=92.5 |
| s6_intent_expire | ACIQ (controller) | 10 | 0.882 +/- 0.004 | 1.000 +/- 0.000 | 3.0 +/- 0.0 | bulk=74.9; call=0.118; game=0; bulk=62.7; call=0.0592; game=0 |

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
| s6_intent_expire | ACIQ (controller) | call via video_call_voice: 1 ticks over 1 seed(s), first t=38.3; game via interactive_gaming: 224 ticks over 8 seed(s), first t=4.3; game via unknown: 52 ticks over 2 seed(s), first t=4.3 |

Warm-up exclusion (declared): every per-tick window above starts at t >= 2.0 s. The diagnosis round (fix 17's diagnosis.md) shows the first ~2 s of per-tick counter rates are a transmit/counter ramp artefact, not traffic behaviour; dropping those ticks removes nothing else. The window boundary is a declared constant in this generator, not a per-run choice.

Further declared exclusions (TASK 5b): (1) ticks at or beyond the label generator's own measured lifetime (`elapsed_s`, capped by the scenario duration) -- a verdict about a label after its traffic stopped describes nothing about the label; (2) ticks whose link counters went BACKWARDS -- a qdisc del/re-add resets every counter on the device, so that tick's per-class goodput is a reset artefact, not a delivery gap. Stars and minima are computed over what remains; nothing is excluded silently.

## S6 intent scenario (TASK 4: real API intent, TTL expiry inside the run, auto-revert)

One intent is requested at t~1s on the operator's real surface (IntentService, the exact upstream-declared code path the HTTP handler calls: POST /intent, target device, weight 0.5, TTL 15s). The 40s scenario makes the TTL expire INSIDE the run, so both endpoints of the intent's life are measured: held while live, auto-reverted at expiry (LeaseBook's implicit sweep plus the per-tick sync_lease). Receiver evidence is the per-second sink sampler; the floors line is a FLOOR line, not a preference claim: on a healthy link a reserve must not starve the other classes, and the reserved device must actually receive bytes. The s6 summary file is quoted when present; the table never infers what the verifier measured.

| arm | intent (verdict from result.json) | auto-revert (lease_active evidence, ticks) | receiver inst in window: game min / bulk min (floors) | declared |
| --- | --- | --- | --- | --- |
- verifier verdict (tools/verify_s6.py, via `/home/mekarz/Desktop/Full-projects/TATA-ELXSI/data/experiments/s6/s6_summary.json`): `{"intent_granted": "PASS", "auto_reverted_at_expiry": "PASS", "floors_held": "PASS", "baselines_declare_unsupported": "PASS", "run_rc": 0, "host": "live step verdict; floors include the absolute fallback floor (verifier re-run over the committed artefacts confirms the same verdict)", "notes": "values PASS/FAIL/NA; per-seed details in data/runs/"}`

| B0 (default router, pfifo) | declared: no intent surface (n=10 seeds) | - (n=10 seeds) | - (n=10 seeds) | declared intent-incapable |
| CAKE-static (95% of pre-drop link, set and forget) | declared: no intent surface (n=10 seeds) | - (n=10 seeds) | - (n=10 seeds) | declared intent-incapable |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | NOT AVAILABLE (no s6 run dir) | - | - | declared intent-incapable |
| ACIQ (controller) | granted t=1.0s, in-effect 13s (TTL 15s); granted t=1.0s, in-effect 13s (TTL 15s); granted t=1.0s, in-effect 14s (TTL 15s); granted t=1.0s, in-effect 13s (TTL 15s); granted t=1.0s, in-effect 13s (TTL 15s); granted t=1.0s, in-effect 13s (TTL 15s); granted t=1.0s, in-effect 13s (TTL 15s); granted t=1.0s, in-effect 13s (TTL 15s); granted t=1.1s, in-effect 13s (TTL 15s); granted t=1.0s, in-effect 13s (TTL 15s) | ok: last active t=15s, clear after 16s; ok: last active t=15s, clear after 16s; ok: last active t=16s, clear after 16s; ok: last active t=15s, clear after 16s; ok: last active t=15s, clear after 16s; ok: last active t=15s, clear after 16s; ok: last active t=15s, clear after 16s; ok: last active t=15s, clear after 16s; ok: last active t=15s, clear after 16s; ok: last active t=15s, clear after 16s | game 0.03 Mbps (>0: PASS); bulk 71.43 Mbps (>=10% of pre-median 21.04: PASS); game 0.03 Mbps (>0: PASS); bulk 56.48 Mbps (>=10% of pre-median 0.00: PASS); game 0.03 Mbps (>0: PASS); bulk 59.25 Mbps (>=10% of pre-median 67.92: PASS); game 0.03 Mbps (>0: PASS); bulk 58.93 Mbps (>=10% of pre-median 34.33: PASS); game 0.03 Mbps (>0: PASS); bulk 57.24 Mbps (>=10% of pre-median 20.25: PASS); game 0.03 Mbps (>0: PASS); bulk 71.75 Mbps (>=10% of pre-median 17.83: PASS); game 0.03 Mbps (>0: PASS); bulk 58.85 Mbps (>=10% of pre-median 17.16: PASS); game 0.03 Mbps (>0: PASS); bulk 63.65 Mbps (>=10% of pre-median 0.00: PASS); game 0.03 Mbps (>0: PASS); bulk 55.23 Mbps (>=10% of pre-median 0.00: PASS); game 0.03 Mbps (>0: PASS); bulk 57.35 Mbps (>=10% of pre-median 33.24: PASS) | ACIQ: intent surface |

## Classifier (router-vantage corpus, thresholds fixed before held-out)

- HEADLINE (fresh held-out, tuple-split by flow, no threshold tuned on this half): strict accuracy 0.5877192982456141 on n=114 (67 correct, 0 abstained). The FULL-corpus figures below are context, not the verdict: the held-out half is the one the classifier never shaped.
- strict: `{"n": 228, "correct": 139, "abstained": 0, "confident_or_wrong": 89, "accuracy_strict": 0.6096491228070176, "accuracy_excl_abstain": 0.6096491228070176}`
- strict_fixed: `{"n": 114, "correct": 72, "abstained": 0, "confident_or_wrong": 42, "accuracy_strict": 0.631578947368421, "accuracy_excl_abstain": 0.631578947368421}`
- strict_heldout: `{"n": 114, "correct": 67, "abstained": 0, "confident_or_wrong": 47, "accuracy_strict": 0.5877192982456141, "accuracy_excl_abstain": 0.5877192982456141}`
- accept_abstain: `{"n": 228, "correct": 139, "abstained": 0, "confident_or_wrong": 89, "accuracy_strict": 0.6096491228070176, "accuracy_excl_abstain": 0.6096491228070176}`
- accept_abstain_heldout: `{"n": 114, "correct": 67, "abstained": 0, "confident_or_wrong": 47, "accuracy_strict": 0.5877192982456141, "accuracy_excl_abstain": 0.5877192982456141}`
- confusion_heldout: `{"classes": ["adaptive_video_streaming", "bulk_download", "cloud_backup", "interactive_gaming", "software_update", "video_call_voice"], "matrix": {"adaptive_video_streaming": {"bulk_download": 0, "cloud_backup": 0, "interactive_gaming": 0, "software_update": 0, "video_call_voice": 0, "adaptive_video_streaming": 26, "?abstain": 0}, "bulk_download": {"adaptive_video_streaming": 4, "cloud_backup": 0, "interactive_gaming": 0, "software_update": 0, "video_call_voice": 0, "bulk_download": 13, "?abstain": 0}, "cloud_backup": {"adaptive_video_streaming": 0, "bulk_download": 0, "interactive_gaming": 0, "software_update": 0, "video_call_voice": 0, "cloud_backup": 15, "?abstain": 0}, "interactive_gaming": {"adaptive_video_streaming": 0, "bulk_download": 0, "cloud_backup": 0, "software_update": 0, "video_call_voice": 18, "interactive_gaming": 0, "?abstain": 0}, "software_update": {"adaptive_video_streaming": 25, "bulk_download": 0, "cloud_backup": 0, "interactive_gaming": 0, "video_call_voice": 0, "software_update": 0, "?abstain": 0}, "video_call_voice": {"adaptive_video_streaming": 0, "bulk_download": 0, "cloud_backup": 0, "interactive_gaming": 0, "software_update": 0, "video_call_voice": 13, "?abstain": 0}}, "per_class": {"adaptive_video_streaming": {"tp": 26, "fp": 29, "fn": 0, "support": 26, "precision": 0.4727272727272727, "recall": 1.0, "f1": 0.6419753086419753}, "bulk_download": {"tp": 13, "fp": 0, "fn": 4, "support": 17, "precision": 1.0, "recall": 0.7647058823529411, "f1": 0.8666666666666666}, "cloud_backup": {"tp": 15, "fp": 0, "fn": 0, "support": 15, "precision": 1.0, "recall": 1.0, "f1": 1.0}, "interactive_gaming": {"tp": 0, "fp": 0, "fn": 18, "support": 18, "precision": null, "recall": 0.0, "f1": null}, "software_update": {"tp": 0, "fp": 0, "fn": 25, "support": 25, "precision": null, "recall": 0.0, "f1": null}, "video_call_voice": {"tp": 13, "fp": 18, "fn": 0, "support": 13, "precision": 0.41935483870967744, "recall": 1.0, "f1": 0.5909090909090909}}}`
- paths_fixed: `["aciq/classify.py", "aciq/features.py"]`
- n_corpus: `228`
- n_heldout: `114`
- per-class floor 30: met (counts: `{"video_call_voice": 30, "interactive_gaming": 30, "adaptive_video_streaming": 49, "bulk_download": 40, "software_update": 49, "cloud_backup": 30}`)

Source: `/home/mekarz/Desktop/Full-projects/TATA-ELXSI/data/experiments/classifier_corpus/eval.json` (written by the corpus evaluator, whose failure table is copied verbatim).

## Safe-state and failure injection (S5)

- a_sigterm_no_filter_residue: `"PASS"`
- b_sigkill_residue_then_cleanup: `"PASS"`
- c_injected_failed_apply_rollbacks: `"PASS"`
- d_watchdog_starve_reaches_safe: `"PASS"`
- host: `"/home/mekarz/aciq-venv/bin/python -V"`
- notes: `"values PASS/FAIL only; the report quotes this file verbatim"`

## EMULATION statement (what is modelled, what is not)

All runs on this host are emulation: one router namespace, its LAN/WAN veth pair, an out-of-band bottleneck (netem with a token bucket limiter on the WAN side) and workload generators in their own netns. There are no physical links, no real video stacks and no third-party traffic; delay/jitter/loss via probes are generator-reported for the transmission path only. No number in this report should be read as an ISP deployment result; the controller's own classification, control loop and translation through tc are the subsystems under test.

