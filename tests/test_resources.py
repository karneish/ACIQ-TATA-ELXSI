"""T5 — resource overhead must be measured, recorded and honest.

* `resources_of` aggregates the per-tick CPU/RSS evidence that MetricsFrame
  already writes; its None contract distinguishes "no samples recorded" from
  "zero overhead".
* `Harness.decision_latency` summarises the adapt_step timing ring; before the
  first decision there is NO latency (None), never a 0 ms p95.
* Every adapt_step call is timed, even the bookkeeping first tick that decides
  nothing -- a decision that costs 900 ms once in forty means nine hundred
  milliseconds, and the artefact must say so.
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aciq.experiment import resources_of  # noqa: E402
from aciq.harness import Harness  # noqa: E402
from aciq.metrics import ClassCounters  # noqa: E402
from aciq.model import TrafficClass  # noqa: E402


SAMPLES = [
    {"t": 0.0, "cpu_fraction": 0.10, "max_rss_bytes": 1000},
    {"t": 1.0, "cpu_fraction": 0.30, "max_rss_bytes": 1500},
    {"t": 2.0, "cpu_fraction": 0.20, "max_rss_bytes": 1500},
    {"t": 3.0, "cpu_fraction": "garbage-not-a-number"},  # must be skipped
]


class TestResourcesOf(unittest.TestCase):
    def test_mean_cpu_and_peak_rss(self):
        r = resources_of(SAMPLES)
        self.assertAlmostEqual(r["cpu_mean_frac"], (0.10 + 0.30 + 0.20) / 3)
        self.assertEqual(r["cpu_ticks"], 3)
        self.assertEqual(r["rss_max_bytes"], 1500)

    def test_non_numeric_slots_are_skipped_not_zeroed(self):
        r = resources_of(SAMPLES)
        # 4 ticks recorded, but only 3 CPU numbers exist: the count is 3.
        self.assertNotIn(4, (r["cpu_ticks"],))

    def test_no_samples_is_none(self):
        self.assertIsNone(resources_of([]))

    def test_decision_summary_is_carried(self):
        d = {"n": 5, "p50_ms": 0.1, "p95_ms": 0.4, "max_ms": 0.4}
        self.assertIs(resources_of(SAMPLES, decision=d)["decision_ms"], d)


class TestDecisionLatency(unittest.TestCase):
    def _harness(self):
        return Harness(runner=_NullRunner(), clock=time.monotonic)

    def test_none_before_any_decision(self):
        h = self._harness()
        self.assertIsNone(h.decision_latency())

    def test_first_bookkeeping_tick_is_measured_too(self):
        # The very first adapt_step has no previous counters: it is a no-op
        # that still costs a scheduling slot. It must appear in the ring.
        h = self._harness()
        counters = {TrafficClass.BULK_DOWNLOAD: ClassCounters(
            cls=TrafficClass.BULK_DOWNLOAD, handle="1:30", rx_bytes=0)}
        self.assertEqual(h.adapt_step(counters, dt=1.0, now=1.0),
                         (None, False))
        got = h.decision_latency()
        self.assertEqual(got["n"], 1)
        self.assertGreaterEqual(got["max_ms"], 0.0)

    def test_two_ticks_p95_geq_p50_geq_zero(self):
        h = self._harness()
        c = {TrafficClass.BULK_DOWNLOAD: ClassCounters(
            cls=TrafficClass.BULK_DOWNLOAD, handle="1:30", rx_bytes=0)}
        h.adapt_step(c, dt=1.0, now=1.0)
        # a second tick with new counters makes the body do real arithmetic
        h.adapt_step(
            {TrafficClass.BULK_DOWNLOAD: ClassCounters(
                cls=TrafficClass.BULK_DOWNLOAD, handle="1:30",
                rx_bytes=125000)},
            dt=1.0, now=2.0)
        got = h.decision_latency()
        self.assertEqual(got["n"], 2)
        self.assertGreaterEqual(got["p95_ms"], got["p50_ms"])
        self.assertGreaterEqual(got["p50_ms"], 0.0)
        self.assertGreaterEqual(got["max_ms"], got["p95_ms"])
        self.assertEqual(got["n"], len(h._decision_ms))

    def test_run_reset_clears_the_ring(self):
        from aciq.txn import FakeRunner
        h = Harness(runner=FakeRunner(auto_readback=True), clock=time.monotonic)
        h._decision_ms.append((0.0, 1.0))
        h.reset_for_run()
        self.assertIsNone(h.decision_latency(), None)


class _NullRunner:
    """No kernel calls anywhere: the ring is about the loop, not tc."""

    def run(self, argv):
        return 0, "", ""


if __name__ == "__main__":
    unittest.main()
