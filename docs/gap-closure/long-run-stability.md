# Long-run stability

Covers §16.

## Not measured

**No sustained multi-hour run exists.** Every run in `data/` is 30–40 seconds.
This shell cannot create namespaces, so a long run cannot be started here.

That is a real gap and it is not something a 40-second run substitutes for.
Stability claims — no oscillation, no unbounded growth, no leak — need time.

## What the design bounds, and where the bounds are enforced

| risk | bound | enforced at |
|---|---|---|
| RTT window per label | `window` samples (50) | `MetricsCollector.ingest` |
| lease accumulation | expired leases dropped from `active()` | `LeaseBook.active` |
| verdict history | `window_verdicts` (200) | `ExperimentRunner` |
| rate-limit table | 1024 clients, oldest-half eviction | `IntentService._allow_write` |
| audit log | one line per commit, never truncated | `audit.json` |
| filter residue | removed on every run exit | gate check 20 |

Two of these were defects found during this work. The verdict history and the
rate-limit table both grew without bound until bounded; the rate table only
surfaced under the fixed clock of a test, where nothing ever expired.

## What a 40-second run *can* show, and did

- **Policy oscillation:** none. Across the seven-seed lease matrix,
  `policy_changes` is 0–2 per run, and the shield's 5 s window is the reason it
  cannot be higher.
- **Filter stability:** verified across a 41-tick run — `fixcheck` held 5
  filters for the whole run after the rebuild-loop defect was fixed. Before that
  fix, the same run committed ten policy changes and destroyed the filters every
  five seconds. That *was* an oscillation, and it is fixed.
- **Recovery after temporary impairment:** the lease reverts on expiry and the
  unleased plan is re-applied, verified in the audit.
- **Counter discontinuity handling:** rate computations guard `dt <= 0` and a
  counter reset produces a negative delta rather than a fabricated spike. The
  reset at teardown is visible in the data as `-487.3`, which is correct
  behaviour — it shows the detection works rather than hiding it.

## Restart recovery is not verified

§16 asks whether restart reconciles actual kernel state with current policy. It
does not: the lease book reloads from disk, the harness has no record of what the
kernel is running, and the two can disagree. See
`device-identity-and-leases.md`.

## What to run

```bash
cd ~/Desktop/Full-projects/TATA-ELXSI
# 30 minutes of mixed load, watching policy_changes and RSS
sudo python3 run_experiments.py --scenario s3_tv_and_gaming --system aciq \
  --enforce --drop 10 --drop-at 5 --seed 42 --results-dir data/soak
# then, repeatedly, across hours:
#   policy_changes per run (should be small and bounded)
#   filters_installed (should be stable, not decaying)
#   rss of the controller process
```

**Blocked-environment.**
