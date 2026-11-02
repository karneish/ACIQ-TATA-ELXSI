# Round 3 — declared parameters (before any evaluation-length execution)

Everything here is fixed ahead of the round-3 runs. Tunable items marked
(tune) are swept ONLY on the DEV band, seeds 1000-1009, using the NEW
s7_* shapes; the final evaluation (seeds 1100-1109) runs the frozen winner
and never revisits a value. Commit hashes are stamped per-run
(`result.json.commit_hash`, report headers) — every conclusion must cite one.
Governor invariants that already exist and stay LAW: the ceiling, the
MIN_DWELL_S 5 s dwell, MAX_RATE_STEP_FRAC 0.25 steps (0.5 in emergencies),
delay emergency descent skipping dwell and step bounds.

## Task 2a — upward probe (cinch-tuned on DEV band)

| Parameter | Declared initial | Rationale |
|-----------|------------------|-----------|
| probe demand evidence | delay EMA clear (`<= clear_threshold`) continuously for `PROBE_HOLD_S` **and** `offered >= 0.85 x applied` for the same window **and** a workload still present (bulk-shaped: offered ≈ applied with an empty queue = an unserved source window-limited by the shaper) | replaces the unsatisfiable `offered > 1.05 x applied` gate; sustained offered == applied on an empty delay-free queue is the pipe-limited signature (round3-diagnosis.md section 1) |
| PROBE_HOLD_S | 12 s (tune) | a step in the dark needs a sustained window; s2's existing hold was 10 s of clear |
| probe step | multiplicative: target = min(applied x (1+PROBE_UP_FRAC), offered) with PROBE_UP_FRAC = 0.25 (tune); the verifier's MAX_RATE_STEP_FRAC stays an upper bound regardless | bounded exponential climb; each step caged by the law's up-step envelope |
| probe ceiling (unsaturated) | when no live belief caps the tree, the probe may push applied above the stale ceiling ONLY while demand evidence holds; the climb stops at `min(offered, applied x (1+PROBE_UP_FRAC))` per commit | the stale ceiling (0.9 x last saturated belief) is exactly what pinned the tree at 16.52; it must yield to the probe |
| probe backoff | any inflation event (delay EMA > inflation threshold, or a backlog spike) cancels the probe, ratchets to the last known-good rate, and blocks further probes for `PROBE_BACKOFF_S = 30 s` (tune) | overshoot discipline: rises are cheap in the budget, back-offs are prioritized as their own change |
| known-good ratchet | `APPLY_known_good` record: the highest applied rate that survived its own hold window without inflation; probes may not target above known_good after a backoff until a new full demand window clears | "cap at the last known-good rate when inflation reappears" |
| rise budget | rises count in the ordinary change budget; declared max `MAX_RISES_PER_MIN = 6` (tune) | the budget already meters every real kernel change; rises are not free |
| probe target cap | no probe may continue while `offered < 0.8 x applied` (source finished) | distinguishes "bulk saturated" from "bulk done" |

## Task 2b — severe-drop landing

| Parameter | Declared initial | Rationale |
|-----------|------------------|-----------|
| trigger | ceiling is VALID (belief saturated, conf >= 0.6) **and** ceiling < 0.6 x applied **and** delay EMA >= inflation_threshold continuously for the dwell window | the 100->10 walk state at t=13.6: belief 11.06, conf 1.0, ceiling 9.95 < 0.6 x 60.03 |
| action | ONE commit landing at `max(ceiling, MIN_RATE_MBPS)`, then ordinary dwell | replaces the 25%-per-commit walk (7 commits, ~31 s, 8/10 seed bind failure); rollback/safe-state rules unchanged |
| guard | no such landing if `BoardGuard` standby is active; the commit must pass verifier bounds (the emergency path already skips dwell+step for down moves) | the landing is still a real kernel change with a real budget |

## Bound probes against the law

The verifier's bound_rate_change gains nothing new: the dwell/step/floor
constants are untouched. Down-emergency already skips dwell+step for
descent; the probe's climbs obey ordinary bounds.

## s7_* DEV shapes + S3-stress (all declared; tuning band ONLY, seeds 1000-1009)

| Scenario | Protocol (declared before any run) | Purpose |
|----------|------------------------------------|---------|
| s7_up_20to60 | link 100? no — **20 -> 60 Mbps** at t=10, duration 40, call+bulk, settle 4 | smaller up-step than 20->100 for magnitudes; tests climb fractionation |
| s7_up_30to100 | 30 -> 100 at t=10, duration 40, call+bulk, settle 4 | recover-path 20->100 shifted pre-step 30 |
| s7_rampup_30to100 | flat 30, ramp 30 -> 100 over 20 s starting t=10, duration 40, call+bulk | ramp-up tracking (the mirror of s2b_ramp_100to30) |
| s7_down_100to15 | 100 -> 15 at t=10, duration 40, call+bulk | mid-severe down-step |
| s7_down_100to8 | 100 -> 8 at t=10, duration 40, call+bulk | severe near-floor down-step |
| s3_stress | flat 100; game (1, DSCP 46) + video tv1..tv3 (1 each) + bulk background (1), duration 40, settle 4 | demand > capacity + background; B0 gaming delay visible (docs/gap-closure: s3 as-shipped does not stress the link) |

## Task 3 — measurement rework (declared, before datasets)

| Item | Declaration |
|------|-------------|
| starvation metric (all arms) | from RECEIVER-side per-second sink logs only (`<label>.sink.log` per kind); a starved tick at label L is `inst < 0.2 x median_L` computed per-second; report starved-tick counts and longest starved streak per arm; the ACIQ `call via unknown` controller-side readout is NOT comparable to the baselines' whole-link rates — controller-side differentials stay but are labelled as different objects |
| bind definition (down-steps) | unchanged from round 2 (\|applied - truth\| <= 10%, holds to the next truth) |
| up-step metric | bind marked `n/a (up-step)`; utilization = mean over the post-change third of (applied / truth) and mean (bottleneck delivered / truth) reported separately |
| CAKE-oracle rename | the arm label becomes `CAKE-decl-final (0.95x the protocol's declared FINAL rate, from t=0; NOT an oracle for the pre-change plateau or for a climbing controller)` |

## Task 4 — new arms (declared; not tuned by ACIQ's budget)

| Arm | Declaration |
|-----|-------------|
| B1_CONS | single-class cake at **0.50 x starting link**, set and forget (rounds to the same semantics as B1_cake95) |
| B1_AUTO | single-class cake at 0.95 x current link, re-applied by the same delay-based probe climb ACIQ gets; declared as **queue-discipline baseline, not an inference baseline**: identical controller logic so the only difference is the qdisc/tree; reported with that label |

## Task 5 — final band structure (declared before any next run)

