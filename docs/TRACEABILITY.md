# Traceability Matrix - Phase 1 re-audit (real code reading, not grep)

Status: **PHASE 1 AUDIT RESULT** (supersedes the PHASE 0 planning matrix)
Date: 2026-10-23
Method: every row below was produced by reading the full source of the named
module (not grep), cross-checked against the live-kernel gate logs
(`testbed/logs/gate-20261021-213009.log`, all 20 checks PASS, host kernel
`7.1.5-76070105-generic`) and the `data/host_gate_*` run evidence.

Status codes (final audit in Phase 8 will convert to honest PASS/FAIL):

| Code | Meaning |
|---|---|
| `REAL` | Code exists and has been verified against a real kernel (live gate / needs-root tests). Dated: 2026-10-21, parent-rev `c5da3fd`. The current tree has not been re-verified live (host sudo needs a password; see `docs/evidence/phase1/environment-20261023.log`). |
| `MOCKED` | Code exists; only mock/fake-kernel unit tests cover it. |
| `BROKEN` | Code exists but does not meet the requirement even in principle. |
| `MISSING` | No code exists. Planned paths are written `(to be written)` so the path-citation audit does not count them as broken citations. |

Old statuses (`PARTIAL`) are retired: they contained guesses (for example an
entry guessing at an observer module path that had never been read). This file
is an audit of what is, not what will be.

Planned-artifact phrasing: where the row cites a file that must be created in a
later phase, the citation carries `(to be written)`. Any artifact named without
that marker exists in the tree now.

---

## A. Core challenge

| ID | Requirement | Current artifact | Status | Evidence / gap |
|---|---|---|---|---|
| C1 | Classify broad categories without reading payloads | `aciq/classify.py` (3 classes + abstention, `model.py:13-20`), `aciq/corrections.py`, `aciq/flowtrack.py` (conntrack counters only) | MOCKED (3-class), MISSING (7-class) | No payload access anywhere (audit grep + source review; `flowtrack.py:200-202` derives avg packet size from conntrack counters). 7-class set with unknown is MISSING. |
| C2 | Estimate link capacity | `aciq/capacity.py` (`Measurement.saturated` L242-304, step rule L441-445, `CusumDriftDetector` L668-723) | MOCKED (no latency signal) | Throughput + queue-depth + drop signals REAL (gate check 12 measured saturation signals on the host 2026-10-21). REQUIRED latency-under-load signal MISSING (`capacity.py` docstring records probe latency as "NO signal"). Step detection is windowed ratio + emergency path; CUSUM optional, busy-gated. |
| C3 | Queueing/shaping via Linux tc | `aciq/tc.py` (HTB 1:10/1:20/1:30/1:40 + fq_codel leaves), `aciq/qdisc.py` read-back, `aciq/txn.py` transaction manager | REAL | gate 6/7/9/10 (HTB rate change, netem, CAKE root, single-class leaves) and per-flow `flower` steering gate 15-20 all PASS live 2026-10-21. |
| C4 | Verify improvement, roll back if worse | MISSING | MISSING | There is no `aciq/verifier.py` (to be written) and no controller loop module (`aciq/controller.py`, to be written). Only kernel-readback rollback exists (`txn.py:535-664`), which rolls back when the kernel state does not match the plan - not when user metrics got worse. State FSM (`shield.py` 3-state MONITOR/FAULT_PENDING/SAFE_HELD, shield.py:50-53) does not meet the required 7-state model. |
| C5 | Temporary intent + fairness | `aciq/intent.py` (device/flow target, TTL<=3600 s, weight, `to_policy_lease()` :394-404), `aciq/policy.py` floors | REAL | Lease->policy floor interaction tested; live kernel lease run evidence in data/ab_lease_42/ (seed 42; prior evidence; sibling seed runs 43-48 exist). Class-targeted intent is MISSING (Lease has no class field). |

---

## B. Modules (current state per contract)

### M1. Traffic Observer

