#!/usr/bin/env python3
"""Run the ACIQ experiment matrix. Needs root.

  # full matrix: scenarios 1 and 3 against all three systems
  sudo ./run_experiments.py

  # one run, no waiting, to prove the plumbing before committing to 6 runs
  sudo ./run_experiments.py --scenario s1_iso_during_call --system aciq --dry-run

The testbed namespaces are built and torn down by testbed/setup.sh and
testbed/cleanup.sh. Every run writes its own directory under data/runs/.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from aciq.experiment import DryLauncher, ExperimentRunner, NetnsLauncher, RESULTS_DIR
from aciq.harness import CapacityMode, Harness, SystemSpec
from aciq.report import build_report
from aciq.txn import FakeRunner


def setup_testbed() -> bool:
    subprocess.run(["sudo", str(ROOT / "testbed" / "cleanup.sh")], check=False)
    r = subprocess.run([str(ROOT / "testbed" / "setup.sh")])
    return r.returncode == 0


def teardown() -> None:
    subprocess.run(["sudo", str(ROOT / "testbed" / "cleanup.sh")], check=False)


# All three scenarios from the brief. s2 needs --drop-at to be meaningful.
ALL_SCENARIOS = ["s1_iso_during_call", "s2_wan_drop", "s3_tv_and_gaming"]
#: Scenarios that only do something interesting with an explicit drop time.
NEEDS_DROP_AT = {"s2_wan_drop"}
ALL_SYSTEMS = [SystemSpec.B0, SystemSpec.B1, SystemSpec.ACIQ]


def main() -> int:
    ap = argparse.ArgumentParser(description="ACIQ+ experiment driver")
    ap.add_argument("--scenario", action="append", choices=ALL_SCENARIOS,
                    help="repeatable; omit to run the default matrix")
    ap.add_argument("--system", action="append",
                    choices=[s.value for s in ALL_SYSTEMS])
    ap.add_argument("--mode", default="adaptive",
                    choices=[m.value for m in CapacityMode])
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--link", type=float, default=100.0)
    ap.add_argument("--drop", type=float, default=20.0)
    ap.add_argument("--drop-at", type=float, default=None,
                    help="seconds into the run at which capacity drops")
    ap.add_argument("--settle", type=float, default=None,
                    help="seconds of interactive-only warmup before measurement "
                         "begins (default: the scenario's own settle time)")
    ap.add_argument("--dry-run", action="store_true",
                    help="build everything but do not wait for the run to finish")
    ap.add_argument("--no-setup", action="store_true",
                    help="assume namespaces already exist")
    ap.add_argument("--results-dir", default=str(RESULTS_DIR))
    ap.add_argument("--report", default=None, help="write the Markdown report here")
    args = ap.parse_args()

    if not args.no_setup:
        print("=== building testbed ===")
        if not setup_testbed():
            print("setup.sh failed; see its output above", file=sys.stderr)
            return 1
        print("=== testbed up ===")

    scenarios = args.scenario or ["s1_iso_during_call", "s3_tv_and_gaming"]
    if args.scenario and any(sc in NEEDS_DROP_AT for sc in args.scenario) \
            and args.drop_at is None:
        # Silently running s2 without a drop would produce a run that looks
        # complete but never exercised the thing the scenario is about.
        print(f"note: {'/'.join(NEEDS_DROP_AT)} needs --drop-at to be meaningful; "
              f"using the midpoint of the run", file=sys.stderr)
        args.drop_at = 30.0
    systems = [SystemSpec(s) for s in args.system] if args.system else ALL_SYSTEMS
    mode = CapacityMode(args.mode)

    # Mode applies to ACIQ. The baselines are run static: a static router does
    # not learn its link got slower, so telling it would not be a baseline.
    #
    # --dry-run must not touch the kernel at all: the launcher is faked AND the
    # harness runs against a FakeRunner that synthesises matching read-back, so
    # the whole sequencing can be exercised with neither root nor `ip`.
    if args.dry_run:
        from aciq.metrics import CounterSnapshot
        from aciq.txn import FakeRunner

        class NullSource:
            """Yields empty snapshots so a dry run never shells out to tc."""

            def snapshot(self):
                return CounterSnapshot(t=time.monotonic(), by_class={})

        harness = Harness(runner=FakeRunner(auto_readback=True))
        launcher = DryLauncher()
        source = NullSource()
    else:
        harness = Harness()
        launcher = NetnsLauncher()
        source = None
    runner = ExperimentRunner(
        launcher=launcher,
        harness=harness,
        results_dir=Path(args.results_dir),
        real_time=not args.dry_run,
        source=source,
    )

    try:
        for sc in scenarios:
            for sysspec in systems:
                m = mode if sysspec is SystemSpec.ACIQ else CapacityMode.STATIC
                print(f"\n=== {sc} / {sysspec.value} / {m.value} / seed {args.seed} ===")
                res = runner.run(
                    sc, sysspec, m, args.seed, args.link, args.drop, args.drop_at,
                    settle_s=args.settle)
                for n in res.notes:
                    # only real problems get a warning marker; a note like
                    # "no capacity drop" is informational and alarming it would
                    # make every successful run look like a failure
                    warn = "failed" in n.lower() or "error" in n.lower()
                    print(f"    {'!' if warn else '  '} {n}")
                print(f"    estimator={res.estimator_mbps} "
                      f"policy_changes={res.policy_changes}")
    finally:
        if not args.no_setup:
            print("\n=== tearing down testbed ===")
            teardown()

    out = Path(args.report) if args.report else ROOT / "data" / "REPORT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_report(Path(args.results_dir)))
    print(f"\nreport written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
