# Live capacity estimation and the control loop

Covers §6. The chain under test:

```
live counters -> valid observation -> capacity estimate -> policy calculation
  -> safety validation -> kernel application -> read-back -> post-change telemetry
```

## What the estimator is, and what changed

M2 estimates capacity from **passive counters only**. `Measurement` has no
configured-rate field, deliberately: reading class `1:1`'s configured rate
would make it an oracle and adaptation time would measure nothing.

Saturation is now decided by any of: parent drops > 0; parent overlimit rate
≥ 3000/s; **child shaper backlog ≥ 1024 bytes**.

Backlog was added as a *reversal*, not an extension. The original decision —
drops and overlimits only — was made from gate check 12, which measured
24803–65101 overlimits/s on a saturated 20 Mbit link. That source was **unpaced**.
HTB shapes paced TCP rather than dropping it, so against the project's own
workloads a congested link reported `dropped 0, overlimits 0` and M2 reported
nothing in **every** run.

Why backlog is defensible where the overlimit threshold was not: a child queue is
non-empty precisely when it wants more than the link will send, because a child
with tokens left to lend borrows rather than queues. That is a semantic
argument. The threshold sits far below the smallest non-zero value ever observed
and is deliberately **not** tuned — the overlimit threshold became wrong by being
calibrated once on a workload that did not resemble the real one.

Two safety properties, both tested:
- an unsaturated sample never moves the estimate, only decays confidence;
- backlog alone cannot declare saturation if the parent counters are unreadable.
  Assuming saturation without parent evidence is what collapsed capacity to
  7.2 Mbps once.

## Verified: replay of a recorded run

`data/ab_lease_42` was captured *before* M2 had a backlog signal, so it is a
genuine holdout rather than a trace fitted to the new code.

```
100 -> 45.97 -> 24.38 -> 15.41 -> 12.15 -> 10.86 Mbps
```

True capacity 10. Monotone, never below the link, no death spiral. Seven tests
assert this, including that no intermediate estimate falls below the true
capacity — the measured failure this project is guarding against.

**This is a replay. It is not a live experiment and is not reported as one.**

## Root cause of the stale estimates in stored runs

Not yet established. This is deliberately not papered over by shortening a
threshold, which would change a number without changing a cause.

Observed and established:
- 12 of 18 ACIQ runs in `data/matrix6` carry `estimator=None, policy_changes=0`;
- the saturation gate never fired in any stored run, because those runs were
  paced — so the estimator had no evidence to act on, which is *correct*
  behaviour rather than a bug;
- each such `result.json` carries an explicit staleness note, so the artefact is
  honest about itself.

Hypotheses still open: whether the estimator state was being updated at all in
those runs (it was not, given `capacity_mbps` stayed 0.0 throughout), and whether
any run produced saturated samples that were not being recorded.

## Control-loop performance

§6.6 asks for detection delay, acceptance time, install time, settling, policy
changes per minute, rollbacks and overhead. **None of these can be measured for
the live loop from this shell** — they require a running namespace experiment.

What *is* measured, on the controller's own arithmetic (`tools/bench.py`):

| operation | mean | p99 |
|---|---|---|
| `build_plan` | 6.95 µs | 19.31 µs |
| `build_tree` + `render` (12 tc commands) | 80.14 µs | 119.15 µs |
| `parse_conntrack_line` | 5.22 µs | 10.91 µs |
| `classify` one flow | 9.65 µs | 17.01 µs |

At 1 Hz, classifying 500 flows costs 4.8 ms of CPU per tick. Rendering a full
policy costs 80 µs. Neither is close to a bottleneck; the expensive part is
issuing `tc` commands, which this shell cannot do.

## Scenario coverage

| scenario | status |
|---|---|
| idle link, known capacity | unit-tested; live **blocked** |
| saturated link, stable capacity | replay-verified; live **blocked** |
| sudden reduction 100 -> 20 | **blocked** (the drop itself is verified — see below) |
| recovery 20 -> 100 | **blocked** — and deliberately conservative: the harness never rescales upwards on a capacity change |
| temporary congestion, no capacity change | replay-verified (the `dev10` windows) |
| workload becomes idle | replay-verified: backlog returns to 0 when demand falls below the cap |
| noisy observations | unit-tested via hysteresis and dwell |
| missing / malformed counters | unit-tested; backlog does not override unreadable parents |
| counter reset or interface recreation | **blocked** |
| multiple competing flows | replay-verified |

## What is already verified about the capacity drop itself

Independent of M2, the drop is real:

```
dropcheck4  capacity_change_applied: True   parent 24.5 -> 10.0 Mbit
dev10       parent_max 10.08 / 10.14        cap 10, both arms
```

Ceiling held at 10.04–10.19 Mbps across all fourteen runs. That is enforcement,
verified on a kernel — but it was **commanded**, not measured by M2.

## Two untested paths

1. **Estimator-triggered rebuild.** `_invalidate_enforcer_filters` has only ever
   been exercised by a lease rebuild. An M2-triggered rebuild is a different
   path through the same code.
2. **M3 replanning around 10.86.** The estimator converges to 10.86, not 10. M3
   will replan around that. Whether the resulting tree is good is unobserved.

## The command that closes this

```bash
cd ~/Desktop/Full-projects/TATA-ELXSI
sudo python3 run_experiments.py --scenario s3_tv_and_gaming --system aciq \
  --enforce --drop 10 --drop-at 5 --seed 42 --results-dir data/m2check
python3 -c "
import json,glob
d=sorted(glob.glob('data/m2check/*/'))[0]
r=json.load(open(d+'result.json'))
print('estimator_mbps :', r['estimator_mbps'], '  (expected ~10)')
print('policy_changes :', r['policy_changes'], '  (expected > 0)')
for e in json.load(open(d+'audit.json')):
    if e['event']=='committed':
        print(f\"  commit t={e['t']:9.1f} classes={e['classes']} 1:1={e.get('applied',{}).get('1:1')}\")
"
```

Success is `estimator_mbps` non-null **and** `policy_changes > 0` **and** every
commit recording `1:1: [10.0, 10.0]`.

**Blocked-environment.** Requires `ip`, `tc` and `sudo`, none of which exist in
this shell.
