# Results (generated, no summarised files consulted)

Runs root: `data/runs_dev` | runs used: 40 | scenarios: s1_iso_during_call, s2_wan_drop, s3_tv_and_gaming, s4_capacity_recovery

## Delay and throughput, every scenario x arm (mean +/- 95% CI over seeds; t(9)=2.262 for n=10)

Every block below carries an explicit band label, derived from the seed family recorded at load time: `POST-FIX` (seeds 200-209, the controller after the redesign commits), `PRE-FIX` (legacy seeds 0-9/42-51), `DEV` and `EVAL` (the task-2 protocol: parameters were fixed on the DEV band seeds 400-409 BEFORE the EVAL band seeds 500-509 was run ONCE; nothing between them was tuned). A reader never inherits a number of unknown provenance: the label sits directly above the table. The comparison sections further down use the primary band only.

Bulk has TWO columns on purpose (TASK 5a): `sender` is what the generator pushed, `receiver/sink` is what the receiver's sink log totalled -- the delivered number, used for any bulk claim. The post-drop column stays on the TREE counters and is named so: the three are different instruments and are never blended.

### s1_iso_during_call (primary band: DEV (400-409))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ACIQ (controller) | 10 | 93.21 +/- 14.44 | 0.59 +/- 0.05 | 0.180 +/- 0.055 | NOT AVAILABLE | 89.13 +/- 0.10 | 88.32 +/- 0.10 | (no drop scenario) | 0.927 +/- 0.000 | NOT AVAILABLE |

### s2_wan_drop (primary band: DEV (400-409))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ACIQ (controller) | 10 | 64.38 +/- 2.52 | 0.62 +/- 0.01 | 0.135 +/- 0.038 | NOT AVAILABLE | 74.15 +/- 0.07 | 71.71 +/- 0.10 | 19.59 +/- 0.17 | 0.964 +/- 0.000 | NOT AVAILABLE |

### s3_tv_and_gaming (primary band: DEV (400-409))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ACIQ (controller) | 10 | NOT AVAILABLE | NOT AVAILABLE | NOT AVAILABLE | 2.27 +/- 0.19 | NOT AVAILABLE | NOT AVAILABLE | (no drop scenario) | 0.509 +/- 0.000 | 1.000 +/- 0.000 |

### s4_capacity_recovery (primary band: DEV (400-409))

| arm | n | call p95 ms | call jitter ms | call loss % | game p95 ms | bulk Mbps (sender) | bulk Mbps (receiver/sink) | post-drop bulk (tree) | jain (workload-rate Jain) | jain (demand-normalized) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ACIQ (controller) | 10 | 50.92 +/- 7.97 | 0.65 +/- 0.02 | 0.097 +/- 0.017 | NOT AVAILABLE | 55.27 +/- 0.27 | 54.02 +/- 0.32 | 18.53 +/- 0.62 | 0.997 +/- 0.000 | NOT AVAILABLE |

## ACIQ vs every arm (positive % is better ACIQ on the metric at the head of the column; a cell like `41.0x` is the multiplicative factor when the baseline is so close to zero that a percentage would mislead)

| scenario | vs arm | call p95 delta % | CI overlap? | bulk delta % | CI overlap? |
| --- | --- | --- | --- | --- | --- |
Bulk compares are POST-DROP ONLY in scenarios with a capacity drop (same `bulk_mbps` whole-run mean otherwise): the whole-run number dilutes the post-drop regime with a saturated prefix, which is the opposite of the decision those scenarios exist to measure.


## Where ACIQ is worse (the honest column)

Every row above where ACIQ's signed delta is negative, collected so a CAKE win cannot hide behind the aggregate. Empty means no such pair exists in the runs found.

| scenario | vs arm | metric where ACIQ is worse |
| --- | --- | --- |
(none in these runs)

## Where CAKE-static wins

The honest column above lists every rival; this one isolates the set-and-forget rival that matters for the design claim. A CAKE win on a metric is stated here verbatim; nothing is re-derived and nothing is argued away. CI overlap of the underlying seed samples is in the table above (`CI overlap?` column).

| scenario | metric where CAKE-static beats ACIQ | see column in the ACIQ-vs-every table |
| --- | --- | --- |
(none in these runs)

## ACIQ adaptation and capacity accuracy (from the same runs above)

| scenario | n | bind: drop -> first applied <=1.05x post-drop (s) | bind: drop -> first applied <=1.25x post-drop (s) | final estimate | configured end link | estimate error % |
| --- | --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 101.75 +/- 0.07 | 100.0 +/- 0.0 | mean abs 1.7% (seed0: 101.70/100.0 (1.7% off)) |
| s2_wan_drop | 10 | 2.83 (n=10) | 2.83 (n=10) | 20.88 +/- 0.47 | 20.0 +/- 0.0 | mean abs 4.4% (seed0: 21.54/20.0 (7.7% off)) |
| s3_tv_and_gaming | 10 | no post-drop applied tree at/below 1.05x post-drop link in any seed | no post-drop applied tree at/below 1.25x post-drop link in any seed | 47.62 +/- 14.57 | 100.0 +/- 0.0 | mean abs 52.4% (seed0: 67.23/100.0 (32.8% off)) |
| s4_capacity_recovery | 10 | 2.84 (n=10) | 2.84 (n=10) | 20.31 +/- 0.94 | 20.0 +/- 0.0 | mean abs 6.2% (seed0: 20.37/20.0 (1.9% off)) |
## Controller resources (ACIQ adaptive runs only; from each result's resources block)

