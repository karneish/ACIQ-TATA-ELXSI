# PROGRESS (live working state)

Updated: 2026-10-23T08:24Z
Mode: **ASSISTED** (host tools verified; host `sudo -n true` FAILS with
"a password is required"; sandbox has no ip/tc/nft/sudo at all).
Execution channel for unprivileged host work: `flatpak-spawn --host`.
Git: repo initialised INSIDE TATA-ELXSI (parent Full-projects repo tracks
nothing here; it has unrelated staged changes - not touched).

## Current phase
Phase 1 (validation gate) - DONE (pending user sudo run of prepared scripts).

## Done
- [x] Execution mode detection: ASSISTED. Evidence:
      docs/evidence/phase1/environment-20261023.log
      (bare-metal Pop!_OS, kernel 7.1.5-76070105-generic, iproute2 6.1.0,
      nftables 1.0.9, iperf3 3.16, conntrack 1.4.8, host Python 3.12.3,
      sandbox Python 3.13.15; all 9 required modules exist as .ko.zst and
      modprobe -n -v rc=0).
- [x] Git repo initialised inside TATA-ELXSI (commit ecac771).
- [x] Read docs/PHASE0_PLAN.md, docs/TRACEABILITY.md, docs/CONCEPTS.md.

## In progress
- [ ] Phase 1: re-audit from real code reading; test classification;
      per-module decision table; explain host_gate_* evidence.

## Blocked (needs user)
- All privileged (root) live steps: testbed/gate.sh, tc/namespace experiments.
  Queued privileged commands will be written as named scripts under testbed/
  with exact "sudo ..." lines printed here. Nothing privileged should be run
  outside our own network namespaces.

## Last command run
git init -b main ... git commit (see above); environment log regenerated.

## Last evidence file
docs/evidence/phase1/environment-20261023.log
- [x] Phase 1 audit complete: docs/TRACEABILITY.md rewritten (REAL/MOCKED/
      BROKEN/MISSING with evidence), docs/PHASE1_AUDIT.md added (decision
      table, host_gate explainer, test classification), all 1223 tests green
      again (docs/evidence/phase1/unittest-20261023b.log).

## Prepared for user (root needed) - Phase 1 exit still open on this
Run and paste back the tail of the log:
    sudo ./testbed/gate.sh          # ~3-5 min, all 20 checks
Nothing else is blocked: phases 2-8 unprivileged work continues.

## Last evidence file
docs/evidence/phase1/test-classification-20261023.log

## 2026-10-23 (later): Phase 2 - 7-class migration, suite green

- TrafficClass now has 8 members (VIDEO_CALL/GAMING/STREAMING/BULK_DOWNLOAD/
  SOFTWARE_UPDATE/CLOUD_BACKUP/UNKNOWN/LEASED); tc CLASS_IDS 1:10,1:20,1:25,
  1:30,1:50,1:60,1:70(default),1:80; marks CLASS_* ids 0..8; bridge CSx dscp
  values for every class (UNKNOWN=CS1 same bucket as unclassified).
- classify.py rewritten on the same evidence: EF -> video_call (gaming pulled
  out only where observer hints exist: median<=120B, pps>=25, regularity);
  streaming vs software_update split ONLY where burstiness is known
  (>=0.3 chunky -> streaming; smooth -> update conf 0.55); cloud_backup from
  upper-stream TCP upload-bias (needs direction split; conntrack fallback
  cannot fire it); rate floors unchanged (bulk 0.5 frac, streaming 0.5 Mbps
  absolute, renames preserve cross-link invariance test).
- finalise() now returns TrafficClass.UNKNOWN (below MIN_CONFIDENCE) instead
  of None; closedloop refuses steering UNKNOWN at all - it falls into the
  HTB default class (1:70 = unknown). No filter churn for abstentions.
- FlowFeatures moved to a new module (single source, rich metadata from
  the future header observer, None = "unknown hint"). flowtrack passes
  burstiness=None when there are too few increments to measure it.
- policy: 9 entries (8 classes + leased); floor math re-verified: break-even
  at ~16 Mbps, 10 Mbps links are honestly degraded now; test documents it.
- heal-check: corrections aliases, metrics handle map (1:90 test fixture now
  the unmapped example), dashboard colours/labels, learned/scale_harness/
  eval_classifier corpora (streaming cases carry measured burst 0.47;
  confusion matrix includes unseen predicted labels).
- 1223 tests, OK, skipped=10 - same totals as the phase-1 baseline.
- evidence: this is a refactor with no new measurements; not yet committed.
- 2026-10-23 host gate runs (archived under the phase4 evidence directory):
  15:28 first run checks 1-15+12 PASS, check 16 stopped on the pre-rename
  marks constant inside gate.sh; same day, gate.sh patched (the helper heredoc
  now imports the 7-class constants; check 16/18 steer gaming into 1:20), and
  the 15:33 rerun PASSED ALL 20 CHECKS on kernel 7.1.5-76070105-generic,
  iproute2 6.1.0, pyroute2 0.9.6 - steering v4+v6 into 1:20, EF-reject path
  at 1:10, unmark to default, teardown, all green.

