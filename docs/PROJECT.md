# ACIQ — Complete Project Reference

Every module, contract, measurement, limitation and known defect, in one place.

This is the document to read instead of the source when you want to know *what
this project is and what it has actually been shown to do*. Where a claim is
measured it is marked **verified** with the evidence. Where it is not, it is
marked as such rather than being quietly omitted.

- **Repository (public):** <https://github.com/karneish/ACIQ-TATA-ELXSI>
- **Tests:** 682 passing
- **Gate:** 20 PASS / 1 MEASURED / 0 FAIL
- **Source:** 7,458 lines across 22 modules; 7,342 lines of tests
*Numbers below are taken from `docs/evidence/gate-20261011-165455.log`, the latest
gate run, not from an earlier plan document.*
- **Commits:** 90

---

## Table of contents

1. [What it is](#1-what-it-is)
2. [Repository layout](#2-repository-layout)
3. [The ten modules](#3-the-ten-modules)
4. [Data plane design](#4-data-plane-design)
5. [The testbed](#5-the-testbed)
6. [Gate checks](#6-gate-checks)
7. [Measured results](#7-measured-results)
8. [Known limitations and defects](#8-known-limitations-and-defects)
9. [Bugs found and how they were found](#9-bugs-found-and-how-they-were-found)
10. [Running it](#10-running-it)
11. [Documents in this repository](#11-documents-in-this-repository)

---

## 1. What it is

ACIQ is an adaptive QoS controller for a Linux home router. It watches real
traffic, classifies each flow, measures the link, sets per-class bandwidth
guarantees, and steers individual flows to those classes using `tc` flower
filters — with a human being able to lease a device extra bandwidth through an
HTTP API.

The design constraint that shapes everything: **it must never make the link
worse.** Every change passes a shield that can veto it, every applied tree is
verified by reading it back, and a fault returns the router to a safe state
rather than to the last thing it tried.

### The loop

```
conntrack ──► M1 classify ──► corrections ──► M7 lease ──┐
                                                          │
      tc counters ──► M2 estimate capacity ──► M3 plan ──┴──► M4 apply
                                                          │
                                                          ▼
                                            M9 shield veto / rollback
```

### What is genuinely working

| Capability | Status | Evidence |
|---|---|---|
| Per-flow steering (IPv4 + IPv6) | **verified** | gate 14–20 |
| Per-flow teardown, no residue | **verified** | gate 19, 20 |
| Capacity drop enforced | **verified** | `dropcheck4/5`, parent 100→10 Mbit |
| Per-device leases discriminate | **verified** | `dev3`, `dev5` verdicts |
| Lease raises the leased device's share | **verified** | 7 paired seeds, **p = 0.015625** |
| Lease lifecycle (grant → expire → revert) | **verified** | "in effect for 38.0s" |
| Baselines apply cleanly | **verified** | B0 FIFO, B1 CAKE |
| Capacity *estimation* | works, **not yet verified live** | replay of a recorded run |

---

## 2. Repository layout

```
TATA-ELXSI/
├── aciq/                    the controller (22 modules, 7,458 lines)
│   ├── model.py       (131) Traffic classes, Flow, Classification, Capacity
│   ├── flowtrack.py   (187) conntrack parsing
│   ├── classify.py    (364) M1 — the classifier
│   ├── corrections.py (359) human/operator corrections to M1
│   ├── capacity.py    (302) M2 — capacity estimation
│   ├── policy.py      (123) M3 — build_plan, weights, floors
│   ├── qdisc.py       (173) qdisc/tree construction
│   ├── tc.py          (260) render/parse `tc`, class ids
│   ├── txn.py         (343) M9 — transaction manager, audit, rollback
│   ├── shield.py      (215) veto rules, rate limiting, fault state
│   ├── bridge.py    (1,013) M4 — flower filters, marks, teardown
│   ├── closedloop.py  (228) classifier → bridge verdict
│   ├── harness.py     (647) M6 — the loop, capacity changes, leases
│   ├── metrics.py     (447) M5 — the counter collector
│   ├── experiment.py   (869) the driver: scenarios, runs, artefacts
│   ├── intent.py      (354) M7 — lease lifecycle, persistence
│   ├── api.py         (189) M7 — stdlib HTTP intent API
│   ├── dashboard.py   (523) M8 — read-only inline-SVG dashboard
│   ├── marks.py       (277) conntrack marks and the `seen` bit
│   └── report.py      (431) M10 — aggregation, exact Wilcoxon
├── tests/                     682 tests, 7,342 lines
├── testbed/
│   ├── gate.sh                21 checks
│   ├── setup.sh               namespaces, addresses, conntrack accounting
│   ├── cleanup.sh
│   ├── bridge_probe.sh        how flower filters were chosen
│   ├── bridge_isolate.sh
│   └── workloads/             call.py game.py video.py bulk.py udpx.py
├── tools/export_aciq.py       standalone public-history exporter
├── docs/                      see §11
├── data/                      run artefacts (committed)
└── aciqctl                    CLI
```

### The testbed

Four network namespaces: `client` (10.0.1.2) — `router` (10.0.1.1 / 203.0.113.1)
— `wan` (203.0.113.2), plus `fd00:1::` and `fd00:2::` for IPv6. The `wan`
namespace also carries **203.0.113.3–10**, one per simulated device — added so a
lease can match one device instead of all of them. See §9 for why that mattered.

---

## 3. The ten modules

### M1 — Classifier (`classify.py`)

Decides which class a flow belongs to. Tiers are the trust level:

| Tier | Meaning | Confidence |
|---|---|---|
| A | Strong evidence: a DSCP-EF claim that survived checking, or a well-known signalling port | high |
| B | Behavioural: rate-relative, port tables | 0.60–0.75 |
| C | Weak: insufficient packets, too young, undecided | ≤0.45 |
| X | A correction overrode everything | 1.0 |

Constants, all measured or argued:

```
DSCP_EF                       46
INTERACTIVE_PORTS             {5349, 5060, 5061, 3478}
BULK_PORTS                    {873, 3389}
MIN_CONFIDENCE                0.5
MIN_AGE_S                     2.0
MIN_PACKETS                   10
BULK_MIN_CAPACITY_FRAC        0.5
ADAPTIVE_MIN_MBPS             0.5
EF_FAST_CONFLICT_CAPACITY_FRAC 0.5
TRUST_DECAY_FACTOR            0.5
MIN_EF_TRUST                  0.25
```

**The EF rule is the interesting one.** A flow claiming DSCP EF is *not*
believed. It is weighed against observed behaviour: a flow that marks itself
interactive but is slow, or is moving a lot of bytes, loses its EF trust
(`TRUST_DECAY_FACTOR` per contradictory observation, floored at `MIN_EF_TRUST`).
Gate check 17 exists specifically to prove a rejected EF flow does not reach
class `1:10`.

Rate-relative behaviour is tested **before** port tables, so a video stream on
port 443 classifies as video rather than as whatever port 443 usually means.

### M2 — Capacity estimator (`capacity.py`)

Estimates link capacity from **passive counters only**. It cannot read the
bottleneck's configured rate — `Measurement` has no such field, deliberately, so
adaptation time cannot be faked by reading an oracle.

Saturation is decided by: parent-class drops > 0, **or** parent overlimit rate
≥ `SAT_OVERLIMIT_MIN`, **or** child shaper backlog ≥ `BACKLOG_MIN_BYTES`.

```
ALPHA_DOWN             0.6     capacity falling is urgent
ALPHA_UP               0.1     capacity rising is taken on trust slowly
HYSTERESIS             0.1     ignore changes smaller than 10%
MIN_DWELL_S            5.0     no two changes closer than this
SAT_STREAK_REQUIRED    2       one burst is not a reading
SAT_OVERLIMIT_MIN      3000    overlimits/sec
BACKLOG_MIN_BYTES      1024    "the queue is not empty", deliberately not tuned
IDLE_DECAY             0.15    confidence decays when idle rather than holding
```

**Backlog was added as a reversal, not an extension.** The original design read
drops and overlimits only, decided from gate check 12 — which had been measured
on an *unpaced* source. HTB shapes paced TCP rather than dropping it, so a
genuinely congested link reported `dropped 0, overlimits 0` and M2 reported
nothing in every run. See §8.

Two safety properties, both tested:
- an unsaturated sample **never** moves the estimate, only decays confidence;
- backlog alone cannot declare saturation if the parent counters are unreadable —
  assuming saturation without parent evidence is what collapsed capacity to
  7.2 Mbps once.

### M3 — Policy (`policy.py`)

`build_plan(capacity, lease)` → guaranteed rates. Invariants:

1. `sum(rates) ≤ capacity`, **always**;
2. no class below its floor — floors scale down proportionally on a small link
   and the plan is marked `degraded`;
3. only shrinking is the harness's job; growth is M3's, once M2 measures it.

Base weights: `interactive 8.0`, `adaptive 4.0`, `bulk 2.0`. A lease overrides
its target's weight.

### M4 — Enforcement (`bridge.py`)

The only module that writes `tc`. Installs one flower filter per flow.

**Filter priority — the ordering is the design:**

```
10-19   bridge, mark-driven, one priority per class per protocol
20-29   reserved
30-31   DSCP-EF fallback (v4 at 30, v6 at 31)
```

`tc` evaluates ascending, so the bridge is consulted before the EF fallback. Two
deliberate consequences: a flow the bridge placed in `unclassified` does **not**
fall through to EF priority (that is what the `seen` bit in `marks.py` is for),
and a flow the bridge never looked at **does** fall through, so behaviour before
the bridge existed is unchanged when it is off.

**Limitation, stated not hidden:** the key uses `th dport`, which exists only for
TCP and UDP. ICMP, SCTP, GRE and IPv6 extension headers cannot be expressed in
this key shape and take the EF path or the default class.

### M5 — Metrics (`metrics.py`)

Reads per-class counters via `tc -s` text and `tc -s -j` (JSON fallback, verified
by gate check 8). Collects bytes, drops, overlimits, backlog, goodput, and — for
the classes that report it — RTT percentiles, jitter and loss.

Note on the parent: class `1:1` is stored with `cls=None` and `handle="1:1"`.
It used to be labelled `realtime_interactive`, which put the wrong class name on
every sample of every system.

### M6 — Harness (`harness.py`)

Owns the loop and every kernel-facing decision:

- applies a system (ACIQ tree, or a baseline tree);
- changes capacity, scaling children so their rates sum to the new capacity;
- syncs leases, rebuilding the plan against the link's **current** capacity;
- invalidates the bridge's filter bookkeeping after any rebuild, because a rebuild
  destroys every flower filter while the bridge's state still says they exist.

The capacity-change path records the rates it applied, and records them **only
when `tc` accepted the change** — a refused change is not the link's capacity.

### M7 — Intent (`intent.py`, `api.py`)

Lease lifecycle with persistence and auto-expiry.

- stdlib `http.server`, **not** FastAPI — a deliberate deviation from the plan,
  to avoid a dependency on a host that may be air-gapped;
- endpoints: `POST /intent`, `GET /intent`, `DELETE /intent/<id>`, `GET /status`;
- `RLock` around the book; atomic JSON writes; finite TTL; most-recent lease per
  scope replaces the earlier one;
- a lease matches a device on **either** `flow.src` or `flow.dst` — source-only
  matching was a bug that made downlink traffic unmatched.

### M8 — Dashboard (`dashboard.py`)

Read-only, inline SVG, **no JavaScript, no CDN**. Six panels: latency, jitter,
loss, throughput, queue depth, fairness. Plus summary tiles, a legend carrying
current values, and the capacity drop marked on every chart.

The no-JS constraint is why it works on an air-gapped host. The cost: charts
update by page reload (`<meta http-equiv="refresh">`), not by a websocket. The
server re-reads `samples.jsonl` per request, so it can be started **before** a
run exists and will pick the file up when the run creates it.

Three of the six panels — latency, jitter, loss — are **not measured** by the
project's generators and say so. See §8.

### M9 — Shield and transaction manager (`shield.py`, `txn.py`)

Pre-apply vetoes:
- `child_sum_exceeds_capacity` — `sum(rates) > capacity`
- `below_floor` — any class under its (possibly scaled) floor
- `rate_limited` — a change within `MIN_CHANGE_WINDOW_S` (5 s) of the last
- `drop_rate_limit` / `overlimit_rate_limit` — above 5000/s

Post-apply: the tree is rendered, applied, then **read back and compared**. A
mismatch is a rollback, not a warning.

Fault handling: breaches put the shield into `FAULT_PENDING` → `SAFE_HELD`, and
`force_safe()` returns the router to an unleased plan rather than to the last
attempted state.

Every commit is recorded in `audit.json` with the class count **and the rates
actually applied**. That field was added late and is the reason the last two
bugs were findable at all. See §9.

### M10 — Report (`report.py`)

Aggregates runs, reports `mean (min–max)` and n, and does **exact** paired
Wilcoxon by enumerating sign flips.

`MIN_PAIRS_FOR_PVALUE = 6`. With fewer than six pairs the report says so instead
of printing a p-value — a p-value that cannot be interpreted is worse than none.

---

## 4. Data plane design

### Class map

| Class | Handle | Base weight | Colour |
|---|---|---|---|
| parent (the link) | `1:1` | — | — |
| interactive | `1:10` | 8.0 | `#c0392b` |
| adaptive video | `1:20` | 4.0 | `#2e86c1` |
| bulk | `1:30` | 2.0 | `#7f8c8d` |
| leased | `1:40` | lease weight | `#8e44ad` |

Qdisc: `htb` on `veth-lan`, `fq_codel` on each leaf.

### Scenarios

| Name | Duration | Settle | Workloads |
|---|---|---|---|
| `s1_iso_during_call` | 30 s | 4 s | call (DSCP 46), bulk |
| `s2_wan_drop` | 40 s | 4 s | call (DSCP 46), bulk |
| `s3_tv_and_gaming` | 40 s | 4 s | game (DSCP 46), tv1, tv2, tv3 |

### Systems

`b0_fifo` (baseline), `b1_cake95` (CAKE at 95% of capacity), `aciq`.

### Modes

`static`, `informed` (told the capacity), `adaptive` (must measure it).

---

## 5. The testbed

- Four namespaces: `client`, `router`, `wan`, plus IPv6 on both links.
- `nf_conntrack_acct=1` installed by an nft rule, so conntrack accounting is on.
- Offloads (`gro`, `gso`, `tso`) disabled on all four ends — required, or counters
  are attributed to the wrong interface.
- One source address per simulated device: `game` = 203.0.113.3, `tv1` = .4,
  `tv2` = .5, `tv3` = .6.
- Generators: `call.py` (UDP probe, RTT/jitter/loss), `game.py` (UDP, 30 pps),
  `video.py` (TCP with a bitrate ladder 8/5/3/1.5 Mbps, stepped every 6 s),
  `bulk.py` (TCP), `udpx.py` (shared UDP probe).

Per-run artefacts in `data/<run>/<scenario>__<system>__<mode>__<seed>/`:

| File | Contents |
|---|---|
| `config.json` | scenario, system, mode, seed, capacities, device→IP map |
| `result.json` | outcome, notes, `estimator_mbps`, `policy_changes`, `capacity_change_applied` |
| `samples.jsonl` | one line per tick: per-class counters, link counters, verdicts |
| `audit.json` | every commit, with the rates applied |
| `workloads.json` | each generator's own byte/packet counts |
| `*.log`, `*.sink.log` | generator stdout |

---

## 6. Gate checks

Latest: **20 PASS, 1 MEASURED, 0 FAIL** —
`docs/evidence/gate-20261011-165455.log`.

| # | Check | What it proves |
|---|---|---|
| 1 | tooling | binaries present |
| 2 | modules | every kernel module loads |
| 3 | conntrack loopback per-flow | two distinct entries (4056488 vs 899688 bytes) |
| 4 | namespaces and routes | including IPv6 |
| 5 | offloads off | gro/gso/tso on all four ends |
| 6 | HTB bottleneck 1:1 | 92.7 → 19.1 Mbps, `sum(child rate)=16 ≤ 20` HOLDS |
| 7 | netem on leaf | +20.072 ms |
| 8 | pyroute2 netlink | per-class bytes/drops/overlimits/backlog |
| 9 | cake at root | 90.8 Mbps |
| 10a | cake as leaf | 18.0 Mbps |
| 10b | pfifo as leaf | 19.1 Mbps |
| 11 | conntrack forwarded per-flow v4 | two distinct entries (1111956 vs 5013556 bytes) |
| 12 | saturation signals | MEASURED — see below |
| 13 | conntrack forwarded per-flow v6 | two distinct entries (4742200 vs 1122200 bytes) |
| 14 | IPv6 EF filter routes | class `1:10` byte count grows |
| 15 | per-flow flower filters install | |
| 16 | steered IPv4 flow routed | `bmark … adaptive` → 1:20 grows |
| 17 | rejected EF flow does not reach 1:10 | the classifier's scepticism |
| 18 | steered IPv6 flow routed | |
| 19 | removing the filter returns the flow | |
| 20 | teardown removes bridge filters | no residue |

**Check 12 is the one that has to be read, not passed.** Measured on a saturated
20 Mbit link:

| Signal | Result | Verdict |
|---|---|---|
| overlimits per class | 24803 → 65101 over 25 s | primary, at the time |
| dropped | 0 → 252 | corroborating |
| unmarked probe | 0.051 → 0.405 ms (~8×) | validated fallback |
| EF probe | 0.051 → 0.070 ms | **rejected** |
| backlog | 0 throughout | rejected **then** — see §8 |

The EF probe was correctly rejected: a probe in the *protected* class reports how
well the class is protected, not whether the link is saturated. The backlog
verdict was wrong, and wrong for a specific reason — see §8.

---

## 7. Measured results

### Baselines vs ACIQ (`data/matrix6`, 6 seeds)

Against `b0_fifo`: p = 0.0312 on p50/p95/p99 and loss.
Against `b1_cake95`: no significant difference.

12 of 18 ACIQ runs carry a stale capacity estimate; each `result.json` says so.

### M7 — leases (7 paired seeds, `--drop 10 --drop-at 5`, lease on `203.0.113.4` = tv1, weight 0.6)

| seed | tv1 no-lease | tv1 leased | change |
|---|---|---|---|
| 42 | 17.99 MB | 23.05 MB | +28.14% |
| 43 | 17.96 MB | 23.00 MB | +28.08% |
| 44 | 17.99 MB | 23.05 MB | +28.16% |
| 45 | 17.93 MB | 23.11 MB | +28.92% |
| 46 | 18.00 MB | 23.05 MB | +28.08% |
| 47 | 18.00 MB | 23.06 MB | +28.08% |
| 48 | 18.00 MB | 22.94 MB | +27.46% |

**Exact paired Wilcoxon (two-sided, by sign enumeration): p = 0.015625, n = 7,
statistic 0.** Seven of seven differences in the same direction gives
2 × (1/2)⁷ — the minimum reachable for seven pairs.

Three-device total: 53.97 → 53.93, 53.88 → 53.74, 53.92 → 53.89 MB. **The link is
saturated, so the lease redistributes rather than adds** — which is the claim.
Without a lease the three TVs are provably symmetric (17.92–18.00 MB each), so the
counterfactual is measured rather than assumed.

Caveats, recorded rather than smoothed over:
- the lease weight (0.6) was chosen in advance, not tuned;
- **M2 was dead during these runs**, so the plan came from the requested drop
  rather than from a measurement. This is the lease mechanism working on a
  correct plan — not adaptation working.

### Capacity drop

```
dropcheck4   capacity_change_applied: True    parent 24.5 → 10.0 Mbit
dropcheck5   capacity_change_applied: True    parent 24.5 → 10.0 Mbit
dev10        parent_max = 10.08 / 10.14        cap 10, both arms
```

Ceiling held at **10.04–10.19 Mbps across all fourteen runs** after the
over-subscription fix.

### M2 — capacity estimation (offline replay of a recorded run)

`data/ab_lease_42`, captured before M2 had a backlog signal:

```
100 → 45.97 → 24.38 → 15.41 → 12.15 → 10.86 Mbps     (true capacity 10)
```

Monotone, never below the link, no death spiral. **Not yet verified live.**

---

## 8. Known limitations and defects

### Open: three of six dashboard panels have no data

Across **every** run in this project, these are identically zero in every sample
of every class:

| field | distinct values | non-zero |
|---|---|---|
| `rtt_p95` | 1 | **0** |
| `jitter_ms` | 1 | **0** |
| `loss_ratio` | 1 | **0** |
| `goodput_mbps` | 119 | 118 |
| `backlog_bytes` | many | many |

The generators do not report per-flow RTT to the collector. The panels now say
"not measured" rather than drawing a flat zero line on an axis that used to span
negative latency. **Fixing this properly means changing `testbed/workloads/` and
what M5 collects.**

### Open: M2 verified only offline

The replay is convincing and uses real recorded counters, but the live path has
never been watched. The outstanding check is a run reporting
`estimator_mbps` non-null and `policy_changes > 0`.

Two untested paths exist there: an estimator-triggered rebuild (only lease
rebuilds have ever exercised `_invalidate_enforcer_filters`), and M3 replanning
around a measured 10.86 rather than an exact 10.

### Open: no device or MAC layer

Leases address an IP. There is no identity, no MAC binding, no way to say "this
lease belongs to that physical device".

### Open: bridge covers TCP and UDP only

`th dport` exists for neither ICMP, SCTP, GRE, nor IPv6 extension headers. Those
take the EF path or the default class. Stated rather than assumed classified.

### Open: latency/jitter/loss unmeasured (see above)

### Withdrawn claims

**"12.92 Mbps mean in the leased class."** Real, and meaningless. Measured before
workloads had distinct addresses, so the lease matched every flow in the run and
the leased class took the whole link. Evidence that steering works — which gate
checks 15–20 already prove — not that a lease protects a device. Withdrawn in
README, architecture.md and limitations.md, each naming the withdrawal rather
than deleting the number.

### Withdrawn: `--drop-at` as a capacity-drop experiment

`matrix6`, `leaseA`, `leaseB`, `fixcheck`, `leaseA2`, `leaseB4` all ran before
the child-ceil fix and the child-scale fix, so their "link end" numbers were the
requested argument, not a measurement. Same-link latency comparisons from those
runs remain valid with that caveat.

---

## 9. Bugs found and how they were found

Recorded because the method mattered more than the fixes.

**`set_capacity` clamped instead of scaled.** Every child got
`min(rate, capacity)` = the *whole link*, so a 100 Mbps plan dropped to 10 became
four classes each guaranteed 10 — 40 Mbps promised on a 10 Mbps link. That
over-subscribed tree stopped the cap being enforced: 12.27 Mbps measured through
a 10 Mbit parent, 23% over. Gate check 6 has always rescaled
(`rate 8mbit ceil 20mbit`, sum 16 ≤ 20); this path did not.

It was defended by a test named `test_set_capacity_never_rescales_child_rates`,
arguing that "rates are policy and belong to M3". The reasoning was sound and the
conclusion wrong: scaling *preserves* M3's proportions, clamping destroys them
while appearing to leave policy alone.

**The audit recorded how many classes, not which rates.** For several runs the
only record that a plan applied `1:1 rate 100Mbit` was a hand-taken `tc` dump on
a wall clock that did not line up with the run's own timeline. Two wrong
diagnoses survived because the evidence needed to check them did not exist.
`audit.json` now records the applied tree on every commit.

**A deferred lease retry re-applied the start-of-run plan.** A lease requested at
t=0 is deferred by the shield's change window and retried every tick; the retry
took the "unchanged" path and applied a 100 Mbps plan onto a link capped to 10.
A real bug — and *not* the cause of the overshoot above, which I initially
claimed it was.

**Per-device leases were inexpressible.** The testbed had one address per side,
so a lease for either matched every flow. Fixed in the testbed (one source
address per workload, `--src` on all generators, `device_ips` in `config.json`).

**The gate broke, and it was my fault.** Adding IPv6 addresses to `wan` made the
kernel's source-address selection ambiguous; `send6()` opened an unbound socket
so the check's exact-match filter missed the flow. Check 18 failed. Fixed by not
adding IPv6 extras (leases here are IPv4-only) *and* by making both gate senders
bind an explicit source — the IPv4 checks had been passing only because
`203.0.113.2` happened to stay primary.

**A run reported a lease "NOT INSTALLED" while it was steering for forty
seconds.** The note read the state at teardown, where leases have always expired.
It now reports seconds-in-effect.

**A refused `tc` change was reported as applied.** The harness captured the error
and the run computed a "REFUSED" note and then never added it to the notes list.
`capacity_change_error` is now a field, because a field cannot be overlooked the
way prose can.

---

## 10. Running it

```bash
cd ~/Desktop/Full-projects/TATA-ELXSI

# tests
python3 -m unittest discover -s tests -t .          # 682 tests

# gate (needs sudo)
sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/gate.sh

# a run
sudo python3 run_experiments.py --scenario s3_tv_and_gaming --system aciq \
  --enforce --drop 10 --drop-at 5 --seed 42 \
  --lease 203.0.113.4 --lease-weight 0.6 --results-dir data/myrun

# dashboard, following a run in progress
./aciqctl serve --samples 'data/myrun/*/samples.jsonl' --port 8080 --watch

# a self-contained file to send to someone
./aciqctl dashboard --samples data/ab_lease_42/*/samples.jsonl --out /tmp/aciq.html

# leases
./aciqctl lease --ip 203.0.113.4 --weight 0.6
./aciqctl leases
```

Useful flags: `--enforce` (opt-in per-flow enforcement), `--drop`/`--drop-at`,
`--seeds`, `--report-only`, `--lease`/`--lease-weight`/`--lease-ttl-s`.

`--lease` requires `--enforce`, since a baseline has no classifier to honour one.

---

## 11. Documents in this repository

| File | Contents |
|---|---|
| `docs/PROJECT.md` | this document |
| `docs/architecture.md` | module contracts, inputs/outputs/failure handling |
| `docs/limitations.md` | every measurement, every withdrawn claim, every open defect |
| `docs/ACIQ_EXPLAINED.md` | plain-language walkthrough |
| `docs/WIRING_AUDIT.md` | how each flow reaches its class, and the traps |
| `docs/setup.md` | how to stand the testbed up from scratch |
| `docs/licenses.md` | third-party licences and their obligations |
| `docs/evidence/` | committed gate logs |
| `PLAN.md` | the build plan and its history, including reversals |
| `README.md` | front page and current claims |

---

## The short version

The per-flow enforcement, the capacity drop, and the lease mechanism are
**verified on a real kernel** — gate 20/21, a parent that drops to exactly what it
was told, and a lease that gives a device +28% at the expense of two others with
p = 0.0156 across seven paired seeds while the link stays capped.

Capacity *estimation* works on recorded data and has never been watched live.
Latency, jitter and loss are not measured at all. There is no device layer.

Those three are the honest gaps. Everything the project claims, it can show the
evidence for.