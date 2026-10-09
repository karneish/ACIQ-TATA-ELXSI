# ACIQ+ — Adaptive Classification & Intent-aware QoS

Prototype for *Case Study 3: Adaptive QoS Engine for Mixed Home Broadband Traffic*.

Combines **ACIQ core** (lease, shared bottleneck, baselines, estimator
blindness) with **Aegis hardening** (shield veto rules, CUSUM, multi-seed
statistics, optional ML comparison).

---

## DEADLINE

> **`unset` — supply TELIPORT round dates.**
> Round 1 may be a *design* submission, in which case phase 0b (architecture +
> module contracts) is due before any code exists. Verify against the official
> TELIPORT timeline or your registration email. This plan is deadline-agnostic
> with docs front-loaded, which is safe under either arrangement.

---

## Status

### GATE COMPLETE — 14/14 checks passing

The testbed is proven. Every binary unknown is now **measured**, not assumed.

| Check | Measured result |
|---|---|
| 1–2 | tooling, all modules load |
| 3 | conntrack loopback per-flow: `4351524` vs `965124` bytes, separate entries |
| 4 | namespaces, routes, **IPv6** reachable |
| 5 | gro/gso/tso off on all four ends |
| 6 | HTB bottleneck: **92.6 → 19.1 Mbps** at the 20 mbit drop, invariant HOLDS |
| 7 | netem on leaf: **+20.107 ms** |
| 8 | pyroute2 netlink: per-class bytes/drops/overlimits/backlog |
| 9 | cake at root: **90.8 Mbps** |
| 10a | cake as leaf: **18.0 Mbps**, `1:50 bytes=11892761` |
| 10b | pfifo as leaf: **19.1 Mbps**, `1:50 bytes=13850504` |
| 11 | conntrack forwarded v4: `4720576` vs `1046976` |
| 12 | **MEASURED** — see the saturation decision below |
| 13 | conntrack forwarded **v6**: `4801936` vs `1136336` |
| 14 | IPv6 EF filter **routes**: `1:10 bytes 1764 → 13004` |

### M1 is decided: conntrack, IPv4 and IPv6

Per-flow byte counters work, separately, over loopback **and** forwarded, over
both IP versions. The nftables fallback is not needed.

### MEASURED BUG (first real matrix): M2 death spiral on child `overlimits`

Scenario 3 (three TVs + gaming, ~10.5 Mbps on a 100 Mbps link) drove the
estimate **100 → 24.6 → 13.3 → 10.8 → 7.2 Mbps** and made 4 policy changes.

Cause: **an HTB child's `overlimits` rise when that child exceeds its own
guaranteed rate**, which happens routinely on a nearly idle link. M2 read summed
child overlimits as congestion, shrank capacity, which shrank the class rates,
which raised the children's overlimits again. Positive feedback.

Gate check 12 could not have caught this: there the link genuinely was saturated,
so child overlimits and link saturation were indistinguishable.

**First fix attempt — parent class only. Insufficient.** HTB attributes a
child's borrow to the parent: a parent's `overlimits` rise when a child is
backlogged and borrowing. So "the parent is busy" does not mean "the link is
full", and the collapse survived (estimate still 7.2 Mbps).

**Final fix: parent overlimit RATE above a threshold set from measurement.**

| Condition | Measured overlimits |
|---|---|
| 100 Mbps link genuinely full (s1, bulk saturating) | **5127 – 6485 /s** |
| 20 Mbps link saturated (gate check 12) | **24803 – 65101 /s** |
| 100 Mbps link ~10% loaded, children rate-limited (s3) | **170 – 1313 /s** |

`SAT_OVERLIMIT_MIN = 3000 /s` separates the two populations with ~4x margin at
the closest point, and unlike attribution alone it does not depend on guessing
HTB's internals. Child overlimits are ignored entirely.

Replayed against the real recorded data:

