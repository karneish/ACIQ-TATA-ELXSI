"""Live header tap: AF_PACKET ingestion and the feature merge point.

`, observer.py` parses frames offline; this is the piece that binds a real
socket to a real interface and hands frames over, plus the place where the
observer's per-flow hints merge with whatever the conntrack fallback sees so
the CLOSED LOOP sees one merged list of FlowFeatures.

Two facts dominate its design:

- an AF_PACKET socket only sees traffic of the network namespace it was
  created in, so `KernelTap` binds a device in the CURRENT namespace. The
  testbed probes run it as `ip netns exec router ...`; a harness process
  outside that namespace cannot fix this after the fact, and we do not try.
- the merge is one-directional and explicit: conntrack owns the byte/packet
  CUMULATIVES; the tap owns the DYNAMICS (packet sizes, inter-arrival
  regularity, direction split). Where they disagree on a field only one owns,
  the owner wins. No field is recomputed from both and averaged — a number
  with two sources is a number with no source.
"""

from __future__ import annotations

import json
import select
import socket
import sys
import time
from dataclasses import dataclass, replace

from .features import FlowFeatures
from .observer import DEFAULT_SNAPLEN, HeaderObserver, parse_frame

#: AF_PACKET with ETH_P_ALL: every packet with an 802.3-ish shape, ingress
#: and egress. Filtering to the one device happens at bind time.
_ETH_P_ALL = 0x0003

#: Frames drained per poll() call. A burst of 256 frames decides nothing
#: anyway; polling again immediately just drains more. Keeps one call's work
#: bounded regardless of link speed.
MAX_FRAMES_PER_POLL = 256


class KernelTap:
    """Binds AF_PACKET on a device in the current namespace and drains it."""

    def __init__(self, observer: HeaderObserver, dev: str,
                 snaplen: int = DEFAULT_SNAPLEN,
                 socket_factory=None, selector=None):
        self._observer = observer
        self._dev = dev
        self._selector = selector or select.select
        factory = socket_factory or \
            (lambda: socket.socket(socket.AF_PACKET, socket.SOCK_RAW,
                                   socket.ntohs(_ETH_P_ALL)))
        self._sock = factory()
        # (device, protocol) bind: only that device's frames arrive, even
        # without host-wide promiscuous capture.
        self._sock.bind((dev, _ETH_P_ALL))
        self._sock.setblocking(False)
        self.exhausted = False        # device found, readable, drained dry
        self.closed = False

    def poll(self, timeout: float = 0.0) -> int:
        """Drain up to MAX_FRAMES_PER_POLL readable frames. Returns count."""
        if self.closed:
            return 0
        r, _, _ = self._selector([self._sock], [], [], timeout)
        if not r:
            return 0
        n = 0
        for _ in range(MAX_FRAMES_PER_POLL):
            try:
                data, _ = self._sock.recvfrom(self._observer._snaplen)
            except BlockingIOError:
                self.exhausted = True
                break
            if self._observer.on_packet(data):
                n += 1
        return n

    def close(self) -> None:
        if not self.closed:
            # The destructor path exists for the teardown contract: a tap in
            # its own process has no one else to do this.
            self.closed = True
            self._sock.close()


