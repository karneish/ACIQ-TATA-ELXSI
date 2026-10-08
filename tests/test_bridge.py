"""Tests for the nftables -> mark -> tc bridge.

These assert *command generation*, not kernel behaviour. The split is the point:
an argv list can be exhaustively checked without privileges, while "the kernel
honours it" is proved separately by testbed/gate.sh. Conflating the two would
mean either skipping the checks or writing tests that need root to run.

The tokenisation tests exist because of a bug this project already hit: passing
"cake bandwidth 95mbit" as one argv token produced "Specified qdisc kind is
unknown", which reads exactly like a missing kernel module.
"""

from __future__ import annotations

import unittest

from aciq import bridge as B
from aciq.bridge import (
    CLASS_PRECEDENCE,
    DSCP_FILTER_PRIO,
    MARKED_CLASSES,
    MAX_STEER_PRIO,
    STEER_PRIO_BASE,
    steer_prio,
    NFT_ELEMENT_TIMEOUT,
    NFT_TABLE,
    SET_NAMES,
    Bridge,
    BridgeError,
    FlowKey,
    generate_add_element,
    generate_del_element,
    generate_flush,
    generate_steer_filters,
    generate_rules,
    generate_sets,
    generate_table,
    generate_teardown,
)
from aciq.marks import (
    CLASS_ADAPTIVE,
    CLASS_BULK,
    CLASS_INTERACTIVE,
    CLASS_LEASED,
    CLASS_UNCLASSIFIED,
    REASON_DSCP,
    class_handle,
    encode,
)

V4 = FlowKey("10.0.1.2", "203.0.113.2", "tcp", 443)
V6 = FlowKey("2001:db8::2", "2001:db8::1", "udp", 5004)


class TestFlowKey(unittest.TestCase):
    def test_ipv4_and_ipv6_keys(self):
        self.assertEqual(V4.src, "10.0.1.2")
        self.assertIn(":", V6.src)

    def test_element_text(self):
        self.assertEqual(V4.element(), "{ 10.0.1.2 . 203.0.113.2 . tcp . 443 timeout 120s }")

    def test_element_without_timeout(self):
        self.assertEqual(V4.element(timeout=None),
                         "{ 10.0.1.2 . 203.0.113.2 . tcp . 443 }")

    def test_udp_works(self):
        k = FlowKey("10.0.1.2", "203.0.113.2", "udp", 5004)
        self.assertIn("udp", k.element())

    def test_non_tcp_udp_rejected_with_a_reason(self):
        for proto in ("icmp", "sctp", "gre", "esp"):
            with self.assertRaises(BridgeError) as cm:
                FlowKey("10.0.1.2", "203.0.113.2", proto, 1)
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
        self.assertEqual(V4.signature, ("10.0.1.2", "203.0.113.2", "tcp", 443))
        self.assertEqual(hash(V4.signature), hash(V4.signature))


class TestTokenisation(unittest.TestCase):
    """The argv-splitting lesson, enforced."""

    def _cmds(self):
        out = list(generate_table("ip", "router"))
        out += list(generate_sets("ip", "router"))
        out += list(generate_rules("ip", "veth-lan", "router"))
        out += [generate_add_element("ip", V4, CLASS_INTERACTIVE, ns="router")]
        out += list(generate_steer_filters("veth-lan", "router"))
        return out

    def test_every_command_is_a_tuple_of_str(self):
        for argv in self._cmds():
            self.assertIsInstance(argv, tuple)
            for tok in argv:
                self.assertIsInstance(tok, str)

    def test_no_rate_or_qdisc_spec_is_a_single_token(self):
        """`"htb rate 100mbit"` as one token is the bug that read as a missing
        kernel module. Any token containing whitespace must be a whole nft
        script fragment in braces, and nothing else."""
        for argv in self._cmds():
            for tok in argv:
                if " " in tok:
                    self.assertTrue(tok.startswith("{") and tok.endswith("}"),
                                    f"whitespace token is not a braced fragment: "
                                    f"{tok!r} in {argv}")

    def test_braced_fragments_are_single_tokens(self):
        chain = generate_table("ip", None)[1]
        frag = chain[-1]
        self.assertTrue(frag.startswith("{") and frag.endswith("}"))
        self.assertIn("hook prerouting", frag)

    def test_netns_prefix_is_three_tokens(self):
        argv = generate_table("ip", "router")[0]
        self.assertEqual(argv[:4], ("ip", "netns", "exec", "router"))

    def test_no_netns_prefix_when_ns_is_none(self):
        argv = generate_table("ip", None)[0]
        self.assertEqual(argv[:3], ("nft", "add", "table"))

    def test_mark_is_its_own_token(self):
        argv = generate_rules("ip", "veth-lan", None)[0]
        self.assertIn(str(encode(CLASS_LEASED)), argv)


