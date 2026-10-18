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


def setup_testbed() -> bool:
    subprocess.run(["sudo", str(ROOT / "testbed" / "cleanup.sh")], check=False)
    r = subprocess.run([str(ROOT / "testbed" / "setup.sh")])
    return r.returncode == 0


def teardown() -> None:
    subprocess.run(["sudo", str(ROOT / "testbed" / "cleanup.sh")], check=False)


# All three scenarios from the brief. s2 needs --drop-at to be meaningful.
# s4 is the rising edge: without --recover-at/--recover-to it behaves like s2.
ALL_SCENARIOS = ["s1_iso_during_call", "s2_wan_drop", "s3_tv_and_gaming",
                 "s4_capacity_recovery"]
#: Scenarios that only do something interesting with an explicit drop time.
#: s4 needs it too -- there is no recovery without a drop first.
NEEDS_DROP_AT = {"s2_wan_drop", "s4_capacity_recovery"}
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
    ap.add_argument("--seeds", type=int, default=None,
                    help="run this many seeds starting at --seed, in one "
                         "invocation. The report needs >=6 paired runs before it "
                         "will emit a p-value, and one invocation means the "
                         "testbed is built and torn down once instead of per seed.")
    ap.add_argument("--link", type=float, default=100.0)
    ap.add_argument("--drop", type=float, default=20.0)
    ap.add_argument("--drop-at", type=float, default=None,
                    help="seconds into the run at which capacity drops")
    ap.add_argument("--recover-at", type=float, default=None,
                    help="seconds into the run at which the link is restored to "
                         "--recover-to. Tests the RISING edge of adaptation, "
                         "which no shipped scenario exercised: a controller that "
                         "cannot walk back up, or a policy left pinned at the "
                         "degraded rate, is invisible to a drop-only test.")
    ap.add_argument("--recover-to", type=float, default=None,
                    help="capacity to restore at --recover-at, in Mbps")
    ap.add_argument("--duration-s", type=float, default=None,
                    help="override each scenario's duration. The shipped "
                         "scenarios are 30-40s, which cannot demonstrate "
                         "stability; this is what makes a sustained soak "
                         "possible without editing the scenario table. "
                         "Omitted, each scenario keeps its own duration.")
    ap.add_argument("--settle", type=float, default=None,
                    help="seconds of interactive-only warmup before measurement "
                         "begins (default: the scenario's own settle time)")
    ap.add_argument("--dry-run", action="store_true",
                    help="build everything but do not wait for the run to finish")
    ap.add_argument("--no-setup", action="store_true",
                    help="assume namespaces already exist")
    ap.add_argument("--enforce", action="store_true",
                    help="apply per-flow classifications as tc flower filters "
                         "(ACIQ only; off by default so runs stay comparable "
                         "to the v0 baseline)")
    ap.add_argument("--lease", action="append", default=[], metavar="IP",
                    help="give this device an M7 lease for the whole run; "
                         "repeatable. Requires --enforce, since a baseline has "
                         "no classifier to honour a lease.")
    ap.add_argument("--lease-weight", type=float, default=0.5)
    ap.add_argument("--lease-ttl-s", type=float, default=None,
                    help="defaults to the whole run, so the measurement is of "
                         "the effect and not of the expiry")
    ap.add_argument("--results-dir", default=str(RESULTS_DIR))
    ap.add_argument("--no-stamp", action="store_true",
                    help="do not record the revision in the results "
                         "directory. Only for deliberately mixing evidence "
                         "from several revisions in one tree.")
    ap.add_argument("--report", default=None, help="write the Markdown report here")
    ap.add_argument("--observe", action="store_true",
                    help="record per-packet send/receive timestamps for every "
                         "latency probe, one JSON line per packet. Off by "
                         "default. Needed to diagnose a latency tail, because "
                         "a percentile says how slow the worst packets were but "
                         "not which they were or when they happened.")
    ap.add_argument("--report-only", action="store_true",
                    help="rebuild the report from existing artefacts and exit. "
                         "No testbed, no runs, no root-adjacent setup -- the "
                         "report is pure post-processing, so re-deriving it after "
                         "a reporting fix should not mean re-running an hour of "
                         "experiments.")
    args = ap.parse_args()

    # Ahead of every testbed step, including cleanup: rebuilding a report touches
    # nothing, and asking for it should not shell out to sudo.
    if args.report_only:
        out = Path(args.report) if args.report else ROOT / "data" / "REPORT.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(build_report(Path(args.results_dir)))
        print(f"report rebuilt from {args.results_dir} -> {out}")
        return 0

    if not args.no_setup:
        print("=== building testbed ===")
        if not setup_testbed():
            print("setup.sh failed; see its output above", file=sys.stderr)
            return 1
        print("=== testbed up ===")

    if args.duration_s is not None:
        # Replace rather than mutate: Scenario is a frozen-ish dataclass and
        # editing SCENARIOS in place would leak across scenarios.
        import dataclasses
        from aciq.harness import SCENARIOS
        for name, sc in list(SCENARIOS.items()):
            SCENARIOS[name] = dataclasses.replace(sc, duration_s=args.duration_s)
        print(f"note: scenario durations overridden to {args.duration_s}s",
              file=sys.stderr)

    if args.recover_at is not None and args.recover_to is None:
        print("note: --recover-at without --recover-to is a no-op; "
              "restoring to the same rate tests nothing", file=sys.stderr)
        args.recover_at = None

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
        launcher = NetnsLauncher(observe=args.observe)
        source = None
    runner = ExperimentRunner(
        launcher=launcher,
        harness=harness,
        results_dir=Path(args.results_dir),
        real_time=not args.dry_run,
        source=source,
    )

    # One seed unless --seeds was given. Kept as a list so the loop reads the same
    # either way, rather than branching inside the inner loop.
    # Stamp the results directory with the revision that produced it.
    #
    # This belongs here, in the producer, and not in tools/host_gate.sh: run
    # this script directly and the evidence had no revision at all, so the
    # acceptance check reported it as UNBOUND or, worse, attributed a stale
    # stamp left by an earlier orchestrator run to a run made with different
    # code. A run now identifies itself.
    if not args.no_stamp:
        try:
            import subprocess as _sp
            rev = _sp.run(["git", "rev-parse", "HEAD"],
                          cwd=ROOT, capture_output=True, text=True,
                          timeout=10).stdout.strip()
            if rev:
                rd = Path(args.results_dir)
                rd.mkdir(parents=True, exist_ok=True)
                (rd / "REVISION").write_text(rev + "\n")
                print(f"evidence stamped with revision {rev[:8]}")
        except (OSError, ValueError):
            pass

    seeds = ([args.seed] if not args.seeds
             else [args.seed + i for i in range(args.seeds)])

    try:
        for sc in scenarios:
            for sysspec in systems:
                m = mode if sysspec is SystemSpec.ACIQ else CapacityMode.STATIC
                for seed in seeds:
                    print(f"\n=== {sc} / {sysspec.value} / {m.value} / seed {seed} ===")
                    res = runner.run(
                        sc, sysspec, m, seed, args.link, args.drop, args.drop_at,
                        settle_s=args.settle, enforce=args.enforce,
                        recover_at_s=args.recover_at,
                        recover_to_mbps=args.recover_to,
                        lease_ips=args.lease, lease_weight=args.lease_weight,
                        lease_ttl_s=args.lease_ttl_s)
                    for n in res.notes:
                        # only real problems get a warning marker; a note like
                        # "no capacity drop" is informational and alarming it
                        # would make every successful run look like a failure
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
