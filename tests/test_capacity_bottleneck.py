"""The capacity drop must be enforced out of band.

**Spec-first, and they earned it.** These were written before the fix and
marked `expectedFailure` while the defect was real. When the fix landed they
reported "unexpected successes" -- which unittest counts as a failure -- so the
requirement could not have been quietly dropped. They are live assertions now.

The collision, from real host evidence (`s2_wan_drop`, kernel 7.1.5):

    t=5.19  ~102 Mbps     link at 100
    t=6.24   12.35 Mbps   drop applied
    t=7.28   10.03 Mbps   correctly at the 10 Mbps target
    t=9.41   47.11 Mbps   controller raised it back
    t=13.51  47.02 Mbps   and stayed there

because both `set_capacity` and `build_plan` write the HTB root class `1:1`.
The controller's policy write therefore erases the drop it is meant to detect,
and the estimator then faithfully reports the number the controller chose.

The generators run in ns `wan`, the sinks in ns `client`, and ACIQ only ever
writes `router/veth-lan`. So `wan/veth-w` is a bottleneck the controller cannot
reach -- which is exactly the property required here.
"""

from __future__ import annotations

import unittest

from aciq.harness import ROOT_CLASS_ID, Harness


class TestCapacityIsEnforcedOutOfBand(unittest.TestCase):
    """After the fix these pass; before it they describe the defect."""

    def test_set_capacity_does_not_write_the_root_class(self):
        """The controller's plan owns 1:1. Nothing else may write it."""
        from aciq.tc import build_tree
        from aciq.model import RatePlan
        h = Harness()
        plan = h.build_plan_for_test(20.0) if hasattr(h, "build_plan_for_test") \
            else _plan(20.0)
        cmds = h.set_capacity(20.0)
        flat = [" ".join(c) for c in cmds]
        for c in flat:
            self.assertNotIn(
                f"classid {ROOT_CLASS_ID}", c,
                f"set_capacity still writes {ROOT_CLASS_ID}, which build_plan "
                f"also writes: {c}")
        # and prove the two really do collide if it ever comes back
        tree_cmds = [" ".join(c) for c in
                     __import__("aciq.tc", fromlist=["x"]).render(
                         build_tree(plan), dev="veth-lan", ns="router")]
        self.assertTrue(any(ROOT_CLASS_ID in c for c in tree_cmds),
                        "build_plan must still write the root class -- if it "
                        "stops, the collision argument above is stale")

    def test_the_bottleneck_is_applied_with_netem(self):
        h = Harness()
        cmds = [" ".join(c) for c in h.set_capacity(10.0)]
        self.assertTrue(any("netem" in c for c in cmds),
                        f"capacity must be limited with netem; got {cmds}")

    def test_the_bottleneck_is_not_on_the_device_the_controller_writes(self):
        """The device is the constraint, not the namespace.

        It started on `wan/veth-w` -- a different namespace, but also a place
        the collector reads no counters, so M2 was blind to it:

            estimator 103.2 Mbps is STALE: M2 only measures an oversubscribed
            link ... no post-drop reading was possible

        Unwritable and observable are separate properties. The bottleneck is on
        `wan/veth-w` because that is the only side whose EGRESS carries the
        data; the reader takes ns and dev, so it reads that link while the
        controller writes `router/veth-lan`.

        It was briefly on `router/veth-wan` to satisfy both at once, which was
        wrong for a physical reason: that qdisc shapes router->wan, i.e. the
        ACK direction. A run with it there reported `rate 10Mbit` and
        `capacity_change_applied: True` and measured 102.44 Mbps -- a limit
        that was applied, verified, and doing nothing.
        """
        h = Harness()
        cmds = [" ".join(c) for c in h.set_capacity(10.0)]
        netem = [c for c in cmds if "netem" in c]
        self.assertTrue(netem)
        for c in netem:
            self.assertNotIn(h.dev, c,
                             f"the bottleneck must not be on the device the "
                             f"controller writes: {c}")
            self.assertIn(h.bottleneck_dev, c, c)

    def test_the_bottleneck_is_on_the_egress_that_carries_the_data(self):
        """netem shapes egress, and only the wan side's egress carries traffic.

        wan -> router -> client. `wan/veth-w` egress is generator -> router and
        limits the data; `router/veth-wan` egress is router -> wan and does not.
        """
        h = Harness()
        self.assertEqual(h.bottleneck_dev, "veth-w")
        self.assertEqual(h.bottleneck_ns, "wan")
        self.assertNotEqual(h.bottleneck_dev, h.dev)

    def test_the_drop_reader_reads_the_bottleneck_namespace(self):
        """Observability comes from the reader's ns argument, not from sharing
        a namespace with the controller."""
        h = Harness()
        src = h._bottleneck_drops()
        self.assertEqual(src.ns, "wan")
        self.assertEqual(src.dev, "veth-w")

    def test_the_rate_reaches_the_command(self):
        h = Harness()
        cmds = [" ".join(c) for c in h.set_capacity(10.0)]
        self.assertTrue(any("10" in c and "rate" in c for c in cmds),
                        f"the 10 Mbps limit must appear in the command: {cmds}")

    def test_a_capacity_change_is_verifiable(self):
        """Same standard as the rollback work: issued is not installed."""
        h = Harness()
        self.assertTrue(
            any("qdisc show" in " ".join(c) for c in h.set_capacity(10.0))
            or hasattr(h, "verify_capacity"),
            "applying the bottleneck must be followed by a read-back, for the "
            "same reason rollback verification exists")


