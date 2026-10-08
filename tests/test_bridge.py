"""Tests for the bridge: per-flow `tc flower` filters.

Mechanism, per `generate_flow_filter`: the classifier installs one flower filter
per flow, matching src/dst/proto/dport and pointing at an HTB class.

The DSCP-steering design this replaced is documented in that function, along
with the measurements that killed it. Nothing here asserts anything about DSCP
steering -- the nftables generators survive in `bridge.py` for reference, but
they are not part of enforcement and are not tested as though they were.

These tests are pure: no root, no netlink. The `executor` is injected, so the
ordering, the handle bookkeeping and the error handling are all checkable offline.
Whether the kernel honours the commands is `testbed/bridge_isolate.sh` (tests J
and K) and `testbed/gate.sh`.
"""

from __future__ import annotations

import unittest

from aciq.bridge import (
    CLASS_PRECEDENCE,
    FLOW_FILTER_PRIO,
    MARKED_CLASSES,
    MAX_FLOW_HANDLE,
    Bridge,
    BridgeError,
    FlowKey,
    family_of,
    generate_del_flow_filter,
    generate_flow_filter,
    generate_table,
    generate_teardown,
)
from aciq.marks import (
    CLASS_ADAPTIVE,
    CLASS_BULK,
    CLASS_INTERACTIVE,
    CLASS_LEASED,
    CLASS_UNCLASSIFIED,
)

V4 = FlowKey("203.0.113.2", "10.0.1.2", "udp", 7001)
V6 = FlowKey("fd00:2::2", "fd00:1::2", "udp", 7003)


def bare(argv: tuple[str, ...]) -> tuple[str, ...]:
    """Strip the `ip netns exec <ns>` prefix."""
    if len(argv) >= 4 and argv[:3] == ("ip", "netns", "exec"):
        return argv[4:]
    return argv


class Recorder:
    """Fake executor. Records argv and can be told to fail."""

    def __init__(self, fail_on: str | None = None, rc: int = 1):
        self.calls: list[tuple[str, ...]] = []
        self.fail_on = fail_on
        self.rc = rc

    def __call__(self, argv: tuple[str, ...]) -> tuple[int, str, str]:
        self.calls.append(argv)
        if self.fail_on and self.fail_on in " ".join(argv):
            return self.rc, "", f"synthetic failure matching {self.fail_on}"
        return 0, "", ""

    def joined(self) -> str:
        return " ".join(" ".join(c) for c in self.calls)


class TestFlowKey(unittest.TestCase):
    def test_element_text(self):
        self.assertEqual(V4.element(),
                         "{ 203.0.113.2 . 10.0.1.2 . udp . 7001 timeout 120s }")

    def test_udp_and_tcp(self):
        self.assertIn("udp", V4.element())
        self.assertIn("tcp", FlowKey("1.1.1.1", "2.2.2.2", "tcp", 80).element())

    def test_non_tcp_udp_rejected_with_a_reason(self):
        """`th dport` in the old design needed this; the flower filter needs
        `ip_proto`, which accepts more. Kept as a documented restriction."""
        for proto in ("icmp", "sctp", "gre", "esp"):
            with self.assertRaises(BridgeError) as cm:
                FlowKey("10.0.1.2", "203.0.113.9", proto, 1)
            self.assertIn("th dport", str(cm.exception))

    def test_protocol_case_normalised(self):
        self.assertEqual(FlowKey("10.0.1.2", "1.1.1.1", "TCP", 1).proto, "tcp")

    def test_dport_range(self):
        FlowKey("10.0.1.2", "1.1.1.1", "tcp", 0)
        FlowKey("10.0.1.2", "1.1.1.1", "tcp", 65535)
        for bad in (-1, 65536):
            with self.assertRaises(BridgeError):
                FlowKey("10.0.1.2", "1.1.1.1", "tcp", bad)

    def test_signature_is_hashable_and_stable(self):
        self.assertEqual(V4.signature, ("203.0.113.2", "10.0.1.2", "udp", 7001))
        self.assertEqual(hash(V4.signature), hash(V4.signature))


class TestFamilyOf(unittest.TestCase):
    def test_ipv4_and_ipv6(self):
        self.assertEqual(family_of("10.0.1.2"), "ip")
        self.assertEqual(family_of("fd00:2::2"), "ip6")

    def test_zone_id_does_not_raise(self):
        """A zone id raises in socket.inet_pton. It must not raise from deep
        inside a classification tick."""
        self.assertEqual(family_of("fe80::1%eth0"), "ip6")

    def test_method_delegates_to_the_helper(self):
        self.assertEqual(Bridge("d", "e").family_of("2001:db8::1"), "ip6")