| Scenario | Before | After |
|---|---|---|
| s1 (full link) | 100.7 | **99.9, saturated** |
| s3 (10% loaded) | 7.2, 4 changes | **0.0, 0 changes** |
| s2 (drop to 20) | 52.7 | **32.4, stepping down** |

Covered by `TestMeasuredSeparation` (5 tests) and `TestDeathSpiral` (3).

**Honest residual limitation:** separating "link full" from "class rate-limited"
by magnitude works for these two populations, but it is a threshold fitted to
observed data, not a proof. A link pushed to 1% over its limit by many children
rather than one would look like scenario 1. Distinguishing them in general needs
the delay-based signal, which remains out of the MVP — this is now a
*demonstrated* limitation rather than an assumed one.

### MEASURED CONSTRAINT: the driver must load kernel modules itself

B1 failed with `Specified qdisc kind is unknown` for `cake`, even though
`modprobe sch_cake` reported success and the identical command had **passed**
inside the 14-check gate. The gate had its own `modprobe` list; `setup.sh` had
none, so qdisc kinds were only present because an earlier gate run happened to
have loaded them. `setup.sh` now loads all ten required modules and warns by
name. Testbed setup must be self-contained — a testbed that depends on residue
from a previous run is not reproducible.

### M2 is decided: COUNTERS ONLY, no probe in the MVP

Check 12, measured on a saturated 20 mbit link (idle baseline **0.051 ms**):

| Signal | Result | Verdict |
|---|---|---|
| `overlimits` per class | **24803 → 65101** over 25 s | **PRIMARY.** Unambiguous, huge, already in `tc -s` |
| `dropped` | 0 → **252** | primary, corroborating |
| Unmarked probe, class 1:30 | **0.051 → 0.405 ms (~8x)** | validated fallback, **not needed** |
| **EF probe, class 1:10** | 0.051 → **0.070 ms** | **REJECTED** |
| `backlog` | **0 throughout** | **REJECTED** |

**The reviewer's HTB reasoning was correct and my EF-probe design was wrong.** A
probe in the *protected* class reports how well the class is protected, not
whether the link is saturated — it showed no signal at all. A probe in the bulk
class would have worked, but the counters are better: they need no probe traffic,
no probe overhead accounting, and no added privilege.

**Consequence:** M2 ships on **drop rate + overlimit rate**, with goodput flat at
a ceiling as corroboration. `backlog` is retained as a diagnostic only. The
probe path stays structurally available but is **not in the MVP** — which also
removes the biggest cost item from the CPU-overhead numbers.

**Honest boundary this does *not* fix:** counters still only see a bottleneck on
the router. A downstream ISP-side bottleneck remains invisible without a delay
signal. That limitation stands, and now has a validated remedy documented
(unmarked probe, ~8x signal) rather than a vague one.

**Gated work — do not build ahead of these:**



---

## Build order (solo, no fixed deadline)

Nothing is cut. Sequencing is what protects the schedule: **breadth moves to the
end instead of being dropped.**

| Phase | Work | Gate to proceed |
|---|---|---|
| **0** | Testbed gate, 14 checks | **Binary go/no-go.** If this fails, everything downstream is built on sand |
| **0b** | ✅ `docs/architecture.md` + module contracts (M1/M2 **DRAFT**). `docs/setup.md` still to write | Before any code, in case Round 1 is design-only |
| **1** | ✅ `model.py`, M3, generators — 38 checks, +4 invariant tests | — |
| **2** | ✅ **M5 metrics collector** — 27 checks | — |
| **3** | ✅ M1 classifier — conntrack, rules + statistics | **DONE, 28 tests** |
| **4** | ✅ M2 estimator — counters only, no probe | **DONE, 27 tests** |
| **5** | ✅ M4 enforcement + M9 transaction/shield — **vertical slice complete** | **DONE, 47 tests** |
| **6** | ✅ M6 + M10 built. **s1 and s2 measured**; B0/B1 still failing to apply — diagnosing |
| **7** | M7 + lease demo run | Contribution becomes visible |
| **8** | M10 thin report → M8 thin dashboard | Phase 6 numbers exist |
| **9** | Scenario 2 both variants, IPv6 run | — |
| **10** | Multi-seed statistics, ≥6 seeds | — |
| **11** | Should: B2, sweeps, `make demo`, CI. Could: CUSUM, ML, probe | — |

