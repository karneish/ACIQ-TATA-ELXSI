# Defect register

Machine-readable: `defect-register.json` (same directory).
Every entry has an acceptance criterion. **Closed only when the criterion is
met by a test that actually ran** — not by code having been added.

Status values: `open` · `fixed-unit` · `fixed-integration` · `fixed-e2e` ·
`blocked-environment` · `documented-limitation`

---

## Environment constraint (applies to many entries)

**This agent shell has no `ip`, `tc`, `iperf3`, `nc` or `ping` on any path, and
no `sudo`.** Verified: `/usr/sbin`, `/sbin` are listable but contain none of
them; `sudo` is absent. The user shell has all of them and has run the gate
successfully.

Consequence: **every kernel-integrated, gate and end-to-end test is
`blocked-environment` from this shell.** The harnesses are implemented, the
commands are recorded, and the results are reported as blocked — never as
passed. See `baseline-audit.md` for the capture.

---

## P0-001 — Latency, jitter and loss are hardcoded to zero

**Severity:** P0 — misleading measurement of the system's primary output.

**Requirement:** §5.1, §3.3 ("Never hardcode zero for an unavailable metric").

**Files:** `aciq/metrics.py:340-349` (`ClassMetrics`), `aciq/metrics.py:405-411`
(`MetricsCollector.poll`).

**Reproduction:** run any experiment, read `samples.jsonl`; `rtt_p95`,
`jitter_ms` and `loss_ratio` are `0.0` on every line, for every class, in every
run in `data/`. Verified across `matrix6`, `fixcheck`, `dev10`, `ab_lease_42`.

**Root cause:** `ClassMetrics` declares `rtt_p50/p95/p99`, `jitter_ms` and
`loss_ratio` as `float = 0.0`. There is no validity field, so "not measured" and
"measured zero" are the same value. The dashboard then padded a flat-zero series
symmetrically and labelled **negative latency**.

**Acceptance:** no unavailable metric is ever represented as `0.0`; validity is
explicit; dashboard and report expose it; ≥1 real kernel-integrated test
produces valid measurements.

**Status:** `open` — see P0-002/003/004.

---

## P0-002 — Evaluation data is keyed by workload label, read back by class name

**Severity:** P0.

**Files:** `aciq/metrics.py:379` (`ingest` stores `_last_eval[data.label]`) vs
`aciq/metrics.py:405` (`_last_eval.get(cls.value)`).

**Root cause:** two different namespaces. Labels are `call`, `game`, `tv1`,
`tv2`, `tv3`, `bulk`. Class values are `realtime_interactive`,
`adaptive_video`, `bulk_transfer`, `leased_flow`. **The lookup never matches**,
so `ev` is always `None` and the entire evaluation branch is dead code.

This is the direct cause of P0-001.

**Acceptance:** a test that ingests evaluation data and asserts the resulting
`ClassMetrics` carries the values.

**Status:** `open`.

---

## P0-003 — Evaluation data is ingested once, after the run

**Severity:** P0 — there is no live series at all.

**Files:** `aciq/experiment.py:538-550`.

**Root cause:** `self.launcher.collect()` waits for every generator to exit,
then `ingest()` is called once. Even with P0-002 fixed, every row of
`samples.jsonl` would carry the same final value — a step function mislabelled
as a time series.

**Acceptance:** RTT/jitter/loss vary per tick during a run.

**Status:** `open`.

---

## P0-004 — `or` used as a null-coalesce on measurements

**Severity:** P0 — a legitimate measured `0.0` is indistinguishable from
missing.

**Files:** `aciq/metrics.py:410-411`.

```python
m.jitter_ms = ev.jitter_ms or jitter_from_samples(...)   # 0.0 -> recomputed
m.loss_ratio = ev.loss_ratio or 0.0                     # 0.0 -> missing
```

**Acceptance:** explicit `None` checks; a measured zero survives.

**Status:** `open`.

---

## P0-005 — No raw probe observations are exported

**Severity:** P0 — §5.7 requires raw and derived to be stored separately, and
nothing is recomputable from the artefacts.

**Files:** `testbed/workloads/udpx.py` (the probe keeps `_waiting` and
`rtts_ms` in memory), `aciq/experiment.py` (only the summary report is read).

**Root cause:** the probe computes correct per-sequence RTT internally and then
discards the individual samples, keeping only a summary. A summary cannot be
re-derived, re-aggregated, or checked.

**Acceptance:** a machine-readable per-observation stream exists; every derived
figure can be recomputed from it.

**Status:** `open`.

