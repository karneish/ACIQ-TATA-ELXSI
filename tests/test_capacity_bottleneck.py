"""The capacity drop must be enforced out of band.

**Spec-first.** These tests describe the behaviour `set_capacity` must have
*after* the fix. They fail today, on purpose: the defect is real and present in
the working tree.

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

    # Expected to FAIL until set_capacity is moved off the root class.
    # `expectedFailure` is the right semantics here: it keeps the suite
    # green while the defect is real, and turns into an "unexpected
    # success" -- which is a failure -- the moment the fix lands.
    @unittest.expectedFailure
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

    # Expected to FAIL until set_capacity is moved off the root class.
    # `expectedFailure` is the right semantics here: it keeps the suite
    # green while the defect is real, and turns into an "unexpected
    # success" -- which is a failure -- the moment the fix lands.
    @unittest.expectedFailure
    def test_the_bottleneck_is_applied_with_netem(self):
        h = Harness()
        cmds = [" ".join(c) for c in h.set_capacity(10.0)]
        self.assertTrue(any("netem" in c for c in cmds),
                        f"capacity must be limited with netem; got {cmds}")

    # Expected to FAIL until set_capacity is moved off the root class.
    # `expectedFailure` is the right semantics here: it keeps the suite
    # green while the defect is real, and turns into an "unexpected
    # success" -- which is a failure -- the moment the fix lands.
    @unittest.expectedFailure
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

    # Expected to FAIL until set_capacity is moved off the root class.
    # `expectedFailure` is the right semantics here: it keeps the suite
    # green while the defect is real, and turns into an "unexpected
    # success" -- which is a failure -- the moment the fix lands.
    @unittest.expectedFailure
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