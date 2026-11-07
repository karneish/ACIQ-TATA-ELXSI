#!/usr/bin/env bash
set -euo pipefail
echo "== capacity up-step (s2b_step_up live, new ALPHA_UP) =="
sudo python3 run_experiments.py --scenario s2b_step_up_20to100 --system aciq --mode adaptive --seed 1400 --seeds 1 --no-setup
echo "== individual protocol runs (defaults now include recover) =="
sudo python3 run_experiments.py --scenario s4_capacity_recovery --system aciq --mode adaptive --seed 1401 --seeds 1 --no-setup
echo "== uplink live (s1 with uplink ceiling) =="
sudo python3 run_experiments.py --scenario s1_iso_during_call --system aciq --mode adaptive --seed 1402 --seeds 1 --enforce --uplink 20 --no-setup
echo "== restart reconciliation live (s2 twice, reconcile between via harness) =="
sudo python3 run_experiments.py --scenario s2_wan_drop --system aciq --mode adaptive --seed 1403 --seeds 1 --drop-at 30 --no-setup
echo "== s5/s8 extended seeds (1100-1104) =="
sudo python3 run_experiments.py --scenario s5_update_backup_voice --system aciq --mode adaptive --seed 1103 --seeds 2 --no-setup
sudo python3 run_experiments.py --scenario s8_ipv6_call --system aciq --mode adaptive --seed 1103 --seeds 2 --no-setup
sudo ./testbed/cleanup.sh
python3 tools/verify_round3.py data/runs_final3
python3 tools/measure_intent_fairness.py
echo "live closeout v2 done"
