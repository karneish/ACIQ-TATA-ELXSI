# Post-705cdd5 baseline

Status labels: PASS · FAIL · BLOCKED · INCONCLUSIVE · NOT RUN

## Revision

| | |
|---|---|
| current | `6a22208c` at baseline, `89b87758` after this change set |
| reported published | `705cdd5` |
| relationship | **same content, different hash** |

`705cdd5` is the *exported standalone* commit; the local history is `6a22208c`.
Both have identical subjects and timestamps, and the trees are byte-identical:

```
exported tree  e87d9cb7dbd97cced80dcd0ec9e70f910b28dc0f   1115 files
local   tree  e87d9cb7dbd97cced80dcd0ec9e70f910b28dc0f   1115 files
```

So the current revision **is** `705cdd5` in content. The hash differs because
`tools/export_aciq.py` replays the history into a root-level repository rather
than sharing one object store.

Branch `main`. Working tree clean for `TATA-ELXSI` (0 changes). The repository
root shows ~30,000 deletions across unrelated sibling projects
(`n8n`, `CyberSecurity`, `METHRIX-MVP`, …); those are pre-existing and **not
touched** by this work.

## Environment — the binding constraint, established not assumed

The prompt says an executable missing from one shell is not necessarily missing
from the host. I checked rather than assumed, and the conclusion is that this is
**a sandbox, not the user's host**:

| check | result |
|---|---|
| `/proc/1/comm` | **`bwrap`** — bubblewrap sandbox |
| `CapEff` | **`0000000000000000`** — zero capabilities |
| `CapBnd` | `0000000000000000` |
| `unshare --net` | `unshare failed: Operation not permitted` |
| `ip`, `tc`, `iperf3`, `nc`, `ping`, `nft`, `socat` | not present anywhere on the filesystem |
| `dpkg -s iproute2 / iperf3 / iputils-ping` | **not installed** (not a `PATH` artifact) |
| `sudo` | not present |

So: not installed at package level, zero capabilities, cannot unshare a network
namespace. **Every kernel-level gate is BLOCKED here.** The user shell runs the
same gate to 20 PASS / 1 MEASURED / 0 FAIL, so the tools exist there.

## Validation commands actually supported

Found by inspection, not invented:

| purpose | command |
|---|---|
| all tests | `python3 -m unittest discover -s tests -t .` |
| metric arithmetic | `python3 -m unittest tests.test_measure` |
| metric integration (real socket) | `python3 -m unittest tests.test_measure_integration` |
| API security | `python3 -m unittest tests.test_api_security` |
| classifier | `python3 tools/eval_classifier.py` |
| benchmark | `python3 tools/bench.py` |
| claim audit | `python3 tools/audit_claims.py` |
| acceptance (new) | `python3 tools/acceptance.py` |
| gate | `sudo env ACIQ_VENV=... ./testbed/gate.sh` |

## Results

| gate | status | detail |
|---|---|---|
| unit + integration + socket | **PASS** | **757 tests**, exit 0 |
| metric integrity | **PASS** | arithmetic + live socket recomputation |
| API security | **PASS** | 27 tests, over-the-wire |
| classifier evaluation | **PASS** | 16 cases × 2 capacities |
| benchmark | **PASS** | control-plane cost |
| claim audit | **PASS** | exit 0 |
| testbed gate (21 checks) | **BLOCKED** | missing `ip`/`tc`; euid 1000 |
| live enforcement | **BLOCKED** | same |
| rollback under real `tc` failure | **BLOCKED** | same |
| live adaptation loop | **BLOCKED** | same |
| FIFO/CAKE/ACIQ comparison | **BLOCKED** | same |
| 30-minute stability | **BLOCKED** | same |

**Test count: 746 → 757.** All 11 added; no test was deleted or weakened.
Count changes are explained in `classifier-before-after.md`.

## Previously reported defects, current status

| defect | status now |
|---|---|
| zero-valued metric defaults | **closed** — re-verified live, see `metric-integrity.md` |
| ingest/poll key mismatch | **closed** — regression test exercises the real label path |
| ingest once after the run | **closed** — series verified to change between polls |
| `or` as null-coalesce | **closed** — measured zero survives |
| API auth / bind policy | **closed** — re-verified, incl. rate-limiter bounds |
| rate limiter unbounded | **closed** — proven bounded on 6 conditions |
| classifier defect A (EF abuse) | **closed** this run |
| classifier defect B (capacity) | **not a defect** — the "fix" was reverted; design asserted |
| classifier defect C (port fallback) | **closed** this run, symmetrically |

## Newly discovered during this run

1. `mature()` in the test helpers left `tx_bytes = 0`, making every fixture
   strictly one-directional — a download, not a conversation. Latent until a rule
   started asking whether a flow looks interactive. **Fixed at the source.**
2. The interactive-port rule granted priority unconditionally — the mirror image
   of the reported bulk-port defect, unreported because only the bulk case was
   examined. **Fixed.**
3. My own first attempt at the EF fix was a no-op (`if not_interactive: pass`),
   caught only because the evaluation still showed 0.95.

## Changes made in this run

See `classifier-before-after.md` for the classifier change set in full, and the
release-readiness report for the complete list.
