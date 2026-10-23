# Rollback read-back verification

## The defect

`TransactionManager._rollback()` replayed the last known-good command list and
returned `True`, unconditionally:

```python
self.runner.run(pre + ("tc", "qdisc", "del", "dev", self.dev, "root"))
for argv in self._last_good:
    self.runner.run(argv)
return True
```

Every return value was discarded. `force_safe()` had the same shape one level
down, returning `True` on a successful `tc qdisc add` without checking the qdisc
existed.

The project already read the kernel back **after applying** a policy. It never
read it back **after undoing** one — and that asymmetry is why it went unnoticed.
A failed apply is loud; a failed rollback is silent, and leaves the controller
reporting itself recovered over a link nobody has shaped.

## The fix

`verified` is now the **only** outcome that makes `rolled_back` true.

| outcome | `ok` | meaning |
|---|---|---|
| `verified` | **yes** | commands ran and the state matches the target |
| `commands_failed` | no | a restore command was refused |
| `verification_failed` | no | commands ran, kernel state is wrong |
| `unverifiable` | no | the state could not be read back |
| `no_target` | no | nothing known-good to restore to |
| `partial` | no | state matches, but some commands were refused |

`RollbackResult` carries mismatches, unverifiable fields, failed commands, the
read-back source and the target, so the verdict is auditable rather than a bare
bool. `Outcome.rollback` carries it to callers; `apply()` logs
`rollback_verification_failed` with the specific mismatches.

### The target is an observation

Rollback compares against `_last_good_state` — the canonical state captured when
the good tree **committed** — not a re-rendering of intent. Replaying commands is
not the same as knowing what they produced.

Before this change there was no snapshot at all, so there was nothing to compare
against. Storing it is one line inside `apply()`, and it is what makes rollback
verifiable.

### Comparison rules

`compare_states()` in `aciq/tc.py`. It is **not** the apply-side `verify()`,
because the failure modes differ:

| situation | verdict | why |
|---|---|---|
| class matches | match | |
| kernel rounding within 1% | match | `tc` rounds freely; `RATE_TOLERANCE = 0.01` |
| `1:0010` vs `1:10` | match | same class, printed differently — the **only** textual normalisation |
| class missing | **mismatch** | not present is not correct |
| class present but not expected | **mismatch (`residual`)** | every expected class correct is still not restoration |
| field the reader cannot see | **unverifiable** | weaker than a match, so never counted as one |
| rate differs beyond 1% | **mismatch** | |

Normalisation is deliberately minimal. Only rounding and handle padding are
absorbed; nothing that could hide a real difference is.

### `force_safe()` is verified differently

The safe state is class-free by design — a single `cake`/`fq_codel`/`pfifo` root.
Reading it through `class show` returns nothing and **cannot distinguish a
working safe state from no qdisc at all**. `parse_qdisc_text()` reads the root
qdisc for exactly that reason. A rung that `tc` accepted but that did not appear
in read-back is reported as not installed.

`parse_qdisc_text` initially matched `root` anywhere in the line, which made
`qdisc cake ... root` parse as `htb` — a test caught it, and root detection now
checks only the two fields after the handle, since a child's `parent` is often
`1:`.

## A third defect, found by tracing the baseline's provenance

Phase 7.1 of the acceptance brief asks whether the rollback target is derived
from a trustworthy baseline rather than from the same state being checked.
Traced, it is: `_last_good_state` is the read-back captured at commit, and that
read-back had already been checked against `tree` by `verify()`. The target is
therefore an observation cross-checked against intent — not the post-rollback
state, and not derived only from the path under test.

**But the trace found something else.** `verify()` deliberately tolerates fields
the reader cannot see, records them in `unverified_fields`, and **commits
anyway**. Under a reader that reports classes but no rates, the stored baseline
is structurally incapable of failing a comparison:

```
baseline stored : {'1:1': {}, '1:10': {}, '1:20': {}, '1:30': {}}
ROLLBACK VERDICT: verified      fields compared: 0      rolled_back: True
```

A rollback reporting success after comparing **nothing**. Same defect family as
the original `return True`, one level deeper, invisible to every existing test
because they all used a reader that reports rates.

Fixed by `_comparable_pairs()`; zero comparable pairs is now `unverifiable`,
never `verified`.

**The fix immediately introduced a false negative, also caught.** Comparing raw
keys meant a baseline keyed `1:10` and a read-back keyed `1:0010` shared zero
fields, so a genuinely verified restore was reported unverifiable.
`test_zero_padded_handles_do_not_trigger_a_false_mismatch` caught it; both sides
are now canonicalised.

## Two defects the tests caught in the fix itself

1. **`_read_class_state` returns raw `ClassState` objects.** The rollback path
   compared them without the `parse_class_state()` normalisation `apply()`
   applies, so it compared dataclasses against dicts and raised
   `AttributeError`. A happy-path test would not have found this.
2. **Outcome ordering hid the cause.** The first cut reported `unverifiable`
   whenever read-back was empty. If every restore command was refused,
   restoration definitionally did not happen — "could not confirm" understates
   it and buries the cause behind a missing reader. Command failure now outranks
   unreadable state.

## Evidence

