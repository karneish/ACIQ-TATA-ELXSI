# ACIQ+ experiment report

Runs found: **3**

## Runs

| scenario | system | mode | seed | link start | link end | estimator | policy changes |
|---|---|---|---|---|---|---|---|
| s3_tv_and_gaming | aciq | adaptive | 42 | 100.0 | 100.0 | n/a | 0 |
| s3_tv_and_gaming | b0_fifo | static | 42 | 100.0 | 100.0 | n/a | 0 |
| s3_tv_and_gaming | b1_cake95 | static | 42 | 100.0 | 100.0 | n/a | 0 |

## Latency, measured by each workload itself

### s3_tv_and_gaming

**game latency — measured by the game itself** (milliseconds, lower is better)

| system | p50 | p95 | p99 | jitter | loss |
|---|---|---|---|---|---|
| aciq | 0.476 | 0.581 | 0.776 | 0.155 | 0.00000 |
| b0_fifo | 0.473 | 33.577 | 33.703 | 6.135 | 0.00000 |
| b1_cake95 | 0.482 | 0.578 | 0.703 | 0.084 | 0.00000 |

- **p50: ACIQ beats b1_cake95 LOSES to b0_fifo.**
- **p95: ACIQ beats b0_fifo LOSES to b1_cake95.**
- **p99: ACIQ beats b0_fifo LOSES to b1_cake95.**
- **jitter_ms: ACIQ beats b0_fifo LOSES to b1_cake95.**

**These verdicts are read per percentile, not cherry-picked.**
Where ACIQ loses, it loses in the table above too.


## Reporting caveats

- **1 run(s) per system.** Paired Wilcoxon cannot reach p < 0.05 with fewer than 6 pairs (the smallest attainable two-sided p is 2^(1-n), which is 0.0625 at n=5). Ranges and confidence intervals only — no p-values.
- **9 latency measurements** across the matrix, each self-reported by the workload that carried it.
- The link is an **HTB token-bucket emulation**, not real DSL/cable/fiber.
- Counter-based detection only sees a bottleneck **on the router**; a downstream ISP-side bottleneck stays invisible. Gate check 12 measured a validated remedy (an unmarked probe showed ~8x delay rise) that is not in the MVP.
- Classification accuracy is measured on **self-generated** traffic.
