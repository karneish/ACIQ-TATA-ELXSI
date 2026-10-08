# Setup Guide

Verified on the development machine. Exact versions recorded because the brief
asks for them and because two behaviours turned out to be version-sensitive.

## 1. Requirements

| Component | Verified version | Notes |
|---|---|---|
| OS | Pop!_OS 24.04 (Ubuntu 24.04 base) | |
| Kernel | `7.1.5-76070105-generic` | Pop!_OS kernel; must provide the qdiscs below |
| `iproute2` | 6.1.0 | provides `tc` and `ip` |
| `conntrack` (conntrack-tools) | 1.4.8 | per-flow byte counters |
| `nftables` | 1.0.9 | |
| `ethtool` | 6.7 | |
| `iperf3` | 3.16 | |
| Python | 3.12.3 (venv) | standard library only |

### Kernel modules

All of these must be loadable. `sch_cake` in particular does **not** auto-load,
and a testbed that depends on it being resident from an earlier run is not
reproducible:

```bash
sudo modprobe sch_htb sch_netem sch_cake sch_fq_codel sch_prio \
                act_gact act_police cls_flower cls_u32 nf_conntrack
lsmod | grep -E 'sch_(htb|netem|cake|fq_codel)|nf_conntrack'
```

A module built into the kernel will not appear in `lsmod`; that is not a failure.

## 2. Install

```bash
sudo apt update
sudo apt install -y iproute2 iperf3 conntrack ethtool nftables python3-venv

# optional: only needed for the full 14-check gate, not for running ACIQ
python3 -m venv ~/aciq-venv
~/aciq-venv/bin/pip install pyroute2
```

See `docs/licenses.md` — the ACIQ runtime itself has **no** pip dependencies.

## 3. Verify before writing any code

```bash
chmod +x testbed/*.sh
bash -n testbed/*.sh                        # syntax
python3 -m unittest discover -s tests       # 260 tests, no root needed

# full gate — needs root, ~2 minutes
sudo env ACIQ_VENV=/home/YOU/aciq-venv ./testbed/gate.sh
sudo ./testbed/cleanup.sh
```

The gate writes `testbed/logs/gate-<timestamp>.log` and stops at the first
failure, naming the check.

## 4. Running the experiments

Needs root.

```bash
sudo rm -rf data/runs
sudo ./run_experiments.py                                  # the 6-run matrix
sudo ./run_experiments.py --scenario s2_wan_drop --system aciq --drop-at 15
sudo ./run_experiments.py --scenario s1_iso_during_call --settle 10
```

The driver calls `testbed/setup.sh` and `testbed/cleanup.sh` itself. Artifacts
land in `data/runs/<scenario>__<system>__<mode>__seed<seed>/` and the report is
written to `data/REPORT.md`.

| Flag | Meaning |
|---|---|
| `--scenario` | repeatable; `s1_iso_during_call`, `s2_wan_drop`, `s3_tv_and_gaming` |
| `--system` | `b0_fifo`, `b1_cake95`, `aciq` |
| `--mode` | `static`, `informed`, `adaptive` (baselines always run static) |
| `--drop-at` | seconds into the run at which capacity drops |
| `--settle` | seconds of interactive-only warmup before measurement begins |
| `--dry-run` | build everything without touching the kernel |
| `--no-setup` | assume the namespaces already exist |

**Each run deletes its own directory first.** `data/runs/` is git-ignored for
that reason. The frozen baseline in `data/baselines/v0/` is versioned.

## 5. What the testbed builds

Three network namespaces, nothing on the host network is touched:

```
client  (10.0.1.2,  fd00:1::2)  ← the household devices
router  (10.0.1.1,  fd00:1::1)  ← ACIQ; tc enforcement here
wan     (203.0.113.2, fd00:2::2) ← "the internet"
```

- Downloads (wan → client) are shaped on the router's **LAN-facing** egress,
  `veth-lan`. **Uplink is not shaped** — a stated limitation.
- The emulated slow link is **HTB class `1:1`**, not `netem`. `netem` supplies
  delay and loss only.
- GRO/GSO/TSO are disabled on all four veth ends; left on, they distort
  packet-size measurements and silently invalidate classifier numbers.

## 6. Troubleshooting

| Symptom | Cause |
|---|---|
| `Specified qdisc kind is unknown` | `sch_cake` not loaded. `modprobe sch_cake`. |
| `cannot stat /proc/sys/net/netfilter/nf_conntrack_acct` in a fresh netns | The `nft` rule must be installed **before** the sysctl is set; the sysctl does not exist until conntrack is pulled in. `setup.sh` does this in order. |
| `Operation not permitted` from `tc` | Not root. All `tc` commands must run via `sudo ip netns exec router …`. |
| conntrack shows no `bytes=` | `nf_conntrack_acct` must be enabled **before** the flow is created. Accounting only counts flows created after it is on. |
| `apply_system failed: read-back mismatch` with every class missing | The read-back source returned nothing. `M4` prefers **text** `tc class show` (verified by gate check 10) and only falls back to `tc -s -j`. |
| `rate_limited: Ns since last change` | The shield's 5-second change window. Expected; it defers rather than fails. |
| `iperf3: the server is busy` | Back-to-back runs. `rate()` sleeps 1 s first. |

## 7. Cleanup

```bash
sudo ./testbed/cleanup.sh
```

Idempotent. Removes the namespaces, which removes the veth pairs and `tc` rules
with them. Note it also runs `pkill -x iperf3`, which will kill any `iperf3` you
started yourself.