# Measurement methodology

Covers §5: what RTT, jitter and loss mean here, how they are computed, and what
remains unverified.

## Definitions

Fixed here and used identically by the generators and the controller, so the two
agree by construction rather than by coincidence.

**RTT — round trip.** Send timestamp to receive timestamp of the *same sequence
number*, on `time.monotonic()`. **One-way delay is not measured and is not
claimed**: there are no synchronised clocks across the namespaces, and reporting
a one-way figure would be unsupported. Every field is therefore named `rtt_*`.

**Jitter — mean absolute consecutive RTT difference**, in arrival order, in
milliseconds. RFC 3550's smoothed interarrival jitter simplified to
consecutive-sample PDV. Chosen because it is computable from what the probe
actually has — one RTT per sequence — with no dependence on a transmit
timestamp the sink does not return.

**Loss — `1 - received / expected`, from sequence accounting only.** Never
inferred from throughput variation. `expected` excludes packets still in flight
when the measurement window closes; counting them would report a loss spike at
the end of every run, which is an artefact of the window rather than of the link.

**Percentiles — nearest rank, no interpolation.** With tens of samples an
interpolated p99 invents a value between two observations that were never
measured. Below `MIN_SAMPLES_FOR_PERCENTILES` (10) percentiles are `None`, not
a number: a p99 from three samples is a number, not an estimate.

## Validity, not zero

| state | meaning |
|---|---|
| `valid` | enough valid observations, all figures present |
| `insufficient_samples` | measured, but too few for percentiles |
| `not_measured` | nothing observed — latency figures are `None` |
| `no_probe` | this class carries no probe traffic at all |

`ClassMetrics` declares the latency fields `float | None`. A metric that could
not be computed is `None` plus a status. `0.0` is a real measurement — a flow
with no delay variation genuinely has jitter 0.0 — and conflating the two is
what previously made the dashboard label negative latency.

## Raw and derived are stored separately

Probes append every individual observation to `<label>.obs.jsonl`:

```json
{"seq": 41, "sent_mono_s": 12.804, "recv_mono_s": 12.812}
```

Losses are recorded as explicit nulls, not omitted — a consumer must be able to
see what *did not* arrive. An incremental summary goes to
`<label>.partial.json`, polled by the driver every tick.

Every derived figure is recomputable from the raw file. Verified end to end
over a real UDP socket, generator and controller computing independently from
the same stream:

```
generator  : sent=150 received=150 loss=0.0000 jitter=0.0870 p95=0.498
recomputed : valid=150/150          loss=0.0000 jitter=0.0870 p95=0.498
```

## Duplicates, reordering and outliers

- **Duplicates** resolve first-occurrence-wins. A repeated sequence is a
  duplicate reply, not a second measurement. Keeping whichever was shorter would
  let a duplicate *reduce* reported delay — the wrong direction.
- **Reordering** is counted in arrival order, before sorting. Counting inversions
  after sorting by sequence is structurally always zero; the first version did
  that and its own test caught it.
- **Implausible samples** (negative, or above 5000 ms) are discarded and counted
  separately, so a host scheduling pause does not become a latency result.

## Per-workload attribution

Probe observations are attributed to the class the bridge actually steered that
workload's flow into, via the run's own verdicts. A class with no probe traffic
reports `no_probe` — which is the honest answer for a bulk transfer, and is why
the dashboard does not show a bulk latency it never measured.

## Tests

`tests/test_measure.py` — 27 deterministic tests over synthetic traces with
known answers: flat and ramping paths, controlled loss, in-flight windows,
duplicates (including shorter-second-arrival), reordering, negative RTT,
implausible samples, and the empty case.

`tests/test_measure_integration.py` — 7 tests over a real UDP socket: every
sequence appears exactly once, every derived figure is recomputable from raw,
the partial report advances mid-run, and the collector's value changes between
polls.

## Not verified

**Kernel-integrated.** Everything above runs on loopback in a single namespace.
The namespace path — probe across `wan` -> `router` -> `client`, through `tc` —
is **blocked-environment**: this shell has no `ip`, `tc`, `sudo`. The command
is in `end-to-end-acceptance.md` §Phase F.

**Per-class separation is by verdict, not by measurement.** A bulk class
reporting `no_probe` is correct behaviour, but it means "bulk latency" is
absent by design rather than measured — a bulk transfer has no probe in it, and
adding one would change the traffic being characterised.
