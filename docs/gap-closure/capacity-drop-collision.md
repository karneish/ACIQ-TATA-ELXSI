# The capacity-drop collision — why `s2_wan_drop` cannot demonstrate adaptation

**Status: BLOCKED, with a root cause.** Found from real host evidence, not
inferred. The adaptation gate cannot be closed until this is fixed, and no
result from that scenario may be reported as an adaptation measurement.

## What was measured

`data/host_gate_adapt/s2_wan_drop__aciq__adaptive__seed42`, kernel
`7.1.5-76070105-generic`, revision `798a4fec`. `samples.jsonl`, 41 ticks at 1 Hz:

| t | total goodput | |
|---|---|---|
| 1.03 – 5.19 | ~100 Mbps | link at 100 |
| 6.24 | 12.35 | drop applied |
| 7.28 | **10.03** | **correctly at the 10 Mbps target** |
| 8.37 | 0.00 | gap |
| 9.41 → 35.99 | **~47 Mbps** | controller raised it back |

And `audit.json`:

```
t=300.963   1:1 rate 100.000
t=308.147   1:1 rate 102.044     <- above the true 100 Mbps link
t=313.374   1:1 rate  47.024     <- 4.7x the true 10 Mbps capacity
```

## Root cause

Two subsystems write the **same HTB root class**:

```python
# aciq/harness.py:389 -- the emulated link capacity
"parent", BARE_CLASS_ID, "classid", ROOT_CLASS_ID, "htb",
"rate", f"{capacity_mbps}mbit", "ceil", f"{capacity_mbps}mbit",

# aciq/tc.py:138 -- every policy plan
TcClass(ROOT_CLASS_ID, BARE_CLASS_ID, cap, cap, cls=None)
```

`set_capacity` emulates the bottleneck by writing `1:1`. `build_plan` writes
`1:1` from the capacity **estimate**. Both target the root class, so:

```
set_capacity(10)  -> 1:1 = 10 Mbps     goodput falls to 10.03   (correct)
controller replans -> 1:1 = 47 Mbps    goodput rises to 47       (drop erased)
estimator observes 47 -> believes 47   -> latches
```

**The controller can undo the very change it is supposed to detect**, and then
the estimator faithfully reports the number the controller chose.

## This is not an estimator defect

The estimator is correct given its input: throughput is 47 because the shape is
47. `observe()` treats saturated goodput as capacity, which is right when the
link is the bottleneck and wrong when the controller's own write is. The defect
is that the experiment makes the controller the bottleneck.

## Why it was invisible

`result.json` persisted only the **last three samples**:

```python
samples=samples[-3:],        # aciq/experiment.py:622
```

so the artefact showed `{t=39, 40, 41}` at ~47 Mbps — a number with no visible
dip, no visible detection, and no way to tell an adaptation from a collapse.
The full series was in `samples.jsonl` the whole time. **Fixed**: the whole
series is now persisted.

## What this does and does not invalidate

| gate | affected? |
|---|---|
| live enforcement (21 checks) | **no** — no capacity drop involved |
| rollback under real tc failure | **no** |
| live adaptation (`s2_wan_drop`) | **YES — invalid** |
| FIFO/CAKE/ACIQ comparison (`s3_tv_and_gaming`) | **no** — no drop |
| 30-minute soak (`s3_tv_and_gaming`) | **no** — no drop |

Only `s2_wan_drop` is affected, because only it drops capacity.

## The fix

**Implemented.** `set_capacity` now applies the limit out of band:

```
ip netns exec wan tc qdisc replace dev veth-w root netem rate 10.0000mbit
ip netns exec wan tc qdisc show  dev veth-w        # read back
```

`wan/veth-w` sits on the path the generators use. `TransactionManager` writes
exactly one device — `router/veth-lan` — and never goes near it. The controller
can shape as hard as it likes; the link stays at the capacity it was given, and
the estimator measures a real bottleneck instead of its own output.

The read-back is not decoration. Applying a bottleneck is no more proof that the
link is limited than `tc qdisc add` returning 0 is proof a qdisc exists — the
same standard the rollback work established. A `replace` that returns 0 without
the rate appearing in `qdisc show` is recorded as a **failure**, so
`link_end_mbps` still reports only a capacity the link actually reached.

### What was removed, and why that is not a loss

`set_capacity` used to rescale every child's ceil, because a bare parent change
does not bound an HTB link — children borrow up to their own ceil. That was
true, and it was also the collision. A `netem` limit bounds the link physically,
and clamping the tree would reintroduce the exact bug the change exists to
remove: the controller would rewrite the ceils on its next policy change.

`max(child ceil) <= capacity` remains a property of `build_plan` for a planned
capacity. It is no longer the mechanism that enforces one, and the tests now say
which is which.

### Tests

The five in `tests/test_capacity_bottleneck.py` were written **before** the
fix and marked `expectedFailure`. When the fix landed they reported *"unexpected
successes"*, which unittest counts as a failure — so the requirement could not
have been quietly dropped. They are live assertions now.

Eighteen existing tests asserted the old mechanism. None were deleted. The ones
that encoded the defect were inverted with the reason recorded
(the old "changes the parent first" test → the new "does not touch the parent's
class" test); the rest were
re-pointed at `build_plan`, where the invariant now lives.

Two of them had been quietly testing nothing: the refusal tests in
`test_intent.py` refused `class change`, which the new code never issues, so
they were refusing nothing. They now refuse the command actually sent — a test
that cannot fail is the same defect as a gate that cannot be run.