---

## P0-006 — Live capacity-estimation loop unverified

**Severity:** P0 — the central adaptive claim.

**Current state:** the estimator works. It was validated by **replaying a
recorded run** (`data/ab_lease_42`): 100 → 45.97 → 24.38 → 15.41 → 12.15 →
10.86 Mbps against a true capacity of 10. That is not a live experiment and is
not reported as one.

**Two untested paths:** an estimator-triggered rebuild (only *lease* rebuilds
have exercised `_invalidate_enforcer_filters`), and M3 replanning around a
measured 10.86 rather than an exact 10.

**Acceptance:** a live run reporting `estimator_mbps` non-null and
`policy_changes > 0`, with `tc` state captured before and after.

**Status:** `blocked-environment` — command recorded in
`live-adaptation.md`.

---

## P0-007 — Stale capacity estimates in stored runs

**Severity:** P0 — a stored result that misstates the link's state.

**Files:** `data/matrix6/*/result.json` (12 of 18 ACIQ runs).

**Current state:** each such `result.json` carries an explicit staleness note,
so the artefact is honest about itself. **Root cause is not yet established** —
the prompt is right that it must not be papered over by shortening a threshold.

**Status:** `open` — investigation required, not yet done.

---

## P1-001 — Intent API has no authentication or authorisation

**Severity:** P1 — §14.

**Files:** `aciq/api.py`, `aciqctl:cmd_serve`.

**Root cause:** stdlib `http.server`, binds `127.0.0.1` by default, and
`POST /intent` creates a lease with no credential. Currently safe **only**
because the default bind is loopback; nothing enforces that.

**Acceptance:** explicit bind policy enforced; loopback binding refused unless
acknowledged; token auth when non-loopback; size limits; schema validation;
tests.

**Status:** `open`.

---

## P1-002 — Lease identity is an IP address with no binding

**Severity:** P1 — §9.1. DHCP change, IPv6 privacy addresses and address reuse
are all unhandled.

**Current state:** documented as a limitation. The testbed now issues one stable
address per simulated device, which is the right *shape* but not an identity
mechanism.

**Acceptance:** assumptions documented and enforced; stale leases do not transfer
privilege after an address change.

**Status:** `open`.

---

## P1-003 — Classifier has no held-out evaluation

**Severity:** P1 — §8. Thresholds were chosen from the same runs that report
performance.

**Acceptance:** per-class precision/recall/F1 from an independent labelled set;
macro-F1; confusion matrix; abstention rate.

**Status:** `open`.

---

## P1-004 — CAKE comparison inconclusive

**Severity:** P0/P1 — §7.

**Current state:** against `b1_cake95`, `matrix6` shows **no significant
difference**. Against `b0_fifo`, p = 0.0312. No claim of superiority over CAKE is
made anywhere in the documentation, and none is supported.

**Acceptance:** matched conditions, a pre-declared primary metric, adequate
sample size, and a stated non-inferiority margin if that is the claim.

**Status:** `open` — correctly reported as inconclusive today.

---

## P1-005 — Fairness measured by Jain index only, per-class, not per-flow

**Severity:** P1 — §10.

**Current state:** `jain_fairness` over per-class goodput. That is a
coarse measure; it cannot show starvation of a single flow inside a large class.

**Acceptance:** per-flow and per-device measurement; starvation duration;
weighted fairness; behaviour when floors cannot all be met.

**Status:** `open`.

---

## P1-006 — Envelope/rollback failure paths never exercised against a real kernel

**Severity:** P1 — §13.

**Current state:** `txn.py` implements rollback and read-back verification and
they are unit-tested against `FakeRunner`. **No test has driven a real `tc`
failure** and then inspected the real kernel state.

**Acceptance:** fault injection at each transaction stage with the actual
installed state compared against the intended safe state.

**Status:** `blocked-environment`.

---

## P2-001 — Three of six dashboard panels have no data source

**Severity:** P2, but it is the *visible* symptom of P0-001.

**Current state:** the panels now say "not measured" rather than drawing a false
zero line. The underlying absence of data is P0-001.

**Status:** `open` — depends on P0-001.

---

## P2-002 — No resource-overhead or scalability measurement

**Severity:** P2 — §15.

**Current state:** `cpu_fraction` (controller process CPU / wall) is recorded
per sample and observed at 0.64% peak. Nothing measures memory, control-loop
latency, or behaviour at 50/100/500 flows.

**Acceptance:** the measurements in §15, or each marked blocked with a reason.

**Status:** `open` — partly feasible in this shell.