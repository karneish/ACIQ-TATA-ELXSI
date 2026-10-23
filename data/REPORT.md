# ACIQ+ experiment report

Runs found: **1**

## Runs

| scenario | system | mode | seed | link start | link end | estimator | policy changes |
|---|---|---|---|---|---|---|---|
| s2_wan_drop | b1_cake95 | static | 7 | 100.0 | 20.0 | n/a | 0 |

## Reporting caveats

- **1 run(s) per system.** Paired Wilcoxon cannot reach p < 0.05 with fewer than 6 pairs (the smallest attainable two-sided p is 2^(1-n), which is 0.0625 at n=5). Ranges and confidence intervals only — no p-values.
- **1 run(s) recorded no latency at all.** Shown as n/a rather than 0, because missing is not zero.
- **0 latency measurements** across the matrix, each self-reported by the workload that carried it.
- The link is an **HTB token-bucket emulation**, not real DSL/cable/fiber.
- Counter-based detection only sees a bottleneck **on the router**; a downstream ISP-side bottleneck stays invisible. Gate check 12 measured a validated remedy (an unmarked probe showed ~8x delay rise) that is not in the MVP.
- Classification accuracy is measured on **self-generated** traffic.
