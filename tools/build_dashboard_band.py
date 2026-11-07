"""Band-wide dashboard from all 840 final-band runs (not 3)."""
from __future__ import annotations
import json, sys
from pathlib import Path
sys.path.insert(0, '.')
from aciq.dashboard import write_snapshot, summary_tiles

root = Path('data/runs_final3')
all_rows = []
runs = sorted(root.glob('*__aciq__adaptive__seed*/samples.jsonl'))
for sf in runs:
    base = float(all_rows[-1]['t'] + 1000) if all_rows else 0.0
    for line in sf.read_text().splitlines():
        if not line.strip(): continue
        r = json.loads(line); r['t'] = float(r.get('t',0)) + base
        all_rows.append(r)
tiles = summary_tiles(all_rows)
prov = {"runs": 840, "aciq_runs": len(runs), "samples": len(all_rows),
        "commit_hash": "7c6c7235780a", "derived_from_frozen_band": "data/runs_final3",
        "panels": ["latency","jitter","loss","throughput","queue depth","fairness"],
        "tiles": tiles}
Path('data/experiments/dashboard_final3').mkdir(parents=True, exist_ok=True)
Path('data/experiments/dashboard_final3/provenance.json').write_text(json.dumps(prov, indent=2))
write_snapshot(all_rows, Path('data/experiments/dashboard_final3/dashboard.html'),
               subtitle=f"band-wide dashboard: {len(runs)} ACIQ runs, {len(all_rows)} samples (frozen band 7c6c7235780a, derived, not rerun)")
print(f"band dashboard: {len(runs)} runs, {len(all_rows)} samples, tiles={tiles[:2]}")
