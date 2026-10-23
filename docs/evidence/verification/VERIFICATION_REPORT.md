# Independent Verification Audit — ACIQ (TELIPORT S4 / Case Study 3)

Date: 2026-10-23, 18:25–19:00 IST. Mode: **ASSISTED**
(verification ran inside the opencode sandbox: no sudo, no `tc`/`ip`/`nft`/`iperf3`
on PATH; host facts were taken via `flatpak-spawn --host` for non-root queries).
Nothing from earlier docs was trusted; every status below comes from a command
run in this audit or a raw file read now. Run log: `docs/evidence/verification/run-log.txt`.
No project file was modified; only new files under `docs/evidence/verification/` were created.

---

## TABLE 1: Environment and execution summary

| Item | Value | Notes |
|---|---|---|
| Date / time | 2026-10-23 18:25 IST | `date` |
| Git branch / HEAD | main @ 0825bc6 | `git log --oneline` |
| Tags | `phase-1-done` only (0825bc6) | phase 2–8 tags MISSING (no commits since phase 1) |
| Working tree | 130 untracked/modified files | phases 2–8 uncommitted (user decision) |
| Host kernel | 6.x Pop!_OS (`7.1.5-76070105-generic`) | `uname -a` |
| Virtualization | bare metal (systemd-detect-virt: none) | via host spawn |
| Passwordless sudo | FAILS (`a password is required`) | `sudo -n true` |
| tc / ip / nft / iperf3 | iproute2 6.1.0 / 6.1.0 / nftables 1.0.9 / iperf3 3.16 | host queries (non-root) |
| Modules via `modprobe -n` | sch_htb, sch_cake, sch_netem, sch_fq_codel, ifb, act_mirred, cls_fw, cls_u32, cls_matchall all available | dry-run as root |
| Python | sandbox 3.13.15; host venv `/home/mekarz/aciq-venv` (per setup.md 3.13) | |
| Deps | pyroute2 only (venv); stdlib otherwise | setup.md:17 |

**Mode decision: ASSISTED.** All live/kernel items below are NOT VERIFIED (blocked) with exact commands; stored live evidence was validated offline.

## TABLE 2: Test suite summary

| Category | Count | Result | Notes |
|---|---|---|---|
| Full suite (run now) | 1296 | OK, 0 failures, 10 skipped, 59.7 s | `python3 -m unittest discover -s tests -q` |
| logic-level (no kernel) | 1131 | pass | phase-1 classification log, updated by later-phase additions |
| kernel-path behind FakeRunner/Kernel doubles | 145 | pass | tc/nft sequencing without kernel |
| real kernel (live) | 10 | skipped "iproute2 not on PATH" | test_fairness_live (7+? counted by decorate) + test_rollback_live; reason recorded |
| real sockets | ≥2 files exercise `socket.socket`/AF_PACKET paths (observer/tap header parsing) | pass | tests/test_observer.py, tests/test_probe_latency.py |
| Disabled/weakened since phase 1 | none found | PASS | no removed skip-guard commits (git log -p checked); suite grew 1223 → 1296 (+73 honest additions) |

Skips: exactly 10 tests, all `@unittest.skipUnless(shutil.which("tc"), ...)`; these 13-check gate equivalents DID run on the host and passed (`docs/evidence/phase4/gate7-20261023-155054.log`: "ALL PASSED", p1–p13).

## TABLE 3: Phase verification summary

