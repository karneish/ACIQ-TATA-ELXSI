"""Tests for the live tap and the feature merge.

Offline by construction:

- the socket is a fake (record frames, dummy recvfrom), so no root, no
  interface, no namespace is needed. `KernelTap` is written so that ONLY the
  device name and the frames matter to these tests.
- `select` is injectable (the `selector` kwarg), so "socket has nothing to
  read" is simulated by returning no fds.

The merge rules tested here are the honest ones the docstring rules say: the
owner of each field wins, None is never turned into a plausible-looking 0.
"""

from __future__ import annotations

import unittest

from aciq.features import FlowFeatures
from aciq.model import Flow
from aciq.observer import HeaderObserver
from aciq.tap import KernelTap, TapSource, merge_features


class FakeSocket:
    def __init__(self, frames):
        self.frames = list(frames)
        self.bound = None
        self.closed = False
        self.set_blocking = None

    def bind(self, addr):
        self.bound = addr

    def setblocking(self, flag):
        self.set_blocking = flag

    def recvfrom(self, cap):
        if not self.frames:
            raise BlockingIOError()
        return self.frames.pop(0), ("", 0)

    def close(self):
        self.closed = True


def always_readable(fds, *a):
    return fds, [], []


def never_readable(fds, *a):
    return [], [], []


def f4(src="10.0.2.15", sport=5000, dst="203.0.113.2", dport=7001,
       proto="udp"):
    return Flow(src=src, sport=sport, dst=dst, dport=dport, proto=proto)


def base_feats(identity_flow: Flow, **kw) -> FlowFeatures:
    return FlowFeatures(flow=identity_flow, rx_bytes=kw.get("rx_bytes", 1000),
                        tx_bytes=kw.get("tx_bytes", 100), packets=100,
                        age_s=60.0, avg_packet_bytes=11.0,
                        burstiness=kw.get("burstiness", 0.2),
                        dscp=kw.get("dscp", 0))


# ethernet + ipv4 + udp header for a knowable frame
def udp_frame(src="10.0.2.15", sport=5000, dst="203.0.113.2", dport=7001,
              body=b"x" * 24, i=None):
    payload = sport.to_bytes(2, "big") + dport.to_bytes(2, "big") + \
        (8 + len(body)).to_bytes(2, "big") + b"\x00\x00" + body
    total = 20 + len(payload)
    hdr = (0x45).to_bytes(1, "big") + b"\x00" + total.to_bytes(2, "big") + \
        b"\x00\x01\x00\x00\x40\x11\x00\x00" + \
        bytes(int(x) for x in src.split(".")) + \
        bytes(int(x) for x in dst.split("."))
    return b"\x01\x02\x03\x04\x05\x06" + b"\x11\x12\x13\x14\x15\x16" + \
        b"\x08\x00" + hdr + payload + (str(i).encode() if i is not None else b"") + b"TRAILING-HARMLESS"


class TestKernelTap(unittest.TestCase):
    def test_poll_drains_frames_and_counts_flows(self):
        obs = HeaderObserver(clock=lambda: 1.0)
        sock = FakeSocket([udp_frame(), udp_frame(dport=7002)])
        tap = KernelTap(obs, dev="veth-lan", socket_factory=lambda: sock,
                        selector=always_readable)
        n = tap.poll()
        self.assertEqual(n, 2)
        self.assertEqual(len(obs), 2)
        self.assertEqual(sock.bound[0], "veth-lan")
        self.assertTrue(sock.closed is False)   # close is explicit

    def test_poll_drains_at_most_bounded(self):
        obs = HeaderObserver(clock=lambda: 1.0)
        sock = FakeSocket([udp_frame(i=i) for i in range(4)])
        tap = KernelTap(obs, dev="veth-lan", socket_factory=lambda: sock,
                        selector=always_readable)
        n = 0
        for _ in range(10):
            n += tap.poll()
        self.assertEqual(n, 4)   # the fake socket refills only when frames exist
        # subsequent polls see a drained socket: the fake raises EAGAIN
        self.assertEqual(tap.poll(), 0)

    def test_poll_no_data(self):
        obs = HeaderObserver(clock=lambda: 1.0)
        sock = FakeSocket([])
        tap = KernelTap(obs, dev="veth-lan", socket_factory=lambda: sock,
                        selector=never_readable)
        self.assertEqual(tap.poll(), 0)
        self.assertEqual(tap.poll(1.0), 0)
        self.assertEqual(len(obs), 0)

    def test_close_stops_poll(self):
        obs = HeaderObserver(clock=lambda: 1.0)
        sock = FakeSocket([udp_frame()])
        tap = KernelTap(obs, dev="veth-lan", socket_factory=lambda: sock,
                        selector=always_readable)
        tap.poll()
        tap.close()
        self.assertEqual(tap.poll(), 0)
        self.assertTrue(sock.closed)


