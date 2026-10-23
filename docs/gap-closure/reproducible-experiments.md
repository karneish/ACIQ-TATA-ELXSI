# Reproducible experiments

Covers §18.

## Entry point

```bash
python3 tools/run_all.py --check      # prerequisites only, no privileges needed
python3 tools/run_all.py --gate        # the 21-check gate (needs sudo)
python3 tools/run_all.py --matrix      # paired seed matrix
python3 tools/run_all.py --report      # re-derive a report from stored data
```

`--check` reports, rather than assumes:

| prerequisite | how it is verified |
|---|---|
| `ip`, `tc` | on `PATH` and executable |
| kernel modules | `/proc/modules` readable |
| privileges | `geteuid() == 0`, or a clear refusal |
| venv | the configured `ACIQ_VENV` exists |
| kernel version | recorded, not checked against a minimum |

**From this shell `--check` fails at the first item**, because `ip` and `tc` are
not installed and `sudo` is absent. That is the correct outcome: it refuses
before touching anything.

## What the runner does, in order

1. record the environment and the git revision into the run manifest
2. build the testbed, or refuse if it cannot
3. start workloads
4. settle, with measurement off
5. sample every tick, ingest probe telemetry **live**
6. apply policy changes, audited
7. tear down, and **verify** teardown rather than assuming it
8. write raw artefacts even if analysis fails
9. generate the analysis

## What exists now, and what does not

| requirement | status |
|---|---|
| deterministic entry point | **added** — `tools/run_all.py` |
| prerequisite check | **added** |
| environment recorded | **added** — into every manifest |
| only its own resources created | yes; gate check 20 verifies no residue |
| raw artefacts preserved on analysis failure | yes — samples are written per tick |
| repeat seeds and manifests | yes, `--seeds` |
| cleanup failure visible | **not implemented** |
| non-zero exit on a failed stage | partially — `--check` refuses; stage failures still need wiring |

## A real reproducibility defect found

**`data/` mixes runs from different source revisions.** `matrix6`, `leaseB`,
`fixcheck`, `dropcheck*`, `dev*`, `ab_*` all sit in one tree with no record of
which code produced them, and several predate the `set_capacity` fix that
changes what "dropped to 10 Mbps" means.

Mitigation in place: `config.json` in each run directory records scenario, system,
mode, seed and capacities, and the stale-capacity runs carry an explicit note.
What is **not** recorded is the source revision.

`tools/run_all.py` records it going forward. Retroactively annotating the old
directories is not done, because a revision stamped onto an old run would be a
guess.

## The rule this project follows

**A failed stage must fail the run.** Not silently, and not with a green
summary. That is why the gate stops at the first failure, and why this document
marks dozens of tests `blocked-environment` instead of quietly omitting them.
