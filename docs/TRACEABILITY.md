# Traceability Matrix

Status: **PHASE 0 PLAN - NOT A FINAL AUDIT**
Date: 2026-10-23
Companion documents: [`PHASE0_PLAN.md`](PHASE0_PLAN.md),
[`CONCEPTS.md`](CONCEPTS.md), and `docs/MODULES.md` (to be written in the
implementation phases).

This matrix maps every requirement in the brief to the file, test or experiment
that will satisfy it. It is intentionally a plan, not a claim of completion.
Status codes:

| Code | Meaning |
|---|---|
| `KEEP` | Existing artifact covers the requirement; must be revalidated on the current revision. |
| `EXTEND` | Existing artifact exists but must change to meet the brief. |
| `NEW` | No artifact yet. |
| `DOC` | Documentation deliverable. |
| `PRIOR` | Prior evidence exists but is not a Phase 0 result; must be relabelled or re-run. |

The final audit in Phase 8 will replace statuses with **PASS / FAIL** and list a
fix for every FAIL. A requirement without a file path or raw result is FAIL.

---

## A. Core challenge

| ID | Requirement | Implementation artifact | Test / experiment evidence | Status | Phase |
|---|---|---|---|---|---|
| C1 | Classify broad traffic categories without reading private payloads or decrypting | `aciq/observer.py` (header-only), `aciq/features.py`, `aciq/classify.py`; no TLS/payload imports in classifier path | `tests/test_observer.py` privacy assertions; `tests/test_classify_7class.py`; `tools/eval_classifier.py` | EXTEND | 2 |
| C2 | Estimate WAN link capacity | `aciq/capacity.py`: passive goodput + queue/latency-under-load signals, confidence, step detection | `tests/test_capacity.py`, `tests/test_capacity_step.py`, new `tests/test_capacity_latency.py`; S2 experiment | EXTEND | 3 |
| C3 | Apply queueing and shaping policies with Linux traffic control | `aciq/tc.py`, `qdisc.py`, `bridge.py`, `marks.py`, `txn.py`; HTB + fq_codel/CAKE + ifb + nftables | `tests/test_enforce.py`, `tests/test_ifb.py`, live `testbed/gate.sh`; S1-S5 | EXTEND | 4 |
| C4 | Verify improvement and roll back if worse (observe -> classify -> estimate -> decide -> enforce -> verify -> rollback) | `aciq/controller.py`, `aciq/state_machine.py`, `aciq/verifier.py`, `aciq/txn.py`, `aciq/closedloop.py` | `tests/test_verifier.py`, `tests/test_state_machine.py`, `tests/test_rollback.py`, `tests/test_rollback_live.py`; S5 | EXTEND / NEW | 4, 6 |
| C5 | Support a temporary user intent while retaining fairness | `aciq/intent.py`, `aciq/api.py`, `aciq/policy.py`, `aciq/dashboard.py` | `tests/test_intent.py`, new `tests/test_intent_class_target.py`, `tests/test_fairness_live.py`; S4 | EXTEND | 5 |

---

## B. Required modules and their five contracts

Every module must document (a) inputs, (b) outputs, (c) state transitions,
(d) failure handling, (e) success conditions in `docs/MODULES.md` and have unit
tests. The tables below name the artifact and the test that will prove each
aspect. The final `docs/MODULES.md` will contain the full prose.

### M1. Traffic Observer

| ID | Contract / requirement | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| M1-a | Inputs: packet headers / conntrack snapshots from edge interfaces | `aciq/observer.py` (new), `aciq/flowtrack.py` | `tests/test_observer.py`, `tests/test_flowtrack.py` | NEW / EXTEND | 2 |
| M1-b | Outputs: per-flow 5-tuple, direction, packet sizes, inter-arrival, bytes/s, duration, protocol | `aciq/observer.py`, `aciq/features.py` (new), `aciq/model.py` | `tests/test_observer.py`, `tests/test_features.py` | NEW | 2 |
| M1-c | State: flow create / update / evict; counter reset; IPv4 and IPv6 | `aciq/features.py`, `aciq/flowtrack.py` | `tests/test_observer.py`, `tests/test_flowtrack.py`, `tests/test_dualstack.py` | NEW / EXTEND | 2 |
| M1-d | Failure: unreadable socket, malformed packet, counter reset, no metadata -> degrade safely, never crash collector | `aciq/observer.py`, `aciq/flowtrack.py` | malformed-input and permission-denied tests; fallback test | NEW / EXTEND | 2 |
| M1-e | Success: metadata-only observation with no payload access; measured flow features match generators | `aciq/observer.py`, privacy test | `tests/test_observer.py` asserts no payload bytes are read or stored; known-generator feature test | NEW | 2 |

### M2. Traffic Classifier

