# Capacity recovery: a self-fulfilling saturation loop

**Status:** OPEN. Three fix attempts have failed. The cause is architectural,
not a coding slip, and is recorded here rather than patched again blindly.

## The symptom

`sudo tools/host_gate.sh --recovery`, revision `664274d4`:

    [FAIL] capacity recovery (rising edge)
           link restored to 100.0 Mbps; steady goodput 17.34 Mbps afterwards
           -- the policy appears pinned at the degraded rate

    estimator=20.26  policy_changes=1

17.34 Mbps is `0.85 x 20` -- the bulk ceiling from the degraded plan, observed
after the link was restored to 100 Mbps. The controller never walked back up.

## The evidence

Per-tick samples from the recovery run (`data/host_gate_recovery/`), around the
restore at t=30:

| t | saturated | goodput |
|---|---|---|
| 20.0 - 29.3 | True | 17.3 |
| **30.4 (link restored)** | True | 17.34 |
| 31.4 - 58.4 | **True on every tick** | 17.3 |
| 59.5 | False | 14.80 |

The link recovered. `saturated` never became false, so the release path could
never begin.

## Root cause: the controller saturates itself

    build_plan(estimate = 20.26)
      -> build_tree writes 1:1 rate = 20 Mbps        <- from the stale estimate
      -> children: bulk ceil 17.0 + adaptive 6.0 + interactive 10.0 = 33 Mbps
      -> 33 > 20, so class 1:1 is overcommitted BY CONSTRUCTION
      -> `overlimits` rises every tick
      -> Measurement.saturated = True
      -> _idle_streak resets every tick
      -> the recovery release never fires

`Measurement.saturated` consults the controller's own parent class
(`link_overlimit_rate_per_s >= SAT_OVERLIMIT_MIN`) before it consults the
out-of-band bottleneck. Since the sum of child ceilings always exceeds the
parent rate under the differentiated-ceiling policy, **the parent is overlimit
permanently and by design**.

The controller therefore reports congestion caused by its own shaping. That
carries no information about the link, and a stale estimate makes it permanent.

This is the same family of defect the module already guards against once: the
docstring warns that *child* overlimits mean "a child exceeded its own
guarantee, which is routine" and must not be read as congestion. The same
argument applies to the parent whenever the policy's ceilings sum above it, and
that was not applied.

## Why three fixes failed

| attempt | why it failed |
|---|---|
| 1. Release on sustained non-saturation | oscillated upward on the way down; caught by the recorded-run suite |
| 2. Require delivered throughput > 1.5 x estimate | unreachable -- the controller throttles itself below the link, so throughput can never exceed its own estimate |
| 3. Exploit rise-slow / fall-fast asymmetry | sound in principle, but `saturated` never goes false, so it never gets the chance |

## Options

**A. Judge external congestion by the external bottleneck.**
When an out-of-band bottleneck exists -- which it always does in this testbed,
and does on any real link the controller does not shape -- judge saturation by
`bottleneck_backlog_bytes > 0` or `bottleneck_drop_rate_per_s > 0`, and stop
consulting the controller's own parent. This is the principled fix and matches
the existing precedent for child counters.

Risk: before the bottleneck is first configured the data shows `qdisc noqueue`
and the parent check is the only signal available, so initial detection at
100 Mbps would weaken. Needs re-validation of the whole drop-detection path,
which currently works.

**B. Stop deriving the parent rate from the estimate.**
Give the shaper's parent a rate that is not the capacity estimate, so the
controller's own tree cannot manufacture congestion. This changes the policy
semantics that `tc.py` and the rollback tests pin.

Risk: touches enforcement semantics; needs the full kernel gate re-run.

**C. Bounded active probe.**
Deliberately offer a little extra traffic to discover headroom. This reverses a
deliberate earlier decision ("counters only, no probe") and is an
architectural reversal, but it is the only option that recovers capacity
*faster* rather than by inference.

**D. Accept and document.**
Keep the conservative hold, and state plainly that ACIQ does not release
capacity until traffic demands it, or until a restart re-measures. Honest, and
a defensible safety posture -- but a user whose link recovers stays throttled.

## Recommendation

Option A, with the full kernel gate re-run afterwards. It is the smallest
change that addresses the actual cause, and the precedent for it is already in
the code. But it changes when the estimator believes it is saturated, which is
central enough to warrant agreement before proceeding.
