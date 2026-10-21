# ACIQ+ — Scenario B - WAN drop 100 -> 20 Mbps

Runs found: **21**

## Runs

| scenario | system | mode | seed | link start | link end | estimator | policy changes |
|---|---|---|---|---|---|---|---|
| s2_wan_drop | aciq | adaptive | 42 | 100.0 | 20.0 | 20.2 Mbps | 1 |
| s2_wan_drop | aciq | adaptive | 43 | 100.0 | 20.0 | 20.6 Mbps | 1 |
| s2_wan_drop | aciq | adaptive | 44 | 100.0 | 20.0 | 20.9 Mbps | 1 |
| s2_wan_drop | aciq | adaptive | 45 | 100.0 | 20.0 | 20.6 Mbps | 1 |
| s2_wan_drop | aciq | adaptive | 46 | 100.0 | 20.0 | 20.6 Mbps | 1 |
| s2_wan_drop | aciq | adaptive | 47 | 100.0 | 20.0 | 20.6 Mbps | 1 |
| s2_wan_drop | aciq | adaptive | 48 | 100.0 | 20.0 | 20.9 Mbps | 1 |
| s2_wan_drop | b0_fifo | static | 42 | 100.0 | 20.0 | n/a | 0 |
| s2_wan_drop | b0_fifo | static | 43 | 100.0 | 20.0 | n/a | 0 |
| s2_wan_drop | b0_fifo | static | 44 | 100.0 | 20.0 | n/a | 0 |
| s2_wan_drop | b0_fifo | static | 45 | 100.0 | 20.0 | n/a | 0 |
| s2_wan_drop | b0_fifo | static | 46 | 100.0 | 20.0 | n/a | 0 |
| s2_wan_drop | b0_fifo | static | 47 | 100.0 | 20.0 | n/a | 0 |
| s2_wan_drop | b0_fifo | static | 48 | 100.0 | 20.0 | n/a | 0 |
| s2_wan_drop | b1_cake95 | static | 42 | 100.0 | 20.0 | n/a | 0 |
| s2_wan_drop | b1_cake95 | static | 43 | 100.0 | 20.0 | n/a | 0 |
| s2_wan_drop | b1_cake95 | static | 44 | 100.0 | 20.0 | n/a | 0 |
| s2_wan_drop | b1_cake95 | static | 45 | 100.0 | 20.0 | n/a | 0 |
| s2_wan_drop | b1_cake95 | static | 46 | 100.0 | 20.0 | n/a | 0 |
| s2_wan_drop | b1_cake95 | static | 47 | 100.0 | 20.0 | n/a | 0 |
| s2_wan_drop | b1_cake95 | static | 48 | 100.0 | 20.0 | n/a | 0 |

## Latency, measured by each workload itself

### s2_wan_drop

**call latency — measured by the call itself** (milliseconds, lower is better)

Cells are **mean (min-max)** over seeds. A mean alone would hide the tails this project keeps getting wrong.

| system | n | p50 | p95 | p99 | jitter | loss |
|---|---|---|---|---|---|---|
| aciq | 7 | 1.180 (0.947-1.249) | 61.948 (2.225-82.217) | 88.891 (31.546-101.932) | 0.704 (0.554-0.800) | 0.001 (0.000-0.003) |
| b0_fifo | 7 | 82.340 (79.418-84.199) | 94.477 (90.048-107.751) | 101.983 (91.890-119.820) | 0.916 (0.804-1.139) | 0.009 (0.003-0.035) |
| b1_cake95 | 7 | 81.957 (77.143-84.000) | 92.374 (91.442-93.029) | 103.637 (95.748-111.737) | 0.844 (0.652-0.911) | 0.003 (0.002-0.004) |

- **p50: ACIQ beats b0_fifo and b1_cake95.**
- **p95: ACIQ beats b0_fifo and b1_cake95.**
- **p99: ACIQ beats b0_fifo and b1_cake95.**
- **jitter_ms: ACIQ beats b0_fifo and b1_cake95.**

**These verdicts are read per percentile, not cherry-picked.**
Where ACIQ loses, it loses in the table above too.


## Paired significance (Wilcoxon signed-rank, exact)

ACIQ against each rival, paired by seed. Exact, by enumerating sign flips -- 2^n, which is why n >= 6 is required before anything is claimed.

| scenario | workload | vs | metric | n | W+ | p | effect r (+ = ACIQ higher) |
|---|---|---|---|---|---|---|---|
| s2_wan_drop | call | b0_fifo | p50 | 7 | 0.0 | 0.0156 | -1.00 |
| s2_wan_drop | call | b0_fifo | p95 | 7 | 0.0 | 0.0156 | -1.00 |
| s2_wan_drop | call | b0_fifo | p99 | 7 | 9.0 | 0.4688 | -0.36 |
| s2_wan_drop | call | b0_fifo | jitter_ms | 7 | 0.0 | 0.0156 | -1.00 |
| s2_wan_drop | call | b0_fifo | loss_ratio | 7 | 0.0 | 0.0156 | -1.00 |
| s2_wan_drop | call | b1_cake95 | p50 | 7 | 0.0 | 0.0156 | -1.00 |
| s2_wan_drop | call | b1_cake95 | p95 | 7 | 0.0 | 0.0156 | -1.00 |
| s2_wan_drop | call | b1_cake95 | p99 | 7 | 3.0 | 0.0781 | -0.79 |
| s2_wan_drop | call | b1_cake95 | jitter_ms | 7 | 0.0 | 0.0156 | -1.00 |
| s2_wan_drop | call | b1_cake95 | loss_ratio | 7 | 0.0 | 0.0156 | -1.00 |

**8 of 10 comparisons reach p < 0.05.** Each is one metric against one rival in one scenario; they are not independent of each other, so this is a count of results, not a family-wise error rate.

## Reporting caveats

- **105 latency measurements** across the matrix, each self-reported by the workload that carried it.
- The link is an **HTB token-bucket emulation**, not real DSL/cable/fiber.
- Counter-based detection only sees a bottleneck **on the router**; a downstream ISP-side bottleneck stays invisible. Gate check 12 measured a validated remedy (an unmarked probe showed ~8x delay rise) that is not in the MVP.
- Classification accuracy is measured on **self-generated** traffic.