`docs/limitations.md` is written **continuously** from phase 0 onward, not
scheduled at the end.

**B0 is in phase 6 deliberately.** It is one `pfifo` qdisc and it demonstrates
the bufferbloat the entire project exists to address. Comparing only against
`cake` hides that.

**Phase 6 is the priority deliverable:** call latency measurably beats `cake` at
95%, with numbers in hand.

---

## Modules

Phases 1–5 complete. **M3, M5, M1, M2, M4 and M9 are all built and tested.**
The vertical slice exists: classify → estimate → shape → roll back, with a
veto-gated shield and an escalating safe state. Next is phase 6, the six runs.

| ID | Module | What it does |
|----|--------|--------------|
| M1 | Classifier | Stage A: DSCP EF + well-known signalling ports. Stage B: per-flow rate/avg-packet/burstiness/duty-cycle from conntrack. Confidence per decision; <0.5 = unclassified. **Ignores the generators' own ports by design**, or accuracy would be circular. UDP/443 ambiguity reported, never guessed. ✅ built |
| M2 | Capacity estimator | `tc -s` counters only, **no probe**. Asymmetric EWMA, ±10% band, 5 s dwell, saturation-gated (never learns from an idle link). Optional busy-gated CUSUM for drift. ✅ built |
| M3 | Policy engine | Pure function, no kernel access. Weights 8/4/2, floors, lease. **Invariant: sum of child rates ≤ link rate.** ✅ built |
| M4 | Enforcement | Sole kernel writer: rates → filters → leaf qdiscs → read-back verify. **Must rebuild the whole tree when the HTB default class changes** — it cannot be changed in place (measured). |
| M5 | Metrics collector | p50/p95/p99, jitter, loss, per-class throughput, queue depth, Jain index, CPU. **Strictly separate from M2's inputs.** ✅ built |
| M6 | Experiment harness | Seeded, scripted. `set_capacity()` changes **only** class 1:1. |
| M7 | Intent API | `POST /intent` (device or flow) with auto-expiry, `GET`/`DELETE`/`/status`. ✅ built — stdlib `http.server`, **not FastAPI**: see below. |
| M8 | Dashboard | Read-only page, inline SVG charts. ✅ built — no JS, no CDN. |
| M9 | Transaction manager + shield | Snapshot, apply, verify, rollback, safe state, audit log, veto rules. |
| M10 | Report generator | Reproducible report from run data, with statistics. |

### Deviations from this plan, and why

**M7 is `http.server`, not FastAPI.** The plan says FastAPI; it is not installed,
and neither are starlette, uvicorn, flask or aiohttp. For *this* service the
standard library is the better fit rather than a compromise: M8's hard
requirement is that it can never write policy, and a handler that only reaches a
lease book and a read-only snapshot cannot be extended into a writer later by
accident. If FastAPI is wanted, `aciq/api.py`'s `IntentService.handle` is the part
to wrap — it is already a pure function of (method, path, body) and needs no
socket.

**M8 uses no JavaScript.** Charts are inline SVG plus one `<meta>` refresh, so
the page is a single self-contained file. A dashboard that needs a CDN stops
working on exactly the air-gapped host it would be demonstrated on. The
trade-off is real: charts update by page reload rather than over a websocket.

**Module contracts** (inputs / outputs / failure handling / success conditions)
live in `docs/architecture.md`. The **M1 and M2 contracts are marked DRAFT** —
they depend on gate results and must not be submitted as final text.

---

## Shield veto rules

Each uses data we actually have:

