# ACIQ — Adaptive Classification & Intent-aware QoS

> **Case Study 3 — Adaptive QoS Engine for Mixed Home Broadband Traffic**
> (TATA ELXSI / TELIPORT)

ACIQ is a traffic controller for a home broadband link. It classifies flows
without reading payload, estimates the link's real capacity from queue
counters only, shares bandwidth between classes with guaranteed floors, and can
grant a user a time-boxed **lease** to one device. This repository contains the
controller, the kernel enforcement layer, the testbed, the measurement
pipeline, and every artefact behind every number quoted below.

This README is deliberately split into **what is verified**, **what is
measured but not yet proven**, and **what is not done**. Where a result is
weaker than it looks, the weakness is stated next to the number.

**Snapshot: 2026-11-01, commit `1ee8e57d`.**

| | |
|---|---|
| Kernel enforcement (HTB, DSCP steering, per-flow filters, IPv4 + IPv6, teardown) | **verified** — testbed gate 20 PASS + 1 MEASURED, 0 FAIL |
| Controller verdicts, round-3 DEV band (seeds 1000–1009, 10 shapes × 10 seeds) | **96 / 100 PASS, 0 SKIP** at `19e9e8a5`; the 4 misses are diagnosed and fixed in `1ee8e57d`, confirming re-run is the next step |
| Final acceptance band (seeds 1100–1109) | **not run** — gated on the DEV verdict and a frozen constant set |
| Unit / integration tests | **1565 run, 0 failed, 10 skipped** (live-kernel tests that need `iproute2`) |
| Lease benefit, 7 paired seeds | **+27.46 % to +28.92 %, mean +28.13 %**, exact paired Wilcoxon **p = 0.015625** |
| Superiority over a tuned CAKE | **not established**, and not claimed |

---

## Contents

