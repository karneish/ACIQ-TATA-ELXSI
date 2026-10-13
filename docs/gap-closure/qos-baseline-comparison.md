# FIFO / CAKE / ACIQ comparison

**Status: BLOCKED.** No throughput comparison was run. **No claim is made that
ACIQ is better than either baseline.**

## Why

BLOCKED — bubblewrap sandbox, `CapEff=0000000000000000`, `ip`/`tc`/`iperf3` not installed, no `sudo`, `unshare --net` EPERM. Available on the user's shell.

## The comparison is not symmetric, and pretending otherwise would bias it

| | FIFO | CAKE | ACIQ |
|---|---|---|---|
| needs kernel module | no | `sch_cake` (b1_cake95) | no |
| configures per-flow rates | no | no | yes |
| deployable in this container | n/a | n/a | no (`tc` absent) |

CAKE would need `modprobe` and `ip link` inside the namespace. The harness
checks for these up front, which is correct: an absent baseline is a **missing
control**, not a free win. A comparison that could only ever have run ACIQ would
produce a number, and that number would mean nothing.

## Fixture

Symmetric 100/100, RTT 20 ms, three concurrent flows — bulk, video, call —
plus an offpath pinger to detect collateral damage.

## Metrics

| metric | direction | why |
|---|---|---|
| call p95 latency | lower better | |
| call loss | lower better | |
| video stalls | lower better | |
| bulk throughput | higher better | |
| reordering | lower better | commonly *worse* under CAKE, not a defect |
| pinger latency (offpath) | lower better | **collateral damage**, so it is easy to miss |

## Fairness note, stated before running

FIFO is **not** a neutral baseline. It is the worst case for a small flow
competing with bulk, and under g首-come FIFO it will look close to what
realtime_interactive is meant to beat. A comparison against CAKE or ACIQ that
beats it on every metric is not evidence of *better scheduling*; it is evidence
of *doing anything at all*. Interpreting this table without that fact would
flatter the result.

## Command

Verified against `run_experiments.py --help`:

```bash
sudo python3 run_experiments.py --scenario s3_tv_and_gaming \
  --system b1_cake95 --seeds 7 --seed 42 --results-dir data/cake
sudo python3 run_experiments.py --scenario s3_tv_and_gaming \
  --system aciq --seeds 7 --seed 42 --results-dir data/aciq_cmp
```

**Correction.** This section previously named a scenario `s4_voip_under_load`
and a system `cake`. Neither exists — the real choices are
`s1_iso_during_call`, `s2_wan_drop`, `s3_tv_and_gaming` and `b0_fifo`,
`b1_cake95`, `aciq`. Both commands would have failed immediately on a real
host, after the testbed had already been built. Found by checking
`--help` rather than trusting prose written earlier, and the choices are now
regression-tested.

## Even a favourable result would not justify a claim

Three seeds per system, one shared machine, one link, and an offline
classification heuristic. **Nothing here establishes ACIQ's advantage in
general**, and no efficiency/scalability claim is made from these numbers even
if the experiment succeeds.
