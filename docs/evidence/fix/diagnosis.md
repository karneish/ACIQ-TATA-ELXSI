# Headline-failure diagnosis: ACIQ does not bind its shape (S1/S2/S4)

Written offline, 2026-10-24, strictly from existing committed evidence
(`data/runs/`, `data/experiments/RESULTS.md`). Every number below is quoted
from an artefact; the file and function citations are exact.

## 0. The headline failure, with its numbers

`data/experiments/RESULTS.md` (regenerated 2026-10-24 10:50):

| scenario | arm | call p95 ms | bulk Mbps |
|---|---|---|---|
| S1 | B0 | 250.71 | 96.29 |
| S1 | CAKE-static (95%) | 1.55 | 90.96 |
| S1 | ACIQ | **238.89** | **96.30** |
| S2 | ACIQ | 98.11 | 39.48 |
| S2 | CAKE-oracle | 2.75 | 18.08 |
| S4 | ACIQ | 96.87 | 32.65 |

ACIQ's applied shaper is at or above the true link for the whole run, so the
queue the emulated workload experiences is the FIFO netem queue, not the
controller's priority tree. ACIQ ≈ B0 is the signature of "not shaping".

## 1. Per-tick estimator belief vs applied rate vs true link

`samples.jsonl` carries `capacity_mbps` (the plan's applied parent rate) and
the bottleneck's own `Sent` byte counter (bytes that LEFT the netem queue —
the true delivered rate). Diffing the Sent counter over the sample interval
gives the true link rate per tick. Source-of-truth vantage:
`aciq/metrics.py:129 delivered_bytes()` — "netem's own `Sent N bytes` is what
left the queue, i.e. what the link really carried".

S1 (`s1_iso_during_call__aciq__adaptive__seed42/samples.jsonl`, link 100):

| t (s) | true link (Sent/dt) | applied (`capacity_mbps`) | netem backlog |
|---|---|---|---|
| 1.01 | 100.90 | 0.000 | 1,198,766 B |
| 2.03 | **111.40** | **102.451** (committed this tick) | 1,841,596 B |
| 3.17 | 89.26 | 102.451 | 1,434,032 B |
| 8.30 | 99.80 | 102.451 | 1,843,408 B |
| end | ~100.0 | 102.451 | max **3,089,058 B** |

The applied tree stays at 102.451 for the **entire run**; the true link is
100.0; backlog never clears (it grows to 3 MB, a netem `limit 416`
holding GRO super-packets).

S4 (`s4_capacity_recovery__aciq__adaptive__seed2/samples.jsonl`, link
100→20 at t≈11):

| t (s) | true link | applied/reported | netem backlog |
|---|---|---|---|
| 2.08 | **114.18** | 104.525 (committed 23201.15) | 1,911,538 B |
| 3.28–10.62 | 78–90 | 104.525 | ≈0–15 kB |
| 11.67 | 21.82 → want **23.822**, first apply STEP-CLAMPED to **78.393** | 23.822 (belief) | 111 kB |
| 13.8–60 | **19.5–20.9** (true 20) | **23.822 — never moves again** | 111–257 kB |

`result.json` `policy_change_log` for S4 seed2 is exactly **two commits** for
the whole 60 s run:

    t=23201.15  want=104.525  applied=104.525  "within step bound"
    t=23210.74  want= 23.822  applied= 78.393  "step-clamped"

(no further commit: the tree stayed at 78.4 Mbps forever, far above the true
20 — nothing binds). The shape repeats across seeds: S4 seeds 0–9 have
exactly 2 commits each (want-pair 103.9–105.2 → 23.05–23.92, applied second
78.0–78.9); S2 seeds 0–9 identical (want 104.4–105.2 → 23.2–23.9, applied
78.2–78.9); the restored S2 seed42 is one historical outlier (3 commits,
101.9 → 39.5 → 28.0). All ten S1 seed runs show ONE commit each: want =
applied = 101.7–103.8 (belief, applied verbatim).