class TestTableAndSets(unittest.TestCase):
    def test_table_and_chain(self):
        t, c = generate_table("ip6")
        self.assertEqual(t, ("nft", "add", "table", "ip6", NFT_TABLE))
        self.assertEqual(c[:6], ("nft", "add", "chain", "ip6", NFT_TABLE, "prerouting"))
        self.assertIn("hook prerouting", c[-1])

    def test_hook_priority_is_mangle(self):
        frag = generate_table("ip")[1][-1]
        self.assertIn("priority mangle", frag)

    def test_one_set_per_class(self):
        sets = generate_sets("ip")
        self.assertEqual(len(sets), len(MARKED_CLASSES))
        names = {s[-2] for s in sets}
        self.assertEqual(names, set(SET_NAMES.values()))

    def test_sets_have_timeout_flag(self):
        """`flags timeout` is the whole of mark expiry: the kernel ages elements
        out, so a crashed ACIQ cannot leave stale marks forever."""
        for s in generate_sets("ip"):
            self.assertIn("flags timeout", s[-1])
            self.assertIn(NFT_ELEMENT_TIMEOUT, s[-1])

    def test_set_element_types_differ_by_family(self):
        v4 = generate_sets("ip")[0][-1]
        v6 = generate_sets("ip6")[0][-1]
        self.assertIn("ipv4_addr", v4)
        self.assertIn("ipv6_addr", v6)

    def test_teardown_deletes_the_table(self):
        self.assertEqual(generate_teardown("ip"),
                         ("nft", "delete", "table", "ip", NFT_TABLE))

    def test_flush_covers_every_set(self):
        self.assertEqual(len(generate_flush("ip")), len(MARKED_CLASSES))


class TestRules(unittest.TestCase):
    def test_address_expressions_match_the_family(self):
        v4 = generate_rules("ip", "eth1")[0]
        v6 = generate_rules("ip6", "eth1")[0]
        self.assertIn(("ip", "saddr"), [v4[i:i + 2] for i in range(len(v4) - 1)])
        self.assertIn(("ip", "daddr"), [v4[i:i + 2] for i in range(len(v4) - 1)])
        self.assertIn(("ip6", "saddr"), [v6[i:i + 2] for i in range(len(v6) - 1)])
        self.assertIn(("ip6", "daddr"), [v6[i:i + 2] for i in range(len(v6) - 1)])

    def test_incoming_interface_is_matched(self):
        self.assertIn("iifname", generate_rules("ip", "eth1")[0])
        self.assertIn("eth1", generate_rules("ip", "eth1")[0])

    def test_one_rule_per_class(self):
        self.assertEqual(len(generate_rules("ip", "eth1")), len(MARKED_CLASSES))

    def test_precedence_order_is_leased_first_unclassified_last(self):
        """nft stops at the first match, so tuple order IS the precedence."""
        self.assertEqual(CLASS_PRECEDENCE[0], CLASS_LEASED)
        self.assertEqual(CLASS_PRECEDENCE[-1], CLASS_UNCLASSIFIED)
        sets = [_set_ref(r) for r in generate_rules("ip", "eth1")]
        self.assertEqual(sets[0], "leased")
        self.assertEqual(sets[-1], "unclassified")

    def test_rule_order_follows_precedence(self):
        sets = [_set_ref(r) for r in generate_rules("ip", "eth1")]
        self.assertEqual(sets, [SET_NAMES[c] for c in CLASS_PRECEDENCE])

    def test_mark_value_matches_the_encoder(self):
        for rule, cid in zip(generate_rules("ip", "eth1"), CLASS_PRECEDENCE):
            self.assertIn(str(encode(cid)), rule)

    def test_dport_lookup_present(self):
        rule = generate_rules("ip", "eth1")[0]
        self.assertIn("meta", rule)
        self.assertIn("@leased", rule)
        self.assertIn("l4proto", rule)
        self.assertIn("dport", rule)

    def test_mark_is_set_not_copied(self):
        rule = generate_rules("ip", "eth1")[0]
        i = rule.index("mark")
        self.assertEqual(rule[i + 1], "set")


class TestMarkFilters(unittest.TestCase):
    def test_one_per_class_per_protocol(self):
        self.assertEqual(len(generate_steer_filters("veth-lan")),
                         len(MARKED_CLASSES) * 2)

    def test_both_protocols_present(self):
        protos = {f[f.index("protocol") + 1]
                  for f in generate_steer_filters("veth-lan")}
        self.assertEqual(protos, {"ip", "ipv6"})

    def test_matches_dscp_selector_codes(self):
        """flower reads the DSCP the nft rules stamp, so the two must agree."""
        for f in generate_steer_filters("veth-lan"):
            self.assertIn("ip_tos", f)
        self.assertTrue(any("0x08/0xfc" in f for f in
                            generate_steer_filters("veth-lan")))

    def test_only_the_dscp_bits_are_masked(self):
        """DSCP is the top 6 bits of TOS; the low 2 are ECN and must not be
        matched, or traffic would be classified by its ECN marks."""
        for f in generate_steer_filters("veth-lan"):
            self.assertIn("/0xfc", f[f.index("ip_tos") + 1])

    def test_no_fw_filters_are_emitted(self):
        """`tc fw` cannot match a mark on iproute2 6.1.0 -- it accepts only
        classid, indev and action. Emitting one makes setup fail outright."""
        for f in generate_steer_filters("veth-lan"):
            self.assertNotIn("fw", f)

    def test_dscp_codes_are_csx_and_unique(self):
        from aciq.bridge import CS_DSCP_NAMES, CS_DSCP_VALUES
        vals = [CS_DSCP_VALUES[c] for c in MARKED_CLASSES]
        self.assertEqual(len(set(vals)), len(vals), "codes must not collide")
        for c in MARKED_CLASSES:
            self.assertTrue(CS_DSCP_NAMES[c].startswith("cs"))

    def test_skip_hw_present(self):
        """flower is hardware-offloadable; without skip_hw the kernel may try to
        push these filters to the NIC and fail on a veth pair."""
        for f in generate_steer_filters("veth-lan"):
            self.assertIn("skip_hw", f)

    def test_protocol_can_be_collapsed(self):
        self.assertEqual(len(generate_steer_filters("d", protocol_filter=False)),
                         len(MARKED_CLASSES))

    def test_flowids(self):
        flowids = {f[f.index("flowid") + 1]
                   for f in generate_steer_filters("veth-lan")}
        self.assertEqual(flowids, {"1:10", "1:20", "1:30", "1:40"})

    def test_unclassified_goes_to_the_default_class(self):
        """The point of the seen bit: an examined-but-unclassified flow must stop
        being EF-eligible, and 1:30 is where non-EF traffic already lands."""
        self.assertEqual(B._flowid(CLASS_UNCLASSIFIED), "1:30")

    def test_flowids_agree_with_tc_module(self):
        """Read from tc.CLASS_IDS rather than restated, so there is nothing left
        to drift -- this asserts the wiring, including the one deliberate
        deviation for unclassified."""
        from aciq import tc
        from aciq.model import TrafficClass
        for tclass, cid in ((TrafficClass.INTERACTIVE, CLASS_INTERACTIVE),
                            (TrafficClass.ADAPTIVE, CLASS_ADAPTIVE),
                            (TrafficClass.BULK, CLASS_BULK),
                            (TrafficClass.LEASED, CLASS_LEASED)):
            self.assertEqual(B._flowid(cid), tc.CLASS_IDS[tclass])
        self.assertEqual(B._flowid(CLASS_UNCLASSIFIED),
                         tc.CLASS_IDS[TrafficClass.BULK])

    def test_dscp_priorities_are_shared_not_redeclared(self):
        """The bridge and tc install filters into the same parent, so two copies
        of these numbers is two chances to get the order wrong silently."""
        from aciq import tc
        self.assertIs(B.DSCP_FILTER_PRIO, tc.DSCP_FILTER_PRIO)
        self.assertLess(MAX_STEER_PRIO, min(B.DSCP_FILTER_PRIO.values()))


