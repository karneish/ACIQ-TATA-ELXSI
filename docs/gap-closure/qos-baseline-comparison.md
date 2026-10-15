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


## Measured result

`s3_tv_and_gaming`, 7 paired seeds, kernel `7.1.5-76070105-generic`, iproute2
`6.1.0`, revision `56a82be8`. Read from each run's final `<label>.json` for the
`game` workload.

| system | n | p95 median | jitter median | loss |
|---|---|---|---|---|
| `b0_fifo` | 7 | **33.612 ms** | 6.2406 ms | 0.0 |
| `b1_cake95` | 7 | **0.592 ms** | 0.0949 ms | 0.0 |
| `aciq` | 7 | **0.563 ms** | 0.0867 ms | 0.0 |

Paired, seed for seed:

| comparison | seeds where aciq is better |
|---|---|
| aciq p95 < cake95 p95 | **7/7** |
| aciq p95 < fifo p95 | **7/7** |

### What this does and does not show

**Against FIFO the result is unambiguous**: 33.6 ms vs 0.563 ms p95. But that
is close to free — FIFO is the do-nothing case, and beating it shows only that
queueing discipline matters. It is not evidence of good scheduling.

**Against CAKE the margin is small**: 0.563 vs 0.592 ms, about 5%, consistent in
direction across 7/7 paired seeds. It is a real ordering, and 7/7 is a sign-test
p of 0.008, but it is a narrow one.

**The scenario does not stress the link.** `s3_tv_and_gaming` has no capacity
change and the interactive workload runs at 30 pps — roughly 1200 packets in 40
seconds. Every system had an uncongested link, which is precisely the regime
CAKE is built for. **This comparison does not demonstrate an advantage under
congestion**, and no such claim is made.

### A measurement gap that made this nearly invisible

Every `rtt_p95` in `result.json` is `None` for every run of every system. The
live ingestion path (`_ingest_probes`) reads `<label>.partial.json`, which the
generators do not write — only the final `<label>.json` exists. So:

- the per-tick series carries goodput, counters and backlog, and no latency;
- the latency was measured, and written, but only at the end of the run.

The acceptance gate initially reported this comparison as **PASS on seed counts
alone**, having verified 7 runs per system and nothing else. That is the same
failure as everywhere else this session: counting something that is not the
evidence. It now requires measurements and reports the medians, so a tree of
runs containing no latency data is `NOT RUN`.
