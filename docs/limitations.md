# Known Limitations

Written before the results are flattering, so that nothing here is an excuse
made afterwards. Where a limitation was *discovered by measurement*, the number
is given.

## 1. The emulated link is not a real link

The slow line is **HTB class `1:1`** — a token-bucket shaper. It does not model
DSL or cable overhead, ISP policing, modem behaviour, or a real CPE. Real
broadband has latency that varies with load and a buffer that overflows; this has
neither.

`netem` supplies delay and loss only, never bandwidth. Using `netem` for rate
would have been simpler and would have been dishonest about what is being
emulated.

## 2. Capacity estimation cannot see a bottleneck it is not on

M2 reads queue counters from the router. In a real home the bottleneck is usually
the modem or the ISP side, where router counters show **nothing at all** — no
drop, no overlimit, no backlog.

This is the most important limitation, and it was confirmed by measurement rather
than assumed:

| Condition | Measured `overlimits` |
|---|---|
| 100 Mbps link genuinely full | 5127 – 6485 /s |
| 20 Mbps link saturated | 24803 – 65101 /s |
| 100 Mbps link ~10% loaded, children rate-limited | 170 – 1313 /s |

Separating "link full" from "class rate-limited" works by *magnitude* against
those two populations, with roughly 4× margin. That is a threshold fitted to
observed data, not a proof. A link pushed 1% over its limit by many children
would look like the full case.

**A validated remedy exists but is not in the MVP.** Gate check 12 measured an
unmarked probe rising from 0.051 ms to 0.405 ms (~8×) under saturation. An EF
probe in the protected class showed no signal at all (0.051 → 0.070 ms) because
it reports how well that class is protected, not whether the link is full. So the
signal must come from the bulk path, and it costs probe traffic that would need
accounting in the CPU-overhead numbers.

## 3. Passive estimation needs a busy link

On an idle link, observed throughput is offered load, not capacity. M2 therefore
does not learn from unsaturated samples, and its confidence **decays** when idle
rather than holding a stale high value. A link that is never busy yields no
capacity estimate at all — `n/a`, not a guess.

## 4. Classification accuracy is measured on self-generated traffic

All traffic comes from our own generators. Real homes have applications we do
not model. Accuracy reported here will look better than reality.

Deliberately, the classifier ignores the generators' own ports, so it cannot
score a meaningless 100%. The residual known-hard case: **UDP/443 carries both
video calls and large downloads**, and when nothing distinguishes them the flow
is reported UNCLASSIFIED rather than guessed.

## 5. Three of the four traffic classes are not populated

Only `INTERACTIVE` receives traffic. Nothing routes to `ADAPTIVE` or `LEASED`:

- **ADAPTIVE** — the classifier never emits it, and no filter targets `1:20`.
  Non-EF traffic falls to the HTB default `1:30` (BULK). Measured:
  `adaptive_video: goodput 0.0`.
  **Correcting the original wording:** the earlier version of this file said
  "in every sample", and specifically "in every s3 sample". That was not
  measured. `s3_tv_and_gaming__aciq__adaptive__seed42` has **no
  `samples.jsonl` at all** -- the run died before artefact collection, which
  `data/baselines/v0/README.md` already documented. The 0.0 is real, but it
  comes from **s1** (`s1_iso_during_call__aciq__adaptive__seed42`, where
  `adaptive_video: 0.0` and `bulk_transfer: 99.926`), and s1 has no video
  workload, so the 0.0 there is trivially expected.
- **LEASED** — class `1:40` is created and given bandwidth, but no filter routes
  to it. The lease allocates to an empty queue.

See `docs/WIRING_AUDIT.md` for the per-module evidence.

## 5b. Superseded 2026-10-08: ADAPTIVE now receives traffic

The first measured run with per-flow enforcement enabled,
`data/enforced/seed42/s3_tv_and_gaming__aciq__adaptive__seed42`:

| tick | interactive | adaptive | bulk | verdict |
|---|---|---|---|---|
| 0.0 | 0.000 | 0.000 | 0.000 | all UNCLASSIFIED, too young |
| 1.02 | 0.042 | 0.000 | **24.245** | still unclassified -- video in BULK |
| 2.03 | 0.040 | 0.000 | 24.419 | classifier fires: game->interactive, tv1-3->adaptive |
| 3.06 | 0.041 | **23.907** | 0.726 | all three video streams moved to 1:20 |
| 4.08 | 0.042 | **24.288** | 0.000 | steady |

( Mbps, from `samples.jsonl`.)

Two independent measurements agree: the adaptive class carried **13.96 Mbps**
mean over 37 ticks, and the three generators sent 3 x 23,808,750 B over 40 s =
**14.29 Mbps**. Every sink received exactly what its sender sent, so nothing was
dropped in moving between classes. The game reported p50 0.467 ms, p95 0.562,
p99 0.669, 0% loss, and 30/30 pps achieved.

Ticks 0-2 are a within-run control: before the classifier fires, the video is in
BULK, which is the v0 behaviour, observed in the same run rather than compared
against another.

**Caveats, and they are not small.**

* **One run, one seed, no baseline in the same run.** This shows the mechanism
  works. It does not show it helps. The report correctly refuses a p-value.
