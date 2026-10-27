# ACIQ+ experiment report

Runs found: **12**

## Runs

| scenario | system | mode | seed | link start | link end | estimator | policy changes |
|---|---|---|---|---|---|---|---|
| s1_iso_during_call | aciq | adaptive | 200 | 100.0 | 100.0 | 101.7 Mbps | 1 |
| s1_iso_during_call | aciq | adaptive | 201 | 100.0 | 100.0 | 101.6 Mbps | 1 |
| s1_iso_during_call | aciq | adaptive | 210 | 100.0 | 100.0 | 91.9 Mbps | 1 |
| s1_iso_during_call | aciq | adaptive | 211 | 100.0 | 100.0 | 91.7 Mbps | 1 |
| s2_wan_drop | aciq | adaptive | 200 | 100.0 | 20.0 | 21.4 Mbps | 2 |
| s2_wan_drop | aciq | adaptive | 201 | 100.0 | 20.0 | 20.1 Mbps | 3 |
| s2_wan_drop | aciq | adaptive | 210 | 100.0 | 20.0 | 19.1 Mbps | 3 |
| s2_wan_drop | aciq | adaptive | 211 | 100.0 | 20.0 | 19.5 Mbps | 3 |
| s4_capacity_recovery | aciq | adaptive | 200 | 100.0 | 20.0 | 18.8 Mbps | 4 |
| s4_capacity_recovery | aciq | adaptive | 201 | 100.0 | 20.0 | 18.7 Mbps | 4 |
| s4_capacity_recovery | aciq | adaptive | 210 | 100.0 | 20.0 | 20.5 Mbps | 2 |
| s4_capacity_recovery | aciq | adaptive | 211 | 100.0 | 20.0 | 20.2 Mbps | 3 |

## Latency, measured by each workload itself

### s1_iso_during_call

**call latency — measured by the call itself** (milliseconds, lower is better)

Cells are **mean (min-max)** over seeds. A mean alone would hide the tails this project keeps getting wrong.

| system | n | p50 | p95 | p99 | jitter | loss |
|---|---|---|---|---|---|---|
| aciq | 4 | 0.819 (0.628-0.975) | 42.583 (1.197-84.546) | 69.532 (1.447-137.094) | 0.508 (0.378-0.579) | 0.001 (0.000-0.001) |

### s2_wan_drop

**call latency — measured by the call itself** (milliseconds, lower is better)

Cells are **mean (min-max)** over seeds. A mean alone would hide the tails this project keeps getting wrong.

| system | n | p50 | p95 | p99 | jitter | loss |
|---|---|---|---|---|---|---|
| aciq | 4 | 0.952 (0.760-1.122) | 61.618 (52.877-68.379) | 99.279 (61.952-133.247) | 0.594 (0.544-0.640) | 0.001 (0.000-0.002) |

### s4_capacity_recovery

**call latency — measured by the call itself** (milliseconds, lower is better)

Cells are **mean (min-max)** over seeds. A mean alone would hide the tails this project keeps getting wrong.

| system | n | p50 | p95 | p99 | jitter | loss |
|---|---|---|---|---|---|---|
| aciq | 4 | 0.990 (0.854-1.109) | 44.945 (3.000-62.648) | 91.357 (47.900-124.732) | 0.606 (0.576-0.632) | 0.001 (0.000-0.001) |


**These verdicts are read per percentile, not cherry-picked.**
Where ACIQ loses, it loses in the table above too.


## Reporting caveats

- **60 latency measurements** across the matrix, each self-reported by the workload that carried it.
- The link is an **HTB token-bucket emulation**, not real DSL/cable/fiber.
- Counter-based detection only sees a bottleneck **on the router**; a downstream ISP-side bottleneck stays invisible. Gate check 12 measured a validated remedy (an unmarked probe showed ~8x delay rise) that is not in the MVP.
- Classification accuracy is measured on **self-generated** traffic.