def _plan(cap: float) -> "RatePlan":  # noqa: F821
    from aciq.policy import build_plan
    return build_plan(cap)


if __name__ == "__main__":
    unittest.main()

class TestBottleneckStateIsEvidence(unittest.TestCase):
    """A run must report the bottleneck it ended with, not the one it was told
    to build.

    A real run applied a 10 Mbps netem limit -- throughput hit exactly 10.00 at
    t=7.22 -- and then climbed back to 46.78 and stayed there. With no record of
    the qdisc's final state, `capacity_change_applied: True` and
    `link_end_mbps: 10.0` read as a working drop, and the only reason the defect
    was visible at all was that samples.jsonl happened to be preserved.
    """

    def test_capture_bottleneck_records_the_real_state(self):
        h = Harness()
        out = h.capture_bottleneck()
        self.assertIsInstance(out, str)
        self.assertEqual(h.bottleneck_state_at_end, out)

    def test_capture_reads_the_bottleneck_device(self):
        from aciq.txn import FakeRunner
        r = FakeRunner()
        h = Harness(runner=r)
        h.capture_bottleneck()
        text = " ".join(" ".join(c) for c in r.commands)
        self.assertIn("qdisc show", text)
        self.assertIn(h.bottleneck_dev, text)
        self.assertIn(h.bottleneck_ns, text)

    def test_runresult_carries_the_bottleneck_state(self):
        import dataclasses
        from aciq.harness import RunResult
        self.assertIn("bottleneck_state",
                      {f.name for f in dataclasses.fields(RunResult)})

    def test_the_evidence_run_is_still_showing_the_fault(self):
        """Guards against this being 'fixed' by re-reading old evidence."""
        import glob
        hits = sorted(glob.glob("data/host_gate_adapt/*/result.json"))
        if not hits:
            self.skipTest("no adaptation evidence")
        import json
        last = json.load(open(hits[-1]))
        if "bottleneck_state" not in last:
            self.skipTest(
                "the newest adaptation run predates bottleneck capture; "
                "re-run s2_wan_drop before trusting the capacity gate")
        # If the limit is recorded as gone at the end of a run, that run is
        # evidence of the fault and must never be counted as an adaptation.
        state = last["bottleneck_state"] or ""
        self.assertNotIn(
            "noqueue", state,
            f"the bottleneck ended as noqueue -- the limit was lost: {state!r}")