| file | contents | status |
|---|---|---|
| `tests/test_rollback.py` | 33 tests | **MOCKED — all of them** |
| `tests/test_rollback_live.py` | 6 tests | **LIVE, skipped here** |
| `artifacts/validation/<rev>/rollback-live.log` | live run | **will not exist until run with root** |

### Mocked coverage (33)

All 14 required scenarios: matching read-back, command failure, commands-ok-state-wrong,
malformed output, missing interface, partial restoration, residual class, divergent
rate, normalisation, idempotence, cleanup failure, read-back exception, original-error
preservation, audit output. Plus comparison-rule tests and two asserting the audit
reason leaks no environment or credential.

**They have teeth — measured, not assumed.** Reinstating the original
`return True` fails **14 of the 29** that existed at the time:

```
FAIL test_cleanup_failure_alone_is_still_reported
FAIL test_outcome_rolled_back_is_false_when_commands_failed
FAIL test_rollback_command_failure_is_not_success
FAIL test_failed_verification_is_recorded_in_the_audit
FAIL test_successful_rollback_is_recorded
FAIL test_exception_during_readback_is_not_swallowed
FAIL test_original_error_is_preserved_when_rollback_also_fails
FAIL test_repeated_rollback_on_unverifiable_stays_unverifiable
FAIL test_empty_readback_is_unverifiable_not_a_pass
FAIL test_malformed_readback_is_unverifiable
FAIL test_missing_target_state_is_unverifiable
FAIL test_residual_class_after_restore_is_detected
FAIL test_state_unchanged_after_restore_is_not_success
FAIL test_successful_rollback_is_verified
```

### Live integration (6) — NOT RUN

`tests/test_rollback_live.py` contains **no mocks at all**:

- an isolated network namespace `aciqrb<random>`, created and destroyed by the
  module, with a veth pair inside it;
- the host's interfaces, routes and qdiscs are never touched — if namespace
  creation is unavailable the module **skips** rather than falling back to a real
  interface;
- the fault is injected by genuinely **not sending** one command, so the kernel
  receives a truncated tree — there is no fake anywhere in the read-back path;
- state is read back with `tc -j` called **directly**, not through
  `TransactionManager`, so a bug shared between the code and its own reader
  cannot make it pass;
- it covers both directions of the verdict: a genuine restoration confirming as
  `verified`, and a lying runner producing `verification_failed` on a real
  kernel, which is otherwise untested production code.

### First real run exposed five defects — all in the test, none in `txn.py`

Run on a real host for the first time, all 6 errored identically:

```
TypeError: cannot unpack non-iterable CompletedProcess object
```

`Runner.run` returned a `subprocess.CompletedProcess` where the runner protocol
requires a `(rc, stdout, stderr)` tuple. Invisible until then, because the
module had only ever skipped. Fixed, and three more found by executing it
against a kernel double:

| defect | consequence |
|---|---|
| `Runner.run` returned `CompletedProcess` | every live test errored |
| `LyingRunner`/`BlindRunner` had no `__init__` | `TypeError` on construction |
| `FlakyRunner` re-armed on the rollback's own `qdisc del` | **the restore it existed to check was broken by the fault itself** — the test would have asserted that a failed rollback is reported failed, a much weaker claim |
| fault fired more than once | same, from a different direction |

The third is the important one: the test named "rollback restores the known-good
tree" would have passed while proving nothing about successful restoration.

### The double, committed as a permanent test

`tests/test_rollback_live_sim.py` (6 tests) executes the **real live test module**
against an in-memory kernel speaking the real `tc` CLI shapes — text output for
the primary reader, JSON for the fallback. It needs no root, so the live path is
never again exercised only for the first time on a real machine. It also asserts
the double is actually modelling the tree, so it cannot degenerate into a
green no-op.

**It proves the live test is not broken. It does not prove a kernel behaves this
way.** Only a root run does that.

All 6 skip here: `iproute2 not on PATH`.

```
sudo python3 -m unittest tests.test_rollback_live -v
```

### LIVE RESULT — PASSED on real hardware

```
$ sudo python3 -m unittest tests.test_rollback_live -v
Ran 6 tests in 0.755s
OK
```

Pop!_OS, kernel `7.1.5-76070105-generic`, iproute2 `6.1.0`, revision `7250aa58`.

**Rollback against a real kernel is now verified**, not merely modelled: the
namespace is real, the `tc` tree is real, the fault is injected by genuinely not
sending a command, and the state is read back with `tc` rather than through the
code under test. Both directions of the verdict are exercised on a real kernel —
a genuine restoration confirming `verified`, and a lying runner producing
`verification_failed`.

The first run failed 3 of 6. All three were defects in the test, and one showed
the in-memory double had been certifying a code path the host never takes:

- `tc -j` is **accepted but prints text** on iproute2 6.1.0, so the test's
  `json.loads()` returned `{}`;
- a veth reverts to **`noqueue`** after `qdisc del`, not to nothing;
- correcting the double then exposed `rstrip("bit")` breaking on `"100000Kbit"`
  and an Mbit scale that read `"100Mbit"` as 0.1 Mbps.

The controller itself needed no change: it reads text first and had already
verified all four classes.