class TestFilterPriority(unittest.TestCase):
    def test_bridge_precedes_dscp_filters(self):
        """tc evaluates ascending, so a steer filter at a higher number would
        never be consulted and its verdicts would be silently ignored."""
        self.assertLess(MAX_STEER_PRIO, min(DSCP_FILTER_PRIO.values()))

    def test_prios_are_unique_per_class(self):
        for proto in STEER_PRIO_BASE:
            prios = [steer_prio(proto, c) for c in MARKED_CLASSES]
            self.assertEqual(len(set(prios)), len(prios))

    def test_prio_values_in_order(self):
        for proto in STEER_PRIO_BASE:
            prios = [steer_prio(proto, c) for c in MARKED_CLASSES]
            self.assertEqual(prios, sorted(prios))

    def test_protocols_never_share_a_priority(self):
        """REGRESSION. `tc` requires every filter at one priority to share a
        protocol and rejects a mismatch with "Protocol mismatch for filter with
        specified priority". Emitting both families at prios 10-14 installed the
        five IPv4 filters and failed on all five IPv6 ones."""
        seen = {}
        for proto in STEER_PRIO_BASE:
            for c in MARKED_CLASSES:
                p = steer_prio(proto, c)
                self.assertNotIn(p, seen,
                                 f"prio {p} claimed by both {seen.get(p)} and {proto}")
                seen[p] = proto

    def test_generated_filters_have_no_priority_collisions(self):
        """The same invariant, checked on the actual argv rather than the
        helper -- a generator bug could bypass the helper entirely."""
        seen = {}
        for f in generate_steer_filters("d"):
            proto = f[f.index("protocol") + 1]
            prio = f[f.index("prio") + 1]
            self.assertNotIn(prio, seen,
                             f"prio {prio} used by {seen.get(prio)} and {proto}")
            seen[prio] = proto

    def test_unknown_protocol_rejected(self):
        with self.assertRaises(BridgeError):
            steer_prio("sctp", CLASS_INTERACTIVE)

    def test_one_prio_per_class_per_protocol(self):
        combos = [(f[f.index("prio") + 1], f[f.index("protocol") + 1])
                  for f in generate_steer_filters("d")]
        self.assertEqual(len(combos), len(set(combos)))


class TestElements(unittest.TestCase):
    def test_add_targets_the_right_set(self):
        argv = generate_add_element("ip", V4, CLASS_ADAPTIVE)
        self.assertIn("adaptive", argv)
        self.assertEqual(bare(argv)[:3], ("nft", "add", "element"))

    def test_add_carries_a_timeout(self):
        argv = generate_add_element("ip", V4, CLASS_ADAPTIVE)
        self.assertIn(NFT_ELEMENT_TIMEOUT, argv[-1])

    def test_delete_has_no_timeout(self):
        argv = generate_del_element("ip", V4, CLASS_ADAPTIVE)
        self.assertEqual(bare(argv)[:3], ("nft", "delete", "element"))
        self.assertNotIn("timeout", argv[-1])

    def test_encoding_is_validated_before_the_command_is_built(self):
        # a lease id on a non-lease class is nonsense and must be caught here,
        # not masked off into a plausible-looking mark
        with self.assertRaises(Exception):
            generate_add_element("ip", V4, CLASS_INTERACTIVE, lease_id=9)

    def test_unknown_class_rejected(self):
        with self.assertRaises(BridgeError):
            generate_add_element("ip", V4, 7)
        with self.assertRaises(BridgeError):
            generate_del_element("ip", V4, 7)

    def test_ipv6_element(self):
        argv = generate_add_element("ip6", V6, CLASS_INTERACTIVE)
        self.assertEqual(argv[3], "ip6")
        self.assertIn("2001:db8::2", argv[-1])


def _set_ref(rule: tuple[str, ...]) -> str:
    """The set a rule references, i.e. the token starting with '@'."""
    return next(tok[1:] for tok in rule if tok.startswith("@"))


def bare(argv: tuple[str, ...]) -> tuple[str, ...]:
    """Strip the `ip netns exec <ns>` prefix so assertions read the real command."""
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


