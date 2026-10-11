# Final release readiness

**Revision:** see `git log -1` · **Suite:** 832 pass, 0 fail, 6 skipped · **Claim audit:** exit 0

## Verdict

# VALIDATION BLOCKED

Not **NOT READY**, and the difference is deliberate.

**NOT READY** would assert something is known to be broken. Nothing is. Every
dimension that could be checked, was checked and passed, and this change set
closed the one real code defect in scope.

**VALIDATION BLOCKED** asserts what is actually true: the environment prevents
required tests, so the available evidence is insufficient to determine whether
the system meets its mandatory requirements. That is a statement about this
shell — PID 1 is `bwrap`, `CapEff` is `0000000000000000`, `ip`/`tc`/`iperf3` are
absent at package level, `unshare --net` returns `EPERM` — and not about the
software.

**READY FOR RELEASE is unavailable** regardless of test count: live kernel
enforcement and kernel-verified rollback are mandatory and unrun.

## A. Repository state

| | |
|---|---|
| path | `~/Desktop/Full-projects/TATA-ELXSI` |
| branch | `main` |
| HEAD | `507ed7af` |
| working tree (TATA-ELXSI) | clean at time of report |
| public remote | `aciq` → `karneish/ACIQ-TATA-ELXSI` |
| parent remote | `origin` → `karneish/Full-projects` — **never pushed** |
| remote HEAD | `705cdd5` — **4 commits behind, unmodified** |

Local commits not on the public remote:

```
507ed7af  Verify rollback by reading the kernel back, not by trusting the replay
17685a45  Document post-705cdd5 validation: 15 deliverables, acceptance harness
89b87758  Classifier: deny an EF claim that contradicts observed behaviour
```

`705cdd5` is the *exported* equivalent of `6a22208c`; the export replays history,
so hashes differ while the trees are identical.

## B. Rollback verification

**The defect.** `_rollback()` replayed the last known-good command list and
returned `True` unconditionally — every `runner.run()` result discarded. A
rollback that restored nothing was indistinguishable from one that restored
everything. The project already read the kernel back after *applying* a policy;
it never read it back after *undoing* one, which is the direction where failure
is silent.

**The change.** `507ed7af`. `verified` is now the only outcome that sets
`rolled_back=True`; five others are distinguished (`commands_failed`,
`verification_failed`, `unverifiable`, `no_target`, `partial`). The comparison
target is the canonical state **observed** at commit, not a re-rendering of
intent. `force_safe()` is verified too, by reading the root qdisc — the safe
state is class-free, so `class show` cannot distinguish it from no qdisc at all.

**Unit-test evidence.** 33 tests in `tests/test_rollback.py`, **all mocked and
labelled as such**, covering all 14 required scenarios.

**A third defect, found this pass by tracing the baseline's provenance (7.1).**
`verify()` tolerates fields the reader cannot see and commits anyway, so a
baseline captured under a reader that reports no rates is structurally incapable
of failing a comparison — and rollback reported `verified` having compared
**zero** fields, with `rolled_back=True`. Same family as the original
`return True`, one level deeper, invisible to every test using a normal reader.
Now zero comparable pairs is `unverifiable`. The fix's first version introduced
a false negative on `1:10` vs `1:0010`, caught immediately by an existing test. They have teeth: the
original defect was reinstated and **14 of the 29 failed**, then the fix was
restored and all 29 pass.

**Live integration evidence. NONE.** `tests/test_rollback_live.py` contains 6
tests with no mocks — isolated network namespace, fault injected by genuinely not
sending a command, state read back with `tc -j` called directly rather than
through `TransactionManager`. **All 6 skip here.**

**Read-back comparison rules.** Kernel rounding within 1% absorbed; `1:0010` vs
`1:10` normalised. Those are the only two equivalences. Missing class = mismatch;
unexpected class = `residual` mismatch; field the reader cannot see =
`unverifiable`, never a pass.

**Remaining failure modes.** A rollback that succeeds but leaves residue the
class reader cannot see (e.g. a filter) is reported `partial`, not verified — the
honest answer, since `class show` cannot see filters at all. Cleanup removes the
root qdisc on the target device and cannot prove it did not remove a qdisc owned
by another subsystem.

## C. Test results

| suite | command | exit | count |
|---|---|---|---|
| full | `python3 -m unittest discover -s tests -t .` | 0 | **832 pass, 0 fail, 6 skipped** |
| rollback (mocked) | `python3 -m unittest tests.test_rollback` | 0 | 33 pass |
| rollback (live) | `sudo python3 -m unittest tests.test_rollback_live -v` | — | **6 skipped — and 5 defects found on first real run** |
| live-vs-double | `python3 -m unittest tests.test_rollback_live_sim` | 0 | 6 pass |
| harness | `python3 -m unittest tests.test_acceptance` | 0 | 21 pass |
| acceptance | `python3 tools/acceptance.py` | 0 | 6 PASS · 0 FAIL · **7 BLOCKED** |
| claim audit | `python3 tools/audit_claims.py` | 0 | clean, incl. 18 test citations resolved |

Count reconciliation: 746 (`6a22208c`) → 757 (+11 classifier) → 809 (+29 rollback,
+16 harness, +6 live) → 813 (+4 audit parser) → 819 (+6 live-vs-double) → 828
(+5 vacuous-verification, +5 completion/skips) → **832** (+4 citation traceability). **Nothing was deleted or weakened at any point.**