1. [What this is](#1-what-this-is)
2. [What is verified, and what is not](#2-what-is-verified-and-what-is-not)
3. [How the controller works](#3-how-the-controller-works)
4. [Measured results](#4-measured-results)
5. [What the round-3 gate checks](#5-what-the-round-3-gate-checks)
6. [Running it](#6-running-it)
7. [Repository layout](#7-repository-layout)
8. [Provenance and reproducibility](#8-provenance-and-reproducibility)
9. [Known limitations](#9-known-limitations)
10. [Documentation](#10-documentation)
11. [Licence](#11-licence)

---

## 1. What this is

A Linux home-router data path:

```
 traffic ──► M1 classify ──► M2 estimate capacity ──► M3 plan ──► M9 shield ──► M4 tc
             (DSCP +          (queue counters        (shares,       (veto,        (HTB +
              behaviour)       only)                  floors,        rollback)     fq_codel)
                                                        leases)
```

- **M1 classifier** — DSCP and per-flow behaviour, never payload. Each decision
  carries a class, a confidence and its evidence.
- **M2 capacity estimator** — reads queue counters from the router. Its input
  type has no `configured_mbps` field, so it cannot read the shaper's rate even
  by accident.
- **M3 policy** — a pure function: per-class rates, floors and lease weights,
  with the invariant `Σ rates ≤ capacity`.
- **M4 enforcement** — renders an HTB + `fq_codel` tree and verifies it by
  reading the kernel back.
- **M9 shield / transaction** — veto rules, snapshot, apply, read-back verify,
  rollback, and an escalating safe state.
- **M5–M10** — metrics, harness, intent API (`aciqctl`), dashboard, experiment
  runner, report generator.

The testbed is three network namespaces (`router`, `client`, `wan`) joined
by veth pairs. The slow line is an **HTB class** —
a token-bucket shaper. `netem` supplies delay and loss only, never bandwidth:
pretending a bandwidth shaper is `netem` would misrepresent what is emulated.

---

## 2. What is verified, and what is not

| Claim | State | Evidence |
|---|---|---|
| Per-flow enforcement, IPv4 and IPv6 | **verified on a kernel** | `testbed/gate.sh` checks 11/13/16/18; `data/live_status_round3/dev_gate.log` |
| DSCP-EF claim rejected below capacity | **verified on a kernel** | gate checks 14 and 17 |
| IPv6 petal/steering path | **verified for filters and routes** | gate checks 13/18; classification wiring is IPv4-only |
| Capacity drop enforced, no over-subscription | **verified on a kernel** | `docs/gap-closure/capacity-drop-collision.md`, `live-enforcement-validation.md` |
| Lease lifecycle and measured benefit | **verified on a kernel**, p = 0.015625 | `docs/limitations.md` §lease, `docs/gap-closure/device-identity-and-leases.md` |
| Controller landing / climb verdicts | **96/100 PASS on DEV**; final band pending | `data/experiments/RESULTS_DEV3.md`, `data/live_status_round3/dev_verify.log` |
| Capacity estimation, replay | **verified offline** | 100 → 45.97 → 24.38 → 15.41 → 12.15 → 10.86 Mbps against truth 10 |
| Capacity estimation, end to end | **exercised live in round 3, not yet frozen** | applied tracks truth on the down shapes; final band pending |
| Rollback against a real failing `tc` | **6 / 6** (earlier phase) | `docs/PROJECT_REPORT.md` |
| Long-run stability | **1851 s, 8 policy changes** (earlier phase) | `docs/PROJECT_REPORT.md` |
| Better than a well-tuned CAKE | **not established** | paired tests below; reported as “not significant” |
| Device identity beyond source IP | **not built** — IP-only identity, documented as a deployment assumption | `docs/gap-closure/final-validation-report.md` §C P1-002 |
| Per-flow (intra-class) fairness surface | **not built** — Jain is per class | `docs/gap-closure/final-validation-report.md` §C P1-005 |
| Soak / memory scaling | **not measured** | `docs/gap-closure/final-validation-report.md` §C P2-002 |

**Nothing blocked is reported as passed.** The distinction between “tested
offline”, “run on a kernel” and “frozen verdict” is kept everywhere in this
repository.

---

## 3. How the controller works

The controller is a **law plus evidence**, not a set of tuned magic numbers.
Every constant is declared in `docs/evidence/round3-params.md` *before* the run
it applies to, and the verifier, not prose, decides PASS/FAIL.

The law (`aciq/ratecap.py`, mirrored by `tools/verify_round3.py`):

| Rule | Value |
|---|---|
| Maximum rate change per commit | 25 % of applied (`MAX_RATE_STEP_FRAC`) |
| Minimum dwell between commits | 5 s (`MIN_DWELL_S`) |
| Emergency descent | 2× the normal step, up to 500 Mbps/s (`EMERGENCY_STEP_MULT`, `EMERGENCY_DROP_RATE_PER_S`) |
| Per-class floor | `max(2 Mbps, 5 % of capacity)`; scaled down with `degraded=True` if the link cannot honour it |
| Down-step legal target | `max(drop_mbps, floor_total)` |
| Down-step acceptance band | 1.10 × legal |
| Climb acceptance | applied ≥ 0.60 × truth **and** delivered ≥ 0.50 × truth over the final third |

Two mechanisms matter for the round-3 work:

- **Severe-drop landing** — when the belief is saturated and has fallen through
  0.9 × applied, the controller commits the whole lawful drop in *one* commit
  instead of walking down 25 % at a time. The landing is still a real kernel
  change, still bounded, still rollback-able.
- **Demand probe** — an up-step cannot be discovered from a saturated link, so
  the controller pierces +25 % for one hold window when the tree is seen
  overlimiting, then lands back on `min(known_good, delivered)` if the wire
  inflates. The pierce gate is the tree's own overlimit counter, not a timer.

### The round-3 shape set

| Shape (10 seeds each) | Protocol | What it tests |
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
| `s3_stress` | flat 100; game + 3 video + bulk background, 40 s | demand > capacity; no enforcement claim by design |

---

## 4. Measured results

### 4.1 The frozen enforcement baseline (v0 snapshot, 2026-10-08)

Seven paired seeds (42–48), three systems, on a kernel. **Read the caveat
before quoting this table.** The frozen snapshot's runtime chain was
**DSCP-EF filtering → HTB → `fq_codel`**; the behavioural classifier and the
flow tracker were tested but *not in the import chain*, ADAPTIVE received no
traffic, and no lease was exercised. The numbers therefore measure the
**enforcement primitives**, not the adaptive controller. That distinction is
recorded in `data/baselines/v0/README.md` and is not softened here.

Scenario B — WAN capacity drop, 100 → 20 Mbps (the case the brief names):

| median of 7 seeds | FIFO | CAKE95 | ACIQ stack |
|---|---|---|---|
| p50 latency | 81.14 ms | 81.10 ms | **1.20 ms** |
| p95 latency | 91.42 ms | 91.79 ms | 71.31 ms |
| p99 latency | 99.57 ms | 105.41 ms | 97.32 ms |
| jitter | 0.90 ms | 0.86 ms | 0.73 ms |
| loss | 0.60 % | 0.45 % | **0.10 %** |

Scenario A — ISO download during a video call:

| median of 7 seeds | FIFO | CAKE95 | ACIQ stack |
|---|---|---|---|
| p50 | 102.79 ms | 0.264 ms | 0.295 ms |
| p95 | 119.32 ms | 0.384 ms | 0.395 ms |
| jitter | 0.582 ms | 0.060 ms | 0.042 ms |

Scenario C — three TVs streaming plus gaming:

| median of 7 seeds | FIFO | CAKE95 | ACIQ stack |
|---|---|---|---|
| p50 | 0.468 ms | 0.472 ms | 0.450 ms |
| p95 | 2.576 ms | 0.563 ms | 0.540 ms |
| jitter | 0.546 ms | 0.092 ms | 0.092 ms |

Paired Wilcoxon (exact, by seed):

- **vs FIFO:** 8 of 10 metric comparisons reach p < 0.05. The median advantage
  is large and reproducible.
- **vs CAKE95:** not established on p99 (p = 0.078). On Scenario A, CAKE is
  statistically indistinguishable on median (p = 0.1094) and p95 (p = 0.7812).
- **p99 is not established anywhere.** Reporting only the median is the failure
  the verification harness exists to catch.

Raw data: `data/baselines/v0/` (integrity: `sha256sum -c SHA256SUMS`),
`docs/gap-closure/reconciliation-congested.json`.

### 4.2 The round-3 adaptive controller (DEV band, seeds 1000–1009)

Ten shapes × ten seeds = **100 judged runs**, 2026-11-01 12:15–17:22
(306 min), engine commit `19e9e8a5`. Delivered throughput is the **receiver's**
sink total; the post-drop column is the **tree counter** and is a different
instrument (run-mean vs post-drop, never blended).

| Shape | Call p95 (ms) | Jitter (ms) | Loss (%) | Bulk delivered, run mean (Mbps) | Post-drop tree (Mbps) | Gate |
|---|---|---|---|---|---|---|
| `s2b_step_50` | 14.20 ± 4.07 | 0.53 | 0.005 | 49.46 ± 0.82 | 39.49 ± 0.80 | 9 / 10 |
| `s2b_step_10` | 77.47 ± 1.95 | 0.97 | 0.175 | 27.21 ± 0.69 | 8.54 ± 0.17 | 10 / 10 |
| `s2b_step_up_20to100` | 8.16 ± 5.44 | 0.35 | 0.007 | 45.24 ± 0.79 | 51.54 ± 1.40 | 10 / 10 |
| `s2b_ramp_100to30` | 36.41 ± 9.22 | 0.56 | 0.000 | 46.32 ± 0.66 | — | 7 / 10 |
| `s7_up_20to60` | 9.96 ± 2.88 | 0.47 | 0.007 | 35.03 ± 1.87 | 38.82 ± 1.92 | 10 / 10 |
| `s7_up_30to100` | 11.37 ± 4.77 | 0.39 | 0.003 | 56.66 ± 1.52 | 64.38 ± 2.64 | 10 / 10 |
| `s7_rampup_30to100` | 10.40 ± 3.94 | 0.43 | 0.007 | 56.03 ± 1.24 | — | 10 / 10 |
| `s7_down_100to15` | 59.79 ± 6.28 | 0.79 | 0.045 | 30.70 ± 0.60 | 13.18 ± 0.37 | 10 / 10 |
| `s7_down_100to8` | 80.62 ± 1.23 | 1.33 | 0.440 | 26.71 ± 0.40 | 7.90 ± 0.12 | 10 / 10 |
| `s3_stress` | game p95 18.36 ± 3.20 | — | — | 71.46 ± 2.44 | — | 10 / 10 |

Mean ± 95 % CI over 10 seeds. The gate judges landing and climb, not
latency; the latency columns are reported as measured. Full per-seed and
per-arm tables (ACI vs CAKE-conservative vs CAKE-adaptive):
`data/experiments/RESULTS_DEV3.md`.

**The four misses, and the fix.** All four were root-caused from per-tick
artefacts, declared in `docs/evidence/round3-params.md`, implemented, and
tested before the confirming re-run:

| Miss | Root cause | Fix in `1ee8e57d` |
|---|---|---|
| `s2b_ramp_100to30` seeds 1001, 1007 (10.4 s vs 8.0 s) | 10 % ratchet + 5 s dwell: two commits after the ramp end; the one-commit landing was refused by the dwell and its intent discarded | wire-drop evidence now permits a full lawful (25 %) step |
| `s2b_ramp_100to30` seed 1003 (11.4 s) | landed 29.17 at 29.83 s, 0.17 s *before* the nominal ramp end; a strict `t > ramp_end` judge discarded it | a pre-end landing inside the band counts as 0.0 s |
| `s2b_step_50` seed 1008 (9.4 s) | overshoot branch landed on the instantaneous 55.90 Mbps (band 55.0), not the 4 s carried 52.40 | drain-signature overshoot lands on `recent_delivered_min` |

The new judge re-scores the old artefacts as **97 / 100** — only seed 1003 is
rescued by the definition change; the other three genuinely needed the
controller fixes. That separation is the point: definitions are not allowed to
launder failures.

> **Status:** the confirming DEV re-run has not started at the time of writing.
> The final band has **not** run, and no final-band number appears anywhere in
> this repository.

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

### 4.4 Capacity estimator

Replaying a recorded run through the revised estimator (counters only):

```
100 → 45.97 → 24.38 → 15.41 → 12.15 → 10.86 Mbps   (truth 10 Mbps)
```

Monotone, no collapse. On live round-3 shapes the applied rate tracks the new
truth after the drop (e.g. `s7_down_100to8` post-drop tree 7.90 vs 8.0 Mbps).
Estimator caveats are structural, not tuning: it can only see a bottleneck the
router is on, and it learns nothing from an idle link (confidence decays rather
than holding a stale value). Both are in `docs/limitations.md`.

### 4.5 Overhead and stability (earlier phase)

| | |
|---|---|
| Controller CPU, 30.8-min soak | 0.00493 of a core median, 0.00580 peak |
| Policy changes during that soak | 8 in 1851 s |
| Rollback against a real failing `tc` | 6 / 6 |
| Per-flow fairness within a class | two flows within ~1 % |
| Headroom retained on a 20 Mbps link | 17.30 of 20 Mbps (86 %) |

Source: `docs/PROJECT_REPORT.md`.

---

## 5. What the round-3 gate checks

`tools/verify_round3.py` is the authority. It reads each run's
`decisions`/`policy_change_log` and the link truth, and prints PASS/FAIL. Prose
may not improve on it.

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

---

## 6. Running it

Requires Linux with `iproute2`, `python3` (≥ 3.11) and root for the testbed.
The unit suite needs neither root nor `tc`.

```bash
# unit / integration tests (1565; 10 live-kernel tests skip without iproute2)
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

The batch runner skips any cell whose `.done` marker exists. To force a cell
to re-run, delete its marker (and, if the namespaces were torn down, the
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
tests/                1565 tests; live-kernel ones skip without iproute2
testbed/              namespaces, gate, workloads, round-3 batch runner
tools/                verifier, reports, analysis, claim audit
docs/                 design, evidence, gap closure, limitations
data/
  baselines/v0/       frozen measured snapshot (tag v0-baseline)
  runs_dev3/          round-3 DEV artefacts, one directory per run
  runs_final3/        final-band artefacts (not yet produced)
  live_status_round3/ batch resume markers and logs
reports/              generated evaluation reports
```

---

## 8. Provenance and reproducibility

- Every run directory carries `config.json` and `result.json`; the latter
  records `commit_hash`, so a number can be traced to the code that produced it.
- `data/experiments/RESULTS_DEV3.md` is generated from the run artefacts, not
  from hand-written tables, and stamps the engine commit per section.
- `docs/evidence/round3-params.md` declares every constant and every retune
  **before** the run it applies to, including the failed attempts.
- `tools/verify_round3.py` re-derives verdicts from raw artefacts; the new judge
  is applied to old artefacts to show what changed and what did not.
- `docs/gap-closure/claim-audit.json` and `tools/audit_claims.py` check prose
  against evidence.
- Frozen baseline integrity: `cd data/baselines/v0 && sha256sum -c SHA256SUMS`.

Repository: <https://github.com/karneish/ACIQ-TATA-ELXSI>

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

## 10. Documentation

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
| [`docs/WIRING_AUDIT.md`](docs/WIRING_AUDIT.md) | how each flow reaches its class, and the traps |
| [`docs/ACIQ_EXPLAINED.md`](docs/ACIQ_EXPLAINED.md) | plain-language walkthrough |
| [`docs/REQUIREMENT_TRACEABILITY.md`](docs/REQUIREMENT_TRACEABILITY.md) | brief requirement → code → evidence |
| [`docs/setup.md`](docs/setup.md) | standing the testbed up from scratch |
| [`docs/licenses.md`](docs/licenses.md) | dependency inventory |

---

## 11. Licence

MIT — see [`LICENSE`](LICENSE). No third-party source is vendored.
