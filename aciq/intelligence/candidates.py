"""Module 5 — Experience-Based Policy Candidate Generator (Phase 4).

Produces a **bounded** set of alternative `RatePlan`s by varying only
`build_plan` weights — never arbitrary configs the controller can't enforce.
Candidates are proposals for the gate; generation never applies anything.
"""
from __future__ import annotations

import copy

from ..model import Lease, RatePlan, TrafficClass
from ..policy import BASE_WEIGHTS, build_plan
from .config import IntelligenceConfig
from .contracts import Candidate, NetworkState, Prediction


class CandidateGenerator:
    def __init__(self, config: IntelligenceConfig | None = None):
        self.config = config or IntelligenceConfig()

    def generate(self, state: NetworkState, current_plan: RatePlan,
                 parent_policy_id: str,
                 capability: float = 1.0,
                 correlation_id: str = "") -> list[Candidate]:
        """≤ max_candidates candidates, always including RETAIN-equivalent.

        `capability` scales capacity (0..1) — e.g. a measured drop shrinks
        every variant proportionally so a candidate never pretends the link
        is bigger than measured.
        """
        cap = max(1.0, state.capacity.mbps * max(0.05, min(1.0, capability)))
        out: list[Candidate] = []

        def _add(label: str, lease: Lease | None, scale: dict[TrafficClass, float],
                 reason: str, refs: tuple[str, ...] = ()) -> None:
            if len(out) >= self.config.max_candidates:
                return
            base = build_plan(cap, lease)
            rates = {c: r * scale.get(c, 1.0) for c, r in base.rates.items()}
            # rescale after weight tweak so sum() <= capacity still holds
            total = sum(rates.values())
            if total > cap and total > 0:
                k = cap / total
                rates = {c: r * k for c, r in rates.items()}
            ceils = {c: min(cap, max(rates[c], base.ceils.get(c, cap)))
                     for c in rates}
            plan = RatePlan(capacity_mbps=cap, rates=rates, ceils=ceils,
                            lease_id=base.lease_id, degraded=base.degraded)
            cand = Candidate(
                plan=plan, parent_policy_id=parent_policy_id,
                reason=reason, experience_refs=refs,
                expected_benefits=(f"matches measured capacity {cap:.1f} Mbps",),
                trade_offs=(f"re-plans around {label}",),
                risks=("candidate, not yet validated",),
                constraints_to_validate=("capacity", "fairness", "stability",
                                         "enforcement", "ipv4_ipv6"),
                required_capabilities=("tc_htb", "fq_codel"),
                correlation_id=correlation_id, recorded_at=state.recorded_at)
            if cand.is_valid():
                out.append(cand)

        if len(out) < self.config.max_candidates:
            # 0: retain-equivalent (same plan shape, same capacity estimate)
            _add("retain", None, {}, "retain current policy shape", ())

        # 1: interactive boost (weights toward call/gaming)
        scale = {TrafficClass.VIDEO_CALL: 1.5, TrafficClass.GAMING: 1.4,
                 TrafficClass.BULK_DOWNLOAD: 0.6}
        _add("interactive-boost", None, scale,
             "protect interactive traffic under congestion")

        # 2: bulk-fair (spread freed share to bulk)
        scale = {TrafficClass.BULK_DOWNLOAD: 1.6,
                 TrafficClass.VIDEO_CALL: 0.85, TrafficClass.GAMING: 0.85}
        _add("bulk-fair", None, scale,
             "let bulk progress when interactive demand is low")

        # 3: streaming-heavy
        scale = {TrafficClass.STREAMING: 1.8, TrafficClass.BULK_DOWNLOAD: 0.7}
        _add("streaming-heavy", None, scale,
             "streaming needs sustained throughput")

        # 4: conservative (floors only — smallest change that still validates)
        scale = {c: 0.4 for c in BASE_WEIGHTS}
        _add("conservative", None, scale,
             "smallest safe move when evidence is thin")

        # dedupe near-identical candidates
        seen: set[tuple] = set()
        uniq: list[Candidate] = []
        for c in out:
            key = tuple(sorted((k.value, round(v, 3)) for k, v in c.plan.rates.items()))
            if key not in seen:
                seen.add(key)
                uniq.append(c)
        return uniq[: self.config.max_candidates]