class TestFlowFilter(unittest.TestCase):
    """The command that does the enforcement."""

    def test_matches_all_four_key_fields(self):
        argv = generate_flow_filter(V4, CLASS_ADAPTIVE, "veth-lan", 1)
        for field in ("src_ip", "dst_ip", "ip_proto", "dst_port"):
            self.assertIn(field, argv)
        self.assertEqual(argv[argv.index("src_ip") + 1], "203.0.113.2")
        self.assertEqual(argv[argv.index("dst_ip") + 1], "10.0.1.2")
        self.assertEqual(argv[argv.index("ip_proto") + 1], "udp")
        self.assertEqual(argv[argv.index("dst_port") + 1], "7001")

    def test_points_at_the_right_class(self):
        for cid, flowid in ((CLASS_INTERACTIVE, "1:10"), (CLASS_ADAPTIVE, "1:20"),
                            (CLASS_BULK, "1:30"), (CLASS_LEASED, "1:40"),
                            (CLASS_UNCLASSIFIED, "1:30")):
            argv = generate_flow_filter(V4, cid, "veth-lan", 1)
            self.assertEqual(argv[argv.index("flowid") + 1], flowid, cid)

    def test_unclassified_goes_to_the_default_class(self):
        """An unclassified flow has no filter at all in normal use; when one is
        forced it lands on the default rather than a class of its own."""
        self.assertEqual(generate_flow_filter(V4, CLASS_UNCLASSIFIED, "d", 1)[-1],
                         "1:30")

    def test_ipv6_filter_uses_protocol_ipv6(self):
        argv = generate_flow_filter(V6, CLASS_ADAPTIVE, "d", 1)
        self.assertEqual(argv[argv.index("protocol") + 1], "ipv6")

    def test_ipv4_filter_uses_protocol_ip(self):
        argv = generate_flow_filter(V4, CLASS_ADAPTIVE, "d", 1)
        self.assertEqual(argv[argv.index("protocol") + 1], "ip")

    def test_handle_is_present_and_padded(self):
        argv = generate_flow_filter(V4, CLASS_ADAPTIVE, "d", 0x2A)
        self.assertEqual(argv[argv.index("handle") + 1], "0x002a")

    def test_handle_range_enforced(self):
        for bad in (0, -1, MAX_FLOW_HANDLE + 1):
            with self.assertRaises(BridgeError):
                generate_flow_filter(V4, CLASS_ADAPTIVE, "d", bad)

    def test_precedes_the_dscp_ef_fallback(self):
        """An explicit classification must beat the EF heuristic -- the ordering
        the `seen` bit used to encode, now expressed in tc."""
        from aciq.tc import DSCP_FILTER_PRIO
        for proto in FLOW_FILTER_PRIO:
            self.assertLess(FLOW_FILTER_PRIO[proto], DSCP_FILTER_PRIO[proto])

    def test_prios_unique_per_protocol(self):
        """`tc` rejects two protocols at one priority with 'Protocol mismatch'."""
        self.assertEqual(len(set(FLOW_FILTER_PRIO.values())), len(FLOW_FILTER_PRIO))

    def test_no_fw_filter_is_emitted(self):
        """`tc fw` cannot read a mark on iproute2 6.1.0: only classid, indev and
        action are accepted."""
        for argv in (generate_flow_filter(V4, CLASS_ADAPTIVE, "d", 1),
                     generate_del_flow_filter("d", 1, "ip")):
            self.assertNotIn("fw", argv)

    def test_skip_hw_present(self):
        self.assertIn("skip_hw", generate_flow_filter(V4, CLASS_ADAPTIVE, "d", 1))

    def test_tokenisation(self):
        """No token may contain whitespace: a spec reaching tc as one token is
        the 'Specified qdisc kind is unknown' class of bug."""
        for argv in (generate_flow_filter(V4, CLASS_ADAPTIVE, "d", 1),
                     generate_del_flow_filter("d", 1, "ip")):
            for tok in argv:
                self.assertNotIn(" ", tok, argv)

    def test_namespace_prefix(self):
        argv = generate_flow_filter(V4, CLASS_ADAPTIVE, "d", 1, ns="router")
        self.assertEqual(argv[:4], ("ip", "netns", "exec", "router"))


class TestDeleteFilter(unittest.TestCase):
    def test_deletes_by_handle(self):
        """Deleting by re-stating a four-field match leaves the filter in place
        silently if any field is wrong."""
        argv = generate_del_flow_filter("veth-lan", 7, "ip", ns="router")
        self.assertEqual(argv[argv.index("handle") + 1], "0x0007")
        self.assertEqual(bare(argv)[:2], ("tc", "filter"))
        self.assertEqual(bare(argv)[2], "del")

    def test_carries_the_same_prio_and_protocol_as_the_add(self):
        add = generate_flow_filter(V4, CLASS_BULK, "d", 3)
        dele = generate_del_flow_filter("d", 3, "ip")
        for field in ("protocol", "prio"):
            self.assertEqual(add[add.index(field) + 1],
                             dele[dele.index(field) + 1], field)

    def test_ipv6_delete(self):
        argv = generate_del_flow_filter("d", 3, "ipv6")
        self.assertEqual(argv[argv.index("protocol") + 1], "ipv6")


