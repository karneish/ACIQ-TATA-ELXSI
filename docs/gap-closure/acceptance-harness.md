# Acceptance harness

**Status: PASS (the harness itself runs end to end).**
**Status: INCOMPLETE acceptance run — 6 of 12 gates BLOCKED.**

## One command

```bash
python3 tools/acceptance.py            # writes artifacts/validation/<rev>/
python3 tools/acceptance.py --out /tmp/acceptance.json
```

## Why it exists

An acceptance run that cannot distinguish "the gate passed" from "the gate could
not run" is worse than none, because it turns an environmental limit into a green
tick. This harness records `BLOCKED` for a missing tool or a missing privilege
and **never** reports that as a pass.

## Result at `89b87758`

```
phase 1  [PASS   ] unit+integration+socket          757 tests, exit 0
phase 2  [PASS   ] metric integrity                arithmetic + socket recomputation
phase 3  [PASS   ] api security                    auth, bind policy, rate limit, audit
phase 4  [PASS   ] classifier evaluation           16 cases, two capacities
phase 5  [PASS   ] control-plane benchmark
phase 6  [BLOCKED] testbed gate (21 checks)        missing ip, tc; euid=1000, need 0
         [BLOCKED] live enforcement
         [BLOCKED] rollback under real tc failure
         [BLOCKED] live adaptation loop
         [BLOCKED] FIFO/CAKE/ACIQ comparison
         [BLOCKED] 30-minute stability
phase 7  [PASS   ] claim audit

PASS 6  FAIL 0  BLOCKED 6  NOT RUN 0
complete acceptance run: False
```

The recorded field is `complete: false` and it is computed, not typed —
`counts[BLOCKED] == 0`. A run with any blocked gate cannot report completeness.

## What it checks, and the order

1. the full suite, so a later phase cannot report success on a broken base;
2. metric integrity alone, because metric claims underpin every other number;
3. API security over the wire on loopback;
4. the classifier against 16 constructed cases at two capacities;
5. control-plane benchmark;
6. kernel-dependent gates — **all six or none**, gated on `ip`/`tc` present and
   `euid == 0`;
7. the claim audit, last, so it sees the final tree.

## Exit code

`0` when there are no failures. **Blocked gates do not fail the run** — they are
recorded as incomplete. A non-zero exit means something was checked and was
wrong, which is a different and more serious event than nothing being checkable.

## Artifacts

| file | contents |
|---|---|
| `acceptance.json` | machine-readable summary, per gate |
| `unittest.log` | full suite |
| `metric-integrity.log` | arithmetic and socket recomputation |
| `api-security.log` | 27 tests, verbose |
| `classifier-eval.log`, `classifier-evaluation.json` | confusion matrices, per-class metrics |
| `benchmark.log`, `benchmark.json` | controller timings |
| `claim-audit.log` | constants, evidence, red-flag phrases |

All under `artifacts/validation/<short-revision>/`, so evidence is bound to the
commit it came from.

## To get a complete run

On a Linux host with `iproute2` installed:

```bash
sudo -v && python3 tools/acceptance.py
```

Phase 6 then executes `testbed/gate.sh` and its result is no longer inferred
from the environment.