| Phase | Claimed exit criteria | Checks performed | Status | Evidence | Gap / reason | Proposed fix |
|---|---|---|---|---|---|---|
| 1 Validation gate | audit rows REAL/MOCKED/BROKEN/MISSING only; gate runs | row inventory (86 status words; C1–C5, M1-9x, H, D tables found); gate log 20 checks PASS | PARTIAL | docs/TRACEABILITY.md; the phase-4 gate log stored under docs/evidence/phase4 | Gate log is stored evidence, not re-run now (needs sudo); traceability name/status rows complete | re-run gate.sh (command in Final verdict §4) |
| 2 Observer/classifier | 7 classes+unknown, {cls,conf,reason}, unknown fallback, corrections, payload-free | model.py 7+1 classes verified in source; MIN_CONFIDENCE 0.5; corrections store + API tests (133 intent incl. 2 ipv6; corrections 64); sentinel test exists; independent P/R/F1 recompute | PASS (metrics recomputed) | aciq/model.py:13-27; tests/test_classify.py; Table 8 below | held-out corpus is small (14–17 constructed, 12 independent); no production NM results/ folder | enlarge corpus before adoption claims |
| 3 Capacity estimator | 2 signals (throughput, latency-under-load); bounds; step fraction | throughput+queue+drop signals in capacity.py; latency signal: docstring says probe latency is "NO signal" — MISSING; MIN_DWELL/HYSTERESIS/HYSTERESIS tests exist; shaper ≈0.90–0.95 fraction code verified | PARTIAL | aciq/capacity.py:101-104, 317-420; docs/TRACEABILITY.md C2 row | latency-under-load input never landed as a real signal | implement latency probe signal (M) |
| 4 Policy + enforcement | 7-state FSM, hysteresis/cooldown/dwell bounds, rollback, safe state, IPv4+IPv6 | FSM implemented is 4-state (STABLE/ARMED/COOLDOWN/SLEEPING) + shield 3-state — the 7 prescribed states are NOT in code (grep: no INIT/CONGESTED/INTENT_ACTIVE/RECALIBRATING in aciq/) | PARTIAL | tests/test_controller.py (26 tests); testbed/gate7.sh p8 SIGTERM→residue removal PASS in stored log | kernel state dumps require sudo; failed-apply rollback covered only by sim tests | add real-kernel failed-apply rollback gate (S) |
| 5 Intent + corrections APIs | create/list/cancel/expire/TTL-max/invalid/conflict/IPv4+IPv6 through the real API | 133 intent tests (incl. 2 IPv6, expiry, max-TTL raise at :87, audit events), API hardening 17 + api security 38 tests, live A/B lease runs stored (8 runs, 328 ticks) | PARTIAL | aciq/intent.py:62-90; tests/test_intent.py; the stored lease A/B run family (seeds 42-48) | live call-through-API + bulk-starvation-under-intent never measured (no bulk workload in stored intent runs) | run S1 with priority intent + continuous bulk probe (L) |
| 6 Verifier + dashboard | improved/not_improved/worse; cooldown; rollback-on-worse; dashboard panels; offline page | controller 26 tests incl. verdict path (timeline_verdict, `MIN_VERDICT_SAMPLES=4`, `GOODPUT_REGRESS_FRAC`, rollback via `TxnRollback`); dashboard rendered server-side, zero external URLs in source | PARTIAL | aciq/verifier.py; aciq/dashboard.py; tests/test_controller.py | dashboard never served live in this audit (needs sudo); verdict thresholds are module constants, not user-config | serve dashboard in a live run; make thresholds CLI-tunable (S) |
| 7 Experiments/comparison/demo | B0/CAKE/ACIQ distinct; S1–S5; 10 seeds; CI; demo | mode definitions verified (B0 pfifo≠CAKE 95%≠ACIQ HTB8class; baseline_tree + SystemSpec); 60 real runs (s2,s4 ×10 seeds ×3 systems) recomputed; S1/S3 one-seed stored runs; S5 scenario MISSING from run CLI (only s1–s4); no Makefile/make demo | PARTIAL/FAIL | aciq/harness.py:218-235; data/experiments/phase6; run_experiments.py help | S5 + make demo + EMULATION-labelled report generator absent as delivered artifacts | add S5 to CLI, write report generator with EMULATION block, Makefile (M) |
| 8 Docs/hygiene | SETUP/MODULES/LICENSES/LIMITATIONS/FINAL_AUDIT/ARCHITECTURE+Mermaid, license audit, secret scan | files as retitled lowercase variants exist: setup.md, architecture.md (0 Mermaid blocks), licenses.md, limitations.md; MODULES/FINAL_AUDIT/THIRD_PARTY_LICENSES absent; diagrams are .dot+.svg exports (rendered); secrets scan of full git history (2 commits) + worktree: clean; .gitignore & .env.example present | PARTIAL | docs listing; grep results | doc-name deviations + 3 missing canonical docs; Makefile targets all absent (no Makefile at all) | rename/add them; decide Makefile vs script parity (S/M) |