## 2. The exact code path that sets the applied rate from the estimate

aciq/harness.py, `Harness._adapt_step_inner` (one closed-loop tick):

1. `gbps = self.bottleneck_delivered_mbps(dt)` — harness.py:943 — the
   bottleneck's own `Sent` counter delta (true link), used in preference to
   the per-class sum.
2. `cap = self._estimator.observe(measurement)` — harness.py:976 — the
   belief. Inside `CapacityEstimator.observe` (aciq/capacity.py:363), when
   saturated: `target = m.goodput_mbps` (capacity.py:418) and the EWMA
   `ALPHA_UP=0.1 / ALPHA_DOWN=0.6 / HYSTERESIS=0.10 / FAST_DROP_RATIO=0.5`
   smoothing runs (capacity.py:452–470).
3. `bound = bound_rate_change(prev_rate, cap.mbps, now, last_change_t, ...)`
   — harness.py:982 → aciq/verifier.py:131. The law enforces only
   `MAX_RATE_STEP_FRAC = 0.25` per change (verifier.py:27) and
   `MIN_DWELL_S = 5.0` — **it never compares the rate to the true delivered
   capacity and never applies a cap fraction.**
4. `applied = bound.rate` — harness.py:996 — **the applied rate IS the
   estimator's belief, exactly; no scaling, no cap fraction**
   (`BULK_CEIL_FRACTION=0.85`, aciq/policy.py:37, is a ceiling for the
   labelled bulk class 1:30 only and never touches the parent).
5. `plan = build_plan(applied, self._lease)` — harness.py:997 →
   aciq/policy.py:82; `self.txn.apply(plan)` — harness.py:1011.

There is deliberately **no headroom factor and no probe overhead**:
`probe` traffic does not exist in the controller's tick loop (samples print
`metric_status: no_probe` for every class in the ACIQ matrix runs). What
inflates the belief is pure measurement dynamics — see §4.

## 3. (a) Why the applied rate exceeds the true link

Three locked-in mechanisms:

1. **Out-of-band netem bottleneck** (testbed/setup.sh builds
   `netem rate <rate> limit _netem_limit(rate)` on `wan/veth-w`;
   `aciq/harness.py:398-399 bottleneck_ns/bottleneck_dev`): the queue the
   workload feels is NOT the controller's HTB. With the parent set above the
   netem rate, the netem FIFO fills with bulk's GRO super-packets, and the
   call's latency = the netem backlog delay ≈ 1.9 MB / 12.5 MB/s ≈ 152 ms
   base with p95 ≈ 238 ms — measured, not conjectured: S1 max backlog
   3,089,058 B, ACIQ call p95 238.89 ≈ B0's 250.71 (both unshaped).

2. **First-window burst adoption** (startup): at t=2.03 the Sent/dt reading
   is 111–114 Mbps (netem token-bucket burst, GRO super-frame accounting) —
   S1: 1.01→111.40, S4: 2.08→114.18, S2: 2.08→113.50. The EWMA walks up
   (`ALPHA_UP=0.1`) and the plan commits the inflated belief (S1 102.451,
   S2 104.416, S4 104.525 — all above their true link).

3. **HYSTERESIS freezes the belief above the link** (capacity.py:462, at
   `HYSTERESIS=0.10` with the DELTA measured as
   `ALPHA_DOWN × |gap|`): every subsequent steady reading (S1 ≈ 100.0, S4 ≈
   20.0) is ignored for ever because the *smoothed* step
   `0.6 × (23.822 − 20) = 2.29` is 9.6 % of the estimate — under the 10 %
   hysteresis band — while the *raw* gap is 16 %:
   `new = 23.822 + 0.6·(20−23.822) = 21.53`, and
   `|21.53 − 23.822| = 2.29 < 0.10·23.822` → "hysteresis: do not move at
   all" (capacity.py:462), for every tick to the end of the run. The
   controller therefore cannot correct any belief error smaller than
   ~16.7 % (0.10/0.6), and its only large correction (the drop) is
   step-clamped (S2/S4: 104.5 → 78.4, never reaching 20).