| Item | Declaration |
|------|-------------|
| seeds | 1100-1109, disjoint from every earlier band (300-319, 400-409, 500-509, 700-709, 800-809, 1000-1009) |
| scenarios | S1, S2, S3_stress, S4, S6 (360s protocol), S2b x 4, s7 x 5 — 14 scenarios x 5 arms x 10 seeds |
| band marks | runs cite commit_hash; RESULT.md headers carry the hash; reports from superseded bands get `SUPERSEDED (controller version <hash>)` headers, not deletion |
| CPU / decision latency | reported per arm; the measured 3x CPU increase vs earlier band is explained from artifact differences (per-tick sample width) rather than assumed |
| pass criteria | acceptance gates are the round-2 ones + up-step climb binds/utilization and new starvation readouts |

## Final-band runtime estimate (privileged work)

~700 runs x ~50 s ≈ 9-10 h sudo wall time; resume-safe `.done` markers like
round 2 (delete the marker to re-run one piece). One script per phase, never
run twice automatically.

## DEV-band retune (declared BEFORE the band rerun; from partial runs, seeds 1000-1009)

The first partial DEV pass (commit `f8cd46f`, 213 run dirs, 21 full cells
of 30) exposed two engine defects. Both are fixed as tunable declarations
here so the rerun judges the declared values, not the legacy seed:

| Parameter | Old | New (tune) | Rationale (dev evidence) |
|-----------|-----|------------|--------------------------|
| pierce gate | ceiling freshness: a saturated observation refreshed the ceiling and blocked the pierce for PROBE_HOLD_S | overlimit witness `PROBE_OVERLIMIT_MIN = 50.0 /s` (tune): the demand window pierces only while the tree is seen overlimiting | a saturated sample refreshes the ceiling AT the pinned applied rate forever — dev seed 1004 s2b_step_up had saturated ticks at rel 22.1/25.2/27.3/32.6, all at applied 15.25 against a 100 Mbps link, so the pierce never started (util 0.15–0.26, 3 seeds with zero post-recovery commits). The tree's own overlimit counter separates the cases the freshness gate could not: >= 940/s while the tree pins and drops demand; ~0 when the LINK carries what the bulk asks for. Plumbed as `observe(..., tree_overlimit_per_s=...)` from the harness class-sum overlimit rate; a counters-less tick (None) refuses to pierce |
| severe_drop_frac | 0.6 | 0.9 | a 2x step (s2b_step_50: ceiling 65.03 against applied 73.51 one tick after the drop as ratcheted at 74.51) never pierced 0.6, so the harness ran the law's 25%-walk (6 commits, final applied 39.72 — 21% under the 50 Mbps truth). At 0.9 the same tick fires the confidence-gated emergency and lands at max(ceiling, MIN_RATE_MBPS) that tick (~1.4 s after the drop). The confidence gate (>= 0.6) still excludes staleness; collapse (< 0.5) unchanged |

Verification-contract note: `down_emergency_landing` (gate limit
`EMERGENCY_COMMIT_LIMIT_S = 8.0 s`) reads the clearance from the governor
DECISION ledger (`changed=True` + `delay_emergency=True` post-drop,
bridged to a committed kernel change within 0.5 s); the
`policy_change_log` row never carried the flag. The tool check is part of
the frozen gate (same rules, corrected data source).

Declared-live constants left untouched from the task-2a seeding:
PROBE_HOLD_S 12.0, PROBE_UP_FRAC 0.25, PROBE_DEMAND_FRAC 0.85,
PROBE_DEMAND_GAP_S 3.0, PROBE_BACKOFF_S 30.0, probe step envelope
(0.25 multiplicative, verifier-clamped), known-good/overshoot landings,
rise budget 6/min.

## DEV-band retune #2 (declared 2026-10-29, commit 5865fe0d data, 12/30 cells, 128/300 runs validated)

`tools/verify_round3.py data/runs_dev3` on the fresh dev band passed every
long-window up shape (s7_up_20to60 aciq 8/8 seeds available: util_applied
0.69-1.06, util_delivered 0.77-0.82) and exposed two fresh failure classes.
Both are retuned as declared tunables below; the affected cells re-run under
the new constants after the current band finishes (markers wiped, old dirs
archived, full band re-run so the band stays single-revision).

| Parameter | Old | New (tune) | Rationale (dev evidence, seeds 1000-1009) |
|-----------|-----|------------|------------------------------------------|
| severe_drop_conf | 0.6 | 0.45 | s2b_step_50: severe fired and PASSED the <=8 s criterion in exactly 6/10 seeds (3.8-4.9 s landings). In the other 4 (1001,1002,1008,1009) the estimator confidence never cleared 0.6, so the name walked 85.1->74.7->58.0->51.1 Mbps over ~16 s instead of committing the emergency landing. 0.45 admits the borderline-confidence cases; the >severity (0.9) and non-collapse guards are unchanged, and overshoot/delay-inflation resolution still applies |
| probe_hold_s | 12.0 | 7.0 | s2b_step_up_20to100 (40 s runs, step at t=10): the governor used its full probe budget (4-5 demand-probe commits/seed) but the 12 s saturation-hold left too few cycles after the step, ending at util_applied 0.32-0.47 with util_delivered 0.20-0.28. In the LONG window (s7_up_20to60, 60 s) the same policy passed 10/10, so the defect is pacing, not the pierce. hold 12->7 gives ~3 probe cycles in the 30-s post-step window instead of ~1.5 |
| probe_backoff_s | 30.0 | 18.0 | companion proof pacing knob: after an overshoot landing the cooldown froze ~a third of the post-step window; 18 s keeps the overshoot protection but leaves a second full cycle |

Not retouched: SEVERE_DROP_FRAC 0.9 (evidence: 6/6 fires PASSED), severe
collapse guard, probe envelope, overlimit witness 50.0/s, all other
declared-live constants.

Validation gates unchanged (frozen): dev up-util >=0.60, down emergency
<=8.0 s, fairness/starvation readouts. The retuned band will be judged by
the SAME gate constants (tools/verify_round3.py:42-46).

## Retune #3 (declared 2026-10-30, BEFORE any re-run of the dev band)

No threshold moved this round. The dev band's DOWN failures (13 of 14:
"no delay-emergency commit after the drop") and the UP wipes
(s2b_step_up_20to100 0/10) traced to two implementation defects and one
guard the probe ladder never had; all three are structurally fixed and
proven by unit tests, with the tuned constants exactly as retune #2 left
them (probe_hold 7/backoff 18/sev-conf 0.45; run-wide: everything else).

