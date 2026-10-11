# Rollback and failure injection

**Status: BLOCKED** for real `tc` failures. Unit-level failure handling is
**PASS**, and the verification gap is now closed in code and covered by 29
mocked tests — but that verification has **not been exercised against a real
kernel**, which is exactly what remains unproven.

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

## The gap found by inspection — NOW FIXED

`_rollback` restored the rendered command list without re-reading the tree, and
returned `True` unconditionally. A rollback that itself failed left the kernel in
an unknown state while the controller reported itself recovered.

**Fixed in `507ed7af`.** The kernel state is now read back and compared against
the canonical snapshot captured when the good tree committed; verification
failure is distinguished from success across six outcomes. Comparison rules and
test evidence: **`rollback-readback-verification.md`**.

## Scenario coverage

| scenario | unit | kernel |
|---|---|---|
| tc command failure | PASS | BLOCKED |
| partial class-tree application | PASS | BLOCKED |
| restored state does not match target | **PASS** (14 mocked tests) | BLOCKED |
| residual class left behind | **PASS** (mocked) | BLOCKED |
| read-back unavailable / malformed | **PASS** (mocked) | BLOCKED |
| repeated rollback is idempotent | **PASS** (mocked) | BLOCKED |
| missing / invalid interface | PASS | BLOCKED |
| permission denial | -- | BLOCKED |
| interface disappears mid-apply | -- | BLOCKED |
| command timeout | -- | BLOCKED |
| unparseable output | PASS | BLOCKED |
| restart after partial failure | -- | BLOCKED |

## Cleanup ownership

Only experiment-created resources are removed; teardown is explicit and gate
check 20 exists because residue steers the *next* run. Not re-verified this run.