## 4. (b) Why the earlier 1-seed S1 run gave 0.36 ms and the matrix gives 238.89

The 1-seed values live in
`docs/evidence/verification/VERIFICATION_REPORT.md:104`
(S1 ACIQ p95 0.364 ms) and were "recomputed from those run dirs" whose
names were later **overwritten by the matrix runs in place**; their
contents survive only at commit `ecac771` (phase-1 import). Comparing that
tree with today's runs, the differences are concrete, not speculative:

1. **Topology, not code, is the biggest difference.** At `ecac771` the S1
   samples have NO `bottleneck` field at all and `result.json`
   `bottleneck_state: ""` — the out-of-band netem bottleneck did not exist
   yet (added by the fix-round "moving the bottleneck out of the
   controller's tree" work, documented in aciq/capacity.py:322-340 and
   built by `testbed/setup.sh`). In the old topology the only queue was the
   controller's own HTB, whose classes were PRIORITISED: the call sat in
   `1:10` (guarantee 26 Mbps) and was never FIFO'd behind bulk. Bulk's queue
   was its own class. Measured old S1: bulk 95.73 Mbps, call p95 0.364 ms,
   estimate 100.748 (0.75 % over the link, and the old-era plan applied
   `~100.75`, which still did NOT bind anything meaningful — but with no
   out-of-band FIFO to fill, the call never saw a 150 ms tail).
2. **Demand differs by run shape.** Old S1 was a single
   30 s run in which bulk delivered 95.73 Mbps (never saturated a 100 Mbps
   link → no standing backlog). The matrix runs deliver ~99.9 Mbps through
   the default class, and the FIFO at the netem fills immediately.
3. **What does NOT differ**: the code path that applies the estimate as the
   rate (`_adapt_step_inner` → `build_plan(applied)`) is the same shape in
   both eras; the old estimate `100.748` was inflated by the same burst
   adoption (see its samples at git `ecac771`), it simply did not matter
   because the old tree carried the queue itself with priority classes.

## 5. (c) Why the ISO bulk is not limited in S1

Two reasons, both in the evidence:

1. **The bulk flow never enters the ceiling that was written for it.** The
   S1 applied plan (seed42 `result.json`
   `policy_change_log[0].applied_state`) is
   `1:1 rate 102.451 / ceil 102.451`, `1:30 (bulk_download) rate 12.132
   ceil 87.083` — a 0.85 ceiling that engages only when traffic is marked
   into `1:30`. Unmarked bulk traffic is steered to the DEFAULT class
   `1:70` on purpose (aciq/bridge.py:615: "Deliberately the DEFAULT class
   (unknown), not a class of its own"; class map
   aciq/metrics.py:363-367: `1:30 → BULK_DOWNLOAD`, `1:70 → UNKNOWN`).
   In the S1 matrix run the default class carries
   `unknown goodput 99.89 Mbps` (samples, `per_class.unknown`), i.e. the
   whole bulk demand rides `1:70` whose ceiling is the full parent rate
   (102.451) — the 0.85 limit never engages.
2. **Even if it did, the parent never binds either**: the applied parent is
   102.451 vs the true 100 (§3). The observed ACIQ bulk 96.30 is byte-for-
   byte B0's 96.29 — there is no shaping at all in either.

## 6. Headroom / probing factor

- There is **no deliberate headroom or probe-traffic factor** in the ACIQ
  path: `applied = bound.rate` is exactly the estimator's belief
  (harness.py:996). `metric_status: no_probe` on every samplesheet row.