class TestMerge(unittest.TestCase):
    def test_dynamics_come_from_tap_only(self):
        fl = f4(dport=9000)
        base = [base_feats(fl)]
        tap = [FlowFeatures(flow=fl, rx_bytes=50, tx_bytes=0, packets=5,
                            age_s=5.0, pps=1.0, pkt_size_median=100.0,
                            pkt_size_p95=120.0, iat_regularity=0.9,
                            iat_median_s=0.01, down_share=1.0)]
        out = merge_features(base, tap)
        self.assertEqual(len(out), 1)
        m = out[0]
        # dynamics from tap:
        self.assertEqual(m.pkt_size_median, 100.0)
        self.assertEqual(m.iat_regularity, 0.9)
        self.assertEqual(m.down_share, 1.0)
        # base's byte totals win (base saw the flow earlier too)
        self.assertEqual((m.rx_bytes, m.tx_bytes), (1000, 100))
        # base's conntrack-side fields win
        self.assertEqual(m.burstiness, 0.2)
        self.assertEqual(m.packets, 100)

    def test_dynamics_stay_none_when_tap_is_silent(self):
        fl = f4(dport=9001)
        base = [base_feats(fl)]
        out = merge_features(base, [])
        self.assertIsNone(out[0].pkt_size_median)
        self.assertIsNone(out[0].iat_regularity)
        self.assertIsNone(out[0].pps)

    def test_tap_only_flow_included(self):
        fl = f4(dport=9002)
        tap = [FlowFeatures(flow=fl, rx_bytes=800, tx_bytes=0, packets=4,
                            age_s=4.0, pps=1.0, pkt_size_median=200.0)]
        out = merge_features([], tap)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0].rx_bytes, 800)
        self.assertEqual(out[0].pkt_size_median, 200.0)
        self.assertIsNone(out[0].burstiness)

    def test_base_zero_totals_fall_back_to_tap(self):
        """Zero bytes + 100 packets is a legitimate conntrack shape (acct
        slot missing): the tap's byte totals fill in, the base ROW keeps its
        packet count — each number keeps its own source, none is overwritten.
        """
        fl = f4(dport=9003)
        base = [base_feats(fl, rx_bytes=0, tx_bytes=0)]
        tap = [FlowFeatures(flow=fl, rx_bytes=4000, tx_bytes=0, packets=4,
                            age_s=4.0, pps=10.0)]
        out = merge_features(base, tap)
        self.assertEqual(out[0].rx_bytes, 4000)     # tap's totals fill in...
        self.assertEqual(out[0].packets, 100)       # ...but 100 packets was measured
        self.assertEqual(out[0].avg_packet_bytes, 11.0)  # base's own average

    def test_protocol_distinguishes_merge(self):
        # tcp and udp on the same tuple are TWO flows; never merged (this is
        # the exact `key`-without-proto bug the tracker had).
        f_tcp = f4(dport=9004, proto="tcp")
        f_udp = f4(dport=9004, proto="udp")
        base = [base_feats(f_tcp)]
        tap = [FlowFeatures(flow=f_udp, rx_bytes=9, tx_bytes=0, packets=1,
                            age_s=1.0, pps=1.0)]
        out = merge_features(base, tap)
        self.assertEqual(len(out), 2)
        tcp_row = [x for x in out if x.flow.proto == "tcp"][0]
        self.assertEqual(tcp_row.rx_bytes, 1000)     # base untouched
        self.assertIsNone(tcp_row.pkt_size_median)


class TestTapSource(unittest.TestCase):
    def test_refresh_merges_tracker_and_observer(self):
        class FakeTracker:
            def scan(self):
                return [base_feats(f4(dport=9005), rx_bytes=2000,
                                   tx_bytes=0, packets=44)]

        obs = HeaderObserver(clock=lambda: 7.0)
        obs.on_packet(udp_frame(sport=4000, dport=9006, dst="203.0.113.9"))
        src = TapSource(tracker=FakeTracker(), observer=obs)
        feats = src.refresh()
        self.assertEqual(len(feats), 2)
        be = [x for x in feats if x.flow.dport == 9005][0]
        te = [x for x in feats if x.flow.dport == 9006][0]
        self.assertEqual(be.rx_bytes, 2000)
        self.assertIsNone(be.pkt_size_median)
        self.assertIsNotNone(te.pkt_size_median)
        self.assertTrue(te.flow.identity.startswith("udp"))

    def test_pump_is_noop_without_tap(self):
        src = TapSource(tracker=None, observer=HeaderObserver())
        self.assertEqual(src.pump(), 0)


if __name__ == "__main__":
    unittest.main()