1. Any class below its floor — **checked against the *scaled* floor, respecting
   `degraded`** (fix 5, below)
2. Child rates sum > link rate
3. More than one policy change per 5 s window
4. `tc` read-back does not match what was applied
5. **Drop / overlimit *rate*** above limit. Backlog is a **warning only** —
   `fq_codel` keeps queues short by design, so a backlog veto would rarely fire
   and would read as protection that isn't there (fix 2)

**Not a veto:** interactive delay. It fires exactly when capacity drops and the
policy is stale — blocking the one change that fixes the problem. Veto
conditions must never include the symptom the system exists to resolve. Delay
is a **reported diagnostic** (fix 1).

### Safe state — measured necessity, not a preference

The emergency safe state has **no per-class breakdown**. It exists to keep the
household protected when something is already wrong, so it must be the thing
most likely to succeed: a tree containing class `1:30` cannot be applied if
`1:30` is precisely what the kernel refuses. This was found by fault injection
— the first design rolled back *into* the same broken command and reported
failure, leaving the household unshaped at the worst moment.

Escalation ladder, each rung measured to work on this laptop:

| Rung | Command | Gate evidence |
|---|---|---|
| 1 | `cake bandwidth 0.95·C` at root | check 9: **90.8 Mbps** |
| 2 | `fq_codel` at root | plain fair queueing, no rate limit |
| 3 | `pfifo limit 1000` at root | check 10b |

Losing the class breakdown is an accepted cost: **during a fault, protection
beats classification.** If all three rungs fail, rollback reports failure
honestly rather than claiming success.

### Shield modes and recovery

```
MONITOR ──breach──> FAULT_PENDING     safe state applied IMMEDIATELY, alarm raised
FAULT_PENDING ──auto──> retry after backoff   1s → 2s → 4s → 8s → 16s → 60s cap
FAULT_PENDING ──budget exhausted──> SAFE_HELD   alarm latched
SAFE_HELD ──manual reset──> MONITOR
```

- **The retry budget wins over the window.** `MAX_RETRIES = 5` consecutive
  failed recovery attempts. Backoff caps at 60 s. A *rolling 60 s window*
  would be a bug: once backoff reaches 60 s each retry lands in its own window,
  the counter never reaches 5, and retries loop forever.
- **The budget resets only after `SUSTAINED_OK_S = 300`** (5 min) with no
  breach, measured in MONITOR/ENFORCE. Time passing alone never resets it.
- **`SAFE_HELD` is a safe state, not a lock.** The safe state **stays applied
  and keeps running** — interactive protected, everything else at its floor.
  Adaptive shaping is suspended, not disabled; the household is never left
  unshaped. The alarm is **latched and visible** (status API, dashboard banner,
  audit log). Manual reset is available and is the only thing that clears it —
  which is correct, because `SAFE_HELD` cannot accumulate sustained health and
  therefore can never auto-reset (fix 4).
- Three breaches in 60 s move MONITOR/ENFORCE → FAULT_PENDING. *Fault* means
  "pinned to safe state **with auto-recovery**", not "waits for a human".
- A fault-injection test feeds a deliberately bad policy and asserts it is
  vetoed and the system returns to the safe state.

---

## Policy and lease rules

| Rule | Value |
|------|-------|
| Floor per class | `max(2 Mbps, 5% of link rate)`, never revocable |
| Rate | Weighted share, **never below the floor**. "Leftovers" is wrong wording — the floor is the guarantee |
| Invariant 1 | Sum of child **rates** ≤ link rate, on every capacity change. Guarded by `test_parent_child_rescale_on_100_to_20` |
| Invariant 2 | Every child **ceil** ≤ link rate. Measured necessity: a 20 Mbps parent with ceil 99/97 children delivered 28.5 Mbps |
| Lease | `{"target":"device","ip":"...","weight":0.4,"ttl_s":90}` or a specific flow |
| Lease formula | `LEASED = INTERACTIVE × (1 + λ × clamp(weight, 0, 1))`, λ = 0.5 → **9.6 at weight 0.4** |
| Device lease | Resolved to live conntrack flows; dominant flow gets sub-class `1:40` |
| Expiry | Automatic; the revert is verified by the shield |
| Overlapping leases | Most recent per target wins (documented) |
| Safe state | Interactive protected, everything else at its floor |