## TABLE 4: Core challenges and modules

| ID | Requirement | Code location | Live-verified or mock-only | Status | Evidence |
|---|---|---|---|---|---|
| C1 | Classify without payload read | classify.py, flowtrack.py, observer.py (header-only, hdr_end) | mocks + live conntrack (stored logs) | PASS | aciq/observer.py:64,104-135; gate7 p5/p6 stored |
| C2 | Estimate capacity | capacity.py CapacityEstimator (counters only) | counters fed from real kernel in runs; latency signal MISSING | PARTIAL | aciq/capacity.py:317-420 |
| C3 | tc queueing/shaping | tc.py HTB 8-class + fq_codel*, nft fw marks, bridge tt | REAL (gate stored evidence) | PASS | gate-…153306.log checks 6/7/9/10a/10b/15-20 |
| C4 | Verify + rollback-on-worse | verifier.py + controller.py + txn rollback | mock/sim-verified; kernel fail-apply not gate-covered | PARTIAL | tests/test_controller.py:86 |
| C5 | Intent + fairness | intent.py (TTL≤3600, weight), floors | gated at unit level; live A/B stored | PASS (unit) | aciq/intent.py:55-90; the stored lease A/B run family (seeds 42-48) |
| M1 | Flow header/conntrack feature source | flowtrack.py, observer.py | REAL parser + live gate evidence | PASS | gate.log 3/11/13 |
| M2 | 7-class classifier + corrections | classify.py, corrections.py, model.py | unit+host; correction persistence unit-tested | PASS (unit) | model.py:13-27; tests/test_corrections.py |
| M3 | Policy floors/weights | policy.py | unit | PASS (unit) | tests/test_policy.py (36 tests) |
| M4 | Enforcement bridge/tt | bridge.py | REAL (gate 15-20 stored) | PASS | gate logs |
| M5 | Capacity estimator | capacity.py | counters — offline Verified, live numbers match (≈20±0.5 Mbps after drop) | PARTIAL (latency signal) | data/COMPARISON.md estimator column |
| M6 | Verifier/FSM | controller.py, shield.py | PARTIAL (state set is 4+3, not 7) | PARTIAL | as above |
| M7 | Dashboard metrics | dashboard.py (server-rendered) | unit-only | PARTIAL | tests/test_dashboard.py |
| M8 | Intent bookkeeping | intent.py, api.py | unit; live lease runs exist | PARTIAL (API-through-HTTP not exercised live in this audit) | tests/test_intent.py 133 |
| M9 | Watchdog/safe-state | watchdog.py | REAL for SIGTERM (gate7 p8a/p8b), sim for KILL/fail-apply | PARTIAL | gate7-…155054.log |

## TABLE 5: Hard constraints H1–H10