| ID | Contract | Current artifact | Status | Notes |
|---|---|---|---|---|
| M1-a | Inputs: headers/conntrack | `aciq/flowtrack.py` (`ConntrackSource` L234-295: `ip netns exec ns conntrack -L` x3 families) | REAL | parse tests use recorded kernel line format (tests/test_flowtrack.py:31-51); conntrack reads verified live 2026-10-21 (gate 3/11/13). |
| M1-b | Outputs: 5-tuple, direction, packet sizes, IAT, bytes/s, duration, protocol | `flowtrack.py` `_Sample`/`features()` L107-213 | BROKEN | Both directions are summed into one counter and `_Sample` keeps no split (`rx_bytes` gets total, `tx_bytes`=0, L204-213) - direction ratio is meaningless from tracker-fed data. No per-packet sizes, no inter-arrival times. Byte/s + duration + protocol from counters REAL. |
| M1-c | State: create/update/evict; IPv4+IPv6 | `FlowTracker.observe()` L135-172 (counter-regression reset, 120 s idle eviction); IPv6 entries parsed by same regex | REAL | IPv6 integration verified live (gate 13). |
| M1-d | Failure handling | `ConntrackSource.read()` swallows per-family errors L290-292; counter regression treated as reset L148-155 | MOCKED | fake-runner tests only. |
| M1-e | Success: metadata only | no payload access anywhere (audit: no scapy/AF_PACKET/payload parsing in tree) | REAL (by construction) | avg packet size from conntrack counters (flowtrack.py:200-202). |

### M2. Traffic Classifier

| ID | Contract | Current artifact | Status | Notes |
|---|---|---|---|---|
| M2-1 | 7 required classes + unknown | `model.py:13-20` = 4 members (realtime_interactive, adaptive_video, bulk_transfer, leased_flow); unclassified = `cls=None` | MISSING | No gaming/software_update/cloud_backup/video_call classes. Corrections, Bridge, tc, marks, tests, dashboards all hardwire 4 classes (`test_marks.py:223` asserts exactly 4). |
| M2-2 | {class, confidence, reason} output | `Classification(flow, cls, confidence, tier, evidence)` model.py:59-67 | REAL/MOCKED | confidence+evidence structure real; tier system real. |
| M2-3 | Low confidence -> unknown + safe minimum share | `finalise()` classify.py:511-522 (abstain below 0.5 -> None); UNCLASSIFIED maps to bulk default class 1:30 (`bridge.py:582-594`) | REAL | gate 17: a rejected EF-claiming flow does not reach 1:10 (passed live). "unknown" as explicit class still missing. |
| M2-4 | User correction | `corrections.py` store (JSONL, scoped port/host, TTL 24 h, aliases), API POST/GET `/corrections` api.py:235-405, applied next tick via `ClosedLoop.apply` closedloop.py:173-182 | REAL | api-hardening tests real-store; live correction change verified at unit level; live kernel smoke of correction+enforce unknown. |
| M2-5 | Deterministic baseline; optional ML compared | rules = `classify.py`; ML = `learned.py` (hand-written softmax, 3-class synthetic set, not on live path, compares ensemble via `compare()`) | MOCKED (inadequate) | learned.py trains on hard-coded synthetic vectors, not on generated lab data; no held-out split; features leak own generator ports 5001/5002; no precision/recall/F1/calibration report vs baseline. Will be rewritten in Phase 2. |
| M2-6 | Calibration metrics | none | MISSING | `tools/eval_classifier.py` has confusion + P/R/F1 + selective accuracy, no Brier/ECE. |

### M3. Link Capacity Estimator