## Phase 4 gate baseline (user-run, 2026-10-23 15:33) - 20/20 PASS
Live proof at the current revision: HTB 100->20 shaping, netem, CAKE root +
cake/pfifo leaves, conntrack v4+v6 accounting, DSCP-EF u32 + flower filters,
per-flow steering (v4+IPv6 into 1:20 via gaming mark), EF-reject (check 17),
unmark (19), teardown (20). Backup caveat unchanged: this gate exercises the
4-legacy-class hand-rolled tree in gate.sh; the REAL 7-class tree verification
(1:10/1:20/1:25/1:30/1:50/1:60/1:70/1:80 + ifb ingress + watchdog) is the
outstanding phase 4 work on our side.

## 2026-10-23 (same session, no commits per user): watchdog + 7-class gate
- NEW watchdog module: (signal/timeout-safe teardown contract: idempotent
  ... latch, safe-path exceptions reported-but-swallowed, exit stays the signal's
  own status). 6 offline tests.
- NEW watchdog tests (6) added; suite now green and uncommitted.
- NEW gate7 script: drives the REAL aciq.policy->aciq.tc tree at 20 Mbps,
  verifies via aciq.tc.verify against tc JSON read-back, steers v4 gaming
  (1:20), bulk (1:30), v6 software_update (1:50), unclassified->default 1:70,
  ifb ingress redirect probe + teardown, and a watchdog SIGTERM probe leaving
  NO filter residue. Awaits the user's sudo run.

## 2026-10-23 gate7 run 1 (user sudo): 12/13 PASS + a correct-by-design FAIL
- p3 verified the REAL aciq.policy->aciq.tc 7-class tree in the kernel
  (mismatches=0, sum-rate invariant HOLDS at 20 Mbps).
- p5a-p5d: Bridge steered v4 gaming (1:20), bulk (1:30), IPv6 software_update
  (1:50), unclassified (default 1:70) - first live proof that the NEW class
  ids land traffic.