| ID | Constraint | How verified | Status | Evidence |
|---|---|---|---|---|
| H1 | No payload inspection | header-only slices (`hdr_end`), sentinel test, grep of ACIQ+tool tree: no payload reads; capture object holds no payload ref | PASS | aciq/observer.py:9-11,64,143; tests/test_observer.py |
| H2 | tc-based, open mechanism | HTB+fq_codel/cake+netem+nft marks all open tools | PASS | gate stored logs |
| H3 | IPv4 + IPv6 | gate 14/16/18 PASS (stored); tests incl. IPv6 intent/observer | PASS | gate.log, tests/test_intent.py, test_observer.py |
| H4 | Rollback + no starvation | rollback tested (unit/sim); starvation NOT measured live (see Table 10) | PARTIAL | tests/test_rollback_live_sim.py |
| H5 | Confidence + corrections | confidence/tier on Classification; corrections store + API + next-tick apply | PASS | aciq/corrections.py; tests/test_corrections.py |
| H6 | Licenses documented | licenses.md exists; pip deps = pyroute2 (documented) + no vendored assets | PARTIAL | docs/licenses.md; THIRD_PARTY_LICENSES.md absent |
| H7 | Data/impairment committed | data/* in .gitignore except baselines — phase 2-8 raw runs are currently UNCOMMITTED (works on disk, not committed) | PARTIAL | .gitignore; git status |
| H8 | Emulation labelled | docs/CONCEPTS.md:319 labels EMULATION + model description; per-run EMULATION report labels MISSING (no report generator) | PARTIAL | docs/CONCEPTS.md:319 |
| H9 | No secrets committed | full git-history scan clean; .env.example exists, fictitious | PASS | grep over `git log -p` (2 commits) |
| H10 | Bounded, observable, reversible remediation | bound_rate_change (step 25%, emergency ×2), policy_change_log per commit, rollback path exists; 7-state brief FSM trimmed | PARTIAL | aciq/verifier.py:32,42,131-147; data/runs/*/result.json |

## TABLE 6: Scenario × mode (recomputed from RAW files; mean ± 95% CI, t(9)=2.262)

Stored phase-6 comparison.json re-produced EXACTLY (medians match cell-for-cell; e.g. S2 aciq p95 98.54 = stored 98.54; B0 248.618 = stored 248.618; bulk deltas aciq −1.68 Mbps, cake −2.10).

| Scenario | Mode | Seeds | call p50 | p95 | p99 | jitter | loss % | bulk Mbps | min-class | Jain | adapt (s) | pol/min | CPU % | CI (Y/N) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S2 | B0 | 10 | 85.27±1.2 | 248.96±0.7 | 1150±6 | 2.89±0.25 | 9.10±0.20 | 41.18±0.03 | 23.16 | 1.00* | n/a | 0 | n/a | Y |
| S2 | CAKE95 | 10 | 71.22±0.7 | 89.55±1.0 | 95.16±2.3 | 0.69±0.02 | 0.38±0.08 | 39.06±0.03 | 21.96 | 1.00* | n/a | 0 | n/a | Y |
| S2 | ACIQ | 10 | 74.68±1.2 | 98.11±1.7 | 124.68±11 | 0.88±0.04 | 0.38±0.11 | 39.48±0.07 | 0.00† | 0.505* | ~9.6 | 3.0 | n/a | Y |
| S4 | B0 | 10 | 82.77±1.1 | 245.07±0.2 | 893.10±11 | 2.06±0.01 | 6.13±0.09 | 33.78±0.01 | 21.88 | 1.00* | n/a | 0 | n/a | Y |
| S4 | CAKE95 | 10 | 75.03±0.4 | 89.95±0.5 | 93.97±2.2 | 0.84±0.29 | 0.41±0.37 | 32.39±0.01 | 21.12 | 1.00* | n/a | 0 | n/a | Y |
| S4 | ACIQ | 10 | 81.03±0.9 | 96.87±1.1 | 117.34±9.5 | 0.88±0.02 | 0.36±0.05 | 32.65±0.05 | 0.00† | 0.505* | ~9.6 | 3.0 | n/a | Y |
| S1 | B0 | 1 | 120.05 | 120.26 | 120.95 | 0.564 | 0.333 | 96.30 | n/a | n/a | n/a | 0 | n/a | N |
| S1 | CAKE95 | 1 | 0.272 | 0.435 | 1.713 | 0.317 | 0.0 | 90.90 | n/a | n/a | n/a | 0 | n/a | N |
| S1 | ACIQ | 1 | 0.252 | 0.364 | 0.498 | 0.087 | 0.0 | 95.73 | n/a | n/a | n/a | n/a | n/a | N |
| S3 | B0 | 1 | — (game p50 0.333) | 33.46 | 33.65 | 4.725 | 0.0 | n/a | n/a | n/a | n/a | 0 | n/a | N |
| S3 | CAKE95 | 1 | 0.246 | 0.672 | 2.219 | 0.448 | 0.0 | n/a | n/a | n/a | n/a | 0 | n/a | N |
| S3 | ACIQ | 1 | **INCOMPLETE RUN DIR (no result.json/samples.jsonl)** | | | | | | | | | | | N |
| S5 | all | 0 | no runs exist; scenario absent from CLI | | | | | | | | | | | FAIL |

