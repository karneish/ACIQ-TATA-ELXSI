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

import json
import unittest

from aciq.bridge import (
    CLASS_PRECEDENCE,
    FLOW_FILTER_PRIO,
    MARKED_CLASSES,
    MAX_FLOW_HANDLE,
    handle_for,
    enumerate_flow_filters,
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
    """Fake executor.

    Records argv, can be told to fail, and answers `tc -j filter show` with a
    realistic listing -- because setup() and teardown() now read the tc tree to
    clear filters a previous run left, and an executor that returns "" for
    everything would make that path untested.
    """

    def __init__(self, fail_on: str | None = None, rc: int = 1,
                 filter_json: str | None = None):
        self.calls: list[tuple[str, ...]] = []
        self.fail_on = fail_on
        self.rc = rc
        self.filter_json = filter_json

    def __call__(self, argv: tuple[str, ...]) -> tuple[int, str, str]:
        self.calls.append(argv)
        if "-j" in argv:
            return 0, (TC_FILTER_JSON if self.filter_json is None
                       else self.filter_json), ""
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


class TestHandlesAreDerived(unittest.TestCase):
    """tc's handle namespace is per DEVICE, so a per-process counter collides.

    Gate check 17 found this: every gate helper is a fresh Bridge, so each one
    restarted its counter at 1 and the second `tc filter add` failed with
    "Filter already exists".
    """

    def test_same_flow_same_handle(self):
        self.assertEqual(handle_for(V4), handle_for(V4))

    def test_different_flows_different_handles(self):
        other = FlowKey("203.0.113.2", "10.0.1.2", "udp", 7002)
        self.assertNotEqual(handle_for(V4), handle_for(other))

    def test_every_field_participates(self):
        base = handle_for(V4)
        for k in (FlowKey("203.0.113.3", "10.0.1.2", "udp", 7001),
                  FlowKey("203.0.113.2", "10.0.1.3", "udp", 7001),
                  FlowKey("203.0.113.2", "10.0.1.2", "tcp", 7001),
                  FlowKey("203.0.113.2", "10.0.1.2", "udp", 7002)):
            self.assertNotEqual(handle_for(k), base, k)

    def test_never_zero(self):
        """tc treats handle 0 as unassigned."""
        for i in range(500):
            self.assertNotEqual(
                handle_for(FlowKey(f"10.0.0.{i % 254}", "1.1.1.1", "tcp", i)), 0)

    def test_fits_32_bits(self):
        for i in range(200):
            h = handle_for(FlowKey(f"10.0.0.{i % 254}", "1.1.1.1", "udp", 1 + i))
            self.assertTrue(0 < h <= MAX_FLOW_HANDLE)

    def test_identical_across_bridge_instances(self):
        k = FlowKey("203.0.113.2", "10.0.1.2", "udp", 7001)
        b1 = Bridge("d", "e", dry_run=True)
        b2 = Bridge("d", "e", dry_run=True)
        h1 = [c[c.index("handle") + 1] for c in b1.mark(k, CLASS_BULK)
              if bare(c)[2] == "add"][0]
        h2 = [c[c.index("handle") + 1] for c in b2.mark(k, CLASS_ADAPTIVE)
              if bare(c)[2] == "add"][0]
        self.assertEqual(h1, h2)

    def test_two_instances_on_different_flows_do_not_collide(self):
        b1 = Bridge("d", "e", dry_run=True)
        b2 = Bridge("d", "e", dry_run=True)
        b1.mark(V4, CLASS_BULK)
        b2.mark(V6, CLASS_ADAPTIVE)
        self.assertNotEqual(handle_for(V4), handle_for(V6))

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
    def test_first_mark_deletes_then_adds(self):
        """The delete is unconditional even with nothing to delete, so a restart
        re-adopts its own filters instead of colliding with them."""
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).mark(V4, CLASS_ADAPTIVE)
        self.assertEqual(len(r.calls), 2)
        self.assertEqual(bare(r.calls[0])[:3], ("tc", "filter", "del"))
        self.assertEqual(bare(r.calls[1])[:3], ("tc", "filter", "add"))

    def test_repeat_mark_in_same_class_is_a_no_op(self):
        """An add per tick per flow would spend the entire netlink budget for
        no behavioural change."""
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_ADAPTIVE)
        self.assertEqual(len(r.calls), 2)          # del + add
        for _ in range(50):
            self.assertEqual(b.mark(V4, CLASS_ADAPTIVE), [])
        self.assertEqual(len(r.calls), 2, "no further netlink traffic")

    def test_reclassification_deletes_then_adds(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_BULK)
        b.mark(V4, CLASS_INTERACTIVE)
        # each mark is del+add
        self.assertEqual(len(r.calls), 4)
        self.assertEqual(bare(r.calls[2])[:3], ("tc", "filter", "del"))
        self.assertIn("1:10", r.calls[3])

    def test_mark_after_a_fake_restart_does_not_collide(self):
        """The check-17 failure, as a test: a second Bridge marking a DIFFERENT
        flow must not reuse handle 1."""
        r1 = Recorder()
        Bridge("d", "eth1", "router", executor=r1).mark(V4, CLASS_BULK)
        r2 = Recorder()
        other = FlowKey("203.0.113.2", "10.0.1.2", "udp", 7002)
        Bridge("d", "eth1", "router", executor=r2).mark(other, CLASS_ADAPTIVE)
        h1 = [c[c.index("handle") + 1] for c in r1.calls
              if bare(c)[2] == "add"][0]
        h2 = [c[c.index("handle") + 1] for c in r2.calls
              if bare(c)[2] == "add"][0]
        self.assertNotEqual(h1, h2)

    def test_reclassification_reuses_the_same_handle(self):
        """Deliberate: the same flow must land on the same handle so the old
        filter is replaced rather than left orphaned beside the new one."""
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_BULK)
        b.mark(V4, CLASS_ADAPTIVE)
        handles = [c[c.index("handle") + 1] for c in r.calls
                   if bare(c)[2] == "add"]
        self.assertEqual(len(set(handles)), 1)

    def test_handles_are_distinct_across_flows(self):
        b = Bridge("d", "eth1", "router", executor=Recorder())
        for i in range(20):
            b.mark(FlowKey("1.1.1.1", "2.2.2.2", "tcp", 1000 + i), CLASS_BULK)
        handles = [s.handle for s in b.state.slots.values()]
        self.assertEqual(len(set(handles)), 20)

    def test_no_handle_exhaustion(self):
        """Handles are derived, so there is no counter to exhaust."""
        b = Bridge("d", "eth1", "router", executor=Recorder())
        for i in range(300):
            b.mark(FlowKey(f"10.0.0.{i % 254}", "2.2.2.2", "tcp", 1 + i),
                   CLASS_BULK)

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

    def test_forget_works_with_empty_state(self):
        """A fresh Bridge must still be able to release a flow. The gate's
        bunmark helper is exactly that case, and it silently did nothing while
        forget depended on in-process state."""
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        ran = b.forget(V4)
        self.assertEqual(len(ran), 1)
        self.assertEqual(bare(ran[0])[:3], ("tc", "filter", "del"))
        self.assertEqual(bare(ran[0])[bare(ran[0]).index("handle") + 1],
                         f"0x{handle_for(V4):08x}")

    def test_forget_on_an_unknown_flow_still_issues_a_delete(self):
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).forget(V4)
        self.assertEqual(len(r.calls), 1)

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
        # del then add; the add carries the class
        self.assertEqual(bare(r.calls[-1])[:3], ("tc", "filter", "add"))
        self.assertIn("1:10", r.calls[-1])

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
    def test_teardown_removes_every_installed_flow(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_BULK)
        b.mark(V6, CLASS_ADAPTIVE)
        r.calls.clear()
        b.teardown()
        dels = [c for c in r.calls if bare(c)[:3] == ("tc", "filter", "del")]
        # two known slots, plus the two the tc listing reported
        self.assertEqual(len(dels), 4)
        self.assertTrue(all(bare(c)[:3] == ("tc", "filter", "del") for c in dels))
        self.assertEqual(b.state.slots, {})
        self.assertTrue(any("nft" in c for c in r.calls), "tables torn down too")

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
        dels = [c for c in r.calls if bare(c)[:3] == ("tc", "filter", "del")]
        self.assertTrue(dels)
        self.assertTrue(all("filter" in " ".join(c) for c in dels))

    def test_setup_clears_a_predecessors_filters(self):
        """A fresh process with empty state still clears what is on the device."""
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).setup()
        dels = [" ".join(c) for c in r.calls
                if bare(c)[:3] == ("tc", "filter", "del")]
        self.assertTrue(any("0x6c1371ad" in d for d in dels), dels)

    def test_setup_on_a_clean_bridge_enumerates_but_deletes_nothing(self):
        """setup() must read the tc tree, because after a restart the device may
        carry filters this process knows nothing about. With nothing found, it
        deletes nothing."""
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).setup()
        # enumeration runs; with the sample listing it finds two and removes them
        dels = [c for c in r.calls if bare(c)[:3] == ("tc", "filter", "del")]
        self.assertEqual(len(dels), 2)

    def test_state_is_cleared_by_teardown(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_BULK)
        b.teardown()
        self.assertEqual(b.state.slots, {})

    def test_dry_run_executes_nothing(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r, dry_run=True)
        b.mark(V4, CLASS_BULK)
        b.teardown()
        self.assertEqual(r.calls, [], "dry_run must not enumerate the tc tree")
        self.assertTrue(b.commands)

    def test_dry_run_plan_matches_commands(self):
        b = Bridge("d", "eth1", "router", dry_run=True)
        b.mark(V4, CLASS_BULK)
        b.mark(V6, CLASS_ADAPTIVE)
        self.assertEqual(b.plan(), [])

    def test_setup_installs_no_filters(self):
        """Per-flow filters are added by mark(); setup only clears. A static
        block would be dead code implying an enforcement path that does not
        exist."""
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).setup()
        self.assertFalse([c for c in r.calls if bare(c)[:3] == ("tc", "filter", "add")])


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
        """Teardown must not abort halfway: a filter that is already gone is the
        desired end state, and leaving the rest installed would be worse."""
        r = Recorder(fail_on="filter del")
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_BULK)
        b.mark(V6, CLASS_BULK)
        r.calls.clear()
        b.teardown()
        dels = [c for c in r.calls if bare(c)[:3] == ("tc", "filter", "del")]
        self.assertGreaterEqual(len(dels), 2, "every delete attempted")
        self.assertEqual(b.state.slots, {})


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