class TestBridgeLifecycle(unittest.TestCase):
    def test_setup_runs_teardown_first_per_family(self):
        """nft's `add` fails on an existing table, so setup deletes first. One
        code path instead of add-with-create-fallback."""
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.setup()
        joined = [" ".join(c) for c in r.calls]
        self.assertIn("delete table ip aciq", joined[0])
        self.assertIn("delete table ip6 aciq", joined[1])
        self.assertIn("add table ip aciq", joined[2])

    def test_setup_emits_every_piece(self):
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).setup()
        j = " ".join(" ".join(c) for c in r.calls)
        for expect in ("add chain", "add set", "add rule",
                       "tc filter add", "flags timeout"):
            self.assertIn(expect, j)

    def test_setup_installs_mark_filters_last(self):
        """Filters are installed after the sets exist, so no packet is matched by
        a rule pointing at a set that is not there yet."""
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).setup()
        self.assertEqual(bare(r.calls[-1])[:3], ("tc", "filter", "add"))

    def test_teardown_removes_both_tables(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.teardown()
        self.assertEqual(len(r.calls), 2)
        self.assertIn("ip", r.calls[0])
        self.assertIn("ip6", r.calls[1])

    def test_setup_is_idempotent_across_runs(self):
        """Running setup twice must not fail, because setup always deletes
        first. This is what makes it safe to call on every run."""
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).setup()
        n = len(r.calls)
        Bridge("d", "eth1", "router", executor=r).setup()
        self.assertEqual(len(r.calls), 2 * n)

    def test_executor_failure_raises(self):
        r = Recorder(fail_on="add table")
        b = Bridge("d", "eth1", "router", executor=r)
        with self.assertRaises(BridgeError) as cm:
            b.setup()
        self.assertIn("synthetic failure", str(cm.exception))
        self.assertIn("rc=1", str(cm.exception))

    def test_dry_run_executes_nothing(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r, dry_run=True)
        cmds = b.setup()
        self.assertEqual(r.calls, [])
        self.assertTrue(cmds)
        self.assertEqual(b.commands, cmds)

    def test_plan_matches_setup_without_running(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        planned = b.plan()
        b.setup()
        self.assertEqual(planned, r.calls)

    def test_family_detection(self):
        b = Bridge("d", "eth1")
        self.assertEqual(b.family_of("10.0.1.2"), "ip")
        self.assertEqual(b.family_of("2001:db8::1"), "ip6")
        self.assertEqual(b.family_of("fe80::1%eth0"), "ip6")

    def test_single_family_deployment(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", families=("ip",), executor=r)
        b.mark(V4, CLASS_BULK)
        self.assertTrue(all("ip6" not in " ".join(c) for c in r.calls))


class TestBridgeMarking(unittest.TestCase):
    def test_mark_adds_an_element(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_INTERACTIVE)
        self.assertEqual(len(r.calls), 1)
        self.assertEqual(bare(r.calls[0])[:3], ("nft", "add", "element"))
        self.assertIn("interactive", r.calls[0])

    def test_repeat_mark_in_same_class_is_a_no_op(self):
        """Re-adding an existing element resets its timeout. Doing that every
        tick would keep a dead flow's mark alive forever -- which is how a stale
        mark becomes permanent."""
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_INTERACTIVE)
        for _ in range(50):
            self.assertEqual(b.mark(V4, CLASS_INTERACTIVE), [])
        self.assertEqual(len(r.calls), 1)

    def test_reclassification_deletes_then_adds(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_BULK)
        b.mark(V4, CLASS_INTERACTIVE)
        self.assertEqual(len(r.calls), 3)
        self.assertEqual(bare(r.calls[1])[:3], ("nft", "delete", "element"))
        self.assertIn("bulk", r.calls[1])
        self.assertIn("interactive", r.calls[2])

    def test_reclassification_is_a_single_delete_not_five(self):
        """Deleting from every set speculatively would be 5 netlink calls per
        change, most tolerating ENOENT."""
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_BULK)
        r.calls.clear()
        b.mark(V4, CLASS_ADAPTIVE)
        self.assertEqual(len(r.calls), 2)

    def test_membership_is_tracked(self):
        b = Bridge("d", "eth1", "router", executor=Recorder())
        b.mark(V4, CLASS_BULK)
        self.assertEqual(len(b.state.membership), 1)
        b.mark(V6, CLASS_INTERACTIVE)
        self.assertEqual(len(b.state.membership), 2)

    def test_flows_are_tracked_separately(self):
        b = Bridge("d", "eth1", "router", executor=Recorder())
        b.mark(V4, CLASS_BULK)
        b.mark(V6, CLASS_BULK)
        self.assertEqual(len(b.state.membership), 2)

    def test_dscp_reason_is_recorded(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_INTERACTIVE, confidence=0.95, reason=REASON_DSCP)
        b.teardown()
        b.mark(V4, CLASS_BULK, confidence=0.75, reason=REASON_DSCP)
        self.assertTrue(any("bulk" in " ".join(c) for c in r.calls))

    def test_forget_removes_the_element(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_LEASED, lease_id=1)
        r.calls.clear()
        ran = b.forget(V4)
        self.assertEqual(len(ran), 1)
        self.assertEqual(bare(ran[0])[:3], ("nft", "delete", "element"))
        self.assertEqual(len(b.state.membership), 0)

    def test_forget_on_an_unknown_flow_is_a_no_op(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        self.assertEqual(b.forget(V4), [])
        self.assertEqual(r.calls, [])

    def test_lease_release_then_remark(self):
        """The lease lifecycle: mark leased, release, re-enter as bulk."""
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_LEASED, lease_id=3)
        b.forget(V4)
        b.mark(V4, CLASS_BULK)
        j = [" ".join(c) for c in r.calls]
        self.assertTrue(any("delete" in c and "leased" in c for c in j))
        self.assertTrue(any("add" in c and "bulk" in c for c in j))

    def test_single_command_is_not_iterated_by_token(self):
        """generate_add_element returns one argv; _do takes a sequence of them.
        Iterating a single argv yielded its tokens, so "nft" and "add element"
        were each run as whole command lines -- 11 commands for 1 mark."""
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_INTERACTIVE)
        self.assertEqual(len(r.calls), 1)
        self.assertEqual(bare(r.calls[0])[:3], ("nft", "add", "element"))

    def test_teardown_runs_one_command_per_family(self):
        r = Recorder()
        Bridge("d", "eth1", "router", executor=r).teardown()
        self.assertEqual(len(r.calls), 2)
        for argv in r.calls:
            self.assertEqual(bare(argv)[:3], ("nft", "delete", "table"))

    def test_mark_routes_to_the_flows_own_family_only(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V6, CLASS_BULK)
        self.assertTrue(all("ip6" in " ".join(c) for c in r.calls))
        self.assertFalse(any(" ip saddr " in " " + " ".join(c) + " " for c in r.calls))

    def test_teardown_clears_membership(self):
        b = Bridge("d", "eth1", "router", executor=Recorder())
        b.mark(V4, CLASS_BULK)
        b.teardown()
        self.assertEqual(b.state.membership, {})