| Defect (evidence) | Fix |
|-------------------|-----|
| `Shield.veto_rate` deferred a delay-emergency descent across the 5 s change window ("rate_limited: 4.25s since last change", s2b_step_50 seed1005): the one-commit landing never reached the tree, the clearance burnt its 30 s cooldown, and the next emergency cleared only at drop+29.5 s, twice past the 8 s gate. | `veto_rate(now, emergency=)`: descents the law already fast-tracked bypass the change window; the flag is set only for want<prev (down) descents (`aciq/shield.py`, threaded through `txn.apply`). |
| The ACIQ `apply_system` branch advanced `_capacity_mbps`/`_current_plan`/`txn._last_capacity` BEFORE the apply, so a deferred emergency left the ledger at the landing rate while the tree still carried the pre-drop rate; the next tick's step bound priced its envelope off a rate the kernel never had (seed1005: ledger 63.13, tree 84.72). | Snapshot before the apply, restore when `txn.apply` did not commit (`aciq/harness.py` `apply_system`). |
| After the ceiling-bind wipe the demand-probe ladder could never promote (the pierce committed 43.9 at t+5.1s, "ceiling binds" held it back to 41.0 = 0.9x the stale belief at t+8.9s, and the estimator's belief can only lag a pierce), so every pierce burnt budget and restarted from below. | Inside a pierce's hold window the bind cannot wipe the probe; a pierce that SURVIVED its window promotes to known-good AND `_probe_verified`, and while the delay stays clear the bind and the clear-and-demanded branch treat the verified rate as the climb floor (`aciq/ratecap.py`). Every descent branch (ratchet, overshoot landing, delay/severe/capacity emergencies) keeps the true ceiling and outranks the guard. `refund_delay_emergency` restocks a clearance whose apply did not commit. |

Why no constant moved: max_changes_per_min was never exhausted in any dev
trace (checks: `rg "rise budget exhausted" data/runs_dev3`), and the up
shapes that passed under retune #2 (s7_up_20to60 10/10, rampup/up cells
20/20) set no cadence deficit. The affected cells re-run under the SAME
constants so the artifacts alone can say whether the structural fixes
close the gate; any further tuning must quote the new run's defect line.

## Retune #4 (declared 2026-10-30, BEFORE any re-run of the dev band)

Gate constants do NOT move this round: up-util 0.60 / delivered 0.50 and
the down landing budget 8.0 s (with its 10% band) are exactly as frozen
above; seeds 1000-1009 / 1100-1109, the scenario durations (40 s), and the
protocol capacities are untouched. What moves is one controller constant
and one measurement instrument, both because the 6917bd32 smoke showed the
previous form could not be satisfied by ANY lawful controller.