| ID | Contract / requirement | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| M2-a | Inputs: flow features, capacity, optional user correction / intent | `aciq/classify.py`, `aciq/features.py`, `aciq/corrections.py` | `tests/test_classify_7class.py`, `tests/test_corrections.py` | EXTEND | 2 |
| M2-b | Outputs: `{class, confidence}` for 7 classes plus unknown; evidence string | `aciq/model.py`, `aciq/classify.py` | `tests/test_classify_7class.py` | EXTEND | 2 |
| M2-c | State: rule confidence, trust decay, correction lifetime, low-confidence abstention | `aciq/classify.py`, `aciq/corrections.py` | `tests/test_classify.py`, `tests/test_corrections.py` | EXTEND | 2 |
| M2-d | Failure: low confidence -> unknown/best-effort; conflicting signals -> abstain; correction store unavailable -> rule path and warning | `aciq/classify.py`, `aciq/corrections.py` | ambiguity/conflict tests; missing-store test | EXTEND | 2 |
| M2-e | Success: measured per-class precision/recall/F1, confusion matrix, calibration, zero high-confidence errors on held-out data | `tools/eval_classifier.py`, `results/classifier/` | `tests/test_eval_classifier.py`, `tools/eval_classifier.py --json` | EXTEND | 2 |
| M2-1 | Classes at minimum: video_call/voice, interactive_gaming, adaptive_video_streaming, bulk_download, software_update, cloud_backup, unknown | `aciq/model.py` enum + `aciq/classify.py` rules | `tests/test_classify_7class.py`; confusion matrix includes all 7 | EXTEND | 2 |
| M2-2 | Confidence exposed per flow | `Classification.confidence`, dashboard, report | unit tests + dashboard test | EXTEND | 2, 6 |
| M2-3 | Low confidence falls back to unknown / best-effort | `aciq/classify.py`, `aciq/closedloop.py`, `tc.py` default class | abstention tests; live filter test | EXTEND | 2, 4 |
| M2-4 | User correction feedback API stores overrides and applies them | `aciq/corrections.py`, `aciq/api.py`, `aciq/dashboard.py` | `tests/test_corrections.py`, `tests/test_api_hardening.py`; live correction run | EXTEND | 5 |
| M2-5 | Deterministic rule-based baseline first; optional ML compared on same held-out data | `aciq/classify.py`, `aciq/learned.py`, `tools/eval_classifier.py` | `tests/test_learned_comparison.py`; ML vs rules report | EXTEND | 2 |

### M3. Link Capacity Estimator

| ID | Contract / requirement | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| M3-a | Inputs: passive goodput, queue depth, drops/overlimits, latency-under-load signals | `aciq/capacity.py`, `aciq/metrics.py` | `tests/test_capacity.py`, `tests/test_capacity_latency.py` | EXTEND | 3 |
| M3-b | Outputs: capacity Mbps, confidence, saturated, changed | `aciq/model.py`, `aciq/capacity.py` | `tests/test_capacity.py` | KEEP / EXTEND | 3 |
| M3-c | State: idle / saturated / step-up / step-down / recovery; no learning from idle; hysteresis | `aciq/capacity.py` | step tests, idle-false-positive tests, recovery test | EXTEND | 3 |
| M3-d | Failure: no counters / no probe / stale estimate -> low confidence, bounded fallback, never crash | `aciq/capacity.py` | unavailable-source and stale tests | EXTEND | 3 |
| M3-e | Success: percent error vs known emulated capacity; detection time after 100->20 step; no idle collapse | S2 experiment, `results/` | `tests/test_capacity_step.py`; S2 baseline/optimized | EXTEND | 3, 7 |
| M3-1 | Passive throughput observation plus latency-under-load signal | `aciq/capacity.py`, real-time flow RTT / optional unmarked probe | `tests/test_capacity_latency.py`; S1/S2 | EXTEND | 3 |
| M3-2 | Detect sudden capacity changes (e.g. 100 -> 20 Mbps) | `aciq/capacity.py` CUSUM/EWMA step detector | `tests/test_capacity_step.py`; S2 detection-time metric | EXTEND | 3 |
| M3-3 | Shaper rate set slightly below estimate, configurable, default 90-95% | `aciq/policy.py`, config in `data/scenarios/` and `.env.example` | `tests/test_policy.py`; live S1/S2 | EXTEND | 3, 4 |

### M4. Policy Engine