class TestEndToEndPlan(unittest.TestCase):
    def test_dscp_claiming_bulk_flow_is_denied_ef(self):
        """The evasion path, end to end through generated commands only.

        A flow claiming EF is classified BULK, so it lands in the bulk set and
        never reaches the DSCP-EF filter at prio 30.
        """
        b = Bridge("veth-lan", "veth-lan", "router", dry_run=True)
        plan = b.plan()
        b.mark(FlowKey("10.0.1.2", "203.0.113.2", "tcp", 443), CLASS_BULK,
               confidence=0.75, reason=2)
        bulk_set = [c for c in b.commands
                    if "element" in c and SET_NAMES[CLASS_BULK] in c]
        self.assertEqual(len(bulk_set), 1)
        dscp_prio = min(DSCP_FILTER_PRIO.values())
        self.assertLess(MAX_STEER_PRIO, dscp_prio)

    def test_unclassified_flow_does_not_reach_the_ef_filter(self):
        b = Bridge("veth-lan", "veth-lan", "router", dry_run=True)
        b.plan()
        b.mark(V4, CLASS_UNCLASSIFIED, confidence=0.4, reason=2)
        uncls = [c for c in b.commands
                 if "element" in c and SET_NAMES[CLASS_UNCLASSIFIED] in c]
        self.assertTrue(uncls)
        prios = [c[c.index("prio") + 1] for c in generate_steer_filters("d")]
        self.assertTrue(all(int(p) < min(DSCP_FILTER_PRIO.values()) for p in prios))


if __name__ == "__main__":
    unittest.main()

class TestMissingObjectTolerance(unittest.TestCase):
    """`nft delete` returning nonzero for an absent object is the expected
    state, not an error.

    Found by gate check 15 on a real kernel: `nft delete table ip aciq` returns
    rc=1 "No such file or directory" on a first run, and setup() raised on it, so
    check 15 died on its first command and the set/rule/tc syntax below it went
    entirely untested.
    """

    def test_setup_succeeds_when_no_table_exists(self):
        """The first-run case: everything nft touches is absent."""
        r = Recorder(fail_on="delete table", rc=1)
        b = Bridge("d", "eth1", "router", executor=r)
        b.setup()                       # must not raise
        self.assertIn("add table", " ".join(" ".join(c) for c in r.calls))

    def test_setup_succeeds_on_a_completely_fresh_netns(self):
        """Every delete fails with ENOENT, as in a freshly created namespace."""
        def fresh(argv):
            if "delete" in argv:
                return (1, "", "Error: Could not process rule: No such file or directory")
            return (0, "", "")
        Bridge("d", "eth1", "router", executor=fresh).setup()

    def test_real_problem_still_surfaces(self):
        """missing_ok must not become a blanket ignore.

        If the table exists and genuinely cannot be removed, `delete` fails and
        the following `add table` fails with EEXIST -- which does raise. That is
        the guarantee which makes tolerating the delete safe.
        """
        def delete_fails_add_fails(argv):
            if "delete" in argv:
                return (1, "", "Error: permission denied")
            if "add" in argv and "table" in argv:
                return (1, "", "Error: File exists")
            return (0, "", "")
        b = Bridge("d", "eth1", "router", executor=delete_fails_add_fails)
        with self.assertRaises(BridgeError):
            b.setup()

    def test_teardown_tolerates_absent_table(self):
        """check 20 calls teardown, and the table may already be gone."""
        r = Recorder(fail_on="delete table", rc=1)
        Bridge("d", "eth1", "router", executor=r).teardown()
        self.assertEqual(len(r.calls), 2)

    def test_expired_element_delete_is_tolerated(self):
        """A 120s kernel set timeout can remove an element before we do.

        Expiry is designed to happen, so reclassifying a flow whose mark has
        aged out is a guaranteed race in normal operation, not an edge case.
        """
        r = Recorder(fail_on="delete element", rc=1)
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_BULK)
        b.mark(V4, CLASS_INTERACTIVE)    # must not raise
        self.assertIn("interactive", " ".join(" ".join(c) for c in r.calls))

    def test_forget_tolerates_an_already_expired_element(self):
        r = Recorder(fail_on="delete element", rc=1)
        b = Bridge("d", "eth1", "router", executor=r)
        b.mark(V4, CLASS_LEASED, lease_id=1)
        b.forget(V4)                     # must not raise
        self.assertEqual(b.state.membership, {})

    def test_add_element_failures_are_never_tolerated(self):
        """Only `delete` is missing_ok. A failed `add element` means the mark was
        NOT set, and continuing silently would ship traffic to a class the
        classifier never chose."""
        r = Recorder(fail_on="add element", rc=1)
        b = Bridge("d", "eth1", "router", executor=r)
        with self.assertRaises(BridgeError):
            b.mark(V4, CLASS_INTERACTIVE)

    def test_set_add_failures_are_never_tolerated(self):
        r = Recorder(fail_on="add set", rc=1)
        b = Bridge("d", "eth1", "router", executor=r)
        with self.assertRaises(BridgeError):
            b.setup()

    def test_plan_is_still_identical_to_setup(self):
        """missing_ok changes error handling only, never the command list."""
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r)
        planned = b.plan()
        b.setup()
        self.assertEqual(planned, r.calls)

    def test_dry_run_plan_unaffected_by_missing_ok(self):
        r = Recorder()
        b = Bridge("d", "eth1", "router", executor=r, dry_run=True)
        self.assertEqual(b.setup(), b.plan())
        self.assertEqual(r.calls, [])


