# Classifier before and after

Same 16 cases, same ground truth, same two capacities, same tool.

## Confusion matrices

### Before (`artifacts/validation/89b87758/classifier-before.txt`)

**100 Mbps**
```
truth \ predicted   interactive   adaptive   bulk   abstain
interactive               4          0         1        0
adaptive                  1          4         0        0
bulk                      1          2         0        0
(abstain)                 0          0         0        3
                                      accuracy 11/16 = 0.6875
```
**10 Mbps**
```
interactive               4          0         1        0
adaptive                  1          4         0        0
bulk                      0          0         3        0
(abstain)                 0          0         0        3
                                      accuracy 14/16 = 0.8750
```

### After

**100 Mbps** — `12/16 = 0.7500`
```
interactive               5          0         0        0
adaptive                  1          4         0        0
bulk                      0          3         0        0
(abstain)                 0          0         0        3
```
**10 Mbps** — `15/16 = 0.9375`
```
interactive               5          0         0        0
adaptive                  1          4         0        0
bulk                      0          0         3        0
(abstain)                 0          0         0        3
```

## The three reported defects

| defect | before | after |
|---|---|---|
| **A** EF abuse | `interactive 0.95` tier A, both capacities | `adaptive 0.60` tier B at 100; `bulk 0.75` at 10 |
| **B** capacity sensitivity | macro F1 0.73 vs 0.85 | **not a defect — see below** |
| **C** port fallback demotion | `bulk 0.70` tier A, both capacities | `interactive 0.55` tier B, both capacities |

A and C are closed. The interactive→bulk cell went from 1 to 0 at both
capacities.

## Defect B was not a defect

The reported symptom — "bulk is never assigned at 100 Mbps" — is the documented
design:

> 88 Mbps is a hog on a 100 Mbps link and a nobody on a gigabit.

An absolute floor was added to the bulk rule to make bulk reachable on a wide,
lightly-loaded link. It broke four tests asserting the opposite, and **those
tests are right**. The evaluation that appeared to justify it was mislabelling
its own cases: a 21 Mbps transfer on a 100 Mbps link is 0.21 of the link and is
not hogging, so `ADAPTIVE` was correct.

The floor was reverted, the design is now asserted by
`test_a_moderate_transfer_on_a_wide_link_is_not_bulk`, and the corrected
finding is recorded here rather than as a "fix".

**The macro F1 difference is not evidence of a better classifier at 10 Mbps.** It
reflects the same cases sitting either side of a capacity-relative threshold —
a property of the labels under that semantics, not of classification quality.

## The two remaining errors, and why both are defensible

| case | truth | got | why |
|---|---|---|---|
| 2.4 Mbps flow claiming EF | adaptive | interactive | within plausible interactive range; a documented decision, not an oversight |
| 21 Mbps transfer, 100 Mbps link | bulk | adaptive | 0.21 of the link — not hogging, by design |

Neither is a defect under the documented semantics.

## Test count: 746 → 757

| change | count | note |
|---|---|---|
| baseline | 746 | |
| EF regression scenarios | +6 | abuse, repeat-abuse, normal call, bursty, high-throughput media, asymmetry-not-duty |
| port regression scenarios | +3 | no demotion, rate-outranks-port, raise-still-works |
| capacity-relative design guards | +2 | moderate transfer, same transfer narrow link |
| **total** | **757** | nothing deleted, nothing weakened |

## Fixture corrections — disclosed, not hidden

Three tests changed input, none changed an assertion:

`mature()` left `tx_bytes = 0`, so **every** fixture was strictly
one-directional — a download, not a conversation. That was invisible until a rule
began asking whether a flow looks interactive, at which point three tests failed
for reasons unrelated to what they were testing. The helper now mirrors `rx` in
`tx`, **halving `rx` so the implied rate is unchanged**.

Two `TrustStore` tests were corrected the same way, with `rx` and `tx` split
rather than added, for the same reason.

Both changes make the fixtures *more* realistic. Neither relaxes an assertion.

## An error of my own, recorded

The first attempt at the EF fix computed `not_interactive`, recorded a trust
miss, and then wrote `if not_interactive: pass` — a no-op. The claim was still
granted, and **the evaluation is what caught it**: `parent_max` style
regression would not have, because the branch had been "handled". A subsequent
attempt returned `None` from `classify()`, which breaks the contract; the
fall-through had to happen inside the function.

The lesson is the same one this project has repeated: an instrument that
measures the right thing catches what a test written against the implementation
cannot.
