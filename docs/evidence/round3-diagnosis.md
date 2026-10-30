# Round 3 — Task 1 diagnosis (offline, per-tick evidence)

Every number below is read from committed run artifacts (`data/runs_s2b/`),
from `samples.jsonl` per-tick tables (`capacity_mbps`, `governor.*`,
`estimator_*`, bottleneck `netem rate` regex, backlog bytes). `true` is the
netem `rate <X>Mbit` string = the protocol's current link truth. No new runs.

## 1. s2b_step_up_20to100, seed 800 — why the climb never starts

Applied-rate timeline: 18.00 → 16.52 (t=7.9) → **pinned at 16.52 for the
remaining 37 s** while the link is 100 from t=12.6 on.

| tick | true | applied | belief = ceil/0.9 | sat | conf | governor reason |
|------|------|---------|-------------------|-----|------|-----------------|
| 3.5  | 20   | 18.00   | 20.14             | F   | 0.05 | hold (delay 0.8 ms) |
| 7.9  | 20   | 16.52   | 18.36             | T   | 0.20 | "belief fell below applied: ceiling binds" |
| 9.2  | 20   | 16.52   | 18.36             | T   | 0.30 | hold |
| 11.4 | 20   | 16.52   | 18.36             | F   | 0.15 | "clear for 10 s but offered 15.7 does not demand it" |
| 12.6→44.7 | **100** | 16.52 | 18.36         | F (1 tick T) | **0.00** | "clear for 10 s but offered 15.x does not demand it" every tick |

Answer to "can the estimator observe above the applied rate": **no, by
construction.** After t=7.9 there is not one saturated sample at the new
link (`sat=F, conf=0.00` for every post-recovery tick; the estimator ignores
unsaturated measurements, so the belief freezes at its last saturated value
18.36). The ceiling `0.9 × belief = 16.52` is exactly the applied rate and can
never rise without a saturated observation — which cannot happen while the
tree is the bottleneck-shaped pipe the bulk source cannot exceed (offered
15.1–16.1 Mbps every tick). **Recovery-time bound under the current design:
infinite**; the arm's manual seed variation in the report was the ramp's own
recovery machinery, not a controller climb.

