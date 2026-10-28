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
