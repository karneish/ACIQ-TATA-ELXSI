# Claim audit

Covers §20. **Reproducible: `python3 tools/audit_claims.py`.** Raw:
`claim-audit.json`. Exit code 0.

## Method

A claim is *supported* if the symbol it names exists, the constant it quotes
matches the code, or the artefact it cites exists and says what is claimed. A
claim whose evidence is missing is reported rather than left in place.

## Constants quoted in the documentation vs the code

All 11 agree. This check found four stale numbers in `docs/PROJECT.md` when it
was first written (gate check 6 at 92.6 rather than 92.7, check 7 at 20.107
rather than 20.072, and two byte counts carried from an older gate run) — all
now taken from `docs/evidence/gate-20261011-165455.log`.

```
ok  SAT_OVERLIMIT_MIN            3000.0     ok  DROP_RATE_LIMIT        5000.0
ok  BACKLOG_MIN_BYTES            1024       ok  OVERLIMIT_RATE_LIMIT   5000.0
ok  MIN_SAMPLES_FOR_PERCENTILES  10         ok  MIN_PAIRS_FOR_PVALUE  6
ok  BULK_MIN_CAPACITY_FRAC       0.5        ok  MAX_BODY_BYTES         65536
ok  EF_FAST_CONFLICT_CAPACITY_FRAC 0.5       ok  RATE_LIMIT_WRITES      30
ok  MIN_CONFIDENCE               0.5
```

## Evidence cited by claims

| claim | evidence | present |
|---|---|---|
| `p = 0.0312` (b0_fifo) | `data/matrix6` | yes |
| `0.015625` (lease Wilcoxon) | `data/ab_lease_42` | yes |
| `92.6` / `92.7` (gate check 6) | `docs/evidence` | yes |
| `20 PASS` | `docs/evidence` | yes |
| `12.92` (withdrawn figure) | `docs/limitations.md` | yes — and withdrawn there |

## Red-flag phrases

None. The audit found one: `PLAN.md` described gate check 12 as one that
"records numbers, **never fails**", which is loose phrasing for a check that
deliberately asserts no threshold. Rewritten to say what it actually does.

## Claims by status

### Supported by measurement

- per-flow steering, IPv4 and IPv6, including teardown — gate 15–20
- capacity drop enforced: parent `100Mbit → 10Mbit`, `capacity_change_applied:
  True`, ceiling held at 10.04–10.19 Mbps across fourteen runs
- per-device lease discrimination: only `tv1` (`203.0.113.4`) classified leased
- lease raises the leased device's share: **p = 0.015625, n = 7**, seven paired
  seeds, sender-side measurement
- lease lifecycle: granted, honoured, expired, reverted — "in effect for 38.0s"
- controller overhead: 0.64% CPU peak; arithmetic benchmarks in
  `performance-measurements.json`

### Implemented and unit-tested, not kernel-verified

- capacity *estimation* (replay-verified on a recorded run; live path never run)
- rollback and read-back verification (`FakeRunner` only)
- API authentication, rate limiting, bind policy (verified over the wire on
  loopback, which is the deployment model)

### Explicitly not claimed anywhere

- superiority over CAKE — `matrix6` shows **no significant difference**
- production readiness, real-time behaviour, guaranteed fairness, zero loss
- any IPv6 or protocol claim beyond what gate 14, 16–20 exercised

### Withdrawn

- **"12.92 Mbps mean in the leased class."** Measured before workloads had
  distinct addresses, so the lease matched every flow and the class took the
  whole link. Evidence that steering works, not that leases protect a device.
  Withdrawn in all three files that carried it, each naming the withdrawal.
- **Every `--drop-at` claim before the `set_capacity` fixes** — those runs
  reported the requested argument as if it were a measurement.

## One honesty note

This audit checks that evidence *exists*, not that a claim is *true*. A claim
supported by a stale artefact would pass. The specific instance of that in this
project — the withdrawn `12.92` — is exactly why the check cannot be the only
one, and why every gate-closure document states what remains unverified in prose
as well.
