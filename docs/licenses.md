# Third-Party Licences

**ACIQ vendors no third-party source code. Nothing is redistributed.**
This file is the complete inventory.

## Python packages

| Package | Version tested | Licence | Where it is used | In the runtime? |
|---|---|---|---|---|
| `pyroute2` | 0.9.6 | BSD-3-Clause | `testbed/gate.sh` — gate check 8, reads qdisc class stats over netlink from inside the `router` namespace | **No** |

### Correcting an earlier claim

Earlier revisions of `PLAN.md` and `README.md` stated that `pyroute2` was "the
only non-stdlib dependency in the MVP" and implied the runtime depended on it.
**That was wrong, and it is corrected here.** Verified by search:

```
$ grep -rn "import pyroute2\|from pyroute2" . --include='*.py'
(no matches)
```

The ACIQ runtime (`aciq/*.py`, `run_experiments.py`) imports **only the Python
standard library**. M4's read-back and M5's metrics collector both shell out to
`tc` and parse its output; they do not use pyroute2.

`pyroute2` appears only in `testbed/gate.sh`, which is a verification script, not
part of the system under test. It is optional for running ACIQ and required only
for the full 14-check gate.

Full text of the BSD-3-Clause licence as it applies to `pyroute2`:
<https://github.com/skvadrik/pyroute2/blob/master/LICENSE>. It is not bundled
here; it is installed by the user via `pip`.

## System software (not redistributed, invoked as external programs)

These come from the Linux distribution and the Linux kernel. They are invoked as
command-line tools; none of their source is included.

| Tool | Package (Pop!_OS / Ubuntu) | Licence | Used for |
|---|---|---|---|
| `tc` (iproute2) | `iproute2` 6.1.0 | GPL-2.0 | all shaping and queueing enforcement |
| `ip` (iproute2) | `iproute2` 6.1.0 | GPL-2.0 | namespaces, veth pairs, addresses, routes |
| `conntrack` (conntrack-tools) | `conntrack` 1.4.8 | GPL-2.0 | per-flow byte counters for M1 |
| `nft` (nftables) | `nftables` 1.0.9 | GPL-2.0 | the rule that activates conntrack accounting |
| `ethtool` | `ethtool` 6.7 | GPL-2.0 | disabling GRO/GSO/TSO on veth ends |
| `iperf3` | `iperf3` 3.16 | BSD-3-Clause | bulk throughput measurement |
| kernel qdiscs | Linux kernel | GPL-2.0 | `sch_htb`, `sch_fq_codel`, `sch_cake`, `sch_pfifo`, `sch_netem` |

## Python standard library only

`aciq/` and `testbed/workloads/` use only: `argparse`, `ast`, `dataclasses`,
`enum`, `json`, `os`, `pathlib`, `random`, `re`, `resource`, `shutil`, `signal`,
`socket`, `statistics`, `struct`, `subprocess`, `sys`, `threading`, `time`,
`typing`, `unittest`. All are PSF-licensed or part of the language runtime.

## This project's own licence

MIT — see `LICENSE` at the repository root.