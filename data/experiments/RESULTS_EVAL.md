# Results (generated, no summarised files consulted)

Runs root: `data/runs_eval` | runs used: 160 | scenarios: s1_iso_during_call, s2_wan_drop, s3_tv_and_gaming, s4_capacity_recovery

## Delay and throughput, every scenario x arm (mean +/- 95% CI over seeds; t(9)=2.262 for n=10)

Every block below carries an explicit band label, derived from the seed family recorded at load time: `POST-FIX` (seeds 200-209, the controller after the redesign commits), `PRE-FIX` (legacy seeds 0-9/42-51), `DEV` and `EVAL` (the task-2 protocol: parameters were fixed on the DEV band seeds 400-409 BEFORE the EVAL band seeds 500-509 was run ONCE; nothing between them was tuned). A reader never inherits a number of unknown provenance: the label sits directly above the table. The comparison sections further down use the primary band only.

Bulk has TWO columns on purpose (TASK 5a): `sender` is what the generator pushed, `receiver/sink` is what the receiver's sink log totalled -- the delivered number, used for any bulk claim. The post-drop column stays on the TREE counters and is named so: the three are different instruments and are never blended.

### s1_iso_during_call (primary band: EVAL (500-509))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.69 +/- 0.02 | 3.09 +/- 0.03 | 0.766 +/- 0.025 | NOT AVAILABLE | 96.29 +/- 0.00 | 95.49 +/- 0.00 | (no drop scenario) | 0.909 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 1.47 +/- 0.01 | 0.45 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 90.96 +/- 0.00 | 90.74 +/- 0.00 | (no drop scenario) | 0.922 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 1.46 +/- 0.01 | 0.45 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 90.96 +/- 0.00 | 90.74 +/- 0.00 | (no drop scenario) | 0.922 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 88.58 +/- 10.87 | 0.57 +/- 0.04 | 0.200 +/- 0.045 | NOT AVAILABLE | 89.15 +/- 0.12 | 88.34 +/- 0.12 | (no drop scenario) | 0.927 +/- 0.000 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s2_wan_drop (primary band: EVAL (500-509))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 251.30 +/- 0.05 | 4.30 +/- 0.02 | 8.985 +/- 0.168 | NOT AVAILABLE | 79.63 +/- 0.05 | 77.38 +/- 0.25 | 22.22 +/- 0.04 | 0.950 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 70.20 +/- 2.07 | 0.51 +/- 0.01 | 0.165 +/- 0.017 | NOT AVAILABLE | 75.19 +/- 0.04 | 74.42 +/- 0.04 | 20.12 +/- 0.01 | 0.961 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 2.33 +/- 0.04 | 0.31 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.09 +/- 0.00 | 18.06 +/- 0.00 | 18.66 +/- 0.08 | 0.820 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 64.14 +/- 2.15 | 0.61 +/- 0.01 | 0.135 +/- 0.038 | NOT AVAILABLE | 74.14 +/- 0.07 | 71.68 +/- 0.11 | 19.54 +/- 0.22 | 0.964 +/- 0.000 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


### s3_tv_and_gaming (primary band: EVAL (500-509))

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


### s4_capacity_recovery (primary band: EVAL (500-509))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| B0 (default router, pfifo) | 10 | 250.41 +/- 0.05 | 3.06 +/- 0.04 | 5.957 +/- 0.130 | NOT AVAILABLE | 59.46 +/- 0.00 | 58.26 +/- 0.00 | 20.68 +/- 0.01 | 0.993 +/- 0.000 | NOT AVAILABLE |
| CAKE-static (95% of pre-drop link, set and forget) | 10 | 90.05 +/- 0.64 | 0.61 +/- 0.01 | 0.193 +/- 0.047 | NOT AVAILABLE | 56.52 +/- 0.02 | 56.04 +/- 0.03 | 20.04 +/- 0.00 | 0.996 +/- 0.000 | NOT AVAILABLE |
| CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 2.74 +/- 0.02 | 0.48 +/- 0.01 | 0.000 +/- 0.000 | NOT AVAILABLE | 18.08 +/- 0.00 | 18.06 +/- 0.00 | 18.78 +/- 0.01 | 0.820 +/- 0.000 | NOT AVAILABLE |
| ACIQ (controller) | 10 | 59.56 +/- 15.64 | 0.81 +/- 0.26 | 0.087 +/- 0.030 | NOT AVAILABLE | 55.45 +/- 0.32 | 54.22 +/- 0.35 | 18.82 +/- 0.58 | 0.997 +/- 0.000 | NOT AVAILABLE |

#### Time-resolved call latency (per-packet trace, --observe runs only; p50/p95/p99/max in ms per run)

NOT AVAILABLE (no run in this band carries call.obs.jsonl; live --observe runs add it, and this table refuses whole-run distributions in its place)


## ACIQ vs every arm (positive % is better ACIQ on the metric at the head of the column; a cell like `41.0x` is the multiplicative factor when the baseline is so close to zero that a percentage would mislead)