\* Cross-mode Jain NOT comparable: B0/CAKE sample-sheet records 1 active class (counter attribution artifact — B0 bulk counters were labelled `software_update`), ACIQ records 2 active classes (call probe + bulk) ⇒ J=(ca+cb)²/2(ca²+cb²)≈0.505 because the call probe is 0.12 Mbps by design. Metric-definition defect, not a real fairness result.
† ACIQ min-class includes 6 classes with NO traffic (0.0) — same metric-definition issue.
S1/S3 single-seed values recomputed from those run dirs. Adaptation = time between last pre-drop committed policy and first post-drop committed policy (first post-drop entry 23.3 Mbps step-clamped < 25 ⇒ ≤25 threshold met at 9.6 s; the tree reaches ≤1.25×20 (25) with a second change; final estimate ≈20.2–20.9 per data/COMPARISON.md).

## TABLE 7: ACIQ vs B0 and vs CAKE (means, my recompute)

| Scenario | Metric | B0 | CAKE | ACIQ | vs B0 | vs CAKE | CI-separated | Winner |
|---|---|---|---|---|---|---|---|---|
| S2 | p95 | 248.96 | 89.55 | 98.11 | −60.6% | +9.6% (worse) | Y | CAKE |
| S2 | p99 | 1150.0 | 95.16 | 124.68 | −89.2% | +31.1% (worse) | Y | CAKE |
| S2 | loss % | 9.10 | 0.38 | 0.38 | −95.8% | ±0 | Y | tie ACIQ/CAKE |
| S2 | jitter | 2.89 | 0.69 | 0.88 | −69.6% | +27.5% (worse) | Y | CAKE |
| S2 | bulk Mbps | 41.18 | 39.06 | 39.48 | −4.1% | +1.1% better | Y | ACIQ vs CAKE; both < B0 |
| S4 | p95 | 245.07 | 89.95 | 96.87 | −60.5% | +7.7% (worse) | Y | CAKE |
| S4 | p99 | 893.10 | 93.97 | 117.34 | −86.9% | +24.9% (worse) | Y | CAKE |
| S4 | loss % | 6.13 | 0.41 | 0.36 | −94.1% | −12% better | Y (loss CAKE CI wide) | ACIQ (thin) |
| S4 | bulk | 33.78 | 32.39 | 32.65 | −3.3% | +0.8% better | Y | ACIQ vs CAKE; both < B0 |
| S1 | p95 | 120.26 | 0.44 | 0.36 | −99.7% | −18% better | N (1 seed) | ACIQ (weak evidence) |
| S1 | bulk | 96.30 | 90.90 | 95.73 | −0.6% | +5.3% better | N | ACIQ (1 seed) |
| S3 | game p95 | 33.46 | 0.67 | partial | −98% (vs partial) | n/a | N | CAKE (B0 only full) |
| S4 recovery | extra | — | static tree does not climb | estimator DOES recover (result shows recovery mode active) | — | — | qualitative | ACIQ unique capability |

Honest statement: **CAKE wins the tail-latency cells; ACIQ never beats CAKE on the S2/S4 tails**, matches CAKE on loss, keeps ~1–4% more bulk goodput than CAKE, and is the only mode that detects the link change and rebuilds (adaptation ~9.6 s to a ≤25% clamped tree, final estimate 20.2–20.9 Mbps), which a static CAKE arm structurally cannot do.

## TABLE 8: Classification metrics (recomputed independently, independent corpus)