* **`estimator=None`, `capacity_mbps = 0.0`.** M2 never measured: ~14 Mbps on a
  100 Mbps link is not saturated, so no reading was emitted. The classifier ran
  the whole run on the **configured 100 Mbps fallback**, not a measurement. The
  two agree here by luck -- at 14.3 Mbps against 100 Mbps the capacity-relative
  thresholds land in the same place either way. A run that saturates the link
  would exercise the measured path instead.
* This is a *mechanism* result. Whether steering video to 1:20 improves anything
  needs paired runs against `b0_fifo` and `b1_cake95`.



## 5c. The first paired comparison (2026-10-08)

`data/enforced/paired42/` -- s3_tv_and_gaming, seed 42, all three systems. Game
latency, self-reported by the game workload:

| system | p50 | p95 | p99 | jitter | loss |
|---|---|---|---|---|---|
| aciq (enforced) | 0.476 | 0.581 | 0.776 | 0.155 | 0.000 |
| b0_fifo | 0.473 | **33.577** | **33.703** | **6.135** | 0.000 |
| b1_cake95 | 0.482 | 0.578 | 0.703 | 0.084 | 0.000 |

**Read honestly:**

* ACIQ beats pfifo by ~58x at p95 and p99 and by ~40x on jitter.
* ACIQ **loses** to cake on all four, by 3-6 microseconds. At that scale these are
  ties and the report is technically right to call them losses.
* One run, one seed, no p-value. The report refuses one for good reason.

### pfifo's 33 ms is NOT explained, and this file will not pretend it is

The obvious reading is bufferbloat. The data does not support it:

* `b0_fifo` recorded **0 drops, 0 backlog** on the link for the whole run.
* The offered load was ~14 Mbps on a 100 Mbps parent -- roughly 14% utilisation.
  A `pfifo limit 1000` queue under a 100 Mbps shaper has no reason to build at
  14% utilisation.
* The artefacts contain **no per-packet RTT trace**; `game.json` stores only
  percentiles, so the 33 ms cannot be localised to a burst or a moment.

So pfifo's p95 is a real measurement whose cause is unknown. Calling it
bufferbloat would be the same error as calling a win a loss -- in the other
direction, and just as unsupported.

### Per-class comparison across systems is not possible yet

`per_class` is populated for `aciq` and **empty for both baselines**, because
their trees have one class that does not map to the ACIQ class names. So
`fairness` reads 0.000 for both baselines, meaning *unavailable*, not *zero
unfairness*. Video is known to sit in bulk for the baselines by construction,
not by measurement.

### Also note: `link.cls` is mislabelled

Every sample of every system records the parent counter under
`link.cls = "realtime_interactive"`. The parent is class `1:1` and is not
`realtime_interactive`. M2 reads only the numbers, so no measurement is
affected, but the artefact is misleading and should be relabelled.

### This run tested the steady-state tree, not adaptation

`estimator=None`, `policy_changes=0`, no capacity drop. At 100 Mbps with 14 Mbps
offered, M2 never saw saturation and nothing had to adapt. The enforced
per-flow path *is* exercised -- video was measured at 13.96 Mbps mean in class
1:20 -- but nothing about capacity adaptation was.

## 5d. The 6-seed matrix (2026-10-08), and two reporting bugs it exposed

`data/matrix6/` -- 54 runs, 3 scenarios x 3 systems x seeds 42-47, 100 -> 20 Mbps
drop at t=20 s. Reproduce:

    sudo python3 run_experiments.py \
      --scenario s1_iso_during_call --scenario s2_wan_drop \
      --scenario s3_tv_and_gaming --enforce --seeds 6 --drop 20 --drop-at 20 \
      --results-dir data/matrix6 --report data/matrix6/REPORT.md

### The report was showing ONE seed under a "54 runs" header

`latency_table` assigned per run directory, so each seed overwrote the last. s1's
ACIQ row read p99=18.461 ms. The six seeds were:

    2.665   1.443   2.147   20.104   2.538   18.461

Two of six hit ~20 ms and the reported number was one of them. The verdict
bullets were one seed's luck. Fixed: cells are mean (min-max) with n stated, and
the seed travels with each value so pairs can be formed.

### No p-value had ever been computed

`build_report` only ever *withdrew the caveat* once 6 runs existed. Nothing
implemented the other branch, so at n=6 the warning vanished and no number
appeared -- silence that reads as significance.

`exact_wilcoxon` is now implemented (two-sided signed-rank, exact, by
enumerating 2^n sign flips; no scipy on this machine and none needed).

### What the result actually says

| comparison | metrics | verdict |
|---|---|---|
| vs `b0_fifo` | p50, p95, p99, loss | p = 0.0312 -- significant |
| vs `b1_cake95` | p50 0.5625, p95 0.0625, p99 0.4375, jitter 0.8438 | **not significant** |

13 of 26 comparisons reach p < 0.05, all of them against pfifo. The defensible
claim is: **ACIQ removes pfifo's bufferbloat decisively, and does not
significantly differ from cake.** The earlier "ACIQ beats both" was an artefact
of comparing one seed.

Note p = 0.0312 is 2/64, the floor at n=6. It barely clears 0.05 and cannot go
lower without more seeds.

### M2 cannot see a drop the workload adapts to

Twelve runs reported `estimator=102.77 Mbps` beside `link_end=20.0`. The
mechanism, from `samples.jsonl`:

| t | link overlimits/s | bulk goodput | saturated |
|---|---|---|---|
| 19.6 | ~7000 | 102.5 Mbps | True |
| 21.6 | ~190 | 19.9 Mbps | False |

