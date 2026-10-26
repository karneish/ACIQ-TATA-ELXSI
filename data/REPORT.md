# ACIQ+ experiment report

Runs found: **40**

## Runs

| scenario | system | mode | seed | link start | link end | estimator | policy changes |
|---|---|---|---|---|---|---|---|
| s1_iso_during_call | aciq | adaptive | 400 | 100.0 | 100.0 | 101.7 Mbps | 1 |
| s1_iso_during_call | aciq | adaptive | 401 | 100.0 | 100.0 | 101.8 Mbps | 1 |
| s1_iso_during_call | aciq | adaptive | 402 | 100.0 | 100.0 | 101.7 Mbps | 1 |
| s1_iso_during_call | aciq | adaptive | 403 | 100.0 | 100.0 | 101.6 Mbps | 1 |
| s1_iso_during_call | aciq | adaptive | 404 | 100.0 | 100.0 | 101.6 Mbps | 1 |
| s1_iso_during_call | aciq | adaptive | 405 | 100.0 | 100.0 | 101.8 Mbps | 1 |
| s1_iso_during_call | aciq | adaptive | 406 | 100.0 | 100.0 | 102.0 Mbps | 1 |
| s1_iso_during_call | aciq | adaptive | 407 | 100.0 | 100.0 | 101.8 Mbps | 1 |
| s1_iso_during_call | aciq | adaptive | 408 | 100.0 | 100.0 | 101.8 Mbps | 1 |
| s1_iso_during_call | aciq | adaptive | 409 | 100.0 | 100.0 | 102.1 Mbps | 1 |
| s2_wan_drop | aciq | adaptive | 400 | 100.0 | 20.0 | 21.6 Mbps | 3 |
| s2_wan_drop | aciq | adaptive | 401 | 100.0 | 20.0 | 21.5 Mbps | 3 |
| s2_wan_drop | aciq | adaptive | 402 | 100.0 | 20.0 | 21.4 Mbps | 3 |
| s2_wan_drop | aciq | adaptive | 403 | 100.0 | 20.0 | 21.4 Mbps | 3 |
| s2_wan_drop | aciq | adaptive | 404 | 100.0 | 20.0 | 21.6 Mbps | 3 |
| s2_wan_drop | aciq | adaptive | 405 | 100.0 | 20.0 | 21.6 Mbps | 3 |
| s2_wan_drop | aciq | adaptive | 406 | 100.0 | 20.0 | 21.4 Mbps | 3 |
| s2_wan_drop | aciq | adaptive | 407 | 100.0 | 20.0 | 21.5 Mbps | 3 |
| s2_wan_drop | aciq | adaptive | 408 | 100.0 | 20.0 | 21.6 Mbps | 3 |
| s2_wan_drop | aciq | adaptive | 409 | 100.0 | 20.0 | 21.5 Mbps | 3 |
| s3_tv_and_gaming | aciq | adaptive | 400 | 100.0 | 100.0 | 37.6 Mbps | 6 |
| s3_tv_and_gaming | aciq | adaptive | 401 | 100.0 | 100.0 | 59.0 Mbps | 6 |
| s3_tv_and_gaming | aciq | adaptive | 402 | 100.0 | 100.0 | 38.6 Mbps | 5 |
| s3_tv_and_gaming | aciq | adaptive | 403 | 100.0 | 100.0 | 47.9 Mbps | 6 |
| s3_tv_and_gaming | aciq | adaptive | 404 | 100.0 | 100.0 | 13.2 Mbps | 6 |
| s3_tv_and_gaming | aciq | adaptive | 405 | 100.0 | 100.0 | 67.2 Mbps | 6 |
| s3_tv_and_gaming | aciq | adaptive | 406 | 100.0 | 100.0 | 9.9 Mbps | 6 |
| s3_tv_and_gaming | aciq | adaptive | 407 | 100.0 | 100.0 | 15.8 Mbps | 6 |
| s3_tv_and_gaming | aciq | adaptive | 408 | 100.0 | 100.0 | 9.5 Mbps | 6 |
| s3_tv_and_gaming | aciq | adaptive | 409 | 100.0 | 100.0 | 67.2 Mbps | 6 |
| s4_capacity_recovery | aciq | adaptive | 400 | 100.0 | 20.0 | 21.5 Mbps | 7 |
| s4_capacity_recovery | aciq | adaptive | 401 | 100.0 | 20.0 | 21.5 Mbps | 7 |
| s4_capacity_recovery | aciq | adaptive | 402 | 100.0 | 20.0 | 21.5 Mbps | 7 |
| s4_capacity_recovery | aciq | adaptive | 403 | 100.0 | 20.0 | 21.4 Mbps | 6 |
| s4_capacity_recovery | aciq | adaptive | 404 | 100.0 | 20.0 | 21.8 Mbps | 7 |
| s4_capacity_recovery | aciq | adaptive | 405 | 100.0 | 20.0 | 18.8 Mbps | 7 |
| s4_capacity_recovery | aciq | adaptive | 406 | 100.0 | 20.0 | 21.4 Mbps | 7 |
| s4_capacity_recovery | aciq | adaptive | 407 | 100.0 | 20.0 | 21.5 Mbps | 7 |
| s4_capacity_recovery | aciq | adaptive | 408 | 100.0 | 20.0 | 21.8 Mbps | 7 |
| s4_capacity_recovery | aciq | adaptive | 409 | 100.0 | 20.0 | 21.4 Mbps | 7 |

