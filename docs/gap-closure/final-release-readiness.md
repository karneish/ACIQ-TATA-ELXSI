# Final release readiness

**Revision:** `89b87758` · **Published:** `705cdd5` (same content, exported history)
**Test suite:** 757 pass, 0 fail · **Claim audit:** exit 0

## Verdict

**NOT READY FOR RELEASE.**

Not "ready with caveats". The pieces that have been validated are validated
properly; the pieces that decide whether this is *useful* cannot be reached from
this environment, and the project's own gate is the thing that would answer
them.

## Readiness by dimension

| # | dimension | status | basis |
|---|---|---|---|
| 1 | core traffic classification | **PASS** | 16 constructed cases, two capacities; 9 prior defects closed |
| 2 | measurement and metrics integrity | **PASS** | re-verified live over a socket; arithmetic recomputed independently and matches |
| 3 | API and security | **PASS** | 27 tests, over the wire; limiter proven bounded on 6 conditions |
| 4 | documentation accuracy | **PASS** | claim audit exit 0; no red-flag phrases |
| 5 | repository / packaging hygiene | **PASS** | 757 tests, no import-time side effects |
| 6 | Linux traffic management enforcement | **BLOCKED** | no `ip`/`tc`/`sudo`; gate is 20/21 on a privileged host |
| 7 | end-to-end traffic shaping | **BLOCKED** | same |
| 8 | stability over extended runs | **BLOCKED** | no run exceeds 40 s; brief requires >= 30 min |
| 9 | live adaptation response | **BLOCKED** | estimator replay-verified, never live |
| 10 | rollback under real failure | **BLOCKED** | control flow unit-tested; no kernel round-trip |
| 11 | fairness / non-starvation | **BLOCKED** | property proven; starvation needs a long run |
| 12 | CAKE / FIFO comparison | **BLOCKED** | CAKE not installable here |
| 13 | hardware / driver coverage | **BLOCKED** | one VM, one link |
| 14 | resource and reliability behaviour | **PARTIAL** | bounded by construction; load unmeasured |

**6 PASS · 1 PARTIAL · 7 BLOCKED · 0 FAIL.**

No dimension is FAIL. That is a real result — nothing checked was found broken.
It is also not a pass, because the seven blocked dimensions include every one
that distinguishes a working QoS controller from a correct-looking one.

## Why blocked is not a soft pass

The classifier, the policy planner and the metric collector have been validated
directly and thoroughly. What remains unvalidated is the part that makes them
matter: whether a flow actually lands in the class it was assigned, at the rate
it was given, on a real link.

Steps 5-7 and 9 of the nine-step chain in `live-enforcement-validation.md` are
exactly the steps that separate application-level correctness from kernel-level
correctness, and **all four are BLOCKED**. A controller that renders the correct
`tc` command has demonstrated it can write a string.

## The one command that changes this verdict

On a Linux host with `iproute2`:

```bash
cd ~/Desktop/Full-projects/TATA-ELXSI
sudo -v && python3 tools/acceptance.py
```

If `complete: true` with 0 FAIL, dimensions 6 and 7 close. The remaining
blocked dimensions need the soak and the comparison suite, both of which are in
`live-adaptation-stability.md` and `qos-baseline-comparison.md` with acceptance
thresholds stated **before** they run.

## Current classifier behaviour, including where it is wrong

| case | classification |
|---|---|
| 5 interactive flows | **interactive, all correct at both capacities** |
| 5 video flows | **4/5 correct at both capacities** |
| 3 bulk at 10 Mbps | **3/3 correct** |
| 3 bulk at 100 Mbps | **0/3 as bulk** |
| ambiguous cases (3) | abstain, **all correct** |
| **accuracy** | **100 Mbps 12/16 = 0.7500 · 10 Mbps 15/16 = 0.9375** |

The 0/3 at 100 Mbps is **by design**, and it is the single most important thing
to understand about this classifier:

> 88 Mbps is a hog on a 100 Mbps link and a nobody on a gigabit.

Three flows at 88 Mbps on a 100 Mbps link each get ~33 Mbps. That is ordinary
bandwidth sharing, not congestion, so they are `ADAPTIVE`. A "fix" that forced
them to bulk was tried and **reverted**; `test_a_moderate_transfer_on_a_wide_link_is_not_bulk`
now exists to stop the next attempt.

Both remaining errors are documented decisions, not oversights: a 2.4 Mbps flow
claiming EF stays interactive (within plausible range), and the case above.

## What was fixed in this change set

| defect | outcome |
|---|---|
| EF priority abuse | closed — an EF claim is weighed against measured behaviour |
| interactive port granted unconditionally | closed — found while fixing the mirror case |
| bulk port demoting small flows | closed — port hints now gated both ways |
| "capacity sensitivity" | **not a defect** — reported fix reverted, design asserted |
| `mature()` fixtures one-directional | closed — 3 tests had unrealistic input |

## Full deliverables

| document | contents |
|---|---|
| `post-705cdd5-baseline.md` | revision identity, environment limits, all prior defects |
| `metric-integrity.md` | fresh measurements, validity states, definitions |
| `api-security-validation.md` | auth, bind policy, bounded limiter, audit, limits |
| `classifier-policy.md` | full decision tree, thresholds, known limitation |
| `classifier-before-after.md` | confusion matrices, defect outcomes, test-count reconciliation |
| `live-enforcement-validation.md` | nine-step chain, what is proven vs unproven |
| `rollback-failure-injection.md` | tested failures, the unverified restore |
| `live-adaptation-stability.md` | estimator replay, timings, stability gaps |
| `qos-baseline-comparison.md` | fixture, metrics, the fairness note, the asymmetry |
| `fairness-policy-safety.md` | the enforced guarantee, the deliberate omission |
| `protocol-device-coverage.md` | per-direction testing, transport and device limits |
| `resource-reliability.md` | measured cost, bounded state, blocked load behaviour |
| `acceptance-harness.md` | the harness and its BLOCKED semantics |
| `documentation-claim-audit.md` | constant and evidence checks, withdrawn claims |

## Honest summary

The classifier is measurably better than when this run started, by an
evaluation run before and after on identical cases. Nine of ten reported defects
are closed; the tenth was shown not to be a defect and the "fix" was reverted.

That is a good result for the code. It is not a release, because whether the
software works on a network is still unmeasured, and this environment is not
where that can be measured.
