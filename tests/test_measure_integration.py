"""Integration tests for the measurement path.

These use a real UDP socket on loopback. No namespaces, no `tc`, no root: they
prove the collector builds a *series* and that every reported figure is
recomputable from the raw observation stream, which is what §5.7 requires.

They do not prove kernel behaviour. The kernel-integrated version of this is
blocked in this shell (no `ip`/`tc`/`sudo`) and is recorded as such in
`docs/gap-closure/measurement-methodology.md`.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "testbed" / "workloads"))

from aciq.measure import VALID, Observation, compute          # noqa: E402
from aciq.metrics import EvaluationData, MetricsCollector      # noqa: E402
from aciq.model import TrafficClass                            # noqa: E402
from udpx import EchoSink, UdpProbe                            # noqa: E402

I = TrafficClass.INTERACTIVE


class _Source:
    """A counter source that never moves, so only telemetry varies."""

    def snapshot(self):
        from aciq.metrics import ClassCounters, CounterSnapshot
        return CounterSnapshot(
            t=__import__("time").monotonic(),
            by_class={I: ClassCounters(cls=I, handle="1:10", rx_bytes=0,
                                       tx_bytes=0, drops=0, overlimits=0,
                                       backlog_bytes=0)})


class TestRawObservationsAreComplete(unittest.TestCase):
    """The raw stream must contain what did *not* arrive, not just successes."""

    def test_every_sequence_appears_exactly_once(self):
        with tempfile.TemporaryDirectory() as d:
            obs = Path(d) / "call.obs.jsonl"
            sink = EchoSink(0).start()
            try:
                p = UdpProbe(dst="127.0.0.1", port=sink.sock.getsockname()[1],
                             pps=80, payload_bytes=64, label="call", obs_path=obs)
                rep = p.run(duration_s=1.0)
            finally:
                sink.stop()
            rows = [json.loads(l) for l in obs.read_text().splitlines() if l.strip()]
            seqs = [r["seq"] for r in rows]
            self.assertEqual(len(seqs), len(set(seqs)), "duplicate sequences")
            self.assertEqual(len(rows), rep["sent"],
                             "the raw stream is missing packets that never arrived")

    def test_every_derived_figure_is_recomputable_from_raw(self):
        """§5.7: derived metrics must be reconstructible, not merely asserted."""
        with tempfile.TemporaryDirectory() as d:
            obs = Path(d) / "call.obs.jsonl"
            sink = EchoSink(0).start()
            try:
                p = UdpProbe(dst="127.0.0.1", port=sink.sock.getsockname()[1],
                             pps=80, payload_bytes=64, label="call", obs_path=obs)
                rep = p.run(duration_s=1.0)
            finally:
                sink.stop()
            rows = [json.loads(l) for l in obs.read_text().splitlines() if l.strip()]
            m = compute([Observation(seq=r["seq"], sent_mono_s=r["sent_mono_s"],
                                     recv_mono_s=r["recv_mono_s"]) for r in rows])
            self.assertEqual(m.expected, rep["sent"])
            self.assertEqual(m.received, rep["received"])
            self.assertAlmostEqual(m.loss_ratio, rep["loss_ratio"], places=4)
            # Same definition on both sides, so they agree by construction.
            self.assertAlmostEqual(m.jitter_ms, rep["jitter_ms"], delta=0.5)


class TestTheSeriesIsLive(unittest.TestCase):
    """The defect this replaces: evaluation data was ingested once, after
    `collect()` returned, so every row of samples.jsonl carried the same final
    value -- a step function presented as a time series."""

    def test_the_generator_writes_an_incremental_partial_report(self):
        with tempfile.TemporaryDirectory() as d:
            part = Path(d) / "call.partial.json"
            sink = EchoSink(0).start()
            try:
                p = UdpProbe(dst="127.0.0.1", port=sink.sock.getsockname()[1],
                             pps=100, payload_bytes=64, label="call",
                             partial_path=part)
                p.run(duration_s=0.4)
                first = json.loads(part.read_text())
                p.run(duration_s=0.4)
                second = json.loads(part.read_text())
            finally:
                sink.stop()
            self.assertLess(first["sent"], second["sent"],
                            "the partial report did not advance mid-run")

    def test_the_collector_reports_a_value_that_changes_between_polls(self):
        c = MetricsCollector(_Source())
        c.poll()
        seen = []
        for i in range(6):
            c.ingest(EvaluationData(t=float(i), label="call",
                                    rtt_ms=5.0 + i, loss_ratio=0.0), cls=I)
            c.poll()
            seen.append(c.poll().per_class[I].rtt_p50)
        self.assertGreater(len(set(seen)), 1,
                           "latency never changed across ticks: not a series")

    def test_a_class_with_no_probe_is_none_not_zero(self):
        c = MetricsCollector(_Source())
        c.poll()
        m = c.poll().per_class[I]
        self.assertIsNone(m.rtt_p95)
        self.assertIsNone(m.loss_ratio)
        self.assertEqual(m.metric_status, "no_probe")

    def test_status_reports_valid_once_there_is_enough_data(self):
        c = MetricsCollector(_Source())
        c.poll()
        for i in range(15):
            c.ingest(EvaluationData(t=float(i), label="call", rtt_ms=4.0 + i * 0.1,
                                    jitter_ms=0.2, loss_ratio=0.0), cls=I)
        m = c.poll().per_class[I]
        self.assertEqual(m.metric_status, VALID)
        self.assertIsNotNone(m.rtt_p95)
        self.assertEqual(m.loss_ratio, 0.0)


class TestLossIsMeasuredNotInferred(unittest.TestCase):
    """§5.2: loss must come from sequence accounting, never from throughput."""

    def test_a_silent_port_produces_total_loss_not_no_data(self):
        """Nothing listening: every packet is lost, and that is a *result*, not a
        missing measurement."""
        c = MetricsCollector(_Source())
        c.poll()
        for i in range(20):
            c.ingest(EvaluationData(t=float(i), label="call",
                                    rtt_ms=None, loss_ratio=1.0), cls=I)
        m = c.poll().per_class[I]
        self.assertEqual(m.loss_ratio, 1.0)
        self.assertIsNone(m.rtt_p95, "latency was invented for a silent port")


if __name__ == "__main__":
    unittest.main()