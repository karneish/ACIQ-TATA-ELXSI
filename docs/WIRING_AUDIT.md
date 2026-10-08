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

Test counts are per **test file**, not per module. Several modules share a file.

| Module | Test file | Tests | Exists | **Connected** | Measured | Documented as working |
|---|---|---|---|---|---|---|
| **M1 classify** | `test_classify.py` | 28 | yes (157) | **NO** | no | **YES — overstated** |
| **M1b flowtrack** | (same file as M1) | *0 extra* | yes (172) | **NO** | no | **YES — overstated** |
| **M2 capacity** | `test_capacity.py` | 38 | yes (263) | yes (harness) | yes — 100.49 / 99.9 Mbps | yes |
| **M3 policy** | `test_policy.py` | 24 | yes (123) | yes (3 files) | indirectly | yes |
| **M4 tc** | `test_enforce.py` | 54 | yes (244) | yes (3 files) | yes — gates 6, 9, 10, 14 | yes |
| **M5 metrics** | `test_metrics.py` | 32 | yes (409) | yes (3 files) | yes — samples.jsonl | yes |
| **M6 harness** | `test_harness.py` | 37 | yes (306) | yes (entry point) | yes — 6 runs | yes |
| **M6 experiment** | `test_experiment.py` | 40 | yes (379) | yes | yes | yes |
| **M7 intent API** | — | 0 | **NO FILE** | n/a | no | **in PLAN.md** |
| **M8 dashboard** | — | 0 | **NO FILE** | n/a | no | **in PLAN.md** |
| **M9 shield/txn** | (same file as M4) | *0 extra* | yes (550) | yes (2 files) | fault-injection | yes |
| **M10 report** | (same file as M6) | *0 extra* | yes (271) | yes | yes — REPORT.md | yes |
| **workload contracts** | `test_workload_reports.py` | 7 | yes | yes | yes | yes |
| **correction file** | — | 0 | **NO FILE** | **NO** | no | **YES — overstated** |
| **IPv6** | `test_enforce.py` | — | in `tc.py` | yes (1:10 filter) | yes — gates 13/14 | yes |

**Total: 38 + 28 + 54 + 32 + 37 + 40 + 24 + 7 = 260.** Verified two ways:
`unittest discover` reports `Ran 260 tests`, and grepping `def test_` in each file
gives the same eight numbers.

> **Correction to the first draft of this table:** its rows summed to 375. That
> was my error — I listed `flowtrack` 28 (the same `test_classify.py` as M1),
> `M9` 54 (same `test_enforce.py` as M4) and `M10` 40 (same `test_experiment.py`
> as M6), counting three files twice.
>
> Also: `test_policy.py` was 20 tests and is now 24. That is not a miscount — four
> tests were **added** after the measured finding that a 20 Mbps parent with
> `ceil 99/97` children delivered 28.5 Mbps. Legitimate growth.

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

### 2. Correction file — NOW IMPLEMENTED (was: does not exist)

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

## Tata deliverables — required outputs

| # | Deliverable | Status | Evidence / gap |
|---|---|---|---|
| 1 | Architecture diagram | **partial** | `docs/architecture.md` has an ASCII diagram; **device, edge, network, data, analytics, UI** named. Not a rendered diagram |
| 2 | Setup guide, exact versions | **partial** | versions recorded in `data/baselines/v0/README.md`; **no `docs/setup.md` exists** |
| 3 | Known limitations | **partial** | present in `PLAN.md` and `README.md`; **no dedicated `docs/limitations.md`** |
| 4 | Third-party licences | **MISSING** | **no `docs/licenses.md`**. Only dependency is `pyroute2` (BSD-3-Clause) |
| 5 | Scripted demo: reset, inject, collect, report | **yes** | `sudo ./run_experiments.py` does exactly this; ends with `data/REPORT.md` |
| 6 | Dashboard (latency, jitter, loss, throughput, queue depth, fairness) | **MISSING** | M8 has no file |
| 7 | Intent API for temporary requests | **MISSING** | M7 has no file; the lease cannot be requested |
| 8 | IPv4 **and** IPv6 | **partial** | `tc.py` emits an IPv6 `flower` filter; gates 13/14 passed. **No IPv6 run in the matrix**, and M1 has no IPv6 classification path |
| 9 | Classifier confidence exposed | **yes (code only)** | `Classification.confidence`, 28 tests. Not exposed in any output artefact |
| 10 | Classifier correction of misclassification | **MISSING** | Tata requirement. `data/corrections.jsonl` never written |
| 11 | Reproducible data + impairment settings | **yes** | seeded; `config.json` per run; committed netem settings |
| 12 | Emulation labelled as emulation | **yes** | `PLAN.md` limitations; v0 README |
| 13 | No secrets in source control | **yes** | `.env.example` holds only fictitious values |

