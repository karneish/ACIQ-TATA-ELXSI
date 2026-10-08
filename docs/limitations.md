# Known Limitations

Written before the results are flattering, so that nothing here is an excuse
made afterwards. Where a limitation was *discovered by measurement*, the number
is given.

## 1. The emulated link is not a real link

The slow line is **HTB class `1:1`** — a token-bucket shaper. It does not model
DSL or cable overhead, ISP policing, modem behaviour, or a real CPE. Real
broadband has latency that varies with load and a buffer that overflows; this has
neither.

`netem` supplies delay and loss only, never bandwidth. Using `netem` for rate
would have been simpler and would have been dishonest about what is being
emulated.

## 2. Capacity estimation cannot see a bottleneck it is not on

M2 reads queue counters from the router. In a real home the bottleneck is usually
the modem or the ISP side, where router counters show **nothing at all** — no
drop, no overlimit, no backlog.

This is the most important limitation, and it was confirmed by measurement rather
than assumed:

| Condition | Measured `overlimits` |
|---|---|
| 100 Mbps link genuinely full | 5127 – 6485 /s |
| 20 Mbps link saturated | 24803 – 65101 /s |
| 100 Mbps link ~10% loaded, children rate-limited | 170 – 1313 /s |

Separating "link full" from "class rate-limited" works by *magnitude* against
those two populations, with roughly 4× margin. That is a threshold fitted to
observed data, not a proof. A link pushed 1% over its limit by many children
would look like the full case.

**A validated remedy exists but is not in the MVP.** Gate check 12 measured an
unmarked probe rising from 0.051 ms to 0.405 ms (~8×) under saturation. An EF
probe in the protected class showed no signal at all (0.051 → 0.070 ms) because
it reports how well that class is protected, not whether the link is full. So the
signal must come from the bulk path, and it costs probe traffic that would need
accounting in the CPU-overhead numbers.

## 3. Passive estimation needs a busy link

On an idle link, observed throughput is offered load, not capacity. M2 therefore
does not learn from unsaturated samples, and its confidence **decays** when idle
rather than holding a stale high value. A link that is never busy yields no
capacity estimate at all — `n/a`, not a guess.

## 4. Classification accuracy is measured on self-generated traffic

All traffic comes from our own generators. Real homes have applications we do
not model. Accuracy reported here will look better than reality.

Deliberately, the classifier ignores the generators' own ports, so it cannot
score a meaningless 100%. The residual known-hard case: **UDP/443 carries both
video calls and large downloads**, and when nothing distinguishes them the flow
is reported UNCLASSIFIED rather than guessed.

## 5. Three of the four traffic classes are not populated

Only `INTERACTIVE` receives traffic. Nothing routes to `ADAPTIVE` or `LEASED`:

- **ADAPTIVE** — the classifier never emits it, and no filter targets `1:20`.
  Non-EF traffic falls to the HTB default `1:30` (BULK). Measured:
  `adaptive_video: goodput 0.0`.
  **Correcting the original wording:** the earlier version of this file said
  "in every sample", and specifically "in every s3 sample". That was not
  measured. `s3_tv_and_gaming__aciq__adaptive__seed42` has **no
  `samples.jsonl` at all** -- the run died before artefact collection, which
  `data/baselines/v0/README.md` already documented. The 0.0 is real, but it
  comes from **s1** (`s1_iso_during_call__aciq__adaptive__seed42`, where
  `adaptive_video: 0.0` and `bulk_transfer: 99.926`), and s1 has no video
  workload, so the 0.0 there is trivially expected.
- **LEASED** — class `1:40` is created and given bandwidth, but no filter routes
  to it. The lease allocates to an empty queue.

See `docs/WIRING_AUDIT.md` for the per-module evidence.

## 5b. Superseded 2026-10-08: ADAPTIVE now receives traffic

The first measured run with per-flow enforcement enabled,
`data/enforced/seed42/s3_tv_and_gaming__aciq__adaptive__seed42`:

| tick | interactive | adaptive | bulk | verdict |
|---|---|---|---|---|
| 0.0 | 0.000 | 0.000 | 0.000 | all UNCLASSIFIED, too young |
| 1.02 | 0.042 | 0.000 | **24.245** | still unclassified -- video in BULK |
| 2.03 | 0.040 | 0.000 | 24.419 | classifier fires: game->interactive, tv1-3->adaptive |
| 3.06 | 0.041 | **23.907** | 0.726 | all three video streams moved to 1:20 |
| 4.08 | 0.042 | **24.288** | 0.000 | steady |

( Mbps, from `samples.jsonl`.)

Two independent measurements agree: the adaptive class carried **13.96 Mbps**
mean over 37 ticks, and the three generators sent 3 x 23,808,750 B over 40 s =
**14.29 Mbps**. Every sink received exactly what its sender sent, so nothing was
dropped in moving between classes. The game reported p50 0.467 ms, p95 0.562,
p99 0.669, 0% loss, and 30/30 pps achieved.

Ticks 0-2 are a within-run control: before the classifier fires, the video is in
BULK, which is the v0 behaviour, observed in the same run rather than compared
against another.

**Caveats, and they are not small.**

* **One run, one seed, no baseline in the same run.** This shows the mechanism
  works. It does not show it helps. The report correctly refuses a p-value.
* **`estimator=None`, `capacity_mbps = 0.0`.** M2 never measured: ~14 Mbps on a
  100 Mbps link is not saturated, so no reading was emitted. The classifier ran
  the whole run on the **configured 100 Mbps fallback**, not a measurement. The
  two agree here by luck -- at 14.3 Mbps against 100 Mbps the capacity-relative
  thresholds land in the same place either way. A run that saturates the link
  would exercise the measured path instead.