> **Lease formula warning — do not "simplify" this.**
> The obvious-looking form `LEASED = λ × weight` makes a lease of 0.4 weigh
> **0.2**, against bulk's **2.0**. The lease then becomes the *lowest* priority
> class in the system — weaker than the traffic it exists to protect. The unit
> tests caught this. The formula is anchored to the class the lease actually
> promotes. `test_lease_influence_is_bounded` and
> `test_leased_class_beats_bulk` guard it.

### Capacity estimation

- **M2 must NEVER read class 1:1's configured rate.** That value is the answer;
  reading it makes the estimator an oracle and makes adaptation time measure
  zero.
- `set_capacity(C)` in M6 changes **only** class 1:1. It never rescales ACIQ's
  children — that is M3's job, after M2 detects the drop.
- Asymmetric EWMA: fast down (α=0.6), slow up (α=0.1). Hysteresis ±10%. Min 5 s dwell.
- Saturation signal: **drop rate + overlimit rate + goodput flat at ceiling.**
  Backlog is a diagnostic only.
- **CUSUM is busy-gated and secondary.** It detects *drift*, not the 5× step
  that scenario 2 produces — a threshold on the EWMA delta is the primary
  mechanism. CUSUM must only consume samples where the link shows demonstrable
  load; an idle link's drain rate near zero is **not** a capacity collapse, and
  feeding it to CUSUM produces false positives (fix 3).
- Generators' own latency measurements are **evaluation data** and never enter M2.

---

## Testbed

| Item | Detail |
|------|--------|
| Environment | Pop!_OS laptop, three namespaces: `client`, `router`, `wan`. Host network untouched |
| Shaped direction | Downloads (wan → client) on the router's **home-facing** `veth-lan` |
| The slow line | HTB class `1:1`: 100 Mbps → 20 Mbps. Identical bottleneck for **all** systems |
| `netem` | Delay/jitter/loss **only**. Never used to set the speed |
| IPv4 / IPv6 | `10.0.1.0/24`, `203.0.113.0/24` / `fd00:1::/64`, `fd00:2::/64` |
| Offloads | gro/gso/tso off on all four veth ends |
| B0 | One class, `pfifo limit 1000` |
| B1 | One class, `cake` at 95% of link |
| B2 (optional) | Static HTB 50/30/20 |
| ACIQ+ | 4 classes, `fq_codel` each, rate **and** ceil |

### Gate progress

| Check | Result |
|---|---|
| 1–9 | **PASSING** on run 3 (tooling, modules, conntrack per-flow, routes+IPv6, offloads, HTB bottleneck **19.1 Mbps at 20 mbit**, netem **+20.057 ms**, pyroute2 netlink, cake root **90.8**) |
| 10–14 | pending |

### 14 gate checks

| # | Check | Pass criterion |
|---|-------|----------------|
| 1 | tooling | incl. `ethtool` |
| 2 | modules | one at a time, names any missing |
| 3 | conntrack loopback per-flow | both flows have `bytes=` **and** 1000B flow larger |
| 4 | namespaces and routes | IPv4 + IPv6 pings succeed |
| 5 | offloads off | all three off, all four ends |
| 6 | HTB 1:1 bottleneck | ~90–97 then ~18–20, same device |
| 7 | netem on leaf | +20 ms |
| 8 | pyroute2 netlink | reports `NETLINK FAILED` if downgraded to `tc -s -j` |
| 9 | cake at root 95% | ~88–93 |
| 10a | cake as leaf | 14–21 Mbps **and** >1 MB on `1:50` |
| 10b | pfifo as leaf | 14–21 Mbps **and** >1 MB on `1:50` |
| 11 | conntrack forwarded per-flow v4 | both flows have `bytes=` **and** 1000B larger |
| 12 | **MEASUREMENT** | saturation signals. Records numbers, never fails |
| 13 | conntrack forwarded per-flow v6 | both flows have `bytes=` **and** 1000B larger |
| 14 | IPv6 EF filter | proven by class 1:10 bytes **growing** |

