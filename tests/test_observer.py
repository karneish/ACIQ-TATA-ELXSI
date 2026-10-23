"""Tests for the header-only flow observer.

Proves the module's three constraints offline (string-built frames, a fake
clock, no sockets, no root):

1. **header-only**: a sentinel string placed in the payload of every test
   frame can never appear in observer state, ids, reprs or features —
   parse slices stop at the transport header, and nothing else is examined.
2. **bounded capture**: shorter-than-header frames and byte-ringed buffers
   behave (None or a parsed packet), never a crash, never an over-read.
3. **bounded state**: rings never exceed the window; idle flows are evicted.

Plus the arithmetic that powers tshe classifier's extended rules: packet-size
median/p95, inter-arrival regularity 1-CV, pps, and the direction split that
only reports a share when EVERY packet's direction was known.
"""

from __future__ import annotations

import unittest

from aciq.features import FlowFeatures
from aciq.model import Flow
from aciq.observer import (
    DEFAULT_WINDOW,
    HeaderObserver,
    parse_frame,
)

PAYLOAD_SENTINEL = "SECRET-CANARY-0x7c3f"

# A fake monotonic clock controllable per test.
class _Clock:
    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


# ---- frame builders (string-level, IPv4/IPv6/UDP; nothing beyond UDP) -----
def eth(payload_types: int, body: bytes) -> bytes:
    head = bytes.fromhex("020304050607") + bytes.fromhex("020304050608")  # MACs
    return head + payload_types.to_bytes(2, "big") + body


def udp_hdr(sport: int, dport: int, body: bytes) -> bytes:
    return sport.to_bytes(2, "big") + dport.to_bytes(2, "big") + \
        (8 + len(body)).to_bytes(2, "big") + b"\x00\x00" + body


def ip4_udp(sport: int, dport: int, body: bytes, src: str = "10.0.2.15",
            dst: str = "203.0.113.2") -> bytes:
    payload = udp_hdr(sport, dport, body)
    total = 20 + len(payload)
    def ip_oct(s: str) -> bytes:
        return bytes(int(x) for x in s.split("."))
    ihdr = (0x45).to_bytes(1, "big") + b"\x00" + total.to_bytes(2, "big") + \
        b"\x00\x01" + b"\x00\x00" + b"\x40" + b"\x11" + b"\x00\x00" + \
        ip_oct(src) + ip_oct(dst)
    assert len(ihdr) == 20, len(ihdr)
    return eth(0x0800, ihdr + payload)


def ip6_udp(sport: int, dport: int, body: bytes, src: str = "fd00:2::2",
            dst: str = "fd00:1::2") -> bytes:
    import ipaddress
    payload = udp_hdr(sport, dport, body)
    ihdr = (0x60).to_bytes(1, "big") + b"\x00\x00\x00" + \
        len(payload).to_bytes(2, "big") + b"\x11" + b"\x40" + \
        int(ipaddress.IPv6Address(src)).to_bytes(16, "big") + \
        int(ipaddress.IPv6Address(dst)).to_bytes(16, "big")
    assert len(ihdr) == 40, len(ihdr)
    return eth(0x86DD, ihdr + payload)


def frame_with_sentinel(mk) -> bytes:
    """Any built frame, with the sentinel riding in the [UDP payload]."""
    return mk(b"1234" + PAYLOAD_SENTINEL.encode())


