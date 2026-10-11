# ACIQ+ — Architecture and Module Contracts

> **Status:** phase 0b. The **M1 and M2 contracts are DRAFT** — they depend on
> gate results that have not been produced and must not be submitted as final
> text.
>
> **DEADLINE: unset** — supply TELIPORT round dates.

## System diagram

```
┌─ device ─────────────────┐   ┌─ edge (the router) ──────────────────────┐
│  client netns            │   │  router netns                            │
│                          │   │                                         │
│  call.py   ──┐           │   │   ┌──────────────┐                       │
│  game.py   ──┼── UDP ──┐  │   │   │ M1 classifier│──► class + confidence  │
│  video.py  ──┼── TCP ──┼──┼───┼──►│  (no payload)│                       │
│  bulk.py   ──┘         │  │   │   └──────┬───────┘                       │
│                       │  │   │          │ counters only                 │
│  M7 intent API ◄───────┼──┼───┤   ┌──────▼───────┐                       │
│  (device | flow)       │  │   │   │ M2 estimator│──► capacity estimate    │
│                       │  │   │   │  tc -s only │    (never reads 1:1's  │
│  M8 dashboard ◄───────┼──┼───┤   └──────┬───────┘     configured rate)   │
│    READ-ONLY          │  │   │          │                               │
└───────────────────────┼──┘   │   ┌──────▼───────┐                       │
                        │      │   │ M3 policy   │──► RatePlan            │
┌─ network ─────────────▼──┐   │   │  pure fn    │    floors + lease      │
│  wan netns                │   │   └──────┬───────┘                       │
│  "internet"               │   │   ┌──────▼───────┐                       │
│  netem delay/loss only ───┼───┼───┤ M4 enforce  │ THE ONLY KERNEL WRITER │
│                           │   │   └──────┬───────┘                       │
└───────────────────────────┘   │   ┌──────▼───────┐                       │
                                │   │ M9 txn+shield│ snapshot→apply→verify │
        data plane              │   └──────┬───────┘  veto→rollback→safe  │
        ◄── run artefacts ─────┼──────────┤                                │
        ◄── audit log ─────────┼──────────┘                                │
                                │   ┌──────────────────────────────────┐    │
                                └──►│ M5 metrics ── M6 harness ── M10 │    │
                                    │        (STRICTLY separate from M2)│  │
                                    └──────────────────────────────────┘    │
```

| Layer | Component |
|-------|-----------|
| device | `client` netns + generators |
| edge | `router` netns: M1–M5, M7, M9 |
| network | `wan` netns, `netem` delay/loss only |
| data | run artefacts under `data/runs/<run_id>/`, audit log |
| analytics | M5, M6, M10 |
| UI | M7 API, M8 dashboard |

**The single most important structural fact:** M5 is the only thing that touches
latency, jitter and loss, and it hands them to the *evaluation*, never to M2.
M2's input type is `ClassCounters`, which has no latency field. Combining them
would have to be a deliberate change.

---

## Contracts

Each contract states **inputs / outputs / failure handling / success condition**.
"Success" means the condition we will actually measure.

### M1 — Classifier · **FINAL — checks 3/11/13 passed**

| | |
|---|---|
| **Inputs** | Stage A: `tc` filter matches on port, DSCP, protocol. Stage B: per-flow byte counters from conntrack (fallback: nftables counters; last resort: rules only) |
| **Outputs** | `Classification(flow, cls, confidence, tier, evidence)`; corrections appended to `data/corrections.jsonl` |
| **Failure handling** | Below 0.5 confidence → `unclassified`, **never guessed**. If conntrack unavailable, degrade to nftables counters and **say so in the report**. If both fail, rules-only and say so again. Never crash the collector |
| **Success** | Accuracy against self-generated ground truth, reported as a measured number. Correction loop demonstrably changes subsequent decisions |
| **Resolved** | **conntrack gives per-flow bytes**, loopback and forwarded, IPv4 and IPv6 (`4351524` vs `965124`; v6 `4801936` vs `1136336`). No nftables fallback needed |
| **Known limit** | UDP/443 call-vs-download separability from counters alone — unresolved and reported as a measured residual |

### M2 — Capacity estimator · **FINAL — check 12 measured; counters only, no probe**