Checks 3/11/13 decide M1. Check 12 decides M2. Check 14 proves the filter
*routes* traffic, not merely that `tc` accepted it.

---

## Experiments

| Scenario | Systems | Runs |
|----------|---------|------|
| 1. ISO during a call (IPv4) | B0, B1, ACIQ+ | 3 |
| 3. Three TVs plus gaming | B0, B1, ACIQ+ | 3 |
| 2. Drop 100 → 20 Mbps | ACIQ+, B0/B1 **static**, B0/B1 **informed** | 5 |
| 1. Same, IPv6 | ACIQ+ only — compatibility check | 1 |
| **Total** | | **12** |

- **Static** baselines keep their 100 Mbps settings — realistic.
- **Informed** baselines are handed the new capacity instantly — an **oracle
  best case no real device has.** It answers "why not just use cake?"
- **Multi-seed:** ≥6 seeds for headline comparisons. For paired Wilcoxon the
  smallest attainable two-sided p-value is `2^(1-n)`: at n=5 that is 0.0625 and
  **cannot** reach p<0.05; at n=6 it is 0.03125. Fewer than 6 pairs → report
  ranges and CIs, not p-values.
- Statistics: paired Wilcoxon, bootstrap CIs, effect sizes.

**Metrics:** p50/p95/p99 latency, jitter, loss, per-class throughput, queue
depth, Jain index, adaptation time, policy changes/min, classification
accuracy, capacity error, CPU (`resource.getrusage`).

**Honest reporting:** "about 95% accuracy" and "within 10% error" are
**hypotheses**. The report states real numbers, including failures. `cake` may
win in some scenarios and that goes in the report. ACIQ's adaptation time is
reported **separately**, not folded into the run table.

---

## Technology stack

| Layer | Tool |
|-------|------|
| Language | Python 3 (C++/eBPF collector optional, later) |
| Enforcement | Linux `tc`: HTB, `fq_codel`, `cake`, `pfifo`, `netem` |
| Per-flow data | conntrack byte accounting; nftables counters as fallback |
| Counter access | `pyroute2`, `tc -s -j` JSON fallback |
| Test network | `iproute2`, namespaces, `veth`, `ethtool` |
| Traffic | own generators (`call`, `game`, `video`, `bulk`) + `iperf3` |
| API / dashboard | FastAPI, static page, inline SVG charts |
| Stats / tests | `numpy`, `scipy`, `pytest`, `hypothesis` |
| Optional | `scikit-learn` ML comparison; Prometheus/Grafana |
| Automation | bash gates, `make demo`, CI on the 38 root-free checks |

Every third-party package is listed in `docs/licenses.md`. Nothing is
redistributed. `pyroute2` (BSD-3-Clause) is the only non-stdlib dep in the MVP.

**ML comparison, if attempted:** train a small model on self-generated traffic,
then compare **rules only / ML only / ML with rules fallback** on the same data.
It counts only if it improves a measured result (e.g. UDP/443 call-vs-download
error, or call latency). **If it does not beat the rules, report that and ship
the rules.**

---

## Tata's requirements and where they are covered

