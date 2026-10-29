# Experiment validation report

Roots: data/runs_dev3

| metric | count |
|---|---|
| planned_seed_runs | 146 |
| artifact_complete_runs | 146 |
| valid_runs | 145 |
| passing_runs | 145 |
| failure_drill_runs | 0 |
| invalid_runs | 0 |
| artifact_incomplete_runs | 1 |
| unknown_runs | 0 |

## Per-cell

| cell | value |
|---|---|
| s2b_ramp_100to30__aciq | {"passing": 10} |
| s2b_ramp_100to30__b1_cake_auto | {"passing": 10} |
| s2b_ramp_100to30__b1_cake_cons | {"passing": 10} |
| s2b_step_10__aciq | {"passing": 10} |
| s2b_step_10__b1_cake_auto | {"passing": 10} |
| s2b_step_10__b1_cake_cons | {"passing": 10} |
| s2b_step_50__aciq | {"passing": 10} |
| s2b_step_50__b1_cake_auto | {"passing": 10} |
| s2b_step_50__b1_cake_cons | {"passing": 10} |
| s2b_step_up_20to100__aciq | {"passing": 10} |
| s2b_step_up_20to100__b1_cake_auto | {"passing": 10} |
| s2b_step_up_20to100__b1_cake_cons | {"passing": 10} |
| s7_up_20to60__aciq | {"passing": 10} |
| s7_up_20to60__b1_cake_auto | {"artifact-missing": 1, "passing": 5} |
| s7_up_20to60__b1_cake_cons | {"passing": 10} |

## Problem runs

- s7_up_20to60__b1_cake_auto__adaptive__seed1005: artifact-missing — result.json absent
