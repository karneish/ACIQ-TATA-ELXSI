# ACIQ+ experiment report

Runs found: **6**

## Runs

| scenario | system | mode | seed | link start | link end | estimator | policy changes |
|---|---|---|---|---|---|---|---|
| s1_iso_during_call | aciq | adaptive | 42 | 100.0 | 100.0 | 100.5 Mbps | 1 |
| s1_iso_during_call | b0_fifo | static | 42 | 100.0 | 100.0 | n/a | 0 |
| s1_iso_during_call | b1_cake95 | static | 42 | 100.0 | 100.0 | n/a | 0 |
| s3_tv_and_gaming | aciq | adaptive | 42 | 100.0 | 100.0 | n/a | 0 |
| s3_tv_and_gaming | b0_fifo | static | 42 | 100.0 | 100.0 | n/a | 0 |
| s3_tv_and_gaming | b1_cake95 | static | 42 | 100.0 | 100.0 | n/a | 0 |

## Latency, measured by each workload itself

### s1_iso_during_call

**call latency — measured by the call itself** (milliseconds, lower is better)

| system | p50 | p95 | p99 | jitter | loss |
|---|---|---|---|---|---|
| aciq | 0.180 | 0.950 | 20.071 | 0.776 | 0.00000 |
| b0_fifo | 119.675 | 121.470 | 126.901 | 2.580 | 0.00400 |
| b1_cake95 | 0.283 | 19.732 | 21.282 | 3.125 | 0.00000 |

- **p50: ACIQ beats b0_fifo and b1_cake95.**
- **p95: ACIQ beats b0_fifo and b1_cake95.**
- **p99: ACIQ beats b0_fifo and b1_cake95.**
- **jitter_ms: ACIQ beats b0_fifo and b1_cake95.**
### s3_tv_and_gaming

**game latency — measured by the game itself** (milliseconds, lower is better)

| system | p50 | p95 | p99 | jitter | loss |
|---|---|---|---|---|---|
| aciq | 0.396 | 0.552 | 0.897 | 0.119 | 0.00000 |
| b0_fifo | 0.325 | 33.477 | 33.693 | 5.636 | 0.00000 |
| b1_cake95 | 0.241 | 1.637 | 33.449 | 1.781 | 0.00000 |

- **p50: ACIQ LOSES to b0_fifo and b1_cake95.**
- **p95: ACIQ beats b0_fifo and b1_cake95.**
- **p99: ACIQ beats b0_fifo and b1_cake95.**
- **jitter_ms: ACIQ beats b0_fifo and b1_cake95.**

**These verdicts are read per percentile, not cherry-picked.**
Where ACIQ loses, it loses in the table above too.


## Reporting caveats

- **2 run(s) per system.** Paired Wilcoxon cannot reach p < 0.05 with fewer than 6 pairs (the smallest attainable two-sided p is 2^(1-n), which is 0.0625 at n=5). Ranges and confidence intervals only — no p-values.
- **18 latency measurements** across the matrix, each self-reported by the workload that carried it.
- The link is an **HTB token-bucket emulation**, not real DSL/cable/fiber.
- Counter-based detection only sees a bottleneck **on the router**; a downstream ISP-side bottleneck stays invisible. Gate check 12 measured a validated remedy (an unmarked probe showed ~8x delay rise) that is not in the MVP.
- Classification accuracy is measured on **self-generated** traffic.