| ID | Contract / requirement | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| M4-a | Inputs: classes, capacity estimate, active intent, live metrics | `aciq/policy.py`, `aciq/state_machine.py` | `tests/test_policy.py`, `tests/test_state_machine.py` | EXTEND / NEW | 4 |
| M4-b | Outputs: per-class rates, ceilings, priorities, queue settings; reason and state | `aciq/model.py` `RatePlan`, `aciq/policy.py`, `aciq/state_machine.py` | `tests/test_policy.py`, `tests/test_state_machine.py` | EXTEND | 4 |
| M4-c | State: explicit `INIT`, `NORMAL`, `CONGESTED`, `INTENT_ACTIVE`, `RECALIBRATING`, `SAFE_MODE`, `ROLLING_BACK`; hysteresis/cooldown | `aciq/state_machine.py` | transition table tests; flapping tests | NEW | 4 |
| M4-d | Failure: invalid plan, capacity too small, repeated faults -> degraded or safe state; no silent floor violation | `aciq/policy.py`, `aciq/state_machine.py`, `aciq/shield.py` | invariant tests; degraded-capacity tests; fault tests | EXTEND | 4 |
| M4-e | Success: `sum(rates) <= capacity`, every class floor honoured or explicitly degraded; stable under noise | `aciq/policy.py`, `tests/test_policy.py`, S2/S3 | policy sweep + live evidence | EXTEND | 4, 7 |
| M4-1 | Prevent flapping with hysteresis/cooldown | `aciq/state_machine.py`, `aciq/shield.py` | flap tests; `changes_per_min` metric | EXTEND / NEW | 4 |
| M4-2 | Minimum guaranteed share for every class | `aciq/policy.py` floors; 7-class weights | `tests/test_policy.py`; S4 starvation test | EXTEND | 4 |
| M4-3 | Intent-aware policy without deleting floors | `aciq/policy.py`, `aciq/intent.py` | `tests/test_intent.py`, S4 | EXTEND | 5 |

### M5. Enforcer

| ID | Contract / requirement | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| M5-a | Inputs: validated `RatePlan`, filters, class mapping | `aciq/tc.py`, `aciq/bridge.py`, `aciq/marks.py` | `tests/test_enforce.py`, `tests/test_bridge.py`, `tests/test_marks.py` | EXTEND | 4 |
| M5-b | Outputs: live tc/nft state; audit log; read-back state | `aciq/tc.py`, `aciq/qdisc.py`, `aciq/txn.py` | live `testbed/gate.sh`; read-back tests | EXTEND | 4 |
| M5-c | State: snapshot -> apply -> verify -> committed / rollback / safe | `aciq/txn.py`, `aciq/shield.py` | `tests/test_rollback.py`, `tests/test_rollback_live.py` | EXTEND | 4 |
| M5-d | Failure: command refused, partial apply, read-back mismatch, exception -> snapshot restore + safe state | `aciq/txn.py`, `aciq/watchdog.py` | failure-injection S5; `tests/test_safe_reset.py` | EXTEND / NEW | 4 |
| M5-e | Success: post-apply read-back matches plan; IPv4/IPv6; no orphan classes; rollback verified | live gate; `tests/test_dualstack.py`; S5 | EXTEND | 4 |
| M5-1 | HTB hierarchy with per-class fq_codel or CAKE | `aciq/tc.py`, `aciq/qdisc.py` | `tests/test_enforce.py`; gate | EXTEND | 4 |
| M5-2 | ifb device for ingress/download shaping | `testbed/setup.sh`, `aciq/tc.py`, `aciq/bridge.py` | `tests/test_ifb.py`; live S1 | NEW / EXTEND | 4 |
| M5-3 | Filters by fwmark/DSCP, IPv4 and IPv6 | `aciq/marks.py`, `aciq/bridge.py`, `aciq/tc.py` | `tests/test_marks.py`, `tests/test_dualstack.py` | EXTEND | 4 |
| M5-4 | Atomic-as-possible with saved snapshot before apply | `aciq/txn.py` | `tests/test_rollback.py`; audit JSON | EXTEND | 4 |
| M5-5 | Bounded rate changes per step, min/max shaping rate | `aciq/policy.py`, `aciq/state_machine.py`, `aciq/tc.py` | boundary tests; S2 overshoot metric | NEW / EXTEND | 4 |
| M5-6 | Structured logs for every decision with reason | `aciq/controller.py`, audit JSONL | log schema tests; `results/` | NEW | 4 |
| M5-7 | Reversible; safe state = fq_codel/CAKE, no special classes; `make safe-reset` | `testbed/safe_reset.sh`, `tools/safe_reset.py`, `Makefile` | `tests/test_safe_reset.py`; S5 | NEW | 4, 8 |
| M5-8 | Handle crash, exception, SIGTERM/SIGINT, watchdog timeout | `aciq/watchdog.py`, controller signal handlers, testbed supervisor | `tests/test_watchdog.py`; S5 | NEW | 4 |

### M6. Verifier / Monitor

