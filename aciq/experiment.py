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
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .bridge import count_flow_filters_text, enumerate_flow_filters
from .flowtrack import ConntrackSource, FlowTracker
from .intent import IntentError, LeaseBook
from .harness import SCENARIOS, CapacityMode, Harness, RunResult, SystemSpec
from .metrics import EvaluationData, MetricsCollector, TextClassSource
from .model import TrafficClass
from .policy import floor_mbps

WORKLOAD_DIR = Path(__file__).resolve().parent.parent / "testbed" / "workloads"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "data" / "runs"

#: Workloads that measure round-trip time and therefore have partial reports.
#: bulk and video deliberately are not: they generate data, and their latency is
#: not the thing being measured.
PROBE_KINDS = ("call", "game")

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
                     dscp: int | None, json_out: Path, log_path: Path,
                     src: str | None = None) -> None:
        self.sources.append([kind, dst, str(port), src])
        self.commands.append([kind, dst, str(port), src])

    def collect(self) -> list:
        return []

    def stop(self) -> None:
        pass


class NetnsLauncher:
    """Runs real generator processes inside namespaces."""

    def __init__(self, python: str = "python3", ns_client: str = NS_CLIENT,
                 ns_wan: str = NS_WAN, out_dir: Path | None = None,
                 observe: bool = False):
        #: Record per-packet send/receive timestamps. Off by default: it
        #: appends a line per packet, which is fine for a probe and wasteful
        #: for the bulk generators. Exists because a percentile cannot say
        #: which packets were slow or when.
        self.observe = observe
        self.python = python
        self.ns_client = ns_client
        self.ns_wan = ns_wan
        self.out_dir = out_dir
        self.procs: list[subprocess.Popen] = []
        #: Sinks run `while True` and never exit on their own -- they are meant
        #: to outlive the run and be torn down with the namespace. Collecting
        #: used to wait for them like senders, so every run sat out a 90-second
        #: timeout PER SINK before killing it. Four workloads = 6 minutes of
        #: dead time per run, which is where the "40-second scenario takes 7
        #: minutes" came from.
        self.sink_procs: list[subprocess.Popen] = []
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
        self.sink_procs.append(p)
        return p

    def spawn_source(self, kind: str, dst: str, port: int, duration: float,
                     dscp: int | None, json_out: Path, log_path: Path,
                     src: str | None = None) -> subprocess.Popen:
        """Sending end, always in the wan namespace (the 'internet')."""
        argv = self._argv(self.ns_wan, f"{kind}.py", "--dst", dst,
                          "--port", str(port), "--duration", str(duration),
                          "--json-out", str(json_out))
        if src:
            # See device_ip_for: one address per workload, so a lease can match
            # one device instead of all of them.
            argv += ["--src", src]
        if kind in PROBE_KINDS:
            # Only the workloads built on UdpProbe accept this. bulk and video
            # implement their own senders and would abort on an unknown flag --
            # and they are bulk data generators, not latency probes, so there is
            # no round trip to report on.
            argv += ["--partial-out", str(json_out.with_suffix(".partial.json"))]
            if self.observe:
                # One line per packet: sequence, send timestamp, receive
                # timestamp. Needed because a percentile cannot say *which*
                # packets were slow or *when* -- an unexplained 80 ms tail
                # appeared for every seed and every system, and without this
                # there is no way to locate it against what the run was doing.
                argv += ["--obs-out", str(json_out.with_suffix(".obs.jsonl"))]
        if dscp is not None:
            argv += ["--dscp", str(dscp)]
        p = subprocess.Popen(argv, stdout=open(log_path, "w"),
                             stderr=subprocess.STDOUT, start_new_session=True)
        self.procs.append(p)
        return p

    def collect(self) -> list[tuple[str, str]]:
        """Wait for the senders, then stop the sinks.

        The sinks do not exit on their own, so waiting for them was always a
        timeout, never a completion. They are asked to stop instead, and only
        killed if they ignore that -- which they do not, because they handle
        SIGTERM.
        """
        out = []
        for p in self.procs:
            try:
                p.wait(timeout=90)
            except subprocess.TimeoutExpired:
                p.kill()
        self._stop_sinks()
        return out

    def _stop_sinks(self, grace: float = 2.0) -> None:
        for p in self.sink_procs:
            if p.poll() is not None:
                continue
            try:
                os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except (ProcessLookupError, PermissionError, OSError):
                try:
                    p.terminate()
                except OSError:
                    continue
        for p in self.sink_procs:
            try:
                p.wait(timeout=grace)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    p.kill()
        self.sink_procs.clear()

    def stop(self) -> None:
        self._stop_sinks()
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
        #: Ticks whose enforcement step raised. Non-zero means the kernel refused
        #: something and the sample's empty verdicts are a failure, not an absence.
        self._enf_errors = 0
        self._enf_last_error: str | None = None
        #: (verdicts_seen, filters_installed) on the first tick that produced a
        #: verdict but installed nothing. Captured so a later drop to zero can be
        #: reported as "4 filters vanished" rather than inferred from a reader
        #: comparing two numbers.
        self._enf_first_steer: tuple[int, int] | None = None
        #: Last observed filter count, and the high-water mark. Run state rather
        #: than a loop local, so the note at the end of the run can see it even
        #: when the loop was skipped entirely.
        self._enf_filters_n = -1
        self._enf_filters_seen_max = 0
        self._last_filter_reads: tuple[int, int] = (-1, -1)
        #: Set when `tc` refused the capacity change. Carried into result.json,
        #: because otherwise the run reports a link state it never reached.
        self._capacity_change_failed = False
        self._capacity_change_error = ""
        #: Lease reporting state. Defaults live here as well as in run() so a
        #: note helper cannot AttributeError on a runner that has not run yet --
        #: which is exactly what happened the first time one was tested.
        self._lease_ips: list[str] = []
        self._lease_weight = 0.5
        self._lease_effective_s = 0.0
        #: Recent per-tick verdicts, newest last. Used to attribute a workload's
        #: probe traffic to the class it was steered into; bounded so a long run
        #: cannot grow it without limit.
        self._last_verdicts: list[dict] = []
        self.window_verdicts = 200

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
        recover_at_s: float | None = None,
        recover_to_mbps: float | None = None,
        settle_s: float | None = None,
        enforce: bool = False,
        lease_ips: Sequence[str] = (),
        lease_weight: float = 0.5,
        lease_ttl_s: float | None = None,
    ) -> RunResult:
        self.enforce = enforce
        self._lease_ips = list(lease_ips)
        #: Seconds during which the lease class actually existed and could steer
        #: a flow. The old note read the *end* state, so a lease installed at
        #: t=6 and reverted at t=46 by its own TTL was reported as "NOT
        #: INSTALLED" -- which is how a working lease arm got read as a failed
        #: one. Coverage over time is the only thing a run can honestly report.
        self._lease_effective_s = 0.0
        #: Recent per-tick verdicts, newest last. Used to attribute a workload's
        #: probe traffic to the class it was steered into; bounded so a long run
        #: cannot grow it without limit.
        self._last_verdicts: list[dict] = []
        self.window_verdicts = 200
        self._lease_weight = lease_weight
        #: None means "one whole run", which is the useful default for measuring
        #: a lease: a TTL shorter than the run would demonstrate expiry and
        #: nothing else. It still expires on its own -- `expires_at` is recorded
        #: -- it simply expires after the measurement rather than during it.
        self._lease_ttl_s = lease_ttl_s
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
        #: Ticks whose enforcement step raised. Non-zero means the kernel refused
        #: something and the sample's empty verdicts are a failure, not an absence.
        self._enf_errors = 0
        self._enf_last_error: str | None = None
        #: (verdicts_seen, filters_installed) on the first tick that produced a
        #: verdict but installed nothing. Captured so a later drop to zero can be
        #: reported as "4 filters vanished" rather than inferred from a reader
        #: comparing two numbers.
        self._enf_first_steer: tuple[int, int] | None = None
        #: Last observed filter count, and the high-water mark. Run state rather
        #: than a loop local, so the note at the end of the run can see it even
        #: when the loop was skipped entirely.
        self._enf_filters_n = -1
        self._enf_filters_seen_max = 0
        self._last_filter_reads: tuple[int, int] = (-1, -1)
        #: Set when `tc` refused the capacity change. Carried into result.json,
        #: because otherwise the run reports a link state it never reached.
        self._capacity_change_failed = False
        self._capacity_change_error = ""
        #: When M2 last produced a *new* reading, and when the link was last
        #: reconfigured. Their comparison decides whether the final estimate
        #: describes the end of the run or a moment before it changed.
        self._est_t: float | None = None
        self._cap_t: float | None = None
        self._lease_book = LeaseBook()
        enforcement_why = "not requested"
        will_enforce = False
        if self.enforce:
            if system is not SystemSpec.ACIQ:
                enforcement_why = f"{system.value} is a baseline, not ACIQ"
            elif isinstance(self.launcher, DryLauncher):
                enforcement_why = "dry run launches no traffic"
            else:
                will_enforce = True
        if self._lease_ips and system is not SystemSpec.ACIQ:
            enforcement_why = (f"leases requested for {', '.join(self._lease_ips)} "
                               f"but {system.value} is a baseline")

        # ---- config, written before anything runs so a crashed run is
        # ---- still reproducible from its artefacts
        ports = sc.seed_workloads(seed)
        cfg = {
            "scenario": sc.name, "system": system.value, "mode": mode.value,
            "seed": seed, "link_mbps": link_mbps, "drop_mbps": drop_mbps,
            "drop_at_s": drop_at_s,
            "recover_at_s": recover_at_s, "recover_to_mbps": recover_to_mbps,
            "duration_s": sc.duration_s,
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
            # Recorded because a lease that was requested and silently refused is
            # indistinguishable from one never asked for.
            "lease_ips": list(self._lease_ips),
            # Which address belongs to which workload. Without this the
            # artefact says a lease was held for 203.0.113.4 and gives no way
            # to tell what that was meant to protect.
            "device_ips": {label: device_ip_for(i)
                           for i, (label, _p, _d) in enumerate(ports)},
            "lease_weight": self._lease_weight if self._lease_ips else None,
            "lease_ttl_s": self._lease_ttl_s,
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
            else:
                # Leases go in before the workloads start, so the very first
                # verdict can already see them. Requesting one mid-run would
                # measure the transition instead of the effect.
                self.harness.enable_leases(self._lease_book)
                ttl = self._lease_ttl_s if self._lease_ttl_s is not None \
                    else sc.duration_s + settle + 1.0
                for ip in self._lease_ips:
                    try:
                        self._lease_book.request(target="device", ip=ip,
                                                 weight=self._lease_weight,
                                                 ttl_s=ttl)
                    except IntentError as e:
                        enforcement_why = f"lease rejected: {e}"
                self.harness.sync_lease(self._lease_book.to_policy_lease(),
                                        link_mbps)

        # ---- 2. launch workloads: sinks first so nothing races the listener
        #
        # NOTE on `zip()` here: plain zip is CORRECT, and `strict=True` was
        # tried and reverted. `ports` is a deliberate FILTERED SUBSET of
        # `_expand(sc)` -- the settle path passes only the interactive
        # workloads, and callers may probe a single class. Plain zip
        # truncating to the shorter sequence is exactly the intended
        # semantics; `strict=True` raises "zip() argument 2 is longer than
        # argument 1" and broke the probe-ingestion tests.
        #
        # So the B905 finding is a false positive at these sites, and the rule
        # is disabled for them in pyproject.toml with this reason recorded
        # rather than "fixed" into a crash.
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

        for idx, ((label, port, dscp), w) in enumerate(
                zip(ports, _expand(sc))):
            self.launcher.spawn_source(
                w.kind, CLIENT_IP, port, sc.duration_s, w.dscp,
                paths.file(f"{label}.json"), paths.file(f"{label}.log"),
                src=device_ip_for(idx))

        # ---- 3. sample
        # Text first: verified by gate check 10. The JSON reader silently
        # returned empty on this host and made every sample come back as
        # `per_class: {}`.
        collector = MetricsCollector(
            self.source or TextClassSource(dev=self.harness.dev, ns=self.harness.ns))
        samples: list[dict] = []
        # Read fresh each tick. Bound before the loop so a run with enforcement
        # off still has them: -1 means "not read", which is what it is.
        n_json = n_text = -1
        _prev_est = self.harness._estimator.current.mbps
        t0 = time.monotonic()
        ticks = int(sc.duration_s / self.tick_s) + 1
        dropped = False
        recovered = False
        for i in range(ticks):
            now = time.monotonic()
            if self.real_time:
                time.sleep(self.tick_s)
            # A dry run must still advance the *scenario* timeline, otherwise
            # drop_at_s can never be reached and the drop path goes untested.
            elapsed = (now - t0) if self.real_time else i * self.tick_s

            # Probe telemetry has to be read *during* the run. It used to be
            # ingested once, after `launcher.collect()` returned, so every row
            # of samples.jsonl would have carried the same final value -- a step
            # function presented as a time series.
            self._ingest_probes(collector, paths, ports, scenario_name)

            frame = collector.poll()

            # Close the loop on every tick. M2 needs consecutive saturated
            # samples before it trusts a reading, so a loop that only ran at a
            # capacity drop and once at the end could never reach its streak and
            # the estimate stayed 0.0 for the whole run.
            if mode is CapacityMode.ADAPTIVE:
                self._closed_loop_step(collector, self.tick_s, t0 + elapsed)
            if (self._lease_book and self._lease_book.active()
                    and getattr(self.harness, "_lease_in_effect", False)):
                self._lease_effective_s += self.tick_s
            if enforcement_on:
                verdicts, filters_n = self._enforcement_step(ports, t0 + elapsed)
                # Kept so the probe collector can ask which class a workload's
                # traffic was actually steered into. Without this mapping, latency
                # had nowhere to land and was reported as zero for the whole
                # life of the project.
                self._last_verdicts.append(verdicts)
                del self._last_verdicts[:-self.window_verdicts]
                self._enf_filters_n = filters_n
                n_json, n_text = self._last_filter_reads
                if filters_n > 0:
                    self._enf_filters_seen_max = max(self._enf_filters_seen_max,
                                                     filters_n)
            else:
                verdicts, filters_n = {}, 0
            # Note when M2 last moved. A run whose only reading predates the drop
            # reports that pre-drop number as "the estimator" alongside
            # link_end=20 -- the matrix showed 102.77 Mbps for a 20 Mbps link.
            if self.harness._estimator.current.mbps != _prev_est:
                _prev_est = self.harness._estimator.current.mbps
                self._est_t = elapsed

            lk = collector.last_link_counters()
            # The external telemetry the ESTIMATOR ACTUALLY SAW this tick.
            #
            # Taken from the Measurement the harness built, not re-read here.
            # The first version of this re-read `tc` independently, so the
            # recorded values could disagree with the verdict they were meant to
            # explain -- and the run produced `sat=True backlog=0 drops=0.0`,
            # which is not a state the code can produce. An instrument that
            # reports a contradiction is worse than none.
            _bn_backlog = None
            _bn_drop_rate = None
            _last_m = getattr(self.harness, "last_measurement", None)
            if _last_m is not None:
                _bn_backlog = _last_m.bottleneck_backlog_bytes
                _bn_drop_rate = _last_m.bottleneck_drop_rate_per_s

            samples.append({
                "t": round(elapsed, 2),
                "bottleneck_backlog_bytes": _bn_backlog,
                "bottleneck_drop_rate_per_s": _bn_drop_rate,
                "per_class": {k.value: vars(v) for k, v in frame.per_class.items()},
                # The link (parent class) counters, which are the ONLY thing
                # M2 treats as saturation. Recorded explicitly so a wrong
                # estimate can be diagnosed from the artefact alone.
                # cls is None and handle carries the classid: the parent is 1:1,
                # and labelling it "realtime_interactive" put a wrong class name
                # on every sample of every system.
                "link": vars(lk) if lk is not None else None,
                # The out-of-band bottleneck's real state, every tick.
                #
                # Added because a 10 Mbps limit WAS applied and verified, was
                # observed holding at exactly 10.00 Mbps, and then throughput
                # climbed back to 46.78 and stayed there for the rest of the
                # run -- with nothing in the tree touching that link. A
                # capacity that vanishes mid-run is only diagnosable if the
                # artefact records it, and result.json recorded only the limit
                # that was asked for.
                "bottleneck": self.harness.capture_bottleneck(),
                "estimator_saturated": self.harness._estimator.current.saturated,
                "fairness": frame.fairness,
                "cpu_fraction": frame.cpu_fraction,
                "capacity_mbps": self.harness._estimator.current.mbps,
                # What each workload was steered to this tick, if enforcement is
                # on. Recorded per sample so the artefact shows the decision and
                # its timing, rather than asking the reader to trust the code.
                "verdicts": verdicts,
                # Whether a lease covered any flow this tick. Sampled, not
                # assumed, so a lease that never matched anything is visible.
                "lease_active": bool(self._lease_book.active()) if self._lease_book else False,
                # How many of our filters the device still has. This is the
                # discriminator the lease A/B run lacked: with the count you can
                # tell "the filter was removed" from "it is installed and not
                # matching", which look identical in the verdicts alone. It is
                # what turned a healthy-looking run into an unanswerable one.
                "filters_installed": filters_n,
                # Both readers, always. When these disagree the JSON reader is
                # lying, and a future run should be able to see that from its own
                # artefacts instead of re-deriving it.
                "filters_json": n_json, "filters_text": n_text,
            })

            # The recovery: the link comes BACK. Without this the controller was
            # only ever tested falling, never recovering -- so a bug that left a
            # policy stuck at the degraded rate, or an estimator that could not
            # walk back up, would never have been caught. The brief grades
            # "adaptation speed and policy stability", and stability after a
            # recovery is half of that.
            #
            # Only the link changes here too. The controller has to notice from
            # counters, the same as for the drop.
            if (recover_at_s is not None and dropped and not recovered
                    and recover_to_mbps is not None
                    and elapsed >= recover_at_s):
                recovered = True
                self._cap_t = elapsed
                self.harness.set_capacity(recover_to_mbps)
                if not self.harness._capacity_change_ok:
                    self._capacity_change_failed = True
                    self._capacity_change_error = \
                        self.harness._capacity_change_error

            # the drop: the link changes, and only the link changes
            if drop_at_s is not None and not dropped and elapsed >= drop_at_s:
                dropped = True
                self._cap_t = elapsed
                # Only the link changes. Baselines are not told; ACIQ must
                # notice from counters alone.
                self.harness.set_capacity(drop_mbps)
                if not self.harness._capacity_change_ok:
                    self._capacity_change_failed = True
                    self._capacity_change_error = \
                        self.harness._capacity_change_error
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
        if self._enf_errors:
            enforcement_note += (f"; {self._enf_errors} tick(s) raised during "
                                 f"enforcement, last: {self._enf_last_error}")
        loss = self._filter_loss_note(self._enf_filters_n)
        if loss:
            enforcement_note += "; " + loss
        lease_note = bool(self._lease_ips) and enforcement_on
        # The distinction that was missing when this was first written: a lease
        # that is *held* and a lease that is *installed* are different states.
        # Held-but-not-installed means class 1:40 was never created, so every
        # per-flow filter points at a class that does not exist and the run
        # steers nothing while reporting "leases held".
        _lease_note = self._lease_note_text() if lease_note else ""
        if enforcement_on:
            self.harness.disable_enforcement()
            self._tracker = self._ct = None

        paths.write_jsonl("samples.jsonl", samples)
        paths.write_json("workloads.json", workloads)
        # The transaction manager's audit was in memory and never written, so a
        # run that applied, vetoed or rolled back a policy left no trace of it.
        # "policy_changes=0" says the count, not the reason.
        paths.write_json("audit.json", self.harness.txn.audit)

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
        # What the bottleneck actually ended up as. The run reports the link it
        # was told to build otherwise, which is how a limit that is applied and
        # then lost can look like a limit that held.
        try:
            bottleneck_state = self.harness.capture_bottleneck()
        except Exception as e:                      # noqa: BLE001
            bottleneck_state = f"(capture failed: {e})"

        res = RunResult(
            scenario=sc.name, system=system.value, capacity_mode=mode.value,
            seed=seed, link_start_mbps=link_mbps,
            link_end_mbps=drop_mbps if dropped else link_mbps,
            capacity_recovered=recovered,
            capacity_recover_to_mbps=recover_to_mbps if recovered else None,
            capacity_change_applied=not self._capacity_change_failed,
            capacity_change_error=self.harness._capacity_change_error,
            estimator_mbps=round(est, 2) if est else None,
            # The WHOLE series, not the tail.
            #
            # This truncated to the last 3 samples, which discarded the entire
            # transition. A real run dropped 100 -> 10 Mbps and then, because of
            # a separate defect, went back up to 47. result.json showed only
            # {t=39,40,41} at 47 -- an unreadable number with no context -- while
            # samples.jsonl held the 10 Mbps dip that showed what had actually
            # happened. An evidence file that hides the interesting part is
            # worse than no evidence file, because it looks like a result.
            samples=samples,
            policy_changes=self.harness.policy_changes,
            bottleneck_state=bottleneck_state,
            # observed, not configured
            duration_s=(round((samples[-1]["t"] - samples[0]["t"]), 2)
                        if len(samples) >= 2 else 0.0),
notes=(([] if dropped else ["no capacity drop in this run"])
                   + ([stale_note] if stale_note else [])
                   + [enforcement_note]
                   + ([_lease_note] if lease_note else [])
                   + ([self._capacity_note()] if self._capacity_change_failed else [])),
        )
        paths.write_json("result.json", json.loads(res.to_json()))
        return res

    def _enforcement_step(self, ports, now: float) -> tuple[dict[str, dict], int]:
        """One enforcement tick: observe flows, classify, steer.

        Returns (verdicts, filters_still_installed).

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
            # Narrow on purpose. This was a bare `except Exception`, which also
            # swallowed BridgeError from a failed `tc filter add` -- so a filter
            # the kernel rejected looked exactly like a tick that found no flows,
            # and the run reported verdicts while steering nothing.
            self._enf_errors += 1
            return {}, -1
        try:
            verdicts = self._steer(ports, now, text)
            return verdicts, self._count_filters()
        except Exception as e:
            # Recorded rather than raised: a run must finish so that its
            # artefacts exist, but the failure has to be visible in them. A tick
            # that silently does nothing is exactly how the leased run looked
            # healthy while the kernel refused every filter install.
            self._enf_errors += 1
            self._enf_last_error = f"{type(e).__name__}: {e}"
            return {}, -1

    def _count_filters(self) -> int:
        """How many of our flower filters the device still has.

        Two independent readers, and the more generous one wins. The JSON reader
        has already been observed returning empty on this host for a sibling
        `tc -j` command, and "empty from JSON" is indistinguishable from "the
        filters are gone" -- which is how a run came to report all four removed
        when they may simply not have been read.

        Taking the max means a filter has to be invisible to *both* readers to
        count as gone. Reporting the smaller number would make every JSON glitch
        look like a lost filter, which is the error in the other direction.

        -1 when neither reader worked, which is deliberately not 0.
        """
        dev, ns = self.harness.dev, self.harness.ns
        # The injected executor, so a dry run or a unit test measures the same
        # thing the bridge would. Without this the readers always shell out for
        # real, return nothing, and the count is permanently -1 -- which reads
        # as "could not tell" and is exactly what makes the note untestable.
        ex = self.bridge_executor
        if ex is None and self.harness.enforcement_enabled:
            ex = getattr(self.harness._enforcer.bridge, "executor", None)
        try:
            n_json = len(enumerate_flow_filters(dev, ns, executor=ex))
        except Exception:
            n_json = -1
        n_text = count_flow_filters_text(dev, ns, executor=ex)
        self._last_filter_reads = (n_json, n_text)
        known = [n for n in (n_json, n_text) if n >= 0]
        if not known:
            return -1
        return max(known)

    def _steer(self, ports, now: float, text: str) -> dict:
        """One tick's work: classify every flow this run owns and steer it."""
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
            if self._enf_first_steer is None:
                self._enf_first_steer = (len(out), self._count_filters())
        return out

    def _lease_note_text(self) -> str:
        """The lease note, factored out so it can be tested directly.

        Coverage over time, not the end state. Leases expire by design, so the
        teardown state is almost always "not installed" even for a lease that
        steered traffic for the whole run -- which is exactly how the lease arm
        of the ab_* comparison got read as a failed one.
        """
        if self._lease_effective_s > 0:
            return (f"leases held for {', '.join(self._lease_ips)} "
                    f"(weight {self._lease_weight:.2f}), in effect for "
                    f"{self._lease_effective_s:.1f}s of the run")
        return (f"leases HELD for {', '.join(self._lease_ips)} but "
                "NEVER INSTALLED -- the shield refused the rate plan, so class "
                "1:40 was never created and no per-flow filter could steer to it")

    def _capacity_note(self) -> str:
        """Loud, because `link_end_mbps` still reports the requested value."""
        return (f"CAPACITY CHANGE REFUSED by tc ({self._capacity_change_error}) -- "
                f"the link was NOT changed. result.json still shows "
                f"link_end_mbps as the value that was requested, not one that was "
                f"measured; treat every result from this run as an undropped run")

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

    def _filter_loss_note(self, filters_n: int) -> str:
        """Say it if our filters went missing, and say how they went.

        This is the note the lease A/B run needed and did not have. B's filters
        matched for three ticks and then never again, with the verdict steady at
        `adaptive` and no error anywhere -- so "the filter was removed" and "it
        is installed and not matching" were indistinguishable, and the run could
        not be diagnosed from its own artefacts.

        Reported only on a clean fall to zero. A count that flickers between 0 and
        N is usually the enumeration losing a race, not filters being deleted, and
        claiming otherwise would send someone hunting a bug that is not there.
        """
        if filters_n != 0 or self._enf_first_steer is None:
            return ""
        if self._enf_filters_seen_max <= 0:
            # Never saw any, so nothing went missing -- the run installed none.
            return ""
        expected, _seen = self._enf_first_steer
        return (f"all {expected} per-flow filters are GONE from the device while "
                f"the classifier still reports verdicts for them -- something "
                f"removed them. filters_installed is in every sample: 0 means "
                f"removed, a non-zero count means they are installed and not "
                f"matching. Compare with data/leaseB, where the count was not "
                f"recorded and this could not be told apart")

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

    def _ingest_probes(self, collector: MetricsCollector, paths: RunPaths,
                       ports, scenario_name: str) -> None:
        """Fold each probe workload's partial report into the collector.

        The generators write their report incrementally rather than only at exit,
        so this can be called every tick. `label -> TrafficClass` comes from the
        classifier's own verdict for that flow, which is the only party that
        knows where the traffic was steered -- that mapping was missing
        entirely, and its absence is why latency was reported as zero forever.
        """
        for (label, _port, _dscp), _w in zip(
                ports, _expand(SCENARIOS[scenario_name])):
            f = paths.file(f"{label}.partial.json")
            if not f.exists():
                continue
            try:
                d = json.loads(f.read_text())
            except (json.JSONDecodeError, OSError):
                continue        # mid-write; the next tick will catch it
            cls = self._verdict_class(label)
            collector.ingest(EvaluationData(
                t=time.monotonic(), label=label,
                rtt_ms=d.get("p95"), jitter_ms=d.get("jitter_ms"),
                loss_ratio=d.get("loss_ratio")), cls=cls)

    def _verdict_class(self, label: str) -> TrafficClass | None:
        """The class the bridge last steered this workload's flow into."""
        for verdicts in reversed(self._last_verdicts):
            v = verdicts.get(label)
            if v is None:
                continue
            name = v.get("class") if isinstance(v, dict) else v
            if not name:
                return None
            try:
                return TrafficClass(name)
            except ValueError:
                # "unclassified" and any future non-enum value: this flow is
                # not in a class that carries probe telemetry.
                return None
        return None

    def _closed_loop_step(self, collector: MetricsCollector, dt: float, now: float):
        """M2 -> M3 -> M4, using only what the counter reader sees."""
        return self.harness.adapt_step(
            _counters_from_last_frame(collector), dt=dt, now=now,
            link=collector.last_link_counters())


def _counters_from_last_frame(collector: MetricsCollector):
    return collector.last_counters()


#: First address handed out to a simulated device. 203.0.113.2 is the wan
#: namespace's own address and is deliberately skipped so "the device" and "the
#: namespace" cannot be confused for each other in a lease.
DEVICE_IP_BASE = 3


def device_ip_for(index: int) -> str:
    """The source address for the *index*-th workload.

    The testbed ran every workload from one address, so a lease for "a device"
    matched every flow and the leased class took the whole link. That is a true
    statement about steering and a useless one about leases: with one device
    there is no "expense to others" to measure.

    Assigning by position rather than by name keeps the mapping deterministic --
    the same scenario always produces the same addresses, so a lease for
    203.0.113.4 means the same workload across runs.
    """
    return f"203.0.113.{DEVICE_IP_BASE + index}"


def _expand(sc):
    """One entry per (label, port) pair, matching seed_workloads' order."""
    out = []
    for w in sc.workloads:
        for _ in range(w.count):
            out.append(w)
    return out