class TestConcatenationDots(unittest.TestCase):
    """nftables concatenates with a literal `.` token.

    Found by bridge_probe.sh on a real kernel: the rule was emitted as

        ip saddr ip daddr meta l4proto th dport @leased meta mark set 20

    and nft answered "syntax error, unexpected meta". Without the dots those are
    five separate expressions and nft binds @leased to only the last one, so the
    set lookup would never match the 4-field key even if it parsed.
    """

    def _rule(self, family="ip", cls=CLASS_LEASED):
        rules = generate_rules(family, "veth-wan")
        return rules[CLASS_PRECEDENCE.index(cls)]

    def test_dots_separate_the_four_key_expressions(self):
        rule = self._rule()
        self.assertEqual(rule.count("."), 3,
                         f"expected 3 concatenation dots, got {rule}")

    def test_dot_precedes_each_key_expression(self):
        """Each concatenation dot sits before the START of an expression.

        The key expressions are multi-token (`ip daddr` is two tokens), so the
        dot precedes the expression's first token, not the token carrying its
        name. saddr is the first expression and has no preceding dot.
        """
        rule = self._rule()
        exprs = [("ip", "saddr"), ("ip", "daddr"),
                 ("meta", "l4proto"), ("th", "dport")]
        # locate each expression as a contiguous run
        starts = []
        for e in exprs:
            for i in range(len(rule) - len(e) + 1):
                if tuple(rule[i:i + len(e)]) == e:
                    starts.append(i)
                    break
            else:
                self.fail(f"expression {e} not found in {rule}")
        starts.sort()
        self.assertEqual(starts, sorted(starts), f"expressions out of order: {rule}")
        # everything after the first must be introduced by a dot
        self.assertEqual(rule[starts[0] - 1], "veth-wan")
        for i in starts[1:]:
            self.assertEqual(rule[i - 1], ".",
                             f"no dot before expression at token {i}: {rule}")

    def test_dots_appear_in_both_families(self):
        for family in ("ip", "ip6"):
            self.assertEqual(self._rule(family).count("."), 3)

    def test_dots_appear_for_every_class(self):
        for c in CLASS_PRECEDENCE:
            self.assertEqual(self._rule(cls=c).count("."), 3, f"class {c}")

    def test_set_reference_comes_after_the_key(self):
        rule = self._rule()
        self.assertLess(rule.index("dport"), rule.index("@leased"))
        self.assertLess(rule.index("@leased"), rule.index("mark"))

    def test_element_text_already_had_dots(self):
        """The set element is a single token and always had its dots. Asserted
        so the two representations cannot drift apart."""
        self.assertEqual(V4.element(),
                         "{ 10.0.1.2 . 203.0.113.2 . tcp . 443 timeout 120s }")

    def test_dot_count_matches_the_set_element_field_count(self):
        """3 dots join 4 expressions; the element has 4 fields joined by 3
        separators. Same shape on both sides of the lookup.

        Counting "." in the element text is meaningless -- the addresses
        contain dots themselves, so a naive count gives 9, not 3. Split on the
        separator instead.
        """
        body = V4.element().strip("{}").strip()
        # the timeout rides on the last field, so strip it before counting
        body = body.rsplit(" timeout ", 1)[0]
        fields = body.split(" . ")
        self.assertEqual(fields, ["10.0.1.2", "203.0.113.2", "tcp", "443"])
        # 4 fields => 3 separators
        self.assertEqual(self._rule().count("."), len(fields) - 1)