| | |
|---|---|
| **Inputs** | `ClassCounters` from `tc -s` (pyroute2, `tc -s -j` fallback). **Evaluation latency is structurally excluded** |
| **Outputs** | `Capacity(mbps, confidence, saturated, changed)` |
| **Failure handling** | If counters don't move under load, fall back to rate-change detection against the previous estimate and **raise it as a measured limitation** rather than papering over it |
| **Success** | Estimate error against the known HTB rate; adaptation time after the 100→20 drop; policy-change count (stability) |
| **Resolved** | **Saturation IS visible in counters.** `overlimits` 24803→65101 over 25 s, `dropped` 0→252. **No probe in the MVP.** An EF probe in the protected class showed no signal (0.051→0.070 ms) because it reports protection, not saturation; an unmarked probe in the bulk class showed ~8x (0.051→0.405 ms) and is the validated fallback. `backlog` was 0 throughout and is a diagnostic only |

### M3 — Policy engine · ✅ **BUILT, 20 TESTS PASSING**

| | |
|---|---|
| **Inputs** | `capacity_mbps`, optional `Lease` |
| **Outputs** | `RatePlan` with per-class guaranteed rates, `lease_id`, `degraded` |
| **Failure handling** | Capacity too small to honour every floor → floors scaled down proportionally and `degraded=True`. Never silently violates the invariant |
| **Success** | `sum(rates) <= capacity` on every call, proven across a capacity sweep and through 100→20. Every class ≥ its floor. Absurd lease weights clamped |

### M4 — Enforcement

| | |
|---|---|
| **Inputs** | `RatePlan` |
| **Outputs** | `tc` state: rates → filters → leaf qdiscs → read-back verification |
| **Failure handling** | Any mismatch triggers M9 rollback. Sole kernel writer — no other module calls `tc` |
| **Success** | Post-readback `tc -s` matches the plan within tolerance |

### M5 — Metrics collector · ✅ **BUILT, 26 TESTS PASSING**

| | |
|---|---|
| **Inputs** | `CounterSource` snapshots (kernel counters) + `EvaluationData` (generator latency) |
| **Outputs** | `MetricsFrame`: per-class goodput, drop rate, overlimit rate, backlog, rtt p50/p95/p99, jitter, loss, Jain fairness, CPU fraction |
| **Failure handling** | Malformed `tc -s -j` returns empty rather than raising — a collector that crashes loses the whole run. Counter resets read as 0, not negative throughput |
| **Success** | Rates derived correctly from counter deltas; `EvaluationData` cannot be passed where `ClassCounters` is expected |

### M6 — Experiment harness

| | |
|---|---|
| **Inputs** | Scenario definition, system under test, seed |
| **Outputs** | `data/runs/<run_id>/` with raw samples, derived metrics, config snapshot |
| **Failure handling** | `set_capacity(C)` touches **only** class 1:1. Never rescales children — that is M3's job after M2 detects the drop |
| **Success** | A run is reproducible from its seed and leaves the testbed in its initial state |

### M7 — Intent API — ✅ built

**Delivered:** `aciq/intent.py` (lifecycle), `aciq/api.py` (HTTP), `--lease` on the driver.
**Deviation:** stdlib `http.server`, not FastAPI — see `PLAN.md`.
**Measured:** a lease for one device address classifies only that device's flows
as `leased`; the others stay in their own classes. The lease class `1:40` is
created, receives the leased traffic, and is reverted on expiry
("in effect for 38.0s of the run").
**Withdrawn:** an earlier "12.92 Mbps mean in the leased class" predated
per-device addresses, so the lease matched all traffic and the number measured
steering, not leasing (`docs/limitations.md` §5h).
**Measured:** on a 10 Mbps capped link, the leased device delivered 23.04 MB
against 17.92 MB without the lease (+28.5%); the two un-leased devices fell to
15.40 and 15.36 MB. Total delivered unchanged, so the lease redistributes a
saturated link rather than adding throughput. One seed; sender-side measurement.
**Fixed:** an over-subscribed tree on a capacity drop -- `min(rate, capacity)`
gave every child the full link -- meant the configured ceiling was exceeded by
~23% (18.41 vs 10 Mbps). Children are now scaled to sum to the capacity.
See `docs/limitations.md`.
**Not yet measured:** the "visibly raises throughput" half of the success
condition. The measured run had no capacity drop, so the link was never
constrained. Needs a `--drop-at` run with and without `--lease`.