* This is a *mechanism* result. Whether steering video to 1:20 improves anything
  needs paired runs against `b0_fifo` and `b1_cake95`.



## 5c. The first paired comparison (2026-10-08)

`data/enforced/paired42/` -- s3_tv_and_gaming, seed 42, all three systems. Game
latency, self-reported by the game workload:

| system | p50 | p95 | p99 | jitter | loss |
|---|---|---|---|---|---|
| aciq (enforced) | 0.476 | 0.581 | 0.776 | 0.155 | 0.000 |
| b0_fifo | 0.473 | **33.577** | **33.703** | **6.135** | 0.000 |
| b1_cake95 | 0.482 | 0.578 | 0.703 | 0.084 | 0.000 |

**Read honestly:**

* ACIQ beats pfifo by ~58x at p95 and p99 and by ~40x on jitter.
* ACIQ **loses** to cake on all four, by 3-6 microseconds. At that scale these are
  ties and the report is technically right to call them losses.
* One run, one seed, no p-value. The report refuses one for good reason.

### pfifo's 33 ms is NOT explained, and this file will not pretend it is

The obvious reading is bufferbloat. The data does not support it:

* `b0_fifo` recorded **0 drops, 0 backlog** on the link for the whole run.
* The offered load was ~14 Mbps on a 100 Mbps parent -- roughly 14% utilisation.
  A `pfifo limit 1000` queue under a 100 Mbps shaper has no reason to build at
  14% utilisation.
* The artefacts contain **no per-packet RTT trace**; `game.json` stores only
  percentiles, so the 33 ms cannot be localised to a burst or a moment.

So pfifo's p95 is a real measurement whose cause is unknown. Calling it
bufferbloat would be the same error as calling a win a loss -- in the other
direction, and just as unsupported.

### Per-class comparison across systems is not possible yet

`per_class` is populated for `aciq` and **empty for both baselines**, because
their trees have one class that does not map to the ACIQ class names. So
`fairness` reads 0.000 for both baselines, meaning *unavailable*, not *zero
unfairness*. Video is known to sit in bulk for the baselines by construction,
not by measurement.

### Also note: `link.cls` is mislabelled

Every sample of every system records the parent counter under
`link.cls = "realtime_interactive"`. The parent is class `1:1` and is not
`realtime_interactive`. M2 reads only the numbers, so no measurement is
affected, but the artefact is misleading and should be relabelled.

### This run tested the steady-state tree, not adaptation

`estimator=None`, `policy_changes=0`, no capacity drop. At 100 Mbps with 14 Mbps
offered, M2 never saw saturation and nothing had to adapt. The enforced
per-flow path *is* exercised -- video was measured at 13.96 Mbps mean in class
1:20 -- but nothing about capacity adaptation was.

## 6. There is no per-user or per-device fairness

`8:4:2` allocates bandwidth **per class**. Fairness within a class is delegated
entirely to the `fq_codel` leaf, which is per-*flow* and knows nothing about
users or devices. Consequences: five simultaneous calls share one queue with no
admission control, and a single flow can take the whole class because every
class has `ceil = capacity`.

Per-*user* fairness is not implementable at the IP layer at all — there is no
user identity. It would require an authentication layer this project does not
have.

## 7. Uplink is not shaped

Enforcement is on the router's LAN-facing egress only. Upload saturation is
unmodelled. In a home link, uploads are usually small — but a slow uplink will
harm download latency through bufferbloat on the upstream path, and ACIQ does not
address it.

## 8. Small and very large links behave differently

`floor = max(2 Mbps, 5% of capacity)` reserves 6 Mbps across 3 classes, so
`degraded` fires only **below 6 Mbps** (below 8 Mbps with an active lease). At
that point floors are scaled down proportionally and flagged. Verified by
running the policy engine, not estimated.

## 9. No aggregation over repeated runs

Every result so far is **one seed**. Paired Wilcoxon cannot reach p < 0.05 with
fewer than 6 pairs — the smallest attainable two-sided p is 2^(1−n), which is
0.0625 at n=5. Until the matrix runs with ≥6 seeds, only ranges and confidence
intervals are legitimate, and no significance claim is made.

## 10. Out of scope

Wi-Fi airtime and WMM · ISP-side policing · TR-069 / TR-369 · certification ·
scale above 1 Gbps · encrypted DNS · QUIC port hiding · real CPE hardware ·
uplink shaping · a dashboard · an intent API · a working correction loop.

## 11. Honest reading of the v0 results

Frozen in `data/baselines/v0/` and tagged `v0-baseline`.

| Scenario | System | p50 | p95 | p99 |
|---|---|---|---|---|
| s1 call | aciq | **0.207** | 0.899 | **19.422** |
| s1 call | b1_cake95 | 0.244 | **0.711** | **1.494** |
| s1 call | b0_fifo | 120.061 | 120.544 | 121.751 |
| s3 game | aciq | 0.393 | **0.546** | **0.785** |
| s3 game | b1_cake95 | **0.277** | 0.710 | 1.425 |
| s3 game | b0_fifo | 0.302 | 33.475 | 33.618 |

**ACIQ wins s1 p50 and eliminates the `pfifo` bufferbloat (120 ms → 0.2 ms). It
loses s1 p95 and p99 to `cake`, and loses s3 p50 to both baselines.** The 19.4 ms
p99 against cake's 1.5 ms is unexplained and is the weakest number here.

One run — `s3_tv_and_gaming__aciq__adaptive__seed42` — has no `result.json`:
its workloads all completed, but the run died before artefact collection. It
contributes no metrics.