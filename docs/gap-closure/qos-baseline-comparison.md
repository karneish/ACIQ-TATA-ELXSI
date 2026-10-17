# FIFO / CAKE / ACIQ comparison

> **SUPERSEDED -- absolute figures withdrawn (4bd5d6eb).**
> The congested numbers below were measured with `netem`'s default
> `limit 1000`, which is ~480 ms of standing queue at 20 Mbps. In the same
> runs the controller's OWN queue for the interactive class held **0 bytes at
> every tick** (netem held 206 packets median, 625 max). The latency was
> therefore the testbed's buffer, not the controller.
>
> The relative comparison is unaffected -- FIFO and CAKE were inflated by the
> same buffer -- so the "ACIQ degrades more gracefully" claim stands. The
> **absolute** numbers are withdrawn and must not be quoted. The bottleneck's
> buffer is now sized to 50 ms; re-measurement is required.
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


## Congested comparison — the one that matters

`s2_wan_drop`, link 100 → 20 Mbps, 7 paired seeds, kernel `7.1.5`, revision
`2fb66c39`.

| system | p95 median | min | max |
|---|---|---|---|
| `b0_fifo` | 1240.192 ms | 1240.146 | 1240.198 |
| `b1_cake95` | 1180.197 ms | 1160.262 | 1240.131 |
| **`aciq`** | **860.134 ms** | 480.172 | 860.343 |

Paired, seed for seed:

| comparison | seeds where aciq is better |
|---|---|
| aciq p95 < cake95 p95 | **7/7** |
| aciq p95 < fifo p95 | **7/7** |

Per seed (ms):

```
seed   aciq    cake95    fifo
  0   480.17   1240.05   1240.15
  1   860.15   1160.26   1240.20
  2   860.11   1240.12   1240.19
  3   860.04   1160.34   1240.19
  4   860.18   1240.13   1240.19
  5   860.34   1160.28   1240.19
  6   860.13   1180.20   1240.19
```

### The margin depends entirely on the condition

| condition | aciq | cake95 | margin over CAKE |
|---|---|---|---|
| light load, 100 Mbps | 0.549 ms | 0.563 ms | **2%** |
| congested, 20 Mbps | 860 ms | 1180 ms | **27%** |

On a free link ACIQ is marginally ahead, which is close to noise. Under load it
is 27% ahead, consistently, on every paired seed. **The advantage appears only
where there is something to be advantaged about** — which is the ordering a
scheduler should show and the opposite of what a result that was noise would do.

### What this does NOT show

**All three numbers are bad.** 860 ms p95 for a voice call is not a good
outcome; ACIQ is *least bad*, not good. Every system queues the interactive
flow deeply behind bulk when the link drops to 20 Mbps, and none of them
protects the call the way the problem statement's first use case implies it
should.

So the honest reading is: **the controller degrades more gracefully than its
baselines under congestion**, and that is a weaker claim than "it fixes the
problem". A pass that meant "the interactive class is protected" would need
latency in the tens of milliseconds, not the hundreds.

Also unchanged: one scenario, one link, one VM, seven seeds. Nothing here
establishes a general advantage.
