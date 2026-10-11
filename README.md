# ACIQ — Adaptive Classification & Intent-aware QoS

> Prototype for **Case Study 3: Adaptive QoS Engine for Mixed Home Broadband Traffic**
> (TATA ELXSI / TELIPORT).
>
> **Status: substantially complete, and this README says exactly where it
> falls short.** Per-flow enforcement, the capacity drop and the lease mechanism
> are **verified on a real kernel**. Three things are not done: capacity
> *estimation* is verified only by replaying a recorded run, latency/jitter/loss
> are not measured at all, and there is no device-identity layer.
> Read [`docs/PROJECT.md`](docs/PROJECT.md) for the complete reference, and
> [Current state](#current-state) for the honest gap list.

A traffic controller for a home broadband link. It classifies flows without
reading any payload, estimates the real link capacity from queue counters, shares
bandwidth between three traffic classes with guaranteed floors, and is designed
to let a user grant a **time-boxed lease** to one device or flow.

---

## Documents

| | |
|---|---|
| **`docs/gap-closure/final-validation-report.md`** | **gap-closure status: what is verified, what is not, and why** |
| **`docs/PROJECT.md`** | **complete project reference** — every module, contract, measurement, limitation and defect |
| `docs/architecture.md` | module contracts, inputs/outputs/failure handling |
| `docs/limitations.md` | every measurement, withdrawn claim and open defect |
| `docs/ACIQ_EXPLAINED.md` | plain-language walkthrough |
| `docs/WIRING_AUDIT.md` | how each flow reaches its class, and the traps |
| `docs/setup.md` | standing the testbed up from scratch |

## Current state

| | |
|---|---|
| Testbed gate | **20 PASS + 1 MEASURED**, 0 FAIL — re-run 2026-10-09 against current code |
| Unit tests | **595 passing**, none requiring root |
| Modules built | M1 (classifier), M2 (capacity), M3 (policy), M4 (tc enforcement), M5 (metrics), M6 (harness), M7 (intent API), M8 (dashboard), M9 (shield/rollback), M10 (report) |
| Modules **not** built | — |
| Measured runs | [`data/matrix6/`](data/matrix6/) — 54 runs, 6 seeds/config |
| Frozen baseline | [`data/baselines/v0/`](data/baselines/v0/) — verify with `sha256sum -c SHA256SUMS` (77/77) |
| Paired significance | ACIQ vs `b0_fifo` p=0.0312; vs `b1_cake95` **not significant** |

### What the measurements actually say

Read this before quoting a number.

1. **ACIQ beats `b0_fifo` and does not significantly differ from `b1_cake95`.**
   Over 6 paired seeds: p50/p95/p99/loss all reach p = 0.0312 against pfifo;
   against cake nothing does (p50 0.5625, p95 0.0625, p99 0.4375, jitter 0.8438).
   The defensible claim is that ACIQ removes pfifo's bufferbloat and does not
   beat a well-tuned cake.
2. **`p = 0.0312` is the floor at n = 6** (2/64). It clears 0.05 barely, and
   nothing finer is reachable without more seeds.
3. **M2's saturation signal was wrong for this workload and has been
   corrected.** It originally read drops and overlimits, chosen from gate check
   12 — which was measured on an *unpaced* source. HTB shapes paced TCP rather
   than dropping it, so a congested link reported `dropped 0, overlimits 0` and
   M2 reported nothing in every run. Shaper backlog now carries the signal, and
   replaying a recorded run through the revised estimator converges
   100 -> 45.97 -> 24.38 -> 15.41 -> 12.15 -> **10.86 Mbps** against a true
   capacity of 10, monotone and never collapsing. **Not yet verified on the live
   testbed** — that needs a run reporting `estimator_mbps` non-null.
4. **Scenario 3 still does not exercise M2 at 20 Mbps** — ~14.3 Mbps on a
   20 Mbps link is 71% utilisation, not congestion, so the estimator correctly
   reports nothing. The runs that do exercise it are the dropped-capacity ones.
5. **A lease routes the leased device's flows to class `1:40`; that it improves
   that device's outcome is unmeasured, and an earlier positive-sounding number
   is withdrawn.** An earlier version of this file reported "12.92 Mbps mean in
   the leased class". That was measured before workloads had distinct addresses,
   so the lease matched every flow in the run and the leased class took the whole
   link — true about steering, not about leases. **Verified since:** with one
   address per device, a lease for `203.0.113.4` classifies only that device's
   flows as leased and leaves the others in their own classes. **Measured** on a 10 Mbps capped link: the leased device gained
   **+27.46% to
   +28.92% (mean +28.13%)** across **seven paired seeds**, **exact paired
   Wilcoxon p = 0.015625** -- the minimum reachable for seven pairs, with all
   seven differences in the same direction. The three-device total moves by
   -0.10%, confirming the link redistributes rather than adds, and the ceiling
   held at 10.04-10.19 Mbps across all fourteen runs. Measured by the senders,
   not by our own class accounting. The plan came from the requested drop rather
   than from a measurement, so this is the lease mechanism working on a correct
   plan -- not adaptation working. M2 can now measure capacity, but these runs
   predate that.
6. **Classification accuracy is measured on self-generated traffic**, and the
   link is an HTB token-bucket emulation rather than real access hardware.

Full per-module audit with raw evidence: [`docs/WIRING_AUDIT.md`](docs/WIRING_AUDIT.md).
Known limits: [`docs/limitations.md`](docs/limitations.md).

### Trying it

```bash
# per-flow enforcement, 6 seeds, with a capacity drop
sudo python3 run_experiments.py \
  --scenario s1_iso_during_call --scenario s2_wan_drop \
  --scenario s3_tv_and_gaming --enforce --seeds 6 --drop 20 --drop-at 20 \
  --results-dir data/matrix6 --report data/matrix6/REPORT.md

# re-derive the report alone -- no root, no re-running
python3 run_experiments.py --report-only \
  --results-dir data/matrix6 --report data/matrix6/REPORT.md

# M7 intent API + M8 dashboard on :8080
sudo python3 aciqctl serve --port 8080

# or render the dashboard from an existing run, no server
python3 aciqctl dashboard \
  --samples data/matrix6/s1_iso_during_call__aciq__adaptive__seed42/samples.jsonl \
  --out dashboard.html --refresh 5
```

---

## Measured results (v0)

Frozen before further work. Single seed — see
[limitations](docs/limitations.md#9-no-aggregation-over-repeated-runs).

**Scenario 1 — ISO download during a video call** (call latency, ms)

| System | p50 | p95 | p99 | loss |
|---|---|---|---|---|
| **ACIQ** | **0.207** | 0.899 | 19.422 | 0.000 |
| `cake` at 95% | 0.244 | **0.711** | **1.494** | 0.000 |
| `pfifo` | 120.061 | 120.544 | 121.751 | 0.00267 |

**Scenario 3 — three TVs streaming plus gaming** (game latency, ms)

| System | p50 | p95 | p99 |
|---|---|---|---|
| **ACIQ** | 0.393 | **0.546** | **0.785** |
| `cake` at 95% | **0.277** | 0.710 | 1.425 |
| `pfifo` | 0.302 | 33.475 | 33.618 |

**Read honestly.** ACIQ wins s1 p50 and removes the `pfifo` bufferbloat
(120 ms → 0.2 ms). It **loses** s1 p95 and p99 to `cake`, and **loses** s3 p50 to
both baselines. The 19.4 ms p99 against cake's 1.5 ms is unexplained.

The capacity estimator works: **100.49 Mbps measured against a 100 Mbps
shaper**, 0.5% error, from counters alone, with no probe and no access to the
configured rate.

---

## Quick start

```bash
# no root needed
python3 -m unittest discover -s tests       # 260 tests
python3 testbed/workloads/selftest.py      # generator self-checks

# needs root
sudo ./run_experiments.py --scenario s1_iso_during_call --system aciq
```

See [`docs/setup.md`](docs/setup.md) for prerequisites, exact versions, the
14-check gate, and troubleshooting.

---

## How it works

```
   traffic
      │
 ┌────▼────┐  classify: DSCP + behaviour → class, confidence, evidence
 │    M1   │  ⚠ built and tested, NOT connected to enforcement
 └────┬────┘
 ┌────▼────┐  estimate capacity from queue counters ONLY
 │    M2   │  never reads class 1:1's configured rate
 └────┬────┘  ✓ 100.49 Mbps vs a 100 Mbps shaper
 ┌────▼────┐  per-class shares, 8:4:2, with guaranteed floors
 │    M3   │  invariant: Σ rates ≤ capacity
 └────┬────┘  ✓ pure function, unit-tested without root
 ┌────▼────┐  the only module that touches the kernel
 │    M4   │  HTB + fq_codel, ceilings clamped to capacity
 └────┬────┘
 ┌────▼────┐  veto rules, rollback, escalating safe state
 │    M9   │  ✓ fault-injection tested
 └────┬────┘
      ▼
   Linux tc
```

### Design points worth knowing

- **Classification, priority, identity and fairness are different things.** ACIQ
  currently does the first two. It has no identity concept and no intra-class
  fairness — that is a known gap, not an oversight.
- **The estimator cannot cheat.** `Measurement` has no `configured_mbps` field,
  so M2 cannot read the bottleneck's configured rate even by accident. Reading it
  would make adaptation time measure zero.
- **No starvation by construction.** Every class keeps
  `max(2 Mbps, 5% of capacity)`, and `Σ rates ≤ capacity` is an invariant that is
  tested, including across a 100 → 20 Mbps collapse.
- **Safety degrades rather than lying.** If the link is too small to honour every
  floor, floors scale down and `degraded=True` is set.
- **HTB's `default` class cannot be changed on a live qdisc** — measured. Every
  policy change is therefore a full tree rebuild, which M9 can roll back.

### Things that were wrong and got fixed

Recorded because each was a real defect found by running the system:

| Finding | Consequence |
|---|---|
| A child class borrows past its parent's `rate`, up to its own `ceil` | A 20 Mbps parent with `ceil 99/97` delivered **28.5 Mbps**. Ceilings are now clamped to capacity |
| M2 read summed child `overlimits` as congestion | A death spiral collapsed 100 Mbps to **7.2 Mbps**. Saturation is now decided by the parent class's overlimit *rate* |
| `tc class show` without `-s` prints no counters | Every sample read `0.0` while classes parsed fine |
| A leaf qdisc spec passed as one argv token | `tc` searched for a kind named `"cake bandwidth 95mbit"` and reported *"Specified qdisc kind is unknown"* |
| `ping -Q 0x2E` for DSCP EF | EF is `0xB8` (46 shifted left two bits) |

---

## Repository layout

```
aciq/            the system
  capacity.py    M2   capacity estimation from counters only
  policy.py      M3   class shares, floors, lease maths (pure function)
  tc.py          M4   declarative qdisc tree, rendering, read-back verify
  shield.py      M9   veto rules, fault modes, backoff
  txn.py         M9   snapshot, apply, verify, rollback, safe state
  metrics.py     M5   counters → rates, percentiles, fairness, CPU
  qdisc.py            read-back readers, ordered by what was verified
  classify.py    M1   ⚠ tested, NOT wired to enforcement
  flowtrack.py   M1   ⚠ conntrack parsing + per-flow behaviour
  harness.py     M6   closed loop, baselines, capacity variants
  experiment.py  M6   run sequencing, artefacts
  report.py      M10  Markdown report, honest verdicts per percentile
tests/           260 tests, none requiring root
testbed/
  setup.sh       namespaces, veth, IPv4+IPv6, offloads off
  gate.sh        14 checks, stops at first failure
  cleanup.sh
  workloads/     call.py, game.py, video.py, bulk.py, udpx.py
docs/            architecture, wiring audit, setup, limitations, licences
data/baselines/v0/   the frozen measured results, tagged v0-baseline
```

## Documentation

- [`docs/architecture.md`](docs/architecture.md) — design and per-module contracts
- [`docs/WIRING_AUDIT.md`](docs/WIRING_AUDIT.md) — what exists, what is tested, what is actually connected
- [`docs/setup.md`](docs/setup.md) — exact versions, gate, troubleshooting
- [`docs/limitations.md`](docs/limitations.md) — what this does not do
- [`docs/licenses.md`](docs/licenses.md) — dependency inventory

## Licence

MIT — see [`LICENSE`](LICENSE). No third-party source is vendored.