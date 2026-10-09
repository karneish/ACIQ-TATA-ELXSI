# The 6-seed matrix — measured 2026-10-08

54 runs: 3 scenarios x 3 systems x seeds 42-47, link dropped 100 -> 20 Mbps at t=20s.

Reproduce:

    sudo python3 run_experiments.py \
      --scenario s1_iso_during_call --scenario s2_wan_drop \
      --scenario s3_tv_and_gaming --enforce --seeds 6 --drop 20 --drop-at 20 \
      --results-dir data/matrix6 --report data/matrix6/REPORT.md

Rebuild the report alone — no root, no testbed, no re-running:

    python3 run_experiments.py --report-only \
      --results-dir data/matrix6 --report data/matrix6/REPORT.md

## What it says

Against b0_fifo, p50/p95/p99/loss all reach p = 0.0312. Against b1_cake95,
nothing does (p50 0.5625, p95 0.0625, p99 0.4375, jitter 0.8438).

**ACIQ removes pfifo's bufferbloat decisively and does not significantly differ
from cake.** 13 of 26 comparisons reach p < 0.05, and every one is against
pfifo. p = 0.0312 is 2/64, the smallest attainable at n = 6: it clears 0.05
barely and cannot go lower without more seeds.

## What it does not show

* **estimator is stale in 12 of 18 ACIQ runs.** M2 measures capacity only while
  the link is oversubscribed. After the drop the workload's own rate fell to
  just under the new capacity, so the link stopped being oversubscribed and the
  pre-drop reading was carried to the end of the run. Each result.json says so.
* **s3 never exercises M2 at all.** It offers ~14.3 Mbps; dropped to 20, that is
  71% utilisation. All six s3 ACIQ runs report estimator=None, policy_changes=0.
  The per-flow enforcement path is exercised; the adaptive path is not.
* One drop timing, one link shape, one machine.

## Layout

| file | what it is |
|---|---|
| REPORT.md | the generated report |
| */config.json | what was asked for, including enforce_requested |
| */result.json | what happened, including the enforcement note |
| */samples.jsonl | per-tick counters, verdicts, capacity |
| */workloads.json | each workload's own latency measurement |
| *.log, *.sink.log | generator and sink output |

Per-flow enforcement was ON for aciq only. The baselines were steered by
nothing, which is what makes them baselines.
