# Fairness and starvation

Covers §10.

## What is measured, and what is not

`jain_fairness` is computed over **per-class goodput** each tick. That is a real
measurement and it is what `samples.jsonl` records.

It is also coarse: it cannot show starvation of a single flow inside a large
class, because two flows in the same class are indistinguishable to it. §10 asks
for per-flow and per-device throughput, which is **not implemented** — the
per-flow filter state exists in the bridge, but it is not surfaced as a
throughput series.

## Weighted fairness is not Jain fairness

Jain's index answers "are these shares equal?". The classes here have *different*
requirements — interactive gets 8× bulk's weight — so equal shares would be the
wrong outcome, and a Jain score of 1.0 would be a coincidence rather than a
success. The prompt is explicit that equal throughput must not be the objective.

What the system guarantees instead, and does verify:

- `sum(rates) <= capacity`, always, vetoed before any kernel write;
- no class below its floor, scaled proportionally when they cannot all fit,
  with `degraded` recorded;
- interactive carries 8× bulk's base weight;
- a lease adds a guaranteed class rather than reordering the others.

## The floor behaviour, which is the interesting part

When the link is too small to honour every floor, floors scale down
proportionally and `degraded=True` is set. The alternative — honouring some and
silently starving others — is worse, and the shield's `below_floor` veto uses the
*scaled* floor so the two agree.

This was exercised for real: the `--drop 10` runs put 10 Mbps under a plan
built for 100. Children scaled to 3.12/1.81/1.16/3.91, summing to exactly 10.

## Starvation

**Not measured.** No test tracks how long any flow waits, and there is no
per-flow telemetry to compute it from. The M8 dashboard's queue-depth panel is
per-class backlog, which is the closest available proxy and cannot isolate a
single flow.

## One high-volume flow against many small ones

§10 requires this case. It cannot be run here (**blocked-environment**: no
namespaces). The design predicts bulk takes 2/14 of the link and small flows
share the rest, but that is a prediction from the weights, not a measurement,
and it is not reported as one.
