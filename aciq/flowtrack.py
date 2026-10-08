"""Per-flow observation from conntrack — M1 Stage B's data source.

conntrack was confirmed by gate checks 3, 11 and 13 to expose per-flow byte
counters separately, over IPv4 and IPv6, for loopback and forwarded traffic. This
module turns those cumulative counters into *behaviour* over time: rate, average
packet size, burstiness and duty cycle.

Parsing is line-based and deliberately tolerant: a metrics path that raises on
one malformed line loses the whole run. Counters are cumulative, so rates come
from deltas, and a counter that goes backwards is treated as a reset rather than
a negative rate.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field

from .classify import FlowFeatures
from .model import Flow

# First tuple of a conntrack line. The second (reply) tuple is ignored: we want
# the originator's view.
#
# The token count before `src=` differs by protocol and TCP state:
#   udp   17 29 src=...                                     (family, timeout)
#   tcp   6 431999 ESTABLISHED src=...                      (family, timeout, state)
#   tcp   6 120 SYN_SENT src=...
# Requiring a fixed token count silently drops every TCP flow, which is most
# real traffic — so the state token is optional.
_TUPLE_RE = re.compile(
    r"^(?P<proto>\w+)\s+\d+\s+\d+(?:\s+\S+)?\s+"
    r"src=(?P<src>\S+)\s+dst=(?P<dst>\S+)\s+"
    r"(?:sport=(?P<sport>\d+)\s+)?(?:dport=(?P<dport>\d+)\s+)?"
    r"packets=(?P<packets>\d+)\s+bytes=(?P<bytes>\d+)"
)


def parse_conntrack_line(line: str) -> Flow | None:
    """Extract the flow identity from a conntrack line. None if unparseable."""
    m = _TUPLE_RE.match(line.strip())
    if not m:
        return None
    g = m.groupdict()
    return Flow(
        src=g["src"],
        sport=int(g["sport"]) if g.get("sport") else 0,
        dst=g["dst"],
        dport=int(g["dport"]) if g.get("dport") else 0,
        proto=g["proto"],
    )


def parse_conntrack(text: str) -> dict[str, tuple[Flow, int, int]]:
    """-> {flow_key: (Flow, packets, bytes)} from `conntrack -L` output."""
    out: dict[str, tuple[Flow, int, int]] = {}
    for line in text.splitlines():
        flow = parse_conntrack_line(line)
        if flow is None:
            continue
        m = _TUPLE_RE.match(line.strip())
        g = m.groupdict()
        out[flow.key] = (flow, int(g["packets"]), int(g["bytes"]))
    return out


@dataclass
class _Sample:
    bytes: int = 0
    packets: int = 0
    increments: list[int] = field(default_factory=list)
    moving_samples: int = 0
    total_samples: int = 0
    first_seen: float = 0.0


class FlowTracker:
    """Accumulates conntrack snapshots into per-flow behaviour.

    Call observe() once per poll with the raw conntrack text. Call features()
    to get FlowFeatures for a flow.
    """

    def __init__(self, window: int = 10):
        #: how many increments to keep for burstiness. Small: burstiness is a
        #: recent-behaviour measure, and an unbounded list would let one old
        #: burst dominate forever.
        self.window = window
        self._samples: dict[str, _Sample] = {}
        self._now = 0.0

    def observe(self, text: str, now: float) -> None:
        self._now = now
        seen = parse_conntrack(text)
        for key, (flow, packets, total_bytes) in seen.items():
            s = self._samples.get(key)
            if s is None:
                s = _Sample(bytes=total_bytes, packets=packets, first_seen=now,
                            total_samples=1)
                s.flow = flow
                self._samples[key] = s
                continue
            delta = total_bytes - s.bytes
            # A counter that decreased means the flow was re-created (or the
            # table was flushed). Restart rather than report nonsense.
            if delta < 0:
                s.bytes = total_bytes
                s.packets = packets
                s.first_seen = now
                s.increments.clear()
                continue
            s.total_samples += 1
            if delta > 0:
                s.moving_samples += 1
            s.increments.append(delta)
            if len(s.increments) > self.window:
                s.increments.pop(0)
            s.bytes = total_bytes
            s.packets = packets

    def features(self, key: str, dscp: int | None = None) -> FlowFeatures | None:
        s = self._samples.get(key)
        if s is None:
            return None
        flow = getattr(s, "flow", None)
        if flow is None:
            return None
        age = max(0.0, self._now - s.first_seen)
        incs = s.increments
        mean = (sum(incs) / len(incs)) if incs else 0.0
        if mean > 0 and len(incs) >= 2:
            var = sum((x - mean) ** 2 for x in incs) / len(incs)
            burstiness = (var ** 0.5) / mean
        else:
            burstiness = 0.0
        duty = (s.moving_samples / s.total_samples) if s.total_samples else 0.0
        # Average packet size over the flow's life. This is the signal that
        # separates a large-packet bulk transfer from a small-packet call; it
        # comes from conntrack's own packet counter, not from any payload read.
        avg_pkt = (s.bytes / s.packets) if s.packets > 0 else 0.0
        return FlowFeatures(
            flow=flow,
            dscp=dscp,
            rx_bytes=s.bytes,
            packets=s.packets,
            age_s=age,
            avg_packet_bytes=avg_pkt,
            burstiness=burstiness,
            duty_cycle=duty,
        )

    def keys(self) -> list[str]:
        return list(self._samples)


class ConntrackSource:
    """Reads `conntrack -L` from a namespace. Needs root."""

    def __init__(self, ns: str = "router", runner=subprocess.run):
        self.ns = ns
        self._run = runner

    def read(self) -> str:
        try:
            r = self._run(
                ["ip", "netns", "exec", self.ns, "conntrack", "-L"],
                capture_output=True, text=True, timeout=5,
            )
            return r.stdout or ""
        except (OSError, subprocess.SubprocessError):
            return ""