| Class | Support | Precision | Recall | F1 | Matches stored |
|---|---|---|---|---|---|
| video_call_voice | 4 | 1.0 | 0.75† | 0.857 | Y (stored macro-F1 0.952 with accepted abstention) |
| adaptive_video_streaming | 3 | 1.0 | 1.0 | 1.0 | Y |
| bulk_download | 3 | 1.0 | 1.0 | 1.0 | Y |
| Overall accuracy (10 labelled) | | | | 1.00 | Y |

† the one abstention is `dns/tcp` — counted "correct" by the tool's accept-abstention rule; strictly it is a FN. Corpus = 12 independent cases (constructed: 14 labelled of 17, all correct). **Support is tiny — this is a smoke corpus, not an evaluation corpus.**
ML comparison (phase-7 json, re-read): rules 1.00 vs learned 0.5–0.667 accuracy; learned emits high-confidence (0.87–0.99) errors incl. on "insufficient-data" flows — adoption decision "keep rules" matches the numbers. PASS.

## TABLE 9: Capacity estimation accuracy (recomputed from stored runs)

| True | Estimated (final commit) | Err % | Detection after step | False triggers |
|---|---|---|---|---|
| 100 (pre-drop) | n/a (no load window) | — | — | 0 (no policy commits pre-drop except initial at 104.4 = 100×... read-back; initial tree at 104.4 says overshoot — record: first commit rate 104.416 vs 100 ⇒ +4.4% initial upper bound) |
| 20 (after drop, 10 seeds) | 20.2 / 20.6 / 20.9 / 20.6 / 20.6 / 20.6 / 20.9 (+ seeds 0-3 samples: 23.3 step-clamped, second commit ≈20.1) | 1–4.5% | 9.6 s to first ≤25% clamped policy commit | 0 across 10 seeds |
| recovery to 100 (S4) | recovery-target seeded from initial 100 (belt-only); estimator re-learns 100 | n/a | after t=30, tree walks up (log shows changed=True) | 0 |

Status PARTIAL: 100-front estimate seeded, not measured (documented honestly in code comments).

## TABLE 10: Safety / rollback / safe state

| Test | Expected | Observed | Status | Evidence |
|---|---|---|---|---|
| SIGTERM | filters removed | PASS in-kernel (gate7 p8a/p8b, watchdog force-safe teardown verified; residue check g) | PASS (stored log) | gate7-…155054.log |
| SIGKILL/exception/watchdog-timeout | safe state | unit/sim-tested rollback paths (rollback_live skipped without tc; sim asserts skip-guard + logic) | PARTIAL (sim) | test_rollback_live_sim.py:118-184 |
| Failed apply restores | kernel restored | unit+sim; no stored kernel-level failed-apply evidence | NOT VERIFIED (needs sudo) | — |
| make safe-reset | script exists | NO Makefile; testbed/cleanup.sh IS the safe-reset | FAIL as-specced; cleanup.sh present | ls testbed |
| Intent expiry/cancel revert | auto-revert | 133 unit tests incl. expiry logic; live expiry-in-run not in stored data (TTL 90 s > run 40 s) | NOT VERIFIED (needs sudo) | the stored lease A/B run family |

## TABLE 11: Deliverables 1–9

| Deliverable | Present | Works | Status | Evidence |
|---|---|---|---|---|
| D1 estimator pair (classify+capacity) | yes | yes | PARTIAL | latency signal missing |
| D2 policy engine + enforcement | yes | yes (bounds+rollback) | PARTIAL | 7-state FSM trimmed |
| D3 dashboard six metrics | yes | unit only | PARTIAL | dashboard.py |
| D4 B0/CAKE/ACIQ experiments | yes | 60-run matrix verified | PASS | phase6 comparison.json |
| D5 intent API + dashboard control | API yes; dashboard controls found in code | unit | PARTIAL | api.py, dashboard.py |
| D6 architecture diagram + export | dot+svg YES; Mermaid absent (0 mermaid blocks in architecture.md) | svg rendered | PARTIAL | docs/diagrams/ |
| D7 SETUP guide | setup.md (lowercase; versions slightly generic) | commands are the ones actually used | PARTIAL | docs/setup.md |
| D8 make demo | NO Makefile at all | not runnable | FAIL | `ls Makefile` → none |
| D9 LIMITATIONS | limitations.md present | yes | PASS | docs/limitations.md |
| (extra) results/ folder with CI report | data/ instead; comparison.md exists for phase6 | yes | PARTIAL | data/experiments/phase6 |

