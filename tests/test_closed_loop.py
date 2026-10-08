"""M5 -- the closed loop from observation to enforcement.

The gap these tests exist to close: `classify` decided a class, `Bridge`
installed a filter, and nothing called them in sequence. So every assertion here
is about the join -- that a decision reaches the kernel, and that the opt-in
boundary holds.
"""

import json
import time
import unittest

from aciq.bridge import Bridge, FlowKey
from aciq.classify import FlowFeatures
from aciq.corrections import CorrectionStore
from aciq.closedloop import CLASS_ID_OF, Enforcer, key_of
from aciq.harness import Harness
from aciq.model import Flow, TrafficClass
from aciq import tc

CAP = 100.0
CALL = Flow("10.0.1.2", 50000, "203.0.113.2", 3478, "udp")


class FakeExec:
    """Records argv and answers tc's -j listing with nothing on the device."""

    def __init__(self):
        self.calls = []

    def __call__(self, argv):
        self.calls.append(argv)
        if "-j" in argv:
            return 0, json.dumps([]), ""
        return 0, "", ""


def bare(argv):
    """Strip the `ip netns exec <ns>` prefix.

    Stripped positionally, not by filtering the argument out: "ip" is also the
    `protocol ip` argument of every IPv4 filter, so a filter-based strip deletes
    the protocol from the command it is supposed to be inspecting.
    """
    if len(argv) >= 4 and argv[:3] == ("ip", "netns", "exec"):
        return argv[4:]
    return argv


def feats(flow=CALL, **kw):
    return FlowFeatures(flow=flow, **kw)


def mature(mbps=4.69, proto="tcp", dport=443, flow=None, **kw):
    """A flow the measured generator produces, at a stated rate.

    The rate is set through mbps rather than raw bytes because the classifier
    reasons in rate, and byte counts make the same verdict look like a different
    test than the one in test_classify.
    """
    flow = flow or Flow("10.0.1.2", 1, "1.1.1.1", dport, proto)
    base = dict(rx_bytes=int(mbps * 1e6 / 8 * 10), packets=6000, age_s=10.0,
                avg_packet_bytes=1200, duty_cycle=1.0)
    base.update(kw)
    return FlowFeatures(flow=flow, **base)


def tiny(flow=None, **kw):
    """Below the maturity floor: the classifier declines.

    Defaults to the *same tuple* as `mature()`, deliberately: "was steered, now
    declines" is a statement about one flow changing its mind, and it only means
    that if both halves describe the same 4-tuple.
    """
    flow = flow or Flow("10.0.1.2", 1, "1.1.1.1", 443, "tcp")
    return FlowFeatures(flow=flow, rx_bytes=100, packets=1, age_s=0.1, **kw)


def enforcer(**kw):
    exec_ = FakeExec()
    b = Bridge("veth-lan", "eth0", "router", executor=exec_)
    e = Enforcer(b, corrections=CorrectionStore(path="/nonexistent/does-not-exist"),
                 capacity_mbps=CAP, **kw)
    return e, exec_


def adds(exec_):
    return [c for c in exec_.calls if bare(c)[:3] == ("tc", "filter", "add")]


def arg(argv, flag):
    """Value following `flag`, or None.

    Positional indexing into a tc argv is the third tool-output coupling this
    project has written; looking the flag up does not move when tc reorders its
    own arguments.
    """
    a = list(argv)
    return a[a.index(flag) + 1] if flag in a else None


class TestOptIn(unittest.TestCase):
    """Enforcement must be something a run asks for, not something it inherits."""

    def test_harness_starts_reporting_only(self):
        self.assertFalse(Harness().enforcement_enabled)

    def test_enable_with_an_injected_executor_needs_no_root(self):
        h = Harness()
        h.enable_enforcement(executor=FakeExec())
        self.assertTrue(h.enforcement_enabled)

    def test_enforce_returns_none_when_disabled(self):
        """None, not a raise: most callers run reporting-only, and a run that
        classified without enforcing is a legitimate thing to want."""
        self.assertIsNone(Harness().enforce(mature()))

    def test_enable_is_idempotent(self):
        """Two bridges would each enumerate and delete the same filters on
        teardown."""
        h = Harness()
        a = h.enable_enforcement(executor=FakeExec())
        b = h.enable_enforcement(executor=FakeExec())
        self.assertIs(a, b)

    def test_enable_wires_up_the_runners_device_and_namespace(self):
        h = Harness(dev="veth-lan", ns_router="router")
        e = h.enable_enforcement(executor=FakeExec())
        self.assertEqual(e.bridge.dev, "veth-lan")
        self.assertEqual(e.bridge.ns, "router")

    def test_disable_tears_down_rather_than_just_dropping_the_reference(self):
        """A filter that outlives the enforcer keeps steering a flow to a class
        nothing is watching -- the residue check 20 was written to catch."""
        h = Harness()
        exec_ = FakeExec()
        h.enable_enforcement(executor=exec_)
        h.enforce(mature())
        exec_.calls.clear()
        h.disable_enforcement()
        self.assertTrue([c for c in exec_.calls
                         if bare(c)[:3] == ("tc", "filter", "del")],
                        "disable_enforcement left filters installed")
        self.assertFalse(h.enforcement_enabled)


