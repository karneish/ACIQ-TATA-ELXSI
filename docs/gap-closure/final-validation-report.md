# Final validation report

Covers §23. Every number below came from a command in this repository, on the
host described in `environment.txt`.

## A. Executive summary

**Partially validated.**

| | |
|---|---|
| Per-flow enforcement, IPv4 + IPv6, teardown | **verified on a kernel** |
| Capacity drop enforced | **verified on a kernel** |
| Per-device leases, lifecycle, measured benefit | **verified on a kernel**, p = 0.015625 |
| Controller arithmetic, API security, measurement pipeline | **verified offline** |
| Capacity *estimation* end to end | **not verified** — replay only |
| Latency / jitter / loss in a real run | **not verified** — pipeline new, never run in namespaces |
| Superiority over CAKE | **not established**, and not claimed |
| Rollback under a real `tc` failure | **not verified** |
| Long-run stability | **not measured** — no run exceeds 40 s |

**The binding constraint is environmental, and it is not subtle: this shell has
no `ip`, `tc`, `iperf3`, `nc` or `ping` on any path, and no `sudo`.** Verified
directly; `/usr/sbin` and `/sbin` are listable and contain none of them. The
user shell has them and has run the gate to 20 PASS / 1 MEASURED / 0 FAIL.

Everything below marked blocked is blocked for that reason, with the command
recorded. **Nothing blocked is reported as passed.**

## B. Defects closed

| ID | root cause | change | evidence |
|---|---|---|---|
| P0-001 | zero-valued metric defaults; no validity field | `float \| None` + `metric_status`; dashboard says "not measured" | 27 arithmetic + 7 integration tests |
| P0-002 | `ingest()` keyed by workload label, `poll()` read by class value — never matched | `ingest(..., cls=)`; `labels_for()` | `test_a_workload_label_reaches_its_class` |
| P0-003 | evaluation ingested once, after `collect()` | probes stream `<label>.partial.json`, polled per tick | `test_the_collector_reports_a_value_that_changes_between_polls` |
| P0-004 | `ev.loss_ratio or 0.0` discarded a measured zero | explicit `None` checks | `test_a_measured_zero_survives` |
| P0-005 | no raw probe observations exported | `<label>.obs.jsonl`, losses as explicit nulls | generator and controller agree exactly over a real socket |
| P1-001 | no auth, no bind policy | token auth, enforced bind, rate limit, audit | 27 tests incl. over-the-wire; live refusal demonstrated |
| — | rate table pruned by age only, unbounded under a fixed clock | cap + oldest-half eviction | 1400-client test |

P0-006, P0-007, P1-002 to P1-009 remain open — §C.

## C. Remaining defects

| ID | impact | next action |
|---|---|---|
| P0-006 | the central adaptive claim is replay-only | run the command in `live-adaptation.md` |
| P0-007 | stale-capacity root cause not established | instrument whether saturated samples were produced and not recorded |
| P1-002 | IP-only identity; reuse transfers privilege | identity model, or accept and document as a deployment assumption |
| P1-003 | no held-out classifier evaluation | **partially done** — 16 constructed cases; needs a larger labelled set |
| P1-004 | CAKE comparison inconclusive | re-run all three arms with the corrected pipeline |
| P1-005 | fairness is per-class Jain only; no per-flow | surface per-flow throughput |
| P1-006 | rollback never driven against a real failing `tc` | write `testbed/fault_inject.sh` |
| P1-007 | EF claim honoured below 50% of capacity | consult packet-level bulk evidence in the EF path |
| P1-008 | quality varies with the capacity assumption | validate across the estimator's range |
| P1-009 | port fallback overrides behaviour | gate the fallback on inconclusive rate rules |
| P2-001 | three dashboard panels unmeasured | **root cause is P0-001**; data now flows, namespaces pending |
| P2-002 | no memory/scale/soak measurement | **partially done** — arithmetic measured; `tc` cost and soak blocked |

## D. Test results

```
$ python3 -m unittest discover -s tests -t .
Ran 746 tests in 6.450s
OK                                                    exit=0
```

| | count |
|---|---|
| Passed | **746** |
| Failed | 0 |
| Skipped | 0 |
| Blocked (not executed) | ~35 kernel-level scenarios, enumerated per document |
| Not executed | phases A–H of the end-to-end experiment |

Growth during this work: 682 → 746. Of the 64 added, 34 are measurement, 27 are
API security, 3 are the reworked collector tests.

Gate: **20 PASS / 1 MEASURED / 0 FAIL**, last run `gate-20261011-165455.log`.
**Not re-run since these changes** — the harness and metric collector both
moved. That is the first thing to do on a host with `sudo`.

Claim audit: `tools/audit_claims.py` exits 0 — 11 constants agree with the code,
all cited evidence present, no red-flag phrases.

## E. QoS results

**Throughput, queue depth and fairness are real. Latency, jitter and loss were
not measured in any stored run.**

Throughput and the ceiling (fourteen runs, `--drop 10 --drop-at 5`):

| arm | parent_max | total |
|---|---|---|
| no lease | 10.05 – 10.19 | 305.27 Mb |
| lease | 10.04 – 10.14 | 302.08 Mb |

Baseline configurations are recorded in `baseline-comparison.md`. Against
`b0_fifo`, p = 0.0312. Against `b1_cake95`, **no significant difference** — and
no superiority claim is made anywhere.

