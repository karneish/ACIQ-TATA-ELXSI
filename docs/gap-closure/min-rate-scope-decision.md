# `min_rate` scope decision

**Decision: not implemented, and the previous rationale for that was wrong.**

The task instructed me to inspect the requirements and the architecture rather
than accept the recorded reason. Doing so turned up something the earlier
reports had backwards, so this section corrects the record rather than restating
it.

## What the earlier reports said

> `min_rate` is deliberately not implemented. Reserving capacity nobody is using
> would throttle other flows on a leased link.

## What the code actually does

`aciq/policy.py` already reserves capacity for every class:

```python
FLOOR_ABS_MBPS  = 2.0
FLOOR_FRACTION  = 0.05

def floor_mbps(capacity_mbps):
    return max(FLOOR_ABS_MBPS, FLOOR_FRACTION * capacity_mbps)
```

and `build_plan` subtracts it **before** distributing anything by weight:

```python
floor    = floor_mbps(capacity_mbps)
reserved = floor * n
...
remaining = capacity_mbps - reserved
```

At 100 Mbps with three classes: floor = 5, reserved = **15 Mbps**, remaining =
85. That 15 Mbps is **reserved whether or not anyone is using it**. It is not a
figure available to bulk. `docs/ACIQ_EXPLAINED.md:551` says so explicitly — *"The
floor is a **guarantee**, not a bonus"* — and lists the invariant "every class
keeps a floor" as a design rule.

**So the recorded objection — that reserving unused capacity would throttle
other flows — does not apply to a design that already reserves.** The premise
was checked and found false.

On a leased link: `n` becomes 4, reserved becomes 20 Mbps of 100, and the
remaining 80 goes to the weights. A single leased flow is not throttled to
nothing; it is bounded, which is the point of a lease.

## What is genuinely absent

Not a floor. What does not exist is a **class-differentiated** reservation —
where `realtime_interactive` is guaranteed strictly more idle capacity than
`bulk_transfer`. Today `floor_mbps()` returns one value for every class, so
interactive and bulk receive identical minimums.

That is a reasonable default, not a defect: interactive traffic in this project
is 0.09 Mbps against bulk's 88, so a 5 Mbps floor is already generous for it.

## Requirements check

| question | finding |
|---|---|
| does any requirement document mandate `min_rate`? | **No** |
| is a guaranteed minimum per class specified? | **Yes — and implemented** (`floor_mbps`) |
| is a *class-specific* reservation specified? | **No** |
| is "anti-starvation" a stated goal? | **Yes**, and met by the uniform floor plus weight ordering |

`docs/ACIQ_EXPLAINED.md:1196` notes a lease has "no time limit and no minimum
guarantee, so one person can permanently starve the household" — that sentence
is about **lease TTL**, and the TTL *is* implemented (default 90 s, revert on
expiry verified by the shield). The gap it describes is closed by expiry, not
by a reservation.

## Decision

**Do not implement `min_rate`.** Nothing requires it, and the objection that
deterred it turned out to be factually wrong about this codebase.

Had a genuine minimum-bandwidth guarantee been required, implementing it as a
permanent reservation would still have been the wrong first move. The hard part
is not setting a number, it is the interaction: reclaiming capacity when the
reserving class goes idle, whether the reservation is preemptible, what happens
under overload, whether a lease can pledge a reservation it does not hold, and
how any of it interacts with `build_plan`'s existing `reserved = floor * n`
subtraction. That needs design and measurable acceptance criteria, and none of
it is specified.

## What is guaranteed, and what is not

**Guaranteed**

- every class has `rate >= max(2.0, 0.05 * capacity)` and that is an HTB
  guaranteed rate, not a best-effort one;
- the sum of child rates never exceeds capacity, including when floors cannot all
  fit — they scale down and the plan reports `degraded`;
- interactive outranks bulk in the weight ordering;
- leases borrow from spare capacity and never take from another class's floor;
- a lease expires and reverts automatically.

**Not guaranteed**

- that interactive is *preferred* under sustained saturation — untested live;
- non-starvation over a long run — no run exceeds 40 s;
- that any class's floor is sufficient for a real interactive workload — the
  floor was chosen from project profiles, not from a latency SLO.