| Requirement | Where |
|-------------|-------|
| Classify without reading payloads | M1 |
| Estimate link capacity | M2 |
| Queueing and shaping | M4, HTB + `fq_codel` |
| Verify improvement | M5, M6, M10 |
| Temporary intent while fair | M7 lease + M3 floors |
| Independent modules with I/O, failure handling, success conditions | `docs/architecture.md` |
| AI vs deterministic baseline | rules baseline + optional ML comparison |
| No decryption | header/counter metadata only |
| Linux `tc` | all enforcement |
| IPv4 and IPv6 | dual filters, checks 13/14, one IPv6 run |
| Rollback, no starvation | M9 + M3 floors |
| Confidence and correction | M1 |
| Licences documented | `docs/licenses.md` |
| Reproducible data and impairment settings | seeds, committed settings, scripted runs |
| Emulation labelled | HTB shaper emulation, stated |
| No secrets | `.env.example`, fictitious values only |
| Bounded, observable, reversible | shield, audit log, rollback |
| Dashboard (latency, jitter, loss, throughput, queue depth, fairness) | M8 |
| API or UI for intent | M7 |
| Architecture diagram | `docs/architecture.md`: device `client`, edge `router`, network `wan`, data run files, analytics M5/M6/M10, UI M7/M8 |
| Setup guide with exact versions | `docs/setup.md` |
| Scripted demo: reset, inject, collect, report | M6 + `make demo` |
| Known limitations | `docs/limitations.md` |

---

## Limitations (stated up front)

- **Emulated line** — an HTB token-bucket shaper, not real DSL/cable/fiber. It
  does not model ISP overhead or modem behaviour.
- **Bottleneck location** — counters only see a bottleneck **on the router**. In
  a real home it is usually the modem or ISP side, where router counters show
  nothing. A real product needs a delay-based signal. The optional probe and
  CUSUM help but do not close this.
- **Idle links** — passive estimation is valid only while the link is busy.
- **Self-made traffic** — classification accuracy is measured on traffic we
  generate, so it looks better than on real homes. UDP/443 call-vs-download
  remains hard.
- **`cake` may win** — static `cake` can hold call latency well in some
  scenarios.
- **Out of scope** — Wi-Fi airtime and WMM, ISP-side policing, TR-069/TR-369,
  certification, scale above 1 Gbps, encrypted DNS, QUIC port hiding, real CPE
  hardware.
- **Untested** — the first run of any script will probably need fixes.

---

## Self-assessment

An 83/100 planning estimate, recorded as a planning aid only. It tracks the
**plan**, not what has been built, and a self-scored rubric is not evidence.
The rows that would move are "testing done so far" (gate unrun), "classifier"
(conntrack unknown), and "line-speed measurement" (downstream bottleneck
invisible). A passing gate plus a measured phase-6 result converts several rows
from plan to evidence.

---

## Next actions

1. **Run the gate.** This unblocks phases 3 and 4; nothing else can be finalised.
   ```bash
   sudo apt update && sudo apt install -y iproute2 iperf3 conntrack ethtool nftables python3-venv
   python3 -m venv ~/aciq-venv && ~/aciq-venv/bin/pip install pyroute2
   sudo ./testbed/setup.sh && sudo ip netns list && sudo ./testbed/cleanup.sh
   sudo env ACIQ_VENV=/home/YOU/aciq-venv ./testbed/gate.sh
   sudo ./testbed/cleanup.sh
   ```
   Paste `testbed/logs/gate-*.log`, **checks 3, 11, 13 first**, then check 12.
2. **Build phase 0b docs** — architecture and module contracts, M1/M2 marked DRAFT.
3. ✅ **M5 built.** Next: `docs/setup.md`, then M1/M2 as soon as the gate log arrives.
4. **Supply TELIPORT round dates** and fill the deadline marker.

### What would change the plan

| Observation | Consequence |
|-------------|-------------|
| Checks 3/11/13 fail | M1 uses nftables counters instead of conntrack. Still valid, slower to build |
| Check 12: nothing moves | Saturation invisible to `tc -s`. Fall back to rate-change detection and **raise it as a real limitation** |
| Check 12: delay-only signal | A probe is required in the MVP, not optional. Adds probe-overhead accounting |
| `sch_cake` missing | B1 baseline unavailable. Report it; do not substitute silently |