M2 measures capacity only while the link is oversubscribed. When the link drops
and the workload's own rate falls with it, the link stops being oversubscribed,
so there is no information left in the counters about capacity -- and the
pre-drop reading is carried to the end of the run as the estimate. Now labelled
STALE with both timestamps.

This is defensible as estimator behaviour; it is **not** defensible to print the
stale number beside the new capacity and say nothing.

### s3 never exercises M2 at all

s3 offers ~14.3 Mbps. Dropped to 20, that is 71% utilisation -- not saturated, so
M2 never reads the link. All six s3 aciq runs report `estimator=None,
policy_changes=0`. The per-flow path *is* exercised; the adaptive path is not.

## 5e. M7 leases — what they do and do not prove (2026-10-08)

The intent API is built and the lease path is unit-tested end to end: a lease
steers its flow to class `1:40`, `build_plan` reserves 39.1 Mbps for it at 100
Mbps capacity, and expiry reverts both. The shield accepts the resulting plan.

**Still not a measurement.** There was no way to run a lease against the
testbed: `--enforce` had no `--lease`. That is now built --

    sudo python3 run_experiments.py --scenario s3_tv_and_gaming --system aciq \
      --enforce --lease 10.0.1.2 --seed 42 \
      --results-dir data/leased --report data/leased/REPORT.md

The first attempt at that command **failed, and the reason was a real bug.**

    $ sudo python3 run_experiments.py --scenario s3_tv_and_gaming --system aciq \
        --enforce --lease 10.0.1.2 --seed 42 --results-dir data/leased ...
    === s3_tv_and_gaming / aciq / adaptive / seed 42 ===
           per-flow enforcement ON (1/41 ticks changed a filter)

No `leases held` line. Reading the artefacts:

    config lease_ips:      ['10.0.1.2']     <- the flag arrived
    lease_active values:   [False, True]     <- the lease was genuinely held
    verdicts seen:         [adaptive, interactive, unclassified]   <- never "leased"

`LeaseStore.for_flow` matched a device lease on `flow.src` only. Traffic runs
internet -> device, so the device's own address is the **destination**: video
flows as `src=203.0.113.2 dst=10.0.1.2`. A lease for 10.0.1.2 -- the client's
own address, the thing a user would naturally name -- matched nothing, while the
run still reported the lease as held.

So src-only matching is wrong for the dominant direction of a home broadband
link. Devices now match on either endpoint. Two tests: a downlink flow matches,
and a flow between two other hosts still does not.

A second, cosmetic bug in the same run: `lease_note` was computed and never added
to `result.json`'s notes, so even the intended diagnostic was invisible. Both are
fixed. **A **third** bug then stopped it working, and this one is about the shield rather
than the lease:

    $ sudo python3 run_experiments.py ... --lease 10.0.1.2 --results-dir data/leased2
           per-flow enforcement ON (2/41 ticks changed a filter)
           leases held for 10.0.1.2 (weight 0.50)
    # artefacts:
    #   verdicts seen: [leased, leased, leased, leased]   <- every flow, every tick
    #   classes with traffic: adaptive_video 0.00, bulk_transfer 24.71, ...
    #   leased_flow: absent

The verdict was right and nothing steered. `apply_system` has just changed policy,
so the shield's 5-second change window refused the lease's rate plan at t=0:

    sync_lease ok : False
    last_reason   : 'rate_limited: 0.00s since last change, minimum 5.0s'

Class `1:40` was therefore never created, every per-flow filter pointed at a class
that did not exist, and the run reported the lease as *held* -- which is true,
and not the same as *installed*.

`sync_lease` now retries while the shield is rate-limiting, and stops rebuilding
once the lease is in effect. "Unchanged but not yet applied" is a third state,
distinct from both "unchanged and applied" and "changed".

Two more bugs surfaced while fixing it: a bare `except Exception` around the
enforcement tick also swallowed `BridgeError`, so a filter the kernel refused
looked identical to a tick that found no flows; and `_lease_in_effect` read
`ok` from the apply, so applying a plan with no leased class -- which succeeds
trivially -- reported a lease in effect after every expiry.

## 5h. The lease, measured (2026-10-09)

Third attempt, and it works. `data/leased3/`:

| class | peak | mean |
|---|---|---|
| ~~leased_flow~~ | ~~24.85 Mbps~~ | ~~12.92 Mbps~~ |

**This row is withdrawn.** It was measured when every workload sent from the one
address the `wan` namespace held, so the lease matched every flow in the run and
the leased class took the whole link. A lease matching all traffic capturing all
traffic is evidence that steering works — which the gate already proves — and not
evidence that a lease protects a device. See "M7 leases cannot be measured in
this testbed as built" below for the topology that made it vacuous.
| adaptive_video | 0.00 | 0.00 |
| bulk_transfer | 0.00 | 0.00 |

Every flow routed to class `1:40` — which is why the other three are zero: the
lease is on the client's address, and in this direction the client is the
*destination* of all four flows.

Cross-checked against the generators' own byte counts, as the first enforced run
was:

    generators sent 71,638,750 B over 40 s = 14.33 Mbps
    leased class carried                    = 13.58 Mbps mean over 39 live ticks

The ~5% gap is tick-boundary sampling: the counter is read once per second, so
traffic in the gaps belongs to no tick, while the generators' figure averages
the whole 40 s. Two independent measurements agreeing to within sampling error is
what makes this evidence rather than an assertion.

