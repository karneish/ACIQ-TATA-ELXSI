# Telemetry and dashboard

Covers §19. Every displayed value traced to its source.

## Provenance of every panel

| panel | source | interval | aggregation | missing behaviour |
|---|---|---|---|---|
| latency | probe RTT samples, per class | per tick | nearest-rank p50/p95/p99 | `None` + status |
| jitter | consecutive RTT difference | per tick | mean | `None` + status |
| loss | sequence accounting | per tick | per probe workload | `None` + status |
| throughput | `tc` class byte counters | per tick | differenced over `dt` | 0.0 (a class with no traffic genuinely has none) |
| queue depth | `tc` class `backlog_bytes` | per tick | instantaneous | 0 (genuine) |
| fairness | Jain over per-class goodput | per tick | per tick | 0 when there is no traffic |

Summary tiles: samples, span, peak and mean throughput, M2 capacity
(**"not measured"** when there is none), flows steered, CPU peak. Each carries
the caveat it belongs with rather than a bare number.

## Validity is surfaced, not hidden

Before this work, three of six panels were flat zero — `rtt_p95`, `jitter_ms`
and `loss_ratio` were identically zero in every run — and the dashboard rendered
that as a *measured* line on an axis padded to −0.5…0.5, labelling **negative
latency**.

Now: a class with no probe reports `no_probe` and its latency fields are `None`.
An all-zero series renders as **"not measured — every sample reported exactly
0"** rather than a line. A genuinely measured `0.0` still renders as `0.0`,
because those are different facts.

## Degraded-operation states the page shows

| state | shown as |
|---|---|
| waiting for a run to start | "waiting for `<pattern>`", `/status.waiting = true` |
| live vs frozen | `live` / `snapshot` badge |
| capacity unmeasured | "not measured — no saturated sample in this run" |
| lease in effect | seconds-in-effect, from the run's own note |
| no samples at all | `samples = 0`, honest rather than an empty chart |

**Not surfaced:** safety vetoes, last rollback, last enforcement verification,
and collector errors. The data exists in `audit.json` and the run's `notes`;
getting it onto the page is unimplemented.

## Deferral, stated

The capacity estimate is shown as M2's output and labelled "measured, not
configured". §19 asks that a stale estimate never be presented as live capacity
— it cannot be here, because M2 has never produced one in a live run (§6), and
the tile says "not measured" rather than showing `0.0` as though it had.

## No JavaScript, and that is a real constraint

The dashboard is inline SVG with a `<meta http-equiv="refresh">`. Live updates
come from the server re-reading `samples.jsonl` per request. Consequences, stated
rather than discovered:

- **no hover tooltips beyond SVG `<title>`**, which is browser-native;
- **no client-side filtering** or range selection;
- **no WebSocket** — charts update by page reload.

A dependency-light handler that cannot reach `tc` was judged worth more than
interactivity, and it is asserted by a test that walks every route.
