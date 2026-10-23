"""Per-flow header-only observation, feeding aciq.features.

`, flowtrack` sees conntrack counters: byte totals and packet counts per flow,
averaged over the flow's whole life. It cannot see the DYNAMICS the extended
classifier rules need — packet-size distribution, inter-arrival regularity,
per-packet direction. This module captures those directly from the wire with
three hard constraints:

- **header-only**: parsing slices stop before the transport payload starts.
  Payload bytes never enter a Python object, so nothing derived from them can
  appear in state, reprs or features. A sentinel in the payload provably
  cannot leak — tests/test_observer.py proves it with a unique marker.
- **bounded capture**: frames are sliced to ``snaplen`` (default 96 bytes)
  before parsing. A tap handing us a 1500-byte buffer for a 96-byte-header
  packet cannot silently widen what we read.
- **bounded state**: per-flow rings hold at most ``window`` samples (default
  64), and flows idle longer than ``idle_s`` are evicted, the same way
  flowtrack drops them. Sixty-four samples cover 1-6 s of recent history at
  10-60 pps — enough for "regular ~60 pps, small packets, mostly down", not
  an unbounded recording.

IPv4 (incl. fragment skipping), IPv6 with its extension-header chain (walked
boundedly), TCP and UDP. Anything not parseable is counted in ``skipped`` and
never guessed at.
"""

from __future__ import annotations

import statistics
import time
from collections import deque
from dataclasses import dataclass

from .features import FlowFeatures, mean_cv
from .model import Flow

#: Ring depth per flow (packet sizes and inter-arrival gaps).
DEFAULT_WINDOW = 64

#: Frame capture bound, bytes. Ethernet + IPv4/6 + TCP/UDP headers fit;
#: everything beyond this bounds is memory we deliberately do not spend.
DEFAULT_SNAPLEN = 96

#: Flows idle longer than this are dropped by evict_idle()/features().
DEFAULT_IDLE_S = 30.0

#: Extension-header walk bound. Real packets end this chain within a few
#: hops; the bound stops a maliciously self-referential buffer from looping.
_MAX_EXT_HOPS = 8

_ETH_HDR_LEN = 14
_ETH_IPV4 = 0x0800
_ETH_IPV6 = 0x86DD
_IPPROTO_TCP = 6
_IPPROTO_UDP = 17
_IP_V6_HDR_LEN = 40

# IPv6 next-header values we walk past on the way to TCP/UDP
_EXT_NEXT_HEADERS = {0, 43, 44, 51, 60, 135, 139}


@dataclass(frozen=True)
class ParsedPacket:
    """What one frame contained, and nothing more (no payload reference)."""

    flow: Flow
    wire_bytes: int      # IP-datagram length from the header fields
    hdr_end: int         # offset just past the transport header in the frame


def _ip6(octets: bytes) -> str:
    """16 octets -> canonical lowercase colon hex, no zero compression."""
    return ":".join(format(int.from_bytes(octets[i:i + 2], "big"), "x")
                    for i in range(0, 16, 2))


def _ipv4(frame: bytes, off: int) -> ParsedPacket | None:
    if len(frame) < off + 20:
        return None
    ihl = (frame[off] & 0x0F) * 4
    if ihl < 20:
        return None
    proto = frame[off + 9]
    if proto not in (_IPPROTO_TCP, _IPPROTO_UDP):
        return None
    # non-first fragments carry no trusted ports; skip them, count nothing
    frag = int.from_bytes(frame[off + 6:off + 8], "big")
    if frag & 0x1FFF:
        return None
    total_len = int.from_bytes(frame[off + 2:off + 4], "big")
    src = ".".join(str(b) for b in frame[off + 12:off + 16])
    dst = ".".join(str(b) for b in frame[off + 16:off + 20])
    l4 = off + ihl
    if len(frame) < l4 + 4:
        return None
    sport = int.from_bytes(frame[l4:l4 + 2], "big")
    dport = int.from_bytes(frame[l4 + 2:l4 + 4], "big")
    # hdr_end = first offset this parser did NOT read: the tight UDP header
    # is 8 bytes (length + checksum we choose not to decode); TCP stopped
    # after the port fields.
    udp = proto == _IPPROTO_UDP
    return ParsedPacket(flow=Flow(src=src, sport=sport, dst=dst, dport=dport,
                                  proto="udp" if udp else "tcp"),
                        wire_bytes=total_len, hdr_end=l4 + (8 if udp else 4))


