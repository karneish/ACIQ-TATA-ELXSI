# Final evaluation report (dev-band data; authoritative sources)

Values computed ONLY from `data/runs_dev3/*/{call,bulk}.json`, `bulk.sink.log`,
and `result.json` of runs classified VALID by `tools/validate_runs.py`
(reports/experiment_validation_report.json), plus frozen-gate verdicts by
`tools/verify_round3.py`. Percentile + jitter definitions are the runtime's own
(call.json: RTT p50/p95 and inter-sample jitter); "delivered" = last `cum=`
total / elapsed from the receiver log (t includes settle). The dev CSV is the
only permitted basis for improvement claims at the growth tested here.

Coverage note: the dev band implements the case-study scenario FAMILIES as
s2b_* (capacity steps), s7_* (shape up/down/ramp), s3_stress; s1/s2/s3_tv
full-form scenarios are staged in the FINAL band definition, not this
band. Arms available here: `b1_cake_cons`/`b1_cake_auto` (baselines) and
`aciq`. FIFO baseline `b0_fifo` and oracle belong to the final band.

Constants provenance: ACIQ rows ran the fa9f27f9-era constants (severe 0.9 /
conf 0.6 / probe hold 12 s); per-run source = `result.json.commit_hash`. The
declared retune #2 (commit 210bd09f: severe conf 0.45, hold 7 s, backoff 18 s)
re-runs the two failing shapes; the tables below remain authoritative for
those cells until the retuned band lands.

## Scenario-wise means of valid seeds (+/- 95% CI where n>1; n listed)

### s2b_step_50

| metric | b1_cake_cons | b1_cake_auto | aciq |
|---|---|---|---|
| call RTT p50 (ms) | 40.70±1.70 (n=10) | 25.91±1.64 (n=10) | 0.91±0.05 (n=10) |
| call RTT p95 (ms) | 169.46±2.00 (n=10) | 54.21±9.11 (n=10) | 26.76±2.23 (n=10) |
| call jitter (ms) | 0.55±0.01 (n=10) | 0.57±0.02 (n=10) | 0.49±0.02 (n=10) |
| call loss (fraction) | 0.01±0.00 (n=10) | 0.00±0.00 (n=10) | 0.00±0.00 (n=10) |
| bulk sender (Mb/s) | 48.29±0.00 (n=10) | 56.92±0.15 (n=10) | 51.76±0.63 (n=10) |
| bulk delivered/sink (Mb/s) | 41.18±0.19 (n=10) | 47.96±0.32 (n=10) | 42.02±0.61 (n=10) |
| controller CPU (mean frac) | 0.00±0.00 (n=10) | 0.00±0.00 (n=10) | 0.01±0.00 (n=10) |

### s2b_step_10

| metric | b1_cake_cons | b1_cake_auto | aciq |
|---|---|---|---|
| call RTT p50 (ms) | 65.57±0.41 (n=10) | 64.78±0.87 (n=10) | 1.53±0.04 (n=10) |
| call RTT p95 (ms) | 82.25±0.54 (n=10) | 80.57±0.41 (n=10) | 77.83±1.04 (n=10) |
| call jitter (ms) | 1.22±0.09 (n=10) | 1.04±0.02 (n=10) | 0.97±0.01 (n=10) |
| call loss (fraction) | 0.01±0.00 (n=10) | 0.01±0.00 (n=10) | 0.00±0.00 (n=10) |
| bulk sender (Mb/s) | 20.11±0.03 (n=10) | 29.73±0.19 (n=10) | 26.86±0.41 (n=10) |
| bulk delivered/sink (Mb/s) | 17.16±0.03 (n=10) | 25.07±0.21 (n=10) | 21.99±0.34 (n=10) |
| controller CPU (mean frac) | 0.00±0.00 (n=10) | 0.00±0.00 (n=10) | 0.01±0.00 (n=10) |

### s2b_step_up_20to100