class TestBottleneckReadBackIsNumeric(unittest.TestCase):
    """The read-back was a substring test, which is the worst kind of bug.

        applied = "10.0000" in out

    tc prints the limit normalised -- `rate 10Mbit` -- so the check could never
    succeed. On the host that turned a perfectly applied netem limit into
    "CAPACITY CHANGE REFUSED ... the link was NOT changed", and the run was
    then discarded as an undropped run while netem was visibly holding the link
    at 10 Mbit for the rest of it.

    It does not miss a fault. It invents one, and makes a working system look
    broken."""

    # verbatim from the user's host, data/host_gate_adapt
    REAL_OUTPUT = ("qdisc netem 8001: root refcnt 5 limit 1000 "
                   "rate 10Mbit")

    def test_the_real_host_output_is_accepted(self):
        from aciq.harness import _qdisc_reports_rate as f
        self.assertTrue(f(self.REAL_OUTPUT, 10.0))

    def test_unit_variants_are_accepted(self):
        from aciq.harness import _qdisc_reports_rate as f
        self.assertTrue(f("qdisc netem 1: root rate 100Mbit", 100.0))
        self.assertTrue(f("qdisc netem 1: root rate 1000Kbit", 1.0))
        self.assertTrue(f("qdisc netem 1: root rate 1Gbit", 1000.0))

    def test_a_wrong_rate_is_rejected(self):
        from aciq.harness import _qdisc_reports_rate as f
        self.assertFalse(f(self.REAL_OUTPUT, 20.0))
        self.assertFalse(f(self.REAL_OUTPUT, 100.0))

    def test_no_rate_at_all_is_rejected(self):
        from aciq.harness import _qdisc_reports_rate as f
        self.assertFalse(f("qdisc noqueue 0: root refcnt 2", 10.0))

    def test_rounding_within_tolerance_is_accepted(self):
        from aciq.harness import _qdisc_reports_rate as f
        self.assertTrue(f("rate 9.9997Mbit", 10.0))

    def test_set_capacity_now_accepts_the_real_output(self):
        """End to end through FakeRunner, which prints what tc prints."""
        from aciq.txn import FakeRunner
        h = Harness(runner=FakeRunner())
        cmds = h.set_capacity(10.0)
        self.assertTrue(h._capacity_change_ok,
                        f"the limit was applied and refused: "
                        f"{h._capacity_change_error}")
        self.assertEqual(h._capacity_mbps, 10.0)


class TestTheRunThatExposedIt(unittest.TestCase):
    """The host run this came from, preserved rather than re-described."""

    def test_a_refusal_is_never_recorded_as_a_drop(self):
        """The property, asserted directly rather than via a pinned artefact.

        It was originally pinned to the run that exposed the substring bug,
        which meant it went on failing every time a newer, correct run landed
        -- a test coupled to a file rather than to a property, which stops
        testing anything the moment the evidence moves on.
        """
        from aciq.txn import FakeRunner
        from aciq.harness import _qdisc_reports_rate

        class Refuses(FakeRunner):
            def run(self, argv, **kw):
                if "qdisc" in argv and "replace" in argv:
                    return 1, "", "RTNETLINK answers: Operation not permitted"
                return super().run(argv, **kw)

        h = Harness(runner=Refuses())
        h.set_capacity(10.0)
        self.assertFalse(h._capacity_change_ok)
        self.assertNotEqual(h._capacity_mbps, 10.0,
                            "a refused change became the configured capacity")

        class Silent(FakeRunner):
            """Accepts the replace but never installs the limit."""

            def run(self, argv, **kw):
                if "qdisc" in argv and "replace" in argv:
                    return 0, "", ""
                if "qdisc" in argv and "show" in argv:
                    return 0, "qdisc noqueue 0: root refcnt 2", ""
                return super().run(argv, **kw)

        h2 = Harness(runner=Silent())
        h2.set_capacity(10.0)
        self.assertFalse(h2._capacity_change_ok,
                         "a limit that never appeared was accepted")


