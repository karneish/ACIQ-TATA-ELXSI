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

    def test_the_bottleneck_is_outside_the_namespace_the_controller_writes(self):
        """ns wan / dev veth-w: ACIQ writes router/veth-lan, never this."""
        h = Harness()
        cmds = [" ".join(c) for c in h.set_capacity(10.0)]
        netem = [c for c in cmds if "netem" in c]
        self.assertTrue(netem)
        for c in netem:
            self.assertNotIn("router", c,
                             f"the bottleneck must not live where the "
                             f"controller writes: {c}")
            self.assertNotIn("veth-lan", c,
                             f"the bottleneck must not live on the device the "
                             f"controller writes: {c}")

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