The probe path was armed throughout and its delay precondition ("clear for
10 s") held; what refused the probe every tick was the **demand gate**
`offered > 1.05 × applied`. So "demand is still missing" is literal: the
offered load can never exceed the shaping (bulk source window-limited to the
pipe), so the gate is unsatisfiable in exactly the regime where the climb is
needed. The up-probe rebuilt in Task 2 must treat **sustained offered ≈
applied on an empty queue with a verified-clear delay window** as the demand
evidence, then resolve the ambiguity (real new demand vs. a finished source)
by a bounded probe-and-see: step up, watch the delay response, back off to
the last known-good rate on any inflation.

## 2. s2b_step_10, seed 800 — why bind happens in 2/10 seeds

| tick | true | applied | belief | ceil | conf | delay ema | governor reason |
|------|------|---------|--------|------|------|-----------|-----------------|
| 9.1  | 100  | 80.04   | 88.93  | 80.04 | 0.30 | 0.5 ms   | hold |
| 11.4 | **10** | 80.04 | 88.93 | 80.04 | 0.25 | 17.2→38.8 | delay inflated: ratchet down one step |
| 12.5 | 10   | 80.04   | 88.93  | 80.04 | 0.35 | 38.8 ms  | ratchet down one step → 60.03 |
| 13.6 | 10   | 60.03   | **11.06** | **9.95** | 0.55 | 54.3 ms | ratchet down one step (belief now saturated, conf 0.55→1.00) |
| 19.3 | 10   | 45.02   | 11.06  | 9.95 | 1.00 | 67.5 ms  | ratchet down → 45.02 |
| 25.0 | 10   | 33.77   | 11.06  | 9.95 | 1.00 | 68.2 ms  | ratchet down → 33.77 |
| 30.6 | 10   | 25.33   | 11.06  | 9.95 | 1.00 | 73.5 ms  | ratchet down → 25.33 |
| 36.3 | 10   | 18.99   | 11.06  | 9.95 | 1.00 | 62.9 ms  | ratchet down → 18.99 |
| 42.1 | 10   | 14.25   | 11.06  | 9.95 | 0.70 | 26.8 ms  | ratchet down → 14.25 (run ends) |

The failure is not inference: by t=13.6 the belief is saturated and confident
(11.06 Mbps, ceiling 9.95 — within 5% of the 10 Mbps truth). The failure is
**descent pacing**: once the ratchet is engaged, the law's 25%/commit step
and the 5 s dwell spread the landing over **7 commits, ~31 s**. Applied never
reaches ≤ 11 Mbps inside the 45 s run in this seed (14.25 at the end), so
bind fails 8/10; the seeds that bind are those where the chain of dwells
lands faster (or the delay emergency fires earlier — the emergency path is
what makes the 2/10). Given a saturated, confident belief, the correct
mechanism is one conservative landing at (or just above) the ceiling target,
not a fixed-fraction walk.

## 3. Verdicts

1. **Up-steps (Task 2a):** the ceiling cannot grow without a saturated
   sample, and no saturated sample can exist while the tree is the limiting
   pipe — the demand gate needs the probe-and-see rewrite (bounded step,
   short hold, immediate back-off, cap at last known-good). Repaired
   recovery via bounded steps: from 16.52, law-bound 25% steps every 5 s
   dwell reach ~85 Mbps in ~40 s of commits; a step tuned on DEV may shorten
   this.
2. **Severe drop (Task 2b):** with a saturated high-confidence belief far
   below applied, land in 1–2 commits (ceiling target = 9.95), not a
   25%-per-commit walk; the walk measured 7 commits / ~31 s and failed to
   bind in 8/10 seeds.
3. **Receipts:** the tables above are reproducible from committed artifacts;
   no new privileged execution was used for this diagnosis.

## Appendix (2026-10-30): the last two DOWN/UP defect traces

### DOWN: the landing deferred, not the decision late (s2b_step_50 seed1005)

Rebased tick ledger (drop at 10.0, truth 50.0, old-constants run):

```
  10.59 CMT ok parent=84.724 within step      (last commit before the drop)
  13.80 DEC rate 63.13 ratchet (delay EMA 23.3ms)
  14.84 DEC rate 63.13 SEVERE DROP (mark=True)  <-- want max(ceiling,floor)=63.13
  14.84 CMT ok=FALSE  bound="delay emergency: descent lands at want"
        violations: rate_limited "4.25s since last change, minimum 5.0s"
        reason: deferred by change window; tree still at 84.723
  15.89 CMT ok parent=53.49 (5s dwell finally open, non-emergency ladder)
```

Three consequences: the landing cost 36 s of anneal instead of one commit;
the emergency flag spent its cooldown (next clearance 30 s out); and the
ledger advanced to 63.13 while the tree stayed at 84.72 (the next commit's
"within step bound" priced its envelope off the phantom rate).

### UP: the pierce wiped, not the pierce late (s2b_step_up_20to100 seed1000)

```
   5.10 CMT parent=43.9  "demand-probe up" (pierce +25%)
   8.90 CMT parent=41.0  "belief fell below applied: ceiling binds"
                        (0.9x the stale pre-pierce belief 45.6)
   ... ladder restarts from 41; promotion never ran (applied never
       stayed >= the pierce rate for a full probe_hold_s window)
```

The ceiling is 0.9 x a belief that definitionally lags a pierce, so the
bind tick immediately after a pierce is structurally guaranteed to
short-circuit the probe's own promotion path. Fixed by the `_probe_verified`
guard (retune #3, round3-params.md).

## Retune #4: what the 6917bd32 smoke proved about retune #3 (2026-10-30)

Retune #3's guards were structurally right but unreachable at the cadence
they observe, and two more defects only show at tick level.

### The survival window could never elapse (seed1000, s2b_step_up)

```
  7.38 DEC 21.19 "demand-probe up"        commit 7.38
  9.56 DEC 26.49 "demand-probe up"  *(same target re-proposed: kernel lag)*
 10.61 DEC 26.49 "demand-probe up"  *(re-stamp)*
 11.68 DEC 26.49 "demand-probe up"  *(re-stamp)*
 12.73 DEC 26.49 "demand-probe up"  *(re-stamp; apply lands here)*
 13.89 DEC 26.49 "pierce probe verifying: hold at probe rate"
```

`_last_rise` was reset on every re-proposal, so `now - _last_rise[0]` never
reached the 7 s window and `_probe_verified` stayed None for the whole run.
The ladder therefore ended at 64.67 and the terminal bind proposed 19.4
(kernel clamp 48.5). Both the re-stamp rule and the window length are fixed
in retune #4.

### The shutdown descent contaminated the measured final third

The bulk flow stops at ~39 s (samples: bulk goodput 54.8 at 37.2, 46.1 at
39.3, 0.0 at 40.3). The belief then decays, and the bind committed
`parent=48.503` at 39.28 -- exactly 64.671 x 0.75, a law-clamped descent.
That commit sits in the last third of the applied series and alone moves
util_applied from 0.65 to 0.566 (the published 0.57). An idle wire has no
queue to protect: the bind now holds (or keeps a pending pierce) when both
`offered` and `delivered` are at idle levels.

### DOWN: the flag never fires because the bind gets there first

s2b_step_50 seed1000: 11.66 "belief fell below applied: ceiling binds" ->
58.02, 16.97 -> 51.03 (legal 50, band 55, drop at 10). The landing is
legal at 6.97 s with `delay_emergency=False` on every decision; the delay
never crossed DELAY_EMERGENCY_MS because the tree was never far enough
above the link to build the queue the delay path needs. seed1001 shows the
cost when the estimator converges slowly: 105.55 -> 79.16 -> 59.37 -> 52.16
enters the band only at 23.28 (13.3 s), a genuine FAIL that retune #4 does
not excuse. The gate now judges the landing outcome (retune #4) and reports
`delay_emergency_s` as evidence.

## Round 5: the 1-seed real smoke (data/runs_smoke_r4a, 6917bd32)

### DOWN: confidence decayed BEFORE the drop, so the severe gate was shut

s2b_step_50 seed1000 (100 -> 50 at t=10), decision/commit trace:

```
 5.3  pierce 105.74  (link 100; ceiling 84.6)          -> commit 6.4
 7.5  belief 83.0, ceiling 74.67 (delay 0.9 ms)
11.7  belief 64.6 (conf 0.3), applied 105.74           -> wish 58.15
                                                          law clamp 79.31
16.7  -> 59.48
21.7  -> 52.16   (inside band 55, but at drop+11.7 s)
```

The pre-drop link was 100 and the tree 84-105, so `saturated` was mostly
False and the estimator's confidence decayed to 0. At the drop the belief
fell correctly (94 -> 83 -> 64.6) but conf was still 0.3. The fix keys on
"belief falling while saturated now", not on confidence.

### The pre-drop pierce above the link is what cost the extra step

The pierce is +25 % of the applied and deliberately passes the stale
ceiling; at 84.59 it lands on 105.74 (>100) because the demand witness
(offered >= 0.85 x applied) is exactly what the policy's 0.85 bulk ceiling
produces. The tree then sits ~5 % above the link for 4 s. With the severe
landing admitted at 11.7 the descent is 105.74 -> 58.14 (one commit) ->
band, instead of three 25 % steps.

### s7 DOWN 100->8: the second, larger collapse arrived inside the cooldown

```
10.6  severe  92.12 -> 65.02  (conf 1.00)   emergency #1
12.8  belief 8.3, ceiling 7.47, applied 58.52 -> RATCHET (cooldown)
16.4  -> 48.77 / 36.57 / 27.43 ... 16.6 s to the band
```

The first severe target (65) was the stale ceiling, not the true 8 Mbps.
The collapse at 12.8 is unambiguous (7.47 < 0.5 x 58.52) and now bypasses
the cooldown.

### UP: 40 s is the wall, not the controller

`bulk.sink.log` peak 39.0 Mbps, final-third 0.30-0.35 x 100. The archived
60 s s7_up_30to100 runs on the same build deliver 66.7-68.1 Mbps in their
final third with the last applied at only 73-76. The 40 s ladder reaches
69.41 at 37.8 s, so the TCP has ~2 s at the terminal rate. See
round3-params.md retune #5.