class TestSteeringCodes(unittest.TestCase):
    """The DSCP selector codes, and the collision that nearly happened."""

    def test_cs0_is_never_used(self):
        """DSCP 0x00 is ordinary best-effort traffic. A CS0 filter would capture
        every unsteered packet and route it to 1:30 -- correct outcome, wrong
        reason, and it destroyed the difference between 'the bridge decided this
        is unclassified' and 'the bridge never looked at this packet'."""
        from aciq.bridge import CS_DSCP_NAMES, CS_DSCP_VALUES
        self.assertNotIn(0x00, CS_DSPF := CS_DSCP_VALUES.values())
        self.assertNotIn("cs0", CS_DSCP_NAMES.values())
        self.assertGreater(min(CS_DSPF), 0x00)

    def test_steering_codes_start_at_cs1(self):
        from aciq.bridge import CS_DSCP_VALUES
        self.assertEqual(min(CS_DSCP_VALUES.values()), 0x08)

    def test_codes_are_unique(self):
        from aciq.bridge import CS_DSCP_VALUES
        vals = list(CS_DSCP_VALUES.values())
        self.assertEqual(len(set(vals)), len(vals))

    def test_codes_are_consecutive_csx(self):
        from aciq.bridge import CS_DSCP_VALUES
        vals = sorted(CS_DSCP_VALUES.values())
        self.assertEqual(vals, list(range(0x08, 0x08 + 8 * len(vals), 8)))

    def test_every_class_has_a_code(self):
        from aciq.bridge import CS_DSCP_VALUES, MARKED_CLASSES
        self.assertEqual(set(CS_DSCP_VALUES), set(MARKED_CLASSES))

    def test_no_code_collides_with_dscp_ef(self):
        """EF is 0xb8. A steering code equal to it would let an EF probe capture
        a steered flow, and the trust logic in classify.py would stop meaning
        anything."""
        from aciq.bridge import CS_DSCP_VALUES
        for c, v in CS_DSCP_VALUES.items():
            self.assertNotEqual(v, 0xB8, f"{c} steers onto DSCP EF")

    def test_steering_filter_value_matches_the_rule(self):
        """The rule stamps DSCP; the filter must read exactly that value. A
        mismatch here would be invisible -- both commands are individually
        valid -- and would silently route every steered flow to the default."""
        from aciq.bridge import (CLASS_PRECEDENCE, CS_DSCP_VALUES,
                                 generate_rules, generate_steer_filters)
        for family in ("ip", "ip6"):
            for rule, c in zip(generate_rules(family, "veth-wan"),
                               CLASS_PRECEDENCE):
                name = CS_DSCP_VALUES[c]
                self.assertIn(f"set {f'cs{(name // 8) & 0x7:d}'}", " ".join(rule))
        handles = {f[f.index("ip_tos") + 1].split("/")[0]
                   for f in generate_steer_filters("d")}
        self.assertEqual(handles,
                         {f"{v:#04x}" for v in CS_DSCP_VALUES.values()})

    def test_ipv4_and_ipv6_spell_dscp_differently(self):
        """`ip dscp set` and `ip6 dscp set` are different keywords."""
        v4 = " ".join(generate_rules("ip", "veth-wan")[0])
        v6 = " ".join(generate_rules("ip6", "veth-wan")[0])
        self.assertIn("ip dscp set", v4)
        self.assertIn("ip6 dscp set", v6)

    def test_mark_is_still_set_alongside_dscp(self):
        """DSCP is 6 bits and carries only the class. The mark additionally
        carries confidence, reason and lease id, so both are written."""
        for family in ("ip", "ip6"):
            for rule in generate_rules(family, "veth-wan"):
                self.assertIn("meta", rule)
                self.assertIn("mark", rule)

    def test_dscp_steering_precedes_ef_filters(self):
        """A steered flow must not be able to fall through to the EF filter,
        which is exactly the evasion the seen-bit design was built to close."""
        from aciq.bridge import MAX_STEER_PRIO
        from aciq.tc import DSCP_FILTER_PRIO
        self.assertLess(MAX_STEER_PRIO, min(DSCP_FILTER_PRIO.values()))


class TestFamilyOf(unittest.TestCase):
    """Module-level so a caller adding one element need not build a Bridge."""

    def test_ipv4_and_ipv6(self):
        from aciq.bridge import family_of
        self.assertEqual(family_of("10.0.1.2"), "ip")
        self.assertEqual(family_of("203.0.113.9"), "ip")
        self.assertEqual(family_of("2001:db8::2"), "ip6")
        self.assertEqual(family_of("fd00:1::2"), "ip6")

    def test_zone_id_does_not_raise(self):
        """A zone id would raise in socket.inet_pton. It must not raise from deep
        inside a classification tick."""
        from aciq.bridge import family_of
        self.assertEqual(family_of("fe80::1%eth0"), "ip6")

    def test_method_delegates_to_the_helper(self):
        from aciq.bridge import Bridge
        self.assertEqual(Bridge("d", "e").family_of("2001:db8::1"), "ip6")


class TestNamespaceDefault(unittest.TestCase):
    """`ns` defaults to None, which means "the current namespace".

    Documented rather than changed: making it mandatory would be the safer
    default, but it is a public keyword on five generators and the unit tests
    legitimately call them with ns=None.

    This footgun cost a gate run. The gate's `bmark` helper omitted `ns`, so
    `nft add element` ran in the host namespace where table `aciq` does not
    exist, and nft answered "No such file or directory" pointing at the SET
    name -- which reads like a missing set in the bridge rather than a missing
    namespace in the caller.
    """

    def test_ns_none_omits_the_prefix(self):
        self.assertEqual(
            generate_add_element("ip", V4, CLASS_BULK, ns=None)[:3], ("nft", "add", "element"))
        self.assertEqual(
            generate_add_element("ip", V4, CLASS_BULK, ns="router")[:4],
            ("ip", "netns", "exec", "router"))

    def test_every_generator_defaults_ns_to_none(self):
        import inspect
        for fn in (generate_add_element, generate_del_element,
                   generate_table, generate_sets, generate_rules,
                   generate_steer_filters, generate_teardown, generate_flush):
            self.assertIsNone(inspect.signature(fn).parameters["ns"].default, fn)

    def test_passing_a_namespace_changes_only_the_prefix(self):
        plain = bare(generate_add_element("ip", V4, CLASS_BULK))
        namespaced = bare(generate_add_element("ip", V4, CLASS_BULK, ns="router"))
        self.assertEqual(plain, namespaced)


