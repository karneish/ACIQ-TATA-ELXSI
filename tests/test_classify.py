"""M1 classifier and flow tracker tests. No root, no network, no conntrack binary."""

from __future__ import annotations

import unittest

from aciq.classify import (
    BULK_MIN_AVG_PACKET,
    DSCP_EF,
    MIN_CONFIDENCE,
    classify,
    finalise,
)
from aciq.flowtrack import FlowTracker, parse_conntrack, parse_conntrack_line
from aciq.model import Flow, TrafficClass

# Real conntrack lines captured from the passing gate run (check 11, IPv4).
GATE_V4 = """udp 17 29 src=203.0.113.2 dst=10.0.1.2 sport=60778 dport=7001 packets=4592 bytes=4720576 [UNREPLIED] src=10.0.1.2 dst=203.0.113.2 sport=7001 dport=60778 packets=0 bytes=0 mark=0 use=1
udp 17 29 src=203.0.113.2 dst=10.0.1.2 sport=47126 dport=7002 packets=4592 bytes=1046976 [UNREPLIED] src=10.0.1.2 dst=203.0.113.2 sport=7002 dport=47126 packets=0 bytes=0 mark=0 use=1"""

# check 13, IPv6
GATE_V6 = """udp 17 29 src=fd00:2::2 dst=fd00:1::2 sport=53489 dport=7003 packets=4582 bytes=4801936 [UNREPLIED] src=fd00:1::2 dst=fd00:2::2 sport=7003 dport=53489 packets=0 bytes=0 mark=0 use=1"""


def feats(**kw) -> "object":
    from aciq.classify import FlowFeatures
    base = dict(flow=Flow("10.0.1.2", 50000, "203.0.113.2", 443, "udp"))
    base.update(kw)
    return FlowFeatures(**base)


class TestConntrackParsing(unittest.TestCase):
    """Parsed against output the laptop actually produced."""

    def test_parses_gate_ipv4_line(self):
        f = parse_conntrack_line(GATE_V4.splitlines()[0])
        self.assertEqual(f.src, "203.0.113.2")
        self.assertEqual(f.dport, 7001)
        self.assertEqual(f.proto, "udp")

    def test_parses_gate_ipv6_line(self):
        f = parse_conntrack_line(GATE_V6)
        self.assertEqual(f.src, "fd00:2::2")
        self.assertEqual(f.dport, 7003)

    def test_reply_tuple_is_not_mistaken_for_origin(self):
        # origin dport 7001, reply dport 60778 — must read 7001
        f = parse_conntrack_line(GATE_V4.splitlines()[0])
        self.assertNotEqual(f.dport, 60778)

    def test_two_flows_parse_separately(self):
        d = parse_conntrack(GATE_V4)
        self.assertEqual(len(d), 2)
        self.assertEqual(d["203.0.113.2:60778->10.0.1.2:7001"][2], 4720576)

    def test_junk_returns_none(self):
        self.assertIsNone(parse_conntrack_line("conntrack v1.4.8: 2 flow entries"))
        self.assertIsNone(parse_conntrack_line(""))

    def test_tcp_line(self):
        line = ("tcp 6 431999 ESTABLISHED src=10.0.1.2 dst=203.0.113.9 "
                "sport=41000 dport=443 packets=100 bytes=150000 "
                "src=203.0.113.9 dst=10.0.1.2 sport=443 dport=41000 "
                "packets=90 bytes=140000 [ASSURED] mark=0 use=1")
        f = parse_conntrack_line(line)
        self.assertEqual(f.proto, "tcp")
        self.assertEqual(f.dport, 443)


class TestFlowTracker(unittest.TestCase):
    def test_single_sample_produces_features(self):
        t = FlowTracker()
        t.observe(GATE_V4, now=0.0)
        f = t.features("203.0.113.2:60778->10.0.1.2:7001")
        self.assertIsNotNone(f)
        self.assertEqual(f.rx_bytes, 4720576)

    def test_avg_packet_size_from_counters(self):
        t = FlowTracker()
        t.observe(GATE_V4, now=0.0)
        f = t.features("203.0.113.2:60778->10.0.1.2:7001")
        self.assertAlmostEqual(f.avg_packet_bytes, 4720576 / 4592, places=2)

    def test_age_accumulates(self):
        t = FlowTracker()
        t.observe(GATE_V4, now=0.0)
        t.observe(GATE_V4, now=10.0)
        f = t.features("203.0.113.2:60778->10.0.1.2:7001")
        self.assertAlmostEqual(f.age_s, 10.0)

    def test_counter_reset_does_not_go_negative(self):
        t = FlowTracker()
        t.observe(GATE_V4, now=0.0)
        t.observe(GATE_V4, now=1.0)
        smaller = GATE_V4.replace("bytes=4720576", "bytes=100")
        t.observe(smaller, now=2.0)
        f = t.features("203.0.113.2:60778->10.0.1.2:7001")
        self.assertEqual(f.rx_bytes, 100)
        self.assertAlmostEqual(f.age_s, 0.0, places=6)  # restarted, not negative

    def test_duty_cycle_between_zero_and_one(self):
        t = FlowTracker()
        t.observe(GATE_V4, now=0.0)
        for i in range(1, 6):
            t.observe(GATE_V4.replace("bytes=4720576", f"bytes={4720576 + i * 1000}"), now=float(i))
        f = t.features("203.0.113.2:60778->10.0.1.2:7001")
        self.assertGreaterEqual(f.duty_cycle, 0.0)
        self.assertLessEqual(f.duty_cycle, 1.0)

    def test_unknown_key_returns_none(self):
        self.assertIsNone(FlowTracker().features("nope"))

    def test_burstiness_is_bounded_window(self):
        t = FlowTracker(window=3)
        t.observe(GATE_V4, now=0.0)
        for i in range(1, 8):
            t.observe(GATE_V4.replace("bytes=4720576", f"bytes={4720576 + i * 1000}"), now=float(i))
        f = t.features("203.0.113.2:60778->10.0.1.2:7001")
        self.assertGreaterEqual(f.burstiness, 0.0)


