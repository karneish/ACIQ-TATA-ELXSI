"""M6 execution layer — drives real namespaces, generators and sampling.

`Harness` (aciq.harness) holds the control logic and is testable without root.
This module is the thin layer that actually touches the machine: it launches
generators inside namespaces, samples counters on a timer, and writes run
artefacts. The launcher and the runner are injected so the sequencing can be
tested with a dry-run launcher.

Layout of one run:

    data/runs/<scenario>__<system>__<mode>__seed<seed>/
        config.json     scenario, system, mode, seed, link capacities
        samples.jsonl   one MetricsFrame per tick
        workloads.json  each generator's own self-measured report
        result.json     RunResult summary
        verdict.json    M10's comparison against the other systems
"""

from __future__ import annotations

import json
import os
import shutil
import signal
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path

from .flowtrack import ConntrackSource, FlowTracker
from .harness import SCENARIOS, CapacityMode, Harness, RunResult, SystemSpec
from .metrics import EvaluationData, MetricsCollector, TextClassSource
from .model import TrafficClass
from .policy import floor_mbps

WORKLOAD_DIR = Path(__file__).resolve().parent.parent / "testbed" / "workloads"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "data" / "runs"

NS_CLIENT = "client"
NS_WAN = "wan"
NS_ROUTER = "router"
CLIENT_IP = "10.0.1.2"

#: DSCP EF per workload kind, matching SCENARIOS.
DSCP_BY_KIND = {"call": 46, "game": 46, "video": None, "bulk": None}


class DryLauncher:
    """Records what would run, executes nothing. Used by tests and --dry-run.

    Implements the same surface as NetnsLauncher so sequencing can be asserted
    without spawning anything.
    """

    def __init__(self):
        self.commands: list[list[str]] = []
        self.sinks: list[list[str]] = []
        self.sources: list[list[str]] = []

    def spawn_sink(self, kind: str, port: int, log_path: Path) -> None:
        self.sinks.append([kind, str(port)])
        self.commands.append([kind, "--listen", str(port)])

    def spawn_source(self, kind: str, dst: str, port: int, duration: float,
                     dscp: int | None, json_out: Path, log_path: Path) -> None:
        self.sources.append([kind, dst, str(port)])
        self.commands.append([kind, dst, str(port)])

    def collect(self) -> list:
        return []

    def stop(self) -> None:
        pass


class NetnsLauncher:
    """Runs real generator processes inside namespaces."""

    def __init__(self, python: str = "python3", ns_client: str = NS_CLIENT,
                 ns_wan: str = NS_WAN, out_dir: Path | None = None):
        self.python = python
        self.ns_client = ns_client
        self.ns_wan = ns_wan
        self.out_dir = out_dir
        self.procs: list[subprocess.Popen] = []
        self.logs: list[Path] = []

    def _argv(self, ns: str, script: str, *args: str) -> list[str]:
        return ["ip", "netns", "exec", ns, self.python,
                str(WORKLOAD_DIR / script), *args]

    def spawn_sink(self, kind: str, port: int, log_path: Path) -> subprocess.Popen:
        """Receiving end, always in the client namespace (the 'household')."""
        p = subprocess.Popen(
            self._argv(self.ns_client, f"{kind}.py", "--listen", "--port", str(port)),
            stdout=open(log_path, "w"), stderr=subprocess.STDOUT,
            start_new_session=True)
        self.procs.append(p)
        return p

    def spawn_source(self, kind: str, dst: str, port: int, duration: float,
                     dscp: int | None, json_out: Path, log_path: Path) -> subprocess.Popen:
        """Sending end, always in the wan namespace (the 'internet')."""
        argv = self._argv(self.ns_wan, f"{kind}.py", "--dst", dst,
                          "--port", str(port), "--duration", str(duration),
                          "--json-out", str(json_out))
        if dscp is not None:
            argv += ["--dscp", str(dscp)]
        p = subprocess.Popen(argv, stdout=open(log_path, "w"),
                             stderr=subprocess.STDOUT, start_new_session=True)
        self.procs.append(p)
        return p

    def collect(self) -> list[tuple[str, str]]:
        """Wait for every sender to finish and return its JSON report."""
        out = []
        for p in self.procs:
            try:
                p.wait(timeout=90)
            except subprocess.TimeoutExpired:
                p.kill()
        return out

    def stop(self) -> None:
        for p in self.procs:
            if p.poll() is None:
                try:
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
                except (ProcessLookupError, PermissionError):
                    p.kill()
        self.procs.clear()