## Latency, measured by each workload itself

### s1_iso_during_call

**call latency — measured by the call itself** (milliseconds, lower is better)

Cells are **mean (min-max)** over seeds. A mean alone would hide the tails this project keeps getting wrong.

| system | n | p50 | p95 | p99 | jitter | loss |
|---|---|---|---|---|---|---|
| aciq | 10 | 0.987 (0.943-1.017) | 83.738 (83.174-84.920) | 137.241 (136.539-137.840) | 0.564 (0.544-0.598) | 0.002 (0.001-0.003) |

### s2_wan_drop

**call latency — measured by the call itself** (milliseconds, lower is better)

Cells are **mean (min-max)** over seeds. A mean alone would hide the tails this project keeps getting wrong.

| system | n | p50 | p95 | p99 | jitter | loss |
|---|---|---|---|---|---|---|
| aciq | 10 | 1.130 (1.112-1.171) | 72.903 (64.079-79.295) | 132.927 (132.459-133.466) | 0.606 (0.573-0.640) | 0.003 (0.002-0.004) |

### s3_tv_and_gaming

**game latency — measured by the game itself** (milliseconds, lower is better)

Cells are **mean (min-max)** over seeds. A mean alone would hide the tails this project keeps getting wrong.

| system | n | p50 | p95 | p99 | jitter | loss |
|---|---|---|---|---|---|---|
| aciq | 10 | 0.502 (0.492-0.516) | 2.172 (1.949-2.398) | 3.838 (3.331-4.177) | 0.498 (0.435-0.534) | 0.000 |

### s4_capacity_recovery

**call latency — measured by the call itself** (milliseconds, lower is better)

Cells are **mean (min-max)** over seeds. A mean alone would hide the tails this project keeps getting wrong.

| system | n | p50 | p95 | p99 | jitter | loss |
|---|---|---|---|---|---|---|
| aciq | 10 | 25.465 (1.436-40.618) | 98.956 (92.477-105.994) | 129.117 (123.187-174.379) | 0.729 (0.700-0.815) | 0.003 (0.002-0.004) |


**These verdicts are read per percentile, not cherry-picked.**
Where ACIQ loses, it loses in the table above too.


## Reporting caveats

- **200 latency measurements** across the matrix, each self-reported by the workload that carried it.
- The link is an **HTB token-bucket emulation**, not real DSL/cable/fiber.
- Counter-based detection only sees a bottleneck **on the router**; a downstream ISP-side bottleneck stays invisible. Gate check 12 measured a validated remedy (an unmarked probe showed ~8x delay rise) that is not in the MVP.
- Classification accuracy is measured on **self-generated** traffic.
