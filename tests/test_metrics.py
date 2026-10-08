"""M5 metrics collector tests. No root, no network, no tc."""

from __future__ import annotations

import json
import time
import unittest

from aciq.metrics import (
    ClassCounters,
    CounterSnapshot,
    EvaluationData,
    MetricsCollector,
    StaticSource,
    TcJsonSource,
    goodput_mbps,
    jain_fairness,
    parse_tc_class_json,
    percentiles,
    rate_per_s,
)
from aciq.model import TrafficClass

B = TrafficClass.BULK
I = TrafficClass.INTERACTIVE


def snap(t, **kw):
    return CounterSnapshot(t=t, by_class={
        cls: ClassCounters(cls=cls, **vals) for cls, vals in kw.items()
    })


class TestPureFunctions(unittest.TestCase):
    def test_goodput(self):
        # 12.5 MB in 1 s == 100 Mbps
        self.assertAlmostEqual(goodput_mbps(0, 12_500_000, 1.0), 100.0, places=6)

    def test_goodput_guards_zero_dt(self):
        self.assertEqual(goodput_mbps(0, 1000, 0.0), 0.0)

    def test_goodput_guards_counter_reset(self):
        # counters going backwards means the class was recreated, not negative throughput
        self.assertEqual(goodput_mbps(5000, 100, 1.0), 0.0)

    def test_rate_per_s(self):
        self.assertAlmostEqual(rate_per_s(0, 50, 2.0), 25.0)

    def test_percentiles_ordered(self):
        p = percentiles([1.0, 2.0, 3.0, 4.0, 100.0])
        self.assertLessEqual(p["p50"], p["p95"])
        self.assertLessEqual(p["p95"], p["p99"])

    def test_percentiles_empty(self):
        self.assertEqual(percentiles([])["p50"], 0.0)

    def test_jain_bounds(self):
        self.assertAlmostEqual(jain_fairness([10, 10, 10]), 1.0, places=9)
        # a single hog is bounded below by 1/n, not zero
        self.assertAlmostEqual(jain_fairness([100, 1, 1]), 0.3467, places=3)
        # Empty is None, not 0.0. Both baselines have a single class, so there is
        # no allocation to be fair or unfair about; 0.0 claimed they were maximally
        # unfair, which is backwards, and put a number in the artefact that looked
        # like a measurement.
        self.assertIsNone(jain_fairness([]))
        # a single flow cannot be unfair to anything either
        self.assertEqual(jain_fairness([5.0]), 1.0)


class TestTheParentIsNotLabelledInteractive(unittest.TestCase):
    """Every sample of every system recorded the parent counter as
    link.cls="realtime_interactive", because it was built with that class and a
    comment claiming the value was never used. It was used -- by `vars()` in
    every sample written."""

    def test_the_parent_carries_no_traffic_class(self):
        from aciq.metrics import CounterSnapshot, ClassCounters
        snap = CounterSnapshot(t=0.0, link=ClassCounters(cls=None, handle="1:1",
                                                          rx_bytes=99))
        self.assertIsNone(snap.link.cls)

    def test_the_parent_names_its_real_classid(self):
        self.assertEqual(CounterSnapshot(
            t=0.0, link=ClassCounters(cls=None, handle="1:1")).link.handle, "1:1")


class TestUnmappedClassesAreVisible(unittest.TestCase):
    """Both baselines have one class at 1:50, which is not an ACIQ class.

    It was dropped, so per_class came back {} and "we have no name for the
    baselines' traffic" looked exactly like "the baselines moved no traffic".
    """

    # Shaped like the real `tc -s class show` output. Two attempts were needed: the
    # first invented a format, and the second omitted `rate` from the leaf line --
    # and _CLASS_RE requires rate, so the parser dropped the class silently. Real
    # leaves do carry a rate (the tree sets one on every class), so the fixture was
    # wrong rather than the parser. Recorded as a known sharp edge below.
    TEXT = ("class htb 1:1 root prio 0 rate 100Mbit ceil 100Mbit burst 15Kb\n"
            "  Sent 4000000 bytes 4000 pkt (dropped 0, overlimits 3 requeues 0)\n"
            "class htb 1:50 parent 1:1 leaf pfifo prio 0 rate 100Mbit ceil 100Mbit\n"
            "  Sent 4000000 bytes 4000 pkt (dropped 0, overlimits 0 requeues 0)")

    def test_an_unnamed_class_is_kept_under_its_classid(self):
        from aciq.metrics import TextClassSource
        src = TextClassSource(runner=lambda *a, **k: type(
            "R", (), {"returncode": 0, "stdout": self.TEXT})())
        snap = src.snapshot()
        self.assertIn("1:50", snap.unmapped)
        self.assertEqual(snap.unmapped["1:50"].rx_bytes, 4000000)

    def test_it_is_not_silently_folded_into_an_aciq_class(self):
        """Mapping 1:50 onto BULK would have been wrong: BULK means "the class
        that deliberately gets the leftovers", and a baseline's single class is
        not that."""
        from aciq.metrics import TextClassSource
        src = TextClassSource(runner=lambda *a, **k: type(
            "R", (), {"returncode": 0, "stdout": self.TEXT})())
        self.assertEqual(src.snapshot().by_class, {})

    def test_the_parent_is_not_in_unmapped_either(self):
        from aciq.metrics import TextClassSource
        src = TextClassSource(runner=lambda *a, **k: type(
            "R", (), {"returncode": 0, "stdout": self.TEXT})())
        snap = src.snapshot()
        self.assertNotIn("1:1", snap.unmapped)
        self.assertIsNotNone(snap.link)


