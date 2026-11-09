"""Module 1 — Network State Observer (Phase 4).

Wraps existing ACIQ snapshots into a `NetworkState`. Read-only: never touches
the network, never fabricates a missing measurement (missing names are listed
in `missing`), never mistakes absence for health.
"""
from __future__ import annotations

import time
from typing import Any

from ..model import Capacity, TrafficClass
from .contracts import NetworkState, Reliability


class NetworkStateObserver:
    """Builds `NetworkState` from existing collector/estimator outputs.

    Inputs are the per-tick sample the harness already produces plus the
    estimator's current `Capacity`. Freshness is computed from each source's
    own timestamp against `config.freshness_limit_s`.
    """

    def __init__(self, capacity: Capacity, now_s: float | None = None,
                 freshness_limit_s: float = 5.0):
        self._capacity = capacity
        self._now = now_s if now_s is not None else time.time()
        self._limit = freshness_limit_s

    def observe(self, sample: dict[str, Any],
                per_class_demand: dict[TrafficClass, float] | None = None,
                current_policy_id: str | None = None,
                enforcement_state: str = "unknown") -> NetworkState:
        missing: list[str] = []
        freshness: dict[str, float] = {}

        def _fresh(name: str, ts: float | None) -> bool:
            if ts is None:
                missing.append(name)
                return False
            age = max(0.0, self._now - float(ts))
            freshness[name] = age
            return age <= self._limit

        # capacity freshness: harness samples carry their own tick time `t`;
        # Capacity itself has no timestamp by design (it is not an oracle).
        sample_t = sample.get("t")
        cap_ok = _fresh("capacity", float(sample_t) if sample_t is not None else None)
        per_class = sample.get("per_class") or {}

        latency = sample.get("latency_ms")
        if latency is None:
            # per-class p95 max is the best available latency proxy
            lat = [v.get("rtt_p95") for v in per_class.values()
                   if isinstance(v, dict) and v.get("rtt_p95") is not None]
            latency = max(lat) if lat else None
            if latency is None:
                missing.append("latency_ms")
        jitter = sample.get("jitter_ms") or sample.get("jitter")
        if jitter is None:
            missing.append("jitter_ms")
        loss = sample.get("loss_ratio")
        if loss is None:
            missing.append("loss_ratio")
        throughput = sample.get("throughput_mbps", sample.get("goodput_mbps"))
        if throughput is None:
            missing.append("throughput_mbps")
        backlog = sample.get("bottleneck_backlog_bytes", sample.get("backlog_bytes"))
        if backlog is None:
            missing.append("queue_backlog_bytes")

        confs = [v.get("confidence") for v in (sample.get("verdicts") or {}).values()
                 if isinstance(v, dict) and v.get("confidence") is not None]
        class_conf = (sum(confs) / len(confs)) if confs else None
        if class_conf is None:
            missing.append("classification_confidence")

        active = self._count_active_flows(per_class_demand or {})
        if active == 0:
            missing.append("active_flows")

        # reliability triage: missing classification confidence degrades
        # (conservative) but must not masquerade as "no evidence at all" —
        # capacity is the decision-critical signal, and it is fresh here.
        cap_conf = float(getattr(self._capacity, "confidence", 0.0) or 0.0)
        if not cap_ok or cap_conf <= 0.0:
            reliability = Reliability.UNKNOWN
        elif len(missing) <= 2 and freshness.get("capacity", 99) <= self._limit:
            reliability = Reliability.RELIABLE
        else:
            reliability = Reliability.DEGRADED

        congestion = bool(sample.get("estimator_saturated")) or (
            backlog is not None and float(backlog) > 0)

        return NetworkState(
            capacity=_capacity_of(self._capacity),
            per_class_demand=dict(per_class_demand or {}),
            active_flows=active,
            latency_ms=latency, jitter_ms=jitter, loss_ratio=loss,
            throughput_mbps=throughput, queue_backlog_bytes=backlog,
            congestion=congestion,
            classification_confidence=class_conf,
            enforcement_state=enforcement_state,
            current_policy_id=current_policy_id,
            freshness=freshness,
            missing=tuple(sorted(set(missing))),
            reliability=reliability,
            recorded_at=self._now,
        )

    @staticmethod
    def _count_active_flows(demand: dict[TrafficClass, float]) -> int:
        return sum(1 for v in demand.values() if v and float(v) > 0)


def _capacity_of(cap) -> Capacity:
    # The estimator (aciq.capacity) and model (aciq.model) define *different*
    # Capacity classes; accept anything with the four fields duck-typed.
    if hasattr(cap, "mbps") and hasattr(cap, "confidence"):
        return Capacity(mbps=float(cap.mbps or 0.0),
                        confidence=float(cap.confidence or 0.0),
                        saturated=bool(getattr(cap, "saturated", False)),
                        changed=bool(getattr(cap, "changed", False)))
    return Capacity(mbps=float(cap.get("mbps", 0.0) or 0.0),
                    confidence=float(cap.get("confidence", 0.0) or 0.0),
                    saturated=bool(cap.get("saturated", False)),
                    changed=bool(cap.get("changed", False)))
