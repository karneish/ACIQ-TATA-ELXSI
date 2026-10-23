"""ACIQ — Adaptive Classification & Intent-aware QoS.

Shared data types. Deliberately dependency-free so that every module that
imports this one stays unit-testable without root.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TrafficClass(str, Enum):
    """The three traffic classes. Mapped onto HTB classes in the testbed."""

    INTERACTIVE = "realtime_interactive"
    ADAPTIVE = "adaptive_video"
    BULK = "bulk_transfer"
    #: created on demand, one per active lease
    LEASED = "leased_flow"


#: Base weights from the plan. A lease borrows a bounded slice of these.
BASE_WEIGHTS: dict[TrafficClass, float] = {
    TrafficClass.INTERACTIVE: 8.0,
    TrafficClass.ADAPTIVE: 4.0,
    TrafficClass.BULK: 2.0,
}


@dataclass(frozen=True)
class Flow:
    """One tracked flow, identified by its conntrack 5-tuple."""

    src: str
    sport: int
    dst: str
    dport: int
    proto: str = "udp"

    @property
    def key(self) -> str:
        return f"{self.src}:{self.sport}->{self.dst}:{self.dport}"

    @property
    def identity(self) -> str:
        """`key` plus the protocol.

        `key` is deliberately protocol-free because it is the *user-facing*
        spelling: leases name flows as `host:port->host:port` and the match at
        intent.py compares that string. But as a *tracker* key it is wrong —
        DNS over tcp and udp to the same server is one `key` and two flows, so
        their counters merged and neither was classified on its own numbers.
        The tracker keys on identity; the lease API keeps its stable spelling.
        """
        return f"{self.proto} {self.key}"


@dataclass(frozen=True)
class Classification:
    """M1 output. `confidence` below 0.5 means UNCLASSIFIED, never guessed."""

    flow: Flow
    cls: TrafficClass | None
    confidence: float
    tier: str
    evidence: str


@dataclass(frozen=True)
class Capacity:
    """M2 output. Never derived from class 1:1's configured rate."""

    mbps: float
    confidence: float
    saturated: bool
    changed: bool


@dataclass(frozen=True)
class Lease:
    """M7 input: a time-boxed, weighted, bounded request.

    A lease is NOT a priority boost. It borrows a bounded share and expires on
    its own, so a forgotten request can never permanently harm the household.
    """

    id: str
    target: str  # "device" | "flow"
    ip: str | None = None
    flow: str | None = None
    weight: float = 0.4
    ttl_s: float = 90.0
    created_at: float = 0.0

    def expired(self, now: float) -> bool:
        return now >= self.created_at + self.ttl_s


@dataclass
class RatePlan:
    """M3 output. An immutable description of intent, not tc commands.

    Two invariants, both enforced by `policy.build_plan` and both confirmed by
    real HTB measurements on the testbed:

    1. sum(rate_mbps) <= capacity_mbps
    2. every ceil_mbps <= capacity_mbps

    (2) matters more than it looks. HTB lets a class borrow *past its parent's
    rate*, up to its own ceil, against the device's real capacity. Measured on
    the testbed: a parent dropped 100 -> 20 Mbit with children left at ceil
    99/97 delivered 28.5 Mbps, not 20. So a ceiling above the bottleneck is not
    a harmless headroom setting — it is a way for traffic to exceed the link.
    """

    capacity_mbps: float
    rates: dict[TrafficClass, float] = field(default_factory=dict)
    ceils: dict[TrafficClass, float] = field(default_factory=dict)
    lease_id: str | None = None
    #: True when floors could not all be honoured because capacity is tiny.
    #: Reported honestly rather than silently violated.
    degraded: bool = False

    def total(self) -> float:
        return sum(self.rates.values())

    def max_ceil(self) -> float:
        return max(self.ceils.values(), default=0.0)


@dataclass(frozen=True)
class Sample:
    """M5 output: one observation of one class at one instant."""

    t: float
    cls: TrafficClass
    rx_bytes: int
    tx_bytes: int
    drops: int
    overlimits: int
    backlog_bytes: int
    rtt_ms: float | None = None
    jitter_ms: float | None = None