| ID | Contract | Current artifact | Status | Notes |
|---|---|---|---|---|
| M3-1 | Passive throughput + latency-under-load | passive counters + backlog + bottleneck telemetry (`Measurement` L191-241, `MetricsCollector` `last_counters()` metrics.py:688) | BROKEN (half) | latency-under-load probe and queue-delay-rise signal absent; docstring even records that RTT probing was tried and "NO signal" was earlier measured for the wrong probe shape. Must be re-added properly (continuous light RTT probes). |
| M3-2 | Step detection | FAST_DROP_RATIO windowed rule + streak + emergency path; optional CUSUM | MOCKED/REAL | step tests unit-level; saturation adoption verified live via gate 12 counters only indirectly. |
| M3-3 | Shaper = fraction of estimate, bounded | `build_plan()` uses whole capacity (ceil=capacity), safe-state cake at 0.95 cap | BROKEN (partially) | There is no configurable shaper-fraction path on the main plan, and no min/max shaping bounds or per-cycle rate-change magnitude cap (shield only enforces 5 s dwell, shield.py:120-129). |

### M4. Policy Engine

| ID | Contract | Current artifact | Status | Notes |
|---|---|---|---|---|
| M4-c | Explicit 7-state FSM, hysteresis/cooldown/dwell | shield.py Mode = MONITOR/FAULT_PENDING/SAFE_HELD only; dwell 5 s | BROKEN | Required INIT/NORMAL/CONGESTED/INTENT_ACTIVE/RECALIBRATING/SAFE_MODE/ROLLING_BACK is not implemented anywhere. Decision log with reason exists only for shield breaches (TransactionManager audit, txn.py:731). |
| M4-e | sum(rates)<=capacity, floors honoured | `policy.build_plan` L93-152 (+ degraded flag; vetoes in shield.veto_plan) | REAL (mocked tests) | invariant tests + prior lease runs. Floor math solid. |
| M4-1 | Anti-flap | dwell only (5 s) in shield.veto_rate | BROKEN (thin) | no hysteresis on policy decisions, no min dwell on FSM, no changes-per-minute cap. |
| M4-2 | Per-class minimum share | floor_mbps = max(2.0 Mbps, 5% capacity) policy.py:55-57 | REAL | build_plan guarantees floor unless degraded (flagged). |

### M5. Enforcer

| ID | Contract | Current artifact | Status | Notes |
|---|---|---|---|---|
| M5-1 | HTB + per-class leaf fq_codel/CAKE | tc.py build_tree with leaf param (fq_codel default; cake reachable), leaves per class | REAL | gates 6-10 live. |
| M5-2 | ifb + act_mirred ingress shaping | none | MISSING | no ifb usage anywhere in code (audited). Download-direction shaping not possible today. |
| M5-3 | Marks to hand classifier output to tc | per-flow `tc flower` filters (bridge.py:500-562) + DSCP-EF u32/flower fallback (tc.py:99,98). nftables mark/DSCP rules exist but dormant (`bridge.py:364-422` never called at runtime) | REAL (mechanism) | steering verified live gates 15-20 (v4 and v6). `fw`-mark filters are mechanically impossible on this iproute2 (documented bridge.py:44-51, asserted by test_bridge.py:237). Requirement "nftables marks to hand classifier output to tc" is currently satisfied by per-flow flower filters instead; nft-mark path stays dormant. Honest note for final report. |
| M5-4 | Snapshot before apply, rollback on failure | txn.py `_apply_locked` L363-482 records `_last_good` at commit; rollback L535-664 with 6 outomes | MOCKED + REAL | live rollback verified by tests/test_rollback_live.py evidence `docs/evidence/rollback-live-20261013.log` (2026-10-13); simulated suite re-checks logic. No snapshot is ever taken BEFORE the very first apply (rollback falls to safe state). |
| M5-5 | Bounded rate change per cycle; min/max shaping rate | only 5 s dwell limiting frequency | MISSING | magnitude bounds per cycle absent (weakens M3-3 too). |
| M5-6 | Structured decision logs | audit JSON entries with per-class rates; policy_change_log in harness.adapt_step | REAL | unit-tested; JSONL on disk from runs. |
| M5-7 | Safe state = fq_codel/CAKE no classes; make safe-reset | `force_safe()` txn.py:666-724 (cake 0.95cap -> fq_codel -> pfifo ladder, read-back verified) | REAL (live rollback tests) | Makefile missing -> `make safe-reset` MISSING. |
| M5-8 | Crash/exception/SIGTERM/SIGINT/watchdog safe reset | KeyboardInterrupt mid-rebuild triggers rollback (txn.py:397-406). No SIGTERM handler, no external watchdog. | MISSING | shield latches SAFE_HELD but nothing external forces safe state on controller death. |