# --------------------------------------------------------------------------
class TestParse(unittest.TestCase):
    def test_ipv4_udp_identity_and_size(self):
        pkt = parse_frame(ip4_udp(52217, 7001, b"hi"))
        self.assertIsNotNone(pkt)
        self.assertEqual(pkt.flow.src, "10.0.2.15")
        self.assertEqual(pkt.flow.dst, "203.0.113.2")
        self.assertEqual((pkt.flow.sport, pkt.flow.dport), (52217, 7001))
        self.assertEqual(pkt.flow.proto, "udp")
        # 20 (IP) + 8 (UDP) + 2 (payload) as declared, NOT the wire size of
        # the frame we built (which includes 14 bytes of eth).
        self.assertEqual(pkt.wire_bytes, 30)
        self.assertEqual(pkt.hdr_end, 14 + 20 + 8)

    def test_ipv6_udp_identity(self):
        pkt = parse_frame(ip6_udp(40000, 22, b"x" * 10,
                                  src="fd00:2::1", dst="fd00:1::1"))
        self.assertIsNotNone(pkt)
        self.assertEqual(pkt.flow.proto, "udp")
        # parser emits uncompressed colon hex, no "::" compression
        self.assertTrue(pkt.flow.src.startswith("fd00:2:"))
        self.assertTrue(pkt.flow.dst.startswith("fd00:1:"))
        self.assertEqual(pkt.wire_bytes, 48 + 10)

    def test_short_and_garbage_frames(self):
        self.assertIsNone(parse_frame(b""))
        self.assertIsNone(parse_frame(b"\x00" * 13))
        self.assertIsNone(parse_frame(eth(0x0800, b"\x00")))  # 1-byte "IP"
        arp = eth(0x0806, b"\x00" * 28)   # ARP, not IP
        self.assertIsNone(parse_frame(arp))

    def test_non_first_fragment_skipped(self):
        body = ip4_udp(1, 2, b"")
        # force fragment offset = 8 in the frag/flags byte, top unspecified
        frame = bytearray(body)
        frame[14 + 7] = frame[14 + 7] | 0x08  # frag_off low bits -> 8
        self.assertIsNone(parse_frame(bytes(frame)))

    def test_snaplen_bound_reduces_parses(self):
        full = ip4_udp(9, 9, b"paced")
        # 96-byte default snaplen still leaves UDP header intact
        self.assertIsNotNone(parse_frame(full, snaplen=96))
        # snaplen 30: not even the IP header ports fit -> None, not a crash
        self.assertIsNone(parse_frame(full, snaplen=30))