So: **routing a leased flow to its class is measured.** What is *not* measured is
the other half of M7's success condition -- that the lease **visibly raises
throughput**. This run had no capacity drop, so the link carried ~14 Mbps of
100 and nothing was contended; a lease cannot raise throughput on a link that was
never the constraint. That needs a `--drop-at` run with and without `--lease`,
compared. Not yet done.

The default TTL is the whole run, so the measurement is of the effect rather than
of the expiry; `--lease-ttl-s` makes a shorter lease if the expiry is what you
want to watch.

Device-scope leases match on IP **and on the destination**, because traffic runs
internet -> device. Matching the source alone -- the original behaviour -- meant
a lease for the client's own address matched nothing at all, while the run
reported the lease as held. See `data/leaseA/README.md` and the "The first
attempt at that command failed" note below.

## 5i. WITHDRAWN: the lease A/B comparison measured our own bug

The A/B in `data/leaseA` vs `data/leaseB` reported a lease holding its flow in a
guaranteed class **93% of ticks against 7% for an un-leased flow**. **Do not use
that number.**

Both arms ran against code that rebuilt the qdisc every five seconds, destroying
the per-flow filters. The bug hit the two arms unequally:

* **B (no lease)** — `sync_lease(None)` never settled, rebuilt every 5 s for the
  whole run, ten commits. B's filters were gone by t=5.19 and never returned, so
  B's 7% was *our bug*, not a property of running un-leased.
* **A (leased)** — the lease landed, `_lease_in_effect` became True, and
  `sync_lease` returned early thereafter. A stopped rebuilding. A kept working
  and B did not.

So the gap measured **a bug in one arm**, not the lease.

What survives: the expiry mechanism is sound (`data/leaseA` shows all four
verdicts flipping back at t=39.66 with `leased_flow` going to zero), and the
throughput question was open then too -- 14.4 Mbps offered on a 20 Mbps link is
72% utilisation, so nothing was contended.

**Both arms need re-running.** And the experiment needs `--drop 10` for the link
to be the constraint at all.

## 5j. The rebuild loop, fixed and verified (2026-10-10)

`data/fixcheck/` — one run, `--enforce --drop 20 --drop-at 20`, seed 42:

| | before | after |
|---|---|---|
| commits in the audit | 10 | **1** |
| filters after t=3 | 1 | **5, every tick** |
| adaptive_video share | 7% | **88%** |
| adaptive_video mean | 1.75 Mbps | **12.40 Mbps** |
| bulk_transfer share | 66% | **7%** |

Generators sent 72,000,000 B over 40 s = 14.40 Mbps; the adaptive class carried
12.40 Mbps mean. Game: 1200/1200 packets, zero loss, p50 0.237 ms.

Per-flow enforcement now survives an entire run. This is the first run where
"classified" and "steered" are the same statement for the whole duration rather
than for the first three seconds.

## 5f. M8 dashboard — read-only by construction, not by discipline

The requirement is that it can **never** write policy. That is enforced
structurally: `aciq/dashboard.py` imports only `html`, `pathlib`, `dataclasses`
and `typing`. It cannot reach a `tc` call because it holds no reference that can.
Two tests assert this -- one walks the module's imports, one greps its source for
`tc`/`nft`/`subprocess`/`set_capacity` -- because an import is the only way a later
edit could turn this into a writer.

Trade-off accepted: no JavaScript and no CDN, so the page is one self-contained
file. Charts update by `<meta>` refresh rather than a websocket. A dashboard that
needs the network stops working on exactly the air-gapped host it would be
demonstrated on.

## 5g. Gate re-verified against current code (2026-10-09, re-run 2026-10-11)

`testbed/logs/gate-20261009-204709.log` and, after the per-workload
addresses and the deferred-lease-retry fix, `docs/evidence/gate-20261011-141836.log`
— **20 PASS, 1 MEASURED, 0 FAIL**, no errors or tracebacks.

One earlier run of this gate failed check 6 with `A=0.0` -- iperf3 produced no
output at all. Check 6 drives raw `tc` and iperf3, not the Harness, and no
leftover processes or namespaces remained, so it was read as transient; the
re-run passed. If it recurs, the gate should surface iperf3's stderr, which it
currently discards.

That log predates the per-workload addresses added for lease matching.
Re-running the gate afterwards failed check 18 and nothing else:

```
PASS  checks 1-17, including check 16 (IPv4 steering)
FAIL  check 18: IPv6 1:20 did not grow (62520 -> 62520)
```

The address change caused it; no product code was involved. `send6()` opened an
unbound socket, so with several IPv6 addresses on `wan` the kernel's
source-address selection could choose one that `bmark`'s exact-match filter did
not cover, and the flow fell through to the default class. The IPv4 checks got
away with it only because `203.0.113.2` stayed primary -- an ordering dependency
rather than a guarantee.

Fixed at both levels: `setup.sh` no longer adds the IPv6 extras (leases here are
IPv4-only, so they bought nothing), and both gate senders now bind an explicit
source so checks 16, 17, 18 and 19 name the address they steer. **Check 18 is
fixed in the source but not yet verified** -- that needs a real gate run.

This mattered: the gate's last run predated three commits that changed
`aciq/closedloop.py` and `aciq/harness.py`, which is the path the gate exists to
test. A green gate on stale code is not evidence about the current code, and the
alternative — assuming it still passed — is how a regression reaches a
demonstration.