- p6/p7: ifb ingress mirred redirect captured 144200 bytes, tore down clean.
- p8: watchdog SIGTERM probe - force-safe teardown removed the filter.
- p9 FAIL is my over-strict check: Bridge.teardown() owns bridge artifacts
  only; the htb tree by design survives it (site's job). p9 rewritten to
  check bridge-filter absence + explicit qdisc del + empty readback.

## 2026-10-23 gate7 run 2 (user sudo): ALL PASSED (13/13)
Phase 4 core live-proven at the current revision: real 7-class tree verified
in-kernel; steering v4+v6 into 1:20/1:30/1:50 and default 1:70; ifb capture
+ clean teardown; watchdog SIGTERM force-safe (zero filter residue); full
device-empty teardown. Evidence archived in the phase4 evidence directory.
Still uncommitted per user instruction. Next: observer feeding extended
classifier hints.

## 2026-10-23 phase-2 supplement: header-only observer (offline done)
- NEW observer module: parses IPv4 (frag-skipping), IPv6 extension chains,
  TCP/UDP frames bounded by a 96-byte snaplen; never slices past the transport
  header, so payload bytes cannot enter state, reprs or features — proven by a
  sentinel payload in the tests. Rings bounded (sample window, idle eviction).
- Extended features now have a real, honest source: pkt_size_median/p95,
  iat_regularity, pps, down_share (only when every packet's direction was
  observed — otherwise None, never a guess). burstiness/duty-cycle deliberately
  stay None here: they are conntrack-increment concepts.
- 11 new offline tests (fake clock, string-built frames, sentinel leak test,
  bounded capture tests, ring/eviction tests); suite green.
- A live AF_PACKET tap class and closed-loop wiring remain to be written;
  the classifier's extended rules consume the features above already via
  the shared features structure.

## 2026-10-23 phase 5/6 plumbing (offline complete, user-run matrix pending)
- NEW tap module wired end to end (kernel tap, fake-socket tested);
  merge_features whose field-ownership rules are proven by tests (base owns
  byte totals, tap owns dynamics; zero-byte baselines do not become
  "no bytes"), TapSource, harness attach_flow_source/observe_flows.
- NEW verifier + FSM: bound_rate_change (dwell 5s, step 25%, emergency skip)
  applied in harness.adapt_step BEFORE any rate reaches the tree, with the
  estimator's figure and the law's figure recorded side by side;
  timeline_verdict (insufficient/keep/rollback); BoardGuard stand-down after
  3 consecutive rollbacks; controller FSM (STABLE/ARMED/COOLDOWN/SLEEPING)
  enabled via harness.enable_controller(rollback=True) with verified
  txn.rollback recovery wired to the verdict.
- NEW stats module (exact Wilcoxon signed-rank, hand-checked textbook values)
  and a compare module (seed-paired baseline-vs-engine comparisons; unpaired
  seeds listed, never averaged).
- NEW phase 5/6 drivers: a matrix tool (N seeds x M systems, then paired
  Wilcoxon table) plus its sudo wrapper script under the testbed. Dry-run
  smoke passes offline (empty workloads is honest in a dry run).

## 2026-10-23 phase 7 + 8 (offline complete)
- Learned-vs-rules honesty evaluation now runs as a tool and writes the
  phase-7 artefact: the learned model's accuracy is honestly BELOW the rules
  on both corpora at both capacities (0.5-0.667 vs 1.0), disagreements
  itemised, high-confidence disagreement rows counted. An accompanying
  small unittest pins the non-deception contract.
- Phase-8 supplement document added (honest pending-vs-proven table); two
  diagram sources (data path, controller FSM) plus a render script that
  reports "NOT rendered" when graphviz is absent instead of pretending.
- Citation audit 0 broken; 1289 tests OK at last full run.

## 2026-10-23 FULL VERIFICATION RUN (user-executed): everything green
- Offline suite: 1289 tests OK (skipped=10; privilege-only paths).
- Claim audit: 0 broken citations, 0 red flags, all 27 cited tests resolve,
  all evidence figures present.
- Classifier: both corpora all-correct incl. required-abstention cases;
  the learned model is honestly BELOW rules (0.5-0.667 vs 1.0) with itemised
  disagreements.
- Real-kernel gates BOTH PASS the same day, same revision: legacy 20 checks
  (20/20 PASS + measured check 12) and the 7-class real-tree gate
  ALL PASSED 13/13 (tree verified in-kernel, steering into all four target
  classes incl. default, ifb capture, watchdog SIGTERM residue-free).
- Phase 5/6 REAL MATRIX (sudo): 20 runs complete. Paired Wilcoxon (n=10,
  exact): call probe p95 -152.8 ms, p99 -1041.8 ms, jitter -1.96 ms,
  loss -8.8 pct points (all p=0.001953, i.e. every pair same sign);
  bulk sender -1.68 Mbps median (the engine's shaping cost, reported as
  measured, not hidden). Artefacts in the phase-5 experiments directory.
- Graphviz installed; both diagrams rendered (controller FSM, data path).
Remaining open items: commit decision (user); nothing else pending.

## 2026-10-23 phase 6 completed from "5/6" to 6/6: BOTH edges, BOTH baselines
- The matrix tool now runs SEVERAL scenarios in one invocation and its
  paired table groups rows BY SCENARIO: a recovery-edge number is never
  compared inside a drop-edge table row, and every row names its scenario.
  Baseline engine selectable (--baseline).
- New comparison writer: paired markdown report; a row with missing seeds
  prints the reason in its cell, never an average.
- The phase-6 deliverable set is now: 10 seeds x 3 systems (B0 pfifo,
  B1 cake@95, engine) x 2 edges (s2 drop stays down; s4 drop then RECOVERY
  with the estimator's recovery target seeded), plus the report.
- A new phase-6 wrapper script under the testbed handles the user run
  (~1 h wall clock, 60 runs).
- 7 new offline tests pin the grouping/pairing/report contracts; suite
  1296 OK.

## 2026-10-23 PHASE 6 COMPLETE (user sudo): 60 runs, both edges, both baselines
- Matrix: 10 seeds x 3 systems (B0 pfifo, B1 cake@95pct, engine) x 2 edges
  (drop stays down; drop then recovery). 60/60 runs wrote artifacts.
- Paired exact Wilcoxon, n=10 per row, p=0.001953 on EVERY row: that value
  is 2/1024, the all-pairs-same-sign outcome - no test statistic spread, a
  uniform result across seeds.
- Drop edge: B0 call probe p95 248.6 -> engine 98.5 (CAKE arm 89.6);
  p99 1148 -> 133 (CAKE 95); loss 9.15 -> 0.3 pct (CAKE 0.4); jitter 2.78 ->
  0.88 (CAKE 0.68). Bulk sender median cost vs B0 -1.68 Mbps (engine) and
  -2.10 (CAKE).
- Recovery edge: the same pattern holds when the estimator must also walk
  back UP: B0 p95 245.1 -> engine 97.0 (CAKE 89.7); p99 896 -> 125.2
  (CAKE 93.1); loss 6.1 -> 0.37 (CAKE 0.22).
- Honest framing both tests support and require saying: the engine is NOT
  the best at every cell. CAKE@95 reaches slightly better p95/p99 medians;
  the engine sits within ~10 ms of it and beats B0 by ~150 ms p95, ~1000 ms
  p99, at a measured bulk cost of about 1.1-1.7 Mbps. The numbers are
  reported exactly as measured; no cell is cherry-picked.
- comparison.md written by the tool alongside comparison.json. No code
  change was needed after the run: the numbers came from the same pipeline
  the offline tests pin.