| ID | Contract / requirement | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| M6-a | Inputs: before/after metric windows, policy transaction, state | `aciq/verifier.py`, `aciq/metrics.py`, `aciq/measure.py` | `tests/test_verifier.py` | NEW / EXTEND | 6 |
| M6-b | Outputs: improved / not improved / worse, effect sizes, reason | `aciq/verifier.py` | `tests/test_verifier.py` | NEW | 6 |
| M6-c | State: baseline window -> candidate window -> verdict -> commit/rollback | `aciq/verifier.py`, `aciq/controller.py`, `aciq/txn.py` | closed-loop tests, S5 | NEW / EXTEND | 4, 6 |
| M6-d | Failure: too few samples, missing probe, metric invalid -> not improved / defer, never invent zero | `aciq/measure.py`, `aciq/verifier.py` | missing/insufficient tests | EXTEND | 6 |
| M6-e | Success: verdict agrees with raw metrics; rollback triggers only on measured worse | `tests/test_verifier.py`; S1-S5 reports | NEW | 6 |
| M6-1 | Measure latency, jitter, loss, throughput, queue depth, fairness before/after | `aciq/measure.py`, `aciq/metrics.py` | unit + live tests | EXTEND | 6 |
| M6-2 | Report improved / not improved / worse | `aciq/verifier.py`, `aciq/report.py` | `tests/test_verifier.py` | NEW | 6 |

### M7. Intent API

| ID | Contract / requirement | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| M7-a | Inputs: create/list/cancel intent; target class/device/flow; TTL; weight/min share | `aciq/intent.py`, `aciq/api.py` | `tests/test_intent.py`, new class-target tests | EXTEND | 5 |
| M7-b | Outputs: intent id, expiry, active list, applied policy reason | `aciq/intent.py`, `aciq/api.py`, `aciq/dashboard.py` | API tests; S4 evidence | EXTEND | 5 |
| M7-c | State: create -> active -> expiring -> expired/cancelled; restart persistence | `aciq/intent.py` (JSONL or SQLite-backed), `aciq/api.py` | TTL tests, restart test | EXTEND | 5 |
| M7-d | Failure: invalid target, duration > max, weight out of range, store unavailable -> reject with reason; no partial grant | `aciq/intent.py`, `aciq/api.py` | validation and failure tests | EXTEND | 5 |
| M7-e | Success: intent applies, expires automatically, reverts, target improves, other classes stay above floor | S4; `tests/test_intent.py`; fairness test | EXTEND | 5 |
| M7-1 | Temporary intent e.g. "prioritise my work call for 60 minutes" | `aciq/intent.py`; `MAX_TTL_S=3600`; dashboard form | S4; API test with 3600 s | EXTEND | 5 |
| M7-2 | Automatic expiry (TTL), maximum duration bound | `aciq/intent.py` sweep | TTL/max-bound tests | EXTEND | 5 |
| M7-3 | Priority never reduces other classes below configurable minimum guaranteed share | `aciq/policy.py` floors, `aciq/intent.py` | floor tests; S4 starvation check | EXTEND | 4, 5 |
| M7-4 | Feedback/correction API stores overrides and applies them | `aciq/corrections.py`, `aciq/api.py` | correction tests + live classifier change | EXTEND | 5 |

### M8. Dashboard

| ID | Contract / requirement | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| M8-a | Inputs: live metrics frames, state, policy, intent, classifier confidence | `aciq/dashboard.py`, `aciq/api.py` | `tests/test_dashboard.py` | EXTEND | 6 |
| M8-b | Outputs: live page with required panels and controls | `aciq/dashboard.py`, vanilla JS | dashboard tests; live browser check | EXTEND | 6 |
| M8-c | State: live update, stale data, disconnected API, no data | `aciq/dashboard.py` | stale/missing data tests | EXTEND | 6 |
| M8-d | Failure: API unavailable, malformed frame -> show unavailable, never zero; renderer cannot write tc | `aciq/dashboard.py` | read-only structural tests; missing-data tests | EXTEND | 6 |
| M8-e | Success: all required panels show real measurements; intent control works | S1-S5 dashboard captures; live check | EXTEND | 6, 7 |
| M8-1 | Panels: latency, jitter, loss, throughput, queue depth, fairness | `aciq/dashboard.py` | `tests/test_dashboard.py` | KEEP / EXTEND | 6 |
| M8-2 | Panels: current state, active policy, active intent, classifier confidence | `aciq/dashboard.py`, `aciq/state_machine.py` | new dashboard tests | NEW / EXTEND | 6 |
| M8-3 | Simple UI control for temporary intent | `aciq/dashboard.py` + API calls | live UI test; API contract test | NEW | 6 |

### M9. Experiment Runner and Report Generator

