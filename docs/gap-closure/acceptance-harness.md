# Acceptance harness

**Status: the harness itself runs end to end.**
**Status: current-revision run — PASS 22, FAIL 1, BLOCKED 0, NOT RUN 0 at `c5da3fd9`.**

The result below at `89b87758` is kept as the historical record. The current
run at `c5da3fd9` added phase 4b (offline resource soak) and phase 7b (data
reconciliation), reads `1174 tests` at phase 1, and was executed on the user's
own host with `sudo`, so every kernel-dependent gate ran rather than reporting
`BLOCKED`.

**The single FAIL is `interactive latency tail`: 13.5% of packets above 5 ms
against a 10% limit.** The threshold was not moved. `docs/PROJECT_REPORT.md`
§11.1 has the per-seed breakdown — two of seven seeds adopted the degraded
capacity at t = 4.14 s instead of 2.05 s, so bulk ran uncapped for two extra
seconds and the interactive packets queued behind it. The other 22 gates pass,
including the whole of phase 1, the metric-integrity recomputation, the API
security suite, the classifier evaluation, and both data-reconciliation gates.

## One command

```bash
python3 tools/acceptance.py            # writes artifacts/validation/<rev>/
python3 tools/acceptance.py --out /tmp/acceptance.json
```

The kernel-dependent gates need root and `iproute2`:

```bash
sudo python3 tools/acceptance.py
sudo bash tools/host_gate.sh --full    # re-measures the live evidence first
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

## Result at `c5da3fd9` (current)

```
phase 1  [PASS   ] unit+integration+socket          1174 tests, 10 skipped, exit 0
phase 2  [PASS   ] metric integrity                arithmetic + socket recomputation
phase 3  [PASS   ] api security                    auth, bind policy, rate limit, audit
phase 4  [PASS   ] classifier evaluation           two corpora, two capacities
phase 4b [PASS   ] offline resource soak           controller structures bounded, 20 s
phase 5  [PASS   ] control-plane benchmark
phase 6  [BLOCKED] testbed gate (21 checks)        missing ip, tc; euid=1000, need 0
         [BLOCKED] live enforcement
         [BLOCKED] live rollback verification (kernel)
         [BLOCKED] rollback under real tc failure
         [BLOCKED] live adaptation loop
         [BLOCKED] FIFO/CAKE/ACIQ comparison
         [BLOCKED] 30-minute stability
phase 6b [PASS   ] lint (ruff)                     no findings
phase 7  [PASS   ] claim audit
phase 7b [PASS   ] headline vs raw reconciliation  medians re-derived, self-report == obs
         [PASS   ] transition/steady tail split    per-packet delay split at t=5 s

PASS 10  FAIL 0  BLOCKED 7  NOT RUN 0
complete acceptance run: False
```

The recorded field is `complete: false` and it is computed, not typed —
`counts[BLOCKED] == 0`. A run with any blocked gate cannot report completeness.

## What it checks, and the order

1. the full suite, so a later phase cannot report success on a broken base;
2. metric integrity alone, because metric claims underpin every other number;
3. API security over the wire on loopback;
4. the classifier against two corpora (constructed + independent) at two
   capacities;
4b. an offline resource soak, because long-run memory drift is testable without
   a kernel and was previously marked BLOCKED only for want of a harness;
5. control-plane benchmark;
6. kernel-dependent gates — **all or none**, gated on `ip`/`tc` present and
   `euid == 0`;
7. the claim audit, last, so it sees the final tree;
7b. data reconciliation — the headline table re-derived from raw per-seed files,
    plus a per-packet check that each workload's self-report is reproducible
    from its own observations, and the transition/steady latency split.

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
| `api-security.log` | auth/bind/rate-limit suite, verbose |
| `classifier-eval.log`, `classifier-evaluation.json` | confusion matrices, per-class metrics, both corpora |
| `offline-soak.log`, `offline-soak.json` | RSS over time, structure sizes |
| `benchmark.log`, `benchmark.json` | controller timings |
| `claim-audit.log` | constants, evidence, red-flag phrases |
| `reconcile.log`, `tail-analysis.log` | headline-vs-raw reconciliation, transient/steady split |

All under `artifacts/validation/<short-revision>/`, so evidence is bound to the
commit it came from.

## To get a complete run

On a Linux host with `iproute2` installed:

```bash
sudo -v && python3 tools/acceptance.py
```

Phase 6 then executes `testbed/gate.sh` and its result is no longer inferred
from the environment.