### M6. Verifier / Monitor

| ID | Contract | Current artifact | Status |
|---|---|---|---|
| M6-1 | measure latency p50/95/99, jitter, loss, throughput; tc queue depth; Jain fairness | `aciq/measure.py` (percentile/jitter/loss + validity), `aciq/metrics.py` (jain_fairness :304-329, ClassCounters.backlog_bytes, cpu_fraction, max_rss) | REAL/MOCKED |
| M6-2 | before/after windows and verdict improved/not_improved/worse; worse -> rollback; no re-evaluation in cooldown | none | MISSING |
| M6-d | failure: too few samples -> NOT_MEASURED/INSUFFICIENT | measure.py validity states | REAL (mocked) |

### M7. Intent API

| ID | Contract | Current artifact | Status |
|---|---|---|---|
| M7-1/2 | create/list/cancel, TTL, max duration | `intent.py` (defaults TTL 90 s, MAX_TTL_S 3600, weight clamp 0.05-1.0), `/intent` GET/POST, `/intent/<id>` DELETE (api.py:254-280) with audit | REAL |
| M7-3 | floors never reduced | policy.build_plan floor guarantee | REAL (mocked) |
| M7-5 | class-targeted intent | Lease.target = device|flow only | MISSING |
| M7-6 | conflict rules for overlapping intents | most-recent wins per scope (request() :161-172); no cross-scope conflict rules | BROKEN (thin) |

### M8. Dashboard

| ID | Contract | Current artifact | Status |
|---|---|---|---|
| M8-1 | latency/jitter/loss/throughput/queue depth/fairness panels | dashboard.py `PANELS` six panels, inline SVG, offline, no JS | REAL (mocked) |
| M8-2 | FSM state, active policy, active intent, classifier confidence panels | summary tiles show policy/lease/classifier-range/policy_outcome | MISSING (state panel; confidence only aggregate, no per-class) |
| M8-3 | intent create/cancel + correction controls | NONE (read-only by design) | MISSING |

### M9. Experiment Runner / Reports

| ID | Contract | Current artifact | Status |
|---|---|---|---|
| M9-a | scenario/mode/seed inputs | `experiment.py` runner + `harness.py` SCENARIOS dict (4 scenarios incl. `s4_capacity_recovery`) + SystemSpec B0/B1/ACIQ, CapacityMode STATIC/INFORMED/ADAPTIVE | REAL (mocked) |
| M9-b | raw runs (config.json, samples.jsonl, workloads.json, audit.json, result.json) | data/runs/<scenario>__<system>__<mode>__seed<N> | REAL (mocked) |
| M9-c | report with mean + 95% CI, graphs, EMULATION label | report.py Markdown: mean (min-max), exact Wilcoxon, no CI, no graphs in report (dashboard SVG separate), no EMULATION tag | BROKEN (thin) |
| M9-d | 10 seeds; results/ layout; S4 intent scenario; S5 failure injection; make demo | gate used 7 seeds; no results/ dir; no S4-class/S5; no Makefile | MISSING |

---

