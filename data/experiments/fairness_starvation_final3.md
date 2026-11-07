# Fairness / starvation telemetry — final band (derived from data/runs_final3)

Derived from frozen samples only; no rerun.

Method:
- Per-class goodput series = `samples.jsonl:per_class.<class>.goodput_mbps` per tick.
- Starvation-duration proxy = longest consecutive ticks where class goodput == 0 while total goodput > 0.1 Mbps (i.e. the link carried traffic, this class got none). Classes that are never present in a scenario (e.g. software_update/cloud_backup in s1) will show long "zero" runs — that is absence of traffic, not starvation. Real starvation must be read per-flow from sink logs.

Sink-log per-flow delivery:
- `*.sink.log` files total delivered bytes per workload sink (call/bulk/game/tv*). Final delivered goodput per flow = sink cumulative bytes / observed duration. These are the per-device numbers the dashboard panels should use (not per-class counters which conflate absent classes with zero traffic).

Intent-fairness:
- Intent lease runs (`lease_active` in samples) exonerate the lease path when per-flow delivered goodput from sink logs stays within floor during lease window. Whole-band intent evidence is thin (one s4 run in `data/experiments/intent_starvation/`); dedicated intent-fairness live scenario remains a gap — see REQUIREMENT_TRACEABILITY REQ-005.

Headline fairness (from RESULTS_FINAL3.md jain columns): publisher tables already report workload-rate Jain and demand-normalized Jain per scenario x arm. This file adds the per-flow sink-log series and starvation-duration proxy so REQ-017/REQ-037 can be audited without class-counter conflation.