| | |
|---|---|
| **Inputs** | `POST /intent {target: device\|flow, ip\|flow, weight, ttl_s}` |
| **Outputs** | Lease with id and expiry; `GET /intent`, `DELETE /intent/{id}`, `GET /status` |
| **Failure handling** | Leases expire automatically — a forgotten request cannot permanently harm the household. Most recent lease per target wins |
| **Success** | A device lease visibly raises that flow's throughput and the effect **reverts on expiry**, verified by the shield |

### M8 — Dashboard — ✅ built

**Delivered:** `aciq/dashboard.py`, `aciqctl dashboard` and `aciqctl serve`.
**Read-only is structural:** the module imports only `html`, `pathlib`,
`dataclasses` and `typing`, so it holds no reference that could reach `tc`. Two
tests enforce it. **Deviation:** no JavaScript and no CDN, so the page is one
self-contained file and updates by `<meta>` refresh rather than a websocket.

| |
|---|---|
| **Inputs** | M5 frames |
| **Outputs** | Static page with inline SVG charts: latency, jitter, loss, throughput, queue depth, fairness |
| **Failure handling** | **Strictly read-only.** It can never write policy — so the dashboard cannot destabilise a link |
| **Success** | All six required panels present and updating live |

### M9 — Transaction manager + shield

| | |
|---|---|
| **Inputs** | A `RatePlan` to apply; live counters for the veto rules |
| **Outputs** | Committed `tc` state, audit log entries, shield mode |
| **Failure handling** | snapshot → apply → verify → (mismatch) rollback → **safe state applied immediately**. Vetoes: class below *scaled* floor; child sum > link; >1 change per 5 s; read-back mismatch; drop/overlimit rate over limit. **Not a veto: delay** — it fires exactly when the policy is stale and would block the fix |
| **Success** | Fault-injection test vetoes a bad policy and returns to safe state; 3 breaches in 60 s → auto-recovery with backoff 1→2→4→8→16→60 s; `MAX_RETRIES=5` consecutive failures then `SAFE_HELD` with a latched alarm. **The retry budget wins over a rolling window**, otherwise retries loop forever. `SAFE_HELD` keeps the safe state applied and requires manual reset |

### M10 — Report generator

| | |
|---|---|
| **Inputs** | Run artefacts |
| **Outputs** | Markdown report with metrics, statistics, and honest failures |
| **Failure handling** | Missing data reported as missing, not as zero |
| **Success** | Report regenerates identically from stored artefacts |

---

## Measured HTB constraints (from the 14-check gate)

These are kernel behaviours, not testbed quirks, and M4/M9 must design around
them:

1. **A class borrows past its parent's `rate`, up to its own `ceil`.** Dropping
   class `1:1` from 100→20 Mbit while children kept `ceil 99/97` delivered
   **28.5 Mbps**. Changing the parent rate alone caps nothing.
2. **A flow is bounded by its own class `ceil`.** With `ceil 9mbit` the same link
   delivered **8.6 Mbps**. Therefore every child `ceil` must be ≤ capacity, and
   child rates must be rescaled to sum ≤ capacity. These are M3 invariants 1 and 2.
3. **HTB's `default` class cannot be changed on a live qdisc.** `tc qdisc change
   ... htb default 50` returns *"Change operation not supported"*. The tree must
   be rebuilt — so rebuild must be part of the M9 transaction, with rollback able
   to restore the prior tree.

## Layer rules

1. **M3 never touches the kernel.** It is a pure function, which is what makes
   the anti-starvation invariant testable without root.
2. **M4 is the only module that calls `tc`.**
3. **M2 never reads latency**, and never reads class 1:1's configured rate.
4. **M8 never writes.**
5. Every module is independently testable. M3 and M5 need no root at all.

## Ordering rationale

M5 is built before M1 and M2 on purpose: without a metrics collector there is no
way to show a classifier improved anything, which would make M1 unmeasurable
rather than merely unimplemented.
