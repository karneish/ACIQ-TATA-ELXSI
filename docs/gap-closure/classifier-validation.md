# Classifier validation

Covers §8. Reproduce with `python3 tools/eval_classifier.py --json out.json`.
Raw output: `classifier-evaluation.json`.

## Ground truth is independent

Every case is *constructed* from a workload profile — the label is a property of
how the flow was built, decided before the classifier ran. No label is taken from
the classifier's own output. The thresholds in `aciq/classify.py` are not
touched by the evaluation, so this is not a train/test split over the same data.

16 cases: 4 interactive, 3 video, 2 bulk, 3 adversarial, 3 that must abstain,
1 correction.

## Results

| link capacity | accuracy (labelled) | macro F1 | abstention | required-to-abstain, did |
|---|---|---|---|---|
| 100 Mbps (shipped default) | 0.6154 | 0.7273 | 0.1875 | 3 / 3 |
| 10 Mbps (what `--drop 10` produces) | 0.8462 | 0.8487 | 0.1875 | 3 / 3 |

Per class at 10 Mbps:

| class | support | precision | recall | F1 |
|---|---|---|---|---|
| realtime_interactive | 5 | 0.80 | 0.80 | 0.800 |
| adaptive_video | 5 | 1.00 | 0.80 | 0.889 |
| bulk_transfer | 3 | 0.75 | 1.00 | 0.857 |

**Abstention is correct in every case that requires it.** The three
insufficient-evidence flows — too few packets, too young, no evidence at all —
all return `cls=None` rather than a guess. That is the behaviour the prompt asks
for and it is the part that matters most: forcing a class from no evidence is
worse than declining.

## Two real defects found

**P1-007 — an EF claim is refused only when the flow saturates.**

```
ADVERSARIAL bulk claiming EF
  80 MB moved, 15 KB packets, 99% duty, dscp=46
  capacity 100: truth=bulk_transfer  got=realtime_interactive  conf=0.95 tier=A
```

`too_fast = frac >= 0.5`. At 21% of a 100 Mbps link that is false, so the claim
is honoured. There is **no packet-level bulk test anywhere in the classifier** —
Tier B's bulk rule is also rate-based, so "bulk" and "saturating" are the same
predicate. A large one-way transfer below half the link is not bulk by
definition.

**P1-009 — the port fallback can override behaviour.**

```
ADVERSARIAL interactive on a bulk port
  small bidirectional flow on port 873 (in BULK_PORTS)
  truth=realtime_interactive  got=bulk_transfer  conf=0.70 tier=A
```

The well-known-port fallback runs after the rate rules but is not gated on them
being *inconclusive*. A port hint overrides a flow demonstrably not bulk-shaped.

## Neither is patched here, and why

Both change which class a flow receives, which is the decision that drives
enforcement. This shell cannot run the kernel-integrated experiment that would
show enforcement still behaves afterwards. Shipping an unvalidated change to
the rule that assigns classes is precisely the failure mode this project has
spent its history correcting. The fixes are small and specified:

- P1-007: consult the same bulk evidence in the EF path, including a
  packet-level test (average packet size, directionality, duty) rather than rate
  alone.
- P1-009: gate the port fallback on the rate rules being inconclusive rather
  than merely unmatched.

## A caveat that applies to every stored run

`BULK_MIN_CAPACITY_FRAC = 0.5` means a flow is bulk only above half the link.
Every stored experiment in `data/` ran at 100 Mbps with ~25 Mbps of load, so
**bulk should rarely have been assigned at all** — the `bulk_transfer` byte
figures reported from those runs deserve re-reading through this lens. At 10 Mbps
the same flows classify correctly, which is why the capacity column above is
reported rather than a single number.

## Limitations

- 16 constructed cases is a smoke test, not a benchmark. The numbers are exact
  for this set and should not be quoted as a general accuracy figure.
- Ground truth is by construction; it cannot catch a generator that does not
  resemble real traffic.
- `leased_flow` has no support here. A lease is an operator override, not a
  classification outcome, so it has no ground truth in this evaluation.
