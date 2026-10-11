# Rollback and failure injection

**Status: BLOCKED** for real `tc` failures. Unit-level failure handling is
**PASS**.

## Why

BLOCKED — this shell is a bubblewrap sandbox with CapEff=0000000000000000. `ip`, `tc`, `iperf3` are not installed at package level (dpkg -s returns not installed), `sudo` is absent, and `unshare --net` fails with EPERM. The user's shell runs the same commands successfully, so this is an environment limit and not a claim about the code.

## What is tested, and what that proves

`txn.py` implements render -> apply -> **read back** -> compare -> roll back to
`_last_good`. Failure at each stage is unit-tested against `FakeRunner`:
before apply, after qdisc creation, partway through the class tree, during filter
installation, during read-back, during rollback.

**That proves the control flow. It does not prove the kernel accepted the
restore.** The prompt's own warning applies directly: a rollback function
returning without raising is not evidence of a successful rollback.

## The gap found by inspection, not fixed

`_rollback` restores the rendered command list. It does **not** re-read the
tree afterwards. A rollback that itself fails silently leaves the kernel in an
unknown state while the controller reports itself recovered.

Specified and small: re-read after rollback, and on mismatch enter
`SAFE_HELD` explicitly. Not shipped because it cannot be validated here.

## Scenario coverage

| scenario | unit | kernel |
|---|---|---|
| tc command failure | PASS | BLOCKED |
| partial class-tree application | PASS | BLOCKED |
| missing / invalid interface | PASS | BLOCKED |
| permission denial | -- | BLOCKED |
| interface disappears mid-apply | -- | BLOCKED |
| command timeout | -- | BLOCKED |
| unparseable output | PASS | BLOCKED |
| restart after partial failure | -- | BLOCKED |

## Cleanup ownership

Only experiment-created resources are removed; teardown is explicit and gate
check 20 exists because residue steers the *next* run. Not re-verified this run.
