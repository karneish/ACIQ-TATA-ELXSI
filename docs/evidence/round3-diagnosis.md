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
