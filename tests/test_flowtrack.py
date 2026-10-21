"""Tests for the conntrack flow tracker.

Three defects fixed here, all found in the pre-acceptance audit:

1. Reply-direction counters were dropped. The regex only matched the origin
   tuple, but conntrack prints per-direction counters and the reply direction
   carries the payload — a download's bytes arrive as the reply to a small
   request. The tracker classified heavy downloads by their request packets.
2. The sample map was keyed by `Flow.key`, which has no protocol: tcp and udp
   flows on the same 4-tuple merged into one sample with one set of counters.
3. Flows were never evicted: a long run accumulated every flow conntrack had
   ever shown, and `flows()` kept offering dead flows to the matcher.

Everything here is string-level: no root, no conntrack binary, no network.
"""

from __future__ import annotations

import unittest

from aciq.flowtrack import (
    FLOW_EVICT_IDLE_S,
    FlowTracker,
    parse_conntrack,
    parse_conntrack_line,
)
from aciq.model import Flow

# Real conntrack -L format, from docs/evidence/gate-*.log (acct=1).
UDP_LINE = ("udp      17 29 src=203.0.113.2 dst=10.0.1.2 sport=60525 "
            "dport=7001 packets=4771 bytes=4904588 [UNREPLIED] "
            "src=10.0.1.2 dst=203.0.113.2 sport=7001 dport=60525 "
            "packets=0 bytes=0 mark=0 use=1")

# A download: the originator (client) sent 1.2 kB of requests; the reply
# direction carries 9.5 MB of payload. This is the asymmetry case.
DOWNLOAD_LINE = ("tcp  6 431999 ESTABLISHED src=10.0.1.2 dst=203.0.113.9 "
                 "sport=40000 dport=443 packets=10 bytes=1200 [ASSURED] "
                 "src=203.0.113.9 dst=10.0.1.2 sport=443 dport=40000 "
                 "packets=8000 bytes=9500000 mark=0 use=1")

# Same tuple, both protocols: the DNS resolver does udp and tcp to one server.
DNS_UDP = ("udp      17 29 src=10.0.1.2 dst=10.0.1.53 sport=50000 "
           "dport=53 packets=100 bytes=10000 [UNREPLIED] src=10.0.1.53 "
           "dst=10.0.1.2 sport=53 dport=50000 packets=50 bytes=6000 "
           "mark=0 use=1")
DNS_TCP = ("tcp  6 431999 ESTABLISHED src=10.0.1.2 dst=10.0.1.53 "
           "sport=50000 dport=53 packets=50 bytes=4000 [ASSURED] "
           "src=10.0.1.53 dst=10.0.1.2 sport=53 dport=50000 "
           "packets=40 bytes=9000 mark=0 use=1")


class TestReplyDirectionCounters(unittest.TestCase):
    def test_reply_bytes_and_packets_are_summed(self):
        parsed = parse_conntrack(DOWNLOAD_LINE)
        self.assertEqual(len(parsed), 1)
        (_flow, packets, total_bytes) = next(iter(parsed.values()))
        self.assertEqual(packets, 8010)
        self.assertEqual(total_bytes, 9501200)

    def test_zero_reply_leaves_totals_unchanged(self):
        parsed = parse_conntrack(UDP_LINE)
        (_flow, packets, total_bytes) = next(iter(parsed.values()))
        self.assertEqual(packets, 4771)
        self.assertEqual(total_bytes, 4904588)

    def test_line_without_reply_tuple_still_parses(self):
        line = ("udp 17 29 src=192.0.2.1 dst=198.51.100.2 sport=1 "
                "dport=9 packets=5 bytes=400")
        f = parse_conntrack_line(line)
        self.assertIsNotNone(f)
        parsed = parse_conntrack(line)
        (_f, packets, total_bytes) = next(iter(parsed.values()))
        self.assertEqual((packets, total_bytes), (5, 400))

    def test_rate_reflects_download_direction(self):
        t = FlowTracker()
        t.observe(DOWNLOAD_LINE, 0.0)
        # Reply bytes double between samples: 9.5 MB -> 19 MB payload.
        grown = DOWNLOAD_LINE.replace("9500000", "19000000") \
                             .replace("packets=8000", "packets=16000")
        t.observe(grown, 1.0)
        f = t.features(Flow(src="10.0.1.2", sport=40000,
                            dst="203.0.113.9", dport=443, proto="tcp").identity)
        self.assertIsNotNone(f)
        self.assertEqual(f.rx_bytes, 19001200)
        self.assertGreater(f.age_s, 0.0)