# --------------------------------------------------------------------------
# merge: one feature list for the closed loop
# --------------------------------------------------------------------------
def merge_features(base: list[FlowFeatures] | None,
                   tap: list[FlowFeatures] | None) -> list[FlowFeatures]:
    """One merged FlowFeatures per observable flow.

    `base` = conntrack-sourced features (the counters, plus whatever the
    conntrack source could derive). `tap` = header-observer features
    (dynamics). Merged rules, in field order:

    - identity: cartesian Merge by BOTH `Flow.identity` keys (protocol plus
      key); anything else is a different flow and is not mixed in.
    - byte totals: base wins when it saw ANY bytes
      (`rx_bytes + tx_bytes > 0`); otherwise the tap's direction-split
      totals apply. A zero-byte base line (acct missing) is NOT treated as
      "no bytes" — the tap's totals fill in, because 0 there would be a
      plausible-looking lie.
    - packets: base wins when > 0, else the tap's. avg_packet_bytes follows
      whoever owns packets (the counters that were computed together stay
      together).
    - dynamics (pkt_size_median/p95, iat_*, pps, down_share): always taken
      from the tap, or left None when the tap did not speak — the base
      conntrack source cannot know them.
    - burstiness/duty_cycle: base's only. The tap never fabricates them; see
      the observer docstring.
    - dscp/correction: base's, untouched (the tap has no such knowledge).

    A tap-only flow (no conntrack layer yet — e.g. a flow conntrack has not
    shown yet, or a tap namespace the counters cannot see) still appears,
    with whatever totals the tap itself measured.
    """
    tips = {f.flow.identity: f for f in (tap or [])}
    if not tips:
        return list(base or [])
    out: list[FlowFeatures] = []
    merged_ids = set()
    for f in (base or []):
        t = tips.get(f.flow.identity)
        base_totals = (f.rx_bytes + f.tx_bytes) > 0
        if t is None:
            out.append(f)
            continue
        merged_ids.add(f.flow.identity)
        rx = f.rx_bytes if base_totals else t.rx_bytes
        tx = f.tx_bytes if base_totals else t.tx_bytes
        packets = f.packets if f.packets > 0 else t.packets
        avg = (f.avg_packet_bytes if f.packets > 0 else t.avg_packet_bytes)
        out.append(replace(
            f, rx_bytes=rx, tx_bytes=tx, packets=packets, avg_packet_bytes=avg,
            pkt_size_median=t.pkt_size_median,
            pkt_size_p95=t.pkt_size_p95,
            iat_regularity=t.iat_regularity,
            iat_median_s=t.iat_median_s,
            pps=t.pps,
            down_share=t.down_share,
        ))
    # tap-only flows, in stable order
    for ident in sorted(set(tips) - merged_ids):
        t = tips[ident]
        out.append(t)
    return out


class TapSource:
    """The closed loop's view: conntrack base + live tap, one refresh()."""

    def __init__(self, tracker=None, observer: HeaderObserver | None = None,
                 tap: KernelTap | None = None):
        """`tracker` is the conntrack layer (must expose .scan()); `tap`
        optional live filter; either may be absent — an all-offline source
        returns `[]` until something is attached."""
        self._tracker = tracker
        self._observer = observer
        self._tap = tap

    def refresh(self) -> list[FlowFeatures]:
        base = []
        if self._tracker is not None:
            base = self._tracker.scan()
        tap_feats = self._observer.features() if self._observer else []
        return merge_features(base, tap_feats)

    def pump(self, timeout: float = 0.0) -> int:
        return self._tap.poll(timeout) if self._tap else 0


# --------------------------------------------------------------------------
# testbed probe entry: `ip netns exec <ns> python -m aciq.tap --dev X`
# --------------------------------------------------------------------------
def main(argv: list[str]) -> int:
    """Stand-alone capture probe. sudo-only in the testbed because of the
    tap; everything it prints is counts and header-side numbers."""
    args = dict(a[1].split("=", 1) for a in argv if len(a) > 1)
    dev = args.get("dev")
    dur = float(args.get("seconds", "5"))
    out = args.get("json-out")
    n_win = int(args.get("window", "64"))
    if not dev:
        print("usage: aciq.tap --dev=NAME [seconds=N] [window=N] [json-out=PATH]",
              file=sys.stderr)
        return 2
    obs = HeaderObserver(window=n_win, idle_s=float(dur) + 1.0)
    tap = KernelTap(obs, dev)
    end = time.monotonic() + dur
    frames = 0
    while time.monotonic() < end:
        frames += tap.poll(timeout=0.05)
    tap.close()
    feats = obs.features()
    print(json.dumps({
        "dev": dev, "seconds": dur, "frames": frames,
        "flows": len(obs), "skipped": obs.skipped,
        "flows_with_dynamics": sum(1 for f in feats
                                   if f.pkt_size_median is not None),
    }))
    if out:
        with open(out, "w") as fh:
            fh.write(json.dumps({
                "flows": [
                    {"identity": f.flow.identity,
                     "pps": f.pps, "median": f.pkt_size_median,
                     "p95": f.pkt_size_p95,
                     "regularity": f.iat_regularity,
                     "down_share": f.down_share, "packets": f.packets}
                    for f in feats
                ]}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
