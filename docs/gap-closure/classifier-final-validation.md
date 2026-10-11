# Classifier final validation

The `89b87758` changes were re-inspected and re-measured, not rewritten.

## Required properties, each traced to code and a test

| property | where | test |
|---|---|---|
| EF alone cannot grant interactive priority | `aciq/classify.py:281` — `not_interactive` gates the claim | `test_sustained_bulk_claiming_ef_is_not_interactive` |
| bulk behaviour considered independently of the EF mark | `FlowFeatures.looks_interactive()` (`:193`) reads rate and asymmetry only; it never inspects DSCP | `test_asymmetry_is_the_separator_not_duty_cycle` |
| port fallback cannot override stronger evidence | rate rules (step 3) precede port hints (step 4); `:387` requires `looks_interactive()` | `test_a_small_flow_on_a_bulk_port_is_not_bulk` |
| conflicting signals follow explicit precedence | documented 6-step tree in `classifier-policy.md` | `test_rate_evidence_outranks_the_port_hint` |
| low confidence does not get priority | `abstain` at `conf=0.35` for insufficient/too-young/idle | `test_bulk_threshold_is_relative_adaptive_is_absolute`, `test_insufficient_*` |
| missing/stale handled explicitly | `mature()` gate; missing `age_s`/`rx_bytes` → abstain | `test_immature_ef_flow_is_not_judged_a_conflict`, `test_insufficient_*` |
| inference independent of ground truth | `classify(f, capacity_mbps, trust)` — no label parameter exists | signature check |
| evaluation labels independent of predictions | `tools/eval_classifier.py` builds truth from the case constructor, never from `Classification` | `:40`, `:170` |

`classify()` has no label, truth or expected argument, so ground truth cannot
reach inference even accidentally.

**Correction.** An earlier revision of this table cited four test names that do
not exist (the invented names are recorded in `acceptance-harness-audit.md`
rather than here, so they are not re-cited as evidence). The tests were real and
the behaviour was correct; the *names* were invented while writing the
document. That is exactly the failure the brief's traceability rule exists to
catch, and it survived because nothing checked it.

`tools/audit_claims.py` now verifies every `test_*` identifier cited in
`docs/gap-closure/` against the actual test sources, so a citation that names
nothing is a DRIFT like any other.

## Measured result — `tools/eval_classifier.py`, revision `507ed7af`

```
realtime_interactive  support 5  P 0.8333  R 1.0     F1 0.9091
adaptive_video        support 5  P 1.0     R 0.8     F1 0.8889
bulk_transfer         support 3  P 1.0     R 1.0     F1 1.0
```

15 of 16 cases correct. The single error:

```
ERR  ADVERSARIAL video claiming EF on a small pipe
     truth=adaptive_video  got=realtime_interactive  conf=0.95 tier=A
```

A 2.4 Mbps flow claiming EF on a small link. It is within
`EF_PLAUSIBLE_MAX_MBPS = 20.0`, so the plausibility test does not fire. This is
the **documented safe fallback**, not an oversight: refusing it would mean
asserting video on evidence that only says "interactive is plausible", which is
the exact mistake the whole EF change was made to stop. It stays interactive.

The adversarial cases that motivated the change now pass:

| case | before | now |
|---|---|---|
| bulk claiming EF | `interactive 0.95` tier A | `bulk 0.75` tier B |
| interactive on a bulk port | `bulk 0.70` tier A | `interactive 0.55` tier B |

## Capacity sensitivity — verified, not reopened

The brief asked me to verify the "not a defect" reasoning rather than reopen it.

**What `capacity_mbps` actually is.** `classify()`'s own docstring: *"the
**measured** capacity from M2, never a configured rate."* So the input is the
**estimated bottleneck capacity**, and the same traffic measured against a
different bottleneck genuinely is different traffic. The classifier is not being
asked the same question twice.

**The macro F1 difference is expected.** Bulk classing is defined relative to
capacity: 88 Mbps is a hog on 100 Mbps and a nobody on a gigabit. The same
88 Mbps cases sit on opposite sides of a threshold when capacity changes. Macro
F1 across *both* capacity settings therefore reflects label movement under a
capacity-relative definition, not a change in classification quality.

**The evaluation that appeared to justify a "fix" was mislabelling its own
cases** — a 21 Mbps transfer on a 100 Mbps link is 0.21 of the link and is not
hogging, so `ADAPTIVE` was correct. Ground truth was not changed to match the
classifier; the label was corrected and the design asserted:

`test_a_moderate_transfer_on_a_wide_link_is_not_bulk` — now fails if anyone
re-adds an absolute floor.

**Conclusion: the documented rationale is supported. Retained.**

## Test count

| revision | count |
|---|---|
| `6a22208c` | 746 |
| `89b87758` | 757 (+11 classifier) |
| `507ed7af` | 809 (+29 rollback, +16 harness, +6 live) |

No classifier test was deleted or weakened.