@dataclass
class RunPaths:
    root: Path

    def file(self, name: str) -> Path:
        return self.root / name

    def write_json(self, name: str, obj) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self.root.joinpath(name).write_text(json.dumps(obj, indent=2, default=str))

    def write_jsonl(self, name: str, rows: list[dict]) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        with self.root.joinpath(name).open("w") as f:
            for r in rows:
                f.write(json.dumps(r, default=str) + "\n")


class ExperimentRunner:
    """Runs one scenario against one system and records everything."""

    def __init__(
        self,
        launcher=None,
        harness: Harness | None = None,
        results_dir: Path = RESULTS_DIR,
        tick_s: float = 1.0,
        real_time: bool = True,
        source=None,
        bridge_executor=None,
    ):
        self.launcher = launcher or NetnsLauncher()
        self.harness = harness or Harness()
        self.results_dir = results_dir
        self.tick_s = tick_s
        self.real_time = real_time
        #: counter source; injectable so a dry run never shells out to `tc`
        self.source = source
        #: bridge executor, injectable for the same reason. Without it, exercising
        #: the enforcement path in a test means running `tc` for real.
        self.bridge_executor = bridge_executor
        #: Per-flow enforcement. Off unless `enforce=True` is passed to run();
        #: see aciq/closedloop.py for why it is not simply always on.
        self.enforce = False
        self._tracker: FlowTracker | None = None
        self._ct: ConntrackSource | None = None
        #: Enforcement health. Watched because ConntrackSource.read() swallows
        #: every error and returns "", so a broken conntrack read, a wrong
        #: namespace and flows that never cross the shaped device all look
        #: exactly like an idle link.
        #:
        #: `_enf_steered` counts ticks where a verdict reached the kernel. That is
        #: the only number that answers the question that matters -- a tick that
        #: saw four flows and declined all four (they were too young) did no work
        #: either, and counting it would let a run look healthy on the strength of
        #: having looked at traffic.
        self._enf_ticks = 0
        self._enf_steered = 0

    def run_paths(self, scenario: str, system: SystemSpec, mode: CapacityMode,
                  seed: int) -> RunPaths:
        stem = f"{scenario}__{system.value}__{mode.value}__seed{seed}"
        return RunPaths(self.results_dir / stem)

    def run(
        self,
        scenario_name: str,
        system: SystemSpec,
        mode: CapacityMode = CapacityMode.ADAPTIVE,
        seed: int = 42,
        link_mbps: float = 100.0,
        drop_mbps: float = 20.0,
        drop_at_s: float | None = None,
        settle_s: float | None = None,
        enforce: bool = False,
    ) -> RunResult:
        self.enforce = enforce
        sc = SCENARIOS[scenario_name]
        # A settle period lets the link reach steady state before anything is
        # measured. Without it the first packets of the run race a flooding bulk
        # transfer, which produced a 19 ms p99 outlier against cake's 1.5 ms.
        settle = sc.settle_s if settle_s is None else settle_s
        paths = self.run_paths(scenario_name, system, mode, seed)
        # Remove any previous artefacts for this run. A stale result.json from a
        # failed attempt would otherwise be compared against a fresh one and
        # reported as if both were real.
        if paths.root.exists():
            shutil.rmtree(paths.root, ignore_errors=True)
        paths.root.mkdir(parents=True, exist_ok=True)

        # ---- 1b (decision only). Whether enforcement engages is pure logic, and
        # ---- it is decided *before* config.json so the config can record it.
        #      The action -- touching the kernel -- happens after the tree is
        #      built, in step 1c.
        #
        #  Three ways it does not engage, each with its reason recorded:
        #
        #  * not requested -- the default, and what keeps runs comparable to the
        #    v0 baseline.
        #  * a baseline system -- it has no classifier to apply, and steering a
        #    baseline's traffic would not make the comparison unfair, it would
        #    make it meaningless: it would no longer be a baseline.
        #  * a dry run -- nothing is launched, so conntrack reports no flows and
        #    the loop would decide nothing. A run that looks wired up while
        #    measuring nothing is worse than one that plainly is not.
        # Reset per run, not per process. These were only ever initialised in
        # __init__, so a runner that executed several runs accumulated them:
        # `1/31`, `2/62`, `3/93` ... `18/678` across one 18-run matrix. Two
        # consequences, the second serious -- the note described the whole
        # process rather than the run, and because _enf_steered never returned to
        # zero, the "STEERED NOTHING" guard could not fire after the first
        # successful run. The net built to catch a silent no-op was blind from
        # run 2 onwards.
        self._enf_ticks = 0
        self._enf_steered = 0
        #: When M2 last produced a *new* reading, and when the link was last
        #: reconfigured. Their comparison decides whether the final estimate
        #: describes the end of the run or a moment before it changed.
        self._est_t: float | None = None
        self._cap_t: float | None = None
        enforcement_why = "not requested"
        will_enforce = False
        if self.enforce:
            if system is not SystemSpec.ACIQ:
                enforcement_why = f"{system.value} is a baseline, not ACIQ"
            elif isinstance(self.launcher, DryLauncher):
                enforcement_why = "dry run launches no traffic"
            else:
                will_enforce = True

        # ---- config, written before anything runs so a crashed run is
        # ---- still reproducible from its artefacts
        ports = sc.seed_workloads(seed)
        cfg = {
            "scenario": sc.name, "system": system.value, "mode": mode.value,
            "seed": seed, "link_mbps": link_mbps, "drop_mbps": drop_mbps,
            "drop_at_s": drop_at_s, "duration_s": sc.duration_s,
            "settle_s": settle,
            "workloads": [{"kind": w.kind, "label": w.label, "dscp": w.dscp}
                          for w in sc.workloads],
            "ports": [{"label": lbl, "port": p, "dscp": d} for lbl, p, d in ports],
            "floor_mbps": floor_mbps(link_mbps),
            # Written because config.json is the artefact that has to say what a
            # run actually did. A sample records the verdicts, but without this
            # an enforced run and a reporting-only run are indistinguishable
            # until you read every sample line -- and "did this run enforce?" is
            # the first question anyone asks of a new result.
            # What was asked for, and why it may not engage. Whether it
            # *actually* engaged is not knowable yet -- the tree is not built --
            # so it is recorded in result.json instead, where it is a fact
            # rather than a prediction.
            "enforce_requested": bool(self.enforce),
            "enforcement_note": enforcement_why,
        }
        paths.write_json("config.json", cfg)

        # ---- 1. build the system tree at the starting capacity.
        # Full reset first: runs must not inherit the previous run's dwell
        # window, or run 2's opening policy change is vetoed as rate-limited.
        self.harness.reset_for_run()
        self.harness.set_lease(None, link_mbps)
        if not self.harness.apply_system(system, link_mbps):
            # Surface *why*. A bare "failed" is useless in a log.
            res = RunResult(sc.name, system.value, mode.value, seed,
                            link_mbps, link_mbps,
                            notes=[f"apply_system failed: {self.harness.txn.last_reason}"])
            paths.write_json("result.json", json.loads(res.to_json()))
            self.launcher.stop()
            return res

        # ---- 1c. perform the opt-in decided in 1b
        enforcement_on = False
        if will_enforce:
            self.harness.enable_enforcement(
                capacity_mbps=self.harness._estimator.current.mbps or link_mbps,
                executor=self.bridge_executor)
            self._tracker = FlowTracker()
            self._ct = ConntrackSource(ns=self.harness.ns)
            enforcement_on = self.harness.enforcement_enabled
            if not enforcement_on:
                enforcement_why = "harness declined to enable enforcement"

        # ---- 2. launch workloads: sinks first so nothing races the listener
        for (label, port, dscp), w in zip(ports, _expand(sc)):
            self.launcher.spawn_sink(w.kind, port, paths.file(f"{label}.sink.log"))
        # Sinks need a moment to bind. Without this the first sender races the
        # listener and dies with "connection refused", which is exactly what the
        # first real run showed for the bulk workload.
        time.sleep(1.0 if self.real_time else 0)

        # ---- 2b. settle, with measurement OFF
        #
        # Only interactive workloads run during the settle phase. If bulk runs
        # too, the transient being avoided is the one bulk causes, and settling
        # would just be hiding the effect we want to measure. Each system
        # therefore experiences the same starting condition.
        if settle > 0:
            self._settle(paths, ports, sc, settle)

        for (label, port, dscp), w in zip(ports, _expand(sc)):
            self.launcher.spawn_source(
                w.kind, CLIENT_IP, port, sc.duration_s, w.dscp,
                paths.file(f"{label}.json"), paths.file(f"{label}.log"))

        # ---- 3. sample
        # Text first: verified by gate check 10. The JSON reader silently
        # returned empty on this host and made every sample come back as
        # `per_class: {}`.
        collector = MetricsCollector(
            self.source or TextClassSource(dev=self.harness.dev, ns=self.harness.ns))
        samples: list[dict] = []
        _prev_est = self.harness._estimator.current.mbps
        t0 = time.monotonic()
        ticks = int(sc.duration_s / self.tick_s) + 1
        dropped = False
        for i in range(ticks):
            now = time.monotonic()
            if self.real_time:
                time.sleep(self.tick_s)
            # A dry run must still advance the *scenario* timeline, otherwise
            # drop_at_s can never be reached and the drop path goes untested.
            elapsed = (now - t0) if self.real_time else i * self.tick_s
            frame = collector.poll()

            # Close the loop on every tick. M2 needs consecutive saturated
            # samples before it trusts a reading, so a loop that only ran at a
            # capacity drop and once at the end could never reach its streak and
            # the estimate stayed 0.0 for the whole run.
            if mode is CapacityMode.ADAPTIVE:
                self._closed_loop_step(collector, self.tick_s, t0 + elapsed)
            verdicts = (self._enforcement_step(ports, t0 + elapsed)
                        if enforcement_on else {})
            # Note when M2 last moved. A run whose only reading predates the drop
            # reports that pre-drop number as "the estimator" alongside
            # link_end=20 -- the matrix showed 102.77 Mbps for a 20 Mbps link.
            if self.harness._estimator.current.mbps != _prev_est:
                _prev_est = self.harness._estimator.current.mbps
                self._est_t = elapsed

            lk = collector.last_link_counters()
            samples.append({
                "t": round(elapsed, 2),
                "per_class": {k.value: vars(v) for k, v in frame.per_class.items()},
                # The link (parent class) counters, which are the ONLY thing
                # M2 treats as saturation. Recorded explicitly so a wrong
                # estimate can be diagnosed from the artefact alone.
                # cls is None and handle carries the classid: the parent is 1:1,
                # and labelling it "realtime_interactive" put a wrong class name
                # on every sample of every system.
                "link": vars(lk) if lk is not None else None,
                "estimator_saturated": self.harness._estimator.current.saturated,
                "fairness": frame.fairness,
                "cpu_fraction": frame.cpu_fraction,
                "capacity_mbps": self.harness._estimator.current.mbps,
                # What each workload was steered to this tick, if enforcement is
                # on. Recorded per sample so the artefact shows the decision and
                # its timing, rather than asking the reader to trust the code.
                "verdicts": verdicts,
            })

            # the drop: the link changes, and only the link changes
            if drop_at_s is not None and not dropped and elapsed >= drop_at_s:
                dropped = True
                self._cap_t = elapsed
                # Only the link changes. Baselines are not told; ACIQ must
                # notice from counters alone.
                self.harness.set_capacity(drop_mbps)
                if mode is CapacityMode.INFORMED:
                    # the oracle variant is handed the new capacity outright
                    self.harness.apply_system(system, drop_mbps)

        # ---- 4. collect the generators' own measurements
        self.launcher.collect()
        workloads = {}
        for (label, port, dscp), _w in zip(ports, _expand(sc)):
            f = paths.file(f"{label}.json")
            if f.exists():
                try:
                    workloads[label] = json.loads(f.read_text())
                    collector.ingest(EvaluationData(
                        t=time.monotonic(), label=label,
                        rtt_ms=workloads[label].get("p50"),
                        jitter_ms=workloads[label].get("jitter_ms"),
                        loss_ratio=workloads[label].get("loss_ratio")))
                except json.JSONDecodeError:
                    workloads[label] = {"error": "unparseable report"}
        self.launcher.stop()

        # Remove every filter before returning. A run that leaves filters behind
        # steers the next run's traffic before it has decided anything -- which
        # is the residue gate check 20 exists to catch, and the reason
        # enforcement cannot be a write-and-forget.
        enforcement_note = self._enforcement_note(enforcement_on, enforcement_why)
        if enforcement_on:
            self.harness.disable_enforcement()
            self._tracker = self._ct = None

        paths.write_jsonl("samples.jsonl", samples)
        paths.write_json("workloads.json", workloads)

        # ---- 5. the loop has already run on every tick
        est = self.harness._estimator.current.mbps or None
        # M2 can only measure a link that is oversubscribed. When the link drops
        # and the workload's own rate falls with it, the link stops being
        # oversubscribed, so there is no longer any information in the counters
        # about capacity -- and the last reading, taken before the drop, is
        # carried to the end of the run as if it described it. Saying so is the
        # difference between a stale estimate and a wrong one presented as
        # current.
        stale_note = self._stale_note(est)
        res = RunResult(
            scenario=sc.name, system=system.value, capacity_mode=mode.value,
            seed=seed, link_start_mbps=link_mbps,
            link_end_mbps=drop_mbps if dropped else link_mbps,
            estimator_mbps=round(est, 2) if est else None,
            samples=samples[-3:],
            policy_changes=self.harness.policy_changes,
            notes=(([] if dropped else ["no capacity drop in this run"])
                   + ([stale_note] if stale_note else [])
                   + [enforcement_note]),
        )
        paths.write_json("result.json", json.loads(res.to_json()))
        return res

    def _enforcement_step(self, ports, now: float) -> dict[str, dict]:
        """One enforcement tick: observe flows, classify, steer.

        Reads conntrack rather than anything the workload knows about itself, so
        the decision rests on observed counters. The workload labels are used
        only to decide which tracked flows belong to this run -- never as a
        classification input. `dscp` is deliberately not forwarded to the
        classifier: the DSCP-EF path is the v0 baseline mechanism, and feeding it
        in here would let the new per-flow path be credited with a shortcut it
        did not take.
        """
        assert self._tracker is not None and self._ct is not None
        try:
            text = self._ct.read()
        except Exception:
            # Losing one poll must not kill the run; the next tick re-reads.
            return {}
        self._tracker.observe(text, now)
        self._enf_ticks += 1

        # Port -> label. The dport is the join key: it is what the generator
        # chose and what conntrack reports, and unlike the source port it does
        # not change on reconnect.
        want = {p: lbl for lbl, p, _d in ports}
        out: dict[str, dict] = {}
        for flow in self._tracker.flows():
            label = want.get(flow.dport)
            if label is None:
                continue
            f = self._tracker.features(flow.key)
            if f is None:
                continue
            v = self.harness.enforce(f, now=now)
            if v is None:
                continue
            out[label] = {
                "class": v.label, "confidence": round(v.classification.confidence, 2),
                "tier": v.classification.tier, "corrected": v.corrected,
                "changed": v.changed,
            }
        if any(v["changed"] for v in out.values()):
            self._enf_steered += 1
        return out

    def _stale_note(self, est: float | None) -> str:
        """Say when the final estimate predates the last capacity change.

        M2 can only measure a link that is oversubscribed. When the link drops
        and the workload's own rate falls with it, the link stops being
        oversubscribed, so there is no longer any information in the counters
        about capacity -- and the last reading, taken before the drop, is carried
        to the end of the run as if it described it. The matrix reported
        estimator=102.77 Mbps beside link_end=20.0 for twelve runs.

        Naming it stale is the difference between an old number and a wrong number
        presented as current.
        """
        if not est or self._cap_t is None or self._est_t is None:
            return ""
        if self._est_t >= self._cap_t:
            return ""
        return (f"estimator {est:.1f} Mbps is STALE: last measured at "
                f"t={self._est_t:.1f}s, before the link changed at "
                f"t={self._cap_t:.1f}s. M2 only measures an oversubscribed link, "
                f"and this one stopped being oversubscribed once the workload's "
                f"rate fell with it, so no post-drop reading was possible")

    def _enforcement_note(self, enforcement_on: bool, why: str) -> str:
        """One line, in result.json, saying what enforcement actually did.

        The check that stops a broken conntrack read from reading as a working
        one. Enforcement can be "on", install nothing, and still produce a run
        that looks fine -- so if it never classified a single flow the run says
        so in those words, instead of leaving a reader to infer health from the
        presence of the word "enforcement".
        """
        if not enforcement_on:
            return f"per-flow enforcement OFF ({why})"
        if self._enf_ticks and not self._enf_steered:
            return (f"per-flow enforcement ON but STEERED NOTHING on any of "
                    f"{self._enf_ticks} ticks -- conntrack produced no usable "
                    f"flows, or no flow was mature enough to classify. This run "
                    f"measures the reporting path, not enforcement.")
        if self._enf_steered < self._enf_ticks:
            return (f"per-flow enforcement ON ({self._enf_steered}/{self._enf_ticks} "
                    f"ticks changed a filter)")
        return "per-flow enforcement ON"

    def _settle(self, paths: RunPaths, ports, sc, settle_s: float) -> None:
        """Run interactive workloads only, and record nothing.

        The point is to let the shaping tree and the interactive path reach
        steady state before bulk arrives. Only interactive traffic runs, so the
        transient being avoided is not simply deferred: each system starts from
        the same condition, and bulk still arrives during the measured window.

        Settle output is written under a `_settle_` prefix and deleted, so a
        settle can never be mistaken for a measurement.
        """
        interactive = [(lbl, p, w.kind) for (lbl, p, _d), w
                       in zip(ports, _expand(sc)) if w.kind in ("call", "game")]
        scratch = paths.root / "_settle"
        scratch.mkdir(parents=True, exist_ok=True)
        for label, port, kind in interactive:
            self.launcher.spawn_source(
                kind, CLIENT_IP, port, settle_s, DSCP_BY_KIND.get(kind),
                scratch / f"{label}.json", scratch / f"{label}.log")
        warm = MetricsCollector(
            self.source or TextClassSource(dev=self.harness.dev, ns=self.harness.ns))
        for _ in range(max(1, int(settle_s / self.tick_s))):
            if self.real_time:
                time.sleep(self.tick_s)
            warm.poll()
        shutil.rmtree(scratch, ignore_errors=True)

    def _closed_loop_step(self, collector: MetricsCollector, dt: float, now: float):
        """M2 -> M3 -> M4, using only what the counter reader sees."""
        return self.harness.adapt_step(
            _counters_from_last_frame(collector), dt=dt, now=now,
            link=collector.last_link_counters())


def _counters_from_last_frame(collector: MetricsCollector):
    return collector.last_counters()


def _expand(sc):
    """One entry per (label, port) pair, matching seed_workloads' order."""
    out = []
    for w in sc.workloads:
        for _ in range(w.count):
            out.append(w)
    return out