The comparison is currently inconclusive rather than negative, for two stated
reasons: the latency pipeline was broken when those runs were made, and the runs
were not contended (71% utilisation is not congestion).

## F. Capacity-estimation results

**Replay of a recorded run** — `data/ab_lease_42`, captured before the estimator
had a backlog signal:

```
100 → 45.97 → 24.38 → 15.41 → 12.15 → 10.86 Mbps      (true capacity 10)
```

Monotone, never below the link. Seven tests, including that no intermediate
estimate falls under the true capacity.

**Live trajectory, detection delay, policy-install timing and final verified
kernel state: not measured.** Command in `live-adaptation.md`.

What *is* verified separately: the drop itself. Parent `100Mbit → 10Mbit`,
`capacity_change_applied: True`, ceiling held across fourteen runs. That is
enforcement — commanded, not measured by M2.

## G. Classification results

`tools/eval_classifier.py`, 16 constructed cases, ground truth from the workload
profile:

| capacity | accuracy | macro F1 | abstention | required-to-abstain, did |
|---|---|---|---|---|
| 100 Mbps | 0.6154 | 0.7273 | 0.1875 | **3 / 3** |
| 10 Mbps | 0.8462 | 0.8487 | 0.1875 | **3 / 3** |

Per class at 10 Mbps: interactive P 0.80 R 0.80 F1 0.800 · video P 1.00 R 0.80
F1 0.889 · bulk P 0.75 R 1.00 F1 0.857.

**Abstention is correct in every case that requires it** — the behaviour that
matters most, since forcing a class from no evidence is worse than declining.

Two high-confidence errors persist at both capacities (P1-007, P1-009). Both are
specified and neither is shipped, because this shell cannot run the experiment
that would show enforcement still behaves.

## H. Safety and security results

All 14 shield invariants enforced and unit-tested. API security verified
**over the wire on loopback**, which is the documented deployment model:
unauthorised writes create nothing; a token prefix does not pass; throttled
requests create nothing; the client table stays bounded under 1400 distinct
clients; the token never reaches the audit log; oversized bodies and NaN weights
refused; a traversal path 404s. The bind refusal was demonstrated live:

```
$ ./aciqctl serve --host 0.0.0.0 --port 8091
ValueError: refusing to bind 0.0.0.0: a non-loopback bind exposes POST /intent
to the network, so a token is required.
```

**Rollback against a real failing `tc`: not verified.** `_rollback` also does not
re-read the tree after restoring, so a silent rollback failure would go
unnoticed — a real gap, specified in `enforcement-failure-testing.md`, not fixed.

## I. Resource and scalability results

```
build_plan                     6.95 us mean    19.31 us p99
build_tree + render (12 cmds) 80.14 us mean   119.15 us p99
parse_conntrack_line            5.22 us mean  (191k lines/s)
classify, one flow              9.65 us mean  (104k flows/s)
resident set                    17.2 MB
cpu_fraction, real runs         0.64% peak
```

500 flows cost 4.8 ms of classification per 1 Hz tick. **The cost of issuing the
`tc` commands, and the kernel's filter-chain lookup cost, are unmeasured** and are
likely the dominant terms. Memory growth over hours and concurrent API load:
not measured.

## J. Reproduction

```bash
cd ~/Desktop/Full-projects/TATA-ELXSI
python3 -m unittest discover -s tests -t .        # 746 tests, no privileges
python3 tools/audit_claims.py                     # claim audit, exits 0
python3 tools/bench.py                             # control-plane cost
python3 tools/eval_classifier.py                   # classifier evaluation
python3 tools/run_all.py --check                   # prerequisites; refuses if absent

sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/gate.sh
sudo python3 run_experiments.py --scenario s3_tv_and_gaming --system aciq \
  --enforce --drop 10 --drop-at 5 --seed 42 --lease 203.0.113.4 \
  --lease-weight 0.6 --results-dir data/e2e
```

`run_all.py --check` **currently exits 1 on this host**, listing `root`, `ip`
and `tc` as missing. That is correct behaviour: it refuses before touching
anything, rather than producing an empty result directory that reads like a
successful run.

Cleanup: `sudo ./testbed/cleanup.sh`. Every namespace is created and destroyed by
`setup.sh`; gate check 20 verifies no filter residue.

## K. Evidence-based conclusion

**Satisfied.** Per-flow enforcement, capacity-drop enforcement, per-device lease
mechanics and the lease's measured effect (p = 0.015625, n = 7) — all on a real
kernel, all with committed artefacts. Controller arithmetic and API security,
verified offline against the real handler.

**Partially satisfied.** Classification (real numbers, two high-confidence
defects open). Fairness (real per-class guarantee, no per-flow or starvation
measurement). Measurement pipeline (correct and tested, never run in
namespaces).

**Unverified.** Live capacity adaptation. Latency/jitter/loss in a real run.
Rollback under a real `tc` failure. Long-run stability. Any protocol outside
TCP/UDP on the bridge. Per-flow fairness. Restart reconciliation against live
kernel state.

**Failed.** Nothing failed a test.

**Explicitly not claimed.** That ACIQ outperforms CAKE — the data shows no
significant difference, and the comparison is inconclusive for two reasons
stated in `baseline-comparison.md`.

The largest honest limitation is not any single defect but the environment: with
`ip`, `tc` and `sudo`, the remaining items are experiments rather than
engineering, and the two classifier rules already specified could be landed and
measured in a single session.