class TestBottleneckDropSignal(unittest.TestCase):
    """M2 must see the bottleneck without ever being told its capacity.

    The host, after the out-of-band move:

        estimator 103.2 Mbps is STALE: M2 only measures an oversubscribed
        link, and this one stopped being oversubscribed once the workload's
        rate fell with it, so no post-drop reading was possible

    The link was 10 Mbps, the plan was 100, the HTB parent was therefore not
    overcommitted, and `saturated()` was correctly false. Drops from the
    bottleneck are the ordinary signal a physical congested link gives.
    """

    NETEM = ("qdisc netem 8001: root refcnt 5 limit 1000 rate 10Mbit\n"
             " Sent 1200 bytes 9 pkt (dropped 40, overlimits 0 requeues 0)")

    @staticmethod
    def _src(outputs):
        it = iter(outputs)

        class R:
            def __call__(self, cmd, **kw):
                import types
                return types.SimpleNamespace(returncode=0,
                                             stdout=next(it, ""), stderr="")
        return R()

    def test_drop_counter_is_parsed(self):
        from aciq.metrics import BottleneckDropSource
        src = BottleneckDropSource(dev="veth-wan", ns="router",
                                   runner=self._src([self.NETEM]))
        self.assertEqual(src.dropped(), 40)

    def test_drop_rate_needs_two_samples(self):
        from aciq.metrics import BottleneckDropSource
        src = BottleneckDropSource(
            dev="veth-wan", ns="router",
            runner=self._src([self.NETEM,
                              self.NETEM.replace("dropped 40", "dropped 90")]))
        self.assertIsNone(src.drop_rate(1.0), "one sample is not a rate")
        self.assertEqual(src.drop_rate(1.0), 50.0)

    def test_no_drop_counter_means_no_signal_not_no_drops(self):
        from aciq.metrics import BottleneckDropSource
        src = BottleneckDropSource(
            dev="veth-wan", ns="router",
            runner=self._src(["qdisc htb 1: root refcnt 5\n"]))
        self.assertIsNone(src.dropped())

    def test_unreadable_device_means_no_signal(self):
        from aciq.metrics import BottleneckDropSource

        class Dead:
            def __call__(self, cmd, **kw):
                raise FileNotFoundError("ip")
        src = BottleneckDropSource(dev="veth-wan", ns="router", runner=Dead())
        self.assertIsNone(src.dropped())
        self.assertIsNone(src.drop_rate(1.0))

    def test_a_dropping_bottleneck_counts_as_saturation(self):
        from aciq.capacity import Measurement
        m = Measurement(t=1.0, goodput_mbps=10.0,
                        link_drop_rate_per_s=0.0,
                        link_overlimit_rate_per_s=0.0,
                        child_backlog_bytes=0,
                        bottleneck_drop_rate_per_s=250.0)
        self.assertTrue(m.saturated,
                        "a bottleneck that is dropping is saturated, whatever "
                        "the controller's own parent class is doing")

    def test_an_idle_bottleneck_does_not(self):
        from aciq.capacity import Measurement
        m = Measurement(t=1.0, goodput_mbps=100.0,
                        link_drop_rate_per_s=0.0,
                        link_overlimit_rate_per_s=0.0,
                        bottleneck_drop_rate_per_s=0.0)
        self.assertFalse(m.saturated)

    def test_absent_bottleneck_reading_is_treated_as_no_signal(self):
        """None must never mean 'dropping', or an unreadable device would
        declare every link saturated."""
        from aciq.capacity import Measurement
        m = Measurement(t=1.0, goodput_mbps=100.0,
                        link_drop_rate_per_s=0.0,
                        link_overlimit_rate_per_s=0.0,
                        bottleneck_drop_rate_per_s=None)
        self.assertFalse(m.saturated)

    def test_the_estimator_is_still_never_told_the_configured_rate(self):
        """The integrity property, asserted.

        `Measurement` deliberately has no field carrying the bottleneck's
        configured capacity -- "the estimator cannot read the bottleneck's
        configured rate even by accident". This must stay true: a drop COUNT is
        an observation; a rate is the answer.
        """
        import dataclasses
        from aciq.capacity import Measurement
        names = {f.name for f in dataclasses.fields(Measurement)}
        self.assertNotIn("configured_mbps", names)
        self.assertNotIn("bottleneck_mbps", names)
        self.assertNotIn("link_capacity_mbps", names)
        self.assertIn("bottleneck_drop_rate_per_s", names)

    def test_harness_asks_the_bottleneck_for_its_drop_rate(self):
        h = Harness()
        self.assertTrue(hasattr(h, "bottleneck_drop_rate"))
        # unreadable here (no `ip`), and that must be None, never 0.0
        self.assertIsNone(h.bottleneck_drop_rate(1.0))


