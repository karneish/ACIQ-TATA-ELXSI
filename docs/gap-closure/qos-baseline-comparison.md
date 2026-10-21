# FIFO / CAKE / ACIQ comparison

## MEASURED -- congested comparison, revision a84b86cb

7 paired seeds, `--enforce` on, per-flow steering verified in every run
(`filters_installed > 0`), 50 ms bottleneck buffer.

> **Provenance.** These figures are a record of the run stamped `a84b86cb`. That
> run's raw per-seed files are **not** in this repository — the `data/host_gate_*`
> directories here hold the *current-revision* run (`c5da3fd9`), not this one — so
> these numbers are reported, not re-derivable. The current-revision figures are
> in `docs/PROJECT_REPORT.md` and `docs/ACIQ_COMPLETE.md`, and the tool that
> re-derives them from the committed files is `tools/reconcile_results.py`.

| median of 7 seeds | FIFO | CAKE95 | **ACIQ** |
|---|---|---|---|
| **p50 latency** | 81.83 ms | 82.18 ms | **1.18 ms** |
| p95 latency | 90.91 ms | 92.39 ms | **70.84 ms** |
| p99 latency | 97.40 ms | 104.62 ms | **98.68 ms** |
| jitter | 0.83 ms | 0.86 ms | **0.74 ms** |
| loss | 0.40% | 0.40% | **0.10%** |

Paired, per seed:

| seed | p95 FIFO | p95 CAKE | p95 ACIQ | loss FIFO | loss CAKE | loss ACIQ |
|---|---|---|---|---|---|---|
| 42 | 107.19 | 92.73 | 70.84 | 3.85% | 0.25% | 0.00% |
| 43 | 90.91 | 91.94 | 71.97 | 0.50% | 0.35% | 0.10% |
| 44 | 91.69 | 92.39 | 71.36 | 0.20% | 0.45% | 0.10% |
| 45 | 90.54 | 90.72 | 59.78 | 0.50% | 0.45% | 0.05% |
| 46 | 89.70 | 92.57 | 62.35 | 0.30% | 0.40% | 0.20% |
| 47 | 89.86 | 91.36 | 64.26 | 0.40% | 0.60% | 0.10% |
| 48 | 92.64 | 92.84 | 80.51 | 0.25% | 0.30% | 0.05% |

- ACIQ lower p95 than FIFO: **7/7**
- ACIQ lower p95 than CAKE: **7/7**
- ACIQ lower loss than FIFO: **7/7**

The median is the headline: **1.18 ms against ~82 ms for both baselines**, a
factor of ~69. Under a saturated link the baselines put every call packet
through a full 82 ms of standing queue; ACIQ keeps the interactive class's queue
empty (measured backlog: 0 bytes, versus a bottleneck buffer that stays pinned
full when bulk is uncapped).

Supporting measurements from the same runs: bulk fell 19.88 -> 17.49 Mbps once
its ceiling reached the kernel, the bottleneck's backlog fell from ~75 packets
to a median of 1, and the capacity estimator converged to 20.57 Mbps against a
true 20.

### The p95 tail is real, and still not closed

ACIQ's p95 is 70.84 ms even though its p50 is 1.18 ms. The per-packet trace
(2995 packets, one seed) shows the tail is **no longer quantised to the pacing
interval** -- values are 59.78, 62.35, 64.26, 70.84, 80.51 ms -- so it is genuine
queueing rather than a measurement artefact. The bottleneck's backlog still
reaches its 83-packet limit transiently, and the capacity drop at t=5 s leaves
a period during which the estimator is still catching up.

So: the median claim is proven and the tail claim is not. Both are stated.


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
