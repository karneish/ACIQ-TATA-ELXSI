# Final state baseline

Verified by read-only inspection, not inherited from any prior report.

## Repository

| | |
|---|---|
| path | `/home/mekarz/Desktop/Full-projects/TATA-ELXSI` |
| git root | `/home/mekarz/Desktop/Full-projects` |
| branch | `main` |
| HEAD at inspection | `17685a450f479f0c171bd89b101259af7c8f2525` |
| working tree (TATA-ELXSI) | **clean** — `git status --short -- .` returned 0 lines |
| commits confirmed present | `89b87758`, `17685a45` — both verified, hashes match the report |

### Remotes

| name | URL | role |
|---|---|---|
| `aciq` | `https://github.com/karneish/ACIQ-TATA-ELXSI.git` | **the public repository** |
| `origin` | `https://github.com/karneish/Full-projects.git` | parent monorepo — **never push here** |

No credentials are embedded in either URL, so neither had to be redacted.

### Public remote state (read-only)

```
$ git ls-remote aciq HEAD refs/heads/main
705cdd5d62ee129affceb2d3693e40474b6cd876	HEAD
705cdd5d62ee129affceb2d3693e40474b6cd876	refs/heads/main
```

The remote is **two commits behind** and was not modified during this work.

### Untracked / ignored

No untracked source files. Ignored and therefore not part of any commit:
`__pycache__/`, `artifacts/validation/*/**.log`, `data/ab_lease*/`,
`testbed/logs/`. Evidence is committed under `docs/evidence/`; raw run logs stay
out of the tree.

## Environment — rechecked, not assumed

| probe | result |
|---|---|
| `/proc/1/comm` | `bwrap` (bubblewrap sandbox) |
| `CapEff` | `0000000000000000` |
| `euid` | `1000` |
| `ip`, `tc`, `iperf3`, `nc`, `ping`, `sudo`, `modprobe` | all **absent from PATH** |
| `unshare --net true` | `unshare failed: Operation not permitted` |

Per the brief, an executable missing from one shell is not proof it is missing
from the host. That was checked rather than assumed, and the conclusion is that
this is a **sandbox, not the user's machine**: PID 1 is bubblewrap, the
capability set is empty, and `unshare --net` is refused at the syscall level.
A missing `PATH` entry alone would not have justified stopping; the empty
capability set does.

**Privileged operations were attempted once, conclusively failed, and were not
retried.** Every kernel-level gate is BLOCKED from this shell.

## Test configuration

| item | value |
|---|---|
| framework | stdlib `unittest` |
| discovery | `python3 -m unittest discover -s tests -t .` |
| runner script | `python3 tools/acceptance.py` |
| test modules | 21 |
| runtime dependencies | **none** — standard library only, including the metrics server |

## Test count reconciliation

| revision | count | delta |
|---|---|---|
| `6a22208c` | 746 | baseline |
| `89b87758` | 757 | +11 classifier regression tests |
| `507ed7af` | **809** | +29 mocked rollback, +16 harness, +6 live rollback (skipped here) |

Nothing was deleted or weakened at any point. Every added test is accounted for
in `rollback-readback-verification.md` and `acceptance-harness-audit.md`.
