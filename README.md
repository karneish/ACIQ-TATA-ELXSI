# ACIQ — Adaptive Classification & Intent-aware QoS

**Case Study 3 — Adaptive QoS Engine for Mixed Home Broadband Traffic**
(TATA ELXSI / TELIPORT)

**Repository:** <https://github.com/karneish/ACIQ-TATA-ELXSI>
**Live demo (static replay):** <https://karneish.github.io/ACIQ-TATA-ELXSI/>
**Code under test:** `1ee8e57d` (commits after it change documentation and
evidence only). **Last full DEV band:** 2026-11-01, seeds 1000–1009.
**Verdict authority:** [`tools/verify_round3.py`](tools/verify_round3.py) — prose
in this file may not improve on what it prints.

---

## At a glance

| | |
|---|---|
| **What it is** | A Linux home-broadband data path: classify flows without payload, estimate the real link capacity from queue counters, plan per-class rates with floors, enforce with HTB + `fq_codel`, and grant time-boxed leases. |
| **Where it runs** | A three-namespace testbed (`router`, `client`, `wan`) on a real kernel; the slow line is an HTB token-bucket shaper. |
| **Enforcement status** | **Verified** — testbed gate **20 PASS + 1 MEASURED, 0 FAIL**. |
| **Controller status** | **96 / 100 PASS, 0 SKIP** on the 2026-11-01 DEV band at `19e9e8a5`; the four misses are diagnosed and fixed in `1ee8e57d`; the confirming full-band re-run started 2026-11-01 19:31. |
| **Final acceptance band** | **Not run** — gated on the DEV verdict and a frozen constant set. |
| **Tests** | **1578 run, 0 failed, 10 skipped** (live-kernel tests that need `iproute2`). |
| **Lease result** | **+27.46 % to +28.92 % (mean +28.13 %)** for the leased device on a saturated 10 Mbps link, 7 paired seeds, exact paired Wilcoxon **p = 0.015625**. |
| **Best claim that is actually supported** | The enforcement stack removes pfifo bufferbloat under a capacity drop; the lease mechanism delivers a measurable, significant redistribution; the round-3 controller lands and climbs inside declared bounds. |
| **Claims that are NOT made** | Superiority over a tuned CAKE; any p99 advantage; device identity beyond source IP; per-flow fairness; the final band. |

---

## Live demo

**<https://karneish.github.io/ACIQ-TATA-ELXSI/>**

A static replay of recorded testbed evidence: a real 100 → 50 Mbps step-down
(`s2b_step_50`, seed 1002) with the applied rate and delivered goodput the
harness measured, plus the 7-seed latency table.

GitHub Pages serves static files only — the controller itself needs root and
Linux network namespaces. Nothing on that page applies rules to your network,
and nothing there is simulated.

---

## Contents