class TestProtocolInIdentity(unittest.TestCase):
    def test_identity_carries_the_protocol(self):
        flow = Flow(src="10.0.1.2", sport=50000, dst="10.0.1.53", dport=53,
                    proto="tcp")
        self.assertEqual(flow.identity, "tcp 10.0.1.2:50000->10.0.1.53:53")
        self.assertEqual(flow.key, "10.0.1.2:50000->10.0.1.53:53")

    def test_tcp_and_udp_on_one_tuple_do_not_merge(self):
        t = FlowTracker()
        t.observe(DNS_TCP + "\n" + DNS_UDP + "\n", 0.0)
        self.assertEqual(len(t.keys()), 2)
        udp = t.features("udp 10.0.1.2:50000->10.0.1.53:53")
        tcp = t.features("tcp 10.0.1.2:50000->10.0.1.53:53")
        self.assertIsNotNone(udp)
        self.assertIsNotNone(tcp)
        # tcp totals 13 000 (4000+9000), udp totals 16 000 (10000+6000).
        self.assertEqual(udp.rx_bytes, 16000)
        self.assertEqual(tcp.rx_bytes, 13000)
        self.assertEqual(udp.packets, 150)
        self.assertEqual(tcp.packets, 90)

    def test_legacy_flow_key_still_resolves(self):
        """experiment used to pass Flow.key; features() accepts it as a
        fallback so no caller breaks, with identity as the exact path."""
        t = FlowTracker()
        t.observe(DNS_TCP + "\n", 0.0)
        f = t.features("10.0.1.2:50000->10.0.1.53:53")
        self.assertIsNotNone(f)
        self.assertEqual(f.flow.proto, "tcp")

    def test_unknown_key_is_none(self):
        t = FlowTracker()
        t.observe(DNS_TCP + "\n", 0.0)
        self.assertIsNone(t.features("192.0.2.9:1->192.0.2.9:2"))


class TestEviction(unittest.TestCase):
    def test_absent_flows_are_evicted_after_the_idle_window(self):
        t = FlowTracker()
        t.observe(UDP_LINE, 0.0)
        # A later successful dump no longer contains this flow (other flows
        # still present — the table is alive, this entry is gone).
        other = UDP_LINE.replace("dport=7001", "dport=7002") \
                        .replace("sport=7001", "sport=7002")
        t.observe(other, FLOW_EVICT_IDLE_S + 1.0)
        self.assertNotIn("udp 203.0.113.2:60525->10.0.1.2:7001", t.keys(),
                         "a flow gone from conntrack must be forgotten, not "
                         "served forever")
        self.assertIn("udp 203.0.113.2:60525->10.0.1.2:7002", t.keys(),
                      "flows still in the table must survive the sweep")

    def test_flows_present_recently_survive(self):
        t = FlowTracker()
        t.observe(UDP_LINE, 0.0)
        t.observe(UDP_LINE, FLOW_EVICT_IDLE_S - 1.0)
        self.assertEqual(len(t.keys()), 1)
        t.observe(UDP_LINE.replace("4904588", "4905588"), FLOW_EVICT_IDLE_S)
        self.assertEqual(len(t.keys()), 1)

    def test_a_failed_read_never_evicts(self):
        """conntrack racing a flush returns "". Reading that as "the table is
        empty" would wipe the run's whole state on one transient error."""
        t = FlowTracker()
        t.observe(UDP_LINE, 0.0)
        t.observe("", FLOW_EVICT_IDLE_S * 10)
        self.assertEqual(len(t.keys()), 1, "an empty/failed read must not "
                                           "evict tracked flows")

    def test_first_seen_survives_non_growing_samples(self):
        t = FlowTracker()
        t.observe(UDP_LINE, 5.0)
        t.observe(UDP_LINE, 6.0)  # same counters: no growth, still present
        f = t.features(Flow(src="203.0.113.2", sport=60525,
                            dst="10.0.1.2", dport=7001, proto="udp").identity)
        self.assertIsNotNone(f)
        self.assertEqual(f.age_s, 1.0)


class TestResetBehaviour(unittest.TestCase):
    def test_counter_decrease_restarts_the_sample(self):
        t = FlowTracker()
        t.observe(UDP_LINE, 0.0)
        t.observe(UDP_LINE.replace("4904588", "1000").replace("4771", "5"),
                  1.0)
        f = t.features(Flow(src="203.0.113.2", sport=60525,
                            dst="10.0.1.2", dport=7001, proto="udp").identity)
        self.assertIsNotNone(f)
        self.assertEqual(f.rx_bytes, 1000)
        # History restarted: increments cleared, first_seen moved.
        self.assertEqual(f.age_s, 0.0)


if __name__ == "__main__":
    unittest.main()
