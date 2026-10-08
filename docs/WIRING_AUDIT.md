# ACIQ — Wiring Audit

**Date:** before any Step 0–7 work
**Method:** greps over the runtime import chain, `unittest` runs, inspection of
`data/` artefacts and documentation claims. Raw evidence cited per row.

**The runtime chain** is what actually executes:

```
run_experiments.py -> experiment.py -> harness.py -> {capacity, metrics, policy,
                                                       shield, tc, txn}
                                              txn.py -> {qdisc, shield, tc}
```

A module is **CONNECTED** only if something in that chain imports it.

---

## The audit table

| Module | Exists | Tests | **Connected** | Measured | Documented as working |
|---|---|---|---|---|---|
| **M1 classify** `classify.py` | yes (157) | 28 | **NO** | no | **YES — overstated** |
| **M1b flowtrack** `flowtrack.py` | yes (172) | 28 | **NO** | no | **YES — overstated** |
| **M2 capacity** `capacity.py` | yes (263) | 38 | yes (harness) | yes — 100.49 / 99.9 Mbps | yes |
| **M3 policy** `policy.py` | yes (123) | 24 | yes (3 files) | indirectly | yes |
| **M4 tc** `tc.py` | yes (244) | 54 | yes (3 files) | yes — gate 6, 9, 10, 14 | yes |
| **M5 metrics** `metrics.py` | yes (409) | 32 | yes (3 files) | yes — samples.jsonl | yes |
| **M6 harness/experiment** | yes (685) | 77 | yes (entry point) | yes — 6 runs | yes |
| **M7 intent API** | **NO FILE** | 0 | n/a | no | **in PLAN.md as a module** |
| **M8 dashboard** | **NO FILE** | 0 | n/a | no | **in PLAN.md as a module** |
| **M9 shield/txn** | yes (550) | 54 | yes (2 files) | fault-injection tests | yes |
| **M10 report** `report.py` | yes (271) | 40 | yes | yes — REPORT.md | yes |
| **correction file** | **NO FILE** | 0 | **NO** | no | **YES — overstated** |
| **IPv6** | in `tc.py` | — | yes (1:10 filter) | yes — gate 13/14 | yes |

**Total tests: 260 passing.** Test count is not the problem — connectivity is.

---

## Rows where "documented as working" = YES but "connected" = NO

These are the three overstatements, each with raw evidence.

### 1. M1 classifier — not connected

```
########## classify() called only from tests ##########
aciq/classify.py:149          <- a docstring, not a call
tests/test_classify.py:124    <- all 14 real hits are here

########## runtime imports: classify/flowtrack absent from every chain ##########
classify     NOT IMPORTED BY ANY RUNTIME MODULE
flowtrack    NOT IMPORTED BY ANY RUNTIME MODULE
```

**Consequence:** enforcement is 100% DSCP-based. The entire behavioural
classifier is inert at runtime.

### 2. Correction file — does not exist

```
########## is data/corrections.jsonl ever WRITTEN? ##########
(empty — no writes anywhere in aciq/ or run_experiments.py)

########## does data/ contain it? ##########
data/  ->  only REPORT.md and runs/
```

`docs/ACIQ_EXPLAINED.md:408` claims it records overrides that "demonstrably
change later decisions."

**This is also a Tata requirement.** The brief states: *"Classifiers must expose
confidence and allow correction of misclassification."* Confidence exists in
code (`Classification.confidence`, tested). Correction is **entirely absent**.

### 3. M7 intent API and M8 dashboard — no files exist

```
########## intent.py / dashboard.py / api.py ##########
none of intent.py / dashboard.py / api.py exist
```

**Consequence:** the lease cannot be requested by a user, because there is no
mechanism to request it. `Lease` is a dataclass used only in tests and in
`harness.set_lease()`. Tata lists both a dashboard and an intent API as
*expected output*.

---

## Additional structural findings (not overstatements, but gaps)

| Finding | Evidence | Meaning |
|---|---|---|
| **ADAPTIVE is unreachable** | `TrafficClass.ADAPTIVE` appears **0 times** in `classify.py`; `tc.py:143-144` emit filters only to `1:10`; default class is `"30"` = BULK | The weight-4 class receives zero traffic. Measured: `adaptive_video: goodput 0.0` in every s3 sample |
| **LEASED is unroutable** | No filter targets `1:40` | The lease allocates bandwidth to an empty queue |
| **No identity layer** | `grep -rniE 'device\|subnet\|macaddr\|principal\|tenant\|udev'` → 3 hits, all prose | No user/device concept exists |
| **Policy has no per-flow input** | `build_plan(capacity, lease)` | Fairness within a class is delegated entirely to `fq_codel` |
| **`INTERACTIVE_MAX_AVG_PACKET = 600`** | `classify.py:42` | A 720p video call sends 1200–1500 byte packets and would **not** classify as interactive |
| **No uplink shaping** | only `veth-lan` (egress to client) is shaped | Accepted limitation; documented in PLAN.md |