class TestDecisionReachesTheKernel(unittest.TestCase):
    """The actual point of the join."""

    def test_adaptive_installs_a_flower_filter_at_our_priority(self):
        e, exec_ = enforcer()
        v = e.apply(mature())
        self.assertEqual(v.cls, TrafficClass.ADAPTIVE)
        self.assertEqual(v.label, "adaptive")
        got = adds(exec_)
        self.assertEqual(len(got), 1, got)
        self.assertEqual(arg(got[0], "prio"), "5", "IPv4 flower filters live at prio 5")

    def test_the_filter_points_at_the_class_the_classifier_chose(self):
        e, exec_ = enforcer()
        v = e.apply(mature())
        got = adds(exec_)[0]
        # flower steers with flowid, not classid: flowid is the HTB class the
        # matched packets land in, which is the whole point of the filter. The
        # bridge's own class id is not the flowid -- it maps through tc.CLASS_IDS
        # so the bridge and the tree cannot disagree about a classid.
        self.assertEqual(v.class_id, CLASS_ID_OF[v.cls])
        self.assertEqual(arg(got, "flowid"), tc.CLASS_IDS[v.cls], got)

    def test_ipv6_gets_its_own_priority(self):
        e, exec_ = enforcer()
        e.apply(mature(flow=Flow("fd00:1::2", 5000, "fd00:2::2", 3478, "udp")))
        got = adds(exec_)[0]
        self.assertEqual(arg(got, "prio"), "6", "IPv6 flower filters live at prio 6")

    def test_a_flow_that_never_gets_a_verdict_installs_nothing(self):
        """Below the maturity floor the classifier declines, and declining must
        not mean "point it somewhere plausible"."""
        e, exec_ = enforcer()
        v = e.apply(tiny())
        self.assertIsNone(v.cls)
        self.assertEqual(v.label, "unclassified")
        self.assertEqual(adds(exec_), [])

    def test_reclassifying_repoints_the_same_filter(self):
        """Same 4-tuple, different verdict: the filter must be replaced, not
        duplicated. A duplicate would double-count the flow's traffic."""
        e, exec_ = enforcer()
        e.apply(mature())
        e.apply(mature(mbps=88.14))
        dels = [c for c in exec_.calls if bare(c)[:3] == ("tc", "filter", "del")]
        self.assertTrue(dels, "the old filter was never removed")

    def test_an_unchanged_verdict_installs_nothing_new(self):
        """mark() is a no-op for a flow already in its class. At N flows a
        redundant add per flow per tick is the whole budget."""
        e, exec_ = enforcer()
        e.apply(mature())
        before = len(adds(exec_))
        e.apply(mature())
        self.assertEqual(len(adds(exec_)), before)


class TestCorrectionsReachTheKernel(unittest.TestCase):
    """M7 -- a user's override must beat inference all the way to tc."""

    def test_a_correction_overrides_the_classifier(self):
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.jsonl")
            store = CorrectionStore(path=p)
            target = Flow("10.0.1.2", 1, "1.1.1.1", 443, "tcp")
            store.record(target, TrafficClass.LEASED, reason="user asked")
            store.reload()
            e, exec_ = enforcer()
            e.corrections = CorrectionStore(path=p)
            e.corrections.reload()
            v = e.apply(mature(flow=target))
            self.assertEqual(v.cls, TrafficClass.LEASED)
            self.assertTrue(v.corrected)
            self.assertEqual(arg(adds(exec_)[0], "flowid"), tc.CLASS_IDS[TrafficClass.LEASED])

    def test_an_expired_correction_stops_applying(self):
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.jsonl")
            store = CorrectionStore(path=p, ttl_s=60)
            store.record(Flow("10.0.1.2", 1, "1.1.1.1", 443, "tcp"),
                         TrafficClass.LEASED, reason="user asked")
            e, exec_ = enforcer()
            e.corrections = CorrectionStore(path=p, ttl_s=60)
            e.corrections.reload()
            # now must be *after* the record's timestamp; an epoch far in the
            # past leaves now - created_at negative, which is not "expired".
            v = e.apply(mature(), now=time.time() + 3600)
            self.assertFalse(v.corrected, "a correction past its TTL still applied")
            self.assertNotEqual(v.cls, TrafficClass.LEASED)


