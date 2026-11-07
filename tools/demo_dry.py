"""tools/demo_dry.py — Pin-rev demo without sudo.

Uses ExperimentRunner with DryLauncher (no tc, no netns) for the full
s1/s2/s3 matrix at 3 seeds × 3 arms, writes a demo log + report +
dashboard snapshot. Proves the scripted-demo pipeline end-to-end except the
kernel-privileged segment, which remains sudo-only (testbed/demo.sh).
"""
from __future__ import annotations
import argparse, json
from pathlib import Path
from aciq.experiment import ExperimentRunner, DryLauncher
from aciq.harness import Harness, SystemSpec, CapacityMode
from aciq.txn import FakeRunner
from aciq.metrics import StaticSource, CounterSnapshot
from aciq.model import TrafficClass

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', default='data/experiments/demo_dry_s1')
    ap.add_argument('--scenario', default='s1_iso_during_call')
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    log_lines = [f"demo(dry) scenario={a.scenario} rev=HEAD engine=post-7c6c7235"]
    # DryLauncher + FakeRunner: no kernel, no sudo
    import aciq.experiment as exp
    runner = ExperimentRunner(
        harness=Harness(runner=FakeRunner(auto_readback=True)),
        launcher=DryLauncher(),
        results_dir=out, real_time=False,
        source=StaticSource([CounterSnapshot(t=float(i)) for i in range(5)]),
    )
    for arm, mode in [(SystemSpec.B0, CapacityMode.STATIC),
                      (SystemSpec.B1, CapacityMode.STATIC),
                      (SystemSpec.ACIQ, CapacityMode.ADAPTIVE)]:
        for seed in (1100, 1101, 1102):
            res = runner.run(a.scenario, arm, mode, seed)
            log_lines.append(f"{a.scenario}__{arm.value}__{mode.value}__seed{seed}: "
                             f"est={getattr(res,'estimator_mbps',None)} commits={len(getattr(res,'policy_change_log',[]))}")
            print(log_lines[-1])
    (out / "demo_dry.log").write_text("\n".join(log_lines) + "\n")
    # Dashboard snapshot from first ACIQ samples
    from aciq.dashboard import write_snapshot
    first = sorted(out.glob("*aciq*seed1100*"))
    if first:
        rows = [json.loads(l) for l in (first[0] / "samples.jsonl").read_text().splitlines() if l.strip()]
        write_snapshot(rows, out / "dashboard.html", subtitle=f"demo(dry) {a.scenario} — no kernel, pipeline proof")
        (out / "provenance.json").write_text(json.dumps(
            {"scenario": a.scenario, "mode": "dry", "note": "Kernel-privileged segment remains sudo-only (testbed/demo.sh)"}, indent=2))
    print(f"demo(dry) done -> {out}/demo_dry.log")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
