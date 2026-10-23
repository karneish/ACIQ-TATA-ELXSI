# Master audit — final gap-closure pass

Revision under audit: **`c5da3fd956069fc70a12eb48054a4f2cd138b754`** (`main`, `TATA-ELXSI/`).
Environment: Linux 7.1.5, Python 3.13.15, `uid=1000`, `CapEff=0`, **no `tc`/`ip`,
no `sudo`, user namespaces denied** — all live-kernel work is `BLOCKED_BY_ENVIRONMENT`.

Every entry has a unique ID used consistently in the plan, tests, change log and
final report. Status values: `FIXED_AND_VERIFIED` · `IMPLEMENTED — VERIFICATION
BLOCKED` · `PARTIALLY ADDRESSED` · `UNRESOLVED` · `NOT APPLICABLE`.

---

## Audit matrix

| ID | Area | Current behavior | Evidence | Defect / uncertainty | Required correction | Verification method | Status |
|---|---|---|---|---|---|---|---|
| A-001 | Latency semantics | Probe measures `recv_mono_s − sent_mono_s` on one monotonic clock in one process | `testbed/workloads/udpx.py:115,266-268,336-338`; `aciq/measure.py:25-28` documents it as **RTT** | Prior pass mislabelled the same quantity **one-way delay** in `tail_analysis.py:8`, `ACIQ_COMPLETE.md:61,1018,1078,1498`, `PROJECT_REPORT.md:47,956` | Rename every occurrence to RTT; state no synchronised-clock one-way measurement exists | `test_measure.py`, new doc assertions, grep for "one-way" | `FIXED_AND_VERIFIED` |
| A-002 | Test-count arithmetic | Report says "1171 collected, 1171 passed, 10 skipped" | `python3 -m unittest discover` → `Ran 1174 tests … OK (skipped=10)`; tiny experiment confirms `Ran` **includes** skips | Internally contradictory: cannot be 1171 passed **and** 10 skipped of 1171 total | Canonical summary: 1174 collected = 1164 passed + 10 skipped + 0 failed | Reproduced command output; `tests/test_acceptance.py` | `FIXED_AND_VERIFIED` |
| A-003 | API security count | Doc says 35 in some places, 38 in others | `python3 -m unittest tests.test_api_security` → `Ran 38`; 38 `def test_` | Inconsistent counting method across docs | Use 38 everywhere; 38 cases, 0 skipped | Reproduced command output | `FIXED_AND_VERIFIED` |
| A-004 | Capacity estimator error | Matrix row 21 claims "within 4%" | Per-seed `estimator_mbps` 20.57…20.65 vs true 20 → max error **3.25%** | Claim understates the true maximum | Change to "within 3.3%"; publish per-seed errors | `tools/reconcile_results.py` extended | `FIXED_AND_VERIFIED` |
| A-005 | Tail statistic labelling | Pooled transition/steady numbers | `tail_analysis.py` output reproduces 61.36/103.72/117.27 and 1.14/2.17/31.17 | Values correct; population not stated as *pooled packet-level* vs *median of runs* | Label as pooled packet-level; give n and run count | `test_reconcile_results.py` | `FIXED_AND_VERIFIED` |
| A-006 | Classifier metric definitions | "100% accuracy on labelled, macro-F1 0.952" | `tools/eval_classifier.py`, `classifier-evaluation.json` | Coverage / selective / end-to-end accuracy not all defined with abstention policy | Publish coverage, selective accuracy, end-to-end accuracy, macro-F1 with stated denominators | Regenerate artifact; `test_eval_classifier.py` | `FIXED_AND_VERIFIED` |
| A-007 | Adaptation-timing events | "convergence ≤1 tick" vs "settles 4–5 s" | `capacity.py`, `experiment.py` | Detection / convergence / decision / application / recovery are distinct events not separately defined in one place | Add event-definition table | `test_capacity.py`, doc | `FIXED_AND_VERIFIED` |
| A-008 | Current-revision evidence | Headline congested data is `ce53da12`; light is `fc65349e` | `data/*/REVISION` files; recovery run is `c5da3fd9` | Historical results must not read as current-revision | Reproducibility matrix; label each artifact's revision | `data/*/REVISION`; doc | `FIXED_AND_VERIFIED` — the current-revision run is now committed under `data/host_gate_*/` (revision `c5da3fd9`) and every published number is re-derived from it |
| A-009 | Soak-test classification | "30-minute stability" gate | `offline_soak.py`, `offline-soak-30min.json` | An offline replay must not be called a live/kernel soak | Classify explicitly as offline replay | Doc; `test_offline_soak.py` | `FIXED_AND_VERIFIED` |
| A-010 | Policy floor wording | "guaranteed floor regardless of load" | `aciq/policy.py` `build_plan` scales floors, sets `degraded=True` | Wording contradicted implementation | "feasible floor, `degraded` reported" | `test_policy.py` | `FIXED_AND_VERIFIED` |
| A-011 | One-way vs half-RTT | Any "÷2" latency claim | grep | none found | none | grep | `NOT_APPLICABLE` |
| A-012 | Pooled vs median p95 | Pooled packet p95 ≠ median of 7 run p95 | `reconcile_results.py` vs `tail_analysis.py` | The two must not be presented as interchangeable | State estimator for each table | `test_reconcile_results.py` | `FIXED_AND_VERIFIED` |
| A-013 | Live-kernel enforcement | `tc` application + read-back | `aciq/tc.py`, `qdisc.py`, `harness.py`; `test_enforce.py` | Cannot execute here | Record `BLOCKED_BY_ENVIRONMENT`, give reproduction command | acceptance phase 6 | `IMPLEMENTED — VERIFICATION BLOCKED` |
| A-014 | Rollback guarantees | rollback on read-back mismatch | `test_rollback*.py` | Atomicity must not be over-claimed | Document exact guarantees; historical evidence labelled | `test_rollback_live_sim.py` | `FIXED_AND_VERIFIED` |
| A-015 | Deployment readiness | API auth/bind/limit/audit verified; TLS/per-role absent | `aciq/api.py`, `api-security-validation.md` | Readiness not stated as a labelled checklist | Add deployment-readiness checklist | `tests/test_api_security.py`; §12.8 | `FIXED_AND_VERIFIED` |
| A-016 | Benchmark significance | Exact Wilcoxon p-values published; effect size absent | `aciq/report.py::exact_wilcoxon`; `data/COMPARISON.md` | A p-value alone hides effect uniformity at small n | Add rank-biserial effect size; publish exact p per metric | `test_experiment.py::test_exact_wilcoxon_reports_effect_size` | `FIXED_AND_VERIFIED` |

---

## Baseline vs final (to be filled at Phase 15)

| item | baseline | final |
|---|---|---|
| collected / passed / skipped | 1171 / (claimed 1171) / 10 | 1174 / 1164 / 10 |
| API security | 35 or 38 (inconsistent) | 38 |
| estimator error bound | "within 4%" | "within 3.3%" |
| latency label | "one-way delay" in 6 places | "RTT" |
| acceptance | PASS 10 / FAIL 0 / BLOCKED 7 | PASS 10 / FAIL 0 / BLOCKED 7 (confirmed) |
| classifier metrics | coverage/selective/end-to-end not separated | independent: coverage 0.90, selective 1.00, strict end-to-end 0.90, macro-F1 0.952 |
| benchmark significance | exact p only | exact p + rank-biserial effect size |
