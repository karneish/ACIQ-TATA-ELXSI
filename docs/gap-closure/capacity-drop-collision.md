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

## The fix, not yet implemented

The bottleneck must be enforced **out of band** — something the controller's
plan cannot rewrite. `netem` is already available and already proven in this
testbed (`gate.sh` check 7 applies `netem delay 20ms` to a leaf). The capacity
limit belongs on a device or qdisc level that `TransactionManager` never
writes: a `netem rate` limit on the path *under* the HTB tree, or on a link the
controller does not configure.

This is a real change to the testbed and to `Harness.set_capacity`, and it
cannot be validated from a sandbox with no `tc`. It is recorded here rather than
attempted blind.

Until then the acceptance harness reports `live adaptation loop` as **FAIL**,
not INCONCLUSIVE, when steady-state throughput exceeds the capacity the link was
clamped to — the signature of this collision.