class TestTcJsonParsing(unittest.TestCase):
    SAMPLE = json.dumps([
        {"kind": "htb", "handle": "1:10", "stats": {"bytes": 1000, "drops": 2, "overlimits": 5}},
        {"kind": "htb", "handle": "1:30", "stats": {"bytes": 2000, "drops": 0, "overlimits": 1}},
        {"kind": "htb", "handle": "1:99", "stats": {"bytes": 9999}},  # unmapped -> ignored
    ])

    def test_parses_known_handles(self):
        s = parse_tc_class_json(self.SAMPLE)
        self.assertEqual(s.by_class[I].rx_bytes, 1000)
        self.assertEqual(s.by_class[I].drops, 2)
        self.assertEqual(s.by_class[B].rx_bytes, 2000)

    def test_ignores_unmapped_handles(self):
        s = parse_tc_class_json(self.SAMPLE)
        self.assertEqual(len(s.by_class), 2)

    def test_accepts_stats2_key(self):
        raw = json.dumps([{"handle": "1:30", "stats2": {"bytes": 77, "drops": 1}}])
        s = parse_tc_class_json(raw)
        self.assertEqual(s.by_class[B].rx_bytes, 77)

    def test_malformed_json_is_not_fatal(self):
        s = parse_tc_class_json("{not json")
        self.assertEqual(s.by_class, {})

    def test_missing_fields_default_zero(self):
        s = parse_tc_class_json(json.dumps([{"handle": "1:30"}]))
        self.assertEqual(s.by_class[B].rx_bytes, 0)
        self.assertEqual(s.by_class[B].drops, 0)

    def test_backlog_from_child_qdisc(self):
        raw = json.dumps([{"handle": "1:30", "stats": {"bytes": 1},
                          "children": [{"kind": "fq_codel", "stats": {"backlog": 4096}}]}])
        s = parse_tc_class_json(raw)
        self.assertEqual(s.by_class[B].backlog_bytes, 4096)

    def test_source_survives_command_failure(self):
        class Boom:
            def __call__(self, *a, **k):
                raise OSError("no tc here")
        s = TcJsonSource(runner=Boom()).snapshot()
        self.assertEqual(s.by_class, {})


class TestCollector(unittest.TestCase):
    def test_first_poll_has_no_rates(self):
        c = MetricsCollector(StaticSource([snap(0.0, **{B: {"rx_bytes": 1000}})]))
        f = c.poll()
        self.assertEqual(f.per_class[B].goodput_mbps, 0.0)

    def test_second_poll_computes_goodput(self):
        src = StaticSource([
            snap(0.0, **{B: {"rx_bytes": 0}}),
            snap(1.0, **{B: {"rx_bytes": 12_500_000}}),
        ])
        c = MetricsCollector(src)
        c.poll()
        f = c.poll()
        self.assertAlmostEqual(f.per_class[B].goodput_mbps, 100.0, places=6)

    def test_drop_rate_computed(self):
        src = StaticSource([
            snap(0.0, **{B: {"drops": 0}}),
            snap(2.0, **{B: {"drops": 10}}),
        ])
        c = MetricsCollector(src)
        c.poll()
        self.assertAlmostEqual(c.poll().per_class[B].drop_rate_per_s, 5.0)

    def test_overlimit_rate_computed(self):
        src = StaticSource([
            snap(0.0, **{B: {"overlimits": 0}}),
            snap(4.0, **{B: {"overlimits": 8}}),
        ])
        c = MetricsCollector(src)
        c.poll()
        self.assertAlmostEqual(c.poll().per_class[B].overlimit_rate_per_s, 2.0)

    def test_backlog_reported(self):
        c = MetricsCollector(StaticSource([snap(0.0, **{B: {"backlog_bytes": 8192}})]))
        self.assertEqual(c.poll().per_class[B].backlog_bytes, 8192)

    def test_fairness_across_classes(self):
        src = StaticSource([
            snap(0.0, **{I: {"rx_bytes": 0}, B: {"rx_bytes": 0}}),
            snap(1.0, **{I: {"rx_bytes": 1_250_000}, B: {"rx_bytes": 1_250_000}}),
        ])
        c = MetricsCollector(src)
        c.poll()
        f = c.poll()
        self.assertAlmostEqual(f.fairness, 1.0, places=6)

    def test_evaluation_data_feeds_percentiles(self):
        c = MetricsCollector(StaticSource([snap(0.0, **{I: {"rx_bytes": 0}})]))
        for v in (10.0, 12.0, 11.0, 40.0):
            c.ingest(EvaluationData(t=0.0, label=I.value, rtt_ms=v))
        f = c.poll()
        self.assertGreater(f.per_class[I].rtt_p50, 0.0)
        self.assertGreater(f.per_class[I].rtt_p99, f.per_class[I].rtt_p50)

    def test_evaluation_window_is_bounded(self):
        c = MetricsCollector(StaticSource([snap(0.0, **{I: {"rx_bytes": 0}})]), window=5)
        for i in range(50):
            c.ingest(EvaluationData(t=0.0, label=I.value, rtt_ms=float(i)))
        self.assertEqual(len(c.rtts(I.value)), 5)

    def test_loss_ratio_propagates(self):
        c = MetricsCollector(StaticSource([snap(0.0, **{I: {"rx_bytes": 0}})]))
        c.ingest(EvaluationData(t=0.0, label=I.value, loss_ratio=0.25))
        self.assertAlmostEqual(c.poll().per_class[I].loss_ratio, 0.25)

    def test_cpu_fraction_zero_on_a_tiny_window(self):
        """getrusage is tick-granular, so over a sub-tick window the CPU delta
        can exceed the wall delta and the ratio exceeds 1.0. Reporting 0.0 for
        an unusably short window is correct; reporting a bogus figure is not,
        because CPU overhead is a graded metric."""
        c = MetricsCollector(StaticSource([snap(0.0, **{B: {"rx_bytes": 0}})]))
        self.assertEqual(c.poll().cpu_fraction, 0.0)

    def test_cpu_fraction_is_measured_over_a_real_window(self):
        c = MetricsCollector(StaticSource([snap(0.0, **{B: {"rx_bytes": 0}})]))
        t0 = time.monotonic()
        while time.monotonic() - t0 < 0.12:  # busy enough to burn real CPU
            sum(i * i for i in range(2000))
        f = c.poll()
        self.assertGreaterEqual(f.cpu_fraction, 0.0)
        self.assertLessEqual(f.cpu_fraction, 1.5)


