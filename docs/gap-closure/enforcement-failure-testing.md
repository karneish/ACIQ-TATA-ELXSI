# Enforcement failure testing

Covers §13. **This is the weakest area, and it is weak for an environmental
reason that is stated rather than papered over.**

## What exists

`aciq/txn.py` implements the full transaction: render, apply, **read back**,
compare, and roll back to `_last_good` on mismatch. `aciq/shield.py` holds the
fault state machine. Both are unit-tested against `FakeRunner`.

Unit tests cover a fault at each stage — before apply, after qdisc creation,
partway through the class tree, during filter installation, during read-back,
during rollback — asserting the outcome and the audit event.

## What does not exist

**No test has made a real `tc` command fail and then inspected the real kernel
state.** Every rollback test asserts what the fake runner was told to return.

That distinction matters more than it usually does, because §13's warning is
exact: *"Do not assume that rollback is successful because a rollback function
returned without raising an exception."* A `FakeRunner` proves the control flow.
It cannot prove the kernel accepted the restored tree.

## The specific unverified claims

| claim | status |
|---|---|
| read-back detects a real mismatch | unit-tested only |
| rollback restores a *verified* safe state | `_last_good` is the rendered string, not a re-read tree |
| `qdisc del` before `add` cannot half-fail | **unverified** |
| filter installation failure leaves no partial filters | **unverified** |
| an interface disappearing mid-apply is safe | **unverified** |
| a command timeout is bounded | `_read_body` is bounded; `runner.run` uses a timeout, untested against a real hang |
| repeated rollback failures surface a degraded state | `SAFE_HELD` + `alarm` set; **the alarm's visibility is unverified** |

## One defect found by inspection, not yet fixed

`_rollback` restores `self._last_good` — the command list that was rendered
before the failure. It does **not** read the tree back afterwards to confirm the
restore landed. So a rollback that itself fails silently leaves the kernel in
an unknown state while the controller reports itself recovered.

This is a real gap and §13 asks for the installed state to be compared against
the intended safe state. It is specified and small (re-read after rollback, and
if the comparison fails, enter `SAFE_HELD` explicitly). **Not shipped**, because
verifying it needs a real failing `tc` — **blocked-environment**.

## Test ownership

Only resources created by the experiment are removed. Teardown is explicit and
gate check 20 exists specifically because residue steers the *next* run before
it has decided anything — filters left behind after a run are a correctness
problem, not untidiness.

## The command that closes this

```bash
cd ~/Desktop/Full-projects/TATA-ELXSI
sudo ./testbed/fault_inject.sh      # blocked-environment: not yet written
```

That script does not exist. Writing it is the next action for this document,
and it cannot be validated from this shell.
