# Acceptance harness audit

`tools/acceptance.py` was audited before being trusted, per the brief. One real
defect was found and fixed; the rest is recorded below as design.

## What it runs

| phase | gates | needs root? |
|---|---|---|
| 1 | full suite (`discover`) | no |
| 2 | metric integrity | no |
| 3 | API security | no |
| 4 | classifier evaluation | no |
| 5 | control-plane benchmark | no |
| 6 | testbed gate, live enforcement, rollback under real `tc` failure, live adaptation, FIFO/CAKE/ACIQ, 30-minute stability, **live rollback verification** | **yes** |
| 7 | claim audit | no |

Phase ordering is dependency order: a later phase cannot report success on a
broken base, and the claim audit runs last so it sees the final tree.

## DEFECT FOUND — a shrinking suite passed silently

The harness **recorded** the collected test count and **never checked it**:

```python
n = 0
for line in txt.splitlines():
    if line.startswith("Ran ") and " test" in line:
        n = int(line.split()[1])
record("unit+integration+socket", PASS if rc == 0 else FAIL,
       f"{n} tests, exit {rc}", "unittest.log")
```

`n` went into a display string and nothing else. A suite that exits 0 while
collection has shrunk — a broken import in one test module, or a deleted module
entirely — produced a **green acceptance run**. The count was being printed as
though it were evidence while never being used as evidence.

This is the same class of error as the rollback defect: something recorded,
formatted, and displayed, but never actually consulted.

**Fixed** by `suite_verdict()`, which fails when the collected count falls below
`MIN_TESTS` (809, the count this suite actually collects). A green run of three
tests is now a FAIL with `only 3 tests collected, floor is 809`.

**Regression-tested** in `tests/test_acceptance.py::test_a_shrinking_suite_must_not_pass_silently`,
alongside the cases it must *not* break: exactly-at-the-floor passes, a non-zero
exit fails, a `FAILED (...)` line fails even with exit 0, and skips are reported
without failing the run.

## Reviewed and found sound

| question | finding |
|---|---|
| Can it report `complete` after skipping a mandatory gate? | **No.** `complete` is computed as `counts[BLOCKED] == 0`, not asserted. |
| Does it trust the exit code alone? | Now checks exit code **and** the `OK`/`FAILED` line **and** the count. |
| Are BLOCKED and FAIL conflated? | No — distinct counters, distinct reasons. |
| Does it verify command exit codes? | Yes, every phase uses the return code. |
| Machine-readable output? | `acceptance.json`, per gate, with status, detail and log path. |
| Human-readable output? | Yes, phased and colour-free. |
| Tied to the revision? | Yes — `artifacts/validation/<short-rev>/`, and `revision` recorded in the JSON. |
| Cleanup? | The harness itself creates no kernel state. `gate.sh` owns its own cleanup (gate check 20). |
| Partial failure handling? | Each phase is independent; one failing phase does not abort the run, so the operator gets the full picture. |
| Does a missing binary crash it? | No — `run()` returns `(127, msg)`. Regression-tested. |

## One honest limitation

Phase 6 requires **all** of `ip`, `tc` and root, and skips the whole phase
otherwise. That is correct for this sandbox but coarse: a host with `tc` and
root but a missing `iperf3` would lose the entire phase rather than the one gate
that actually needs it. Recorded rather than fixed — splitting the phase needs a
real host to validate against, and guessing would be worse than the current
honest all-or-nothing.