class TestCapacityIsMeasured(unittest.TestCase):
    def test_capacity_is_passed_to_the_classifier(self):
        """M2's measurement, never class 1:1's configured rate."""
        e, exec_ = enforcer()
        e.set_capacity(20.0)
        self.assertEqual(e.capacity_mbps, 20.0)

    def test_harness_feeds_its_measured_capacity_to_the_enforcer(self):
        """Pushed on the next enforce(), not on set_capacity(): capacity is
        pushed where a verdict is actually produced, so a run that measures
        capacity but classifies no flows does no redundant work."""
        h = Harness()
        h.enable_enforcement(executor=FakeExec())
        h._enforcer.capacity_mbps = 999.0
        h.set_capacity(37.5)
        h.enforce(mature())
        self.assertEqual(h._enforcer.capacity_mbps, 37.5)


class TestTrustSurvivesAcrossFlows(unittest.TestCase):
    def test_trust_is_not_reset_per_call(self):
        """A per-call TrustStore would give every source confidence 1.0 on each
        tick, so an EF-claiming source that had already lost trust would regain
        it immediately and the decay would be inert."""
        e, _ = enforcer()
        first = e.trust
        e.apply(mature())
        self.assertIs(e.trust, first)


class TestKeys(unittest.TestCase):
    def test_source_port_is_not_part_of_the_match_key(self):
        """The kernel flower filter cannot match sport anyway, and including it
        would install a second filter for the same real flow."""
        a = Flow("10.0.1.2", 1111, "203.0.113.2", 3478, "udp")
        b = Flow("10.0.1.2", 2222, "203.0.113.2", 3478, "udp")
        self.assertEqual(key_of(feats(a)), key_of(feats(b)))
        self.assertEqual(key_of(feats(a)), FlowKey("10.0.1.2", "203.0.113.2", "udp", 3478))

    def test_protocol_is_case_normalised(self):
        e, _ = enforcer()
        self.assertEqual(key_of(feats(Flow("10.0.1.2", 1, "203.0.113.2", 1, "TCP"))).proto,
                         "tcp")


class TestVerdictReport(unittest.TestCase):
    def test_str_names_the_tier_that_decided(self):
        e, _ = enforcer()
        self.assertIn("adaptive", str(e.apply(mature())))

    def test_a_declined_verdict_for_a_never_steered_flow_runs_nothing(self):
        """`forget` deliberately issues a delete even with no local slot, so a
        fresh Bridge can release a filter it did not install. Once per tick that
        is a netlink round trip per immature flow for a filter that never
        existed, so apply() short-circuits when there is provably nothing there.
        Asserted both ways: the shortcut must not swallow the case below."""
        e, exec_ = enforcer()
        v = e.apply(tiny())
        self.assertFalse(v.changed)
        self.assertEqual(exec_.calls, [], "a declined verdict touched the device")
        self.assertEqual(adds(exec_), [], "a declined verdict installed a filter")

    def test_a_declined_verdict_for_a_previously_steered_flow_does_delete(self):
        """The case the shortcut must not swallow: the flow was steered on an
        earlier tick, so there IS a filter to remove. Suppressing this would
        reintroduce exactly the residue check 20 was written to catch."""
        e, exec_ = enforcer()
        self.assertTrue(e.apply(mature()).changed)
        exec_.calls.clear()
        v = e.apply(tiny())
        self.assertTrue(v.changed)
        self.assertTrue([c for c in exec_.calls
                         if bare(c)[:3] == ("tc", "filter", "del")],
                        "a steered-then-declined flow kept its filter")

    def test_the_shortcut_does_not_persist_a_stale_decision(self):
        e, _ = enforcer()
        e.apply(mature())
        e.apply(tiny())
        self.assertFalse(e.decisions[key_of(mature())].class_id)


if __name__ == "__main__":
    unittest.main()