# Modules — the actual finite-state machines

Written for the fix round to replace a stale draft. Every state listed here
is one a unit test drives on the live paths of this repo.

## `aciq/controller.py` — measurement controller, 4 states

| State | Meaning |
|---|---|
| `STABLE` | steady sampling window; a change notification ARMS it |
| `ARMED`  | change applied; waiting for the after-window measurement |
| `COOLDOWN` | a rollback just happened; short quiet interval before STABLE |
| `SLEEPING` | standby after consecutive rollback budget exhaustion; no actuation |

Transitions are driven by `aciq/controller.py`'s own run loop; the common
papered-over path (treating any state as STABLE) is caught by
`tests/test_controller*.py` (all `tests/test_controller*` names), which asserts that ONLY STABLE samples count
and that ARMED never produces a verdict prematurely.

## `aciq/shield.py` — safety latch, 3 states

| State | Meaning |
|---|---|
| `MONITOR` | normal; clean observations sustained for SUSTAINED_OK_S forgive the retry budget |
| `FAULT_PENDING` | a breach; backoff before retry; recovery returns to MONITOR through `observe_ok` |
| `SAFE_HELD` | latched safe state (retry budget exhausted or manual); safe plan stays APPLIED (this is a safe state, not a lock) |

The earlier concept that an 8- or 9-state joint FSM was required is
overstated for the shipped controller: the controller's 4 states and the
shield's 3 states cover every transition a test exercises. No eighth state
exists in code, so none is documented here.

## `aciq/txn.py` — the transaction path

Applies through live `tc`. `last_rollback` replays `_last_good_state`; a
failed `apply` reports `kernel_touched` with a kernel-visible reason. The
injection helper `inject_failed_apply_once(marker)` makes the next CLI
failure a REAL kernel refusal (bounded by the `_FailOnceRunner` wrapper, so
what fails is a genuine `tc` call, not a plan mutation).

## `aciq/harness.py` — what the run actually does

Baseline trees are applied ONCE at run start; `set_capacity` only touches
the out-of-band netem (wan/veth-w) bottleneck. Decision latency is timed in
`adapt_step` (a per-run deque), surfaced in the run's `resources` block as
`decision_ms` (n, p50, p95, max).