1. [What this is](#1-what-this-is)
2. [Status: verified, measured, not done](#2-status-verified-measured-not-done)
3. [How the controller works](#3-how-the-controller-works)
4. [Measured results](#4-measured-results)
5. [The round-3 verdict rule](#5-the-round-3-verdict-rule)
6. [Reproducing every number](#6-reproducing-every-number)
7. [Repository layout](#7-repository-layout)
8. [Provenance and the retune discipline](#8-provenance-and-the-retune-discipline)
9. [Known limitations](#9-known-limitations)
10. [FAQ — reading the results without being misled](#10-faq--reading-the-results-without-being-misled)
11. [Documentation](#11-documentation)
12. [Licence](#12-licence)

---

## 1. What this is

ACIQ is a traffic controller for a home broadband link. It answers four
questions, in order, every tick:

1. **What is this flow?** — DSCP and per-flow behaviour, never payload. Every
   decision carries a class, a confidence and its evidence.
2. **How much capacity is actually there?** — queue counters only. The
   estimator's input type has no `configured_mbps` field, so it cannot read the
   shaper's configured rate even by accident.
3. **How should the link be shared?** — a pure policy function: per-class
   rates, guaranteed floors, lease weights, with the invariant
   `Σ rates ≤ capacity`.
4. **Is it safe to commit?** — a verifier, a shield with veto rules, a
   snapshot/apply/read-back/rollback transaction, and an escalating safe state.

Then the only module that touches the kernel renders the tree and reads it back.

```
 traffic ──► M1 classify ──► M2 estimate capacity ──► M3 plan ──► M9 shield ──► M4 tc
             (DSCP +          (queue counters        (shares,       (veto,        (HTB +
              behaviour)       only)                  floors,        rollback)     fq_codel)
                                                        leases)
```

### The testbed

Three network namespaces — `router`, `client`, `wan` — joined by veth pairs.
The slow line is **HTB class `1:1`**, a token-bucket shaper. `netem` supplies
delay and loss only, never bandwidth. Using `netem` for rate would have been
simpler and would have lied about what is being emulated.

### Safety

- **Every policy change is transactional** (`aciq/txn.py`): snapshot → apply →
  read the kernel back → roll back on mismatch. A change that does not verify is
  never left in place.
- **The shield can veto** (`aciq/shield.py`): the rate law's step/dwell envelope,
  the change-rate limit and the delay-emergency path are enforced before a commit
  reaches `tc`.
- **Degradation is explicit**: if the link cannot honour every floor, floors
  scale down and `degraded=True` is set; the controller does not silently
  over-subscribe.
- **The band runner is bounded**: every cell runs under
  `timeout --foreground --kill-after=60s` at 3× its estimate, so a hung kernel
  call cannot block a 5-hour band.
- **Cleanup is checked**: the runner exits non-zero if `router`, `client` or
  `wan` survives teardown.

### Modules

| Module | File | Responsibility |
|---|---|---|
| M1 classifier | `aciq/classify.py`, `aciq/flowtrack.py`, `aciq/features.py` | DSCP + behaviour → class, confidence, evidence |
| M2 capacity | `aciq/capacity.py`, `aciq/external_capacity.py` | estimate from counters only |
| M3 policy | `aciq/policy.py` | shares, floors, lease maths (pure function) |
| Rate law | `aciq/ratecap.py`, `aciq/verifier.py` | steps, dwell, severe landing, demand probe |
| M4 enforcement | `aciq/tc.py`, `aciq/qdisc.py` | render, apply, read back |
| M5 metrics | `aciq/metrics.py`, `aciq/measure.py` | counters → rates, percentiles, jitter, loss, fairness, CPU |
| M6 harness | `aciq/harness.py`, `aciq/experiment.py`, `aciq/closedloop.py` | closed loop, baselines, run sequencing |
| M7 intent API | `aciq/intent.py`, `aciq/identity.py`, `aciq/corrections.py`, `aciq/api.py` | leases, corrections, token-auth HTTP API |
| M8 dashboard | `aciq/dashboard.py` | read-only view of a run |
| M9 shield | `aciq/shield.py`, `aciq/txn.py`, `aciq/watchdog.py` | veto, rollback, safe state |
| M10 report | `aciq/report.py` | Markdown with per-percentile verdicts |

---

## 2. Status: verified, measured, not done

| Claim | State | Evidence |
|---|---|---|
| Per-flow enforcement, IPv4 and IPv6 | **verified on a kernel** | gate checks 11/13/16/18; [`data/live_status_round3/dev_gate.log`](data/live_status_round3/dev_gate.log) |
| DSCP-EF claim rejected below capacity | **verified on a kernel** | gate checks 14 and 17 |
| IPv6 filters, routes and teardown | **verified** | gate checks 13/18/19/20 |
| Capacity drop enforced, no over-subscription | **verified on a kernel** | [`docs/gap-closure/capacity-drop-collision.md`](docs/gap-closure/capacity-drop-collision.md), [`docs/gap-closure/live-enforcement-validation.md`](docs/gap-closure/live-enforcement-validation.md) |
| Lease lifecycle and measured benefit | **verified on a kernel**, p = 0.015625 | [`docs/limitations.md`](docs/limitations.md) §lease, [`docs/gap-closure/device-identity-and-leases.md`](docs/gap-closure/device-identity-and-leases.md) |
| Controller landing / climb verdicts | **96/100 PASS on DEV**; final band pending | [`data/experiments/RESULTS_DEV3.md`](data/experiments/RESULTS_DEV3.md), [`data/live_status_round3/dev_verify.log`](data/live_status_round3/dev_verify.log) |
| Capacity estimation, replay | **verified offline** | 100 → 45.97 → 24.38 → 15.41 → 12.15 → 10.86 Mbps against truth 10 |
| Capacity estimation, end to end | **exercised live in round 3, not yet frozen** | applied tracks truth on the down shapes; final band pending |
| Rollback against a real failing `tc` | **6 / 6** (earlier phase) | [`docs/PROJECT_REPORT.md`](docs/PROJECT_REPORT.md) |
| Long-run stability | **1851 s, 8 policy changes** (earlier phase) | [`docs/PROJECT_REPORT.md`](docs/PROJECT_REPORT.md) |
| API security (token auth, bind policy, rate limit, audit) | **verified offline and over a socket** | [`docs/gap-closure/api-security-validation.md`](docs/gap-closure/api-security-validation.md) |
| Better than a well-tuned CAKE | **not established** | paired tests in §4.1 |
| Device identity beyond source IP | **not built** — IP-only identity, documented as a deployment assumption | [`docs/gap-closure/final-validation-report.md`](docs/gap-closure/final-validation-report.md) §C P1-002 |
| Per-flow (intra-class) fairness surface | **not built** — Jain is per class | ibid. §C P1-005 |
| Soak / memory scaling | **not measured** | ibid. §C P2-002 |
| Final acceptance band (seeds 1100–1109) | **not run** | gated on the DEV verdict |

**Nothing blocked is reported as passed.** The distinction between “tested
offline”, “run on a kernel” and “frozen verdict” is kept everywhere in this
repository.

### The testbed gate (2026-11-01)

Twenty checks PASS and one is a measurement; none fails:

```
 1 tooling                              11 conntrack forwarded per-flow v4
 2 modules                              12 saturation signals      (MEASURED)
 3 conntrack loopback per-flow          13 conntrack forwarded per-flow v6
 4 namespaces and routes                14 IPv6 EF filter routes to 1:10
 5 offloads off                         15 per-flow flower filters install
 6 HTB bottleneck 1:1                   16 steered IPv4 flow routes to 1:20
 7 netem on leaf                        17 rejected EF claim does not reach 1:10
 8 pyroute2 netlink                     18 steered IPv6 flow routes to 1:20
 9 cake at root                         19 removing the filter restores default
10a cake as leaf                        20 teardown removes bridge filters
10b pfifo as leaf
```

The gate stops at the first failure; this run is recorded verbatim in
`data/live_status_round3/dev_gate.log`.

---

## 3. How the controller works

The controller is a **law plus evidence**, not a set of tuned magic numbers.
Every constant is declared in
[`docs/evidence/round3-params.md`](docs/evidence/round3-params.md) *before* the
run it applies to, and the verifier decides PASS/FAIL.

| Rule | Value |
|---|---|
| Maximum rate change per commit | 25 % of applied (`MAX_RATE_STEP_FRAC`) |
| Ordinary descent step | 10 % (`down_step_frac`); 25 % when the wire itself drops |
| Minimum dwell between commits | 5 s (`MIN_DWELL_S`) |
| Emergency descent | 2× the normal step, up to 500 Mbps/s |
| Per-class floor | `max(2 Mbps, 5 % of capacity)`; scaled with `degraded=True` if unaffordable |
| Change-rate limit | 12 commits per minute |
| Down-step legal target | `max(drop_mbps, floor_total)` |
| Down-step acceptance band | 1.10 × legal |
| Climb acceptance | applied ≥ 0.60 × truth **and** delivered ≥ 0.50 × truth over the final third |
| Stress acceptance | ≥ 1 commit and last-third delivered/applied ≥ 0.50; no rate claim during pure saturation |

The two mechanisms that matter for round 3:

- **Severe-drop landing** — when the belief is saturated and has fallen through
  0.9 × applied, the controller commits the whole lawful drop in *one* commit
  instead of walking down 25 % at a time. The landing is still a real kernel
  change, still bounded, still rollback-able.
- **Demand probe** — an up-step cannot be discovered from a saturated link, so
  the controller pierces +25 % for one hold window when the tree is seen
  overlimiting, then lands back on `min(known_good, delivered)` if the wire
  inflates. The pierce gate is the tree's own overlimit counter, not a timer.

Design points worth knowing:

- **The estimator cannot cheat.** `Measurement` has no `configured_mbps` field.
- **No starvation by construction.** Every class keeps a floor and
  `Σ rates ≤ capacity` is tested, including across a 100 → 20 Mbps collapse.
- **HTB's `default` class cannot be changed on a live qdisc** — measured. Every
  policy change is a full tree rebuild, which the transaction can roll back.

### The round-3 shape set (10 shapes × 10 seeds)

| Shape | Protocol | What it tests |
|---|---|---|
| `s2b_step_50` | 100 → 50 Mbps at t=10 s, 40 s | mid-range drop |
| `s2b_step_10` | 100 → 10 Mbps at t=10 s, 40 s | near-floor drop |
| `s2b_step_up_20to100` | 20 → 100 Mbps at t=10 s, 40 s | recovery / climb |
| `s2b_ramp_100to30` | flat 100, ramp to 30 over 20 s from t=10, 60 s | tracking a moving target |
| `s7_up_20to60` | 20 → 60 at t=10 s, 40 s | climb fractionation |
| `s7_up_30to100` | 30 → 100 at t=10 s, 40 s | climb from a high start |
| `s7_rampup_30to100` | flat 30, ramp to 100 over 20 s from t=10, 40 s | up-ramp tracking |
| `s7_down_100to15` | 100 → 15 at t=10 s, 40 s | mid-severe drop |
| `s7_down_100to8` | 100 → 8 at t=10 s, 40 s | severe drop near the floor |
| `s3_stress` | flat 100; game + 3 video + bulk background, 40 s | demand > capacity; no rate claim by design |

---

## 4. Measured results

Every table in this section names its source. Percentiles are the runtime's own
(`call.json`: RTT p50/p95 and inter-sample jitter); “delivered” is the
receiver's `cum=` total over elapsed time, not our class accounting.

### 4.1 The 7-seed scenario band (pre-round-3 stack, revision `c5da3fd9`)

Seven paired seeds (42-48), three systems, on a kernel. In these runs the
classifier is wired to enforcement: the ADAPTIVE class carries the video traffic
(4.69 Mbps at t=20.77 in Scenario C). This is the **pre-round-3** stack, not the
round-3 controller of §4.2.

The separate `data/baselines/v0/` snapshot (2026-10-08, six runs, seed 42, tag
`v0-baseline`) predates that wiring; its README records that ADAPTIVE received
no traffic and no lease was exercised. It is kept frozen for integrity and is
**not** the source of the tables below.

Scenario B — WAN capacity drop, 100 -> 20 Mbps at t=5 s, 40 s (the case the brief names):

| median of 7 seeds | FIFO | CAKE95 | ACIQ |
|---|---|---|---|
| p50 latency | 81.14 ms | 81.10 ms | **1.20 ms** |
| p95 latency | 91.42 ms | 91.79 ms | 71.31 ms |
| p99 latency | 99.57 ms | 105.41 ms | 97.32 ms |
| jitter | 0.90 ms | 0.86 ms | 0.73 ms |
| loss | 0.60 % | 0.45 % | **0.10 %** |

Scenario A — ISO download during a video call, flat 100 Mbps, 30 s:

| median of 7 seeds | FIFO | CAKE95 | ACIQ |
|---|---|---|---|
| p50 | 102.79 ms | 0.264 ms | 0.295 ms |
| p95 | 119.32 ms | 0.384 ms | 0.395 ms |
| jitter | 0.582 ms | 0.060 ms | 0.042 ms |

Scenario C — three TVs streaming plus gaming, flat 100 Mbps, 40 s:

| median of 7 seeds | FIFO | CAKE95 | ACIQ |
|---|---|---|---|
| p50 | 0.468 ms | 0.472 ms | 0.450 ms |
| p95 | 2.576 ms | 0.563 ms | 0.540 ms |
| jitter | 0.546 ms | 0.092 ms | 0.092 ms |
| video goodput (3 streams) | 14.31 Mbps | 14.28 Mbps | 14.30 Mbps |

Paired Wilcoxon (exact, by seed):

- **vs FIFO:** 8 of 10 latency/jitter/loss comparisons reach p < 0.05. The
  median latency advantage is large and reproducible.
- **vs CAKE95:** not established on p99 (p = 0.078). On Scenario A, CAKE is
  statistically indistinguishable on median (p = 0.1094) and p95 (p = 0.7812).
- **p99 is not established anywhere.** Reporting only the median is the failure
  the verification harness exists to catch.

Sources:

- Scenario A: `data/host_gate_s1_{aciq,b0_fifo,b1_cake95}/` (7 seeds each,
  `REVISION c5da3fd9`).
- Scenario B: `data/host_gate_congested_{aciq,b0_fifo,b1_cake95}/`; re-derivation
  in `docs/gap-closure/reconciliation-congested.json`.
- Scenario C: `data/host_gate_{aciq,b0_fifo,b1_cake95}/`.
- Frozen pre-wiring snapshot (not used above): `data/baselines/v0/` (integrity:
  `sha256sum -c SHA256SUMS`).

### 4.2 The round-3 adaptive controller (DEV band, seeds 1000–1009)

Ten shapes × ten seeds = **100 judged runs**, 2026-11-01 12:15–17:22
(306 min), engine commit `19e9e8a5`.

| Shape | Call p95 (ms) | Jitter (ms) | Loss (%) | Gate |
|---|---|---|---|---|---|
| `s2b_step_50` | 14.20 ± 4.07 | 0.53 | 0.005 | 9 / 10 |
| `s2b_step_10` | 77.47 ± 1.95 | 0.97 | 0.175 | 10 / 10 |
| `s2b_step_up_20to100` | 8.16 ± 5.44 | 0.35 | 0.007 | 10 / 10 |
| `s2b_ramp_100to30` | 36.41 ± 9.22 | 0.56 | 0.000 | 7 / 10 |
| `s7_up_20to60` | 9.96 ± 2.88 | 0.47 | 0.007 | 10 / 10 |
| `s7_up_30to100` | 11.37 ± 4.77 | 0.39 | 0.003 | 10 / 10 |
| `s7_rampup_30to100` | 10.40 ± 3.94 | 0.43 | 0.007 | 10 / 10 |
| `s7_down_100to15` | 59.79 ± 6.28 | 0.79 | 0.045 | 10 / 10 |
| `s7_down_100to8` | 80.62 ± 1.23 | 1.33 | 0.440 | 10 / 10 |
| `s3_stress` | game p95 18.36 ± 3.20 | — | — | 10 / 10 |

Mean ± 95 % CI over 10 seeds (t(9) = 2.262). The gate judges landing and climb,
not latency; the latency columns are reported as measured. Full per-seed and
per-arm tables (ACI vs CAKE-conservative vs CAKE-adaptive):
[`data/experiments/RESULTS_DEV3.md`](data/experiments/RESULTS_DEV3.md).

**The four misses, and the fix.** All four were root-caused from per-tick
artefacts, declared in
[`docs/evidence/round3-params.md`](docs/evidence/round3-params.md), implemented,
and tested before the confirming re-run:

| Miss | Root cause | Fix in `1ee8e57d` |
|---|---|---|
| `s2b_ramp_100to30` seeds 1001, 1007 (10.4 s vs 8.0 s) | 10 % ratchet + 5 s dwell: two commits after the ramp end; the one-commit landing was refused by the dwell and its intent discarded | wire-drop evidence now permits a full lawful (25 %) step |
| `s2b_ramp_100to30` seed 1003 (11.4 s) | landed 29.17 at 29.83 s, 0.17 s *before* the nominal ramp end; a strict `t > ramp_end` judge discarded it | a pre-end landing inside the band counts at `0.0 s` |
| `s2b_step_50` seed 1008 (9.4 s) | the overshoot branch landed on the instantaneous 55.90 Mbps (band 55.0), not the 4 s carried 52.40 | drain-signature overshoot lands on `recent_delivered_min` |

The new judge re-scores the old artefacts as **97 / 100** — only seed 1003 is
rescued by the definition change; the other three genuinely needed the
controller fixes. That separation is deliberate: a definition change is not
allowed to launder a controller failure.

> **Status of the re-run.** The full DEV band was re-launched on the fixed tree
> at 19:31 on 2026-11-01 (all markers cleared, so every cell runs on one
> commit). Its verdict lands in
> [`data/live_status_round3/dev_verify.log`](data/live_status_round3/dev_verify.log);
> per-cell progress is the set of `dev_cell_*.done` markers. The final band has
> **not** run, and no final-band number appears anywhere in this repository.

### 4.3 Lease — the measured benefit

On a 10 Mbps capped link, with one address per device (so classification is not
accidental), a lease for one device's flows:

| seed | leased device, no lease | leased | change | parent ceiling |
|---|---|---|---|---|
| 42 | 17.99 MB | 23.05 MB | +28.14 % | 10.19 / 10.07 |
| 43 | 17.96 MB | 23.00 MB | +28.08 % | 10.15 / 10.11 |
| 44 | 17.99 MB | 23.05 MB | +28.16 % | 10.08 / 10.10 |
| 45 | 17.93 MB | 23.11 MB | +28.92 % | 10.08 / 10.11 |
| 46 | 18.00 MB | 23.05 MB | +28.08 % | 10.06 / 10.10 |
| 47 | 18.00 MB | 23.06 MB | +28.08 % | 10.05 / 10.04 |
| 48 | 18.00 MB | 22.94 MB | +27.46 % | 10.08 / 10.07 |

Mean **+28.13 %**, exact paired Wilcoxon **p = 0.015625** (7/7 in the same
direction — the minimum reachable p for seven pairs). The three-device total
moves **−0.10 %**: the link redistributes, it does not add. The parent ceiling
held at **10.04–10.19 Mbps** across all fourteen runs, measured by the senders
rather than by our own class accounting.

Honest caveat: the plan came from the requested drop, not from M2, so this
demonstrates the **lease mechanism on a correct plan**, not adaptation.

Source: [`docs/limitations.md`](docs/limitations.md) §lease.

### 4.4 Capacity estimator

Replaying a recorded run through the revised estimator (counters only):

```
100 → 45.97 → 24.38 → 15.41 → 12.15 → 10.86 Mbps   (truth 10 Mbps)
```

Monotone, no collapse. On live round-3 shapes the applied rate tracks the new
truth after the drop (e.g. `s7_down_100to8` post-drop tree 7.90 vs 8.0 Mbps).
The estimator's caveats are structural, not tuning: it can only see a
bottleneck the router is on, and it learns nothing from an idle link
(confidence decays rather than holding a stale value). Both are in
[`docs/limitations.md`](docs/limitations.md).

### 4.5 Overhead and stability (earlier phase)

| | |
|---|---|
| Controller CPU, 30.8-min soak | 0.00493 of a core median, 0.00580 peak |
| Policy changes during that soak | 8 in 1851 s |
| Rollback against a real failing `tc` | 6 / 6 |
| Per-flow fairness within a class | two flows within ~1 % |
| Headroom retained on a 20 Mbps link | 17.30 of 20 Mbps (86 %) |

Source: [`docs/PROJECT_REPORT.md`](docs/PROJECT_REPORT.md).

### 4.6 Where every number comes from

| Number | Produced by | Stored in |
|---|---|---|
| Gate 20 PASS / 1 MEASURED | `testbed/gate.sh` | `data/live_status_round3/dev_gate.log` |
| 1578 tests, 0 failed | `python3 -m unittest discover -s tests -t .` | terminal / `artifacts/validation/` |
| DEV verdict 96/100 | `tools/verify_round3.py data/runs_dev3` | `data/live_status_round3/dev_verify.log` |
| Per-shape means ± CI | `tools/build_report.py` over `data/runs_dev3` | `data/experiments/RESULTS_DEV3.md` |
| 7-seed latency medians (A/B/C) | workload-measured `call.json` / `game.json`, median over seeds | `data/host_gate_*` (revision `c5da3fd9`) |
| Scenario B re-derivation | `tools/reconcile_results.py` over `data/host_gate_congested_*` | `docs/gap-closure/reconciliation-congested.json` |
| Lease +28.13 %, p = 0.015625 | paired sender totals, sign-enumeration Wilcoxon | `docs/limitations.md` §lease |
| Estimator replay | recorded run, replayed through `aciq/capacity.py` | `docs/PROJECT.md`, `docs/PROJECT_REPORT.md` |
| Root causes of the four misses | per-tick `decisions` + `policy_change_log` | `docs/evidence/round3-params.md` |

---

## 5. The round-3 verdict rule

[`tools/verify_round3.py`](tools/verify_round3.py) is the authority. It reads
each run's `decisions`/`policy_change_log` and the link truth, and prints
PASS/FAIL. Prose may not improve on it.

| Check | Definition |
|---|---|
| Down-step | one commit lands at or below `1.10 × max(drop, floor)` within **8.0 s** of the drop, and delivered ≥ 0.50 × legal afterwards |
| Ramp-down | same band, measured against the instantaneous ramp truth; a landing inside the band just before the nominal ramp end counts at its own tick |
| Up-step | over the final third: applied ≥ **0.60 × truth** and delivered ≥ **0.50 × truth** |
| Stress | at least one commit, and last-third delivered/applied ≥ 0.50; no rate claim is made during pure saturation |

Floor totals: 100 Mbps → 35.0; 50 → 17.5; 30/15/8 → 14.0. The constants
(`BIND_TOL = 0.10`, `EMERGENCY_COMMIT_LIMIT_S = 8.0`,
`UP_UTIL_APPLIED_MIN = 0.60`, `UP_UTIL_DELIVERED_MIN = 0.50`) are frozen at the
top of the verifier.

The verifier prints a final line such as:

```
verify_round3 FAILED: 2 judged FAIL, 88 PASS of 90 -- 0 skips: every shape is judged
```

A band is green only when that line reports `0 judged FAIL` over the full
100-cell ACIQ set.

---

## 6. Reproducing every number

Requires Linux with `iproute2`, `python3` (≥ 3.11) and root for the testbed. The
unit suite needs neither root nor `tc`.

```bash
# unit / integration tests (1578; 10 live-kernel tests skip without iproute2)
python3 -m unittest discover -s tests -t .

# lint
./tools/lint.sh

# testbed gate (needs root): 21 checks, 20 PASS + 1 MEASURED
sudo ./testbed/gate.sh

# bring the namespaces up, then tear them down
sudo ./testbed/setup.sh
sudo ./testbed/cleanup.sh

# round-3 DEV band (resumable; ~5 h). Markers live in data/live_status_round3/
sudo ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_round3_batch.sh dev

# the one-shot final band (seeds 1100-1109; run once, never re-tuned)
sudo ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_round3_batch.sh final

# judge a band
python3 tools/verify_round3.py data/runs_dev3

# regenerate the per-scenario report
python3 tools/build_report.py --runs-root data/runs_dev3 --out data/experiments/RESULTS_DEV3.md

# intent API + dashboard on :8080
sudo python3 aciqctl serve --port 8080

# render a dashboard from an existing run, no server needed
python3 aciqctl dashboard \
  --samples data/baselines/v0/runs/s1_iso_during_call__aciq__adaptive__seed42/samples.jsonl \
  --out dashboard.html --refresh 5
```

The batch runner skips any cell whose `.done` marker exists. To force a cell to
re-run, delete its marker (and, if the namespaces were torn down, the
`gate`/`reset_hub`/`setup_ub`/`cleanup_ub` markers too). A hung cell is bounded
by `timeout --foreground --kill-after=60s` at 3× its estimate.

The legacy brief-scenario runner is still present:

```bash
sudo python3 run_experiments.py \
  --scenario s1_iso_during_call --scenario s2_wan_drop \
  --scenario s3_tv_and_gaming --enforce --seeds 6 --drop 20 --drop-at 20 \
  --results-dir data/matrix6 --report data/matrix6/REPORT.md
```

---

## 7. Repository layout

```
aciq/                 the system
  classify.py   M1    DSCP + behaviour → class, confidence, evidence
  flowtrack.py  M1    conntrack parsing and per-flow behaviour
  capacity.py   M2    capacity from queue counters only
  policy.py     M3    shares, floors, lease maths (pure function)
  ratecap.py          the rate law (steps, dwell, severe landing, probe)
  tc.py         M4    declarative qdisc tree, render, read-back verify
  shield.py     M9    veto rules, fault modes, backoff
  txn.py        M9    snapshot, apply, verify, rollback, safe state
  metrics.py    M5    counters → rates, percentiles, fairness, CPU
  harness.py    M6    closed loop, baselines, capacity variants
  experiment.py M6    run sequencing and artefacts
  report.py     M10   Markdown report with per-percentile verdicts
aciqctl               M7/M8  intent API + dashboard
tests/                1578 tests; live-kernel ones skip without iproute2
testbed/              namespaces, gate, workloads, round-3 batch runner
tools/                verifier, reports, analysis, claim audit
docs/                 design, evidence, gap closure, limitations
data/
  baselines/v0/       frozen measured snapshot (tag v0-baseline)
  runs_dev3/          round-3 DEV artefacts, one directory per run
  runs_final3/        final-band artefacts (not yet produced)
  live_status_round3/ batch resume markers and logs
reports/              generated evaluation reports
artifacts/            validation manifests and logs
```

---

## 8. Provenance and the retune discipline

- Every run directory carries `config.json` and `result.json`; the latter records
  `commit_hash`, so a number can be traced to the code that produced it.
- `data/experiments/RESULTS_DEV3.md` is generated from the run artefacts, not
  from hand-written tables, and stamps the engine commit per section.
- `docs/evidence/round3-params.md` declares every constant and every retune
  **before** the run it applies to, including the failed attempts.
- `tools/verify_round3.py` re-derives verdicts from raw artefacts; the current
  judge is applied to old artefacts to show exactly what a definition change
  rescues and what it does not (97/100, one rescued seed).
- `docs/gap-closure/claim-audit.json` and `tools/audit_claims.py` check prose
  against evidence.
- Frozen baseline integrity: `cd data/baselines/v0 && sha256sum -c SHA256SUMS`.

A retune that is not declared before its run is not a retune; it is a result
chosen after seeing the data. The declaration files are in `docs/evidence/`.

---

## 9. Known limitations

Stated before the results, so none of them is an excuse made afterwards. Full
list with measurements: [`docs/limitations.md`](docs/limitations.md).

1. **The emulated link is not a real link.** The bottleneck is an HTB class, not
   DSL/cable access hardware. It models rate shaping, not ISP policing or modem
   behaviour.
2. **The estimator cannot see a bottleneck it is not on.** In a real home the
   bottleneck is usually the modem or the ISP side, where router counters show
   nothing. This is the most important limitation. A validated probe remedy
   exists but is not in the MVP.
3. **Passive estimation needs a busy link.** Idle means `n/a`, not a guess.
4. **Classification is measured on self-generated traffic.** The known-hard case
   is UDP/443 carrying both video calls and downloads; ambiguity is reported as
   UNCLASSIFIED rather than guessed.
5. **Identity is source IP only.** Reusing an address transfers privilege; this
   is a documented deployment assumption, not a solved problem.
6. **Jain fairness is per class**, not per flow.
7. **The final acceptance band has not run.** Until it does, the round-3
   controller result is a DEV-band result and is labelled as such.
8. **p99 is not established** in any ACIQ-vs-CAKE comparison.

---

## 10. FAQ — reading the results without being misled

**Is ACIQ better than CAKE?**
Not established. It removes pfifo bufferbloat and wins the median under a
capacity drop; against a tuned CAKE the tests do not separate it except on
specific metrics, and p99 is not significant anywhere.

**Why is the call p95 77 ms on `s2b_step_10`?**
Because on a 10 Mbps link the call is not protected by a reserved EF lane the
way the brief's scenario protects it; the gate judges the controller's landing,
and the latency is reported as it was measured. Hiding it would be dishonest.

**Why 96/100 and not 100?**
Four cells failed on the first complete band. Each was traced to a mechanism,
fixed, and covered by tests; the confirming re-run is in progress. The fixes
were declared before the run, and the judge change alone rescues only one seed.

**Why are the A/B/C tables labelled “pre-round-3” and not “adaptive controller”?**
Because they are the 7-seed stack at `c5da3fd9`, before the round-3 rate law. The
classifier is wired there (ADAPTIVE carries the video traffic), but the
controller is the older one. The round-3 controller's own results are §4.2, and
the separate frozen `v0` snapshot (which *did* predate the wiring) is kept only
for integrity and is not the source of these tables.

**What does “PASS” mean?**
It means `tools/verify_round3.py` printed PASS for that run: the applied rate
landed inside the declared band within the declared time, or climbed to the
declared utilisation. It does not mean “low latency” or “good user experience”.

**What is the final band?**
Seeds 1100–1109, one run per cell, executed once on a frozen constant set after
the DEV band is green. It has not been run. No final-band number exists yet.

**Can I trust a number in this file?**
Each one is mapped to a file in §4.6. If a number has no file behind it, it does
not belong here.

---

## 11. Documentation

| | |
|---|---|
| [`docs/PROJECT.md`](docs/PROJECT.md) | complete reference: modules, contracts, measurements, defects |
| [`docs/architecture.md`](docs/architecture.md) | design and per-module contracts |
| [`docs/limitations.md`](docs/limitations.md) | every measurement, withdrawn claim and open defect |
| [`docs/FIX_REPORT.md`](docs/FIX_REPORT.md) | round-3 failures, root causes and fixes |
| [`docs/evidence/round3-params.md`](docs/evidence/round3-params.md) | declared constants and every retune, with the evidence that forced it |
| [`docs/evidence/round3-diagnosis.md`](docs/evidence/round3-diagnosis.md) | pre-fix diagnosis of the declared failures |
| [`docs/gap-closure/final-validation-report.md`](docs/gap-closure/final-validation-report.md) | what is verified, what is blocked, and why |
| [`docs/gap-closure/device-identity-and-leases.md`](docs/gap-closure/device-identity-and-leases.md) | the lease measurement |
| [`docs/gap-closure/api-security-validation.md`](docs/gap-closure/api-security-validation.md) | token auth, bind policy, rate limit, audit |
| [`docs/WIRING_AUDIT.md`](docs/WIRING_AUDIT.md) | how each flow reaches its class, and the traps |
| [`docs/ACIQ_EXPLAINED.md`](docs/ACIQ_EXPLAINED.md) | plain-language walkthrough |
| [`docs/REQUIREMENT_TRACEABILITY.md`](docs/REQUIREMENT_TRACEABILITY.md) | brief requirement → code → evidence |
| [`docs/setup.md`](docs/setup.md) | standing the testbed up from scratch |
| [`docs/licenses.md`](docs/licenses.md) | dependency inventory |

---

## 12. Licence

MIT — see [`LICENSE`](LICENSE). No third-party source is vendored.
