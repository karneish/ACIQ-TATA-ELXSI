# Performance and scalability

Covers §15. Reproduce with `python3 tools/bench.py --json out.json`.
Raw: `performance-measurements.json`.

## Environment these numbers are valid for

```
kernel  7.1.5-76070105-generic
python  3.13.15
machine x86_64
```

**These are controller-arithmetic measurements on an unconstrained desktop.**
No `tc` call is made and no namespace is touched. Claims about router-grade
performance are not made from them.

## Measured

| operation | mean | p99 | max |
|---|---|---|---|
| `build_plan`, no lease | 6.95 µs | 19.31 µs | 58.92 µs |
| `build_plan`, with lease | 8.12 µs | 19.23 µs | 72.51 µs |
| `build_tree` + `render` (12 tc commands) | 80.14 µs | 119.15 µs | 246.04 µs |
| `parse_conntrack_line` | 5.22 µs | 10.91 µs | 31.14 µs |
| `classify`, one flow | 9.65 µs | 17.01 µs | 95.24 µs |

Derived:

| | |
|---|---|
| conntrack parsing throughput | ~191,000 lines/s |
| classification throughput | ~104,000 flows/s |
| classifier cost, 10 flows per 1 Hz tick | 0.097 ms |
| classifier cost, 100 flows per tick | 0.965 ms |
| classifier cost, 500 flows per tick | 4.825 ms |
| resident set, whole controller | 17.2 MB |

`cpu_fraction` measured in real runs peaks at **0.64%** of one core.

## Scaling

The costs that grow with the number of things being managed:

| quantity | growth | note |
|---|---|---|
| `build_plan` | **constant** | three or four classes, whatever the flow count |
| conntrack parsing | linear in flow entries | 5.22 µs/line |
| classification | linear in flows | 9.65 µs/flow/tick |
| tc commands per apply | constant | 12, regardless of flow count |
| flower filters installed | linear in steered flows | one per flow |
| `_rtts` window | bounded | last `window` samples per label |
| lease book | linear in live leases | expired leases are dropped |
| rate-limit table | **capped** | 1024 clients, oldest-half eviction |

The design point is visible: per-flow cost is observation and one filter per
flow, while policy application is O(1) in flow count. A household link will not
be limited by either; a 500-flow budget costs 4.8 ms of classification per tick
against a 1000 ms period.

## What is not measured, and cannot be from this shell

- **Cost of issuing the `tc` commands.** Rendering 12 commands takes 80 µs;
  running them is a process spawn per command plus the kernel's work. This is
  likely the dominant control-plane cost and it is **unmeasured**.
- **Filter-table lookup cost at 500+ flower filters.** The kernel's tc filter
  chain is walked per packet; that cost is invisible from userspace.
- **`tc -s` collection duration.** Every tick shells out and parses; its latency
  is not instrumented.
- **API latency under load.** No concurrent-client test.
- **Sustained-load memory growth over hours.**

All of the above require namespaces and `tc`. **Blocked-environment.**

## Targets

Not set. Setting a router-grade target from desktop arithmetic would be the kind
of claim this project has been removing. The first honest target requires
measuring on hardware resembling the deployment.