class TestTierA(unittest.TestCase):
    def test_dscp_ef_is_high_confidence_interactive(self):
        c = classify(feats(dscp=DSCP_EF, avg_packet_bytes=300))
        self.assertEqual(c.cls, TrafficClass.INTERACTIVE)
        self.assertGreaterEqual(c.confidence, 0.9)
        self.assertEqual(c.tier, "A")

    def test_dscp_beats_every_other_signal(self):
        # EF wins even when the statistics look like a bulk transfer
        c = classify(feats(dscp=DSCP_EF, avg_packet_bytes=1500, duty_cycle=1.0, age_s=10))
        self.assertEqual(c.cls, TrafficClass.INTERACTIVE)

    def test_stun_port_is_interactive(self):
        c = classify(feats(flow=Flow("10.0.1.2", 1, "203.0.113.2", 3478, "udp")))
        self.assertEqual(c.cls, TrafficClass.INTERACTIVE)

    def test_classifier_ignores_generator_ports(self):
        """Guards against a circular 100% accuracy result. The generators use
        5001-5004; none of them may appear in the rule tables."""
        from aciq.classify import INTERACTIVE_PORTS, BULK_PORTS
        for p in (5001, 5002, 5003, 5004):
            self.assertNotIn(p, INTERACTIVE_PORTS)
            self.assertNotIn(p, BULK_PORTS)


class TestTierB(unittest.TestCase):
    def test_large_continuous_packets_are_bulk(self):
        c = classify(feats(
            flow=Flow("10.0.1.2", 1, "203.0.113.2", 443, "tcp"),
            avg_packet_bytes=BULK_MIN_AVG_PACKET + 100, duty_cycle=0.95, age_s=5.0))
        self.assertEqual(c.cls, TrafficClass.BULK)
        self.assertEqual(c.tier, "B")

    def test_large_but_short_flow_is_not_bulk(self):
        c = classify(feats(avg_packet_bytes=1500, duty_cycle=1.0, age_s=0.5))
        self.assertNotEqual(c.cls, TrafficClass.BULK)

    def test_large_but_intermittent_is_not_bulk(self):
        c = classify(feats(avg_packet_bytes=1500, duty_cycle=0.2, age_s=10.0))
        self.assertNotEqual(c.cls, TrafficClass.BULK)

    def test_small_packets_are_interactive_udp(self):
        c = classify(feats(avg_packet_bytes=250, packets=100, age_s=5.0))
        self.assertEqual(c.cls, TrafficClass.INTERACTIVE)
        self.assertLess(c.confidence, 0.6)  # weak evidence, not strong


class TestHonestGap(unittest.TestCase):
    """The UDP/443 ambiguity is reported, not guessed."""

    def test_ambiguous_udp443_is_unclassified(self):
        c = classify(feats(
            flow=Flow("10.0.1.2", 1, "203.0.113.2", 443, "udp"),
            avg_packet_bytes=800, duty_cycle=0.5, age_s=5.0, packets=200))
        self.assertIsNone(c.cls)
        self.assertIn("ambiguous", c.evidence)

    def test_ambiguous_udp443_below_min_confidence(self):
        c = classify(feats(flow=Flow("10.0.1.2", 1, "203.0.113.2", 443, "udp"),
                           avg_packet_bytes=800, duty_cycle=0.5, age_s=5.0, packets=200))
        self.assertLess(c.confidence, MIN_CONFIDENCE)

    def test_dscp_resolves_udp443(self):
        # same ambiguous flow, but marked EF -> confidently interactive
        c = classify(feats(flow=Flow("10.0.1.2", 1, "203.0.113.2", 443, "udp"),
                           dscp=DSCP_EF, avg_packet_bytes=800))
        self.assertEqual(c.cls, TrafficClass.INTERACTIVE)

    def test_big_udp443_is_bulk(self):
        c = classify(feats(flow=Flow("10.0.1.2", 1, "203.0.113.2", 443, "udp"),
                           avg_packet_bytes=1500, duty_cycle=0.95, age_s=6.0))
        self.assertEqual(c.cls, TrafficClass.BULK)


class TestFinalise(unittest.TestCase):
    def test_low_confidence_demoted(self):
        c = finalise(classify(feats(avg_packet_bytes=800, duty_cycle=0.5, age_s=5.0, packets=200)))
        self.assertIsNone(c.cls)

    def test_high_confidence_preserved(self):
        c = finalise(classify(feats(dscp=DSCP_EF)))
        self.assertEqual(c.cls, TrafficClass.INTERACTIVE)

    def test_no_class_never_raises(self):
        c = finalise(classify(feats()))
        self.assertIsNone(c.cls)
        self.assertLess(c.confidence, MIN_CONFIDENCE)


if __name__ == "__main__":
    unittest.main()