class TestBridgeMarking(unittest.TestCase):
    def test_first_mark_installs_one_filter(self):
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).mark(V4, CLASS_ADAPTIVE)
        self.assertEqual(len(r.calls), 1)
        self.assertEqual(bare(r.calls[0])[:3], ("tc", "filter", "add"))

    def test_repeat_mark_in_same_class_is_a_no_op(self):
        """An add per tick per flow would spend the entire netlink budget for
        no behavioural change."""
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_ADAPTIVE)
        for _ in range(50):
            self.assertEqual(b.mark(V4, CLASS_ADAPTIVE), [])
        self.assertEqual(len(r.calls), 1)

    def test_reclassification_deletes_then_adds(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_BULK)
        b.mark(V4, CLASS_INTERACTIVE)
        self.assertEqual(len(r.calls), 3)
        self.assertEqual(bare(r.calls[1])[:3], ("tc", "filter", "del"))
        self.assertIn("1:10", r.calls[2])

    def test_reclassification_uses_a_fresh_handle(self):
        """A reused handle would let a stale delete remove another flow's filter."""
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_BULK)
        b.mark(V4, CLASS_ADAPTIVE)
        handles = [c[c.index("handle") + 1] for c in r.calls
                   if bare(c)[2] == "add"]
        self.assertEqual(len(set(handles)), 2)

    def test_handles_are_never_reused_across_flows(self):
        b = Bridge("d", "eth1", "router", executor=Recorder())
        for i in range(20):
            b.mark(FlowKey("1.1.1.1", "2.2.2.2", "tcp", 1000 + i), CLASS_BULK)
        handles = [s.handle for s in b.state.slots.values()]
        self.assertEqual(len(set(handles)), 20)

    def test_handle_exhaustion_raises(self):
        b = Bridge("d", "eth1", "router", executor=Recorder())
        b.state.next_handle = MAX_FLOW_HANDLE
        b.mark(V4, CLASS_BULK)
        with self.assertRaises(BridgeError):
            b.mark(FlowKey("1.1.1.1", "2.2.2.2", "tcp", 9999), CLASS_BULK)

    def test_flows_are_tracked_separately(self):
        b = Bridge("d", "eth1", "router", executor=Recorder())
        b.mark(V4, CLASS_BULK)
        b.mark(V6, CLASS_INTERACTIVE)
        self.assertEqual(len(b.state.slots), 2)

    def test_forget_removes_the_filter(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_LEASED)
        r.calls.clear()
        self.assertEqual(len(b.forget(V4)), 1)
        self.assertEqual(bare(r.calls[0])[:3], ("tc", "filter", "del"))
        self.assertEqual(len(b.state.slots), 0)

    def test_forget_on_an_unknown_flow_is_a_no_op(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        self.assertEqual(b.forget(V4), [])
        self.assertEqual(r.calls, [])

    def test_lease_release_then_remark(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_LEASED)
        b.forget(V4)
        b.mark(V4, CLASS_BULK)
        j = r.joined()
        self.assertIn("del", j)
        self.assertIn("1:30", j)

    def test_classify_flow_with_none_removes_the_filter(self):
        """An unclassified flow should fall through to the HTB default, which
        means no filter rather than one pointing at 1:30."""
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_ADAPTIVE)
        r.calls.clear()
        b.classify_flow(V4, None)
        self.assertEqual(bare(r.calls[0])[:3], ("tc", "filter", "del"))

    def test_classify_flow_with_a_class_installs(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.classify_flow(V4, CLASS_INTERACTIVE)
        self.assertEqual(bare(r.calls[0])[:3], ("tc", "filter", "add"))

    def test_ipv6_flow_uses_the_ipv6_protocol_and_prio(self):
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).mark(V6, CLASS_ADAPTIVE)
        argv = r.calls[0]
        self.assertEqual(argv[argv.index("protocol") + 1], "ipv6")
        self.assertEqual(argv[argv.index("prio") + 1],
                         str(FLOW_FILTER_PRIO["ipv6"]))

    def test_family_not_installed_is_skipped(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", families=("ip",), executor=r)
        self.assertEqual(b.mark(V6, CLASS_BULK), [])
        self.assertEqual(r.calls, [])


class TestLifecycle(unittest.TestCase):
    def test_teardown_removes_every_filter(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_BULK)
        b.mark(V6, CLASS_ADAPTIVE)
        r.calls.clear()
        b.teardown()
        # two filter deletes, then one table teardown per address family
        self.assertEqual(len(r.calls), 4)
        self.assertEqual(sum(1 for c in r.calls if "tc" in c), 2)
        self.assertTrue(all(bare(c)[:3] == ("tc", "filter", "del")
                            for c in r.calls if "tc" in c))
        self.assertEqual(b.state.slots, {})

    def test_teardown_also_clears_nftables_tables(self):
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).teardown()
        self.assertTrue(any("nft" in c for c in r.calls))

    def test_setup_clears_residue(self):
        """A filter left by a crashed run keeps routing its flow to a class that
        may no longer exist, and nothing else would remove it."""
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_BULK)
        r.calls.clear()
        b.setup()
        self.assertEqual(len(r.calls), 1)
        self.assertEqual(bare(r.calls[0])[:3], ("tc", "filter", "del"))

    def test_setup_on_a_clean_bridge_does_nothing(self):
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).setup()
        self.assertEqual(r.calls, [])

    def test_dry_run_executes_nothing(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r, dry_run=True)
        b.mark(V4, CLASS_BULK)
        b.teardown()
        self.assertEqual(r.calls, [])
        self.assertTrue(b.commands)

    def test_dry_run_plan_matches_commands(self):
        b = Bridge("d", "eth1", "router", dry_run=True)
        b.mark(V4, CLASS_BULK)
        b.mark(V6, CLASS_ADAPTIVE)
        self.assertEqual(b.plan(), [])

    def test_no_static_filter_install(self):
        """Per-flow filters are added by mark(); setup installs none. A static
        block would be dead code implying an enforcement path that does not
        exist."""
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).setup()
        self.assertFalse(any("flower" in " ".join(c) for c in r.calls))


