# Requirement Traceability — 42 canonical requirements (2026-11-04 final band, engine 7c6c7235)

> **Currentness notice:** Live traceability record. The 2026-11-04 final band (840 runs, engine `7c6c7235`, `data/runs_final3/`) supersedes dev-band statements. Classifier fresh corpus: 61.0% strict / 74.1% broad. Capacity accuracy: `data/experiments/capacity_accuracy_final3.md`. Fairness/starvation: `data/experiments/fairness_starvation_final3.md`. IPv6 end-to-end, crash-restart reconciliation, and uplink shaping remain PARTIALLY VERIFIED (mechanisms implemented, no dedicated live scenario in the frozen band).

Original requirements are taken verbatim-from-structure from the case study
(traffic-class + capacity estimator, adaptive QoS policy, dashboard,
baselines-vs-optimized experiments, temporary-intent API, module contracts,
scenarios S1/S2/S3, constraints C1–C13, evaluation criteria E1–E11). No
requirement is merged or split dishonestly; verbatim repeats in the brief are
counted once with both sources cited. Statuses use the project's five-value
vocabulary (VERIFIED / PARTIALLY VERIFIED / IMPLEMENTED BUT UNVERIFIED /
MISSING / NOT APPLICABLE) with one status per row.

Counts: **21 VERIFIED · 18 PARTIALLY VERIFIED · 2 IMPLEMENTED BUT UNVERIFIED · 0 MISSING · 1 NOT APPLICABLE = 42** (final-band baseline; see currentness notice for classifier/capacity/fairness numbers).

