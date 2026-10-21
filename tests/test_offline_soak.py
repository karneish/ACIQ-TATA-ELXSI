"""Offline long-run stability: the controller's structures stay bounded.

`docs/gap-closure/resource-reliability.md` claimed the structures were "bounded
by construction" while marking long-run drift BLOCKED. The soak
(`tools/offline_soak.py`) found one that was not: `TrustStore` grew without
limit under source churn. These tests pin the bound so it cannot regress, and
run a short soak through the real pipeline to confirm the steady state is flat.

They are deliberately fast (a few seconds). The full 30-minute soak is a
measurement, not a unit test; this is the invariant behind it.
"""

from __future__ import annotations

import unittest

from aciq.capacity import CapacityEstimator, Measurement
from aciq.classify import MAX_TRUST_SOURCES, TrustStore
from aciq.flowtrack import FlowTracker, FLOW_EVICT_IDLE_S
from aciq.policy import build_plan

from tools.offline_soak import LIFETIME, _conntrack


class TestStructuresAreBounded(unittest.TestCase):
    def test_trust_store_is_bounded_under_source_churn(self):
        t = TrustStore(max_sources=32)
        for i in range(10_000):
            t.record_miss(f"10.0.{i // 256}.{i % 256}")
        self.assertLessEqual(len(t), 32)

    def test_the_default_trust_cap_is_finite(self):
        self.assertGreater(MAX_TRUST_SOURCES, 0)
        self.assertLess(MAX_TRUST_SOURCES, 10 ** 9)

    def test_flow_tracker_evicts_completed_flows(self):
        """Flows that conntrack no longer reports must be forgotten, so a
        churning flow population reaches a steady state rather than growing."""
        tr = FlowTracker()
        # Ticks 0..LIFETIME-1 carry the flows; after that the snapshot is empty
        # of them, so a later tick past the idle threshold must evict.
        tr.observe(_conntrack(0, 10), 0.0)
        self.assertEqual(len(tr._samples), 10)
        tr.observe(_conntrack(LIFETIME, 10), FLOW_EVICT_IDLE_S + 1.0)
        # The LIFETIME-window flows are new; the originals are long idle.
        for key in list(tr._samples):
            self.assertGreaterEqual(tr._samples[key].last_seen,
                                    FLOW_EVICT_IDLE_S)

    def test_an_empty_snapshot_does_not_wipe_the_tracker(self):
        """A transient read failure ("" -> {}) must not look like "the table
        emptied, drop everything"."""
        tr = FlowTracker()
        tr.observe(_conntrack(0, 5), 0.0)
        tr.observe("", 1.0)
        self.assertEqual(len(tr._samples), 5)


class TestShortSoakReachesSteadyState(unittest.TestCase):
    def test_the_live_structure_count_is_flat_not_growing(self):
        """Run the real per-tick arithmetic for a few seconds. The number of
        tracked flows must oscillate around the pool size, not climb."""
        from tools.offline_soak import soak
        r = soak(seconds=4.0, flows=60, sample_every=1.0)
        # With a fixed pool and finite lifetimes, tracked flows is bounded by
        # the pool, not by the tick count (which is far larger).
        self.assertLessEqual(r["tracked_flows"], 60)
        self.assertGreater(r["ticks"], r["tracked_flows"])

    def test_rss_does_not_grow_without_bound_over_a_short_soak(self):
        from tools.offline_soak import soak
        r = soak(seconds=4.0, flows=60, sample_every=1.0)
        # A leak would show as drift proportional to ticks. Allow a generous
        # allocator high-water margin; a real leak over thousands of ticks is
        # far larger than this.
        self.assertLess(r["rss_drift_mb"], 20.0,
                        f"rss drifted {r['rss_drift_mb']} MB in a 4 s soak")


class TestTheSoakDrivesTheRealPipeline(unittest.TestCase):
    def test_a_saturated_tick_moves_the_estimator(self):
        """The soak is only meaningful if it exercises the estimator, not just
        the flow tracker."""
        e = CapacityEstimator()
        e.observe(Measurement(t=1.0, goodput_mbps=20.0,
                              link_overlimit_rate_per_s=6000.0))
        e.observe(Measurement(t=2.0, goodput_mbps=20.0,
                              link_overlimit_rate_per_s=6000.0))
        self.assertGreater(e.current.mbps, 0.0)
        self.assertTrue(build_plan(e.current.mbps).rates)

    def test_the_soak_does_not_retain_per_tick_data(self):
        """The harness must not measure its own retention.

        An earlier revision appended one float per tick to a `tick_times` list
        and read it only at the end. Over a 30-minute run at 200 flows that was
        262k floats -- about 8-10 MB -- which the harness then reported as
        controller RSS drift. Only the first and last tick times are needed.
        """
        import inspect
        from tools import offline_soak
        src = inspect.getsource(offline_soak.soak)
        # No accumulation call on a per-tick container. `.append` on a list
        # named tick_times is the exact regression; assert the shape is gone.
        self.assertNotIn("tick_times", src,
                         "soak() appears to accumulate per-tick times again")
        self.assertNotIn("tick_times.append", src)


if __name__ == "__main__":
    unittest.main()
