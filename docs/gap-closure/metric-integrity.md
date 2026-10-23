# Metric integrity

Status: **PASS** for everything executable in this environment. Kernel-integrated
latency is **BLOCKED**.

## Fresh measurements — not reproductions

New runs, new conditions, recorded. Kernel `7.1.5-76070105-generic`, Python
3.13.15, loopback with an ephemeral port.

| profile | pps | payload | sent | received | loss | jitter (gen) | jitter (recomputed) | p95 (gen) | p95 (recomputed) | agree |
|---|---|---|---|---|---|---|---|---|---|---|
| call | 100 | 64 B | 150 | 150 | 0.00000 | 0.0574 | 0.0574 | 0.477 | 0.477 | **yes** |
| video | 250 | 1200 B | 500 | 500 | 0.00000 | 0.0552 | 0.0552 | 0.461 | 0.461 | **yes** |
| bulk | 500 | 128 B | 500 | 500 | 0.00000 | 0.0584 | 0.0584 | 0.442 | 0.442 | **yes** |

These differ from the previously reported 150 / 0.0870 / 0.498, which confirms
the harness measures rather than replays.

## Real loss, from a real condition

A probe aimed at a port nothing is listening on. The kernel really does drop
every datagram; this is a measurement, not a mock.

```
probe -> 127.0.0.1:56617   (nothing listening)
  generator : sent=100 received=0 loss_ratio=1.0
  raw obs   : 100 lines, 100 with recv=null
  recomputed: expected=100 received=0 loss_ratio=1.0
  latency   : None            <- not 0.0
```

**The historical pipeline reported `0.0` here, which is indistinguishable from
"fine".**

## Validity states, and that zero survives

| state | meaning |
|---|---|
| `valid` | enough observations, all figures present |
| `insufficient_samples` | measured, too few for percentiles |
| `not_measured` | nothing observed — latency is `None` |
| `no_probe` | the class carries no probe traffic |

Verified: a measured `0.0` loss and a measured `0.0` jitter both survive
ingestion, aggregation and serialisation (`test_a_measured_zero_survives`).

## Definitions

| metric | definition | direction |
|---|---|---|
| latency | send → receive of the same sequence, monotonic clock | **round trip** |
| jitter | mean absolute consecutive RTT difference, arrival order | PDV, ms |
| loss | `1 - received/expected`, sequence accounting | not inferred from throughput |
| percentiles | nearest rank, no interpolation | `< 10` samples → `None` |

**One-way delay is not claimed anywhere** — there are no synchronised clocks
across namespaces.

`expected` excludes in-flight packets, so a window closing mid-flight does not
report a loss spike.

## Ingestion and polling

The previously reported mismatch (`ingest` keyed by workload label, `poll` read
by class name) is closed and regression-tested on the **real** label path
(`tv1`, `call`) rather than the class name that made it work by coincidence.

The series is genuinely live: the collector's reported latency changes between
polls (`test_the_collector_reports_a_value_that_changes_between_polls`).

## Duplicates, reordering, malformed, stale

All covered by deterministic tests: first-occurrence-wins dedupe, reordering
counted in arrival order, negative and >5000 ms samples discarded and counted,
empty input → `not_measured` with every figure `None`.

## The controller cannot pass by repeating the generator

Every figure above is computed **twice** — once by the generator, once by
`aciq.measure` from the raw observation stream. They agree to the last digit in
all three profiles and on the total-loss case. The controller never reads the
generator's summary for a reported figure.

## BLOCKED

**Kernel-integrated latency.** Not run: no `ip`, no `tc`, no `sudo`, no network
namespaces. The measurement is verified over a real socket and the arithmetic is
verified against traces with known answers; the namespace path is not.

Command for a Linux host: in `final-release-readiness.md` §Reproduction.