class TestLiveLatencyIngestion(unittest.TestCase):
    """Live per-tick latency has never worked, and nothing said so.

    `_ingest_probes` reads `<label>.partial.json`. No workload was ever asked to
    write one: `UdpProbe` supports `partial_path` and writes it every
    `PARTIAL_EVERY_S`, but no caller passed a path, and no workload had a CLI
    flag for it. So the file never existed, `_ingest_probes` silently skipped,
    and every `rtt_p95` in every result.json was None.

    Nothing failed. The measurement was simply absent and the absence read like
    a zero -- the same failure this project has now produced several times over.

    The latency was measured; it was only written at exit, into `<label>.json`.
    """

    def test_probe_workloads_accept_a_partial_path(self):
        from pathlib import Path as _P
        base = _P(__file__).resolve().parents[1] / "testbed" / "workloads"
        for w in ("call.py", "game.py"):
            src = (base / w).read_text()
            self.assertIn("--partial-out", src, f"{w} has no flag")
            self.assertIn("partial_path=args.partial_out", src,
                          f"{w} does not pass it to UdpProbe")

    def test_bulk_and_video_are_not_given_an_unknown_flag(self):
        """They implement their own senders and have no UdpProbe, so the flag
        would abort them. They are also not latency probes."""
        from aciq.experiment import PROBE_KINDS
        self.assertEqual(set(PROBE_KINDS), {"call", "game"})
        self.assertNotIn("bulk", PROBE_KINDS)
        self.assertNotIn("video", PROBE_KINDS)

    def test_the_launcher_passes_the_partial_path(self):
        from pathlib import Path as _P
        src = (_P(__file__).resolve().parents[1] / "aciq"
               / "experiment.py").read_text()
        self.assertIn("--partial-out", src)
        self.assertIn('kind in PROBE_KINDS', src)
        self.assertIn(".partial.json", src)

    def test_the_partial_name_matches_what_ingestion_reads(self):
        """Writers and reader must agree on the filename, or this stays broken
        while looking fixed."""
        from pathlib import Path as _P
        src = (_P(__file__).resolve().parents[1] / "aciq"
               / "experiment.py").read_text()
        self.assertIn('json_out.with_suffix(".partial.json")', src)
        self.assertIn('f"{label}.partial.json"', src)

    def test_partial_writes_are_periodic_not_only_at_exit(self):
        from pathlib import Path as _P
        src = (_P(__file__).resolve().parents[1] / "testbed" / "workloads"
               / "udpx.py").read_text()
        self.assertIn("PARTIAL_EVERY_S", src)
        self.assertIn("def write_partial", src)


