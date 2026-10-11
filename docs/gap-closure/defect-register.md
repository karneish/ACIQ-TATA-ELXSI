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
---

## P1-007 — An EF claim is refused only when the flow saturates

**Severity:** P1 — §8.1, "cases in which missing evidence is treated as positive
evidence".

**Files:** `aciq/classify.py:238-272`.

**Root cause:** the EF conflict test is `too_fast = frac >= EF_FAST_CONFLICT_CAPACITY_FRAC`
(0.5). A flow taking 21% of a 100 Mbps link is therefore not "too fast", so a
bulk-shaped flow that marks itself EF receives **interactive priority at 0.95
confidence** — 80 MB moved, 15 KB packets, 99% duty cycle, and it is treated as a
call.

There is no packet-level bulk test anywhere in the classifier. `Tier B`'s bulk
rule is also purely rate-based (`frac >= 0.5`), so "bulk" and "saturating" are the
same predicate, and a large one-way transfer at half the link or less is not
bulk by definition.

**Reproduction:** `python3 tools/eval_classifier.py`, case
"ADVERSARIAL bulk claiming EF".

```
capacity 100 Mbps:  truth=bulk_transfer  got=realtime_interactive  conf=0.95 tier=A
capacity  10 Mbps:  (same case resolves, because frac then exceeds 0.5)
```

**Evidence:** `docs/gap-closure/classifier-evaluation.json`.

**Required change:** the EF path must consult the same bulk evidence as the rate
path, including a packet-level test (average packet size, directionality, duty
cycle) rather than rate alone.

**Why this is documented and not patched here:** it changes the core
classification rule, and this shell cannot run the end-to-end experiment that
would show whether enforcement still behaves. Shipping an unvalidated change to
the rule that decides which class a flow gets is the exact failure this project
has spent its history correcting. The change is small and specified; it needs a
kernel-integrated run to land.

---

## P1-008 — Classifier quality depends materially on the capacity assumption

**Severity:** P1 — an operating point that is never stated.

**Measured** (`tools/eval_classifier.py`, 16 constructed cases, ground truth from
the workload profile rather than from the classifier):

| link capacity | accuracy | macro F1 | bulk F1 |
|---|---|---|---|
| 100 Mbps (shipped default) | 0.6154 | 0.7273 | **0.0 — bulk never assigned** |
| 10 Mbps (what `--drop 10` produces) | 0.8462 | 0.8487 | 0.8571 |

`BULK_MIN_CAPACITY_FRAC = 0.5` means the same flow is bulk on a 10 Mbps link and
merely adaptive on a 100 Mbps one. Every stored experiment in `data/` ran at
100 Mbps with ~25 Mbps of load, so **bulk should rarely have been assigned in
them at all** — and the `bulk_transfer` figures reported from those runs deserve
re-reading through this lens.

**Status:** `open` — a threshold and an assumption, both documented, neither
validated across the capacity range the estimator can actually produce.

---

## P1-009 — A port-table rule can override behaviour at high confidence

**Severity:** P1.

**Case:** "ADVERSARIAL interactive on a bulk port" — a small bidirectional flow
on port 873, which is in `BULK_PORTS`. It is classified **bulk at 0.70**, tier A.

**Root cause:** the well-known-port fallback runs after the rate rules and is not
gated on the rate evidence *disagreeing*. A port hint overrides a flow that is
demonstrably not bulk-shaped.

**Evidence:** `tools/eval_classifier.py`, both capacities.

**Status:** `open` — small fix (gate the port fallback on the rate rules being
inconclusive rather than merely unmatched), not applied pending the same
validation as P1-007.
