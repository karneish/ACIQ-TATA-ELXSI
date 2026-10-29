# Demo execution report

## Status: NOT EXECUTED IN THIS ENVIRONMENT — BLOCKED BY PRIVILEGES (exact preflight recorded)

The canonical scripted demo is `testbed/demo.sh` (authoritative sequence by
inspection: `cleanup.sh` → `setup.sh` → per-arm `run_experiments.py` →
`tools/build_report.py` → `testbed/dashboard_evidence.sh`). It requires root
(`tc qdisc` in netns). The completion environment (this shell) has **no
`sudo` binary** (also no `tmux`), so the demo could not be executed here, and
no `demo-*.log` exists in `testbed/logs/` from any earlier execution either —
that absence was part of the REQ-030 PV finding and it still stands.

| Field |value|
|---|---|
| Command | `sudo env ACIQ_VENV=/home/mekarz/aciq-venv SCENARIO=s2_wan_drop SEEDS=3 ./testbed/demo.sh` |
| Revision | any execution must be at a pinned HEAD (current: `210bd09f` + retuned-band rerun) |
| Exit code | not recorded — not executed |
| Prior committed evidence | `data/host_gate_*` runs (revs `ce53da12`, `fc65349e`, `c5da3fd9`), `docs/ACIQ_COMPLETE.md:435,753`; the harness at `tools/host_gate.sh` |
| Missing | a fresh `demo-*.log` + artifacts under the current revision |

## Execution recipe (when a host with sudo is available)

1. Preflight: `command -v sudo; command -v tmux; ip netns add __probe__ && ip netns del __probe__`
2. Preflight: confirm isolation — the testbed is confined to its own network
   namespaces and virtual interfaces (see `testbed/setup.sh`) and must never
   touch host routing/firewall; verify `ip netns list` before and after (must
   be empty when idle).
3. Run the demo command above with `SCENARIO=s2_wan_drop SEEDS=3`.
4. On success: `testbed/logs/demo-<ts>.log` + `data/experiments/dashboard/`
   + a generated report; append log path here as execution proof.