**Three of Tata's thirteen required outputs are entirely missing** (6, 7, 10),
and a fourth (2, 3, 4 — documentation set) is missing in file form.

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

*(That label describes the v0 baseline only. The classifier-to-enforcement join
exists as of 2026-10-08 and is proven by gate checks 16-20, but no run has been
measured with it enabled, so no result here should be read as post-wiring.)*
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

### Status: BUILT, NOT WIRED, NOT EXECUTED

`aciq/marks.py` and `aciq/bridge.py` now exist and implement the mechanism
described below (commit `dc49ed5d`). What is true and what is not:

| Claim | Status |
|---|---|
| Mark layout defined and unit-tested | **done** — `aciq/marks.py`, 32 tests |
| nftables set-per-class, `flags timeout` | **done, command generation only** |
| Static `tc fw` filters masked to the class nibble | **done, command generation only** |
| Kernel accepts the generated commands | **NOT VERIFIED** — gate checks 15–20 written, never run |
| Marks actually influence enforcement | **NO** — `harness.py` does not import `bridge` |
| `classify()` is called at runtime | **NO** — still tests only |

The two design points below were settled by measurement, not by argument, and
both differ from what this audit originally proposed. See "Corrections" at the
end of this file.

### Mechanism chosen: conntrack marks, keyed on the 5-tuple

Per-host nft sets are **rejected**: a device running Teams *and* Steam would put
both flows in one class, which is requirement 1 violated by construction.
Concatenated sets are also rejected — the 5-tuple is not a contiguous key, so
concatenation degenerates to a scan.

Instead, `tc` matches the **5-tuple directly against one nft set of 5-tuple
elements**, and nftables owns the expiry:

```
nftables (router ns)
  set interactive_v4 { type inet_service ; flags timeout ; }   # dport
  set flow_interactive_v4 { type ipv4_addr ; flags timeout ; } # src, matched
                                                               # in tc via u32/flower
                                                               # on the full tuple
  #   -> both src and dport must match: two lookups, one rule each
  #   -> lease: add the device's dst-address set, expire = ttl_s

tc — STATIC, built once, never rebuilt
  filter add … protocol ip prio 10 flower ip_tos 0xb8/0xfc mark 10 flowid 1:10
  filter add … protocol ip prio 20 flower ip_tos 0xb8/0xfc mark 10 flowid 1:10
  filter add … protocol ip prio 30 u32   <5-tuple match> mark 20 flowid 1:20
  filter add … protocol ip prio 40 u32   <5-tuple match> mark 30 flowid 1:30
```

**Shaping is toward the client, so the household device is the DESTINATION.**
Every device and lease rule keys on `daddr`, never `saddr`.

**The priority conflict is in `tc`, not nft.** Two options:

| Option | Change | Risk |
|---|---|---|
| **A** | Give mark filters `prio 10` and the EF filter `prio 20` | If EF matches first, marks never apply to marked traffic. Ordering must be proven |
| **B** | Delete the `u32` DSCP filter; match DSCP in nft as one more set | Removes the conflict entirely; larger change to `tc.py` |

Neither has been tested. **Gate check 15 must prove mark-filtered traffic reaches
its class; check 16 must prove an expired mark reverts to the default class.**
Both on IPv4 **and** IPv6.

**`cake … besteffort`** is required so the leaf does not re-decide priority by
DSCP inside the qdisc — otherwise priority is decided twice.

**`cake dual-dsthost`** is tested as an *addition*, not a substitution;
`fq_codel` stays for the main matrix so results stay comparable.

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

**Correction feature (Tata requirement): DONE as of commit below.**

- command: `./aciqctl correct --src ... --dst ... --proto ... --dport ... --as <class>`
- also `aciqctl list` and `aciqctl check`
- `aciq/corrections.py` reads `data/corrections.jsonl` and answers per flow
- `classify()` already honoured `FlowFeatures.correction`; this supplies it
- tests prove a correction changes a subsequent decision
  (`TestCorrectionChangesADecision`), including that `finalise()` cannot demote
  it, that it beats a DSCP-EF verdict, and that it stops applying on expiry

Design decisions worth knowing:

- **Append-only.** A correction is a statement about a class of traffic, not a
  snapshot. Overwriting would destroy the record an accuracy claim is audited
  against. `data/corrections.jsonl` is gitignored, being per-deployment
  operational data rather than source.
- **Source port is never part of a match key.** It changes on every reconnect,
  so a correction keyed on it would stop applying minutes after being made.
  A correction may be port-scoped (default) or host-scoped (`dport: null`).
- **Finite TTL by default (24h).** A correction is a hypothesis about traffic
  that will change. Expiries are counted in `stats.expired` so a stale
  correction is visible rather than merely gone.
- **Specificity wins ties, recency wins outright.** A port correction beats a
  host correction recorded at the same instant; a *later* host correction beats
  an older port one, because re-correcting the whole host is deliberate intent.