| ID | Contract / requirement | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| M9-a | Inputs: scenario, mode, seed, impairment config, system | `aciq/experiment.py`, `aciq/harness.py`, `run_experiments.py` | `tests/test_experiment.py`, `tests/test_harness.py` | EXTEND | 7 |
| M9-b | Outputs: raw CSV/JSONL, summary JSON, report, manifest | `aciq/experiment.py`, `aciq/report.py`, `results/` | `tests/test_workload_reports.py`, `tests/test_report_ci.py` | EXTEND | 7 |
| M9-c | State: reset -> baseline -> inject -> measure -> optimized -> compare -> cleanup | `tools/demo.py`, `run_experiments.py` | dry-run + live demo | NEW / EXTEND | 7 |
| M9-d | Failure: run crash, partial data, testbed dirty -> safe cleanup, mark run invalid, no fabricated report | `tools/demo.py`, `experiment.py`, `watchdog.py` | failure-injection tests | NEW | 7 |
| M9-e | Success: 10 seeds x S1-S5 x baseline/optimized, raw evidence, mean + 95% CI | `results/matrix/`, `aciq/report.py` | full matrix run; report | EXTEND | 7 |
| M9-1 | Automated baseline-vs-optimized experiments | `run_experiments.py`, `aciq/report.py` | S1-S5 | EXTEND | 7 |
| M9-2 | `make demo` resets, injects condition, collects evidence, writes report | `Makefile`, `tools/demo.py` | demo run log + report | NEW | 7 |
| M9-3 | Report includes graphs, raw CSV/JSON kept in `results/` | `aciq/report.py`, `results/` | report + file listing | EXTEND | 7 |

---

## C. Hard constraints

| ID | Requirement | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| H1 | Do not decrypt application traffic; no payload inspection; classification uses metadata/flow statistics only | `aciq/observer.py` header-only; `aciq/classify.py`; docs statement in `CONCEPTS.md`, `MODULES.md`, `LIMITATIONS.md` | `tests/test_observer.py` asserts no payload access; source grep for TLS/payload parsing; report statement | NEW / DOC | 2, 8 |
| H2 | Enforcement uses Linux traffic control or another open, inspectable mechanism | `aciq/tc.py`, `qdisc.py`, `bridge.py`; `tc`/nftables commands logged | live gate; audit JSON | KEEP / EXTEND | 4 |
| H3 | Support IPv4 and IPv6; test both address families | `testbed/setup.sh`, `aciq/marks.py`, `aciq/bridge.py`, `aciq/flowtrack.py`; dual-stack scenario | `tests/test_dualstack.py`; gate checks; S1 IPv4 + IPv6 | EXTEND | 1, 4, 7 |
| H4 | Policy rollback and no starvation; minimum guaranteed share for every class; bulk throughput > 0 during intent | `aciq/policy.py` floors, `aciq/txn.py`, `aciq/verifier.py`; S4 | `tests/test_policy.py`, `tests/test_rollback.py`, `tests/test_fairness_live.py`; S4 | EXTEND | 4, 7 |
| H5 | Classifiers expose confidence and allow correction of misclassification | `aciq/classify.py`, `aciq/corrections.py`, `aciq/api.py` | `tests/test_classify_7class.py`, `tests/test_corrections.py`, API tests | EXTEND | 2, 5 |
| H6 | Document all third-party licenses; no redistribution contrary to license; prefer permissive; flag GPL/AGPL | `docs/THIRD_PARTY_LICENSES.md`; dependency inventory; source links | licence audit; `make license-audit` (optional) | DOC / NEW | 8 |
| H7 | Generated data and impairment settings committed (netem/tbf, seeds, generator configs) | `data/impairments/*.json`, `data/scenarios/*.json`, `data/seeds.json`, `results/` | git manifest; `tests/test_reproducibility.py` (new) | NEW | 1, 7 |
| H8 | Emulated hardware labelled clearly; model and limitations explained | `docs/LIMITATIONS.md`, every report header `EMULATION` | report template test; docs review | DOC | 8 |
| H9 | No credentials/private keys/tokens in source; env vars; `.env.example` fictitious; `.gitignore`; secret scan | `.env.example`, `.gitignore`, `tools/secret_scan.py`; `Makefile` target | `tests/test_secret_scan.py`; `make secret-scan` | EXTEND / NEW | 8 |
| H10 | Automated remediation bounded, observable, reversible, safe; crash/exception/SIGTERM/SIGINT/watchdog; `make safe-reset` | `aciq/state_machine.py`, `aciq/policy.py`, `aciq/txn.py`, `aciq/watchdog.py`, `testbed/safe_reset.sh`, `Makefile` | `tests/test_state_machine.py`, `tests/test_watchdog.py`, `tests/test_safe_reset.py`; S5 | NEW / EXTEND | 4, 8 |

---

## D. Testbed requirements