The log itself is gitignored (`.gitignore` line 10, `testbed/logs/`), so this
note is the record.

## 5k. `--drop-at` never actually dropped anything (2026-10-10)

Found while analysing `data/leaseB4`. The parent class counter, across the drop at
t=20 on a link requested at 10 Mbps:

    t=19.50  parent rate  4.67 Mbps
    t=23.61  parent rate 14.23 Mbps
    t=25.66  parent rate 24.68 Mbps   <- the "10 Mbps" link

Traffic peaks at 24.9 Mbps *after* the drop, in both arms. And `result.json`
reported `link_end_mbps: 10.0` throughout, because it is the **argument**, not a
measurement.

**Every `--drop-at` run taken so far — `data/matrix6`, `leaseA`, `leaseB`,
`fixcheck`, `leaseA2`, `leaseB4` — ran against a link that never got slower.**
So `--drop-at` has never been tested in a real run, and neither has anything that
depends on a genuine capacity drop.

Cause, in two parts:

1. **`set_capacity` discarded tc's return code.** A refused change looked
   identical to a successful one. It now records success, refuses to record a
   refused value as the configured capacity, and the run carries a
   `CAPACITY CHANGE REFUSED` note plus `capacity_change_applied: false`, which
   the report renders as `10.0 (REFUSED)`.
2. **Not yet fixed: why the change does not constrain.** `set_capacity` changes
   **only** class `1:1`, deliberately, so that rescaling children stays M3's job.
   Gate check 6 shows the two must happen together — it rescales the children's
   ceil explicitly, because a child with ceil 100 under a 10 Mbps parent keeps
   borrowing. M3 only rescales when M2 has measured a new capacity, and M2 has
   never measured in any of these runs. So the parent's rate change alone does not
   bound the link, and nothing in the loop notices.

Part 1 is done, and part 2 turned out to be two bugs rather than a design
question:

**The clamp could not be expressed.** `tc class change ... htb ceil X` is refused
with `"rate" is required`. So a bare ceil clamp never worked, and the first
attempt at it was rejected by the kernel for every child -- which is why
`dropcheck3` reported `capacity_change_applied: False`. Each child now passes its
existing `rate` back unchanged alongside the clamped `ceil`.

**And HTB requires `rate <= ceil`.** Clamping the ceil to 10 under a child whose
rate was 53.57 would leave an invalid class, so the rate is clamped down with
`min()` -- never up, because a raise would hand M3's bandwidth to someone. The
*proportions* remain M3's to decide; this only stops the configuration being
illegal.

### The drop works. Measured.

`dropcheck4`, `--drop 10 --drop-at 20`:

```
capacity_change_applied: True
capacity_change_error  : ''
parent rate: 24.5 Mbps before the drop, 10.0 Mbps from t=24 onward
```

The link was genuinely capped for the first time in this project.

### And M2 still reported nothing -- correctly.

`estimator_saturated` is False on every one of 41 samples, and `capacity_mbps`
never leaves 0.0. The cause is visible in the artefacts rather than inferred:

```
parent overlimits/sec:  1643 at t=1 (demand 24 Mbps on a 100 Mbps link)
                         289 at t=20
                           0 from t=24 onward
```

Neither regime is congestion. At t=1 the link carried 24 Mbps of 100 -- a
quarter loaded, so the parent is correctly not saturated. At t=20 the workload
had decayed to 4.66 Mbps, *below* the new 10 Mbps cap, so the link shaped
cleanly with zero overlimits and zero drops.

**The generators are paced, so a capacity drop creates no congestion signal
unless offered load exceeds the new capacity.** The drop was applied at t=20,
in the quiet phase of the workload ramp, where demand was 4.66 Mbps:

```
t=  4.32   24.62 Mbps     <- demand here would overwhelm a 10 Mbps cap
t= 12.77    9.31 Mbps
t= 20.16    4.66 Mbps     <- where the drop actually landed
```

### That explanation was also wrong. Measured.

`dropcheck5`, `--drop 10 --drop-at 5`, dropped while demand was 24.16 Mbps against
the new 10 Mbps cap -- genuinely oversubscribed, goodput clipped 24 -> 10. M2
still reported nothing, and it was still not broken:

```
   t   parent overlim/s   drop/s   rx Mbps   goodput
 1.02                1647        0     24.82      24.76    demand 24 of 100: not congested
 5.14                1442        0     24.17      24.16
 6.17                  19        0     10.11      10.10    demand 24 of 10: CONGESTED
 7.21                   0        0     10.21      10.21
10.26                   0        0     10.00      10.00
```

**A congested link with zero drops and zero overlimits.** HTB is a shaper: it
holds packets in the queue and delays them rather than overrunning, so with paced
TCP senders there is nothing for the drop/overlimit signal to read. Congestion is
real -- goodput is clipped from 24 to 10 -- but it is invisible to the counters
M2 was built on.

The gate check 12 calibration (24803-65101 overlimits/s on a saturated 20 Mbps
link) came from a source that was not paced, and does not transfer to this
workload.

**Shaper backlog does carry the signal**, and separates the two regimes exactly:

```
   t   parent backlog   children   goodput   demand vs cap
 1.02          0            0       24.76     24 of 100
 6.17          0        18168       10.10     24 of 10     <- queue full
12.30          0        22710       10.04     24 of 10
17.39          0            0        8.13      4.7 of 10   <- demand fell, queue drains
20.47          0            0        4.73      4.7 of 10
24.54          0        16654      10.03     >10 of 10     <- queue full again
```

