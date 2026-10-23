# Resource use and reliability

Status: **PARTIAL**. Controller memory bounded and soak-tested offline; kernel
and packet-buffer load **BLOCKED**.

## Controller cost — measured

`tools/bench.py`, mixed classes, on this host:

| operation | time |
|---|---|
| classify one flow | ~7 µs (p99 ~22 µs) |
| build_plan (no lease) | ~6 µs |
| build_tree_and_render | ~50 µs |
| full classification at 1 Hz | 10 flows 0.07 ms · 100 flows 0.71 ms · 500 flows 3.5 ms |
| apply | **BLOCKED** (no `tc`) |

Pure Python, single core. Classification cost is linear in flow count; policy
*generation* and audit are constant.

**No efficiency or scalability claim is made from these numbers.** They are
controller arithmetic at one scale on one machine.

## Memory — bounded by construction, and now tested

| structure | bound |
|---|---|
| per-flow RTT window | 10 increments, ring |
| tracked flows | evicted after `FLOW_EVICT_IDLE_S = 120 s` idle, guarded on a non-empty snapshot |
| trust store | `MAX_TRUST_SOURCES = 1024`, least-recently-seen evicted |
| lease book | one entry per IP |
| rate-limit table | 1024 entries, oldest-half evicted |
| audit log | grows on disk; rotation still **not** tested |

**A structure that was not bounded, found by the soak.** `TrustStore`'s three
maps (`_trust`, `_claims`, `_misses`) were keyed by source address and *never
evicted* — "bounded and in-memory" was in the docstring and false in the code.
Under source churn (NAT, DHCP, a spoofing sender) they grew one entry per new
source for the life of the process. They now evict the **least recently seen**
source at `MAX_TRUST_SOURCES`, not the least trusted: forgetting a stale entry
is safe because default trust is 1.0, whereas forgetting by trust could evict a
well-behaved source and let an active mislabeller's low entry survive.
`tests/test_offline_soak.py` pins the bound.

## Offline long-run soak — measured

`tools/offline_soak.py` drives the real per-tick arithmetic — `FlowTracker` →
`classify` → `TrustStore` → `CapacityEstimator` → `build_plan` — with no kernel,
for a configurable duration, and reports RSS over time and the size of every
bounded structure.

RSS is read from `/proc/self/statm` (current resident pages), **not**
`ru_maxrss`. `ru_maxrss` is the peak over the process's life and can never
decrease, so it reports a "drift" that only climbs and hides whether memory is
ever reclaimed; the peak is reported separately as `rss_ru_maxrss_peak_mb`.

| run | flows | ticks | tracked flows (end) | RSS start → end | drift/tick | tick time first → last |
|---|---|---|---|---|---|---|
| 20 s | 150 | 4 944 | 150 | 16.7 → 17.1 MB | ~0 | 3.5 → 3.9 ms |
| 180 s | 200 | 25 633 | 200 | 16.8 → 17.8 MB | ~0.04 KB | 6.4 → 8.1 ms |
| 1 800 s (30 min) | 200 | 277 106 | 200 | **17.03 → 17.41 MB** | **0.001 KB** | 5.7 → 10.6 ms |

The 30-minute result is the headline: **0.38 MB total drift across 277 106 ticks,
plateauing** (the final RSS samples are flat at 17.41 MB), with tracked flows
pinned at the pool size and per-tick time not climbing. The 4-second soak is a
unit test (`TestShortSoakReachesSteadyState`); the 20 s and 180 s runs are shown
because they exceed the "no run exceeds 40 s" gap the earlier revision named.

**The soak found two bugs, one of them in itself.** The first was the
`TrustStore` bound above. The second was the harness retaining one float per
tick in a `tick_times` list and reading it only at the end — 262k floats ≈ 8-10
MB over a 30-minute run, which the harness then reported as *controller* RSS
drift. The first 30-minute run therefore showed a false ~10 MB "leak". The list
was replaced by two scalars (first/last tick), a regression test
(`test_the_soak_does_not_retain_per_tick_data`) guards the shape, and the true
drift is the 0.38 MB above. A measurement that measures itself is not a
measurement.

**What this does not measure, stated so the numbers are not over-read:** qdisc
and packet-buffer memory, controller CPU during a *live* convergence, and the
kernel's cost of applying a policy all need a kernel and remain BLOCKED.

## Gaps, named

- **Packet-buffer / qdisc memory under load: BLOCKED.**
- **Controller CPU during an actual convergence: BLOCKED** — the bench times
  arithmetic, not a live loop, and the difference is the point.
- **Kernel-side cost of applying a policy: BLOCKED** (no `tc`).
- **Live 30-minute run: BLOCKED** — needs root and a kernel; the offline soak
  substitutes for the memory question only.

## Cleanup ownership

Only resources the experiment created are removed. Evidence that this matters:
residue on `veth-a`/`veth-b`/the routers steers the **next** run's classification
as well as the current one, and Q13 exists because of it.

Unverified in this run; previously gate check 20 on a privileged host.

## Dependency posture

Runtime dependencies are **deliberately absent**: the controller uses only the
Python standard library, including the metrics server.

The consequence, and it is the reason for the decision rather than an
afterthought: there is no third-party SDK between this code and the kernel. The
maintenance surface is `tc`, `ip`, and this repository — and a dependency bump
cannot silently change what "6 Mbps of priority" means.

The cost is that the metrics server is hand-written and therefore carries its
own bug surface.

## Operational blockers before any scale claim

| # | claim | status |
|---|---|---|
| 1 | controller memory does not grow unboundedly over a long offline run | **MEASURED** — 0.38 MB / 277 106 ticks / 30 min, plateauing (`tools/offline_soak.py`); kernel-side memory still BLOCKED |
| 2 | CPU stays within an operator budget during live convergence | **BLOCKED** |
| 3 | does not leak controller resources across repeated experiments | **PARTIAL** — cleanup implemented; kernel residue check needs root |
