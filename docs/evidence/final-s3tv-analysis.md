# Final band: the ten `s3_tv_and_gaming` ACIQ runs (seeds 1100-1109)

The raw final gate logged ten FAILs, all `s3_tv_and_gaming`, all with

```
stress_deliver=FAILED: no delivered stream in the final third
```

They are not delivery collapses and not controller failures. They are the
gate applying the **bulk** stress law to a shape that has no bulk workload.

## What the ten runs actually contain

`workloads.json` for every seed lists `game`, `tv1`, `tv2`, `tv3`; there is no
`bulk` entry. The run directories contain `game.sink.log`, `tv1.sink.log`,
`tv2.sink.log` and `tv3.sink.log`; there is no `bulk.sink.log`.

| seed | commits | applied final third (Mbps) | interactive delivered (Mbps) | game p95 (ms) | game loss |
|---|---|---|---|---|---|
| 1100 | 6 | 35.73 | 15.20 | 2.386 | 0.0 % |
| 1101 | 3 | 90.00 | 14.73 | 2.133 | 0.0 % |
| 1102 | 5 | 48.62 | 15.18 | 2.661 | 0.0 % |
| 1103 | 5 | 48.62 | 15.01 | 2.160 | 0.0 % |
| 1104 | 7 | 35.73 | 15.07 | 2.008 | 0.0 % |
| 1105 | 6 | 35.73 | 15.28 | 1.964 | 0.0 % |
| 1106 | 5 | 90.00 | 15.18 | 2.432 | 0.0 % |
| 1107 | 7 | 42.18 | 15.17 | 1.938 | 0.0 % |
| 1108 | 4 | 66.15 | 14.81 | 2.671 | 0.0 % |
| 1109 | 7 | 35.73 | 14.77 | 2.705 | 0.0 % |

The three video ladders are the delivered payload. Each advertises
`sender_mbps = 4.82`, so the source offers about **14.46 Mbps** in total. The
delivered column is 14.7-15.3 Mbps: the source is being delivered, at its
offered rate, with zero game loss and game p95 below 2.7 ms.

## Why the raw gate failed

`sink_last_third()` reads `bulk.sink.log` only. For this shape it returns
`None`, so `check_stress()` reports "no delivered stream". `s3_tv_and_gaming`
has no `drop_at_s`, `recover_at_s` or `ramp_to_mbps`, so `check_run()` fell
through to the stress lane.

The stress law is "deliver >= 0.50 of what you commit". With applied rates of
35.73-90.00 Mbps and a source that offers only 14.46 Mbps, the ratio is
0.16-0.43 **even on a perfect link**. The law is undefined without a bulk
source that can fill the committed rate. This is an applicability bug in the
judge, not a data-path fault.

## The fix

- A shape whose `workloads.json` has no `bulk` entry is `NOT APPLICABLE`
  (report-only), never PASS and never FAIL. The gate records the interactive
  delivered rate, game p95 and game loss as evidence.
- Bulk shapes with no capacity change are judged by the stress law only when
  declared as stress lanes (`s1_iso_during_call`, `s3_stress`). An unknown
  bulk shape fails instead of silently inheriting a law.
- The stress and ramp-down sink windows are cut from the **run's** samples,
  not the last commit (the same Round 9 truncation fixed for the UP lane).
  This changes the measured values, not any verdict: all stress and ramp
  runs still pass.

## Verdict

- Corrected final gate: `130 judged PASS, 0 FAIL, 10 NOT APPLICABLE of 140`.
- Dev gate: `100 judged PASS, 0 FAIL of 100`.
- Full suite: **1583 tests**, 0 failed, 10 live-kernel skips.

Raw log: `data/live_status_round3/final_verify.log` (130 PASS / 10 FAIL).
Corrected log: `data/experiments/final_verify_round9.txt`.
No final run was re-executed and no controller code changed; the 840 runs are
exactly the final band's output, all at `7c6c7235`.

## Reproduce (no root)

```bash
python3 tools/verify_round3.py data/runs_final3
python3 -m unittest discover -s tests -t .
```

## If you want to re-execute the ten cells (diagnostic, privileged)

```bash
sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_round3_batch.sh s3tv
python3 tools/verify_round3.py data/runs_rerun_s3tv
```

This is a separate results root (`data/runs_rerun_s3tv`). It does not touch
`data/runs_final3` and is not part of the frozen final band. The expected
output is `10 NOT APPLICABLE`, not `10 FAIL`.
