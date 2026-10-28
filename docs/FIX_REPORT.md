# Fix report (round 3) — demand-probe climb and severe-drop landing

Round-3 brief deliverable. The prior round's report (2026-10-23/24, T1–T10
closure) is archived verbatim at `docs/FIX_REPORT_archive_2026-10-24.md`; no
number here comes from it.

Status marker: **PENDING means the verdict awaits runs only root can
make.** Match rule: what the frozen gate `tools/verify_round3.py` prints
is the verdict; prose may not improve on it.

## 1. The declared failures (what was broken, with evidence)

### FAILURE A — up-step stall
`docs/evidence/round3-diagnosis.md` (committed `8f009df`, offline, BEFORE
this report): at the s2b_step_up_20to100 plateau (link truth 100 from
t=7502), the applied tree pinned at **16.52 Mbps for the final 37 s** of
the run (final tick: UNSATURATED, applied 16.5 vs truth 100, 83% off
truth). Chain: belief frozen at 18.36; ceiling stale (no saturated
refresh, conf 0.00); the probe was ARMED (delay clear >= 10 s) but the
old demand gate required `offered > 1.05 x applied` and refused —
unsatisfiable because a tenant's bulk source is window-limited by our
own tree (offered 15.1–16.1 == applied). The controller could never see
the recovery. Round-2 band verdict, 10 seeds: utilization (applied
/truth over the final third) ≈ 0.15; delivered ratio ≈ 0.13. **FAIL.**

### FAILURE B — severe-drop walk (the floor veto)
s2b_step_10 (100 → 10 at t=10): the belief saturated CORRECTLY at 11.06
(ceiling 9.95, conf 1.00) at t=13.6, but the collapse emergency was
vetoed: `min_rate <= ceiling` refused every landing because the plan's
floor total is 14.0 (7 classes x 2.0) > ceiling 9.95, so the law's
25%/5 s envelope walked **7 commits over ~31 s** (80.0 → 60.0 → 45.0 →
33.8 → 25.3 → 19.0 → 14.25) and the tree spent the whole post-drop
window far above the 10 Mbps truth. Round-2 band: bind on ONE seed out
of ten (22.8 s), final-tick applied 14.2/42% off truth on most. The
walk is also the honest explanation of the round-2 CPU/latency budget
being spent on tethered commits, not of controller bugs. **FAIL.**

## 2. The fixes (principle, not tuned patches)

Both land in `aciq/ratecap.py` (commit `53c27bc`), governed by
`GovernorConfig` constants DECLARED in `docs/evidence/round3-params.md`
(`probe_hold_s`, `probe_up_frac`, `probe_demand_frac`,
`probe_demand_gap_s`, `probe_backoff_s`, `probe_running_frac`,
`severe_drop_frac`, `severe_drop_conf` — all marked tune-on-DEV, seeds
1000–1009). The controller's decision rules and 1490-test suite are
greener than round-2's (the suite counts PROBE/SEVERE states, 7 new
tests, all run before the dev band).

### Fix for FAILURE A — the demand probe + probe overshoot landing
- `held_demand` (`offered >= 0.85 x applied` while delay CLEAR, gap
  grace 3 s) replaces the unsatisfiable `offered > 1.05 x applied` gate.
- The step is bounded: one **+25% of applied** pierce per
  `probe_hold_s` window, a **30 s** back after any piercing probe, and
  an overshoot landing `min(known_good, delivered)` in ONE commit when
  the pierced step inflates the wire. A rise that survives its full
  window clear promotes itself to known_good and lifts the cap; the
  pierce precondition (DEV-band retune, round3-params.md) is the
  **overlimit witness**: the probe fires only while the tree is seen
  overlimiting at >= `PROBE_OVERLIMIT_MIN` (50.0/s), so the ceiling
  "climbs as high as evidence carries it" rather than lying the tree at
  the old plateau. (The first landing of this fix used ceiling
  staleness — no saturated refresh within `probe_hold_s` — but the DEV
  band showed a saturated sample refreshes the ceiling AT the pinned
  applied rate forever, so the staleness gate could never lapse and
  the pierce never started; the tree's overlimit counter separates a
  tree pin from a real link plateau.)

### Fix for FAILURE B — the severe-drop landing
- The veto is gone. A confident ceiling (`conf >= 0.6`) below
  **90% of applied** (`SEVERE_DROP_FRAC`, DEV-band retune: 0.6 fired
  too rarely — a 2x drop like s2b_step_50 reads ceiling ~0.89x applied
  one tick in, so the harness kept the 25%-walk and overshot the legal
  band 21% downward) — or any collapse/delay shock as before — commits
  ONE landing at `max(ceiling, floor)` with `delay_emergency=True`,
  bypassing the dwell + step envelope for that single DOWN commit.
  The floor stays respected: when the plan floor (14.0) legally
  exceeds the new link (10), the drop lands on the FLOOR instead of
  walking for 31 s; bind is declared INFEASIBLE-BY-CONFIG there (below
  the class floors no tree can follow the link), not swept into a
  number.

## 3. Verification contract (frozen BEFORE the runs)

`tools/verify_round3.py <runs_root>` computes the verdicts by the
declared rules:

- UP shapes (recover_to / ramp_to above the pre-change link): final
  third **util_applied >= 0.60** and **util_delivered >= 0.50** per ACIQ
  seed. UP bind is `n/a (up-step)`: the round-3 report table says `n/a
  (up-step)` and shows the utilization column instead (committed
  0e6f986).
- DOWN shapes: the first post-drop committed delay-emergency commit
  must occur **<= 8.0 s** after the drop AND the final committed rate
  must stay **within 10%** of `max(truth_after, floor_total)` to the
  run end (the FLOOR-BOUND case judges against the plan floor).
- `s3_stress`: demand-stress scenario, `no_controller_claim` (delay and
  delivered-goodput columns only).
- Provenance: every run's `result.json.commit_hash` must equal the
  engine that generated the report; report headers stamp per-band and
  per-scenario hashes with SUPERSEDED verdicts (commit 0e6f986). A band
  only makes a claim if all its runs share one hash.

## 4. Status

| Item | Verdict | Basis |
| --- | --- | --- |
| FAILURE A pre-fix | FAIL | diagnosis `8f009df` + round-2 band tiles |
| Fix A code | SHIPPED | `53c27bc` + 1490-test suite green + lint |
| FAILURE B pre-fix | FAIL | diagnosis `8f009df` + round-2 band tiles |
| Fix B code | SHIPPED | `53c27bc` + 1490-test suite green + lint |
| DEV band (seeds 1000–1009, tuning) | PENDING | privileged: `sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_round3_batch.sh dev` (~6.5–9.5 h; resume-safe `.done` markers) |
| Freeze constants from dev | PENDING | agent edits `docs/evidence/round3-params.md` + `aciq/ratecap.py` defaults AFTER dev artifacts exist |
| FINAL band (seeds 1100–1109, once) | PENDING | same script, `final`; only AFTER the freeze (~12–14 h) |
| FIX_REPORT verdicts | PENDING | `tools/verify_round3.py data/runs_final3` + RESULTS_FINAL3.md |

## 5. What to run (privileged, ONE script, resumed freely)

```bash
sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_round3_batch.sh dev
#  ^ run inside tmux; ~6.5-9.5 h; safe to Ctrl-C and resume.
#  After the agent freezes constants from the artifacts and commits, run:
sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/run_round3_batch.sh final
#  ^ ~12-14 h; runs the frozen evaluation ONCE, seeds 1100-1109.
```

`ip netns list` must be EMPTY afterward (the script checks and exits 2).
