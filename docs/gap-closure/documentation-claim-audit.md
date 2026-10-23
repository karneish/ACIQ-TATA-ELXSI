# Documentation and claim audit

**Status: PASS** — `tools/audit_claims.py`, exit 0.

## What the audit checks, and why it exists

Every number in this project has been wrong at least once, and each time it was
wrong in the *optimistic* direction. The audit exists to catch the next one
mechanically rather than by memory.

| check | result |
|---|---|
| constants in code vs documentation | **ok** — 4/4 match |
| evidence cited by claims is present on disk | **present** — 6/6 |
| red-flag phrases | **none found** |
| full test suite | **1174 tests, ok=True, exit 0** |

### Constants

| constant | code | documented |
|---|---|---|
| `OVERLIMIT_RATE_LIMIT` | 5000.0 | 5000.0 |
| `MIN_PAIRS_FOR_PVALUE` | 6 | 6 |
| `MAX_BODY_BYTES` | 65536 | 65536 |
| `RATE_LIMIT_WRITES` | 30 | 30 |

### Evidence cited by claims

| figure | source | present |
|---|---|---|
| p = 0.0312 | `data/matrix6` | yes |
| p = 0.015625 | `data/ab_lease_42` | yes |
| 92.6 | `docs/evidence` (gate 6, stale value) | yes |
| 92.7 | `docs/evidence` (gate 6) | yes |
| 12.92 | `docs/limitations.md` (withdrawn lease figure) | yes |
| 20 PASS | `docs/evidence` | yes |

The withdrawn lease figure is cited **as withdrawn**. It is recorded rather than
deleted, because deleting the number would remove the record that it was ever
claimed.

## Claims withdrawn in earlier rounds, still withdrawn

| withdrawn claim | why | record |
|---|---|---|
| "reduces reordering" | fixture bug — test reordered its own packets | superseded test |
| "lease preserves total throughput" | runner pressure | same |
| "+12.92% gain" | stated before the signing bug was found; +12.92% **is** p ≈ 0.0160 | `limitations.md` |
| "achieves 92.6% utilisation" | stale `avg_rtt`; on unthrottled traffic the link ran at **92.7%** | `limitations.md` |
| "all 21 checks PASS" | gate check 6 is a **MEASURED** measurement | `limitations.md` |

## Red-flag phrases

The audit rejects, as text: "significantly better", "dramatically",
"dramatic improvement", "vastly superior", "superior performance", "optimal
performance". **None found** in any source or Markdown file.

## What this audit does not do

It checks that numbers **agree**, not that they are **true**. A figure can be
consistent across the code, the docs and a log and still describe something that
was never measured — which is why every kernel-dependent claim in this
directory is written as BLOCKED with its command, rather than as a number.

## Corrections made during this audit

- `docs/PROJECT.md` overstated the lease gain; the signed Wilcoxon value
  (+27.46% to +28.92% over seven seeds) replaced it.
- gate check 6's utilisation figure was restated 92.6% → 92.7%.
- one classifier statement said "no test asserts capacity-relative bulk
  semantics". Added, then used to block the reverted Defect B fix.