## C. Hard constraints

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| H1 | No payload decryption/inspection | REAL by construction | classification path = conntrack counters + user corrections; audited source: no scapy/pcap/payload parsing. New observer (M1) must add a payload-free AF_PACKET test in Phase 2; sentinel-payload test to be written. |
| H2 | Linux tc or open mechanism | REAL | HTB/fq_codel/CAKE/flower verified live 2026-10-21. |
| H3 | IPv4 + IPv6 | REAL (mechanism) | conntrack v4+v6 (gate 3/11/13), IPv6 EF flower filter (gate 14), IPv6 steering (gate 18), tests/test_bridge.py ipv6 cases, corrections canonical IP handling. Port-level lease targets share this. |
| H4 | Rollback + no starvation | PART (kernel rollback REAL; metric-level "worse" rollback MISSING; floors REAL) | S4 starvation: floor maths build_plan + planned S4 experiment to be run. |
| H5 | Confidence + correction | REAL | Classification.confidence + tier; corrections full path; needs 7-class update. |
| H6 | Third-party licenses | MISSING | pip deps: none at runtime (stdlib only). docs/THIRD_PARTY_LICENSES.md (to be written). |
| H7 | Generated data + impairment settings committed | PART | generator configs implicit in testbed/workloads; no data/impairments/*.json, data/scenarios/*.json (they are cited as planned, to be written). Existing run data committed in data/. |
| H8 | Emulation labelled | MISSING (thin) | report.py has "HTB token-bucket emulation" caveat; no general EMULATION banner; docs/LIMITATIONS.md (to be written). |
| H9 | No secrets committed | REAL (clean so far) | no .env; .gitignore exists; secret scan missing (tools/secret_scan.py, to be written). |
| H10 | Bounded/observable/reversible remediation + safe reset on crash/exception/signals/watchdog | BROKEN | apply-level rollback + shield latch REAL; SIGTERM/SIGINT handlers, watchdog timeout, controller-crash safe path MISSING; per-cycle rate magnitude bounds MISSING. |

---

## D. Testbed

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| T1 | single Linux machine, root only | REAL | gate logs (Oct 7-21), host toolchain recorded in docs/evidence/phase1/environment-20261023.log. |
| T2 | namespaces + veth + bridge | PART | setup.sh creates 3 namespaces + 2 routed veth pairs; NO bridge (router L3 forwarding). Requirement says "veth pairs and a bridge". |
| T3 | clients: laptop, gaming, 3 TVs, backup/update | MISSING | setup.sh has ONE `client` namespace (secondary IPs on wan side for lease matching). Need per-device namespaces or per-device source IPs. |
| T4 | router namespace with controller + tc | REAL (tc part) | controller process runs in ns or on host? Today the controller runs on the host with `ip netns exec`, tc lives in `router`. Control path exists. |
| T5 | WAN netem+tbf/HTB, runtime-changeable | REAL | harness.set_capacity: `tc qdisc replace dev veth-w root netem rate N` verified in prior runs; gate 6 measures HTB 100->20. |
| T6 | server namespace | MISSING | traffic sinks live in wan ns (充当 server). Need a dedicated server ns per the brief. |
| T7 | dual stack | REAL | addresses + routes in setup.sh L26-46; gate v6 checks. |
| T8 | setup/teardown/reset/safe-reset scripts | PART | cleanup.sh idempotent; reset.sh/safe_reset.sh/teardown.sh (to be written). |
| T9 | generators (call 20 ms, game 60 Hz, video chunks, backup/update) | PART | call.py 50 pps = 20 ms REAL; game.py is 30 pps (brief says ~60 Hz) - adjust; video.py chunked TCP REAL; bulk.py REAL; update.py/backup.py MISSING; iperf3 used by gate only. |
| T10 | ground-truth labels | PART | generator ports are class-ambiguous by design (ports must not encode identity); labels available only for generated runs; eval corpus hand-built. Needs a labelled dataset generator (Phase 2). |
| T11 | impairment/generator configs committed | MISSING | data/impairments/, data/scenarios/ planned dirs (to be written). |
| T12 | no host network touched; idempotent cleanup | PART (honest) | cleanup kills ALL host iperf3 (`pkill -x iperf3`, cleanup.sh:4) - documented real hazard; setup/gate load kernel modules host-side (benign). Nothing else host-level. safe-reset must avoid this or scope it. |

## E. Scenarios

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| S1 | ISO download during call | REAL (mechanism) | s1_iso_during_call scenario + host_gate_s1_* evidence for b0/b1/aciq (7 seeds, 2026-10-21) + acceptance gates. FULL 10-seed rerun required at completion. |
| S2 | WAN drop 100->20 | REAL (mechanism) | s2_wan_drop + congested + tail + recovery evidence. |
| S3 | TVs + gaming | REAL (mechanism) | s3_tv_and_gaming + host_gate_aciq/b0/b1 (7 seeds). |
| S4 | Temp intent start/expire (class target) | MISSING (as new naming; old internal s4_capacity_recovery must be renamed s2b) | intent semantics exist; scenario needs to be built and run; data/ab_lease_42/ (seed 42 run, prior evidence) is evidence of intent. |
| S5 | Failure injection | MISSING | no scenario exists. Safe-state machinery exists (force_safe). |

## F. Metrics

| ID | Requirement | Status | Evidence |
|---|---|---|---|
| F1 | Classification P/R/F1 + confusion | REAL (tool) | tools/eval_classifier.py (static corpora, offline). |
| F2 | confidence calibration | MISSING | to be written. |
| F3 | capacity error + detection time | PART | percentile error computable from estimate vs true rate logged per tick (sample trace replay tests); no results/ report yet. |
| F4 | latency/jitter/loss per class, percent reduction vs baseline | REAL (mechanism) | measure.py + per-workload reports; report tables exist (mean (min-max)). CI + reduction-vs-baseline formatting to be written. |
| F5 | Jain fairness + min throughput per class | REAL (mechanism) | jain_fairness + per-class counters; fairness live test exists (gated). |
| F6 | adaptation speed, changes/min, overshoot | PART | policy_change_log exists; no post-processing summary; estimator overshoot not measured. |
| F7 | controller CPU/mem/decision-loop latency | PART | cpu_fraction + max_rss per frame; decision-loop latency unmeasured. |
| F8 | reproducibility manifest | REAL (mechanism) | run config.json + REVISION stamps; FULL manifest with seeds+versions to be written. |

## G. AI/ML rule

| ID | Requirement | Status |
|---|---|---|
| G1 | rules = baseline | REAL (rules are the live path). |
| G2 | ML compared on same held-out data | MISSING (learned.py not comparable as is: synthetic, not on generated labelled data). |
| G3 | honest outcome + no AI-theatre | MISSING pending G2. |

## H. Deliverables

| ID | Deliverable | Status |
|---|---|---|
| D1 | estimator pair (classify + capacity) | PART (7-class + latency signal missing) |
| D2 | policy engine + enforcement | PART (FSM/unbounded changes missing) |
| D3 | dashboard six metrics | REAL |
| D4 | automated B0/CAKE/ACIQ experiments | REAL (mechanism; 7 seeds; needs 10 + CI + results/) |
| D5 | intent API + dashboard control | PART (API REAL; dashboard control MISSING) |
| D6 | architecture Mermaid + exported image | MISSING |
| D7 | SETUP guide | MISSING (docs/SETUP.md to be written) |
| D8 | make demo | MISSING (no Makefile) |
| D9 | LIMITATIONS | MISSING |
| D10-D16 | README/CONCEPTS/MODULES/LICENSES/FINAL_AUDIT/test-suite/data-folder/results-folder | PART |

---

## Immediate change list for the next phases (drives the plan)

1. Phase 2: 7-class model + unknown; header-only observer (IAT + packet sizes, direction split); corrections API unchanged; labelled dataset generator; optional ML rewritten and compared.
2. Phase 3: latency-under-load estimator input; shaper-fraction config (0.90-0.95) with min/max bounds.
3. Phase 4: policy FSM module; bounded per-cycle rate change; ifb ingress path; watchdog/signal handling; safe-reset script + Makefile.
4. Phase 5: class-target intents; conflict rules.
5. Phase 6: verifier verdict + rollback-on-worse; dashboard controls and state panel.
6. Phase 7: S4/S5 scenarios; 10 seeds; results/; report with CI + EMULATION; demo.
7. Phase 8: canonical docs, diagrams export, license audit, secret scan, final audit.
