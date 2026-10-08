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
  `adaptive_video: goodput 0.0` in every sample.
- **LEASED** — class `1:40` is created and given bandwidth, but no filter routes
  to it. The lease allocates to an empty queue.

See `docs/WIRING_AUDIT.md` for the per-module evidence.

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