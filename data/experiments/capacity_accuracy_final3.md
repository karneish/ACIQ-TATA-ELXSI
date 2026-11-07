# Capacity accuracy — final band (derived from data/runs_final3, engine 7c6c7235780a)

Derived artifact: frozen final band is NOT rerun. Numbers below are computed from `result.json:estimator_mbps` and the last `samples.jsonl:capacity_mbps` (applied parent / governor rate) vs scenario truth (final link_end_mbps).

- ACIQ runs: 140
- estimator_mbps MAPE 33.4%, median 23.4%
- applied last-capacity MAPE 28.4%, median 13.9%

Interpretation: `estimator_mbps` is the estimator's internal EWMA; `capacity_mbps` is what the enforcement path actually applied. On up-steps the applied rate tracks truth (86–120 Mbps) while the estimator lags (seed-high-water / release logic). The s4_capacity_recovery runs show the known defect: applied ~17 Mbps while truth recovers to 100 — see fix target in `aciq/experiment.py` (seed high-water on recover/ramp).

Per-scenario means (est / applied):

| scenario | truth | est_mean | applied_mean |
|---|---:|---:|---:|
| s1 | 100 | 78.6 | 89.4 |
| s2 | 20 | 21.4 | 18.9 |
| s2b_ramp_down | 30 | 25.3 | 25.6 |
| s2b_step_10 | 10 | 11.6 | 14.0 |
| s2b_step_50 | 50 | 40.8 | 36.7 |
| s2b_step_up | 100 | 38.8 | 97.5 |
| s3_stress | 100 | 84.5 | 92.6 |
| s3_tv | 100 | 40.5 | 52.2 |
| s4_recovery | 100 | 16.3 | 17.0 |
| s7_down_15 | 15 | 13.6 | 14.0 |
| s7_down_8 | 8 | 9.0 | 14.0 |
| s7_rampup | 100 | 52.3 | 102.4 |
| s7_up_60 | 60 | 32.8 | 58.2 |
| s7_up_100 | 100 | 51.7 | 119.9 |

Source: `data/runs_final3/*/result.json` + last `samples.jsonl` capacity.

## Post-band fix (new HEAD, not rerun into final band)

`aciq/experiment.py` now seeds the estimator high-water with `recover_to_mbps`
and `ramp_to_mbps` at run start, so post-recovery release no longer uses a
stale low high-water. The final-band numbers above remain the frozen
acceptance evidence; the fix ships for future bands with unit tests in
`tests/test_experiment.py`.

## Post-band fix (new HEAD, not rerun into final band)

`aciq/experiment.py` now seeds the estimator high-water with `recover_to_mbps`
and `ramp_to_mbps` at run start, so post-recovery release no longer uses a
stale low high-water. The final-band numbers above remain the frozen
acceptance evidence; the fix ships for future bands with unit tests in
`tests/test_experiment.py`.

## Post-band fix (new HEAD, not rerun into final band)

`aciq/experiment.py` now seeds the estimator high-water with `recover_to_mbps`
and `ramp_to_mbps` at run start, so post-recovery release no longer uses a
stale low high-water. The final-band numbers above remain the frozen
acceptance evidence; the fix ships for future bands with unit tests in
`tests/test_experiment.py`.

## Post-band fix (new HEAD, not rerun into final band)

`aciq/experiment.py` now seeds the estimator high-water with `recover_to_mbps`
and `ramp_to_mbps` at run start, so post-recovery release no longer uses a
stale low high-water. The final-band numbers above remain the frozen
acceptance evidence; the fix ships for future bands with unit tests in
`tests/test_experiment.py`.