class TestProbeIngestionLandsInAClass(unittest.TestCase):
    """The path from a partial report to a measured latency, end to end.

    Worth testing without a kernel because every link in it can fail silently
    and produce the same result: no latency. `_ingest_probes` skips a missing
    file, `_verdict_class` returns None for a class it cannot name, and
    `MetricsCollector` records `no_probe` rather than failing. Three silent
    paths, one symptom.

    This run produced `rtt_p95: None` on every sample of every system for the
    whole project, and nothing raised.
    """

    @staticmethod
    def _source():
        """A source whose frame actually carries the interactive class.

        `poll()` reports what the frame holds, merged with what was ingested.
        An empty frame produces an empty result no matter what was ingested --
        which is itself a third way this path can fail silently.
        """
        from aciq.metrics import ClassCounters, CounterSnapshot, StaticSource
        from aciq.model import TrafficClass
        snap = CounterSnapshot(
            t=0.0,
            by_class={TrafficClass.INTERACTIVE: ClassCounters(rx_bytes=14000)})
        return StaticSource([snap for _ in range(40)])

    def _paths(self, d):
        from pathlib import Path as _P
        from aciq.experiment import RunPaths
        return RunPaths(_P(d))

    def test_a_partial_report_reaches_the_collector_as_latency(self):
        import json
        import tempfile
        from aciq.experiment import ExperimentRunner
        from aciq.metrics import MetricsCollector

        d = tempfile.mkdtemp()
        (self._paths(d).file("call.partial.json")).write_text(json.dumps({
            "p95": 0.9, "jitter_ms": 0.11, "loss_ratio": 0.0}))

        r = ExperimentRunner(launcher=None, harness=None,
                             results_dir=None, real_time=False)
        r._last_verdicts = [{"call": {"class": "realtime_interactive"}}]
        collector = MetricsCollector(source=self._source())
        r._ingest_probes(collector, self._paths(d),
                         [("call", 5001, 46)], "s2_wan_drop")
        frame = collector.poll()
        m = frame.per_class.get(__import__("aciq.model", fromlist=["x"])
                                .TrafficClass("realtime_interactive"))
        self.assertIsNotNone(m, "latency did not reach the interactive class")
        self.assertEqual(m.metric_status, "valid")
        self.assertAlmostEqual(m.rtt_p95, 0.9, places=6)

    def test_an_unclassifiable_flow_is_reported_as_no_probe(self):
        """The documented fallback, asserted so it cannot silently become 0.0."""
        import json
        import tempfile  # noqa: F401
        from aciq.experiment import ExperimentRunner
        from aciq.metrics import MetricsCollector

        d = tempfile.mkdtemp()
        (self._paths(d).file("call.partial.json")).write_text(json.dumps({
            "p95": 0.9, "jitter_ms": 0.11, "loss_ratio": 0.0}))
        r = ExperimentRunner(launcher=None, harness=None,
                             results_dir=None, real_time=False)
        r._last_verdicts = [{"call": {"class": "unclassified"}}]
        collector = MetricsCollector(source=self._source())
        r._ingest_probes(collector, self._paths(d),
                         [("call", 5001, 46)], "s2_wan_drop")
        frame = collector.poll()
        from aciq.model import TrafficClass
        vals = [v for v in frame.per_class.values()]
        self.assertTrue(all(v.metric_status == "no_probe" for v in vals),
                        "an unclassifiable flow must not report a latency")
        for v in vals:
            self.assertIsNone(v.rtt_p95)

    def test_a_missing_partial_file_is_skipped_silently_and_safely(self):
        import tempfile
        from aciq.experiment import ExperimentRunner
        from aciq.metrics import MetricsCollector
        d = tempfile.mkdtemp()
        r = ExperimentRunner(launcher=None, harness=None,
                             results_dir=None, real_time=False)
        collector = MetricsCollector(source=self._source())
        r._ingest_probes(collector, self._paths(d),
                         [("call", 5001, 46)], "s2_wan_drop")
        frame = collector.poll()
        for v in frame.per_class.values():
            self.assertIsNone(v.rtt_p95, "a missing file must not become 0.0")
