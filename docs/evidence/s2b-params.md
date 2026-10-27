# S2b — generalization scenarios, declared before any run

The shipped suite tunes nothing on these: S2b exists to see whether the
controller's adaptation machinery, tuned on the S1-S4 bands, generalizes to
capacity changes it was never tuned on. Every parameter below is fixed here,
before the S2b dataset exists, and is never revisited on results. Controllers
are not re-tuned for these scenarios; the shipped build runs unchanged.

## Declared scenarios (names, protocols, seeds)

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| s2b_step_50 | link 100 -> 50 Mbps at t=10 s, duration 40 s, workloads call(H)+bulk | A mid-range down-step between the shipped 100->20 (s2) and no-change; tests the controller that learned one drop magnitude. |
| s2b_step_10 | link 100 -> 10 Mbps at t=10 s, duration 40 s | The hardest down-step: near the estimator's floor; shows where the adaptation breaks rather than degrades gracefully. |
| s2b_step_up_20to100 | link 20 -> 100 Mbps at t=10 s (recover machinery), duration 40 s | The magnitude of s4's rising edge with a fresh pair: 5x up. A controller pinned at the degraded rate fails here. |
| s2b_ramp_100to30 | link 100, ramp to 30 Mbps over 20 s STARTING t=10 s, duration 60 s | NEW engine capability (per-tick interpolated link). A moving target is the generalization case a step never tests: the controller must track, not recover once. |
| Workloads | call (DSCP 46 EF, 1 stream) + bulk (unmarked, 1 stream), settle 4 s | Identical to s2/s4 so the S2b numbers read against the S2/S4 tables. |
| Seeds | EVAL band ONLY: 800-809, fresh, disjoint from every earlier band (300-319, 400-409, 500-509, 700-709) | S2b is evaluation-only by decree: no tuning band exists for it, so no parameter can be defended as tuned. |
| Arms | all four: b0_fifo, b1_cake95 (set-and-forget at 0.95 x STARTING link), b1_cake_oracle (0.95 x true link from t=0 where the protocol declares a final capacity), ACIQ adaptive | CAKE-static semantics declared for changes: it is applied at launch and never re-applied; on any change it stays at its launch rate by design (that is what "set and forget" means, and S2b exists to surface the consequences). |
| Enforcement | ACIQ runs --enforce, same as the shipped eval band | Classification under moving capacity is part of what generalizes. |
| Deliver ratios | drop = target: s2b_step_50: --link 100 --drop 50 --drop-at 10; s2b_step_10: --link 100 --drop 10 --drop-at 10; s2b_step_up_20to100: --link 20 --drop 20 --drop-at 10 --recover-at 10 --recover-to 100 (the recover IS the scenario's step; link never drops at 20); s2b_ramp_100to30: --link 100 --ramp-at 10 --ramp-duration 20 --ramp-to 30 | Down-steps reuse the shipped drop path unchanged. The up-step reuses the recover path. Only the ramp needs new engine fields. |

## Declared metrics (computed from artefacts only; no per-scenario tuning)

| Metric | Definition (declared before the dataset) |
|--------|------------------------------------------|
| bind_s (steps) | first sample t >= change_at with \|capacity_mbps - link truth\| <= 10% of the truth, which then holds to the next capacity truth (for the up-step the change is the recover). NOT AVAILABLE when never met inside the run. |
| bind_s (ramp) | first sample t >= ramp_at + ramp_duration where the criterion holds against the final truth (30); the ramp window itself is judged by tracking error, not bind. |
| ramp tracking error | per-tick \|capacity_mbps - link truth(t)\|, mean over [ramp_at, ramp_at + ramp_duration], multi-armed over the arm's seeds. |
| estimate error (final third) | mean \|capacity_mbps - link truth\| over the last third of the run (the changed regime; the third of evidence after the controller could have bound). |
| call p95 (whole-run + post-change) | the wired call_metrics percentile; post-change window = [change_at, end] per run, t-CI across the arm's seeds. |
| bulk goodput (post-change) | receiver/sink inst mean over the last third of the run (after bind could have happened); sender number kept beside it. |
| ACIQ admits failure (declared rule) | When the estimator is UNSATURATED (estimator_saturated False on the run's final tick) the run's long-horizon policy MUST quote its own low confidence instead of a firm number: a firm tree applied against a truth it does not measure is that failure. Reported as: saturated(yes/no), final estimate, truth, and the named verdict "no saturation at the final regime" (this is the honesty row the brief asks for: ACIQ's own confidence signal, machine-computed, not a judgement). |
| Paired CIs | n=10 per arm, t-table intervals; arms never pooled across scenarios. |

## Pass/fail posture

S2b reports; it does not gate. Where ACIQ fails (bind not reached, tracking
error high, or the honesty row says unsaturated with a firm tree), the table
SAYS SO in the row text -- the failure admission is part of the deliverable,
not something to smooth over. Baseline behaviour (CAKE static staying at its
launch rate on the up-step) is stated, not excused.
