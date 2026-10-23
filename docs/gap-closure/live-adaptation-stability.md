# Live adaptation and control-loop stability

**Status: BLOCKED.** No live control-loop measurement in this run.

## Why

BLOCKED — this shell is a bubblewrap sandbox with CapEff=0000000000000000. `ip`, `tc`, `iperf3` are not installed at package level (dpkg -s returns not installed), `sudo` is absent, and `unshare --net` fails with EPERM. The user's shell runs the same commands successfully, so this is an environment limit and not a claim about the code.

## Verified without a kernel

The estimator is correct on a recorded holdout. `data/ab_lease_42` was captured
*before* the backlog signal existed:

```
100 -> 45.97 -> 24.38 -> 15.41 -> 12.15 -> 10.86 Mbps     (true capacity 10)
```

Monotone, never below the link. Seven tests, including that no intermediate
estimate falls below the true capacity.

**That is a replay.** It is not a live experiment and is not reported as one.

**Command correction.** This section previously paired `--drop` with
`s3_tv_and_gaming`. Only `s2_wan_drop` is about a capacity change; the driver
warns when a drop is requested without `--drop-at` for exactly this reason.

**The 30-minute requirement was not reachable** through the CLI: every shipped
scenario is 30-40 seconds and `duration_s` was hardcoded per scenario. Rather
than document the gap and stop, `--duration-s` was added, which replaces the
scenario without mutating it and without touching the defaults. Verified:
overriding to 1800s preserves every workload and DSCP marking.

## Timings the prompt asks for

| quantity | status |
|---|---|
| observation / decision / enforcement interval | not measured |
| measurement age at decision time | not measured |
| detection delay | not measured |
| policy install time | not measured |
| recovery time after capacity restore | not measured |
| policy changes per unit time | not measured live |
| oscillation | not measured |
| CPU / memory under control | arithmetic benchmarked; loop not |

## Stability: no run exceeds 40 seconds

The prompt asks for at least 30 minutes. **No run in `data/` exceeds 40
seconds.** Nothing here supports a long-run claim, and the absence of observed
oscillation over 40 s is not evidence of stability.

What is bounded by design: RTT window per label, lease book, verdict history,
rate-limit table, filter residue.

## Commands for a Linux host

```bash
# detection + policy install, with the applied tree in the audit
sudo python3 run_experiments.py --scenario s2_wan_drop --system aciq \
  --enforce --drop 10 --drop-at 5 --seed 42 --results-dir data/adapt42

# 30-minute soak. No shipped scenario is longer than 40s, so the override is
# what makes this possible at all.
sudo python3 run_experiments.py --scenario s3_tv_and_gaming --system aciq \
  --enforce --duration-s 1800 --results-dir data/soak

# while it runs, in another terminal -- watch the parent rate
for i in $(seq 1 60); do
  printf '%s ' "$(date +%T)"
  sudo ip netns exec router tc class show dev veth-lan 2>/dev/null \
    | grep 'class htb 1:1 root'
  sleep 30
done
```

Acceptance thresholds must be set **before** running. Proposed engineering
thresholds, not requirements from the brief: detection within 10 s of a capacity
change, policy installed within a further 5 s, no more than 2 policy changes per
minute after settling, parent ceiling never above cap + 5%.
