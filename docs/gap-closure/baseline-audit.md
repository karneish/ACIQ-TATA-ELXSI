# Baseline audit

Taken before any change, at revision `66298cd9`. Re-run with
`python3 -m unittest discover -s tests -t .`.

## Test suite

```
$ python3 -m unittest discover -s tests -t .
Ran 682 tests in 1.952s
OK
exit=0
```

682 passed, 0 failed, 0 skipped, 0 blocked. **The prompt asks that these numbers
be independently reproduced rather than assumed — they were, and they held.**

## Environment

Full capture in `environment.txt`. Summary:

| | |
|---|---|
| kernel | `7.1.5-76070105-generic` |
| python | 3.13.15 |
| revision | `66298cd9` |
| euid | 1000 |

### The binding constraint on this work

**This shell has no `ip`, `tc`, `iperf3`, `nc` or `ping` on any path, and no
`sudo`.** Verified directly: `/usr/sbin` and `/sbin` are listable and contain
none of them; `sudo` is not installed. The user shell has all of them and has
run the gate to 20 PASS / 1 MEASURED / 0 FAIL.

Everything in this report that requires a kernel is therefore marked
**blocked-environment**, with the command recorded so it can be run elsewhere.
Nothing blocked is reported as passed.

## Subsystem inspection

Traced the real data flow rather than inferring it from names:

```
conntrack (kernel)  -> aciq/flowtrack.py    -> Flow / FlowFeatures
                    -> aciq/classify.py     -> Classification (cls, confidence, tier)
                    -> aciq/corrections.py  -> operator override
                    -> aciq/closedloop.py   -> FlowKey + class
                    -> aciq/bridge.py       -> tc flower filters (the only writer)

tc counters         -> aciq/metrics.py      -> ClassMetrics per tick
tc JSON/text        -> aciq/qdisc.py, aciq/tc.py

counters            -> aciq/capacity.py     -> Capacity      (M2)
                     -> aciq/policy.py       -> RatePlan      (M3)
                     -> aciq/harness.py      -> build_tree    (M4)
                     -> aciq/txn.py          -> apply + read-back + audit
                     -> aciq/shield.py       -> veto, rate limit, rollback

lease               -> aciq/intent.py       -> LeaseBook
HTTP                -> aciq/api.py          -> stdlib http.server
dashboard           -> aciq/dashboard.py    -> inline SVG, no JS
report              -> aciq/report.py       -> aggregation, exact Wilcoxon
driver              -> aciq/experiment.py   -> scenarios, runs, artefacts
```

## Metrics that were constant, missing, stale or inferred

This was the most consequential part of the audit, and it is what P0-001 turned
on. Every metric was traced to its actual source across four independent run
trees:

| field | source | finding |
|---|---|---|
| `goodput_mbps` | class byte counters, differenced | **real** |
| `backlog_bytes` | class counters | **real** |
| `drop_rate_per_s`, `overlimit_rate_per_s` | class counters, differenced | **real** |
| `fairness` | Jain index over per-class goodput | real, but coarse |
| `rtt_p50/p95/p99` | generator report | **identically zero — see below** |
| `jitter_ms` | generator report | **identically zero** |
| `loss_ratio` | generator report | **identically zero** |
| `cpu_fraction` | getrusage SELF / wall | real, controller process only |
| `capacity_mbps` | M2 | real but **0.0 in every stored run** |

Measured across `data/matrix6`, `data/fixcheck`, `data/dev10_lease`,
`data/ab_lease_42`:

```
rtt_p95       distinct values 1   non-zero 0
jitter_ms     distinct values 1   non-zero 0
loss_ratio    distinct values 1   non-zero 0
goodput_mbps  distinct values 119 non-zero 118
```

Four independent causes, all upstream of any arithmetic. See
`defect-register.md` P0-001 to P0-004.

## Existing test coverage and what it missed

682 tests, all passing. The gap that mattered:

**Two of them were passing for the wrong reason.** `test_evaluation_data_feeds_
percentiles` and `test_loss_ratio_propagates` labelled their probe with
`TrafficClass.INTERACTIVE.value` — the class *name* — which made the broken
lookup work by coincidence. In a real run the label is `call` or `tv1`, so the
branch never fired. A test suite that agreed with a broken implementation
because it used the wrong key is worse than no test; both are corrected and now
also exercise the real label path.

## What was already correct, and worth not breaking

- shield vetoes: child sum vs capacity, class floors, 5 s rate limit, drop and
  overlimit ceilings at 5000/s
- read-back verification after every apply, with rollback on mismatch
- audit of every commit — extended here to record *which rates* were applied
- filter teardown: gate check 20 exists because residue steers the next run
- exact paired Wilcoxon with `MIN_PAIRS_FOR_PVALUE = 6`, and the report refuses
  to print a p-value below that rather than printing an uninterpretable one