def _ipv6(frame: bytes, off: int) -> ParsedPacket | None:
    if len(frame) < off + _IP_V6_HDR_LEN:
        return None
    proto = frame[off + 6]
    l4 = off + _IP_V6_HDR_LEN
    payload_len = int.from_bytes(frame[off + 4:off + 6], "big")
    walk = 0
    while proto in _EXT_NEXT_HEADERS and walk < _MAX_EXT_HOPS:
        if len(frame) < l4 + 2:
            return None
        nxt = frame[l4]
        ext_len = (frame[l4 + 1] + 1) * 8 if proto != 44 else 8
        if len(frame) < l4 + ext_len:
            return None
        proto, l4 = nxt, l4 + ext_len
        walk += 1
    if proto not in (_IPPROTO_TCP, _IPPROTO_UDP):
        return None
    if len(frame) < l4 + 4:
        return None
    sport = int.from_bytes(frame[l4:l4 + 2], "big")
    dport = int.from_bytes(frame[l4 + 2:l4 + 4], "big")
    src = _ip6(frame[off + 8:off + 24])
    dst = _ip6(frame[off + 24:off + 40])
    udp = proto == _IPPROTO_UDP
    return ParsedPacket(
        flow=Flow(src=src, sport=sport, dst=dst, dport=dport,
                  proto="udp" if udp else "tcp"),
        wire_bytes=_IP_V6_HDR_LEN + payload_len, hdr_end=l4 + (8 if udp else 4))


def parse_frame(frame: bytes, snaplen: int = DEFAULT_SNAPLEN) -> ParsedPacket:
    """One ethernet frame -> ParsedPacket, or None if not TCP/UDP over IP.

    Bounded by ``snaplen``: only the first snaplen bytes are ever examined,
    and every slice below ends at or before the transport header end, so the
    payload region is never referenced.
    """
    frame = frame[:max(0, int(snaplen))]
    if len(frame) < _ETH_HDR_LEN:
        return None
    ethertype = int.from_bytes(frame[12:14], "big")
    if ethertype == _ETH_IPV4:
        return _ipv4(frame, _ETH_HDR_LEN)
    if ethertype == _ETH_IPV6:
        return _ipv6(frame, _ETH_HDR_LEN)
    return None


@dataclass
class _FlowRecord:
    """Bounded per-flow state. Every field is a header-side number."""

    flow: Flow
    sizes: deque                       # wire bytes per packet, last N
    gaps: deque                        # inter-arrival seconds, last N
    down_flags: deque                  # True = reply (down) direction, known
    first_seen: float
    last_seen: float = 0.0
    packets: int = 0
    bytes_tx: int = 0                  # originator->peer, when direction known
    bytes_rx: int = 0                  # reply direction, when direction known
    directed: int = 0                  # packets whose direction was known