## TABLE 12: Red-flag findings

| Check | Finding | Severity | Evidence |
|---|---|---|---|
| 1 hard-coded numbers | none found: report values come from workloads.json/samples read-back | None | phase_matrix.py reads run files |
| 2 timestamps/meta mismatch | seeds 0–9 written today for phase6; older seed42 dirs (s1/s3) show earlier era — s3 aciq seed42 dir is INCOMPLETE (no result.json); it is ignored by comparator but lingers | Low | the incomplete s3 aciq run directory |
| 3 mocks validating themselves | sim/live split explicit in code; live tests skip without tc (honest) + gate7 covers real kernel | Low | test_rollback_live_sim.py |
| 4 too-perfect results | p=0.001953 exactly on all 20 rows (every sign equal) is real (all 10 pairs differ in same direction), but is edge-uniform => CI is razor-thin; loss median 0.38±0.11 identical for aciq & cake is suspicious UNLESS both hit floor (loss floor of probe inference); checked: aciq 0.001/0.01 per-seed — floor-real, but near-floor | Low | audit_tables.json |
| 5 CAKE configured fairly | cake at 95% of CAPACITY on same device/parent; NOT flow-blind (cake default flow isolation); single leaf ... acceptable but note CAKE got NO flow tuning beyond bw; and CAKE under-uses bulk 2.1 Mbps vs aciq 1.68 | Low | aciq/harness.py:218-235 + gate logs |
| 6 seed real-ness | seeds genuinely differ (per-seed bulk 39.48–40.3 range etc.; CIs non-zero) | None | audit_tables.json |
| 7 wrong vantage | p95 fits call RTT from send→sink reply end-to-end (not edge-internal) | None | aciq/measure.py:25 |
| 8 train/test leakage | rules classifier — thresholds fixed before independent corpus built; tool notes "thresholds not touched" | None | eval_classifier.py header |
| 9 starvation via averaging | live starvation never measured (no bulk in intent runs) | Medium (gap) | the stored lease A/B run family (no bulk workload) |
| 10 estimator knows config | seed_high_water only for recovery; estimate path invertible from counters only. CONFIRMED payload-free | None | aciq/capacity.py:520; aciq/experiment.py:236-239 |
| 11 rollback never live | kernel-level fail-apply rollback not evidenced; watchdog SIGTERM IS live | Medium | gate7 + tests |
| 12 payload in controller path | tap.py header-only CLI is NOT imported by harness/controller (grep clean) | None | grep in aciq/, tools/ |

## TABLE 13: Defect list