| ID | Requirement | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| T1 | Everything runs on a single Linux VM; root required; documented | `docs/SETUP.md`, `testbed/gate.sh`, host toolchain record | exact commands + versions; gate log | DOC / EXTEND | 1, 8 |
| T2 | Linux network namespaces, veth pairs, bridge | `testbed/setup.sh`, `testbed/teardown.sh`, `testbed/reset.sh` | live `ip netns`/`ip link` evidence | EXTEND / NEW | 1 |
| T3 | Several home client namespaces: laptop call, gaming, 3 TVs, backup/updates | `testbed/setup.sh`: `laptop`, `gaming`, `tv1`, `tv2`, `tv3`, `backup` | namespace inventory in gate log | NEW | 1 |
| T4 | Edge/router namespace with controller + tc | `testbed/setup.sh` router ns; `aciq/controller.py`; management path | gate; controller run log | EXTEND / NEW | 1, 4 |
| T5 | WAN emulation link with netem + tbf or HTB for rate/delay/loss, dynamically changeable | `testbed/setup.sh`, `data/impairments/*.json`, capacity-step code | S2; gate checks | EXTEND | 1, 3 |
| T6 | Server namespace | `testbed/setup.sh` `server` ns; workload endpoints | gate; workload run | NEW | 1 |
| T7 | Dual-stack IPv4/IPv6 | addresses and routes in setup; `tests/test_dualstack.py` | S1 IPv4 + IPv6; conntrack v4/v6 | EXTEND | 1, 7 |
| T8 | Scripts: setup, teardown, reset | `testbed/setup.sh`, `teardown.sh`, `reset.sh`, `safe_reset.sh` | idempotence tests; `make testbed-up/down/reset` | EXTEND / NEW | 1 |
| T9 | Generators: iperf3, ping/irtt or similar, custom call 20 ms, game 60 Hz, adaptive video chunked TCP, update/backup long TCP | `testbed/workloads/*.py`; iperf3 for bulk cross-check; custom UDP probe for RTT/jitter/loss | workload self-reports; S1-S5 | EXTEND / NEW | 1 |
| T10 | Ground-truth labels known; classification accuracy measurable | `data/scenarios/*.json`, label manifest, `tools/eval_classifier.py` | confusion matrix + per-class metrics | EXTEND | 1, 2 |
| T11 | Impairment settings, generator configs, seeds committed | `data/impairments/`, `data/scenarios/`, `data/seeds.json` | git status; manifest hash | NEW | 1, 7 |
| T12 | No host network touched; cleanup idempotent | `testbed/cleanup.sh`, `teardown.sh` | cleanup run twice; no leftover namespaces | KEEP / EXTEND | 1 |

---

## E. Required scenarios and repetitions

| ID | Requirement | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| S1 | Large ISO download starts during video conference; protect call latency | `data/scenarios/s1_iso_during_call.json`, `aciq/experiment.py` | baseline/optimized, 10 seeds, `results/matrix/s1/` | EXTEND | 7 |
| S2 | WAN drops 100 -> 20 Mbps; recalculate shaping; measure adaptation time | `data/scenarios/s2_wan_drop.json`, `aciq/capacity.py` | 10 seeds; estimate error, detection/stabilisation time | EXTEND | 7 |
| S3 | Three TVs stream while gaming needs low latency; balance household | `data/scenarios/s3_tv_and_gaming.json` | 10 seeds; game latency, Jain, per-TV fairness | EXTEND | 7 |
| S4 | Temporary work-call intent starts and expires; auto-revert and fairness | `data/scenarios/s4_intent.json`, `aciq/intent.py`, dashboard | 10 seeds; intent active/expired, floors, fairness | NEW | 7 |
| S5 | Failure injection: kill controller, make tc apply fail; return to safe state | `data/scenarios/s5_failure_injection.json`, `watchdog.py`, `txn.py` | 10 seeds; safe-state assertions, rollback logs | NEW | 7 |
| S-common-1 | Each scenario runs BASELINE and OPTIMIZED | `run_experiments.py`, `aciq/harness.py` | result rows tagged mode/system | EXTEND | 7 |
| S-common-2 | At least 10 repeats with fixed and logged seeds | `data/seeds.json` (1001-1010), run manifest | 10 rows per arm; seed in manifest | NEW | 7 |
| S-common-3 | Report mean and confidence interval | `aciq/report.py`, `tests/test_report_ci.py` | report tables with n=10 and 95% CI | EXTEND | 7 |
| S-common-4 | Baseline-vs-optimized comparison and honest significance | `aciq/report.py`, `tools/compare.py` | paired tests; no overclaim at n=10 | EXTEND | 7 |
| S-common-5 | Old internal `s4_capacity_recovery` renamed to `s2b_capacity_recovery` | `aciq/harness.py`, scenario JSON | name uniqueness test | EXTEND | 1, 7 |

---

## F. Evaluation metrics