class HeaderObserver:
    """Accumulates header-derived features per flow, bounded in all dims."""

    def __init__(self, window: int = DEFAULT_WINDOW,
                 idle_s: float = DEFAULT_IDLE_S,
                 snaplen: int = DEFAULT_SNAPLEN,
                 clock=time.monotonic):
        self._window = max(4, int(window))
        self._idle_s = float(idle_s)
        self._snaplen = int(snaplen)
        self._clock = clock
        self._flows: dict[tuple, _FlowRecord] = {}
        self.skipped = 0

    # ---- ingestion --------------------------------------------------------
    def on_packet(self, frame: bytes, ts: float | None = None,
                  towards_home: bool | None = None) -> bool:
        """Feed one captured frame from the tap.

        ``towards_home``: True if this packet travels in the reply (down)
        direction for the flow's *originator-facing* orientation used by
        ``FlowFeatures.rx_bytes``. None = direction not observable; the
        observer then reports unsplit counts and ``down_share=None`` rather
        than a guess. Returns True if the packet enriched a flow.
        """
        pkt = parse_frame(frame, self._snaplen)
        if pkt is None:
            self.skipped += 1
            return False
        now = self._clock() if ts is None else ts
        ident = pkt.flow.identity
        rec = self._flows.get(ident)
        if rec is None:
            rec = _FlowRecord(flow=pkt.flow,
                              sizes=deque(maxlen=self._window),
                              gaps=deque(maxlen=self._window),
                              down_flags=deque(maxlen=self._window),
                              first_seen=now)
            self._flows[ident] = rec
        else:
            rec.gaps.append(now - rec.last_seen)
        rec.sizes.append(pkt.wire_bytes)
        rec.last_seen = now
        rec.packets += 1
        if towards_home is not None:
            rec.directed += 1
            rec.down_flags.append(bool(towards_home))
            if towards_home:
                rec.bytes_rx += pkt.wire_bytes
            else:
                rec.bytes_tx += pkt.wire_bytes
        return True

    def evict_idle(self, cutoff_s: float | None = None) -> int:
        """Drop flows idle longer than the cutoff seconds. Returns count."""
        cutoff = self._clock() - (self._idle_s if cutoff_s is None
                                  else cutoff_s)
        stale = [k for k, r in self._flows.items() if r.last_seen < cutoff]
        for k in stale:
            del self._flows[k]
        return len(stale)

    # ---- projection -------------------------------------------------------
    def features(self, dscp: int | None = None,
                 correction=None) -> list[FlowFeatures]:
        """Project tracked flows into FlowFeatures (evicting idle first)."""
        self.evict_idle()
        out: list[FlowFeatures] = []
        for rec in self._flows.values():
            mean_ms, cv = mean_cv([g * 1000.0 for g in rec.gaps])
            regularity = None if cv is None else round(1.0 - min(cv, 1.0), 4)
            ordered = sorted(rec.sizes)
            median = statistics.median(rec.sizes) if rec.sizes else None
            if ordered:
                # sample p95, nearest-rank convention
                lo = 0.95 * len(ordered)
                idx = min(len(ordered) - 1, int(lo))
                p95 = ordered[idx]
            else:
                p95 = None
            fully_directed = rec.directed == rec.packets and rec.packets > 0
            age = max(rec.last_seen - rec.first_seen, 1e-6)
            out.append(FlowFeatures(
                flow=rec.flow,
                dscp=dscp,
                rx_bytes=rec.bytes_rx if fully_directed else 0,
                tx_bytes=rec.bytes_tx if fully_directed else 0,
                packets=rec.packets,
                age_s=age,
                # ringed recent-window average: after the ring rotates, the
                # early big packets are forgotten; the flowtrack average would
                # not be. Recorded as what the window actually saw.
                avg_packet_bytes=(sum(rec.sizes) / len(rec.sizes)
                                  if rec.sizes else 0.0),
                # burstiness/duty-cycle are conntrack-increment concepts; the
                # header observer does not fabricate them. See features doc.
                burstiness=None,
                duty_cycle=None,
                correction=correction,
                iat_regularity=regularity,
                iat_median_s=None if mean_ms is None else mean_ms / 1000.0,
                pkt_size_median=median,
                pkt_size_p95=p95,
                pps=(rec.packets / age) if age > 0 else None,
                down_share=(sum(1 for f in rec.down_flags if f)
                            / len(rec.down_flags)) if fully_directed else None,
            ))
        return out

    def __len__(self) -> int:
        return len(self._flows)

    def ids(self) -> list[str]:
        return sorted(self._flows)
