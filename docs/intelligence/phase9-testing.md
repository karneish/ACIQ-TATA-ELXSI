# Phase 9 — Testing and Validation

## Results actually obtained (this session, `master` local)
| Command | Result |
|---|---|
| `python3 -m unittest tests.test_intelligence_*` | contracts 27 + foundation 15 + modules 21 + integration 7 + outcome 10 + e2e 3 + dashboard 7 + scenarios 18 = **108 intelligence tests, all pass** |
| `python3 tools/verify_round3.py data/runs_final3` | **140 judged PASS, 0 FAIL** (frozen band untouched) |
| `python3 tools/measure_intelligence.py` | decision cycle **~1.08 ms** (candidates 0.44, gate 0.29, predict 0.10, retrieve 0.12, decide 0.08, evaluate 0.04) — budget 1000 ms/tick, headroom >1000×. RSS not meaningfully measurable (bare interpreter variance) — stated, not hidden |
| Citation/acceptance/gates suites | pass (117–240 targeted incl. capacity/classify) |

## Scenario mapping (A–R → `tests/test_intelligence_scenarios.py`)
A healthy→RETAIN · B ISO+conf (bulk progress) · C capacity reduction ·
D TVs+gaming · E bounded intent expiry · F stale→DEFER · G wrong prediction→no change ·
H sim≠actual→RECOVER · I fairness reject · J capacity reject · K apply failure→marked failed ·
L invalid old policy→SAFE_FALLBACK · M recovery bounded · N similar history used ·
O misleading history → empty · P no history → operate w/o it · Q hold-time stability ·
R unknown traffic conservative. (18 tests incl. sub-cases.)

## What was NOT run live in this session (honest limits)
- Live kernel intelligence runs (`--intelligence` on netns). Existing book of
  live runs stays on `main`-era evidence; intelligence live runs are Phase 9's
  remaining step on a sudo host (`tools/run_live_closeout.sh` pattern).
- Full 1605-suite re-run after Phase 9 docs; targeted 240 re-verified after
  Phase 5, intelligence suites re-run every phase.
