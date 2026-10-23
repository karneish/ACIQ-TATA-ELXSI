# Phase 1 audit - validation gate results

Date: 2026-10-23. Mode: **ASSISTED** (host passwordless sudo FAILS; see
`environment-20261023.log`). No privileged command was executed by the agent.

This file answers the three Phase 1 questions: what the existing evidence
proves, how the 1223 tests classify, and keep/repair/rewrite per module.
The requirement-by-requirement reality matrix is in `docs/TRACEABILITY.md`.

---

## 1. Execution mode + environment

Evidence: `docs/evidence/phase1/environment-20261023.log` (generated 2026-10-23).

- Host: Pop!_OS bare metal (`systemd-detect-virt` prints `none`), kernel
  `7.1.5-76070105-generic`, iproute2 6.1.0, nftables 1.0.9, iperf3 3.16,
  conntrack 1.4.8, host Python 3.12.3, sandbox Python 3.13.15.
- Host `sudo -n true` FAILS ("a password is required"); the agent sandbox has
  no `ip`/`tc`/`nft`/`sudo`/`iperf3` at all. Consequently live privileged work
  CANNOT be run by the agent: ASSISTED mode.
- All nine required kernel modules load-able: every `modprobe -n -v` returns
  rc=0 and the `.ko.zst` files exist under
  `/usr/lib/modules/7.1.5-76070105-generic/kernel/net/sched/` (ifb under
  `kernel/drivers/net/`). Nothing to install.
- What the user must run for live evidence is prepared as named scripts under
  `testbed/` with exact `sudo ...` lines (see the phase notes in PROGRESS.md).

## 2. What the `data/host_gate_*` and gate-log evidence is

**What it is.** Raw artifacts of live runs the user performed with root on this
host, on 2026-10-07 through 2026-10-21:

- `testbed/logs` (timestamps like `gate-20261021-213009.log`) - 74 gate transcripts from
  `testbed/gate.sh` (which re-creates the testbed itself). The most recent,
  `gate-20261021-213009.log`, ran ALL 20 checks to PASS on kernel
  `7.1.5-76070105-generic`: HTB 100->20 Mbps shaping + measurement, netem delay,
  CAKE root and CAKE-vs-pfifo leaves, conntrack byte accounting (loopback,
  forwarded IPv4, forwarded IPv6), DSCP-EF u32 filter (IPv4), flower EF filter
  (IPv6), per-flow flower steering IPv4+IPv6, unmark fallback, bridge teardown.
- `data/host_gate_<name>/` - experiment run directories written by the user-run
  privileged driver `tools/host_gate.sh`, each stamped with the git revision it
  ran at (`REVISION` = `c5da3fd`, commit dated 2026-10-19 on the parent
  workspace clone). Contains: S1 (7 seeds x 3 systems), S3 (7 seeds x 3
  systems), congested S2 (7 seeds x 3 systems), S2 adaptation, recovery, soak,
  tail-latency runs, with `config.json`, `samples.jsonl`, `result.json` etc.
- `docs/evidence/rollback-live-20261013.log` - output of the needs-root live
  rollback test suite (`tests/test_rollback_live.py`).

**What it proves.** The tc mechanics in this repo genuinely work on this
kernel: HTB class rate/ceil math, read-back, per-flow flower filters, ipv4 and
ipv6 steering, conntrack-based observation, netem impairments. It also proves
the experiment driver produces consistent per-seed artifacts with a logged
capacity enum and revision.

**What it does NOT prove.**
- It was produced at revision `c5da3fd` (2026-10-19) on the parent workspace
  clone; files may have changed since. Nothing here is a claim about the
  current tree until the gate is re-run.
- It does not cover the REQUIRED new features: 7 classes, latency-under-load
  estimation, FSM states, ifb ingress, class-target intents, verifier verdicts,
  S4/S5 scenarios, 10-seed FULL matrix.
- `data/host_gate_soak` (30 min) is a single-seed stability run, not a
  statistics source.
- 7 seeds is below the required 10; the reports carry mean (min-max), not
  mean + 95% CI.

## 3. Test suite classification (1223 tests)

Full table: `docs/evidence/phase1/test-classification-20261023.log`.
Post-audit run: `docs/evidence/phase1/unittest-20261023b.log` - **1223 tests,
OK, skipped=10** (the skip mechanism is `@unittest.skipUnless(shutil.which("tc"), ...)`
plus `os.geteuid()` and namespace-availability checks in
`tests/test_rollback_live.py` and `tests/test_fairness_live.py` only).

