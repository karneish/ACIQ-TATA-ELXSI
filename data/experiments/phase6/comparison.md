# Phase 6: baselines vs engine, paired by seed

## s2_wan_drop

| engine | workload | metric | pairs | base med | engine med | Δ | p (exact Wilcoxon) | notes |
|---|---|---|---|---|---|---|---|---|
| aciq | bulk | sender_mbps | 10 | 41.18 | 39.48 | -1.68 | 0.001953 | n=10, dropped-zero-pairs=0 |
| b1_cake95 | bulk | sender_mbps | 10 | 41.18 | 39.065 | -2.1 | 0.001953 | n=10, dropped-zero-pairs=0 |
| aciq | call | probe_jitter_ms | 10 | 2.7791 | 0.8762 | -1.93 | 0.001953 | n=10, dropped-zero-pairs=0 |
| b1_cake95 | call | probe_jitter_ms | 10 | 2.7791 | 0.6827 | -2.086 | 0.001953 | n=10, dropped-zero-pairs=0 |
| aciq | call | probe_loss_pct | 10 | 9.15 | 0.3 | -8.725 | 0.001953 | n=10, dropped-zero-pairs=0 |
| b1_cake95 | call | probe_loss_pct | 10 | 9.15 | 0.4 | -8.75 | 0.001953 | n=10, dropped-zero-pairs=0 |
| aciq | call | probe_p95_ms | 10 | 248.618 | 98.54 | -151.5 | 0.001953 | n=10, dropped-zero-pairs=0 |
| b1_cake95 | call | probe_p95_ms | 10 | 248.618 | 89.624 | -159.8 | 0.001953 | n=10, dropped-zero-pairs=0 |
| aciq | call | probe_p99_ms | 10 | 1148.0905 | 132.8175 | -1019 | 0.001953 | n=10, dropped-zero-pairs=0 |
| b1_cake95 | call | probe_p99_ms | 10 | 1148.0905 | 95.384 | -1053 | 0.001953 | n=10, dropped-zero-pairs=0 |
## s4_capacity_recovery

| engine | workload | metric | pairs | base med | engine med | Δ | p (exact Wilcoxon) | notes |
|---|---|---|---|---|---|---|---|---|
| aciq | bulk | sender_mbps | 10 | 33.78 | 32.67 | -1.11 | 0.001953 | n=10, dropped-zero-pairs=0 |
| b1_cake95 | bulk | sender_mbps | 10 | 33.78 | 32.385 | -1.395 | 0.001953 | n=10, dropped-zero-pairs=0 |
| aciq | call | probe_jitter_ms | 10 | 2.0556 | 0.8743 | -1.182 | 0.001953 | n=10, dropped-zero-pairs=0 |
| b1_cake95 | call | probe_jitter_ms | 10 | 2.0556 | 0.7128 | -1.349 | 0.001953 | n=10, dropped-zero-pairs=0 |
| aciq | call | probe_loss_pct | 10 | 6.1 | 0.367 | -5.734 | 0.001953 | n=10, dropped-zero-pairs=0 |
| b1_cake95 | call | probe_loss_pct | 10 | 6.1 | 0.2165 | -5.849 | 0.001953 | n=10, dropped-zero-pairs=0 |
| aciq | call | probe_p95_ms | 10 | 245.084 | 97.0225 | -148.1 | 0.001953 | n=10, dropped-zero-pairs=0 |
| b1_cake95 | call | probe_p95_ms | 10 | 245.084 | 89.749 | -155.1 | 0.001953 | n=10, dropped-zero-pairs=0 |
| aciq | call | probe_p99_ms | 10 | 896.021 | 125.2345 | -777.8 | 0.001953 | n=10, dropped-zero-pairs=0 |
| b1_cake95 | call | probe_p99_ms | 10 | 896.021 | 93.087 | -803.2 | 0.001953 | n=10, dropped-zero-pairs=0 |

Exact enumeration, no normal approximation; and a smaller `p` is reported as computed, not rounded to a symbol.