# Sample `tc -j filter show` output: two of our per-flow flower filters, plus
# the gate's own u32 filters at pref 30 (DSCP-EF) and pref 1, which must never
# be touched.
TC_FILTER_JSON = json.dumps([
    {"protocol": "ip", "pref": 5, "kind": "flower",
     "options": {"handle": 0x6C1371AD, "classid": 49168, "dst_port": 7001}},
    {"protocol": "ipv6", "pref": 6, "kind": "flower",
     "options": {"handle": 12345, "classid": 49216}},
    {"protocol": "ip", "pref": 30, "kind": "u32", "options": {"handle": 1}},
    {"protocol": "ip", "pref": 1, "kind": "u32", "options": {"handle": 1}},
])
# Built with json.dumps rather than a literal because JSON has no hex syntax:
# an earlier fixture wrote 0x6c1371ad directly, which is not valid JSON, and the
# enumeration correctly returned nothing for it.


class TestEnumerateFlowFilters(unittest.TestCase):
    """Clearing residue after a restart needs the tc tree, not process state.

    Gate check 20 failed on exactly this: it built a fresh Bridge, whose state is
    empty, and the IPv6 filter check 18 had installed survived. The gate was
    asserting a capability the code did not have -- so the capability was added
    rather than the assertion weakened.
    """

    class Ex:
        def __init__(self, rc=0, out=None, err=""):
            self.rc, self.out, self.err = rc, out, err

        def __call__(self, argv):
            return self.rc, self.out if self.out is not None else TC_FILTER_JSON, self.err

    def test_finds_only_our_flower_filters(self):
        """The gate's own u32 filters sit at pref 30 and pref 1. Deleting those
        would tear down the DSCP-EF path, which is not ours to remove."""
        got = enumerate_flow_filters("d", "router", self.Ex())
        self.assertEqual([f.pref for f in got], [5, 6])
        self.assertEqual([f.protocol for f in got], ["ip", "ipv6"])

    def test_decodes_hex_and_decimal_handles(self):
        got = enumerate_flow_filters("d", "router", self.Ex())
        self.assertEqual(got[0].handle, 0x6C1371AD)
        self.assertEqual(got[1].handle, 12345)

    def test_decodes_string_handles(self):
        ex = self.Ex(out='[{"protocol":"ip","pref":5,"kind":"flower",'
                         '"options":{"handle":"0xabc"}}]')
        self.assertEqual(enumerate_flow_filters("d", "r", ex)[0].handle, 0xABC)

    def test_bad_json_returns_empty(self):
        for out in ("", "not json", "{}", "null", "[1,2,3]"):
            self.assertEqual(
                enumerate_flow_filters("d", "r", self.Ex(out=out)), [], out)

    def test_nonzero_exit_returns_empty(self):
        """Failing to enumerate must not stop teardown removing what it knows."""
        self.assertEqual(
            enumerate_flow_filters("d", "r", self.Ex(rc=1, out="")), [])

    def test_malformed_entries_skipped(self):
        ex = self.Ex(out='[{"pref":5},{"pref":5,"kind":"flower"},'
                         '{"pref":5,"kind":"flower","options":{}},'
                         '{"pref":5,"kind":"flower","options":{"handle":0}},'
                         'notadict]')
        self.assertEqual(enumerate_flow_filters("d", "r", ex), [])

    def test_uses_json_not_text_output(self):
        """Text parsing of tool output has bitten this project twice. The
        structured format is the fix, not a more careful parser."""
        seen = {}

        class Rec:
            def __call__(self, argv):
                seen["argv"] = argv
                return 0, TC_FILTER_JSON, ""
        enumerate_flow_filters("d", "router", Rec())
        self.assertIn("-j", seen["argv"])
        self.assertLess(seen["argv"].index("-j"), seen["argv"].index("filter"))

    def test_teardown_removes_filters_it_did_not_install(self):
        """The restart case: fresh Bridge, device carries a predecessor's filter."""
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        ran = b.teardown()
        dels = [c for c in ran if bare(c)[:3] == ("tc", "filter", "del")]
        self.assertTrue(any("6c1371ad" in " ".join(c) for c in dels),
                        f"the ipv4 filter from the sample was not removed: {dels}")
        # 12345 renders as %08x -> 0x3039
        self.assertTrue(any("0x3039" in " ".join(c) for c in dels),
                        f"the ipv6 filter from the sample was not removed: {dels}")

    def test_teardown_never_removes_the_dscp_ef_filters(self):
        """Deleting the gate's u32 filters would tear down the DSCP-EF path,
        which is not the bridge's to remove."""
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).teardown()
        for c in r.calls:
            if bare(c)[:3] != ("tc", "filter", "del"):
                continue
            argv = bare(c)
            prio = argv[argv.index("prio") + 1]
            self.assertIn(prio, [str(v) for v in FLOW_FILTER_PRIO.values()])

    def test_setup_also_clears_residue(self):
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).setup()
        dels = [c for c in r.calls if bare(c)[:3] == ("tc", "filter", "del")]
        self.assertEqual(len(dels), 2)


if __name__ == "__main__":
    unittest.main()