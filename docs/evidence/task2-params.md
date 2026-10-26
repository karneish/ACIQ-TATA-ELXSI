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
   the delay reading spikes to 99-149 ms, and the call's p95 lands at
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

## Amendment 2026-10-26 (Task 2 round; declared from the seeds 500-509 EVAL
## diagnosis BEFORE the next evaluation; no re-tuning of any earlier row)

Declared from the offline diagnosis of `data/runs_eval` seeds 500-509, the
instrumented `data/runs_diag` runs, and the code path audit:

7. **The launch-shaping declaration (#4) must actually reach the kernel.**
   The audit trail of every post-fix ACIQ run shows commit #1 at
   `1:1 rate/ceil = [100.0, 100.0]` on a 100 Mbps link - an UNSHAPED first
   second - exactly the transient row 4 was declared to remove. Cause, read
   from the code: `experiment.py` calls `set_lease(None, link_mbps)` before
   `apply_system(...)`, which pre-seeds `_current_plan` at the full link;
   `apply_system` then takes `plan = self._current_plan or
   build_plan(applied, self._lease)`, so the `INITIAL_PARENT_FRACTION`
   plan never builds. Fix: `apply_system` builds the launch plan from
   `INITIAL_PARENT_FRACTION x capacity` unconditionally for ACIQ runs with
   no lease; a leased rebuild keeps its lease plan. No bound, dwell,
   budget, rollback or safe-state path changes.
8. **Provisional early classification, tier "P", confidence 0.50.** A flow
   with an unambiguous mark at its FIRST sighting (packet DSCP EF, or a
   well-known interactive signalling port from the `INTERACTIVE_PORTS`
   public table - never the workload registry) is claimed provisionally
   as `video_call` at 0.50 confidence, tier `P`, before `MIN_AGE_S`
   maturity. It routes to the class's own fq_codel leaf, so no strict
   priority is granted to any flow a mature verdict would deny, and the
   per-tick maturity gate (2.0 s + 10 packets) still decides the final
   class with the existing rules. On the conntrack-only enforcement path
   (the shipped live path, `experiment.py:1149`) DSCP is deliberately not
   forwarded, so this branch is inert there and the 2.0 s abstention stays
   the declared behaviour; the provisional path activates wherever packet
   evidence (the tap feed) is available. Declared, not invented live.
9. **Hedge low-confidence strict claims into the fair best-effort leaf.**
   `STRICT_MIN_CONFIDENCE = 0.60`: a tier-B claim of a strict class with
   confidence below 0.60 is hedged to `UNKNOWN` for steering (the verdict
   still records the would-have-been class). Never applied to corrections
   (tier X) or leases (tier L): operator intent is not behaviour inference.
   Evidence: on seeds 310-319 the 0.55 small-media branch claimed BOTH the
   call and the game flows as `video_call` for the whole run (the game
   mislabel is visible in every enforced seed's verdicts; gaming's true
   class needs the header-observer hints, also already declared). Hedged
   flows ride the default class, which carries `fq_codel` on its leaf -
   per-flow fair by construction - so blockage between hedged flows is
   structurally impossible.
10. **Per-flow fair AQM on every leaf, including default, is a guard, not a
    change.** `build_tree(leaf="fq_codel")` already attaches `fq_codel` to
    all eight classes (1:1, 1:10, 1:20, 1:25, 1:30, 1:50, 1:60, 1:70); the
    unknown/default `1:70` leaf is `fq_codel`. Added to the tests so it
    cannot regress silently.

Unchanged on purpose: `MIN_AGE_S = 2.0`, `MIN_PACKETS = 10`,
`MIN_CONFIDENCE = 0.5`, the rate rules, bounds, dwell, budget, rollback and
safe-state ladder - nothing in rows 7-10 re-tunes a number any earlier row
declared. Evaluation happens ONCE on fresh seeds 800-809 after the DEV-band
(700-709) shakedown; any further change after seeing EVAL data violates the
brief.

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