class TestTextClassSource(unittest.TestCase):
    """The reader the experiment actually uses. Gate check 10 proved the text
    path; the JSON path returned empty and made every sample `per_class: {}`."""

    SAMPLE = ("class htb 1:10 root prio 0 rate 40Mbit ceil 100Mbit burst 15Kb\n"
              "  Sent 4000000 bytes 4000 pkt (dropped 1, overlimits 900 requeues 0)\n"
              "class htb 1:30 root prio 0 rate 30Mbit ceil 100Mbit burst 15Kb\n"
              "  Sent 9000000 bytes 9000 pkt (dropped 12, overlimits 4200 requeues 0)")

    def _src(self, out, argv_seen=None):
        from aciq.metrics import TextClassSource

        class R:
            returncode = 0
            stdout = out

        def run(argv, **kw):
            if argv_seen is not None:
                argv_seen.append(argv)
            return R()

        return TextClassSource(runner=run)

    def test_reads_counters_per_class(self):
        s = self._src(self.SAMPLE).snapshot()
        self.assertEqual(len(s.by_class), 2)
        self.assertEqual(s.by_class[TrafficClass.BULK].rx_bytes, 9000000)
        self.assertEqual(s.by_class[TrafficClass.BULK].overlimits, 4200)
        self.assertEqual(s.by_class[TrafficClass.BULK].drops, 12)

    def test_maps_interactive_class(self):
        s = self._src(self.SAMPLE).snapshot()
        self.assertEqual(s.by_class[TrafficClass.INTERACTIVE].rx_bytes, 4000000)

    def test_reader_asks_for_statistics(self):
        """`tc class show` without -s prints only configuration and no `Sent`
        line, so every counter came back 0.0 while classes parsed fine."""
        seen = []
        self._src(self.SAMPLE, seen).snapshot()
        self.assertTrue(seen, "no command was issued")
        self.assertIn("-s", seen[0])

    def test_command_failure_is_not_fatal(self):
        from aciq.metrics import TextClassSource

        class Boom:
            returncode = 1
            stdout = ""

        self.assertEqual(TextClassSource(runner=lambda *a, **k: Boom()).snapshot().by_class, {})

    def test_missing_binary_is_not_fatal(self):
        from aciq.metrics import TextClassSource

        def boom(*a, **k):
            raise FileNotFoundError("ip")

        self.assertEqual(TextClassSource(runner=boom).snapshot().by_class, {})


class TestSeparation(unittest.TestCase):
    """The structural guarantee: M2 consumes ClassCounters, never latency."""

    def test_evaluation_data_is_not_a_counter(self):
        self.assertNotIsInstance(
            EvaluationData(t=0.0, label="x", rtt_ms=1.0), ClassCounters)

    def test_counter_carries_no_latency_fields(self):
        c = ClassCounters(cls=I)
        self.assertFalse(hasattr(c, "rtt_ms"))
        self.assertFalse(hasattr(c, "jitter_ms"))


if __name__ == "__main__":
    unittest.main()
