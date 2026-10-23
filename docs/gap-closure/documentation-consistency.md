# Documentation consistency matrix

Revision: **`c5da3fd956069fc70a12eb48054a4f2cd138b754`**. Every figure below was
re-derived from the current tree, not copied from an earlier pass.

## Canonical vs historical documents

Some documents are **living** (they must track the current revision) and some are
**dated snapshots** (a record of what was true at an earlier revision, kept
frozen on purpose). A "27 tests" line in a snapshot is not a bug; the same line
in a living document is. The matrix says which is which.

| document | kind | authority |
|---|---|---|
| `docs/ACIQ_COMPLETE.md` | living | primary deliverable |
| `docs/PROJECT_REPORT.md` | living | kept in sync with `ACIQ_COMPLETE.md` |
| `docs/gap-closure/master-audit.md` | living | this pass's audit matrix |
| `docs/gap-closure/acceptance-harness.md` | living | current harness output |
| `docs/gap-closure/api-security-validation.md` | living | current API-security facts |
| `docs/gap-closure/documentation-claim-audit.md` | living | claim-audit summary |
| `docs/gap-closure/novelty-assessment.md` | living | novelty statement |
| `docs/gap-closure/{measurement-methodology,metric-integrity}.md` | living | definitions |
| `docs/gap-closure/post-705cdd5-baseline.md` | snapshot (`705cdd5`) | frozen record |
| `docs/gap-closure/final-validation-report.md` | snapshot (pre-audit) | frozen record |
| `docs/gap-closure/real-kernel-acceptance.md` | snapshot | frozen record |
| `docs/gap-closure/final-state-baseline.md` | snapshot | frozen record |
| `docs/gap-closure/baseline-audit.md` | snapshot | frozen record |

Snapshots are **not** edited to match later counts: rewriting a record of what
was measured is exactly the behavior this project exists to avoid. Where a
snapshot could be misread as current, the living matrix above names its revision.

## Figures checked for agreement (living documents)

| figure | authoritative source | value | `ACIQ_COMPLETE.md` | `PROJECT_REPORT.md` | status |
|---|---|---|---|---|---|
| total tests | `python3 -m unittest discover` | 1174 collected / 1162 passed / 12 skipped | 1174 | 1174 | **consistent** |
| API-security cases | `python3 -m unittest tests.test_api_security` | 38, 0 skipped | 38 | 38 | **consistent** |
| acceptance result | `python3 tools/acceptance.py` | PASS 22 / FAIL 1 / BLOCKED 0 / NOT RUN 0 | PASS 22 / FAIL 1 | PASS 22 / FAIL 1 | **consistent** |
| estimator worst error | `tools/reconcile_results.py` | 3.25 % (seed 48) | "within 3.3%" | "within 3.3%" | **consistent** |
| latency quantity | `testbed/workloads/udpx.py`, `aciq/measure.py` | RTT | RTT | RTT | **consistent** |
| p50 headline (ACIQ) | `data/host_gate_congested_aciq` | 1.20 ms | 1.20 | 1.20 | **consistent** |
| p50 headline (FIFO) | `data/host_gate_congested_b0_fifo` | 81.14 ms | 81.14 | 81.14 | **consistent** |
| loss (ACIQ / FIFO) | raw `call.json` | 0.10 % / 0.60 % | 0.10 / 0.60 | 0.10 / 0.60 | **consistent** |
| classifier independent corpus | `classifier-evaluation.json` | coverage 0.90 / selective 1.00 / strict 0.90 / macro-F1 0.952 | same | same | **consistent** |
| exact p (p50/p95/jitter/loss) | `aciq/report.py::exact_wilcoxon` | 0.0156 | 0.0156 | 0.0156 | **consistent** |
| exact p (p99 vs FIFO / CAKE) | same | 1.0000 / 0.0781 | 1.0000 / 0.0781 | 1.0000 / 0.0781 | **consistent** |
| soak RSS drift | `offline-soak-30min.json` | 0.38 MB over 277 106 ticks | 0.38 | 0.38 | **consistent** |
| `MIN_TESTS` guard | `tools/acceptance.py` | 1160 | 1160 | 1160 | **consistent** |

## Gate that enforces this mechanically

`tools/audit_claims.py` re-derives the four constants, checks that every cited
evidence path is present on disk, scans for red-flag phrases, and runs the full
suite. It exits non-zero on any mismatch, so drift in a living document fails
the acceptance run (`phase 7: claim audit`) rather than surviving silently.

## Figures corrected in this pass

| figure | was | now | where |
|---|---|---|---|
| latency label | "one-way delay" | "RTT" | `ACIQ_COMPLETE.md` (5), `PROJECT_REPORT.md` (2), `tail_analysis.py` (2) |
| test counts | 1171 / 1161 | 1174 / 1164 | living docs + harness doc |
| API-security count | 35, 27 | 38 | both living docs + `api-security-validation.md` |
| estimator bound | "within 4%" | "within 3.3%" | both living docs |
| acceptance status | PASS 8 | PASS 22 / FAIL 1 | §18.2 + harness doc |
| `MIN_TESTS` (report) | 1100 | 1160 | `PROJECT_REPORT.md` |
| claim-audit suite size | 757 | 1174 | `documentation-claim-audit.md` |
| classifier metrics | one accuracy | coverage + selective + end-to-end | both living docs |