| scenario | vs arm | call p95 delta % | CI overlap? | bulk delta % | CI overlap? |
| --- | --- | --- | --- | --- | --- |
Bulk compares are POST-DROP ONLY in scenarios with a capacity drop (same `bulk_mbps` whole-run mean otherwise): the whole-run number dilutes the post-drop regime with a saturated prefix, which is the opposite of the decision those scenarios exist to measure.

| s1_iso_during_call | B0 (default router, pfifo) | +64.7 | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | 60.3x | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s1_iso_during_call | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 60.6x | disjoint | NOT AVAILABLE | NOT AVAILABLE |
| s2_wan_drop | B0 (default router, pfifo) | +74.5 | disjoint | -12.1 | disjoint |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | +8.6 | disjoint | -2.9 | disjoint |
| s2_wan_drop | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 27.5x | disjoint | +4.7 | disjoint |
| s3_tv_and_gaming | B0 (default router, pfifo) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s3_tv_and_gaming | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE |
| s4_capacity_recovery | B0 (default router, pfifo) | +76.2 | disjoint | -9.0 | disjoint |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | +33.9 | disjoint | -6.1 | disjoint |
| s4_capacity_recovery | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 21.8x | disjoint | +0.2 | overlap |

## Where ACIQ is worse (the honest column)

Every row above where ACIQ's signed delta is negative, collected so a CAKE win cannot hide behind the aggregate. Empty means no such pair exists in the runs found.

| scenario | vs arm | metric where ACIQ is worse |
| --- | --- | --- |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | call p95 60.3x |
| s1_iso_during_call | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | call p95 60.6x |
| s2_wan_drop | B0 (default router, pfifo) | post-drop bulk Mbps -12.1 |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -2.9 |
| s2_wan_drop | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | call p95 27.5x |
| s4_capacity_recovery | B0 (default router, pfifo) | post-drop bulk Mbps -9.0 |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -6.1 |
| s4_capacity_recovery | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | call p95 21.8x |

## Where CAKE-static wins

The honest column above lists every rival; this one isolates the set-and-forget rival that matters for the design claim. A CAKE win on a metric is stated here verbatim; nothing is re-derived and nothing is argued away. CI overlap of the underlying seed samples is in the table above (`CI overlap?` column).

| scenario | metric where CAKE-static beats ACIQ | see column in the ACIQ-vs-every table |
| --- | --- | --- |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | call p95 60.3x |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -2.9 |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | post-drop bulk Mbps -6.1 |

## ACIQ adaptation and capacity accuracy (from the same runs above)

| scenario | n | bind: drop -> first applied <=1.05x post-drop (s) | bind: drop -> first applied <=1.25x post-drop (s) | final estimate | configured end link | estimate error % |
| --- | --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 101.81 +/- 0.15 | 100.0 +/- 0.0 | mean abs 1.8% (seed0: 101.72/100.0 (1.7% off)) |
| s2_wan_drop | 10 | 2.93 (n=10) | 2.93 (n=10) | 20.75 +/- 0.48 | 20.0 +/- 0.0 | mean abs 3.8% (seed0: 21.49/20.0 (7.4% off)) |
| s3_tv_and_gaming | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 53.23 +/- 8.90 | 100.0 +/- 0.0 | mean abs 46.8% (seed0: 59.04/100.0 (41.0% off)) |
| s4_capacity_recovery | 10 | 2.72 (n=10) | 2.72 (n=10) | 20.64 +/- 0.83 | 20.0 +/- 0.0 | mean abs 5.9% (seed0: 21.63/20.0 (8.1% off)) |
## Controller resources (ACIQ adaptive runs only; from each result's resources block)

| scenario | n | cpu mean frac | decision p95 ms | decision max ms | max RSS bytes |
| --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | 10 | 0.0041 +/- 0.0001 | 12.72 +/- 0.41 | 72.64 +/- 1.74 | 27560346 +/- 282310 |
| s2_wan_drop | 10 | 0.0041 +/- 0.0001 | 36.38 +/- 21.31 | 75.23 +/- 2.86 | 28174336 +/- 373853 |
| s3_tv_and_gaming | 10 | 0.0042 +/- 0.0002 | 63.62 +/- 13.04 | 72.24 +/- 1.28 | 28144026 +/- 430901 |
| s4_capacity_recovery | 10 | 0.0044 +/- 0.0002 | 41.19 +/- 25.16 | 113.12 +/- 51.65 | 28893184 +/- 549960 |

## Fairness detail (workload-rate Jain; per-class minima over ASSIGNED classes only, same scope for every mode)

| scenario | arm | n | jain mean +/- CI | demand-jain mean +/- CI | flows used | min over time (per label, via carrying class) |
| --- | --- | --- | --- | --- | --- | --- |
demand-jain: Jain over per-flow satisfied-demand ratios (achieved/demand, demand self-reported by the generator; elastic flows without a declared demand are excluded by definition -- see aciq/fairness.py). A scenario flows all-elastic has no such index and prints NOT AVAILABLE rather than a substitute.