- The inflation is entirely accidental measurement dynamics:
  - netem token-bucket/GRO burst readings (111–114 Mbps against a 100 link)
    in the first ~2 s,
  - a one-tick transition reading (23.2–23.8 on a true 20) adopted
    whole by `FAST_DROP_RATIO` (capacity.py:468: `alpha = 1.0`),
  - a hysteresis floor (10 %, i.e. ~0.6 × gap) that permanently freezes
    beliefs within ~16.7 % of a target reading rather than drifting down.
- CAKE's own `0.95` factor (`harness.py:243`, `txn.py:739`,
  `experiment.py:443`) is a fixed pre-drop shape and is NOT part of ACIQ's
  path: the missions's contrast is that CAKE never claim to estimate.

## 7. Task-2 design consequences (for the fix)

1. Belief and applied must be separated in the code path at
   harness.py:996: `applied = min(belief, APPLIED_CAP_FRACTION ×
   delivered)` with a latency-inflation ratchet (backlog-delay here, since
   the per-class RTT probes do not exist mid-run in S1; samples carry
   `bottleneck_backlog_bytes` every tick — measured, not conjectured).
2. The ratchet must NOT inherit the estimator's hysteresis freeze: it keeps
   correcting back to its cap every cycle, and climbs only under explicit
   hold + hysteresis.
3. The law's bounds (step/dwell/floor, rollback, safe state) stay exactly
   as they are; the governor's output is what feeds `bound_rate_change`.

## 8. Concrete explanation for S1: ACIQ 238.89 ms vs CAKE-static 1.55 ms (from samples.jsonl)

**What differed (topology/class mapping):**
- **Class steering**: Bulk traffic in the S1 matrix runs is unmarked; `aciq/bridge.py:615` deliberately leaves it in the DEFAULT class `1:70` (labeled `UNKNOWN` in `aciq/metrics.py:363-367`) not a dedicated bulk class. `1:30` → `BULK_DOWNLOAD` is the shaped bulk class but most bulk never hits it. 
- **Per-class ceiling**: `1:70` has no restrictive per-class ceiling in the default policy; its ceiling is effectively the parent rate. `1:30` has a 0.85 limit that never engages because traffic isn't steered there.
- **Parent shaping**: Both ACIQ and B0 apply effectively no shaping on the parent in S1 (ACIQ parent/applied ~102 Mbps vs true ~100 Mbps). CAKE-static applies fixed shaping at 95% of pre-drop link via `harness.py:243`, `txn.py:739`, `experiment.py:443` (CAKE's `0.95` factor is fixed, not learned).
- **Applied vs belief**: `harness.py:996` sets `applied = bound.rate` with `applied == belief` (no cap fraction applied). The estimator/hysteresis keep belief high (~102 Mbps) so applied stays high; bulk rides the unshaped default class.

**Concrete numbers (from repo runs):**
- S1 matrix (pre-fix seeds 42-51, from `data/experiments/RESULTS.md` legacy): ACIQ call p95 **238.89 ms**, bulk **96.30 Mbps**; CAKE-static call p95 **1.55 ms**, bulk **90.96 Mbps**. ACIQ bulk is byte-for-byte like B0 (96.30 vs 96.29).
- Samples show `per_class.unknown` carrying bulk (default class), `capacity_mbps` ≈ 102 Mbps (estimator/applied high), parent never binds down.

**Why the earlier single-seed S1 run showed 0.36 ms:**
- Different topology/configuration (older setup) gave different class mapping/queuing. As documented in §4(b): in that older topology the only queue was the shaped one and bulk landed in its own class with different behavior. The matrix run reflects the current testbed topology from `testbed/setup.sh`. The 0.36 ms number came from a different setup, not the current matrix topology; the matrix is the canonical comparison.

**Fix (T2):** RateGovernor caps applied rate at `cap_fraction × belief` (default 0.90) with delay ratchet, separates applied from belief in `harness.py`, fixes hysteresis to judge on raw target gap in `aciq/capacity.py`. On post-fix seeds 200-209 (see current `data/experiments/RESULTS.md`), binding is observed in drop scenarios (s2/s4) with governor engaged.