Non-zero backlog appears when and only when offered load exceeds capacity. The
parent's own backlog stays 0 throughout -- the queue lives in the children -- so
this would have to be read as a sum over children, which is the same pattern that
previously produced a measured capacity death spiral when applied to overlimits.
Backlog differs in that being non-empty means the shaper is actually holding
packets, but that is a claim to be tested, not assumed.

**Status: M2's saturation detector does not work against this workload.** Three
predictions were made and all three were wrong, each time for a different reason
that only the artefacts could have shown. The capacity drop itself works
(`dropcheck4`, `dropcheck5`); estimating capacity from it does not.

Until that is settled, treat every result involving `--drop` as an undropped run.

## 6. There is no per-user or per-device fairness

`8:4:2` allocates bandwidth **per class**. Fairness within a class is delegated
entirely to the `fq_codel` leaf, which is per-*flow* and knows nothing about
users or devices. Consequences: five simultaneous calls share one queue with no
admission control, and a single flow can take the whole class because every
class has `ceil = capacity`.

Per-*user* fairness is not implementable at the IP layer at all — there is no
user identity. It would require an authentication layer this project does not
have.

## 7. Uplink is not shaped

Enforcement is on the router's LAN-facing egress only. Upload saturation is
unmodelled. In a home link, uploads are usually small — but a slow uplink will
harm download latency through bufferbloat on the upstream path, and ACIQ does not
address it.

## 8. Small and very large links behave differently

`floor = max(2 Mbps, 5% of capacity)` reserves 6 Mbps across 3 classes, so
`degraded` fires only **below 6 Mbps** (below 8 Mbps with an active lease). At
that point floors are scaled down proportionally and flagged. Verified by
running the policy engine, not estimated.

## 9. Significance rests on six seeds, and the floor is close

**Superseded 2026-10-08.** This section used to say every result was one seed and
that no significance claim could be made. The matrix in §5d now runs 6 seeds per
configuration and the report computes an exact paired Wilcoxon.

What still constrains it: the smallest attainable two-sided p at n=6 is 2/64 =
**0.0312**. It clears 0.05, but only just, and nothing finer is reachable without
more seeds. A comparison whose true p is 0.04 and one whose true p is 0.001 are
both reported as 0.0312. **Treat p=0.0312 as "at the floor", not as a measurement
of how large the effect is.**

## 10. Out of scope

Wi-Fi airtime and WMM · ISP-side policing · TR-069 / TR-369 · certification ·
scale above 1 Gbps · encrypted DNS · QUIC port hiding · real CPE hardware ·
uplink shaping.

**Removed from this list 2026-10-08**, having been built: *a dashboard* (M8,
`aciq/dashboard.py`), *an intent API* (M7, `aciq/intent.py` + `aciq/api.py`), and
*a working correction loop* (`aciq/corrections.py`, on the enforcement path
since `aciq/closedloop.py`).

## 11. Honest reading of the v0 results

Frozen in `data/baselines/v0/` and tagged `v0-baseline`.

| Scenario | System | p50 | p95 | p99 |
|---|---|---|---|---|
| s1 call | aciq | **0.207** | 0.899 | **19.422** |
| s1 call | b1_cake95 | 0.244 | **0.711** | **1.494** |
| s1 call | b0_fifo | 120.061 | 120.544 | 121.751 |
| s3 game | aciq | 0.393 | **0.546** | **0.785** |
| s3 game | b1_cake95 | **0.277** | 0.710 | 1.425 |
| s3 game | b0_fifo | 0.302 | 33.475 | 33.618 |

**ACIQ wins s1 p50 and eliminates the `pfifo` bufferbloat (120 ms → 0.2 ms). It
loses s1 p95 and p99 to `cake`, and loses s3 p50 to both baselines.** The 19.4 ms
p99 against cake's 1.5 ms is unexplained and is the weakest number here.

One run — `s3_tv_and_gaming__aciq__adaptive__seed42` — has no `result.json`:
its workloads all completed, but the run died before artefact collection. It
contributes no metrics.

## M7 leases cannot be measured in this testbed as built

Both lease comparisons are void, and for the same structural reason rather than
a coincidence.

`ab_lease` leased `10.0.1.2` and `dev_lease` leased `203.0.113.2` -- the two
endpoints available. Both produced the same result:

```
   no-lease  total=304.54 Mb   adaptive_video=190.0  bulk_transfer=113.2  realtime=1.4
  lease      total=303.79 Mb   leased_flow=303.8    adaptive_video=0.0  bulk=0.0  realtime=0.0
```

The verdicts say why. At t=0, with a lease held for `203.0.113.2`:

```
  {"game": {"class": "leased", "confidence": 1.0}, "tv2": {... "leased" ...},
   "tv1": {... "leased" ...}, "tv3": {... "leased" ...}}
```

Every workload is leased. Because **the testbed has exactly one address per
side**: `wan` holds `203.0.113.2/24` and `client` holds `10.0.1.2/24`, and all
four workloads are spawned from `wan`, separated only by `dst_port`. So a lease
for either address matches every flow in the run, and every byte is steered to
class 1:40. The lease class then takes the whole link regardless of its rate,
which is what the 100% share is.

