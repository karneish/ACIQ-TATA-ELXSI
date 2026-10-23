# Live kernel enforcement

**Status: BLOCKED.** Not run. Nothing in this document is asserted as observed.

## Why

BLOCKED — this shell is a bubblewrap sandbox with CapEff=0000000000000000. `ip`, `tc`, `iperf3` are not installed at package level (dpkg -s returns not installed), `sudo` is absent, and `unshare --net` fails with EPERM. The user's shell runs the same commands successfully, so this is an environment limit and not a claim about the code.

## What is verified without a kernel

Nothing about enforcement. The read-back verifier, the transaction manager and
the flower-filter renderer are unit-tested against a fake runner, and the bridge
has been exercised by gate checks 15-20 on a host with privileges -- but **not
in this run**, so those results are not re-attributed to this revision.

## The nine-step chain the prompt requires

| step | evidence available here |
|---|---|
| 1 flow observed | parse_conntrack_line unit-tested |
| 2 features measured | FlowFeatures unit-tested |
| 3 classifier selects a class | 16 constructed cases, two capacities |
| 4 policy decision | build_plan unit-tested |
| 5 maps to kernel config | render() unit-tested -- **commands generated, never issued** |
| 6 packets land in the class | **BLOCKED** |
| 7 behaviour measured | **BLOCKED** |
| 8 measurements return to controller | poll()/ingest unit-tested |
| 9 next decision reflects them | **BLOCKED** |

Steps 5-7 and 9 are the ones that distinguish *application-level* correctness
from *kernel-level* correctness, and they are exactly what this environment
cannot reach. Generating a correct command is not proof it was applied.

## What previous runs established, and what that is worth

Committed evidence from earlier revisions, on a host with privileges:

- gate 16: a steered IPv4 flow grows class `1:20`
- gate 18: a steered IPv6 flow grows class `1:20`
- gate 19: removing the filter returns the flow to the default class
- gate 20: teardown removes the bridge's filters
- `dev10`: parent ceiling held at 10.04-10.19 Mbps across fourteen runs

**These were not re-run against this revision.** The harness, the metric
collector and the classifier all changed, so the gate result is stale by
construction. It is reported as prior evidence, not as a current PASS.

## The command

```bash
cd ~/Desktop/Full-projects/TATA-ELXSI
sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/gate.sh
```

Expected: 20 PASS / 1 MEASURED / 0 FAIL. Any FAIL is a regression from this
revision's changes, and the first suspect is the metric collector.
