"""M1 — flow classification.

Pure decision logic: (flow features) -> (class, confidence, evidence).

**Deliberate constraint: the classifier never keys on the test generators' own
ports.** Our workloads listen on 5001-5004; classifying those would give 100%
accuracy on every run and mean nothing. Instead Stage A uses only signals a
real deployment could rely on:

  * DSCP EF (46) — real VoIP/video endpoints mark their media EF
  * a small table of well-known signalling ports (STUN/TURN, SIP)

Everything else is decided in Stage B from traffic behaviour, which is what makes
the accuracy number worth reporting.

The UDP/443 case is handled honestly rather than guessed. A video call and a
large download both run over UDP/443. When nothing distinguishes them, the flow
is reported UNCLASSIFIED with a reason, because a confident wrong label is worse
than an honest gap.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Classification, Flow, TrafficClass

#: DSCP EF. Real endpoints mark interactive media with this.
DSCP_EF = 46

#: Well-known signalling ports. Deliberately tiny: this is not the main signal.
INTERACTIVE_PORTS = frozenset({3478, 5060, 5061, 5349})
BULK_PORTS = frozenset({873, 3389})  # rsync, RDP-ish bulk

#: Confidence below this means UNCLASSIFIED. Never guessed.
MIN_CONFIDENCE = 0.5

#: Evidence thresholds for the statistics-based tier.
BULK_MIN_AVG_PACKET = 1200
BULK_MIN_DUTY_CYCLE = 0.8
BULK_MIN_AGE_S = 3.0
INTERACTIVE_MAX_AVG_PACKET = 600


@dataclass(frozen=True)
class FlowFeatures:
    """What Stage B observed about one flow. All fields are behaviour, not identity."""

    flow: Flow
    dscp: int | None = None
    rx_bytes: int = 0
    tx_bytes: int = 0
    packets: int = 0
    age_s: float = 0.0
    avg_packet_bytes: float = 0.0
    #: coefficient of variation of per-sample byte increments. High = bursty.
    burstiness: float = 0.0
    #: fraction of samples in which bytes moved. ~1.0 = continuous stream.
    duty_cycle: float = 0.0

    @property
    def total_bytes(self) -> int:
        return self.rx_bytes + self.tx_bytes

    @property
    def rate_bps(self) -> float:
        return (self.total_bytes * 8) / self.age_s if self.age_s > 0 else 0.0


def classify(f: FlowFeatures) -> Classification:
    """Decide a class and a confidence. Pure function, no I/O, no kernel."""
    # ---- Tier A: DSCP. Highest confidence, and realistic. ------------------
    if f.dscp == DSCP_EF:
        return Classification(
            flow=f.flow, cls=TrafficClass.INTERACTIVE, confidence=0.95,
            tier="A", evidence=f"dscp=ef({DSCP_EF})",
        )

    # ---- Tier A: known signalling ports ------------------------------------
    if f.flow.dport in INTERACTIVE_PORTS:
        return Classification(
            flow=f.flow, cls=TrafficClass.INTERACTIVE, confidence=0.85,
            tier="A", evidence=f"well-known interactive port {f.flow.dport}",
        )
    if f.flow.dport in BULK_PORTS:
        return Classification(
            flow=f.flow, cls=TrafficClass.BULK, confidence=0.70,
            tier="A", evidence=f"known bulk port {f.flow.dport}",
        )

    # ---- Tier B: behaviour -------------------------------------------------
    if _looks_bulk(f):
        return Classification(
            flow=f.flow, cls=TrafficClass.BULK, confidence=0.65,
            tier="B",
            evidence=(
                f"avg_pkt={f.avg_packet_bytes:.0f}B duty={f.duty_cycle:.2f} "
                f"age={f.age_s:.1f}s burst={f.burstiness:.2f}"
            ),
        )

    if _looks_interactive_udp(f):
        return Classification(
            flow=f.flow, cls=TrafficClass.INTERACTIVE, confidence=0.55,
            tier="B",
            evidence=(
                f"small avg_pkt={f.avg_packet_bytes:.0f}B "
                f"duty={f.duty_cycle:.2f} burst={f.burstiness:.2f}"
            ),
        )

    # ---- Tier C: honest gap ----------------------------------------------
    # UDP/443 with nothing to separate a call from a download. Report it.
    if f.flow.proto == "udp" and f.flow.dport == 443:
        return Classification(
            flow=f.flow, cls=None, confidence=0.40, tier="C",
            evidence=(
                "udp/443 ambiguous: no dscp mark and statistics do not separate "
                "a call from a download"
            ),
        )

    return Classification(
        flow=f.flow, cls=None, confidence=0.30, tier="C",
        evidence="insufficient evidence",
    )


def _looks_bulk(f: FlowFeatures) -> bool:
    return (
        f.avg_packet_bytes >= BULK_MIN_AVG_PACKET
        and f.duty_cycle >= BULK_MIN_DUTY_CYCLE
        and f.age_s >= BULK_MIN_AGE_S
    )


def _looks_interactive_udp(f: FlowFeatures) -> bool:
    return (
        f.flow.proto == "udp"
        and f.avg_packet_bytes > 0
        and f.avg_packet_bytes <= INTERACTIVE_MAX_AVG_PACKET
        and f.packets >= 10
    )


def finalise(c: Classification) -> Classification:
    """Demote anything below MIN_CONFIDENCE to UNCLASSIFIED.

    Separate from classify() so a raw score can be inspected for analysis
    without a mislabelled flow ever reaching enforcement.
    """
    if c.cls is not None and c.confidence >= MIN_CONFIDENCE:
        return c
    return Classification(
        flow=c.flow, cls=None, confidence=c.confidence, tier=c.tier,
        evidence=f"{c.evidence} -> below {MIN_CONFIDENCE}, unclassified",
    )