Per-tick counter attribution (fix 18): ACIQ's tree has one leaf per class; the baselines' single-class tree carries the WHOLE link on the 1:50 leaf. New artefacts sample that aggregate under `unknown` (an aggregate can no longer masquerade as a software_update class); artefacts from before this change stored the same aggregate under `software_update`, and consumers that fall back to the legacy label must name it -- the post-drop bulk column does exactly that.

| s1_iso_during_call | B0 (default router, pfifo) | 10 | 0.909 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=99.6; call via unknown=99.6; bulk via unknown=99.6; call via unknown=99.6; bulk via unknown=99.6; call via unknown=99.6 |
| s1_iso_during_call | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.922 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=95; call via unknown=95; bulk via unknown=95; call via unknown=95; bulk via unknown=94.9; call via unknown=94.9 |
| s1_iso_during_call | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.922 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=95; call via unknown=95; bulk via unknown=95; call via unknown=95; bulk via unknown=95; call via unknown=95 |
| s1_iso_during_call | ACIQ (controller) | 10 | 0.927 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=91.4; call via unknown=91.4; bulk via unknown=91.4; call via unknown=91.4; bulk via unknown=91.4; call via unknown=91.4 |
| s2_wan_drop | B0 (default router, pfifo) | 10 | 0.950 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=19.9; call via unknown=19.9; bulk via unknown=20; call via unknown=20 |
| s2_wan_drop | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.961 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20 |
| s2_wan_drop | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.820 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19; call via unknown=19; bulk via unknown=19; call via unknown=19; bulk via unknown=19; call via unknown=19 |
| s2_wan_drop | ACIQ (controller) | 10 | 0.964 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19.2; call via unknown=19.2; bulk via unknown=18.2; call via unknown=18.2; bulk via unknown=18.2; call via unknown=18.2 |
| s3_tv_and_gaming | B0 (default router, pfifo) | 10 | 0.509 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=4.64; tv1 via unknown=4.64; tv2 via unknown=4.64; tv3 via unknown=4.64; game via unknown=4.64; tv1 via unknown=4.64 |
| s3_tv_and_gaming | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.509 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=4.64; tv1 via unknown=4.64; tv2 via unknown=4.64; tv3 via unknown=4.64; game via unknown=4.65; tv1 via unknown=4.65 |
| s3_tv_and_gaming | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.509 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=4.65; tv1 via unknown=4.65; tv2 via unknown=4.65; tv3 via unknown=4.65; game via unknown=4.64; tv1 via unknown=4.64 |
| s3_tv_and_gaming | ACIQ (controller) | 10 | 0.509 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=4.65; tv1 via unknown=4.65; tv2 via unknown=4.65; tv3 via unknown=4.65; game via unknown=4.65; tv1 via unknown=4.65 |
| s4_capacity_recovery | B0 (default router, pfifo) | 10 | 0.993 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19.6; call via unknown=19.6; bulk via unknown=20; call via unknown=20; bulk via unknown=19.8; call via unknown=19.8 |
| s4_capacity_recovery | CAKE-static (95% of pre-drop link, set and forget) | 10 | 0.996 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20; bulk via unknown=20; call via unknown=20 |
| s4_capacity_recovery | CAKE-oracle (post-drop rate from t=0; an oracle an operator cannot have) | 10 | 0.820 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19; call via unknown=19; bulk via unknown=19; call via unknown=19; bulk via unknown=19; call via unknown=19 |
| s4_capacity_recovery | ACIQ (controller) | 10 | 0.997 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19.3; call via unknown=19.3; bulk via unknown=16.8; call via unknown=16.8; bulk via unknown=19.2; call via unknown=19.2 |

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
| - | - | no run in this root has per-tick samples |

Warm-up exclusion (declared): every per-tick window above starts at t >= 2.0 s. The diagnosis round (fix 17's diagnosis.md) shows the first ~2 s of per-tick counter rates are a transmit/counter ramp artefact, not traffic behaviour; dropping those ticks removes nothing else. The window boundary is a declared constant in this generator, not a per-run choice.

Further declared exclusions (TASK 5b): (1) ticks at or beyond the label generator's own measured lifetime (`elapsed_s`, capped by the scenario duration) -- a verdict about a label after its traffic stopped describes nothing about the label; (2) ticks whose link counters went BACKWARDS -- a qdisc del/re-add resets every counter on the device, so that tick's per-class goodput is a reset artefact, not a delivery gap. Stars and minima are computed over what remains; nothing is excluded silently.

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

- NOT AVAILABLE: unreadable: Expecting ',' delimiter: line 32 column 2 (char 666)

## EMULATION statement (what is modelled, what is not)

All runs on this host are emulation: one router namespace, its LAN/WAN veth pair, an out-of-band bottleneck (netem with a token bucket limiter on the WAN side) and workload generators in their own netns. There are no physical links, no real video stacks and no third-party traffic; delay/jitter/loss via probes are generator-reported for the transmission path only. No number in this report should be read as an ISP deployment result; the controller's own classification, control loop and translation through tc are the subsystems under test.