class TestPriorityIsOptional(unittest.TestCase):
    """`meta priority` is opt-in and OFF by default.

    The hypothesis it addresses -- that `tc flower ip_tos` matches skb->priority
    rather than iph->tos -- was tested on a real kernel and is WRONG: with
    'meta priority set 0:18' visible in the ruleset, 1:20 still did not grow.

    It is also not free. HTB uses skb->priority as a 0-7 class priority, and the
    DSCP selector codes are 8, 16, 24, 32, 40 -- all outside that range. Mirroring
    the DSCP there may actively confuse class selection inside HTB.

    Kept available for testbed/bridge_isolate.sh, which can settle whether it
    helps or hurts. Not enabled blindly in the shipped rules.
    """

    def test_off_by_default(self):
        for family in ("ip", "ip6"):
            for rule in generate_rules(family, "veth-wan"):
                self.assertNotIn("priority", rule)

    def test_enabled_when_asked(self):
        for family in ("ip", "ip6"):
            for rule in generate_rules(family, "veth-wan", set_priority=True):
                self.assertIn("priority", rule)

    def test_enabled_value_equals_the_dscp_code(self):
        from aciq.bridge import CS_DSCP_VALUES
        for rule, c in zip(generate_rules("ip", "veth-wan", set_priority=True),
                           CLASS_PRECEDENCE):
            i = rule.index("priority")
            self.assertEqual(rule[i + 1], "set")
            self.assertEqual(rule[i + 2], str(CS_DSCP_VALUES[c]))

    def test_dscp_is_written_before_the_priority(self):
        for rule in generate_rules("ip", "veth-wan", set_priority=True):
            self.assertLess(rule.index("dscp"), rule.index("priority"))

    def test_dscp_and_mark_are_written_in_both_modes(self):
        """The steering mechanism does not depend on this option."""
        for kwargs in ({}, {"set_priority": True}):
            for family in ("ip", "ip6"):
                for rule in generate_rules(family, "veth-wan", **kwargs):
                    self.assertIn("dscp", rule)
                    self.assertIn("mark", rule)
                    self.assertIn("counter", rule)

    def test_dscp_codes_exceed_the_htb_priority_range(self):
        """Documents why mirroring the DSCP into skb->priority is risky: HTB
        treats skb->priority as a 0-7 class priority."""
        from aciq.bridge import CS_DSCP_VALUES
        for c, v in CS_DSCP_VALUES.items():
            self.assertGreater(v, 7, f"class {c} DSCP code fits HTB's range")

    def test_steer_filter_and_priority_agree_when_enabled(self):
        from aciq.bridge import CS_DSCP_VALUES, steer_prio
        by_prio = {steer_prio(p, c): c
                   for p in STEER_PRIO_BASE for c in MARKED_CLASSES}
        for f in generate_steer_filters("d"):
            prio = int(f[f.index("prio") + 1])
            self.assertIn(prio, by_prio)
            self.assertIn(f"{CS_DSCP_VALUES[by_prio[prio]]:#04x}/0xfc", f)


class TestFamilyOf(unittest.TestCase):
    """Module-level so a caller adding one element need not build a Bridge."""

    def test_ipv4_and_ipv6(self):
        from aciq.bridge import family_of
        self.assertEqual(family_of("10.0.1.2"), "ip")
        self.assertEqual(family_of("203.0.113.9"), "ip")
        self.assertEqual(family_of("2001:db8::2"), "ip6")
        self.assertEqual(family_of("fd00:1::2"), "ip6")

    def test_zone_id_does_not_raise(self):
        """A zone id would raise in socket.inet_pton. It must not raise from deep
        inside a classification tick."""
        from aciq.bridge import family_of
        self.assertEqual(family_of("fe80::1%eth0"), "ip6")

    def test_method_delegates_to_the_helper(self):
        from aciq.bridge import Bridge
        self.assertEqual(Bridge("d", "e").family_of("2001:db8::1"), "ip6")


class TestNamespaceDefault(unittest.TestCase):
    """`ns` defaults to None, which means "the current namespace".

    Documented rather than changed: making it mandatory would be the safer
    default, but it is a public keyword on five generators and the unit tests
    legitimately call them with ns=None.

    This footgun cost a gate run. The gate's `bmark` helper omitted `ns`, so
    `nft add element` ran in the host namespace where table `aciq` does not
    exist, and nft answered "No such file or directory" pointing at the SET
    name -- which reads like a missing set in the bridge rather than a missing
    namespace in the caller.
    """

    def test_ns_none_omits_the_prefix(self):
        self.assertEqual(
            generate_add_element("ip", V4, CLASS_BULK, ns=None)[:3], ("nft", "add", "element"))
        self.assertEqual(
            generate_add_element("ip", V4, CLASS_BULK, ns="router")[:4],
            ("ip", "netns", "exec", "router"))

    def test_every_generator_defaults_ns_to_none(self):
        import inspect
        for fn in (generate_add_element, generate_del_element,
                   generate_table, generate_sets, generate_rules,
                   generate_steer_filters, generate_teardown, generate_flush):
            self.assertIsNone(inspect.signature(fn).parameters["ns"].default, fn)

    def test_passing_a_namespace_changes_only_the_prefix(self):
        plain = bare(generate_add_element("ip", V4, CLASS_BULK))
        namespaced = bare(generate_add_element("ip", V4, CLASS_BULK, ns="router"))
        self.assertEqual(plain, namespaced)


