# End-to-end acceptance

Covers §17. The complete experiment, and exactly how far it has been run.

## Topology

The repository's existing namespaces, not a new framework:

```
client 10.0.1.2  ──veth-c──  router (10.0.1.1 / 203.0.113.1)  ──veth-wan──  wan
                          shaping on veth-lan: htb root, fq_codel leaves
IPv6: fd00:1::2 ── client, fd00:2::2 ── wan
devices: 203.0.113.3 game, .4 tv1, .5 tv2, .6 tv3
```

## Concurrent workloads

| workload | generator | characteristic |
|---|---|---|
| call | `call.py` (UDP probe) | latency-sensitive, sequence-aware, measured |
| gaming | `game.py` (UDP, 30 pps) | small, latency-sensitive |
| adaptive video | `video.py` ×3 (TCP) | bitrate ladder 8/5/3/1.5 Mbps, stepped every 6 s |
| bulk | `bulk.py` (TCP) | saturating one-way |
| measurement | `call.py` probe + raw observation stream | per-sequence RTT and loss |

**Synthetic, and labelled as such.** A UDP probe is not a video call; it is a
latency measurement with a call's cadence and packet size. No application-level
quality claim is made from it.

## Phase results

| phase | what it establishes | status |
|---|---|---|
| A — FIFO baseline | unshaped reference | **blocked-environment** |
| B — CAKE 95% | a fair, strong baseline | **blocked-environment** |
| C — ACIQ steady state | classification, policy, kernel state | **blocked-environment** |
| D — capacity reduction | estimate → policy → install → read-back | **blocked-environment** |
| E — recovery | restore to 100 Mbps, measure settling | **blocked-environment** |
| F — adversarial classification | misleading DSCP, confidence handling | **blocked-environment** |
| G — lease conflict | competing leases, capacity invariants | **blocked-environment** |
| H — failure injection | controlled `tc` failure, recovery | **blocked-environment** |
| I — repeat across seeds | matched runs, all preserved | **partially run** |

### What *was* run, and is real

From `data/`, seven paired seeds at `--drop 10 --drop-at 5` with a lease on
`203.0.113.4`:

| seed | tv1 no-lease | tv1 leased | change | parent_max |
|---|---|---|---|---|
| 42 | 17.99 MB | 23.05 MB | +28.14% | 10.19 / 10.07 |
| 43 | 17.96 MB | 23.00 MB | +28.08% | 10.15 / 10.11 |
| 44 | 17.99 MB | 23.05 MB | +28.16% | 10.08 / 10.10 |
| 45 | 17.93 MB | 23.11 MB | +28.92% | 10.08 / 10.11 |
| 46 | 18.00 MB | 23.05 MB | +28.08% | 10.06 / 10.10 |
| 47 | 18.00 MB | 23.06 MB | +28.08% | 10.05 / 10.04 |
| 48 | 18.00 MB | 22.94 MB | +27.46% | 10.08 / 10.07 |

**Exact paired Wilcoxon: p = 0.015625, n = 7, statistic 0.** Ceiling held in all
fourteen runs. Measured by the senders, independent of the controller's own
accounting.

**Phases A–H were not run with the corrected measurement pipeline.** Every
stored run predates the P0 fix, so its `rtt_p95`, `jitter_ms` and `loss_ratio`
are zero and cannot be re-derived. Those phases must be re-run; the command is
below.

## Evidence captured per run

`config.json` (scenario, system, mode, seed, capacities, device→IP map) ·
`result.json` (outcome, notes, `estimator_mbps`, `policy_changes`,
`capacity_change_applied`, `capacity_change_error`) · `samples.jsonl` (per-tick
per-class counters, link counters, verdicts, filters, estimator state) ·
`audit.json` (every commit **with the tree it applied**) · `workloads.json` ·
`<label>.obs.jsonl` (raw probe observations, new) · generator logs.

The run identifier is the directory name, and it is consistent across all of
them.

## The command

```bash
cd ~/Desktop/Full-projects/TATA-ELXSI
python3 tools/run_all.py --check          # refuses cleanly if prerequisites fail

for s in 42 43 44 45 46 47 48; do
  for arm in fifo cake aciq; do
    SYSPARAM="--system $arm"
    [ "$arm" = fifo ] && SYSPARAM="--system b0_fifo"
    [ "$arm" = cake ] && SYSPARAM="--system b1_cake95"
    sudo python3 run_experiments.py --scenario s3_tv_and_gaming \
      $SYSPARAM --enforce --drop 10 --drop-at 5 --seed $s \
      --lease 203.0.113.4 --lease-weight 0.6 --results-dir data/e2e_${arm}_$s
  done
done
```

## The causal chain a reader must be able to trace

```
workload -> observed traffic -> classification -> capacity estimate
  -> intent + policy -> safety decision -> kernel enforcement
  -> read-back verification -> measured QoS -> statistical comparison
```

**Traceable today for phases C (partially), D and G.** Broken at two links:

1. **capacity estimate** — the chain runs from a *commanded* drop, not a
   measured one. The estimator's contribution is replay-verified only.
2. **measured QoS** — throughput, queue depth and fairness are real; latency,
   jitter and loss were not measured at all in any stored run, and the pipeline
   that measures them has never run inside the namespaces.

**Not traceable for phases A, B, E, F, H.** Not run.

## Acceptance criteria

| criterion | status |
|---|---|
| complete causal chain traceable | **partial** — two links broken, stated above |
| no manual editing of results | yes — every figure derived from a stored artefact |
| raw and processed data both kept | yes, now including raw probe observations |
| all runs preserved including failures | yes for what exists; `data/` still mixes pre-fix runs (documented) |

§17.4's requirement that a reader trace the chain end to end is **not met**, and
the two broken links are named rather than papered over.
