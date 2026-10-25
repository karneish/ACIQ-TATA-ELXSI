# ACIQ+ experiment report

Runs found: **1**

## Runs

| scenario | system | mode | seed | link start | link end | estimator | policy changes |
|---|---|---|---|---|---|---|---|
| s2_wan_drop | aciq | adaptive | 42 | 100.0 | 20.0 | 21.4 Mbps | 4 |

## Latency, measured by each workload itself

### s2_wan_drop

**call latency — measured by the call itself** (milliseconds, lower is better)

Cells are **mean (min-max)** over seeds. A mean alone would hide the tails this project keeps getting wrong.

| system | n | p50 | p95 | p99 | jitter | loss |
|---|---|---|---|---|---|---|
| aciq | 1 | 1.016 | 70.312 | 130.692 | 0.605 | 0.003 |


**These verdicts are read per percentile, not cherry-picked.**
Where ACIQ loses, it loses in the table above too.


## Reporting caveats

- **1 run(s) per system.** Paired Wilcoxon cannot reach p < 0.05 with fewer than 6 pairs (the smallest attainable two-sided p is 2^(1-n), which is 0.0625 at n=5). Ranges and confidence intervals only — no p-values.
- **5 latency measurements** across the matrix, each self-reported by the workload that carried it.
- The link is an **HTB token-bucket emulation**, not real DSL/cable/fiber.
- Counter-based detection only sees a bottleneck **on the router**; a downstream ISP-side bottleneck stays invisible. Gate check 12 measured a validated remedy (an unmarked probe showed ~8x delay rise) that is not in the MVP.
- Classification accuracy is measured on **self-generated** traffic.