Smoke evidence at 6917bd32 (the two 3-seed chunks re-run after retune #3):
s2b_step_up_20to100 0/3 (util_applied 0.57/0.53/0.52, delv 0.34/0.24/0.24);
s2b_step_50 0/3 with `delay_emergency` NEVER set (`emerg decisions: []`)
although the tree landed legally (11.66->58.02, 16.97->51.03 on a 50 Mbps
link: inside the 55 band at drop+6.97 s).

| Change | Old | New (declared) | Evidence |
|--------|-----|----------------|----------|
| probe_hold_s | 7.0 | 5.0 | The SAME number is the survival window that promotes a pierce to `_probe_verified` and the bind guard that keeps it alive. A survival window longer than the minimum spacing of the pierces it observes can never elapse: the ladder is law-paced at one change per 5 s (`MIN_DWELL_S`), so every new pierce re-stamped `_last_rise` first. seed1000 trace: piers at 7.4/12.7/18.1/23.4/28.7/34.0, promotions 0, terminal bind to the stale ceiling 19.4 (law-clamped 48.5) = "publishable" 0.57. 5 s is the largest reachable window; the demand window it also governs becomes exactly one law slot of sustained evidence |
| re-stamped pending pierce | every `demand-probe up` decision | only a NEW higher target | Between a pierce decision and its kernel apply the governor re-proposes the SAME target each tick (seed1000: 9.56/10.61/11.68/12.73 all 26.49). Each re-proposal restarted the survival clock, so even the 5 s window could not conclude. Re-proposing the pending rate is not a new rise |
| idle-wire bind | descent to the decayed ceiling | hold the applied rate; keep a pending pierce while the wire is idle | Load shutdown is not a link shrink. seed1000: the bulk stopped at ~39 s (`offered 0`, `delivered 0`), the belief decayed, and the final commit fell to 48.50 (25% law clamp from 64.67) inside the measured final third, costing ~0.08 utilization for no protection (`IDLE_WIRE_MBPS=5.0`; measured idle: 0.0-0.12, any real bulk flow: tens). A BUSY wire keeps the full descent priority (that is the real drop path) |
| down gate instrument (`tools/verify_round3.py`) | a `delay_emergency`-flagged decision bridged to a commit | FIRST committed rate inside the legal band within 8.0 s AND the final commit inside it; the flag is reported (`delay_emergency_s`), not required | The case-study requirement is "recalculates shaping rather than building a large queue", an OUTCOME. Retune #3 made law-cleared descents legal, so the belief-fall bind now lands in-band in ~7 s with no delay flag (seed1000/1002 smoke, 13.3 s walk in seed1001 = a real miss, still FAIL). Deep drops still cannot pass on a walk: from ~90 Mbps two 25% steps cannot reach a 15.4 band in 8 s |

Structural guard added to the suite: `PROBE_HOLD_S <= MIN_DWELL_S`
(tests/test_rate_governor.py::TestRound4SurvivalWindowAndIdleWire), so the
survival window can never again drift above the cadence it observes.

Open risk stated honestly: the up shape's DELIVERED criterion is bounded by
the bulk class ceiling (BULK_CEIL_FRACTION 0.85 x capacity) and the single
TCP flow's ramp; at 40 s the measured sink tops out at ~0.53 of a 100 Mbps
truth in the best seed (52.6 Mbps), so util_applied must land >=0.64 for
delivered >=0.50. The retune maximizes the lawful climb (one rung earlier,
no wipe, no shutdown descent) and the smoke re-run must show whether that
is enough on seeds 1000-1002 before the full band is committed.

## Retune #5 (declared 2026-10-30, AFTER the 1-seed real smoke at 6917bd32)

No gate constant moved. Two DOWN defects and one measurement fact were
measured on `data/runs_smoke_r4a` (1 seed per shape, same build the band
will run), and only the DOWN controller changed.

### DOWN: a falling belief on a saturated link is a drop, not a stale ceiling

| Defect (measured tick) | Fix |
|---|---|
| s2b_step_50 seed1000: pre-drop pierce to 105.74 on a 100 link; at drop+1.7 s the belief had fallen 83 -> 64.6 (ceiling 58.15 < 0.9 x 105.74) but `belief_conf` was 0.3 (< the 0.45 severe gate) because confidence had decayed on a pre-drop link the tree never saturated. The severe trigger refused and the verifier's 25 % envelope walked 79.31 -> 59.48 -> 52.16: **landed at 11.7 s**, not 6.97 s as in the earlier smoke. | The severe landing is admitted when the bottleneck is saturated THIS tick AND the belief is FALLING over one tick (>= 2 %), without the confidence gate. A belief that merely sits low (the up shapes: constant 16-18 under a 100 link, because capacity is unobservable below saturation) is NOT a drop and never clears. Applied in both the inflating ratchet and the non-inflating bind (the 1:1 delay sat at 15.9 ms, below the 20 ms ratchet, so the bind was the branch that mattered). |
| s7_down_100to8 seed1000: the first severe landing (10.6 s) targeted the stale ceiling 65.02; the belief then snapped to 8.3 two seconds later (ceiling 7.47 vs applied 58.52) inside the shared 30 s clearance cooldown, so the emergency was refused and the 25 % walk 48.77/36.57/27.43 needed **16.6 s**. | A CAPACITY COLLAPSE (ceiling <= 0.5 x applied) bypasses the clearance cooldown: the cooldown exists to stop repeated moderate emergencies, not to refuse a second, larger collapse. The landing is still `max(ceiling, floor)`, so the class floors are respected (s7 100->8: max(7.47, 14.0) = 14.0, the legal floor). |

Expected after the fix, replayed on the recorded tick values (unit tests
`TestRound5SevereLanding` and the updated `TestChangeBudget`):
s2b_step_50 seed1000 lands 58.14 at drop+1.7 s and the next lawful commit
reaches the band at drop+~6.7 s (PASS); s7_down_100to8 seed1000 lands 14.0
at drop+~2.8 s (PASS).

### UP: the 40 s run cannot reach the delivered gate (measured, not inferred)

The up ladder is law-bounded at ONE 25 % step per 5 s dwell. From 18.19 at
the t=10 step it reaches 69.41 only at 37.8 s, so the final third averages
0.62-0.73 of the applied rate but the bulk TCP never reaches steady state
inside the window: `bulk.sink.log` peaks at 39.0 Mbps and the final-third
mean is 0.30-0.35 of the 100 Mbps truth (gate 0.50). The same workload on
the SAME build reaches 67-68 Mbps in the final third of the 60 s
`s7_up_30to100` runs (archived dev band: sink final-third 66.7-68.1 across
seeds, last applied only 73-76), and 39-40 in the 60 s `s7_up_20to60`.
So the delivered ceiling is a function of TIME AT RATE, not of the
controller: the 40 s shape leaves ~4 s at the terminal rung.

The harness already declares the rule this shape violates: "Up-shapes get
60 s (s4's duration): a bounded multiplicative climb needs room that 40 s
does not leave" (aciq/harness.py:252-254), and `s2b_ramp_100to30` in the
same table is 60 s (harness.py:242). `s2b_step_up_20to100` was declared at
40 s in Task 4 (commit 857ce7bb) and never revisited.

DECLARED CHANGE (operator-approved 2026-10-30): `s2b_step_up_20to100`
now runs 60 s, the duration the harness already declares for up-shapes
and the one `s2b_ramp_100to30` in the same table uses. Nothing else moves:
seeds 1000-1009 / 1100-1109, the protocol (20 -> 100 at t=10), the
capacity, and every gate constant stay frozen. The step stays at t=10, so
the run gives the ladder 50 s post-step instead of 30 s; the archived
60 s 30->100 evidence (final-third delivered 66.7-68.1 Mbps) is the
expected outcome, re-measured on the re-run, not assumed.

### Retune #6 -- the real 1-seed smoke at ed34fa3e (data/runs_smoke_r5)

The operator-approved 60 s duration was necessary but NOT sufficient. The
re-run measured 4 FAIL / 3 PASS of 7:

* `s7_down_100to8` 3/3 **PASS** (1.8 / 0.6 / 1.7 s, landing 14.0): the
  collapse bypass works on the real kernel.
* `s2b_step_up_20to100` seed1000: util 0.65 (PASS) but delivered 0.48
  (gate 0.50) -- one rung short, for a reason the recorded ticks name
  exactly (see UP below).
* `s2b_step_50` seed1000/1001/1002: the landing now happens, but (a) two
  seeds landed at 8.1 / 8.0 s (budget 8.0) and (b) after the landing the
  tree **re-pierced upward** and the final commit sat at 64.5-71.6 on a
  50 Mbps link (band top 55.0).

#### DOWN: land at the delivered rate, and do not probe a link that just fell

| Defect (measured tick, seed1000/1002) | Fix |
|---|---|
| The first post-drop tick was classified as a PROBE OVERSHOOT (delivered 52.5 of applied 75.15 = 0.70, above the 0.6 discriminant) and returned a non-emergency landing 52.55; the law then step-clamped it to **56.36** (see the cooldown row) and the in-band commit only arrived at 50.57 / 52.22 via the belief's slow decay **8.1 / 8.0 s** after the drop. | The overshoot branch now refuses to claim a wire carrying less than the belief says it can (`not wire_dropped`), so the tick falls through to the severe path; the landing is `min(ceiling, delivered)` -- the same "never land above what the wire carries" rule the overshoot branch already uses -- 52.18 / 52.27, in ONE commit. |
| The pre-drop severe at 7.5 s spent the shared 20 s clearance, so at 12.8 s `emerg_free` was False and the drop landing was refused as an emergency; the law's 25 % step from 75.15 is 56.36, above the 55.0 band top, so the landing slipped to 8.13 s. This is the measured FAIL on seed1000 (and seed1002's 68.98). | A wire carrying `< 0.80 x applied` **and** `< ceiling` (demonstrated under-delivery: 52.18 of 75.15 on a 50 Mbps link) bypasses the clearance cooldown, the same way a capacity collapse already does. The cooldown exists to stop repeated moderate emergencies, not to refuse a landing on a link the bulk cannot fill. The landing is `min(ceiling, delivered)`, never below the plan floor. |
| After the landing the probe re-pierced 41.3 -> 51.6 -> 64.5 -> 71.6 on the 50 Mbps link. The demand witness is tautological for a starved bulk: the harness derives `offered` from the applied (`= 0.85 x applied`), so `offered >= 0.85 x applied` holds every tick, and the shielded call's delay never sees the parent queue (the bulk is shaped at its leaf). | The probe is suppressed while the estimator is in a DROP REGIME: `belief < 0.8 x max(belief over the last 30 s)`. A probe is a bet that the ceiling is stale-LOW; it must not be placed while the estimator's own history says capacity FELL. The up shapes never enter the regime (their belief is flat/rising: 17.4 -> 19.5 -> 23.3 in the seed1000 run). |

| A third hit on seed1002 (the first band re-run at b26d1670): the severe landed at **55.69**, 0.69 above the 55.0 top, because the 1 s `delivered` sample at the drop tick (12.79 s) still held the pre-drop queue draining -- the tick before (11.67 s) had carried 52.39. The follow-up bind reached 52.18, but the 5 s dwell pushed its commit to 18.09 s, 0.09 s past the 8.0 s budget (`landed 8.1s`, FAIL). | The severe landing targets the **lowest delivered over the last 4 s** (`SEVERE_LANDING_WINDOW_S`), still clamped by the ceiling and the plan floor: seed1002 lands 52.39 at drop+2.8 s, seed1000 52.38 and seed1001 52.33 (their drained minimums). The instantaneous sample is a transient, not the wire's carried rate. |

#### DOWN: the stuck re-pierce chain, and the up-shape lost rung

One more defect was visible across both shapes. A pierce is held by the round-4
guard only after `held_clear` (10 s of clear delay); the first up pierce
(17.14 -> 21.42 at t+1.1 s) was therefore undone by the bind branch the next
second ("belief fell below applied: ceiling binds"), costing ONE rung of a
ladder that is budget-bound at ~7 rises per rolling minute. The guard now
holds a pending pierce while the delay is CLEAR **and the belief is not
falling** (a genuine drop keeps the descent path).

#### UP: 60 s is enough once the lost rung is recovered

The 60 s seed1000 run reached applied 65.4 at 39.2 s and then sat there;
the 7 rises were spent, but one of them re-achieved the 17.1 -> 21.4 rung
the bind had undone. With the guard fixed the same 7 rises each land one
rung higher (21.4, 26.8, 33.5, 41.8, 52.3, 65.4, **81.8**), so the final
third applies ~0.78-0.82 and the delivered (0.85 x applied x the ~0.85
idle-tail factor) is ~0.56-0.59 -- above the 0.50 gate. No duration,
budget, step or gate constant changes for this.

Replayed on the recorded ticks in `TestRound6DownRegime` (new),
`TestRound5SevereLanding` (landing updated to the delivered clamp) and the
round-4 guard test. Feeding the recorded ticks (belief, delivered, applied,
delay, overlimit) back through the new governor reproduces the intended
single commit: seed1000 lands **52.18 at rel 12.8 s (drop+2.8 s, inside the
8.0 s budget)** with `delay_emergency` set, seed1002 lands 52.39 at
drop+2.8 s (the 55.69 transient is filtered by the drained-minimum window),
seed1001 lands 52.33 at 1.7 s. The post-landing tail is the *bind*, not a probe: in the drop
regime no pierce is placed and the bind never climbs above `applied`, so the
bind/ceiling commits cannot lift the tree back above the band.

The replay is open-loop (the kernel's response is not modelled), so it
corroborates the FIRST post-drop decision only -- the tail and the up
ladder are decided by the real kernel and are the point of the re-smoke.
Expected on the re-run: s2b_step_50 lands ~52.2 at drop+~2-4 s with the
tail <= 55.0; s2b_step_up_20to100 util ~0.78, delivered ~0.57;
s7_down_100to8 unchanged (PASS).

## Retune #7 (declared 2026-10-30, after the dev band at fdfd2cf6)

Band result: 6 judged FAIL / 74 PASS / 20 skipped (no controller claim)
of 100 (`tools/verify_round3.py data/runs_dev3`). Gate constants do NOT
move this round. One controller change, one withdrawn change.

#### The up shapes landed at the stale-LOW ceiling

`s7_rampup_30to100` seed1008 (rel 42.8) and `s7_up_20to60` seed1002
(rel 43.1) committed a severe drop at the ceiling in one commit while the
wire's own evidence said the link was fine:

* seed1008: `ceiling 40.78 < 0.90x applied 121.33: land at 40.78 (wire
  carries 104.58)` -- a carry of 0.86x applied.
* seed1002: `ceiling 27.38 < 0.90x applied 82.10: land at 27.38 (wire
  carries 63.00)` -- a carry of 0.77x applied.

`wire_dropped` is FALSE in exactly those ticks (delivered sits ABOVE the
stale ceiling), so retune #6's ceil-led `min()` kept the stale leg. The
decision log shows the shared shape: the demand-probe ladder pushed the
applied while the estimator -- a slow-increase with release dwell -- still
held the pre-climb belief; the ladder's own overshoot lifted the delay EMA
over the 20 ms inflation threshold (6.7 -> 16.1 -> 22.2 ms on seed1002),
the severe block fired, and the landing took the belief's word.

Fix: in `land_target` (aciq/ratecap.py), for a wire-dropped-NO landing the
ceiling is dropped from the min ONLY when the wire demonstrably cannot
hold the applied: carry < `SEVERE_WIRE_LED_CARRY_FRAC` = 0.9x applied.
Rationale: the recorded anti-patterns carry 0.86x / 0.77x (the applied is
the snake's own overshoot; the wire's rate IS the link); the genuine-drop
smoke the ceil-led rule protects carries 1.00-1.09x applied while the
320-500 ms of queued bytes drains (the task2 collapse fixtures), so its
instantaneous carry proves nothing and the ceiling keeps owning the land.
`TestRound7DevBand` replays both recorded landings (104.58 / 59.1) plus
the round-6 anchor (52.18) under the new rule.

#### The s2b_step_up stall: budget hypothesis examined and WITHDRAWN

The failing quartet's recorded shape (`s2b_step_up_20to100` seeds
1001/1002/1003/1008): the pierce ladder stops at rungs 6-8 (rates
55.6-69.2) and the reason falls through to
`clear for 10 s but offered X does not demand it` for the rest of the run
at offered 57.3-58.1 of applied 64.88 (= 0.88x applied -- ABOVE the 0.85x
demand threshold, with dw 36+ s and overlimit 4744/s).

First hypothesis: `MAX_CHANGES_PER_MIN = 6` rations the 9 rungs a
20 -> 100 recovery needs. A synthetic 25 %-step ladder confirmed the
budget stalls the 7th rung under the code's `budget_left > 0` gate, and
the fall-through text matches. It was then WITHDRAWN: the recorded runs
contradict the gate -- seed1000's ladder committed NINE pierces inside
~43 s under the same budget (decisions log: rungs at rel 6.3-48.9, each
`demand-probe up`), which the gate cannot produce. The constant stays 6
(the discipline this file holds: a constant moves only when the artefacts
defend the move; here they defended its opposite). A faithful replay of
the recorded decisions could not be built this round (offered/applied
reconstruction diverges from the recorded flow), so the exact refusal
path of the stall ticks stays OPEN; the four seeds re-run under the
landing fix and the diagnosis resumes on their trace if they fail again.

## Retune #8 (declared 2026-10-31, BEFORE any re-run of the dev band)

The band at fdfd2cf6 left 20 of 100 cells judged SKIP because
`tools/verify_round3.py` had no lane for a walking-wire ramp-down or a
steady-demand stress. The round-7 artefacts can say nothing about those
shapes if the gate cannot judge them, so the two LAST skip classes
become judged lanes here, ahead of the re-band that must pass them. No
gate constant moves: the new lanes reuse the frozen constants (the 10%
bind band, the 8.0 s landing budget, the 0.50 delivered law). Only the
judge file changes (`tools/verify_round3.py`: `ramp_down_landing`,
`stress_deliver`); an unclassified shape FAILS from now on -- nothing
reaches the gate that the gate cannot judge.

### ramp-down lane (s2b_ramp_100to30: the wire walks 100 -> 30 Mb/s over [t=10, t=30], 3.5 Mb/s/s)

The wire cannot be announced to the controller, so a per-commit tracking
law would judge the estimator, not the contract (the round-6 artefacts
put the earliest ramp commits at 1.27-1.53x the walking target -- they
are counted and printed as `overtrack_max` evidence, never a pass
condition). The frozen contract is the ENDPOINT mirror of the DOWN lane:

| Law | Frozen value | Old-code measurement (seeds 1000-1009) |
|-----|--------------|----------------------------------------|
| END-BAND LANDING | first committed rate <= 33.0 (30 x 1.10) within 8.0 s of the ramp END | 9/10 seeds land 0.9-4.1 s after ramp end (31.26-31.64), seed1003 walks 39.48 -> 35.54 -> 31.62 and lands at ramp END + 12.6 s: FAIL, exactly the judged step-walk class |
| TAIL | the final committed rate stays <= 33.0 to the run end | 10/10 (tails 22.32-30.56) |
| DELIVERED | last-third bulk.sink mean >= 0.50 x 30 | 10/10 (0.828-1.261) |

(The landing budget counts from the ramp END, not from ramp start: the
walk loses 70 Mb/s at 3.5 Mb/s/s by declaration and the tree cannot see
it coming; the endpoint is the event, and round 7's wire-rate landing is
the mechanism that must cover it.)

### stress lane (s3_stress: demand above the capacity, no capacity shape)

`s3_stress` was held judge-free through round 7 ("no controller claim").
The minimal mechanical pass rule frozen here judges what the ACIQ arm
claims on any shape -- it acts and it delivers what it commits:

| Law | Frozen value | Old-code measurement (seeds 1000-1009) |
|-----|--------------|----------------------------------------|
| ACTS | at least one committed policy change | 10/10 (6-8 commits per seed) |
| DELIVER-AS-COMMITTED | last-third bulk.sink mean >= 0.50 of the last-third applied mean | 10/10 (0.613-1.144) |

No interactive-protection number becomes a gate: the workload reports
carry those measurements and no claim has been frozen for them; the
delay columns stay report, not gate (docs/FIX_REPORT.md section 3,
updated to point here).

## Retune #9 -- frozen before the runs (step_up plateau-lock, seeds 1000/1003/1006)

### The measured defect (dev band, 2026-10-31, retune-8 judge: 4 FAIL / 96 PASS / 0 skips)

Three step_up seeds reached only 6 rungs of the x1.25 demand-probe ladder
and then plateau-locked in refusal ticks for the rest of the run
("clear for 10 s but offered X does not demand it", overlimit 4092-4217
per second, delay EMA < 1 ms -- the wire is demonstrably over-subscribed
the whole time). The other seven seeds committed 7-10 rungs and passed.
The pass/fail split was traced to a lottery:

- The pierce ledger spends one stamp per committed rise within a rolling
  60 s window; `budget_left = max_changes_per_min - len(ups_recent)`.
- A spent budget is only ever refilled by `refund_last_change()`, and that
  refund fires only when the harness ATTEMPTS a law-bound apply the law
  refuses. No-op wants (`rate == applied`) early-out in the harness and
  never reach the law.
- Seeds whose estimator ceiling stayed flat after rung 6 (seed1000:
  belief 16.40 / ceiling 14.76 constant to run end) never trigger
  cap.changed, so no refund ever fires: the 7th pierce is budget-blocked
  for the rest of the run (util 0.56). Seeds whose ceiling stepped up in
  lock-step with the ladder got one law-refused no-op bypass per step,
  one refund per step, and the budget stayed live (util 1.01).

Offline replay with kernel latency and the demand signature modeled
reproduces the stall exactly: 6 rungs then plateau at 56.3 with the
ledger at exactly 6.

### The fix

`MAX_CHANGES_PER_MIN` 6 -> 12. The budget keeps its role as a backstop;
upward churn stays paced by the pre-existing hard laws, which the spent
budget never replaced: the law's 5 s dwell between real kernel changes
(the measured rung cadence was 5.3 s in every seed) and the x1.25 step
cap. At dwell cadence a 60 s window cannot exceed 12 spends, so the
budget becomes non-binding and the plateau-lock class is closed without
moving any pacing covenant. Downward change spends nothing (unchanged).

### Predictions to falsify on the next dev band

- step_up seeds 1000/1003/1006 commit to >= 90 of the 100 Mbps target
  (util_delivered >= 0.90) instead of plateauing at 0.56-0.71.
- step_up seeds that passed keep passing; no seed's commit cadence
  quickens below the 5.3 s dwell floor (the dwell still binds).
- No other lane's result changes: the budget spends only on rises, and
  the down/ramp/stress lanes rise nothing.

## Retune #10 -- frozen before the runs (ramp-down landing, seed1005)

### The measured defect (fresh dev band 2026-10-31, retune-8 judge)

`s2b_ramp_100to30` seed1005 landed 9.7 s after the ramp END (first
commit <= 33.0 at rel 39.7 of a 2-step walk 49.38 -> 37.04 (rel 34.4) ->
31.45 (rel 39.7)); the budget is 8.0 s and the other nine seeds landed
0.9-4.1 s after the END. The walk arrived at the ramp END one commit late
(a windshield pierce at rel 6.4/11.9 overshot the walking link; its
arrest delayed the descent walk), leaving the tree at 49.38 vs a link at
30 -- a landing the tree demonstrably knows (the wire carries exactly
31.37, delay EMA 39-52 ms, backlog draining) but the probe-overshoot
branch answered with `emerg=False`, so the law clamped the landing to
one 25 % down step per dwell and the second commit fell 1.7 s past the
frozen budget.

### The fix

The probe-overshoot landing (inflating delay, wire carrying the landing
figure through the tree) now spends one delay-emergency clearance when
one is free (`emerg_free`): the law's DOWN emergency path skips dwell and
the step bound, so the landing reaches the wire's rate in one commit.
The clearance accounting is untouched: a clearance costs its 20 s
cooldown ONLY when the apply commits (the landed-only refund stands), a
clearance-less tick falls back to the dwelled 25 % step clamp as before,
and a real 100 ms delay-shock share the same budget (one per 20 s).
The landing value is unchanged: min(known-good, the wire's carried rate),
floored at the plan floor; DOWN-only by the branch's own `land < applied`
predicate.

### Predictions to falsify on the next dev band

- ramp_100to30 seed1005's first commit <= 33.0 lands within 8.0 s of the
  ramp END (the 31.37 want commits at ~rel 31.3-34.4, one dwell after
  the 29.1 commit it waited behind).
- No seed's landing commits faster than that same signature allows
  (one clearance per 20 s). The other nine ramp-down seeds keep their
  results; their landing values do not change (the wire carried them too).
- step_up/up lanes: an overshoot arrest now lands in one commit instead
  of two dwelled steps; the ladder cadence and the pierce budget are
  untouched. No lane judges this as churn: commits never accelerate
  above the law's one-clearance-per-cooldown covenant.

## Retune #11 -- frozen before the runs (wire-led landing margin, s2b_step_50 seed1001)

### The measured defect (dev band 2026-11-01, post retunes #9/#10, in flight)

`s2b_step_50` (100 -> 50 at t=10) seed1001: the severe-drop landing fired at
t+0.88 s on the FIRST post-drop delivered sample, 55.38 Mbps. That sample is
the pre-drop queue still draining -- the new truth is 50.0, so the landing
sat at 1.108x the truth, 0.38 Mbps ABOVE the judge's 1.10x band top (55.0).
The judge does not count an out-of-band commit as the landing; the tree then
held 55.38 until the belief fell at t+9.5 s and stepped to 49.84, so the
judged landing moved from t+0.88 s to t+9.5 s (budget 8.0 s). The seeds that
passed sampled the drain lower (seed1000 landed 53.31, seed1002 52.76, both
inside the band): the failure is a coin flip on the drain transient, not a
lane behaviour.

The round-6 rule already prefers the drained rate (`recent_delivered_min`
over a 4 s window, retune-tested as `test_landing_uses_the_drained_rate_not_
the_drain_transient`). It only has something to drain TO when an earlier
sample already read below the current carry. seed1001's drop arrived with no
such sample: the current tick WAS the window minimum, and the landing trusted
it verbatim.

### The fix

When the wire-led landing's only sub-applied evidence is the current tick
(the window minimum is at or above the current carry), land with the
ratchet's own 10 % hysteresis below the demonstrated carry:
`land = min(ceiling, delivered, carried) x (1 - WIRE_LANDING_MARGIN_FRAC)`.
A window that has already drained (an earlier sample below the current
carry) lands at the measured rate unchanged -- the round-6 anchor is about
the drained rate, not the transient. The plan-floor clamp and the one-commit
emergency are untouched. Scope is the `wire_dropped` leg only; the round-7.1
stale-low-ceiling leg inside `land_target` lands at a HEALTHY wire the tree
overshot (no queue drain to distrust) and stays verbatim (s7_rampup seed1008
keeps 104.58).

### Predictions to falsify on the next dev band

- `s2b_step_50` seed1001 lands inside the 55.0 band within 1 s
  (49.84 at t+0.88 s) and the other nine seeds keep their landings; the
  cell passes on all 10 seeds.
- No down lane's landing moves ABOVE its previous value: the margin only
  ever lowers a fresh-transient landing by 10 %, and the drained-window
  path (seed1002's 52.39) is bit-for-bit unchanged.
- The round-7.1 stale-low-ceiling anchor is bit-for-bit unchanged
  (s7_rampup seed1008 still lands at the wire's 104.58, not a margin).
- The up lanes are untouched: `land_target` is only reached from the
  inflating and bind down branches; no rise path calls it.
- Landings stay above the plan floor (max(min_rate) clamp) and the
  delivered last-third stays >= 0.5x the truth (0.9x the truth by
  construction in the fresh case).

## Retune #12 -- frozen before the run (the ramp-end rail and the band edge)

The dev band on `19e9e8a5` (2026-11-01 12:15-17:22 IST, seeds 1000-1009,
all 100 cells judged) returned **96 PASS / 4 FAIL / 0 skips**. Retunes
#9/#10/#11 fixed all five earlier failures (step_up seeds 1000/1003/1006
land 1.109/1.147 applied and 0.553-0.678 delivered; ramp seed1005 6.2 s;
step_50 seed1001 1.8 s at 47.54) and exposed two new families, both read
per tick from `data/runs_dev3`.

### A. The ramp-end rail -- `s2b_ramp_100to30` seeds 1001, 1003, 1007

Measured. At the ramp end (t=30.0) the tree sat at 42.14 (1001), 29.83
(1003) and 42.07 (1007) against a 30 Mbps truth (band top 33.0).

* 1001/1007: the ordinary delay ratchet moves 10 % per commit and the law's
  dwell is 5 s, so 42.14 -> 37.93 (t+5.2) -> 31.36 (t+10.4). The
  one-commit overshoot landing at t+0.98 (33.77/33.82) was *dwell-refused*
  (the previous commit was 1.1 s earlier) and `refund_last_change()` dropped
  it; the next tick read `wire_dropped` and the overshoot branch could no
  longer fire, so the landing intent was lost and the ratchet walked.
  Judged 10.4 s, budget 8.0 s.
* 1003: the collapse emergency landed 29.17 at 29.83 -- **0.17 s before the
  nominal ramp end**, i.e. the ramp's last tick -- and the rate never moved
  again. `check_down_ramp` only accepts commits with `t > ramp_end`, so it
  timed the next same-rate commit at 41.40 = 11.4 s. The cell physically
  landed; the judge's window boundary discarded it.

Fix.

* `aciq/ratecap.py`: when the wire has demonstrated it cannot carry the
  applied rate (`wire_dropped`) and the *ordinary delay ratchet* fires, take
  the law's full step envelope (`MAX_RATE_STEP_FRAC = 0.25`) instead of the
  gentle 10 %. The 10 % pace is a delay-only convenience; with a 5 s dwell
  it needs three commits to cross a gap wider than 22 %, which cannot fit
  the 8 s budget. `wire_dropped` is affirmative wire evidence (the same
  fact every landing branch already trusts), so the full lawful step is
  justified. The emergency branches, the step bound, the floor clamp and
  every other branch are untouched.
* `tools/verify_round3.py` (`check_down_ramp`): a rate already inside the
  end-band at the ramp end counts as a landing at 0.0 s. The ramp's
  remaining movement can only LOWER its target, so a commit one tick before
  the end whose rate is <= the end-band is still inside the band at the
  end; the old strict `t > ramp_end` charged the next same-rate commit
  11.4 s later. The tail check (final commit <= band) is unchanged and now
  reads the last commit overall, which is the applied state when no
  post-end commit exists. This is a definition fix, not a threshold change:
  the 8.0 s budget, the 33.0 band and the 0.50 delivered floor are frozen.

Predictions. 1001/1007 land at ~5.2 s (46.82 -> 35.12 at 29.85, then
35.12 -> 31.6 at 35.16); 1003 reports 0.0 s with its existing 29.17
landing; no other ramp seed's landing value, tail or delivered moves (the
25 % step only fires on the `wire_dropped` fall-through, and the emergency
landings are unchanged).

### B. The overshoot band edge -- `s2b_step_50` seed1008

Measured. At t+4.05 the probe-overshoot branch landed at the *instantaneous*
delivered 55.897 on a 50 Mbps truth (band 55.0, 0.897 above) -- the drop
tick's queue still draining -- and only re-entered the band at t+9.42
(judged 9.4 s, budget 8.0 s; `delay_emergency_s=4.1`). The branch capped the
landing at `delivered` but ignored the 4 s drained carry that `land_target`
already uses (round 6).

Fix. In the overshoot branch, when the wire sits BELOW the belief at the
overshoot tick (`delivered < ceiling`: the drop-drain signature, not the up
lanes' stale-low probe, where the wire carries MORE than the belief), cap
the landing at the 4 s carried minimum. seed1008's carried was 52.40 --
inside the band. The up-lane overshoots (s7_rampup 109.12, s7_up_30to100
110.19) carry above the belief and are untouched; the round-7.1 anchor
(s7_rampup seed1008 at the wire's 104.58) stays bit-for-bit.

### Predictions to falsify on the next dev band

- `s2b_ramp_100to30`: 1001 and 1007 land <= 8.0 s (predicted ~5.2 s);
  1003 reports 0.0 s; all ten seeds pass.
- `s2b_step_50`: seed1008 lands 52.40 at t+4.05 and all ten seeds pass;
  no other seed's landing moves above its previous value.
- No up-lane landing value changes; no stress delivered ratio falls.
- The whole band returns 100 PASS / 0 FAIL / 0 skips, or the two new
  mechanisms are falsified and retuned again.

## Round 7 -- the four late ramp-down landings

Measured. The dev band at `f9bd5a90` (300 cells) returned 96 PASS / 4 FAIL.
All four failures were `s2b_ramp_100to30` late landings against the 8.0 s
budget from the 30.0 Mbps ramp end (band top 33.0):

| seed | held at | first in-band commit | why |
|---|---|---|---|
| 1003 | 33.45 from 31.4 s | 57.6 s | ceiling stayed 42.8 until 38.3 s and entered the band only at 44.0 s; the clear branch then held with `offered 32.0 does not demand it` |
| 1004 | 33.12 at 38.0 s | 43.96 s | the landing was 0.12 above the 33.0 band top |
| 1005 | 33.94 at 35.95 s | 41.72 s | the decision at 37.2 s already proposed 30.54; the 5 s dwell deferred it |
| 1007 | 32.86 at 38.04 s | 38.04 s | in band, but the 4.6 s dwell since 32.29 pushed the commit 0.04 s past the budget |

The causes are different: 1005/1007 are cadence, 1004 is rounding, 1003 is a
lagging ceiling. Three mechanisms answer them; all three are confined to
descents and leave the ceiling, step bound, floor and emergency cooldowns
untouched.

* `aciq/verifier.py`: `LANDING_HEADROOM_FRAC = 0.02`. Every DOWN landing is
  shaved 2 % after the law permits it, so a carry measured at 33.121 becomes
  32.46 -- inside the 33.0 band -- instead of sitting 0.121 above it. Up
  moves are never shaved, and the plan floor is re-applied after the shave.
* `aciq/harness.py`: a DOWN move whose delay EMA is above
  `inflation_threshold_ms` (20 ms) skips the dwell for that tick only. A
  lower rate cannot grow a queue, and the rise budget still paces upward
  churn. The same tick also skips the shield's change window.
* `aciq/harness.py`: a `probe overshoot` landing skips the dwell. The
  overshoot branch returns the wire's own carry, which can sit a fraction
  ABOVE the applied rate while still inside the end-band (32.29 -> 32.86);
  that is a corrective landing, not a new probe. The step bound and ceiling
  still apply.
* `aciq/ratecap.py`: the sustained shortfall. Clear delay, the wire carrying
  < `SHORTFALL_CARRY_FRAC` (0.98) of the applied rate, and the tree's own
  saturation witness (a saturated belief or overlimit >= `probe_overlimit_min`)
  held for `SHORTFALL_HOLD_S` (3.0 s) land at the carried rate. A single
  light tick is tolerated for `SHORTFALL_GAP_S` (2.0 s). Under-demand alone
  is explicitly excluded: a healthy bulk rides at 0.89-0.96x applied without
  saturating, so the witness and the drop regime are both required.

Not a new probe, not a threshold move: the 8.0 s budget, the 33.0 band, the
0.50 delivered floor, `MIN_DWELL_S = 5.0`, `MAX_RATE_STEP_FRAC = 0.25` and
the emergency cooldowns are unchanged.

Predictions to falsify on the next dev band. Seed1003 lands at ~31.5 at
t=37.1 (7.1 s); seed1004 lands at ~32.9 at t=36.9 (6.9 s); seed1005 lands
30.54 at t=37.2 (7.2 s); seed1007 lands 32.86 at t=36.9 (6.9 s). All ten
`s2b_ramp_100to30` seeds pass, and no other scenario's landing value or
delivered ratio moves.

## Round 8 -- one carry landing per descent (after the 2026-11-02 full dev band)

The full DEV band at `e84778a9` ran all 300 cells at one engine revision. The
gate judged 99/100 ACIQ shapes PASS. The one FAIL was not a late landing:
`s2b_ramp_100to30` seed1001 landed at 29.37 Mbps at t=35.65 (inside the 8 s
budget and the 33.0 band) and then kept descending to 14.27 Mbps:

| t (s) | branch | applied -> landed |
|---|---|---|
| 35.65 | wire carried 30.0 of applied 33.5 for 3 s | 33.5 -> 30.0 |
| 36.79 | wire carried 23.5 of applied 29.4 for 3 s | 29.4 -> 23.5 |
| 42.24 | belief fell below applied: severe drop | 26.5 -> 21.1 |
| 44.40 | wire carried 18.7 of applied 20.7 for 3 s | 20.7 -> 18.7 |
| ... | ... | ... -> 14.27 |

The cause is the Round 7 shortfall branch re-firing every hold window. A
healthy bulk rides at 0.85-0.95x applied, so `delivered < applied` stays true
forever and each fire chases the overhead down. The gate's delivered floor
(0.50 of the 30 end truth) caught it; the landing-time check did not.

Fix: the carry branch lands **at most once per descent**. `_shortfall_spent`
is set when the branch lands, cleared only by a rise or by the shortfall
window going away (a real re-drop after recovery). A zero carry is excluded
explicitly -- an idle wire is no demand, not a drop, and landing at it would
hit the 14.0 floor. `SHORTFALL_HOLD_S`, `SHORTFALL_GAP_S`,
`SHORTFALL_CARRY_FRAC`, the 8.0 s budget, the 33.0 band and the 0.50 floor
are unchanged.

Predictions to falsify on the next full band: seed1001 fires the carry once
instead of ratcheting. The pre-existing severe-drop path may still step to
the lagging belief's ceiling (~21 Mbps), so the prediction is the delivered
ratio (>= 0.50 of 30, which the ratchet broke at 14.27), not a hold at 30.
The four Round 7 landings stay inside 8 s and the band. Two new unit tests
pin the one-shot rule and the idle-wire exclusion (`TestSustainedShortfall`).

## Round 9 -- the up window is the run's final third (after the 2026-11-02 band)

The 300-cell DEV band at `912a6e2e` (the Round 8 one-shot carry, engine code
unchanged since `e84778a9`) judged 99/100. The one FAIL was not a climb:

`s2b_step_up_20to100` seed1002 -- `up_util_applied=1.10`,
`util_delivered=0.47` (sink mean 47.22 Mbps of the 100 truth).

The applied series is the policy-change log. Seed1002's last change is at
56.4 s of a 64 s run, so `check_up` cut the final third from that log
(42.2-56.4) and ended the delivered window before the steady state. The same
sink log delivers 64.6 Mbps (0.646) over the run's own final third
(45.9-63.9). Seeds 1003 and 1004 read 0.50/0.49 in the commit window and
0.61/0.59 in the run window: the old cut was the failing part, not the
delivered rate.

Fix: `check_up` cuts the window from the post-change sample timeline. The
applied utilization holds the last rate when the window carries no new
commit. The thresholds (applied >= 0.60, delivered >= 0.50), the 8 s landing
budget and every other window are unchanged. A held rate with an early last
commit is pinned by
`test_up_window_is_the_run_final_third_not_the_commit_log_end`.

Judged on the existing `912a6e2e` runs: 100/100 PASS. The final band runs the
same controller at the new pin with this judge; nothing in `aciq/` changed.