class TestErrorHandling(unittest.TestCase):
    def test_add_failure_raises(self):
        """A failed add means the flow is NOT steered, and continuing silently
        would ship traffic to a class the classifier never chose."""
        r = Recorder(fail_on="filter add")
        with self.assertRaises(BridgeError):
            Bridge("d", "eth1", "router", executor=r).mark(V4, CLASS_BULK)

    def test_state_is_not_updated_when_the_add_fails(self):
        """Otherwise the next tick would think the filter exists and skip it."""
        r = Recorder(fail_on="filter add")
        b = Bridge("d", "eth1", "router", executor=r)
        with self.assertRaises(BridgeError):
            b.mark(V4, CLASS_BULK)
        self.assertEqual(len(b.state.slots), 0)

    def test_delete_failure_is_tolerated(self):
        """Teardown must not abort halfway: a filter that is already gone is the
        desired end state."""
        r = Recorder(fail_on="filter del")
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_BULK)
        r.calls.clear()
        b.teardown()          # must not raise
        self.assertEqual(b.state.slots, {})

    def test_teardown_completes_despite_a_failure(self):
        r = Recorder(fail_on="filter del")
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_BULK)
        b.mark(V6, CLASS_BULK)
        r.calls.clear()
        b.teardown()
        self.assertEqual(len(r.calls), 4, "two filter deletes plus two table teardowns")


class TestSetMechanismIsNotEnforcement(unittest.TestCase):
    """The nftables generators survive for reference but are not the path."""

    def test_install_sets_is_off_by_default(self):
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).setup()
        self.assertFalse(any("nft" in c and "add" in c for c in r.calls))

    def test_sets_are_removed_on_teardown_anyway(self):
        """Harmless residue removal, not enforcement."""
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).teardown()
        self.assertTrue(any(bare(generate_teardown("ip")) == bare(c) for c in r.calls))

    def test_table_generator_still_works(self):
        """Kept compiling and covered so the reference implementation does not
        rot while it sits unused."""
        self.assertEqual(generate_table("ip")[0],
                         ("nft", "add", "table", "ip", "aciq"))


class TestMarkedClassesOrder(unittest.TestCase):
    def test_precedence_is_leased_first(self):
        """Not used by the per-flow mechanism, but `sets` and the reference
        generators still depend on the order."""
        self.assertEqual(CLASS_PRECEDENCE[0], CLASS_LEASED)
        self.assertEqual(CLASS_PRECEDENCE[-1], CLASS_UNCLASSIFIED)

    def test_all_classes_have_a_flowid(self):
        for c in MARKED_CLASSES:
            argv = generate_flow_filter(V4, c, "d", 1)
            self.assertEqual(argv[argv.index("flowid") + 1][:1], "1")


if __name__ == "__main__":
    unittest.main()