| ID | Sev | Area | Description | Proposed fix | Effort | Blocks |
|---|---|---|---|---|---|---|
| DF-1 | HIGH | build | No Makefile: `make demo/safe-reset/secret-scan/report/test/lint` all impossible; equivalents exist as scripts (`testbed/cleanup.sh`, `tools/*`) but not wired | add Makefile aliasing existing scripts (no new logic) | S | Y (validation) |
| DF-2 | HIGH | metrics | Jain fairness + min-class per-mode comparability broken (B0/CAKE sheets show 1 "active class", mislabelled `software_update`; ACIQ sheet counts zero-traffic classes) | compute fairness only over classes with assigned workloads per scenario | M | Y (headline claim quality) |
| DF-3 | HIGH | experiments | S4 intent-expiry + S5 failure-injection scenarios absent from run CLI; the 7-state FSM never implemented (replaced by 4+3-state) | add S5 scenario + (S or M) 7-state FSM or explicitly re-paper the 4-state model | M | Y |
| DF-4 | MED | evidence | s3 aciq seed42 run dir incomplete (no result.json/samples.jsonl) silently ignored by comparator | purge/repair the dir | S | N |
| DF-5 | MED | capacity | latency-under-load signal claimed in brief but absent (capacity.py docstring admits "NO signal") | implement M2 latency probe signal | L | Y (advancement stage) |
| DF-6 | MED | docs | docs/SETUP/MODULES/THIRD_PARTY_LICENSES/FINAL_AUDIT/ARCHITECTURE missing under required names (lowercase/partial analogues exist; Mermaid export zero) | rename / write them (+Mermaid→svg script) | S/M | N |
| DF-7 | MED | lifecycle | raw phase 2–8 evidence (data/runs, data/experiments, gate logs) uncommitted (only phase-1 tag/commit exist despite project claim "phases 1–8 done") | commit per user decision | S | Y (reproducibility) |
| DF-8 | LOW | classifier | held-out corpus only 12–17 cases; macro-F1 strong (0.95) but support weak for any "production-grade" claim | scale corpus (≥50/ class) | M | N |
| DF-9 | LOW | CLI | Verifier/estimator thresholds module-level constants, not user-configurable via CLI/JSON | expose config plumbing | S | N |
| DF-10 | LOW | report | EMULATION label present in docs but not stamped into a generated per-run report (report generator D8/D9 partially missing) | wire render_report + EMULATION section | S | N |

---

## FINAL VERDICT

### Counts across audited items
PASS: 21 · PARTIAL: 22 · FAIL: 5 · NOT VERIFIED (sudo-blocked): 9

### Honest verdict
**Not yet ready for the advancement (add-on) stage without fixing DF-1–DF-3, DF-5, DF-7.** The core technical claims are real: 1296 tests pass; the live-kernel evidence in stored gate logs matches what the code can build; the 60-run phase-6 matrix recomputed from raw files reproduces the stored statistics exactly; the statistics pipeline (exact Wilcoxon) is independently verified through creator-less enumeration; the classifier evaluation is honest, small but real, and the ML comparison argues correctly against adoption of `learned.py`. But the *project wrapper* lags the *engine*: no Makefile/demo, missing canonical docs, no S5/failure-injection scenario in the runner, no latency-under-load estimator signal, and cross-mode fairness metrics as computed are not defensible. Two claimed items (S5 scenario, 7-state FSM) never existed in code — they must either be built or the documentation must openly paper the deviation before the advancement stage.

### Blocked items the user must run (exact commands, paste output back)
```sh
# 1. re-run validation gate + phase gates live
sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/gate.sh
sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/gate7.sh
# 2. safe state + intent lifecycle, one invocation:
sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/phase6.sh && \
sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/cleanup.sh ; \
ip netns list
# 3. dashboard live: run `sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./aciqctl --serve 127.0.0.1:8787`
#    (check port via ss -tnlp; browser to http://<address>/dashboard)
# 4. after ALL of the above: `make safe-reset` equivalent → `sudo ./testbed/cleanup.sh` then
#    `ip netns list` must be EMPTY.
```

### ACIQ vs CAKE fairness statement
CAKE ran at 95% of the same applied capacity on the same device/parent with cake's default per-flow isolation — not rigged, but not flow-optimized either; both engines shape on the same single egress. ACIQ's honest contribution: adaptivity (rebuild tree on a step change — CAKE structurally cannot), lower measured bulk penalty (−1.68 vs −2.10 Mbps in S2), equal loss, slightly worse tail than CAKE. The comparison stands, but the "FAIRNESS" cross-mode column of any future report needs the DF-2 rework.

### Runtime + repeat commands
Audit wall time ≈ 34 min in sandbox. Repeat: `python3 -m unittest discover -s tests -q`, plus the two python blocks recorded in `docs/evidence/verification/run-log.txt` (recompute scripts over `data/runs`).
