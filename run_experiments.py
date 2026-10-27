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
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from aciq.experiment import DryLauncher, ExperimentRunner, NetnsLauncher, RESULTS_DIR
from aciq.harness import CapacityMode, Harness, SystemSpec
from aciq.report import build_report


def _safe_sudo(cmd: str) -> int | None:
    """Run a testbed script, shell-free. Retuning 0 root needs no sudo and some
    sandboxes have no sudo BINARY: root runs it directly, a missing sudo binary
    in a non-root dev shell returns None so a dry run can still happen."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return subprocess.run([cmd], check=False).returncode
    try:
        return subprocess.run(["sudo", cmd], check=False).returncode
    except FileNotFoundError:
        print(f"note: no sudo and not root; skipped {Path(cmd).name}",
              file=sys.stderr)
        return None


def setup_testbed() -> bool:
    _safe_sudo(str(ROOT / "testbed" / "cleanup.sh"))
    r = subprocess.run([str(ROOT / "testbed" / "setup.sh")])
    return r.returncode == 0


def teardown() -> None:
    _safe_sudo(str(ROOT / "testbed" / "cleanup.sh"))


# All three scenarios from the brief. s2 needs --drop-at to be meaningful.
# s4 is the rising edge: without --recover-at/--recover-to it behaves like s2.
# s6 is the intent scenario: --api-intent requested at t~1, TTL inside the run.
ALL_SCENARIOS = ["s1_iso_during_call", "s2_wan_drop", "s3_tv_and_gaming",
                 "s4_capacity_recovery", "s6_intent_expire",
                 "s2b_step_50", "s2b_step_10", "s2b_step_up_20to100",
                 "s2b_ramp_100to30",
                 "s7_up_20to60", "s7_up_30to100", "s7_rampup_30to100",
                 "s7_down_100to15", "s7_down_100to8", "s3_stress"]
#: Scenarios that only do something interesting with an explicit drop time.
#: s4 needs it too -- there is no recovery without a drop first.
NEEDS_DROP_AT = {"s2_wan_drop", "s4_capacity_recovery"}
#: S2b (declared docs/evidence/s2b-params.md): the link protocol is part of
#: the scenario, fixed before the S2b dataset exists. Overrides for these
#: names are refused rather than half-honoured, so nothing can drift back
#: into exactly the tuning the scenarios exist to avoid.
S2B_PROTOCOLS: dict[str, dict[str, float]] = {
    "s2b_step_50": {"link_mbps": 100.0, "drop_mbps": 50.0, "drop_at_s": 10.0},
    "s2b_step_10": {"link_mbps": 100.0, "drop_mbps": 10.0, "drop_at_s": 10.0},
    "s2b_step_up_20to100": {"link_mbps": 20.0, "drop_mbps": 20.0,
                            "drop_at_s": 10.0, "recover_at_s": 10.0,
                            "recover_to_mbps": 100.0},
    "s2b_ramp_100to30": {"link_mbps": 100.0, "ramp_at_s": 10.0,
                         "ramp_duration_s": 20.0, "ramp_to_mbps": 30.0},
}
#: Round 3 (declared docs/evidence/round3-params.md, task 5): the DEV-band
#: shapes. Same refusal semantics as S2B: the protocol is part of the
#: scenario and user flags may not override it.
S7_PROTOCOLS: dict[str, dict[str, float]] = {
    "s7_up_20to60": {"link_mbps": 20.0, "drop_mbps": 20.0, "drop_at_s": 10.0,
                     "recover_at_s": 10.0, "recover_to_mbps": 60.0},
    "s7_up_30to100": {"link_mbps": 30.0, "drop_mbps": 30.0, "drop_at_s": 10.0,
                      "recover_at_s": 10.0, "recover_to_mbps": 100.0},
    "s7_rampup_30to100": {"link_mbps": 30.0, "ramp_at_s": 10.0,
                          "ramp_duration_s": 20.0, "ramp_to_mbps": 100.0},
    "s7_down_100to15": {"link_mbps": 100.0, "drop_mbps": 15.0, "drop_at_s": 10.0},
    "s7_down_100to8": {"link_mbps": 100.0, "drop_mbps": 8.0, "drop_at_s": 10.0},
}
#: Every scenario name whose link protocol is part of the scenario.
SCENARIO_PROTOCOLS: dict[str, dict[str, float]] = {**S2B_PROTOCOLS,
                                                   **S7_PROTOCOLS}
ALL_SYSTEMS = [SystemSpec.B0, SystemSpec.B1, SystemSpec.B1_ORACLE,
               SystemSpec.B1_CONS, SystemSpec.B1_AUTO, SystemSpec.ACIQ]


def expected_s5_note(note: str) -> bool:
    """True for the S5(c) ARMED note: its word "failed" NAMES the injection
    being exercised. The driver that deletes a run dir on a "failed" note
    must not delete the very evidence S5(c) exists to produce; judging the
    armed run (rollback replayed, run continued) is verify_s5c's job on the
    artefacts. The NOT-armed counterpart is absent here on purpose: it means
    the injection silently did nothing, which stays a failure."""
    return "ARMED at t=" in note


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
    ap.add_argument("--link", type=float, default=None)
    ap.add_argument("--drop", type=float, default=None)
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
    ap.add_argument("--ramp-at", type=float, default=None,
                    help="S2b ramp: run time (s) the link starts moving")
    ap.add_argument("--ramp-duration", type=float, default=None,
                    help="S2b ramp: seconds over which the link moves from "
                         "--link to --ramp-to, linearly")
    ap.add_argument("--ramp-to", type=float, default=None,
                    help="S2b ramp: the link's final capacity, in Mbps")
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
    ap.add_argument("--inject-fail-apply", action="store_true",
                    help="S5 failure injection: ACIQ runs get one tc apply "
                         "forced to fail at mid-run; rollback must restore")
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
    ap.add_argument("--api-intent", action="store_true",
                    help="S6: request one intent through the real API surface "
                         "(IntentService, POST /intent) at --intent-at for "
                         "ACIQ runs; baselines declare no intent support")
    ap.add_argument("--intent-at", type=float, default=10.0,
                    help="run time (s) when the API intent is requested "
                         "(default 10.0: the s6 protocol declared in "
                         "docs/evidence/task3-params.md -- the bulk stream "
                         "is in steady state before the grant fires)")
    ap.add_argument("--intent-ttl", type=float, default=20.0,
                    help="intent TTL (s). Default 20.0 on the 60 s scenario: "
                         "the TTL expires at t~=30 INSIDE the run, leaving a "
                         "full third of post-expiry evidence for the "
                         "auto-revert and the recovery window")
    ap.add_argument("--intent-weight", type=float, default=0.5)
    ap.add_argument("--intent-label", default="game",
                    help="which workload's device the intent reserves for "
                         "(default: game)")
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
        # A SIGTERM/SIGINT'd run must leave NO kernel residue: force the safe
        # tree and tear down bridge filters on the way out, the same contract
        # the gate proves with its own probe (gate7 p8). The watchdog is the
        # only thing between a KILLING signal and leftover flower filters on
        # the live testbed, so it is armed before anything touches tc.
        from aciq.watchdog import Watchdog
        from aciq.bridge import Bridge

        def _force_safe_exit() -> None:
            try:
                harness.txn.force_safe()
            except Exception:
                pass                # teardown of the bridge is the residue that matters
            try:
                Bridge(dev="veth-lan", in_if="veth-wan",
                       ns="router").teardown()
            except Exception:
                pass

        Watchdog(safe_fn=_force_safe_exit).install()
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

    # Resolve the defaults that were flags with implicit values, so an
    # explicitly-passed --link/--drop can be told apart from the default
    # when a scenario's declared protocol must win (S2b).
    # S2b scenarios run their DECLARED link protocol (docs/evidence/
    # s2b-params.md), which the user's --link/--drop flags must not override:
    # a quietly retuned protocol would be exactly the tuning S2b exists to
    # avoid. The check runs on the RAW flags (None unless explicitly given),
    # so an s2b step that passes neither flag cannot be accused of
    # overriding the protocol with the base scenarios' defaults.
    for sc in scenarios:
        proto = SCENARIO_PROTOCOLS.get(sc)
        if proto is None:
            continue
        conflicts = []
        if args.link is not None and args.link != proto.get("link_mbps"):
            conflicts.append(f"--link {args.link}")
        if "drop_mbps" in proto and args.drop is not None \
                and args.drop != proto["drop_mbps"]:
            conflicts.append(f"--drop {args.drop}")
        if conflicts:
            ap.error(f"{sc} runs its declared protocol "
                     f"{proto}; refusing override: {', '.join(conflicts)}")
    args.link = 100.0 if args.link is None else args.link
    args.drop = 20.0 if args.drop is None else args.drop

    # A failed run must not be reported as a finished step: the pipeline's
    # resume markers once let an aborted intent step march on silently
    # (the driver recorded the dead run and returned 0).
    warned: list[str] = []

    try:
        for sc in scenarios:
            for sysspec in systems:
                # The adaptive-CAKE baseline (round 3) runs the ADAPTIVE
                # loop: it exists so the engine's decision chain meets a
                # different queue discipline, so a static run of it would
                # not be the declared arm.
                m = (mode if sysspec in (SystemSpec.ACIQ, SystemSpec.B1_AUTO)
                     else CapacityMode.STATIC)
                for seed in seeds:
                    print(f"\n=== {sc} / {sysspec.value} / {m.value} / seed {seed} ===")
                    proto = SCENARIO_PROTOCOLS.get(sc) or {}
                    run_link = proto.get("link_mbps", args.link)
                    run_drop = proto.get("drop_mbps", args.drop)
                    run_drop_at = proto.get("drop_at_s", args.drop_at)
                    run_recover_at = proto.get("recover_at_s", args.recover_at)
                    run_recover_to = proto.get("recover_to_mbps",
                                               args.recover_to)
                    run_ramp_at = proto.get("ramp_at_s", args.ramp_at)
                    run_ramp_dur = proto.get("ramp_duration_s",
                                             args.ramp_duration)
                    run_ramp_to = proto.get("ramp_to_mbps", args.ramp_to)
                    res = runner.run(
                        sc, sysspec, m, seed, run_link, run_drop, run_drop_at,
                        settle_s=args.settle, enforce=args.enforce,
                        initial_link_mbps=run_link,
                        recover_at_s=run_recover_at,
                        recover_to_mbps=run_recover_to,
                        ramp_at_s=run_ramp_at,
                        ramp_duration_s=run_ramp_dur,
                        ramp_to_mbps=run_ramp_to,
                        lease_ips=args.lease, lease_weight=args.lease_weight,
                        lease_ttl_s=args.lease_ttl_s,
                        inject_fail_apply=args.inject_fail_apply,
                        api_intent=args.api_intent,
                        intent_at_s=args.intent_at,
                        intent_ttl_s=args.intent_ttl,
                        intent_weight=args.intent_weight,
                        intent_label=args.intent_label)
                    for n in res.notes:
                        # only real problems get a warning marker; a note like
                        # "no capacity drop" is informational and alarming it
                        # would make every successful run look like a failure
                        warn = (("failed" in n.lower() or "error" in n.lower())
                                and not expected_s5_note(n))
                        if warn:
                            print(f"    ! {n}")
                            warned.append(n)
                            dead = runner.run_paths(sc, sysspec, mode, seed).root
                            shutil.rmtree(dead, ignore_errors=True)
                            print(f"    (removed incomplete run dir {dead})")
                        else:
                            print(f"      {n}")
                    print(f"    estimator={res.estimator_mbps} "
                          f"policy_changes={res.policy_changes}")
    finally:
        if not args.no_setup:
            print("\n=== tearing down testbed ===")
            teardown()

    out = Path(args.report) if args.report else ROOT / "data" / "REPORT.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    if warned and (not Path(args.results_dir).exists()
                   or not any(Path(args.results_dir).iterdir())):
        print(f"\nno runs succeeded; report NOT written (would clobber {out})")
        return 1
    out.write_text(build_report(Path(args.results_dir)))
    print(f"\nreport written to {out}")
    return 1 if warned else 0


if __name__ == "__main__":
    raise SystemExit(main())