One gap remains: corrections are read by the library but the **runtime chain
still does not consult them**, because the runtime chain still does not call
`classify()` at all. See the wiring status above.

**M7 intent API** — required for the lease to be demonstrable at all.
**M8 dashboard** — listed by Tata as expected output.

---

## The bridge: DSCP steering does not work on this toolchain

Two mechanisms were built and measured. The first was impossible; the second was
possible and did not work. Both findings are controls-backed.

### 1. No tc classifier can read a packet mark (iproute2 6.1.0)

Every spelling rejected:

    fw handle 0xNN/0x0f         fw has no `handle`
    fw mask 0xf handle 0x1      fw has no `mask`
    flower meta mark            flower has no `meta` key at all
    basic match "skb/mark ..."  not the ematch grammar
    basic ematch "..."          `basic` takes `match`, not `ematch`

An absent capability, not a syntax slip. This killed `marks.py`'s original role.

### 2. A DSCP written by nftables is invisible to tc

The replacement used nftables to stamp a CSx selector code in prerouting and a
static `flower ip_tos` filter to read it on egress. It installed perfectly and
never matched once. `testbed/bridge_isolate.sh` reproduced it with one filter,
one rule, no sets and no fq_codel, then established each fact with a control:

| fact | control |
|---|---|
| flower ignores `skb->priority` | setting priority alone does nothing |
| u32 works | u32 + sender-set DSCP routes |
| header is 0x18 at postrouting | chain counters read 60 |
| the wire is 0x18 | the client reads 60 |
| a **sender**-written DSCP matches | passes |
| an **nftables**-written DSCP does not | fails, on two different ports |

So the fault is provenance: the same header value, written by a sender, is
matched; written by nftables, it is not. Five hypotheses died to this one,
including a `meta l4proto` width mismatch (the rule matched all 60 packets), a
lost `skb->priority`, and a DSCP that did not survive to egress. Each was
consistent with every measurement available at the time; four of them died to an
*uncontrolled variable* rather than to being wrong -- destination port and
provenance were confounded until tests H and I separated them.

### What ships instead

One `tc flower` filter per flow, matching src/dst/proto/dport directly. Proven
behaviourally in isolate tests J and K, K being the control that proves it does
not over-match.

Costs, stated:

* one netlink transaction per reclassification -- roughly 4-12 ms per tick at 20
  flows, against a ~1 s tick;
* **kernel-side expiry is lost.** The nftables sets expired marks for free via
  `flags timeout`, surviving even a crashed process. Per-flow filters are not
  kernel-timed, so an unclean exit leaves filters routing flows to stale classes.
  `Bridge.teardown()` clears them and callers must use it.

Gains: nothing is mutated on the wire, so the DSCP-rewrite side effect and its
collision risk disappear; no dependency on `tc fw`; no dependency on nftables'
DSCP write being visible to tc.

#### Handles are derived, not counted

The first version allocated filter handles from a per-`Bridge` counter. tc's
handle namespace is per **device**, so two `Bridge` instances -- or one restarted
-- both allocate handle 1, and the second `tc filter add` fails with
"Filter already exists". Gate check 17 hit this: every gate helper is a fresh
`Bridge`, so each restarted the counter.

Handles are now CRC32 of the flow key, masked to 32 bits and never zero. That
makes the bridge stateless with respect to tc: any instance computes the same
handle for the same flow, so `forget()` works even with empty in-process state,
and a restart re-adopts its own filters rather than colliding with them.

Cost: `mark()` now always issues a delete before the add, even when there is
nothing to delete, because that is what makes it restart-safe. Two netlink
transactions per reclassification rather than one.

### Still unresolved

**A fresh process cannot clear residue from a previous one.** `setup()` deletes
the filters this instance knows about, and after a restart it knows none, so
filters left by a crashed run survive until the device is reconfigured. Clearing
them properly needs enumeration of the tc tree, which is not implemented. In the
gate this is invisible because each run rebuilds the namespaces.

## SUPERSEDED (2026-10-08): now wired

Everything above was measured, and it was true when measured. The gap it
recorded is closed:

* `aciq/closedloop.py` calls `classify()`, then `CorrectionStore.lookup()`, then
  `Bridge.classify_flow()`, in that order.
* `Harness.enable_enforcement()` builds the bridge; `Harness.enforce(features)`
  applies one verdict.
* Enforcement is **opt-in**: `enforcement_enabled` is False until a run asks.

What this document's evidence sections still prove, unchanged:

* The v0 baseline results remain DSCP-EF + HTB + fq_codel. They predate the join
  and are labelled that way in `data/baselines/v0/README.md`. **No post-wiring
  run has been measured yet**, so `adaptive_video: goodput 0.0` is still the last
  observed value and "the classifier is inert" is still true *of those results*.
