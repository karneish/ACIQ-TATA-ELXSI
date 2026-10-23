"""Per-flow traffic features shared by every observation source.

One data structure feeds both the classifier (aciq.classify) and any optional
learned model (aciq.learned), no matter which observation source produced it:
the header-level observer (aciq.observer) or the conntrack fallback
(aciq.flowtrack).

Fields a source cannot provide stay ``None`` — the rules in ``classify.py``
only use a hint when they can SEE it, never a defaulted guess. ``flowtrack``
(conntrack counters only) fills the basic byte/packet fields; the header
observer fills everything, including packet-size and inter-arrival statistics,
without ever touching a payload byte.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Flow, TrafficClass


def mean_cv(values) -> tuple[float | None, float | None]:
    """(mean, coefficient of variation) of a bounded series, or (None, None)."""
    n = len(values)
    if n == 0:
        return None, None
    m = sum(values) / n
    if m <= 0 or n < 2:
        return m, None
    var = sum((v - m) ** 2 for v in values) / (n - 1)
    return m, (var ** 0.5) / m


@dataclass(frozen=True)
class FlowFeatures:
    """What was observed about one flow. All fields are behaviour, not identity."""

    flow: Flow
    dscp: float | int | None = None
    rx_bytes: int = 0     # reply direction (downloads, for a home-originated flow)
    tx_bytes: int = 0     # request direction (from the flow's originator)
    packets: int = 0
    age_s: float = 0.0
    avg_packet_bytes: float = 0.0
    #: coefficient of variation of per-poll byte increments. Recorded, not used
    #: as a discriminator by the rule base — see the classify.py docstring.
    burstiness: float | None = None
    #: fraction of polls in which bytes moved. Measured 1.00 for every
    #: generator, so it is recorded but not used to separate classes.
    duty_cycle: float | None = None
    #: user's override for this flow, if any. Takes precedence over everything.
    correction: TrafficClass | None = None
    # ---- extended, header-observer-only fields -------------------------------
    #: 1 - CV of inter-arrival times; high (>= 0.7) means clock-regular emission
    iat_regularity: float | None = None
    iat_median_s: float | None = None
    #: median / p95 packet size on the wire (headers included, payload never read)
    pkt_size_median: float | None = None
    pkt_size_p95: float | None = None
    #: packets per second
    pps: float | None = None
    #: share of all bytes carried in the reply (downward) direction: 1.0 is a
    #: pure download, 0.0 a pure upload. None when the direction was unknown to
    #: the source.
    down_share: float | None = None

    @property
    def total_bytes(self) -> int:
        return self.rx_bytes + self.tx_bytes

    @property
    def rate_bps(self) -> float:
        return (self.total_bytes * 8) / self.age_s if self.age_s > 0 else 0.0

    @property
    def rate_mbps(self) -> float:
        return self.rate_bps / 1e6

    @property
    def asymmetry(self) -> float:
        """max(rx,tx) / min(rx,tx). 1.0 is perfectly bidirectional.

        The separator between a transfer and a conversation. Deliberately *not*
        duty cycle: measured 1.00 for every generator, because each emits
        continuously at a target rate, so it carries no information at all.
        """
        lo = min(self.rx_bytes, self.tx_bytes)
        if lo <= 0:
            return float("inf")      # strictly one-directional
        return max(self.rx_bytes, self.tx_bytes) / lo

    def looks_interactive(self, max_mbps: float = 20.0,
                          max_asymmetry: float = 50.0) -> bool:
        """Could this plausibly be a real-time conversation?

        Rate and direction together. Used to test an *EF claim* only. The
        defaults echo the interactive-plausibility envelope owned by
        aciq.classify; they are duplicated here rather than imported to keep
        this module free of rule knowledge.
        """
        return (self.rate_mbps <= max_mbps
                and self.asymmetry <= max_asymmetry)