| metric | b1_cake_cons | b1_cake_auto | aciq |
|---|---|---|---|
| call RTT p50 (ms) | 1.00±0.02 (n=10) | 0.75±0.02 (n=10) | 0.38±0.01 (n=10) |
| call RTT p95 (ms) | 2.14±0.08 (n=10) | 2.18±0.05 (n=10) | 1.53±0.02 (n=10) |
| call jitter (ms) | 0.63±0.04 (n=10) | 0.44±0.03 (n=10) | 0.26±0.00 (n=10) |
| call loss (fraction) | 0.00±0.00 (n=10) | 0.00±0.00 (n=10) | 0.00±0.00 (n=10) |
| bulk sender (Mb/s) | 9.47±0.01 (n=10) | 15.89±0.49 (n=10) | 20.34±0.74 (n=10) |
| bulk delivered/sink (Mb/s) | 8.13±0.05 (n=10) | 13.48±0.39 (n=10) | 16.65±0.62 (n=10) |
| controller CPU (mean frac) | 0.00±0.00 (n=10) | 0.00±0.00 (n=10) | 0.01±0.00 (n=10) |

### s2b_ramp_100to30

| metric | b1_cake_cons | b1_cake_auto | aciq |
|---|---|---|---|
| call RTT p50 (ms) | 39.28±1.44 (n=10) | 40.10±5.26 (n=10) | 1.15±0.12 (n=10) |
| call RTT p95 (ms) | 108.80±1.67 (n=10) | 84.96±9.03 (n=10) | 57.56±7.11 (n=10) |
| call jitter (ms) | 0.76±0.05 (n=10) | 0.85±0.06 (n=10) | 0.79±0.08 (n=10) |
| call loss (fraction) | 0.00±0.00 (n=10) | 0.00±0.00 (n=10) | 0.00±0.00 (n=10) |
| bulk sender (Mb/s) | 38.01±0.01 (n=10) | 49.14±0.23 (n=10) | 44.08±0.37 (n=10) |
| bulk delivered/sink (Mb/s) | 33.79±0.16 (n=10) | 43.00±0.27 (n=10) | 36.96±0.37 (n=10) |
| controller CPU (mean frac) | 0.00±0.00 (n=10) | 0.00±0.00 (n=10) | 0.01±0.00 (n=10) |

### s7_up_20to60

| metric | b1_cake_cons | b1_cake_auto | aciq |
|---|---|---|---|
| call RTT p50 (ms) | 0.97±0.01 (n=6) | n/a | 0.56±0.02 (n=10) |
| call RTT p95 (ms) | 2.06±0.03 (n=6) | n/a | 20.32±1.70 (n=10) |
| call jitter (ms) | 0.63±0.02 (n=6) | n/a | 0.54±0.05 (n=10) |
| call loss (fraction) | 0.00±0.00 (n=6) | n/a | 0.00±0.00 (n=10) |
| bulk sender (Mb/s) | 9.46±0.00 (n=6) | n/a | 29.60±0.66 (n=10) |
| bulk delivered/sink (Mb/s) | 8.46±0.08 (n=6) | n/a | 24.88±0.59 (n=10) |
| controller CPU (mean frac) | 0.00±0.00 (n=6) | n/a | 0.01±0.00 (n=10) |

### s7_up_30to100

(no validated seeds yet)

### s7_rampup_30to100

(no validated seeds yet)

### s7_down_100to15

(no validated seeds yet)

### s7_down_100to8

(no validated seeds yet)

### s3_stress

(no validated seeds yet)

## Frozen-gate verdicts on this data (tools/verify_round3.py; 49 judged runs)

- s2b_step_10 aciq (emergency landing): 10/10 PASS, landings 0.6-4.8 s (limit 8.0 s).
- s2b_step_50 aciq: 6/10 PASS (3.8-4.9 s); 4 seeds FAIL the criterion (severe
  drop never fired -> ~16 s walk). Gate-read, not interpreted.
- s7_up_20to60 aciq (climb, 60-s window): 8/8 judged PASS, util_applied
  0.69-1.06, util_delivered 0.77-0.82 (limits 0.60 / 0.50).
- s2b_step_up_20to100 aciq: 0/10 PASS (util_applied 0.32-0.47) — pacing defect;
  declared retune (210bd09f) targets it and re-runs.
- s3_stress aciq: controller makes NO enforcement claim (design: no new-rate
  commits during pure-saturation stress) — consistent readout.

## What is NOT yet claimed
- final acceptance band (84 cells / 840 seed-runs): NOT RUN.
- retuned step_50/step_up cells: re-run pending; the numbers above remain the
  pre-retune evidence for those shapes.
- IPv6 classification and a recorded live Jain fairness measurement: see
  docs/REQUIREMENT_TRACEABILITY.md.

