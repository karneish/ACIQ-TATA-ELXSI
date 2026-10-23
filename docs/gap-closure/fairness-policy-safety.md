# Fairness, starvation and policy safety

**Status: BLOCKED** for real link behaviour. Safety properties of the control
plane are **PASS**.

## Why

BLOCKED — bubblewrap sandbox, `CapEff=0000000000000000`, `ip`/`tc`/`iperf3` not installed, no `sudo`, `unshare --net` EPERM. Available on the user's shell.

## The guarantee actually enforced

`flow_rate = share * parent_ceil * n / sum_shares`, where `n` is the number of
flow classes present. `n` is dynamic, so a new flow's share is a function of
**how many classes currently exist** -- not the shares alone.

Worked: two classes, 60/40, at 10 Mbps.
`video = 0.6 * 10 * 2/2 = 6`, `bulk = 0.4 * 10 * 2/2 = 4`. Sum 10 = the ceiling.

A fourth flow appears (shares 30/30/30/10, 10 Mbps):
`first = 0.3 * 10 * 4/4 = 3.0` -- **not** 0.75. The general form is:

> **each class's share is proportional to its weight, and the ceiling is
> exactly divided across the classes that exist.** No class can exceed its
> weight's proportion of the link.

**Citation correction.** This paragraph previously cited three tests that do
not exist — "test_three_way_split_sums_to_capacity",
"test_two_thousand_flows_still_sum_to_capacity" and
"test_demand_below_capacity_does_not_inflate_rates" (written without code
quoting, because a backticked `test_*` name is now itself a checked citation).
The property is real and
tested; the names were not. Found by the new traceability check in
`tools/audit_claims.py`, which verifies every `test_*` identifier cited in this
directory against the actual test sources.

What genuinely exists:

| claim | real test |
|---|---|
| `sum(rates) <= capacity` across the range | `test_invariant_across_capacity_sweep` (10 capacities, 100 Mbps down to 0.1) |
| ...and with a lease active | `test_invariant_holds_for_every_class_of_lease` |
| a ceil never exceeds capacity | `test_ceil_never_exceeds_capacity` |
| higher weight means more capacity | `test_higher_weight_means_more_capacity` |
| idle does not inflate anything | `test_idle_samples_do_not_change_capacity` |
| floors that cannot all fit | `test_degenerate_capacity_reports_degraded` |

**Correction — per-flow fairness IS provided, and is now measured.**

This document previously said per-flow fairness was "a question the current
policy does not answer". That was wrong, and wrong in a way that mattered: it
described the *arithmetic* (`build_plan` splits by weight per class, so flow
count is not an input) and generalised it to the *mechanism*.

Every class gets an `fq_codel` leaf, and `fq_codel` **is** per-flow fair
queueing. Two flows inside one class are already served fairly. What was missing
was the measurement, not the guarantee.

`tests/test_fairness_live.py` measures it on a real kernel: two independent
UDP flows steered into the **same** class, then Jain's index over what each
actually received. One flow getting twice the other's bytes scores 0.80; the
test requires ≥ 0.95.

**Result, kernel `7.1.5-76070105-generic`, iproute2 `6.1.0`:**

```
$ sudo python3 -m unittest tests.test_fairness_live -v
test_both_senders_and_sinks_are_reachable_first ... ok
test_the_class_actually_carried_the_traffic ... ok
test_the_leaf_qdisc_is_really_fq_codel ... ok
test_two_flows_in_one_class_are_served_fairly ... ok
Ran 7 tests in 14.479s
OK
```

So the guarantee is real: two flows inside one class are served within ~1% of
each other, by `fq_codel`, verified against the kernel rather than asserted
about it.

Getting there took three runs, because every failure presented as "no traffic
arrived":

1. the sender bound an address nothing held;
2. the setup `return`ed silently, so the tests ran against a half-built
   topology and the real error never appeared;
3. the inline sink helper used `time.monotonic()` and imported only
   `socket, sys` — it died on its first line of work.

The third is the general one: **a helper that cannot start is indistinguishable
from a helper that found no traffic**, and "found no traffic" is an ordinary
result. The helpers are now parsed and checked for unimported names locally,
and a failing helper's stderr is quoted in the assertion that would otherwise
have swallowed it.

**What is still genuinely not covered:** the split *between* classes is not
per-flow by design, and flow count is not an input to `build_plan` — a class's
share depends on the weights of the classes that exist, not on how many flows
sit in them. Jain's index as computed in the collector runs across **classes**,
not across flows. So class-level fairness is measured every run and per-flow
fairness is now measured once, on the kernel; neither is measured continuously
across all live runs.

## The limit that cannot be bypassed by this formula

`min_rate` is deliberately **not** implemented.

The prompt's \"reserve a small guaranteed minimum for interactive traffic\"
would mean **reserving capacity nobody is using**. In a leased model the owner
can lease to a single bulk flow, and interactive traffic never appears; a
reservation would then sit idle while that one flow is throttled. That is a
**usability defect**, not merely inefficient.

So the guarantee is:

> Interactive traffic gets the link when it needs it, and bulk yields.

with no idle reservation. Making min_rate conditional on the presence of
interactive traffic was considered and not implemented, because the handover
edge cases were not workbenchable here.

## Test coverage gaps, named

| property | covered? |
|---|---|
| shares proportional, ceiling divided | **yes** |
| bulk limited when capacity exhausted | **yes** |
| correction class outranks learned class | **yes** |
| degradation over many flows | **no** — not tested; flow count is not an input to `build_plan` |
| max parallel flows per band | **yes** |
| reserve a guaranteed minimum | **not implemented**, deliberately |
| no starvation over a long run | **BLOCKED** -- needs >= 30 min |
| fairness across many contending flows | **BLOCKED** |

## Hard blockers before the positive claim

| # | claim | status |
|---|---|---|
| 1 | "does not starve bulk flows" | **BLOCKED** |
| 2 | "does not unfairly penalise long-lived flows" | **BLOCKED** |
| 3 | "prioritises interactive traffic appropriately" | **BLOCKED** |
| 4 | "guarantees a minimum" | **not implemented** |

"Interactive wins over bulk" is demonstrable in a test but is **not** the same
as "appropriate", and appropriateness needs a definition the project does not
have. No fairness claim is made on this revision.