class TestObserverAccumulation(unittest.TestCase):
    def _obs(self, **kw) -> tuple[HeaderObserver, _Clock]:
        c = _Clock()
        return HeaderObserver(clock=c, **kw), c

    def test_p3_extended_fields(self):
        obs, c = self._obs()
        f = frame_with_sentinel(lambda b: ip4_udp(40001, 7002, b))
        # 40 packets, every 10 ms, same size -> pps 100, regularity 1.0
        for _ in range(40):
            c.advance(0.01)
            self.assertTrue(obs.on_packet(f))
        feats = obs.features()
        self.assertEqual(len(feats), 1)
        ff = feats[0]
        self.assertIsInstance(ff, FlowFeatures)
        self.assertAlmostEqual(ff.pkt_size_median,
                               20 + 8 + 4 + len(PAYLOAD_SENTINEL))
        self.assertAlmostEqual(ff.iat_regularity, 1.0, places=4)
        # pps = packets / observed span; the span excludes the interval that
        # led in to the first packet, so 40 packets over 39 declared gaps
        # lands slightly above the nominal rate. At steady state this bias
        # is one-sample in n; here n=40 -> ~102.
        self.assertAlmostEqual(ff.pps, 100 * 40 / 39, delta=1.0)
        self.assertEqual(ff.packets, 40)
        # untouched fields stay the dataclass defaults: observer does not
        # fabricate conntrack-only concepts
        self.assertIsNone(ff.burstiness)
        self.assertIsNone(ff.duty_cycle)

    def test_down_share_only_when_fully_directed(self):
        obs, c = self._obs()
        f = frame_with_sentinel(lambda b: ip4_udp(40001, 7003, b))
        for i in range(10):
            c.advance(0.1)
            obs.on_packet(f, towards_home=(i % 2 == 0))  # 5 up / 5 down
        ff = obs.features()[0]
        # 10 directed / 10 packets -> share known
        self.assertAlmostEqual(ff.down_share, 0.5)
        self.assertEqual(ff.packets, 10)

        obs2, c2 = self._obs()
        for i in range(10):
            c2.advance(0.1)
            obs2.on_packet(f, towards_home=True if i < 5 else None)
        ff2 = obs2.features()[0]
        self.assertIsNone(ff2.down_share)   # 5 undirectional -> no guess
        self.assertEqual(ff2.rx_bytes, 0)   # split unknown -> no split bytes

    def test_window_bound_and_idle_eviction(self):
        obs, c = self._obs(window=8, idle_s=1.0)
        f = frame_with_sentinel(lambda b: ip4_udp(40001, 7004, b))
        g = frame_with_sentinel(lambda b: ip4_udp(40001, 7005, b))
        for i in range(50):
            c.advance(0.1)
            obs.on_packet(f)
        c.advance(0.1)
        obs.on_packet(g)
        self.assertEqual(len(obs), 2)
        ff = [x for x in obs.features() if x.flow.dport == 7004][0]
        self.assertEqual(ff.packets, 50)      # total counts stay exact
        # ring kept last 8 sizes, so the p95 of the ring is the max of them
        self.assertLessEqual(ff.pkt_size_p95, 20 + 8 + 4 + len(PAYLOAD_SENTINEL))
        ff2 = [x for x in obs.features() if x.flow.dport == 7005][0]
        self.assertEqual(ff2.packets, 1)
        # evict: c is past idle (g seen 0.2 s ago; idle at 1.0 s)
        c.advance(1.5)
        self.assertEqual(obs.evict_idle(), 2)
        self.assertEqual(len(obs), 0)

    def test_regularity_distinguishes_uniform_from_jitter(self):
        obs, c = self._obs()
        f = frame_with_sentinel(lambda b: ip4_udp(50001, 7009, b))
        for delay in (0.02, 0.02, 0.02, 0.02, 0.02):
            c.advance(delay)
            obs.on_packet(f)
        a = obs.features()[0].iat_regularity
        obs2, c2 = self._obs()
        for delay in (0.005, 0.05, 0.02, 0.04, 0.001):
            c2.advance(delay)
            obs2.on_packet(f)
        b = obs2.features()[0].iat_regularity
        self.assertGreater(a, b)
        self.assertAlmostEqual(a, 1.0, places=4)

    def test_seed_and_flow_identity_is_proto_aware(self):
        obs, c = self._obs()
        f6 = frame_with_sentinel(lambda b: ip6_udp(7007, 7007, b))
        self.assertTrue(obs.on_packet(f6))
        self.assertEqual(len(obs), 1)
        self.assertIn("udp", obs.ids()[0])
        self.assertTrue(obs.ids()[0].startswith("udp"))


class TestPrivacy(unittest.TestCase):
    def test_payload_sentinel_never_leaks(self):
        """The sentinels in the payload are unreadacross in ALL projections."""
        c = _Clock()
        obs = HeaderObserver(clock=c)
        frames = [
            frame_with_sentinel(lambda b: ip4_udp(60001, 7010, b)),
            frame_with_sentinel(lambda b: ip4_udp(60001, 7010, b)),
            frame_with_sentinel(lambda b: ip6_udp(60002, 7011, b)),
        ]
        t = 0.0
        for f in frames:
            for i in range(3):
                t += 0.02
                obs.on_packet(f, ts=t, towards_home=i % 2 == 0)
        blobs = [repr(obs), repr(obs.ids()), repr(obs.features())]
        feats = obs.features()
        for ff in feats:
            blobs.append(repr(ff))
            blobs.append(repr(ff.flow))
        # the observer sees the packet SIZES (which the sentinel inflates),
        # but its bytes must be nowhere in any projection as text
        for blob in blobs:
            self.assertNotIn(PAYLOAD_SENTINEL, blob)
            self.assertNotIn(PAYLOAD_SENTINEL.encode().hex(), blob)
        # and the parse function itself cannot hand one back: ParsedPacket
        # carries only (flow, wire_bytes, hdr_end) — assert the field set
        pkt = parse_frame(frames[0])
        self.assertEqual(set(pkt.__dict__.keys()),
                         {"flow", "wire_bytes", "hdr_end"})


if __name__ == "__main__":
    unittest.main()