The consequence for what can be claimed: a lease matching all traffic capturing
all traffic is not evidence that leases work. It is evidence that steering works,
which `matrix6` and gate checks 15-19 already establish. M7's actual claim --
that leasing one device raises *its* share at the expense of others -- is not
testable until the testbed has more than one device address.

`docs/WIRING_AUDIT.md` flags this trap at line 256 ("key device/lease rules on
the DESTINATION address"); the wider version of it -- that there is only one
destination and one source to choose from -- is a topology limitation, not a
wiring bug.


## Open defect: a lease makes the link exceed its configured ceiling — FIXED

**Fixed.** Root cause: `set_capacity` clamped each child with
`min(child_rate, capacity)`, putting *every* child at the full link capacity --
a 100 Mbps plan dropped to 10 became four classes each guaranteed 10, so 40 Mbps
was promised on a 10 Mbps link, and the over-subscribed tree stopped the cap
being enforced. Children are now scaled so their rates sum to the new capacity,
preserving M3's proportions. Measured before and after:

```
dev7_lease   parent_max = 18.41 Mbps   (24% over)
dev10_lease  parent_max = 10.14 Mbps   (cap 10)
dev10_nolease parent_max = 10.08 Mbps
```

A test named `test_set_capacity_never_rescales_child_rates` had asserted the
harness must not rescale, on the sound grounds that rates are M3's policy. The
reasoning was right and the conclusion wrong: scaling preserves M3's
proportions, clamping destroys them while appearing to leave policy alone.

### What was ruled out along the way

Two other causes were investigated and disproved, both by measurement:

* a lease rebuild restoring the pre-drop capacity -- the audit showed the lease
  commit applying 100 Mbps, but the settle offset places that commit *before*
  the drop, so it was legitimate. `sync_lease` was correct;
* the metrics reader over-counting -- the parent's byte counter equals the sum
  of its four children to the byte and matches `tc`'s own `Sent`.

Recording the applied rates in every commit (`audit.json`) is what ended the
guessing; without it the rate on parent `1:1` existed only in hand-taken dumps
on a wall clock that did not line up with the run's own timeline.

## M7 measured: a lease raises the leased device's share

First real evidence for M7's claim. `--drop 10 --drop-at 5`, lease on
`203.0.113.4` (= `tv1`) at weight 0.6, seed 42.

Measured by the senders themselves, so independent of the class accounting:

| | tv1 (leased) | tv2 | tv3 |
|---|---|---|---|
| no lease | 17.92 MB | 17.92 MB | 17.92 MB |
| lease 0.6 | **23.04 MB (+28.5%)** | 15.40 MB (-14.1%) | 15.36 MB (-14.3%) |

Totals 53.76 MB against 53.80 MB. The link is the constraint, so the lease
**redistributes rather than adds** -- which is the point. Without a lease the
three TVs are provably symmetric (17.92 MB each), so the counterfactual is
measured rather than assumed. Class-side: `tv1` alone classifies `leased` and
the other three keep their own classes.

### Replicated across three paired seeds

| seed | tv1 no-lease | tv1 leased | change | parent_max (no-lease / leased) |
|---|---|---|---|---|
| 42 | 17.99 MB | 23.05 MB | **+28.14%** | 10.19 / 10.07 |
| 43 | 17.96 MB | 23.00 MB | **+28.08%** | 10.15 / 10.11 |
| 44 | 17.99 MB | 23.05 MB | **+28.16%** | 10.08 / 10.10 |

Three-device total: 53.97 -> 53.93, 53.88 -> 53.74, 53.92 -> 53.89 MB. The link
is saturated in every run and delivery is redistributed, not added. The ceiling
held in all six runs at 10.07-10.19 Mbps against a 10 Mbps cap, which is the
independent confirmation that the over-subscription fix works.

### Seven paired seeds, and a p-value

| seed | tv1 no-lease | tv1 leased | change | parent_max (no-lease / leased) |
|---|---|---|---|---|
| 42 | 17.99 MB | 23.05 MB | +28.14% | 10.19 / 10.07 |
| 43 | 17.96 MB | 23.00 MB | +28.08% | 10.15 / 10.11 |
| 44 | 17.99 MB | 23.05 MB | +28.16% | 10.08 / 10.10 |
| 45 | 17.93 MB | 23.11 MB | +28.92% | 10.08 / 10.11 |
| 46 | 18.00 MB | 23.05 MB | +28.08% | 10.06 / 10.10 |
| 47 | 18.00 MB | 23.06 MB | +28.08% | 10.05 / 10.04 |
| 48 | 18.00 MB | 22.94 MB | +27.46% | 10.08 / 10.07 |

**Exact paired Wilcoxon (two-sided, by sign enumeration): p = 0.015625, n = 7,
statistic 0.** Seven of seven differences in the same direction gives the
minimum reachable p for seven pairs — 2 x (1/2)^7 — so this is the strongest
result the test can return, not a convenient one.

tv1 change: **+27.46% to +28.92%, mean +28.13%**. Three-device total across all
seven: 53.91 -> 53.86 MB, a **-0.10%** change. The link is saturated, so the
lease redistributes and does not add — which is the whole claim.

`parent_max` held at **10.04-10.19 Mbps in all fourteen runs**, which is
independent confirmation that the over-subscription fix works and that the
ceiling is enforced rather than merely requested.

Caveats, stated rather than smoothed over:

* The lease weight (0.6) was chosen in advance, not tuned.
* **M2 is still dead.** The plan comes from the requested drop, not from a
  measurement, so this is the lease mechanism working on a correct plan — not
  adaptation working.
* **M2 is still dead.** The plan comes from the requested drop, not from a
  measurement, so this shows the lease mechanism working on a correct plan --
  not adaptation working.
* the lease weight (0.6) was chosen in advance, not tuned.

## Open defect: a lease makes the link exceed its configured ceiling

Reproducible, bounded, and **not explained**.

```
dev7_nolease   parent_max = 10.32 Mbps   total = 305.27 Mb
dev7_lease     parent_max = 18.41 Mbps   total = 413.99 Mb
```

The link is configured to 10 Mbps. With a lease active it delivers 12.27 Mbps
averaged over the post-drop window -- 23% over. Without a lease the same run
delivers 8.98 Mbps, comfortably under. Same seed, same scenario, same drop.

What has been established:

* the parent is genuinely capped -- live `tc` at peak demand shows
  `class htb 1:1 root rate 10Mbit ceil 10Mbit`, with `tokens` deeply negative,
  i.e. actively throttling;
* the parent's byte counter is read correctly -- it equals the sum of its four
  children to the byte, and matches `tc`'s own `Sent` to within a second's
  traffic;
* it is not a sampling artefact -- the cumulative figure over 33s is 12.27 Mbps,
  not a burst that averages out;
* no filter carries `flowid 1:1`, so nothing is classified into the root and
  bypassing the shaper;
* two candidate causes were investigated and **both disproved**:
  1. a lease rebuild restoring the pre-drop capacity -- the deferred-retry path
     did re-apply the start-of-run plan (a real defect, fixed, `3655bfcf`), but
     `dev7_lease` still reads 18.41 after that fix;
  2. the metrics reader over-counting -- refuted by `tc`'s own byte totals.

`dev7` is the post-fix measurement and is unchanged from `dev3`/`dev5`
(18.42 / 18.35 / 18.41), so the fix did not address this.

**Mechanism not established.** Three further hypotheses were considered and
rejected on evidence rather than pursued: that child rates summing to more than
the parent let HTB over-deliver (children were observed at `rate 10Mbit` each on
a 10 Mbit parent, but the same configuration without a lease stays under the
cap); that `fq_codel` burst delivery distorted a one-second delta (refuted by
the cumulative figure); and that the parent's `rate` is not the binding
constraint on this kernel.

Recorded here rather than chased further: two plausible diagnoses were already
wrong, and a third guess would have been a guess.


## M2 works: shaper backlog as the saturation signal

The one gap, now closed and validated against a recorded run rather than a
constructed one.

M2 looked for drops and overlimits. HTB shapes rather than drops, so against
paced TCP a congested link reported `dropped 0, overlimits 0` and the detector
never fired — in **every** run. That was not a bug in the estimator; it was the
"counters only, no probe" decision, made from gate check 12, which had been
measured on an *unpaced* source.

Child backlog carries the signal. The parent's own backlog reads 0 throughout a
congested run — the queue lives in the children — so it is summed across them:

| window | backlog | delivered | offered vs cap |
|---|---|---|---|
| t=0–4.2 | 0 | 24.9 Mbps | 25 of 100 |
| t=5.2–17.5 | 5.8–22 kB | ~10 Mbps | 25 of 10 |
| t=18.5–22.6 | 0 | 4.7 Mbps | demand fell back below the cap |

Backlog returns to zero when demand falls below the cap, which is the property
that makes it a saturation signal rather than a load signal.

Replaying the recorded run (`data/ab_lease_42`, captured before M2 had this
signal) through the revised estimator:

```
100 -> 45.97 -> 24.38 -> 15.41 -> 12.15 -> 10.86 Mbps
```

against a true capacity of 10. Monotone, never below the link, and no death
spiral — the failure mode this project is guarding against is a separate test
here, replaying the same trace and asserting no intermediate estimate ever falls
under the true capacity.

Why this is defensible where the overlimit threshold was not: it is a semantic
argument, not a fitted threshold. A child queue is non-empty precisely when it
wants more than the link will send, because a child with tokens left to lend
borrows rather than queues. The threshold (1024 bytes) sits far below the
smallest non-zero value ever observed, and is deliberately not tuned — the
overlimit threshold became wrong precisely by being calibrated once on a
workload that did not resemble the real one.

Backlog is still consulted *after* the parent counters, so a reader that cannot
see the parent refuses to declare saturation from backlog alone. Assuming
saturation without parent evidence is what collapsed capacity to 7.2 Mbps once.

**Not yet verified on the live testbed.** The replay uses recorded counters; a
real run with `estimator_mbps` non-null and `policy_changes > 0` is the
remaining check.

## M8 follows a run in progress

`aciqctl serve` read `samples.jsonl` once, at startup, and every browser refresh
re-rendered the same stale view — indistinguishable from a dashboard that is not
live, which is how it behaved, while carrying a meta-refresh the whole time.

Rows are now re-read per request, so the page tracks a run in progress:

```
samples at first request  : 5
samples after run grew   : 12
page changed between requests: True
meta refresh present: True     no <script>: True
```

A run appends to `samples.jsonl` while the dashboard reads it, so the last line
can be caught mid-write; an unparseable line is skipped rather than fatal. The
update stays JavaScript-free by design: `<meta http-equiv="refresh">` only.

`--watch` is implied by `--refresh`; `--refresh 0 --watch` gives a live server
with no automatic page refresh.
