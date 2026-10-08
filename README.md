# ACIQ — Adaptive Classification & Intent-aware QoS

> Prototype for **Case Study 3: Adaptive QoS Engine for Mixed Home Broadband Traffic**
> (TATA ELXSI / TELIPORT).
>
> **Status: incomplete, and this README says so.** Three of the brief's required
> outputs do not exist yet, and the behavioural classifier is tested but **not
> connected to enforcement**. Read [Current state](#current-state) before
> anything else.

A traffic controller for a home broadband link. It classifies flows without
reading any payload, estimates the real link capacity from queue counters, shares
bandwidth between three traffic classes with guaranteed floors, and is designed
to let a user grant a **time-boxed lease** to one device or flow.

---

## Current state

| | |
|---|---|
| Testbed gate | **14 / 14 checks passing** |
| Unit tests | **260 passing**, none requiring root |
| Modules built | M2 (capacity), M3 (policy), M4 (tc enforcement), M5 (metrics), M6 (harness), M9 (shield/rollback), M10 (report) |
| Modules **not** built | M1 classifier (unwired), M7 intent API, M8 dashboard, correction loop |
| Experiment runs | 6 (frozen as [`v0-baseline`](data/baselines/v0/)) |
| Seeds per configuration | **1** — no significance claim is made |

### Three things that do not work yet

1. **The classifier never reaches enforcement.** `aciq/classify.py` and
   `aciq/flowtrack.py` are fully unit-tested, but neither appears in the runtime
   import chain from `run_experiments.py`. Enforcement today is
   **DSCP-EF filtering + HTB + `fq_codel`**.
2. **`ADAPTIVE` receives no traffic.** Nothing routes to class `1:20`; all non-EF
   traffic falls to the HTB default class `1:30` (BULK). In scenario 3 the three
   video streams were classified **BULK**.
3. **The lease is not enforced.** Class `1:40` is created and given bandwidth,
   but no filter routes traffic to it, and no intent API exists to request one.

Full per-module audit with raw evidence: [`docs/WIRING_AUDIT.md`](docs/WIRING_AUDIT.md).

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