* "ADAPTIVE is unreachable" was a claim about `tc.py` emitting filters only to
  `1:10`. ADAPTIVE is now reachable by a different mechanism -- a per-flow `tc
  flower` filter at priority 5/6 -- proven by gate checks 16, 18, 19 and 20.

Gate check 20 also retired the residue paragraph above: `setup()` and `teardown()`
now enumerate the tc tree with `tc -j filter show` and delete every flower filter
at our two priorities, which is why a fresh `Bridge` can clear a predecessor's
filters.

## The bridge: what the first real run proved

`testbed/bridge_probe.sh` ran for the first time on Pop!_OS kernel 7.1.5,
iproute2 6.1.0. 14 PASS, 28 FAIL, three independent causes:

1. **Missing `.` concatenation tokens (mine).** `ip saddr ip daddr meta l4proto
   th dport @leased` needs `ip saddr . ip daddr . meta l4proto . th dport
   @leased`. Without the dots nftables sees five separate expressions and binds
   the set lookup to only the last. Fixed; 7 tests added. The existing
   tokenisation test could not catch this -- it asserted no whitespace outside
   braced fragments, which is a different invariant.

2. **`tc fw` cannot match a packet mark. This breaks the design.** iproute2
   6.1.0 accepts only `classid`, `indev` and `action` for the `fw` classifier --
   no `handle`, no `mask`, in either syntax. The "nftables sets -> mark ->
   static `tc fw` filters" mechanism in `aciq/bridge.py` **cannot be built on
   this toolchain.** Not a syntax slip: an absent capability.

   `aciq/marks.py` and the nftables half remain correct and useful for
   telemetry, but the mark -> class step needs a different classifier. The
   extended probe tests `flower meta mark`, `basic ematch meta`, steering via a
   DSCP rewrite plus the `flower ip_tos` matcher already proven in check 14, and
   per-class `flower` filters matching the flow key directly. Whichever passes
   becomes the design. **Unresolved.**

3. **The probe's own bug.** Its set/key-shape probes targeted a table that was
   never created, so all three failed with "No such file or directory" and
   reported nothing about the key shape they existed to test.

## Corrections to the bridge design, after measurement

The audit's original Step 3 and the plan's "separate ADAPTIVE from BULK by
on/off pattern" were both wrong, and both were caught by measuring first.

**Duty cycle separates nothing.** Sampling the generators at the same 200 ms
tick `FlowTracker` uses:

| generator | Mbps | duty | burstiness |
|---|---|---|---|
| call  |  0.09 | 1.00 | 0.16 |
| video |  4.69 | 1.00 | 0.47 |
| bulk  | 88.14 | 1.00 | 0.17 |

Duty cycle is 1.00 for all three, because every generator emits continuously at
a target rate. ADAPTIVE is therefore separated from BULK on **rate**, and
`duty_cycle`/`burstiness` are recorded but never used to decide. Video's 0.47
burstiness is an artifact of the 6-second ABR ladder stepping, not a property
of real streaming, so it is not relied on either. **Any accuracy figure measured
on this traffic will be optimistic**, because `video.py` models a stepped
ladder where real streaming drifts smoothly.

**EF conflict is two-sided, not a floor.** The first rule flagged "EF claimed
but rate below 2% of capacity", and the measured call at 0.09 Mbps is 0.09% of a
100 Mbps link — so every legitimate voice call was a "conflict". Too slow to be
media is now an **absolute** floor (10 kbps, below G.711 silence suppression),
because a call's rate does not scale with link speed. Too fast to be believable
is **relative** (claiming EF while consuming half the link), because that is the
actual evasion: one DSCP byte on a torrent.

**ADAPTIVE is absolute, BULK is relative.** An ADAPTIVE threshold of 2% of
capacity classified the 4.69 Mbps stream as UNCLASSIFIED at 1 Gbps, where it is
0.5% — a 1080p stream on a fast line would have received no class at all. So
`ADAPTIVE_MIN_MBPS` is fixed at 0.5 Mbps while `BULK_MIN_CAPACITY_FRAC` stays
relative: "bulk" is a claim about the link, "adaptive" is not. Both properties
are asserted in `tests/test_classify.py`, including that bulk *does* drift with
capacity, since that asymmetry is deliberate.

**DSCP priority in the tc tree remains unshielded.** Mark filters are installed
at prio 10-14 and DSCP-EF moved to prio 30-31 so marks cannot be pre-empted, but
class `1:10` still has `prio 8` over every other class. 32 Mbps of EF still
beats 100 Mbps of bulk. Capping EF at `ceil(1.2 * r_a)` is the fix and needs an
A/B measurement, because it will also worsen video p99.

---

## Open item

**TELIPORT round dates are still unset.** Steps 4–7 cannot be prioritised
against a real deadline until they are known.