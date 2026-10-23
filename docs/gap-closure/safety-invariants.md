# Safety invariants

Covers §11. Every invariant below is enforced in `aciq/shield.py` /
`aciq/txn.py` and covered by tests. Invariants **1–4** are checked before any
kernel write; the rest are properties of the apply path.

## Pre-apply vetoes

| # | invariant | where | test |
|---|---|---|---|
| 1 | `sum(child rates) <= capacity` | `veto_plan` | `child_sum_exceeds_capacity` |
| 2 | no class below its floor (scaled when degraded) | `veto_plan` | `below_floor` |
| 3 | invalid / NaN / infinite / non-numeric rates rejected | API boundary | `test_nan_weight_is_refused` |
| 4 | capacity estimate fresh enough and non-decreasing-only | `capacity.py` | hysteresis, dwell, streak |

Rate limiting (5) is a 5 s minimum between policy changes; dwell (6) is enforced
inside the estimator; a lease (7) cannot bypass the shield because
`sync_lease` goes through `txn.apply`.

## Apply-path invariants

| # | invariant | status |
|---|---|---|
| 8 | conflicting leases produce a deterministic result | last-writer-wins per scope; tested |
| 9 | unsupported traffic gets a documented safe policy | falls to the default class; documented |
| 10 | application failure is never reported as success | `capacity_change_ok`, read-back mismatch |
| 11 | rollback restores a known, verified state | `_rollback` restores `_last_good` |
| 12 | repeated rollback failure is visible | shield enters `FAULT_PENDING` -> `SAFE_HELD`, `alarm` set |
| 13 | audit explains accepted, rejected and reverted changes | `audit.json` records the applied tree |
| 14 | recovery does not reinstall stale policy | deferred plans are rebuilt against current capacity |

## Boundary and extreme-value behaviour

- **NaN/inf**: rejected at the API boundary. A NaN plan fails every comparison
  silently, so this is a safety failure that would otherwise read as success.
- **Zero capacity**: `build_plan` returns an empty plan marked `degraded` rather
  than dividing by zero.
- **Capacity below viable**: floors scale down proportionally and `degraded` is
  set, rather than violating invariant 1.
- **Repeated refusal**: `txn.apply` returns `False` with a reason, and the reason
  reaches `result.json`. It is not retried forever.
- **Deferral**: a change inside the shield's window is deferred, not dropped,
  and is rebuilt against the link's *current* capacity when it finally applies.

## Property-style tests

The stack has no property-testing library and the prompt says to use one "where
the existing stack supports them". Instead, boundary values are enumerated
explicitly: zero, negative, NaN, inf, exactly-at-floor, exactly-at-capacity,
one-below, one-above.

## Not verified

**Real fault injection.** Every rollback and read-back test runs against
`FakeRunner`, which returns whatever the test tells it to. No test has made a
real `tc` command fail and then inspected the real kernel state. §13's scenario
list is implemented as unit tests; the kernel version is **blocked-environment**.