| ID | Requirement | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| E1 | Classification accuracy: precision, recall, F1 per class, confusion matrix | `tools/eval_classifier.py` | `tests/test_eval_classifier.py`; `results/classifier/` | EXTEND | 2 |
| E2 | Confidence calibration | `tools/eval_classifier.py` (Brier, ECE, reliability), `aciq/classify.py` | `tests/test_calibration.py` (new); report | NEW | 2 |
| E3 | Link estimation percent error vs known emulated capacity; detection time | `aciq/capacity.py`, `aciq/report.py` | S2; `results/matrix/s2/` | EXTEND | 3, 7 |
| E4 | Interactive latency p50/p95/p99, jitter, loss baseline vs optimized, percent reduction | `aciq/measure.py`, `aciq/metrics.py`, report | S1/S3; paired comparison | EXTEND | 6, 7 |
| E5 | Fairness: Jain index across flows/devices; minimum throughput per class; no starvation | `aciq/metrics.py`, `aciq/verifier.py` | S3/S4; `tests/test_fairness_live.py` | EXTEND | 6, 7 |
| E6 | Adaptation speed and policy stability: stabilisation seconds, changes/min, overshoot | `aciq/state_machine.py`, `aciq/controller.py`, report | S2/S5; transition log | NEW / EXTEND | 4, 7 |
| E7 | CPU overhead, memory, decision-loop latency | `aciq/metrics.py` (CPU/RSS), controller timestamps | `tests/test_metrics.py`; S1-S5 | EXTEND | 4, 7 |
| E8 | Reproducibility and clarity: revision, versions, seeds, configs, raw data | `results/<run>/manifest.json`, `docs/SETUP.md` | manifest test; report links | NEW | 7, 8 |
| E9 | Rule-based baseline first; optional ML compared on same held-out data; honest outcome | `aciq/learned.py`, `tools/eval_classifier.py` | `tests/test_learned_comparison.py`; ML report | EXTEND | 2 |
| E10 | Raw CSV/JSON retained in `results/` | `aciq/experiment.py`, `results/` | file listing; report references | NEW | 7 |
| E11 | Graphs in report (HTML or Markdown) | `aciq/report.py`, inline SVG | report render test | EXTEND | 7 |
| E12 | No fabricated numbers; missing data reported as missing | `aciq/report.py`, `aciq/measure.py` | tests for missing/zero distinction; final audit | KEEP / EXTEND | 8 |

---

## G. AI/ML rule

| ID | Requirement | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| AI1 | Deterministic rule-based classifier is built first and remains the baseline | `aciq/classify.py` | all classification tests; baseline report | KEEP / EXTEND | 2 |
| AI2 | Any ML classifier compared against baseline on same held-out data | `aciq/learned.py`, `tools/eval_classifier.py` | grouped held-out split; metrics table | EXTEND | 2 |
| AI3 | Report honestly whether ML improves a measurable outcome; no AI-only chat interface | `docs/PROJECT_REPORT.md` / `results/classifier/` | ML vs rules table; no LLM in path | EXTEND | 2, 8 |

---

## H. Required deliverables

| ID | Deliverable | Implementation artifact | Test / evidence | Status | Phase |
|---|---|---|---|---|---|
| D1 | Traffic-class and link-capacity estimator | `aciq/observer.py`, `features.py`, `classify.py`, `capacity.py` | module tests; S1-S3 | EXTEND / NEW | 2, 3 |
| D2 | Dynamic QoS policy engine and enforcement | `aciq/state_machine.py`, `policy.py`, `tc.py`, `qdisc.py`, `bridge.py`, `txn.py` | policy/enforcement/rollback tests; live gate | EXTEND / NEW | 4 |
| D3 | Dashboard for latency, jitter, loss, throughput, queue depth, fairness | `aciq/dashboard.py` | dashboard tests; live capture | EXTEND | 6 |
| D4 | Automated baseline-versus-optimized experiments | `run_experiments.py`, `aciq/experiment.py`, `report.py` | S1-S5 matrix | EXTEND | 7 |
| D5 | API/UI for temporary service intent | `aciq/api.py`, `intent.py`, dashboard form | API tests; S4; UI test | EXTEND / NEW | 5, 6 |
| D6 | Architecture diagram: device, edge, network, data, analytics, UI; Mermaid + exported image | `docs/diagrams/architecture.mmd`, `.svg`, `docs/architecture.md` | `make diagrams`; file existence; version log | NEW | 8 |
| D7 | Setup guide with prerequisites, exact versions, commands, config, verification | `docs/SETUP.md` | commands executed; version capture | NEW / DOC | 8 |
| D8 | One-command `make demo` resets, injects condition, collects evidence, writes report; raw CSV/JSON in `results/` | `Makefile`, `tools/demo.py`, `results/demo/` | demo log; report; raw files | NEW | 7 |
| D9 | Known limitations: real hardware, certification, scale, proprietary integration; prototype/production boundary | `docs/LIMITATIONS.md` | docs review; final audit | DOC / NEW | 8 |
| D10 | README | `README.md` | final review | EXTEND / DOC | 8 |
| D11 | `docs/CONCEPTS.md` | `docs/CONCEPTS.md` | final review | NEW / DOC | 0 |
| D12 | `docs/MODULES.md` | `docs/MODULES.md` | module audit | NEW / DOC | 2-8 |
| D13 | `docs/THIRD_PARTY_LICENSES.md` | `docs/THIRD_PARTY_LICENSES.md` | licence audit | NEW / DOC | 8 |
| D14 | `tests/` per module | `tests/test_*.py` | `make test` | KEEP / EXTEND | all |
| D15 | `data/` generated data + impairment configs | `data/` | git manifest | EXTEND | 1, 7 |
| D16 | `results/` raw CSV/JSON + reports | `results/` | file listing; report links | NEW | 7 |

