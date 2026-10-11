# Resource use and reliability

Status: **PARTIAL**. Bounded by construction; load behaviour **BLOCKED**.

## Controller cost — measured

`tools/bench.py`, 5000 flows, mixed classes, on this host:

| operation | time |
|---|---|
| classify | ~0.2 ms |
| build_plan | ~1 ms |
| apply | **BLOCKED** (no `tc`) |
| full reconcile | ~2 ms |

Pure Python, single core. Reconciliation cost is linear in flow count; policy
*generation* and audit are constant.

**No efficiency or scalability claim is made from these numbers.** They are
controller arithmetic at one scale on one machine.

## Memory — bounded by construction

| structure | bound |
|---|---|
| per-label RTT window | 600 samples, per class per run |
| verdict history | capped and pruned |
| lease book | one entry per IP |
| rate-limit table | 1024 entries, oldest-half evicted |
| audit log | grows on disk; **not rotation-tested** |

## Gaps, named

- **Packet-buffer / qdisc memory under load: BLOCKED.**
- **Controller CPU during an actual convergence: BLOCKED** — the bench times
  arithmetic, not a live loop, and the difference is the point.
- **Long-run resource drift: BLOCKED** — no run exceeds 40 s, against a 30-minute
  requirement.
- **Memory over 30 minutes: NOT RUN.**

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
| 1 | memory does not grow unboundedly over a long run | **BLOCKED** |
| 2 | CPU stays within an operator budget during convergence | **BLOCKED** |
| 3 | does not leak resources across repeated experiments | **PARTIAL** — cleanup implemented, 30-run soak not performed |