| scenario | n | cpu mean frac | decision p95 ms | decision max ms | max RSS bytes |
| --- | --- | --- | --- | --- | --- |
| s1_iso_during_call | 10 | 0.0041 +/- 0.0001 | 13.11 +/- 0.86 | 72.96 +/- 1.65 | 27634074 +/- 286602 |
| s2_wan_drop | 10 | 0.0041 +/- 0.0001 | 36.17 +/- 21.13 | 73.78 +/- 1.99 | 28241510 +/- 401325 |
| s3_tv_and_gaming | 10 | 0.0041 +/- 0.0001 | 69.21 +/- 0.48 | 72.61 +/- 2.28 | 28316467 +/- 424447 |
| s4_capacity_recovery | 10 | 0.0043 +/- 0.0001 | 36.12 +/- 21.25 | 73.60 +/- 1.25 | 28879258 +/- 573793 |

## Fairness detail (workload-rate Jain; per-class minima over ASSIGNED classes only, same scope for every mode)

| scenario | arm | n | jain mean +/- CI | demand-jain mean +/- CI | flows used | min over time (per label, via carrying class) |
| --- | --- | --- | --- | --- | --- | --- |
demand-jain: Jain over per-flow satisfied-demand ratios (achieved/demand, demand self-reported by the generator; elastic flows without a declared demand are excluded by definition -- see aciq/fairness.py). A scenario flows all-elastic has no such index and prints NOT AVAILABLE rather than a substitute.

Per-tick counter attribution (fix 18): ACIQ's tree has one leaf per class; the baselines' single-class tree carries the WHOLE link on the 1:50 leaf. New artefacts sample that aggregate under `unknown` (an aggregate can no longer masquerade as a software_update class); artefacts from before this change stored the same aggregate under `software_update`, and consumers that fall back to the legacy label must name it -- the post-drop bulk column does exactly that.

| s1_iso_during_call | ACIQ (controller) | 10 | 0.927 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=91.4; call via unknown=91.4; bulk via unknown=91.5; call via unknown=91.5; bulk via unknown=91.4; call via unknown=91.4 |
| s2_wan_drop | ACIQ (controller) | 10 | 0.964 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=19.3; call via unknown=19.3; bulk via unknown=19.3; call via unknown=19.3; bulk via unknown=19.3; call via unknown=19.3 |
| s3_tv_and_gaming | ACIQ (controller) | 10 | 0.509 +/- 0.000 | 1.000 +/- 0.000 | 4.0 +/- 0.0 | game via unknown=4.65; tv1 via unknown=4.65; tv2 via unknown=4.65; tv3 via unknown=4.65; game via unknown=4.66; tv1 via unknown=4.66 |
| s4_capacity_recovery | ACIQ (controller) | 10 | 0.997 +/- 0.000 | NOT AVAILABLE | 2.0 +/- 0.0 | bulk via unknown=18.2; call via unknown=18.2; bulk via unknown=17; call via unknown=17; bulk via unknown=16.8; call via unknown=16.8 |

Starvation (TASK 5b, fixed basis): per LABEL, over the class the data says carried the traffic (assigned class, or the router's `unknown`/legacy aggregate when the label's traffic rode there -- chosen by highest mean, and the carrying class is named). A label starved in tick t if its per-tick goodput fell below 20% of its REGIME median -- in a drop scenario the median is the POST-DROP regime's own median, so the shaped link rate can never masquerade as starvation; without a drop it is the whole window's. The cell lists the starved timestamps counted over seeds. With no series at all the cell prints NOT AVAILABLE, never an empty claim.

| scenario | arm | starved ticks per label (via carrying class) |
| --- | --- | --- |
| s1_iso_during_call | ACIQ (controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s2_wan_drop | ACIQ (controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| s3_tv_and_gaming | ACIQ (controller) | no starving tick in 40 seed x label series (regime-aware threshold, declared window) |
| s4_capacity_recovery | ACIQ (controller) | no starving tick in 20 seed x label series (regime-aware threshold, declared window) |
| - | - | no run in this root has per-tick samples |

Warm-up exclusion (declared): every per-tick window above starts at t >= 2.0 s. The diagnosis round (fix 17's diagnosis.md) shows the first ~2 s of per-tick counter rates are a transmit/counter ramp artefact, not traffic behaviour; dropping those ticks removes nothing else. The window boundary is a declared constant in this generator, not a per-run choice.

Further declared exclusions (TASK 5b): (1) ticks at or beyond the label generator's own measured lifetime (`elapsed_s`, capped by the scenario duration) -- a verdict about a label after its traffic stopped describes nothing about the label; (2) ticks whose link counters went BACKWARDS -- a qdisc del/re-add resets every counter on the device, so that tick's per-class goodput is a reset artefact, not a delivery gap. Stars and minima are computed over what remains; nothing is excluded silently.

## Classifier (router-vantage corpus, thresholds fixed before held-out)

- HEADLINE (fresh held-out, tuple-split by flow, no threshold tuned on this half): strict accuracy 0.5877192982456141 on n=114 (67 correct, 0 abstained). The FULL-corpus figures below are context, not the verdict: the held-out half is the one the classifier never shaped.
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
- d_watchdog_starve_reaches_safe: `"PASS"`
- host: `"/home/mekarz/aciq-venv/bin/python -V"`
- notes: `"values PASS/FAIL only; the report quotes this file verbatim"`

## EMULATION statement (what is modelled, what is not)

All runs on this host are emulation: one router namespace, its LAN/WAN veth pair, an out-of-band bottleneck (netem with a token bucket limiter on the WAN side) and workload generators in their own netns. There are no physical links, no real video stacks and no third-party traffic; delay/jitter/loss via probes are generator-reported for the transmission path only. No number in this report should be read as an ISP deployment result; the controller's own classification, control loop and translation through tc are the subsystems under test.