---

## I. Workflow phases

| ID | Phase | Required output | Gate / evidence | Status |
|---|---|---|---|---|
| P0 | Plan | `docs/PHASE0_PLAN.md`, `docs/TRACEABILITY.md`, structure, tech choices | This matrix approved | DONE (awaiting approval) |
| P1 | Testbed + baseline | 6 clients, router, WAN, server, dual-stack; setup/teardown/reset/safe-reset; baseline measurements | gate PASS; baseline raw data; exact versions | PLANNED |
| P2 | Observer + classifier | header-only observer; 7-class rules; confidence; corrections; calibration; optional ML | class tests; confusion/calibration; no high-confidence errors | PLANNED |
| P3 | Capacity estimator | throughput + latency-under-load; step detection; confidence; 90-95% shaping | estimate/detection tests; S2 | PLANNED |
| P4 | Policy + enforcer + rollback + safe | explicit FSM; 7-class HTB; ifb; nft marks; bounded changes; snapshot/rollback; watchdog | live apply/read-back; IPv4/6; no starvation; safe reset; signals | PLANNED |
| P5 | Intent + feedback API | create/list/cancel; TTL/max; class/device/flow; correction API; dashboard control contract | API tests; S4; floors preserved | PLANNED |
| P6 | Verifier + dashboard | before/after verdict; full panels; live controls | verifier tests; dashboard panels; UI intent | PLANNED |
| P7 | Experiments + report + demo | S1-S5, 10 seeds, baseline/optimized/reference, raw results, report, `make demo` | full matrix; CIs; demo one command | PLANNED |
| P8 | Docs + licence + secret + limitations + final audit | canonical docs; Mermaid export; secret scan; DoD checklist | every item PASS or documented FAIL+FIX | PLANNED |

---

## J. Definition of Done checklist (final audit template)

This is the checklist that Phase 8 will fill in. It is included now so that no
requirement is discovered late. No item is PASS until it has a file path or raw
result.

| # | Check | Evidence required | Status (Phase 8) |
|---|---|---|---|
| 1 | Payload is never read/decrypted; classifier metadata-only | Privacy test + source review + report statement | PENDING |
| 2 | Linux tc/open enforcement | Live tc audit + gate log | PENDING |
| 3 | IPv4 and IPv6 tested | Dual-stack test + S1 v4/v6 evidence | PENDING |
| 4 | Rollback works | S5 + rollback logs | PENDING |
| 5 | No starvation; every class has minimum share | S4 + per-class throughput table | PENDING |
| 6 | Classifier confidence + correction | Tests + API + live correction run | PENDING |
| 7 | Classification metrics (P/R/F1/confusion/calibration) | `results/classifier/` | PENDING |
| 8 | Capacity estimate error + detection time | S2 table | PENDING |
| 9 | Interactive latency/jitter/loss baseline vs optimized | S1/S3 tables | PENDING |
| 10 | Fairness Jain + minimum throughput | S3/S4 tables | PENDING |
| 11 | Adaptation speed/stability/overshoot | S2/S5 tables | PENDING |
| 12 | CPU/memory/decision-loop latency | Metrics table | PENDING |
| 13 | Reproducibility: versions/seeds/configs/raw data | Manifests + setup guide | PENDING |
| 14 | Rule baseline + optional ML honest comparison | Classifier report | PENDING |
| 15 | Dashboard panels + intent control | Screenshot/report + test | PENDING |
| 16 | Architecture Mermaid + exported image | Files + tool version | PENDING |
| 17 | Setup guide exact versions and commands | `docs/SETUP.md` | PENDING |
| 18 | `make demo` works from clean state | Demo log + report + raw files | PENDING |
| 19 | Licences documented; GPL/AGPL flagged | `docs/THIRD_PARTY_LICENSES.md` | PENDING |
| 20 | Secrets absent; `.env.example` fictitious; scan passes | Secret scan log | PENDING |
| 21 | Emulation labelled; limitations documented | Report header + `docs/LIMITATIONS.md` | PENDING |
| 22 | Bounded/observable/reversible/safe remediation | FSM + bounding tests + S5 | PENDING |
| 23 | SIGTERM/SIGINT/crash/watchdog safe state | S5 logs | PENDING |
| 24 | `make safe-reset` works and is idempotent | Two-run log | PENDING |
| 25 | README, CONCEPTS, MODULES, SETUP, LICENCES, LIMITATIONS present | File list | PENDING |
| 26 | `tests/`, `data/`, `results/` present and populated | File list | PENDING |
| 27 | Every number in reports traceable to raw data | `tools/reconcile_results.py` output | PENDING |
| 28 | No requirement without evidence | This matrix completed | PENDING |

---

## K. Immediate next action

Phase 0 stops here. No code or testbed changes have been made. The user must
approve the plan and reply **"continue"** before Phase 1 begins.
