# Classifier policy

The decision tree as it stands after this change set.

## Precedence, highest first

```
0  operator correction (tier X)      -- overrides everything
1  DSCP EF claim, weighed against behaviour   (tier A, conf 0.95 / 0.70)
     a. saturates the link        -> BULK 0.75 (rate evidence)
     b. too slow to be real media -> abstain (tier C)
     c. implausibly interactive   -> DENIED, falls through to 2
     d. otherwise                 -> INTERACTIVE
2  not enough history              -> abstain (tier C, conf 0.35)
3  rate evidence, before ports     (tier B)
     a. frac >= 0.5 of capacity    -> BULK 0.75
     b. tcp and rate >= 0.5 Mbps   -> ADAPTIVE 0.60
4  port hints, only where behaviour does not contradict   (tier A)
     a. interactive port AND looks_interactive -> INTERACTIVE 0.85
     b. bulk port AND (hogs link OR not interactive) -> BULK 0.70
5  packet shape: small udp, not 443, 100-1500 B  -> INTERACTIVE 0.55
6  honest gap                        -> abstain
```

`udp/443` is excluded from rule 5 on purpose: QUIC carries calls and downloads
alike, and calling it interactive on packet size alone would be a guess.

## What changed

**1. EF is an input signal, not proof.** The claim is now tested against a
question that does not depend on the bottleneck: *could this plausibly be a
conversation?*

```
EF_PLAUSIBLE_MAX_MBPS = 20.0
EF_MIN_ASYMMETRY     = 50.0
```

Asymmetry is `max(rx,tx) / min(rx,tx)`. Measured on this project's profiles:

| profile | rate | asymmetry |
|---|---|---|
| call | 0.09 Mbps | 1.0 – 3.3 |
| video | 4.69 Mbps | 22 – 28 |
| bulk | 88 Mbps | 400 – 1200 |

A conversation is bidirectional and small. **Duty cycle was considered and
rejected**: measured 1.00 for every generator, so it separates nothing — the
module already documents this and the new test asserts it.

Denial **falls through to the rate rules** rather than asserting BULK. The
evidence is "not plausibly interactive", not "bulk".

**2. A port may not contradict behaviour, in either direction.** Previously the
bulk port could demote a 0.19 Mbps flow and the interactive port granted
unconditionally. Now both are gated on the observed behaviour. The interactive
side of this was **not** in the reported defects and was found while fixing the
bulk side.

**3. Bulk remains capacity-relative, deliberately.**

> "88 Mbps is a hog on a 100 Mbps link and a nobody on a gigabit, so it stops
> being BULK as the link grows. This is the design, not a bug."

An absolute floor was tried and reverted; `test_a_moderate_transfer_on_a_wide_link_is_not_bulk`
now asserts the design survives the next attempt.

## Unchanged and worth stating

- thresholds still never key on the test generators' own ports (5001–5004);
- `MIN_CONFIDENCE`, `MIN_AGE_S`, `MIN_PACKETS` unchanged;
- a correction still outranks everything;
- abstention is still preferred to a guess.

## Known limitation

A 2.4 Mbps flow claiming EF stays **interactive**. That is within plausible
interactive range and is now a documented decision rather than an oversight: the
prompt is explicit that ambiguous cases need a documented safe fallback, not a
predetermined label.