## D. Live QoS evidence

**None at this revision.** Kernel 7.1.5 is present but unreachable; no `tc`.

| step | status |
|---|---|
| traffic generated in topology | BLOCKED |
| collector observes it | BLOCKED |
| classifier selects class | PASS (16 constructed cases) |
| policy decision | PASS |
| `tc` config updated | BLOCKED |
| filters/classes exist | BLOCKED |
| counters show activity | BLOCKED |
| behaviour matches policy | BLOCKED |
| measurements return | PASS (live socket) |
| control loop responds | BLOCKED |

Historical gate evidence (20 PASS / 1 MEASURED / 0 FAIL) exists at `705cdd5` on a
privileged host. It is **stale by construction** — the collector and classifier
have both changed since — and is not re-attributed to this revision.

## E. Remaining limitations

**Blocked gates (7):** testbed gate · live enforcement · live rollback
verification · rollback under real `tc` failure · live adaptation loop ·
FIFO/CAKE/ACIQ comparison · 30-minute stability.

**`min_rate`: not implemented, and the earlier rationale was wrong.** The code
already reserves `floor * n` (`max(2.0, 0.05 * capacity)` per class) *before*
weight distribution — 15 Mbps held back at 100 Mbps whether or not anyone uses
it. The recorded objection ("reserving unused capacity would throttle other
flows") describes a design this codebase does not have. What genuinely does not
exist is a *class-differentiated* reservation. Nothing requires it. Full
reasoning: `min-rate-scope-decision.md`.

**Benchmark limitation.** Controller arithmetic only — classify, `build_plan`,
reconcile — at one scale on one machine. No efficiency or scalability claim.

**Other.** No per-role API authorization. No TLS. Not penetration tested. Audit
log rotation untested. Unused capacity is not proactively reclaimed — unused
capacity is borrowed by other classes under the weight split.

## F. Claim audit

```
python3 tools/audit_claims.py     # exit 0
  ran 813 tests, ok=True, exit=0, 6 skipped
```

- constants code-vs-docs: 4/4 agree
- evidence cited by claims present: 6/6
- red-flag phrases: none

**Corrections made this run:**

1. `tools/audit_claims.py` reported `ok=False` on a fully passing suite because
   it tested `endswith("OK")`, and `OK (skipped=6)` does not end in `OK`. Skips
   are expected in any sandbox — so the audit was wrong in exactly the
   environment where it matters most. Fixed and regression-tested (4 tests).
2. `tools/acceptance.py` recorded the collected test count and never checked it:
   a suite that exits 0 while collection silently shrinks produced a **green
   acceptance run**. Fixed with a floor; regression-tested.
3. `min_rate` scope rationale corrected — see E.
4. `rollback-failure-injection.md` marked the verification gap fixed.
5. **Seven invented test names removed** from two documents. The tests were
   real; the names were not. `audit_claims.py` now resolves every backticked
   `test_*` citation in `docs/gap-closure/` against the real test sources, and
   an unresolvable citation reaches the exit code — reporting DRIFT and exiting
   0 would make the check decorative, the third instance of that shape here.
6. Correcting those names revealed that a test named
   test_two_thousand_flows_still_sum_to_capacity **never existed**, so "degradation over many flows: yes (2000 flows)" was
   wrong. `build_plan` splits per *class*, so flow count is not an input to the
   arithmetic. Per-flow fairness is unasked and untested.

## G. Verdict rationale and what would change it

**VALIDATION BLOCKED.** Six dimensions PASS, one PARTIAL, seven BLOCKED, zero
FAIL. The blocked set contains every dimension that separates a working QoS
controller from a correct-looking one.

### To reach READY FOR RELEASE

Run the harness **as root** — `sudo -v && python3 tools/acceptance.py` refreshes
the sudo timestamp but leaves the harness running as your user, so every
mandatory gate is reported BLOCKED even though root was available:

```bash
cd ~/Desktop/Full-projects/TATA-ELXSI
sudo python3 tools/acceptance.py
sudo python3 -m unittest tests.test_rollback_live -v
```

The harness now tries a cached sudo rather than only checking `euid`, and says
which command to run when it cannot.

On a Linux host with `iproute2`, this closes live enforcement and
kernel-verified rollback — the two mandatory gates. The soak
(`live-adaptation-stability.md`) and the CAKE comparison
(`qos-baseline-comparison.md`) follow, with acceptance thresholds stated before
they run.

**Warning before running:** `acceptance.py` phase 6 changes kernel networking
state via `testbed/gate.sh`, which creates network namespaces, veth pairs and
`tc` qdiscs, and removes them on exit. Inspect `testbed/gate.sh` before running
it privileged. There is **no dry-run mode**, and none was invented.

## Honest summary

One real defect was found and fixed this run: rollback reported success without
checking. It is now verified by reading the kernel back, with six distinguishable
failure outcomes, 29 mocked tests that demonstrably catch the original defect,
and a live integration test written but not yet runnable here.

Three smaller defects were found by auditing the verification tooling itself —
each one a number recorded, formatted, displayed, and never consulted. That
pattern recurring inside the audit tools is itself worth noting: the same
class of error was fixed in `txn.py`, `acceptance.py` and `audit_claims.py`.

The code is in better shape than it was. Whether it works **on a network** is
still unmeasured, and this environment is not where that can be found out.