# Task 3 — s6 intent protocol, declared before any evaluation

Written before the 2026 s6 dataset exists (the prior s6 seeds 300-309 ran
the pre-2026 protocol: intent at t~=1s into a 40s run, TTL 15s). The
redesigned protocol fixes two defects the old verifier's own artefacts
documented: the "pre-intent median" for the bulk floor was computed from
~one tick of bulk (the stream had barely started), and the post-expiry
recovery window claimed nothing because nothing was measured for it.

## Declared protocol (every parameter fixed here, before the runs)

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Scenario duration | 60 s (`aciq/harness.py s6_intent_expire`) | A full third of steady-state bulk before the grant; a full third after expiry. |
| Intent request time | t=10 s (CLI default `--intent-at 10.0`) | The bulk stream is in steady state; a floor claim now compares against ~30 ticks of pre-intent receiver evidence, not ~1. |
| Intent TTL | 20 s (CLI default `--intent-ttl 20.0`) | Expiry lands at t~=30, inside the run, with ~30 s of post-expiry evidence for auto-revert AND recovery. |
| Seeds | 310-319 | 10 seeds, disjoint from both the legacy s6 set (300-309) and the Task 2 dev/eval splits (400-409/500-509). |
| Bulk floor (absolute) | `aciq.policy.floor_mbps(link_mbps)` | Floors are the policy's own guarantee (max(FLOOR_ABS_MBPB, FLOOR_FRACTION x capacity) = 5.0 Mbps on the 100 Mbps link); no verifier-picked constant. |
| Bulk floor (relative, stronger) | 10% of the pre-intent sink median, when that median >= the policy floor | Preserves the old verifier's starve check; now measured against a real steady state. |
| Game floor | receiver series > 0 Mbps every second in the window | Existence claim only (adopted unchanged from the old verifier). |
| Recovery | first post-expiry second at which bulk >= 0.90 x pre-intent median; PASS when within 5.0 s of the lease going inactive | 0.90 / 5 s declared here, before the dataset; not tuned on results. Runs whose pre-median never reaches the policy floor (e.g. legacy artefacts) report N/A and join no denominator. |
| Intent timings per run | read from config.json (`intent_at_s`, `intent_ttl_s`) | The verifier judges the artefact the run declares, not a module constant. |

## Unchanged

* The grant path itself (IntentService.handle over the real API surface),
  the auto-revert mechanism (LeaseBook sweep + per-tick sync_lease), and the
  baselines' declared "no intent surface" rows.
* The legacy s6 dataset (300-309) stays on disk and stays verifiable: for
  runs with intent_at 1.0 / TTL 15.0 the verifier reads those timings and
  the recovery line reports N/A where no pre-median was measurable.