---

## Corrections to earlier analysis

Three errors of mine, verified by re-running the code:

| Row | I claimed | Actual |
|---|---|---|
| 20 | `degraded` fires at 15 Mbps | **Wrong.** At 15 Mbps floors reserve 8 of 15 → not degraded. Real edge: **below 6 Mbps** (3 classes) / **below 8 Mbps** (4 classes) |
| 22 | "2.5× step" | **5×** (`100/20 = 5.0`) |
| 24 | evasion gets "a better class" | **Inverted.** Evasion is *punished*: hidden call on udp/443 → `None`@0.40 → BULK, which hurts a real call. The abuse vector is **DSCP marking (row 29)** |

---

## How the current results should be labelled

> The measured system is **DSCP-EF filtering + HTB + `fq_codel`**.
> The behavioural classifier is tested but not connected to enforcement.
> In scenario 3 the three video streams were classified into **BULK**, not
> ADAPTIVE. No lease was exercised. These are the results of system **v0**.

Today's six runs are retained untouched as **frozen baseline v0** so the
improvement can be shown afterwards.

---

## Connection mechanism, corrected

My original Step 3 proposed per-flow `tc` filters built from a Python TTL table.
That was wrong on two counts:

1. **It forces a tree rebuild per classification change.** We measured that
   rebuilds require `tc qdisc del root` plus re-adding everything, and that
   HTB's `default` cannot change in place. At per-flow frequency that means
   constant queue flushes and latency spikes.
2. **It puts unbounded state in Python.**

Revised, verified against the nftables documentation:

```
nftables (router ns)  — dynamic, kernel garbage-collected
  set interactive_v4 { type ipv4_addr; flags timeout; }
  set adaptive_v4  / bulk_v4 / leased_v4
  update @set_xxx { ip saddr timeout Ns }     <- refreshed from the packet path

tc — STATIC, built once, never rebuilt
  filter add … fw mark 10 flowid 1:10
  filter add … fw mark 20 flowid 1:20
  filter add … fw mark 30 flowid 1:30
```

nftables `set` timeouts with `flags timeout` and packet-path `update` are core,
documented nftables features. Expiry is the kernel's job, so the lease TTL needs
no Python sweeper.

### Requirements the bridge must satisfy

| # | Requirement | Why |
|---|---|---|
| 1 | **Per flow, not per host** | One device runs Teams *and* Steam; a host set would put both in one class. Classify per flow, then evaluate conntrack marks against concatenated nft sets |
| 2 | **Key device/lease rules on the DESTINATION address** | Shaping is toward the client, so the household device is the *destination*. A lease on `daddr = 10.0.1.2` |
| 3 | **A device lease lifts only that device's INTERACTIVE flows** | Otherwise the lease boosts the laptop's bulk download too. Test: leased laptop running a bulk download |
| 4 | **Mark rules must outrank the DSCP EF filter** | The existing DSCP filter is prio 1. If it runs first, EF traffic is sent to `1:10` before marks are consulted. Either give marks lower `prio` in nft, or move DSCP matching into nft entirely |
| 5 | **IPv6 equivalents + gate checks** | Sets must exist for v6, and the gate must prove a mark routes bytes **and** that it expires — on both families |
| 6 | **Measure CPU cost of the mechanism** | Graded criterion; must not pollute the overhead number |
| 7 | **`cake … besteffort`** | Otherwise cake re-prioritises by DSCP *inside* the leaf, double-deciding priority |
| 8 | **Keep `fq_codel` for the main matrix** | `cake dual-dsthost` is tested as an addition, not substituted, so results stay comparable |

---

## Required new work surfaced by this audit

**Correction feature (Tata requirement, currently absent):**

- a command/endpoint to record a correction (`aciqctl classify --correct <flow> --as <class>`)
- the classifier **reads** corrections and applies them to later decisions
- a test proving a correction changes a subsequent decision
- write to `data/corrections.jsonl` (append, one JSON object per line)

This is what makes the later optional ML comparison credible: you cannot compare
a model against a baseline if there is no ground truth and no correction path.

**M7 intent API** — required for the lease to be demonstrable at all.
**M8 dashboard** — listed by Tata as expected output.

---

## Open item

**TELIPORT round dates are still unset.** Steps 4–7 cannot be prioritised
against a real deadline until they are known.