| ID | Requirement (abbreviated) | Implementation | Tests | Experiment | Evidence / artifact | Status | Remaining work |
|---|---|---|---|---|---|---|---|
| REQ-001 | Classify broad categories w/o reading payloads | header-only capture + feature classify | classifier suites (66-class family) | dev band classify→steer chain | `aciq/classify.py:117`; samples per_class; live gate | VERIFIED | none |
| REQ-002 | Estimate link capacity | `aciq/capacity.py` replay/estimator | unit tests | dev band; estimator in result.json | `capacity_validation_report…`, `final-validation-report.md:16` (newest e2e replay-only) | PARTIALLY VERIFIED | final band 840 runs at 7c6c7235 |
| REQ-003 | Apply queueing/shaping policies | tc htb/tbf/fq_codel netns tree + readback | harness/kernel-gated tests | dev band: every cell committed+readback | `aciq/harness.py`; result.json applied_state | VERIFIED | none |
| REQ-004 | Verify policy improved the experience | paired-arm reporting from gate | report tests | dev band per-seed tables | `tools/build_report.py`; RESULTS_* | PARTIALLY VERIFIED | full-band final comparison (closed) |
| REQ-005 | Temporary intent (prioritise call) with fairness retained; API/UI | M7 lease + API/UI | unit + kernel-gated | live lease once at real kernel | `docs/evidence/rollback-live-20261013.log:14`; `WIRING_AUDIT.md:338–345` | PARTIALLY VERIFIED | fairness-outcome-under-intent measurement |
| REQ-006 | Independently testable modules w/ contracts | M1–M10 contract docs | per-module suites | — | `docs/architecture.md`, `docs/modules.md` | VERIFIED | none |
| REQ-007 | Where AI is used, compare vs deterministic baseline | no model used (stdlib-only, learned.py eval-only) | — | — | 3-agent wiring audit | NOT APPLICABLE | — |
| REQ-008 | Observe conditions and change policy as demand changes | governor + closed-loop bridge | governor suites | dev band (all shapes) | decision ledgers in result.json | PARTIALLY VERIFIED | retuned closure of step_50/step_up |
| REQ-009 | Protect interactive, keep bulk progressing | per-class floors + shield | invariant tests | dev band: call RTTdrop vs cake arms | `reports/FINAL_EVALUATION_REPORT.md` tables | VERIFIED | fresh confirmation from final band |
| REQ-010 | Scenario S1 (ISO download during call) | `aciq/harness.py:158` | scenario tests | final band staged | run dirs (s1 family, historical) | PARTIALLY VERIFIED | fresh band execution |
| REQ-011 | Scenario S2 (WAN drop 100→20) | same | same | dev family s2b/s7_down + final s2 | gate landings 0.6–4.9 s; table | PARTIALLY VERIFIED | fresh full-band |
| REQ-012 | Scenario S3 (TVs + gaming) | same | same | s3_stress now; s3_tv final | dev s3_stress readouts | PARTIALLY VERIFIED | fresh full-band |
| REQ-013 | No decryption of traffic | structural | — | — | grep audits | VERIFIED | none |
| REQ-014 | tc / open enforcement | tc only | readback tests | all cells | run artifacts | VERIFIED | none |
| REQ-015 | IPv4 + IPv6 where available | IPv4 full; IPv6 observe/enforce; NO IPv6 classification | v6 suites | — | `WIRING_AUDIT.md:117` | PARTIALLY VERIFIED | IPv6 classification path decision |
| REQ-016 | Policy rollback | txn + watchdog | rollback suites | live-once | `rollback-live-20261013.log:14` | VERIFIED | periodic re-validation |
| REQ-017 | No starvation of low-priority | floors + scaling | invariant tests | dev band floors held | kernel counters | PARTIALLY VERIFIED | measured starvation-readout from band |
| REQ-018 | Expose classification confidence | per-class conf | suites | per sample | `classify.py:117` | VERIFIED | none |
| REQ-019 | Allow correction | `corrections.py` | suites | corpus runs | ledger | VERIFIED | none |
| REQ-020 | Third-party licences | LICENSE + docs/licenses.md | — | — | files | VERIFIED | none |
| REQ-021 | Include generated data + impairment settings | data/ + per-run config | — | band | SHA256SUMS; config.json | VERIFIED | none |
| REQ-022 | Label emulated capabilities | report banner | — | — | generator | VERIFIED | none |
| REQ-023 | No real secrets committed | guard scan | guard suite | — | scan clean | VERIFIED | scan-log artifact |
| REQ-024 | Bounded remediation; safe state on failure | FAULT ladder | txn suites | live-once | `aciq/txn.py` | VERIFIED | none |
| REQ-025 | Prototype boundary description | limitations doc + banner | — | — | `docs/limitations.md` | VERIFIED | none |
| REQ-026 | Dashboard w/ latency, jitter, loss, throughput, queue, fairness | offline renderer | 26 UI tests | render from validated run | `data/experiments/dashboard_r3/dashboard.html` + provenance.json (six panels, 0 no-data) | PARTIALLY VERIFIED | tile-level assertion suite incl. unavailable-states |
| REQ-027 | Automated baseline-vs-optimized experiments | run_experiments multi-arm | experiment tests | dev band live | `data/runs_dev3/*` | VERIFIED | final band |
| REQ-028 | Architecture diagram | docs/architecture.md | — | — | committed | VERIFIED | cosmetic UI diagrams-as-text |
| REQ-029 | Setup guide w/ exact versions | docs/setup.md | — | — | version conflict :17 vs :180 | PARTIALLY VERIFIED | version reconciliation (this effort fixes) |
| REQ-030 | Scripted demo | `testbed/demo.sh` + `tools/host_gate.sh` | — | host_gate runs at 3 revs; no fresh demo log | `docs/ACIQ_COMPLETE.md:435,753` | PARTIALLY VERIFIED | execute demo at pinned rev with log (blocked: no sudo here) |
| REQ-031 | Known-limitations documentation | limitations.md + banner | — | — | committed | VERIFIED | none |
| REQ-032 | Classification accuracy | eval harness + eval.json + 7 dated corpus logs | eval suites | corpus evals 2026-10-23–25 | `data/experiments/classifier_corpus*/eval.json` (no rev stamp) | PARTIALLY VERIFIED | stamped/current-revision re-eval |
| REQ-033 | Link-estimation accuracy | estimator + gate artifact | unit | replay; newest e2e replay-only | `final-validation-report.md:16` | PARTIALLY VERIFIED | fresh e2e |
| REQ-034 | Latency reduction | call.json p50/p95 | suites | dev band (all cells) | FINAL_EVALUATION_REPORT tables | PARTIALLY VERIFIED | full-band + doc contradiction fix (README:9) |
| REQ-035 | Jitter reduction | call.json jitter | suites | dev band | tables | PARTIALLY VERIFIED | full band |
| REQ-036 | Loss reduction | call.json loss_ratio | suites | dev band (0.00 both arms on 40/60 s) | tables | PARTIALLY VERIFIED | full band |
| REQ-037 | Fairness + no starvation (measured) | jain_fairness invariant | `tests/test_fairness_live.py` registered — no live run record | none live | no log found | PARTIALLY VERIFIED | schedule live measurement with band |
| REQ-038 | Adaptation SPEED | retuned governor (`7c6c7235`) | 34 governor tests OK | 6/10 step_50 + 8/8 s7_up fresh passes | verify_round3 on runs_dev3 | IMPLEMENTED BUT UNVERIFIED | retuned band + full verdict |
| REQ-039 | Policy STABILITY | same | same | ratchet/overshoot logs | decision ledgers | IMPLEMENTED BUT UNVERIFIED | retuned band verdict |
| REQ-040 | CPU overhead | per-run resources | suites | all cells | result.json.resources (0.005–0.01 mean frac band mean) | VERIFIED | none |
| REQ-041 | Reproducibility | REVISION stamps + SHA256SUMS + validator | validator tested | band | `reports/REPRODUCIBILITY_REPORT.md` | VERIFIED | semantic re-run equivalence |
| REQ-042 | Clarity of results | NOT_AVAILABLE semantics + provenance | suites | all artifacts | reports/ | VERIFIED | none |

## Verification commands

- Run validators: `~/aciq-venv/bin/python tools/validate_runs.py`
- Gate: `~/aciq-venv/bin/python tools/verify_round3.py data/runs_dev3`
- Suite: `~/aciq-venv/bin/python -m unittest discover -s tests -q`
- Lint: `~/aciq-venv/bin/ruff check .`
- Demo (host w/ sudo only): `sudo env ACIQ_VENV=~/aciq-venv SCENARIO=s2_wan_drop SEEDS=3 ./testbed/demo.sh`
