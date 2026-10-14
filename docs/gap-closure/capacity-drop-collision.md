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


## Update: the bottleneck holds, but adaptation is still not demonstrated

Two runs later, with `samples[i]["bottleneck"]` recorded every tick:

```
t=5.24   qdisc noqueue 0: root refcnt 2
t=6.26   qdisc netem 8001: root refcnt 5 limit 1000 rate 10Mbit
t=11.39  qdisc netem 8001: root refcnt 5 limit 1000 rate 10Mbit
```

**The out-of-band bottleneck holds.** Steady-state goodput is **10.01 Mbps** on a
link clamped to 10, where the pre-fix run measured **46.78**. The collision is
closed: the controller can shape as hard as it likes and the link stays where it
was put.

### A verification bug that invented the fault

The first run with the new bottleneck reported:

```
CAPACITY CHANGE REFUSED by tc (qdisc replace returned 0 but read-back did not
show the limit: qdisc netem 8001: root refcnt 5 limit 1000 rate 10Mbit)
```

while the same qdisc was visibly holding the link. The check was

```python
applied = "10.0000" in out
```

`tc` prints the limit **normalised** — `rate 10Mbit` — so that comparison could
never succeed. It is the worst shape of verification bug: it does not miss a
fault, it **invents** one, and it makes a working system look broken. Now parsed
numerically, case-insensitively, with a 1% tolerance.

### What is still unproven, and why

The estimator reported **103.2 Mbps** and the run said so itself:

> estimator 103.2 Mbps is STALE: last measured at t=2.1s, before the link
> changed at t=5.2s. M2 only measures an oversubscribed link, and this one
> stopped being oversubscribed once the workload's rate fell with it, so no
> post-drop reading was possible

This is the remaining design issue, and it is a real one:

- the plan shapes the HTB tree to **100 Mbps**;
- the real bottleneck is **external** and delivers 10;
- so the HTB parent is **not overcommitted** — no overlimit, no drop, no backlog;
- `Measurement.saturated()` is false, and the estimator correctly declines to
  produce a reading from an unsaturated link.

**M2 detects saturation of its own tree.** With the bottleneck moved out of
band, a link that is slower than the current plan is no longer detectable by
that test — which is the price of moving it out of band, and it was previously
hidden because the collision produced a fake reading instead.

### The fix this implies

The controller needs a saturation signal it can see and cannot overwrite. The
drops currently happen inside netem on `wan/veth-w`, where the collector does
not read. Moving the limit to **`router/veth-wan`** -- still a device
`TransactionManager` never writes, but one the collector already reads -- and
feeding that interface's drop counter into `Measurement.saturated()` would give
M2 exactly what it had before, sourced from a bottleneck the controller cannot
raise.

Not implemented. It changes the measurement contract and needs a host run to
validate, and it is recorded here rather than attempted blind.

**Current status: the bottleneck is fixed and evidenced. Adaptation to a slower
link is BLOCKED on M2's saturation test seeing a bottleneck it cannot overwrite.**
