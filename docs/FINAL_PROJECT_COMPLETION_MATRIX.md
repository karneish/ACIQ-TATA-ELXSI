# Final project completion matrix — 42 requirements (final band 7c6c7235)

> Historical matrix (dev-band baseline). Live authority is `docs/REQUIREMENT_TRACEABILITY.md`; final-band outcome is `data/experiments/RESULTS_FINAL3.md` (840 runs, 130 judgeable PASS).

Statuses identical to `docs/REQUIREMENT_TRACEABILITY.md` (single source): 21
VERIFIED · 18 PARTIALLY VERIFIED · 2 IMPLEMENTED BUT UNVERIFIED · 0 MISSING ·
1 NOT APPLICABLE. Claim-allowed = the honest sentence for your academic
report. Every status change from history has a reason column.

| ID | Requirement | Implementation | Test | Experiment | Evidence | Validation | Status | Remaining work | Claim allowed |
|---|---|---|---|---|---|---|---|---|---|
| 001 | classify w/o payload-reading | header-only observe+classify | classifier suite | classify→steer chain | classify.py:117 | iterator+unit+live-chain | VERIFIED | — | classification runs without payload access |
| 002 | capacity estimation | aciq/capacity.py | unit | estimator in every run | result.json.estimator_mbps | validator: identity+numeric | PARTIALLY VERIFIED | fresh e2e | implemented; unit+replay verified; final band measured |
| 003 | shaping policy application | tc tree + readback | kernel-gated | every cell | result.json.applied_state | validator | VERIFIED | — | tc enforcement verified via readback |
| 004 | engine verifies improvement | build_report from gate | report tests | dev per-seed tables | RESULTS_dev3 | validator | PARTIALLY VERIFIED | final band | comparison machinery runs on validated data |
| 005 | temporary intent + fairness | intent lease + API/UI | unit+kernel-gated | live-once | rollback-live log:14 | unit+live-once | PARTIALLY VERIFIED | fairness-under-intent | lease works at kernel; fairness-outcome deferred |
| 006 | module decomposition | M1–M10 contracts | per-module suites | — | architecture.md/module docs | unit per module | VERIFIED | — | independently testable as specified |
| 007 | AI-vs-baseline | no model used | — | — | wiring audit | n/a | NOT APPLICABLE | — | no AI claimed; stdlib deterministic engine |
| 008 | adapt to demand change | governor bridge | governor suites | all shapes | decision ledgers | validator+gate | PARTIALLY VERIFIED | retuned shape verdicts | adapts; two shapes being retuned |
| 009 | protect interactive / bulk progress | floors+shield | invariant tests | dev band | call RTT vs cake arms table | validator | VERIFIED | fresh confirm | interactive protected; bulk keeps progress |
| 010 | S1 ISO-call scenario | harness:158 | scenario suite | final-staged | s1 family dirs | validator(n/a yet) | PARTIALLY VERIFIED | fresh band | scenario implemented; fresh run pending |
| 011 | S2 WAN drop | same | same | dev s2b + final s2 | landings 0.6–4.9 s | validator+gate | PARTIALLY VERIFIED | fresh band | drop handling demonstrated; full form pending |
| 012 | S3 TVs+gaming | same | same | s3_stress now | dev readouts | validator | PARTIALLY VERIFIED | fresh band | stress form validated; TV form pending |
| 013 | no decryption | structural | — | — | audit | static | VERIFIED | — | no payload decryption path |
| 014 | tc/open enforcement | tc only | readback | all cells | artifacts | validator | VERIFIED | — | open tc used exclusively |
| 015 | IPv4+IPv6 | v6 observe/enforce; no v6 classify | v6 suite | — | WIRING_AUDIT:117 | unit | PARTIALLY VERIFIED | v6 classify decision | IPv6 observe/shape verified; classification IPv4-only |
| 016 | rollback | txn+watchdog | rollback suites | live-once | rollback log | unit+live | VERIFIED | — | rollback verified on kernel once |
| 017 | no starvation of bulk/low-priority | floors/scale | invariant tests | dev band | floors held in counters | validator | PARTIALLY VERIFIED | measured readout | floor guarantee tested; measured outcome pending |
| 018 | confidence exposure | per-class conf | unit | per sample | classify.py:117 | unit | VERIFIED | — | confidence exposed (not calibrated — documented) |
| 019 | correction support | corrections.py | unit | corpus | kiosk mapping | unit | VERIFIED | — | correction path tested |
| 020 | licences | LICENSE/licenses.md | — | — | files | static | VERIFIED | — | documented |
| 021 | data+impairment settings included | data/baselines/v0/SHA256SUMS | — | band | config.json+SHA256SUMS | validator | VERIFIED | — | config+data reproducible |
| 022 | emulation labelling | report banner | — | — | generator | unit | VERIFIED | — | every report labelled |
| 023 | no real secrets | guard scan | guard suite | — | scan clean | static | VERIFIED | — | no credentials committed |
| 024 | bounded remediation/safe state | FAULT ladder | txn suite | live-once | txn.py | unit+live | VERIFIED | — | failure → known-safe scratch state |
| 025 | prototype boundary | limitations.md | — | — | committed | static | VERIFIED | — | boundary documented |
| 026 | dashboard 6 metrics | dashboards.py renderer | 26 UI tests | dashboard_r3 render | dashboard_r3/dashboard.html + provenance.json | render-validated | PARTIALLY VERIFIED | unavailable-state test suite | six metrics render; unavailability states tested partially |
| 027 | automated experiments | run_experiments | suite | dev band | runs_dev3 | validator | VERIFIED | final band | harness executes paired arms automatically |
| 028 | architecture diagram | docs diagrams | — | — | committed | static | VERIFIED | — | diagrams present (text-render cosmetic nit) |
| 029 | setup guide | docs/setup.md | — | — | version conflict | static | PARTIALLY VERIFIED | fixed this pass | guide functional after version fix |
| 030 | scripted demo | demo.sh + tools/host_gate.sh | — | host_gate 3 revs | ACIQ_COMPLETE:435 | partial | PARTIALLY VERIFIED | execute+log demo at pinned rev | demo harness exists and has committed historical runs; fresh log pending |
| 031 | known limitations | limitations.md | — | — | banner | static | VERIFIED | — | documented |
| 032 | classification accuracy | eval harness | eval suite | corpus logs 10-23..25 | eval.json (no rev stamp) | unit+historical | PARTIALLY VERIFIED | stamped re-eval | measured on committed corpus; revision invisible |
| 033 | estimation accuracy | estimator | unit | gate artifact | final-validation:16 | unit+replay | PARTIALLY VERIFIED | fresh e2e | clamp verified; final band measured |
| 034 | latency reduction | call p50/p95 | suite | dev band | EVAL tables | validator | PARTIALLY VERIFIED | final band + README:9 fix | measured medians reported; full-band claim pending |
| 035 | jitter reduction | call jitter | suite | dev band | tables | validator | PARTIALLY VERIFIED | final band | measured; pending |
| 036 | loss reduction | loss_ratio | suite | dev band | tables | validator | PARTIALLY VERIFIED | final band | measured; pending |
| 037 | fairness measured | jain index | fairness-live registered (no run record) | none live | no log | invariant only | PARTIALLY VERIFIED | live measurement | invariant verified; live measurement absent |
| 038 | adaptation speed | retuned governor | 34 governor tests | step_50 6/10 + s7_up 8/8 | verify_round3 | gate+validator | IMPLEMENTED BUT UNVERIFIED | retuned verdicts | implemented+unit; speed claims withheld |
| 039 | policy stability | same | same | ledgers | ratchet/overshoot marks | gate | IMPLEMENTED BUT UNVERIFIED | retuned verdicts | implemented+unit; stability claims withheld |
| 040 | CPU overhead | resources dict | suite | all cells | result.json.resources | validator | VERIFIED | — | measured + reported per run |
| 041 | reproducibility | REVISION+SHA256SUMS+validator | validator tests | band | REPRODUCIBILITY_REPORT | validator | VERIFIED | re-run equivalence | infrastructure+stamps verified |
| 042 | clarity of results | NOT_AVAILABLE semantics | suite | artifacts | reports/ | validator | VERIFIED | — | honest reporting structure |

## Status-change reasons (from last audit round)

- REQ-005 V→PV: live log contains lease/rollback only, no fairness-outcome under intent.
- REQ-026 V→PV: only artifact had "no data" panels; fresh render (dashboard_r3) is populated — kept PV until the unavailable-states test suite exists.
- REQ-030 V→PV: no fresh end-to-end demo log; host_gate path error corrected (it exists at tools/).
- REQ-032 V→PV: eval.json carries no revision stamp; current-rev applicability rests on unchanged code path.
- REQ-038/039 remain IBU: retune (7c6c7235) awaits its band.

Rules honored: no gate constants changed; retune declared BEFORE the re-run (round3-params.md retune #2); final band NOT RUN; suite 1498 OK at 7c6c7235.
