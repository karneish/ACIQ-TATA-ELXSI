# Task 2 — redesign parameters, declared before any evaluation

Written before a single code line of the redesign, from the offline diagnosis
of the POST-FIX run artefacts only (seeds 200-209, `data/runs/*__aciq__adaptive__*`).
No parameter below may be re-tuned after evaluation data exists. Evaluation
never runs on this file's sources: it runs once, later, on seeds 500-509.

## The defect chain the artefacts prove

1. **The law cannot keep up with a 5x drop, and the budget then starves it
   permanently.** In every S2/S4 run (10 + 10 seeds): exactly 3 commits. The
   drop-tick commit is step-clamped (86.22 -> 64.67 Mbps against a deliverable
   20). The governor wants 19.43 (0.90 x belief 21.59) on the next tick; the
   dwell (5 s) refuses it, and the run artefact then records
   "rate change budget exhausted (6/min)" on every remaining tick (7-8 in S2's
   40-tick runs, 27-28 in S4's 60-tick runs). Six `changed=True` stamps - 3
   committed, 3 dwell-refused and not refunded in these runs' engine version -
   filled the 6/min ledger for the rest of the run. The kernel root therefore
   sat at 64.666/64.529 Mbps (3.23x the link) from the drop until run end,
   CAKE-static's ~1.5 ms.
2. **The law's only fast path cannot see this failure mode.**
   `EMERGENCY_DROP_RATE_PER_S = 500` requires >= 500 drops/s on the child
   classes. A capacity drop here does not produce drops in any of the 20 runs
   (`drop_rate_per_s` is 0.0 on every tick): the netem at 20 Mbps backs the
   queue up instead of dropping it. The one mechanism designed to skip the
   dwell never fired. (`law_events` is empty in all 20 runs.)
3. **The first second is unshaped, and S1 pays for it in warm-up.** ACIQ's
   tree is built at `start_capacity = link_mbps` (100), so the launch ramp
   burst (1.25-1.89 MB in the first ticks) queues in the netem's own buffer,
   the delay reading spikes to 99-149 ms, and守法 the call's p95 lands at
   82-84 ms against CAKE-static's 1.45 ms. The first governor commit (90, at
   t~1 s) already lands at the rate the controller wanted all along - the
   transient is purely the pre-commit window.

## Parameters declared (all derived from the artefacts above, not from any
## future evaluation)

| # | Parameter | Value | Where | Justification from artefacts |
|---|-----------|-------|-------|------------------------------|
| 1 | `DELAY_EMERGENCY_MS` | 100.0 | verifier.py | The law gains a delay-driven emergency: when the recorded delay EMA is >= 100 ms, a DOWN move may land at the want in one commit. 100 ms is the transient level measured in runs (99-149 ms) and 1/2 the pre-fix catastrophe (238-250 ms); it cannot fire on a healthy link whose residue is 0.9-1.7 ms. |
| 2 | `DELAY_EMERGENCY_COOLDOWN_S` | 20.0 | ratecap.py (GovernorConfig) | One delay-emergency clearance per 20 s; between clearances descent proceeds at the dwell-bounded pace. 20 s ~= 4 dwell windows. |
| 3 | Change budget applies to UP moves only | - | ratecap.py | Descent was starved by stamps from refused DOWN attempts (6/min filled by 3 commits + 3 refusals); the budget's purpose (no flap) is already enforced on descent by the 5 s dwell. UP probing keeps the 6/min budget. |
| 4 | `INITIAL_PARENT_FRACTION` | = cap_fraction (0.90) | ratecap.py, used at launch | ACIQ's tree is built at 0.90 x the configured link at t=0 instead of 1.00, removing the unshaped warm-up window that produced S1's 82 ms p95. Uses the existing default cap_fraction; no new constant. |
| 5 | `delivered_mbps` added to `GovernorDecision` | - | ratecap.py | Per-tick receiver-side (post-queue) delivered goodput recorded next to belief, so future artefacts can compare the controller's reference against the bottleneck's output per tick instead of only at run end. |
| 6 | `CAPACITY_EMERGENCY_COLLAPSE_FRAC` | 0.5 | ratecap.py (amendment, declared from the DEV band, seeds 400-409, BEFORE any EVAL band run; the DEV gate FAIL 2026-10-26 measured the gap) | A ceiling at or below 0.5 x the applied root is a declared emergency in its own right: it shares the emergency cooldown and bypasses dwell + the law's step envelope for that one DOWN commit, like the delay emergency. Evidence: after s2's post-drop tick the ceiling was 0.21x the applied root while the delay EMA stayed at 37-72 ms (< DELAY_EMERGENCY_MS), so no declared bypass could fire; the law's walk-down (0.25x per commit, one per 5 s dwell) needs ~25 s, and s2's post-drop window (~10-14 s) ran out with the kernel at 51.5 Mbps = 2.57x the link on all ten dev seeds while s4 (60 s run) converged to 0.97x. |

## Unchanged on purpose

* `CAP_FRACTION = 0.90` - 0.90 x (1 + 0.079 belief error) = 0.97 x link; the
  ceiling holds. The +7.9% per-seed residual estimate error is bounded by the
  ceiling and is not re-tuned here.
* `DOWN_STEP_FRAC = 0.10`, `UP_STEP_FRAC = 0.02`, `PROBE_RATIO = 1.05`,
  dwell 5 s, law step 25%, drop-rate emergency (>= 500/s) - all untouched.
* `aciq/policy.py` floors and B0/CAKE arms - untouched (user directive).

## What success must look like (S2/S4, on dev seeds 400-409)

* kernel root within the deliverable within one commit of the drop tick
  (delay emergency fires once), then stays <= 1.05 x deliverable;
* no "budget exhausted" reason for the remainder of any run;
* call p95 no worse than CAKE-static on S1's steady state, and materially
  better than the 62-98 ms POST-FIX p95 on S2/S4;
* bulk goodput does not lose its floor (policy floor intact).

Evaluation happens ONCE on seeds 500-509; any change after seeing that data
violates the brief. The dev split is 400-409 for parameter shakedown only.