| Category | Count | Files |
|---|---|---|
| Needs real kernel (root+tc, auto-skip) | 13 | test_fairness_live (7), test_rollback_live (6) |
| Kernel path exercised via FakeRunner / in-memory Kernel double | 544 | test_enforce, test_rollback, test_harness, test_intent, test_experiment, test_closed_loop, test_capacity_bottleneck, test_saturation_source, test_metrics, test_initial_link_shaping, test_rollback_live_sim |
| Logic-level only (pure units, no kernel doubles) | 666 | e.g. test_classify, test_policy, test_capacity*, test_corrections, test_marks, test_measure, test_dashboard, test_api_*, test_acceptance |
| Real sockets but no root (loopback UDP) | 14 | test_measure_integration (7), test_probe_latency (7) (counted inside the 666 above) |

So: of 1223 tests, exactly **13 touch real tc/namespaces**
(and only the user can run them today); **1210 never touch a kernel** -
they either use the FakeRunner double, pure functions, or loopback sockets.
There is also one live gate script (`testbed/gate.sh`, 20 checks) which is not
part of the unittest count.

## 4. Per-module decision table

| Module | Existing artifact(s) | Decision | Reason |
|---|---|---|---|
| Observer | aciq/flowtrack.py (conntrack) | **keep + repair** | conntrack read/parse/eviction verified live; but no per-direction split, no packet sizes, no IAT -> add a header-only observer module and extend features. |
| Classifier | aciq/classify.py, model.py, corrections.py | **keep + repair** | solid rule engine with confidence/abstention/corrections; must extend 3 -> 7 classes + unknown and port rules to new features. |
| ML | aciq/learned.py | **rewrite** | trains on a hard-coded synthetic set, not the generated labelled data; features leak own generator ports; not wired into evaluation. Phase 2 rebuilds it as an optional comparison. |
| Capacity | aciq/capacity.py | **keep + repair** | real saturation/step/recovery machinery (live-verified counters); add latency-under-load signal + configuration for shaper fraction. |
| Policy | aciq/policy.py | **keep + repair** | floor/ceiling invariants sound; needs 7 classes, bounded shaper fraction, min/max shape bounds. |
| FSM | aciq/shield.py only | **keep shield + new state machine** | shield is a good internal veto/latch; required 7-state FSM is a new module that will drive shield. |
| Enforcer | aciq/tc.py, qdisc.py, bridge.py, marks.py, txn.py | **keep + repair** | live-verified HTB/CAKE/flower path; add per-cycle rate-change magnitude bound, ifb ingress path, nftables marking brought out of dormancy OR documented flower-only reliance, and signal/watchdog safe path. |
| Verifier | none | **new** | verdict logic + worse->rollback is absent. |
| Controller loop | `adapt_step` in aciq/harness.py + experiment driver only | **keep + wrap** | the tick loop exists and is live-proven; a controller module will formalise FSM+verifier around it. |
| Watchdog | none | **new** | SIGTERM/SIGINT/timeout -> force_safe. |
| Intent | aciq/intent.py, api.py | **keep + repair** | leases real (live run evidence data/ab_lease_42/); add class target, conflict rules, audit log wiring for intent lifecycle. |
| Dashboard | aciq/dashboard.py | **keep + repair** | six panels + policy tiles real; add FSM state panel, per-class confidence, intent/correction controls. |
| API | aciq/api.py (stdlib http.server) | **keep** (documented deliberate choice) | hardened (auth/rate-limit/replay); FastAPI replacement optional at Phase 8 only. |
| Experiments | aciq/experiment.py, harness.py, report.py, run_experiments.py | **keep + repair** | run matrix + honest reporting exist; add 10 seeds + 95% CI + results/ layout + S4/S5 + Makefile demo. |
| Testbed | testbed/setup.sh, cleanup.sh, gate.sh, workloads/ | **keep + repair** | live-verified dual-stack topology; extend to laptop/gaming/3 TVs/backup+update namespaces + server ns + bridge; game pacing 30->60 Hz; add update/backup generators; scope the host-wide `pkill -x iperf3` in cleanup. |
| Scenarios | harness SCENARIOS (S1-S3 + s4_capacity_recovery) | **keep + repair** | rename s4_capacity_recovery -> s2b; add S4 (class intent) and S5 (failure injection). |

## 5. Honest unknowns

- Whether gate.sh still passes at the CURRENT tree revision - can only be
  checked by the user (root). Command prepared below.
- Whether `ifb` ingress shaping interoperates with the existing flower steering
  under netns (needs the live Phase 4 gate).
- Exact controller CPU overhead at 100 Mbps under the AF_PACKET observer
  (to be measured in Phase 2/7).
