"""Data contracts for the ACIQ intelligence layer (Phase 2).

Every cross-module value is one of the frozen dataclasses below. Rules that
apply to all records (see `docs/intelligence/phase2-contracts.md`):

* ``schema`` is always ``SCHEMA_VERSION`` (1). Bump on any breaking change;
  readers must reject unknown schemas, never coerce.
* ``record_id`` is a non-empty string (UUID hex from the producer).
* ``recorded_at`` is finite epoch seconds (> 0). Tick time is never recorded
  here — only wall-clock evidence time.
* ``correlation_id`` ties every record of one decision lifecycle together.
  Records without a shared ``correlation_id`` must never be compared.
* Confidence values are floats in [0, 1]. ``None`` means *unknown*, never 0.
* Enums serialise by value (``str`` enums) so JSONL stays human-readable.
* ``to_dict`` / ``from_dict`` are the *only* serialisation path. A record
  that fails validation is rejected, never repaired silently.
* Existing ACIQ types are reused, never duplicated: ``Capacity``,
  ``RatePlan``, ``TrafficClass``, ``Classification``, ``Lease`` from
  ``aciq.model``. Candidates carry a ``RatePlan`` — the exact object
  ``policy.build_plan`` produced — so an unsupported parameter cannot exist.

No enforcement happens here. Nothing in this module imports the kernel,
naketypes, or the controller.
"""
from __future__ import annotations

import json
import math
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, ClassVar

from ..model import Capacity, Lease, RatePlan, TrafficClass

SCHEMA_VERSION: int = 1


# --------------------------------------------------------------------------
# enums
# --------------------------------------------------------------------------

class Reliability(str, Enum):
    RELIABLE = "reliable"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


class PolicyHealth(str, Enum):
    HEALTHY = "healthy"
    MONITOR = "monitor"
    DEGRADING = "degrading"
    CONFIRMED_DEGRADATION = "confirmed_degradation"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class PredictionStatus(str, Enum):
    NONE = "none"
    POTENTIAL = "potential"
    HIGH = "high"
    UNCERTAIN = "uncertain"


class ExperienceStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    SIMULATION_ONLY = "simulation_only"
    REJECTED = "rejected"
    RECOVERY = "recovery"
    PREDICTION_ONLY = "prediction_only"
    INCOMPLETE = "incomplete"


class DecisionAction(str, Enum):
    RETAIN = "retain"
    SELECT = "select"
    REJECT_ALL = "reject_all"
    DEFER = "defer"
    RECOVER = "recover"
    SAFE_FALLBACK = "safe_fallback"


class OutcomeClass(str, Enum):
    SUCCESSFUL = "successful"
    DEGRADED = "degraded"
    INCONCLUSIVE = "inconclusive"
    APPLICATION_FAILED = "application_failed"
    RECOVERED = "recovered"


class ValidationStatus(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    DEFER = "defer"
    RETAIN = "retain"


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------

def _new_id() -> str:
    return uuid.uuid4().hex


def _valid_conf(v: float | None) -> bool:
    return v is None or (isinstance(v, float) and math.isfinite(v) and 0.0 <= v <= 1.0)


def _valid_ts(v: float) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(float(v)) and float(v) > 0.0


def _enum_val(v: Any) -> Any:
    return v.value if isinstance(v, Enum) else v


def _plan_to_dict(plan: RatePlan | None) -> dict[str, Any] | None:
    if plan is None:
        return None
    return {
        "capacity_mbps": plan.capacity_mbps,
        "rates": {c.value: r for c, r in plan.rates.items()},
        "ceils": {c.value: r for c, r in plan.ceils.items()},
        "lease_id": plan.lease_id,
        "degraded": plan.degraded,
    }


def _plan_from_dict(d: dict[str, Any] | None) -> RatePlan | None:
    if d is None:
        return None
    return RatePlan(
        capacity_mbps=float(d["capacity_mbps"]),
        rates={TrafficClass(k): float(v) for k, v in d.get("rates", {}).items()},
        ceils={TrafficClass(k): float(v) for k, v in d.get("ceils", {}).items()},
        lease_id=d.get("lease_id"),
        degraded=bool(d.get("degraded", False)),
    )


class Record:
    """Base validation + serialisation shared by every contract."""

    schema: ClassVar[int] = SCHEMA_VERSION

    def errors(self) -> list[str]:  # pragma: no cover - overridden
        return []

    def is_valid(self) -> bool:
        return not self.errors()

    def validate(self) -> None:
        errs = self.errors()
        if errs:
            raise ValueError(f"{type(self).__name__} invalid: {errs}")

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        for k, v in list(d.items()):
            d[k] = _enum_val(v)
        # RatePlan fields (candidate.plan, evaluation.current_plan, …)
        for k, v in list(d.items()):
            if isinstance(v, dict) and "rates" in v and "ceils" in v and "capacity_mbps" in v:
                d[k] = v
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Record":
        raise NotImplementedError


def _base_errors(rec: Record) -> list[str]:
    errs: list[str] = []
    if getattr(rec, "schema", None) != SCHEMA_VERSION:
        errs.append(f"schema must be {SCHEMA_VERSION}")
    if not getattr(rec, "record_id", ""):
        errs.append("record_id is required")
    if not _valid_ts(getattr(rec, "recorded_at", 0.0)):
        errs.append("recorded_at must be finite epoch seconds > 0")
    return errs


# --------------------------------------------------------------------------
# 1. network state
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class NetworkState(Record):
    """Module 1 output. A snapshot of what is *known right now*."""

    capacity: Capacity
    per_class_demand: dict[TrafficClass, float] = field(default_factory=dict)
    active_flows: int = 0
    latency_ms: float | None = None
    jitter_ms: float | None = None
    loss_ratio: float | None = None
    throughput_mbps: float | None = None
    queue_backlog_bytes: int | None = None
    congestion: bool = False
    classification_confidence: float | None = None
    enforcement_state: str = "unknown"
    current_policy_id: str | None = None
    freshness: dict[str, float] = field(default_factory=dict)  # name -> age_s
    missing: tuple[str, ...] = ()
    reliability: Reliability = Reliability.UNKNOWN
    record_id: str = field(default_factory=_new_id)
    recorded_at: float = 0.0
    schema: int = SCHEMA_VERSION

    def errors(self) -> list[str]:
        errs = _base_errors(self)
        if self.capacity is None:
            errs.append("capacity is required")
        for name, age in self.freshness.items():
            if not isinstance(age, (int, float)) or not math.isfinite(float(age)) or age < 0:
                errs.append(f"freshness[{name}] must be a finite age >= 0")
        for f in ("latency_ms", "jitter_ms", "loss_ratio", "throughput_mbps"):
            v = getattr(self, f)
            if v is not None and (not isinstance(v, (int, float)) or not math.isfinite(float(v)) or v < 0):
                errs.append(f"{f} must be finite and >= 0")
        if self.loss_ratio is not None and float(self.loss_ratio) > 1.0:
            errs.append("loss_ratio must be <= 1.0")
        if not _valid_conf(self.classification_confidence):
            errs.append("classification_confidence must be in [0,1] or None")
        if self.active_flows < 0:
            errs.append("active_flows must be >= 0")
        return errs

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "NetworkState":
        cap = d["capacity"]
        return cls(
            capacity=Capacity(mbps=float(cap["mbps"]), confidence=float(cap.get("confidence", 0.0)),
                              saturated=bool(cap.get("saturated", False)), changed=bool(cap.get("changed", False))),
            per_class_demand={TrafficClass(k): float(v) for k, v in d.get("per_class_demand", {}).items()},
            active_flows=int(d.get("active_flows", 0)),
            latency_ms=d.get("latency_ms"), jitter_ms=d.get("jitter_ms"),
            loss_ratio=d.get("loss_ratio"), throughput_mbps=d.get("throughput_mbps"),
            queue_backlog_bytes=d.get("queue_backlog_bytes"), congestion=bool(d.get("congestion", False)),
            classification_confidence=d.get("classification_confidence"),
            enforcement_state=d.get("enforcement_state", "unknown"),
            current_policy_id=d.get("current_policy_id"),
            freshness={k: float(v) for k, v in d.get("freshness", {}).items()},
            missing=tuple(d.get("missing", ())),
            reliability=Reliability(d.get("reliability", "unknown")),
            record_id=d["record_id"], recorded_at=float(d["recorded_at"]), schema=int(d.get("schema", SCHEMA_VERSION)),
        )


# --------------------------------------------------------------------------
# 2. current policy evaluation
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class PolicyEvaluation(Record):
    """Module 2 output. Is the active plan still the right plan?"""

    current_policy_id: str
    health: PolicyHealth
    evidence: dict[str, float] = field(default_factory=dict)
    missing: tuple[str, ...] = ()
    explanation: str = ""
    correlation_id: str = ""
    record_id: str = field(default_factory=_new_id)
    recorded_at: float = 0.0
    schema: int = SCHEMA_VERSION

    def errors(self) -> list[str]:
        errs = _base_errors(self)
        if not self.current_policy_id:
            errs.append("current_policy_id is required")
        if not self.correlation_id:
            errs.append("correlation_id is required")
        return errs

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PolicyEvaluation":
        return cls(current_policy_id=d["current_policy_id"], health=PolicyHealth(d["health"]),
                   evidence={k: float(v) for k, v in d.get("evidence", {}).items()},
                   missing=tuple(d.get("missing", ())), explanation=d.get("explanation", ""),
                   correlation_id=d.get("correlation_id", ""), record_id=d["record_id"],
                   recorded_at=float(d["recorded_at"]), schema=int(d.get("schema", SCHEMA_VERSION)))


# --------------------------------------------------------------------------
# 3. prediction
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Prediction(Record):
    """Module 3 output. A forecast — never a fact, never stored as success."""

    horizon_s: float
    status: PredictionStatus
    confidence: float | None
    severity: float = 0.0
    evidence: tuple[str, ...] = ()
    missing_inputs: tuple[str, ...] = ()
    predicted_metrics: dict[str, float] = field(default_factory=dict)
    correlation_id: str = ""
    record_id: str = field(default_factory=_new_id)
    recorded_at: float = 0.0
    schema: int = SCHEMA_VERSION

    def errors(self) -> list[str]:
        errs = _base_errors(self)
        if not (isinstance(self.horizon_s, (int, float)) and math.isfinite(float(self.horizon_s)) and self.horizon_s > 0):
            errs.append("horizon_s must be finite and > 0")
        if not _valid_conf(self.confidence):
            errs.append("confidence must be in [0,1] or None")
        if not math.isfinite(float(self.severity)) or self.severity < 0:
            errs.append("severity must be finite and >= 0")
        if self.status == PredictionStatus.HIGH and self.confidence is None:
            errs.append("HIGH predictions require a confidence value")
        return errs

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Prediction":
        return cls(horizon_s=float(d["horizon_s"]), status=PredictionStatus(d["status"]),
                   confidence=d.get("confidence"), severity=float(d.get("severity", 0.0)),
                   evidence=tuple(d.get("evidence", ())), missing_inputs=tuple(d.get("missing_inputs", ())),
                   predicted_metrics={k: float(v) for k, v in d.get("predicted_metrics", {}).items()},
                   correlation_id=d.get("correlation_id", ""), record_id=d["record_id"],
                   recorded_at=float(d["recorded_at"]), schema=int(d.get("schema", SCHEMA_VERSION)))


# --------------------------------------------------------------------------
# 4. experience (repository record)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Experience(Record):
    """Module 4 record. One row per `data/experiences.jsonl` line."""

    status: ExperienceStatus
    network_context: dict[str, Any] = field(default_factory=dict)
    policy_context: dict[str, Any] = field(default_factory=dict)
    decision_context: dict[str, Any] = field(default_factory=dict)
    outcome_context: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = ""
    record_id: str = field(default_factory=_new_id)
    recorded_at: float = 0.0
    schema: int = SCHEMA_VERSION

    def errors(self) -> list[str]:
        errs = _base_errors(self)
        # Status separation is a hard rule: MEASURED statuses must carry measured
        # evidence; SIMULATION_ONLY must never look like measured success.
        if self.status in (ExperienceStatus.SUCCESS, ExperienceStatus.FAILED,
                           ExperienceStatus.RECOVERY):
            if self.outcome_context.get("measured") is None:
                errs.append(f"{self.status.value} requires outcome_context['measured']")
        if self.status == ExperienceStatus.SIMULATION_ONLY:
            if self.outcome_context.get("measured") is not None:
                errs.append("simulation_only must not carry measured outcomes")
        if self.status == ExperienceStatus.INCOMPLETE:
            # Incomplete records are quarantined, never promoted.
            if self.outcome_context.get("measured") is not None:
                errs.append("incomplete records must not carry measured outcomes")
        return errs

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Experience":
        return cls(status=ExperienceStatus(d["status"]),
                   network_context=dict(d.get("network_context", {})),
                   policy_context=dict(d.get("policy_context", {})),
                   decision_context=dict(d.get("decision_context", {})),
                   outcome_context=dict(d.get("outcome_context", {})),
                   correlation_id=d.get("correlation_id", ""), record_id=d["record_id"],
                   recorded_at=float(d["recorded_at"]), schema=int(d.get("schema", SCHEMA_VERSION)))


# --------------------------------------------------------------------------
# 5. candidate policy
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Candidate(Record):
    """Module 5 proposal. Carries the exact RatePlan build_plan produced."""

    plan: RatePlan
    parent_policy_id: str
    reason: str
    experience_refs: tuple[str, ...] = ()
    expected_benefits: tuple[str, ...] = ()
    trade_offs: tuple[str, ...] = ()
    risks: tuple[str, ...] = ()
    constraints_to_validate: tuple[str, ...] = ()
    required_capabilities: tuple[str, ...] = ()
    correlation_id: str = ""
    record_id: str = field(default_factory=_new_id)
    recorded_at: float = 0.0
    schema: int = SCHEMA_VERSION

    def errors(self) -> list[str]:
        errs = _base_errors(self)
        if self.plan is None:
            errs.append("plan is required")
        else:
            if self.plan.capacity_mbps <= 0:
                errs.append("plan.capacity_mbps must be > 0")
            if self.plan.total() > self.plan.capacity_mbps + 1e-9:
                errs.append("sum(rates) must be <= capacity_mbps")
            for c, ceil in self.plan.ceils.items():
                if ceil > self.plan.capacity_mbps + 1e-9:
                    errs.append(f"ceil[{c.value}] must be <= capacity_mbps")
        if not self.parent_policy_id:
            errs.append("parent_policy_id is required")
        if not self.reason:
            errs.append("reason is required")
        return errs

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["plan"] = _plan_to_dict(self.plan)
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Candidate":
        return cls(plan=_plan_from_dict(d["plan"]), parent_policy_id=d["parent_policy_id"],
                   reason=d.get("reason", ""), experience_refs=tuple(d.get("experience_refs", ())),
                   expected_benefits=tuple(d.get("expected_benefits", ())),
                   trade_offs=tuple(d.get("trade_offs", ())), risks=tuple(d.get("risks", ())),
                   constraints_to_validate=tuple(d.get("constraints_to_validate", ())),
                   required_capabilities=tuple(d.get("required_capabilities", ())),
                   correlation_id=d.get("correlation_id", ""), record_id=d["record_id"],
                   recorded_at=float(d["recorded_at"]), schema=int(d.get("schema", SCHEMA_VERSION)))


# --------------------------------------------------------------------------
# 6. validation result (unified gate)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ValidationResult(Record):
    """Module 6 gate verdict for one candidate. No bypass of this record."""

    candidate_id: str
    accepted: bool
    checks: tuple[str, ...] = ()
    failed_constraints: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    explanation: str = ""
    corrective_action: str = ""
    correlation_id: str = ""
    record_id: str = field(default_factory=_new_id)
    recorded_at: float = 0.0
    schema: int = SCHEMA_VERSION

    def errors(self) -> list[str]:
        errs = _base_errors(self)
        if not self.candidate_id:
            errs.append("candidate_id is required")
        if self.accepted and self.failed_constraints:
            errs.append("accepted candidates must not carry failed_constraints")
        if not self.accepted and not self.failed_constraints and not self.missing_evidence:
            errs.append("rejected candidates must state why (failed or missing)")
        return errs

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ValidationResult":
        return cls(candidate_id=d["candidate_id"], accepted=bool(d.get("accepted", False)),
                   checks=tuple(d.get("checks", ())), failed_constraints=tuple(d.get("failed_constraints", ())),
                   warnings=tuple(d.get("warnings", ())), missing_evidence=tuple(d.get("missing_evidence", ())),
                   explanation=d.get("explanation", ""), corrective_action=d.get("corrective_action", ""),
                   correlation_id=d.get("correlation_id", ""), record_id=d["record_id"],
                   recorded_at=float(d["recorded_at"]), schema=int(d.get("schema", SCHEMA_VERSION)))


# --------------------------------------------------------------------------
# 7. historical what-if result (simulation, measured-based)
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class HistoricalResult(Record):
    """Module 7 output. Historical comparison — never a real measurement."""

    candidate_id: str
    baseline_policy_id: str
    metrics: dict[str, float] = field(default_factory=dict)
    ranking: tuple[str, ...] = ()
    limitations: tuple[str, ...] = ()
    complete: bool = False
    correlation_id: str = ""
    record_id: str = field(default_factory=_new_id)
    recorded_at: float = 0.0
    schema: int = SCHEMA_VERSION

    def errors(self) -> list[str]:
        errs = _base_errors(self)
        if not self.candidate_id or not self.baseline_policy_id:
            errs.append("candidate_id and baseline_policy_id are required")
        if not self.limitations:
            errs.append("limitations must always be stated")
        for k, v in self.metrics.items():
            if not isinstance(v, (int, float)) or not math.isfinite(float(v)):
                errs.append(f"metrics[{k}] must be finite")
        return errs

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "HistoricalResult":
        return cls(candidate_id=d["candidate_id"], baseline_policy_id=d["baseline_policy_id"],
                   metrics={k: float(v) for k, v in d.get("metrics", {}).items()},
                   ranking=tuple(d.get("ranking", ())), limitations=tuple(d.get("limitations", ())),
                   complete=bool(d.get("complete", False)), correlation_id=d.get("correlation_id", ""),
                   record_id=d["record_id"], recorded_at=float(d["recorded_at"]),
                   schema=int(d.get("schema", SCHEMA_VERSION)))


# --------------------------------------------------------------------------
# 8. decision result
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class DecisionResult(Record):
    """Module 8 output. The single decision a lifecycle produces."""

    action: DecisionAction
    current_policy_id: str
    confidence: dict[str, float | None] = field(default_factory=dict)
    selected_candidate_id: str | None = None
    rejected_candidate_ids: tuple[str, ...] = ()
    mandatory_checks: tuple[str, ...] = ()
    relevant_experiences: tuple[str, ...] = ()
    expected_trade_offs: tuple[str, ...] = ()
    reason: str = ""
    correlation_id: str = ""
    record_id: str = field(default_factory=_new_id)
    recorded_at: float = 0.0
    schema: int = SCHEMA_VERSION

    def errors(self) -> list[str]:
        errs = _base_errors(self)
        if not self.current_policy_id:
            errs.append("current_policy_id is required")
        if self.action == DecisionAction.SELECT and not self.selected_candidate_id:
            errs.append("SELECT requires selected_candidate_id")
        if self.action in (DecisionAction.RETAIN, DecisionAction.REJECT_ALL, DecisionAction.DEFER) and self.selected_candidate_id:
            errs.append(f"{self.action.value} must not carry a selected candidate")
        for name, v in self.confidence.items():
            if not _valid_conf(v):
                errs.append(f"confidence[{name}] must be in [0,1] or None")
        if not self.reason:
            errs.append("reason is required")
        return errs

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "DecisionResult":
        return cls(action=DecisionAction(d["action"]), current_policy_id=d["current_policy_id"],
                   confidence={k: (float(v) if v is not None else None) for k, v in d.get("confidence", {}).items()},
                   selected_candidate_id=d.get("selected_candidate_id"),
                   rejected_candidate_ids=tuple(d.get("rejected_candidate_ids", ())),
                   mandatory_checks=tuple(d.get("mandatory_checks", ())),
                   relevant_experiences=tuple(d.get("relevant_experiences", ())),
                   expected_trade_offs=tuple(d.get("expected_trade_offs", ())),
                   reason=d.get("reason", ""), correlation_id=d.get("correlation_id", ""),
                   record_id=d["record_id"], recorded_at=float(d["recorded_at"]),
                   schema=int(d.get("schema", SCHEMA_VERSION)))


# --------------------------------------------------------------------------
# 9. application result
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ApplicationResult(Record):
    """Controller submission outcome. Selected != applied != verified."""

    decision_id: str
    candidate_id: str | None
    submitted: bool
    controller_accepted: bool
    applied: bool
    readback_verified: bool
    intended_cfg: dict[str, Any] = field(default_factory=dict)
    actual_cfg: dict[str, Any] = field(default_factory=dict)
    failure: str | None = None
    correlation_id: str = ""
    record_id: str = field(default_factory=_new_id)
    recorded_at: float = 0.0
    schema: int = SCHEMA_VERSION

    def errors(self) -> list[str]:
        errs = _base_errors(self)
        if not self.decision_id:
            errs.append("decision_id is required")
        if self.applied and not self.controller_accepted:
            errs.append("applied implies controller_accepted")
        if self.readback_verified and not self.applied:
            errs.append("readback_verified implies applied")
        return errs

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ApplicationResult":
        return cls(decision_id=d["decision_id"], candidate_id=d.get("candidate_id"),
                   submitted=bool(d.get("submitted", False)), controller_accepted=bool(d.get("controller_accepted", False)),
                   applied=bool(d.get("applied", False)), readback_verified=bool(d.get("readback_verified", False)),
                   intended_cfg=dict(d.get("intended_cfg", {})), actual_cfg=dict(d.get("actual_cfg", {})),
                   failure=d.get("failure"), correlation_id=d.get("correlation_id", ""),
                   record_id=d["record_id"], recorded_at=float(d["recorded_at"]), schema=int(d.get("schema", SCHEMA_VERSION)))


# --------------------------------------------------------------------------
# 10. readback result
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class ReadbackResult(Record):
    """Kernel read-back comparison. Independent of outcome measurement."""

    verified: bool
    expected_cfg: dict[str, Any] = field(default_factory=dict)
    actual_cfg: dict[str, Any] = field(default_factory=dict)
    mismatches: tuple[str, ...] = ()
    correlation_id: str = ""
    record_id: str = field(default_factory=_new_id)
    recorded_at: float = 0.0
    schema: int = SCHEMA_VERSION

    def errors(self) -> list[str]:
        errs = _base_errors(self)
        if self.verified and self.mismatches:
            errs.append("verified readback must not carry mismatches")
        if not self.verified and not self.mismatches:
            errs.append("failed readback must name mismatches")
        return errs

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ReadbackResult":
        return cls(verified=bool(d.get("verified", False)),
                   expected_cfg=dict(d.get("expected_cfg", {})), actual_cfg=dict(d.get("actual_cfg", {})),
                   mismatches=tuple(d.get("mismatches", ())), correlation_id=d.get("correlation_id", ""),
                   record_id=d["record_id"], recorded_at=float(d["recorded_at"]), schema=int(d.get("schema", SCHEMA_VERSION)))


# --------------------------------------------------------------------------
# 11. actual outcome
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Outcome(Record):
    """Module 9 output. Real measurements only — predictions/sims excluded."""

    decision_id: str
    applied_policy_id: str
    outcome: OutcomeClass
    measurements: dict[str, float] = field(default_factory=dict)
    predicted: dict[str, float] = field(default_factory=dict)
    simulated: dict[str, float] = field(default_factory=dict)
    limitations: tuple[str, ...] = ()
    correlation_id: str = ""
    record_id: str = field(default_factory=_new_id)
    recorded_at: float = 0.0
    schema: int = SCHEMA_VERSION

    def errors(self) -> list[str]:
        errs = _base_errors(self)
        if not self.decision_id or not self.applied_policy_id:
            errs.append("decision_id and applied_policy_id are required")
        for k, v in self.measurements.items():
            if not isinstance(v, (int, float)) or not math.isfinite(float(v)):
                errs.append(f"measurements[{k}] must be finite")
        if self.outcome in (OutcomeClass.SUCCESSFUL, OutcomeClass.DEGRADED, OutcomeClass.RECOVERED) and not self.measurements:
            errs.append(f"{self.outcome.value} requires measured evidence")
        return errs

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Outcome":
        return cls(decision_id=d["decision_id"], applied_policy_id=d["applied_policy_id"],
                   outcome=OutcomeClass(d["outcome"]),
                   measurements={k: float(v) for k, v in d.get("measurements", {}).items()},
                   predicted={k: float(v) for k, v in d.get("predicted", {}).items()},
                   simulated={k: float(v) for k, v in d.get("simulated", {}).items()},
                   limitations=tuple(d.get("limitations", ())), correlation_id=d.get("correlation_id", ""),
                   record_id=d["record_id"], recorded_at=float(d["recorded_at"]), schema=int(d.get("schema", SCHEMA_VERSION)))


# --------------------------------------------------------------------------
# 12. recovery event
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class RecoveryEvent(Record):
    """Module 10 audit. Bounded, verified, never blind."""

    trigger: str
    previous_policy_id: str
    action: str  # ROLLBACK | SAFE_FALLBACK
    outcome: str  # SUCCESS | FAILED | INCONCLUSIVE
    failure_evidence: dict[str, Any] = field(default_factory=dict)
    duration_s: float | None = None
    remaining_uncertainty: str = ""
    correlation_id: str = ""
    record_id: str = field(default_factory=_new_id)
    recorded_at: float = 0.0
    schema: int = SCHEMA_VERSION

    def errors(self) -> list[str]:
        errs = _base_errors(self)
        if not self.trigger.strip():
            errs.append("trigger is required")
        if self.action not in ("ROLLBACK", "SAFE_FALLBACK"):
            errs.append("action must be ROLLBACK or SAFE_FALLBACK")
        if self.outcome not in ("SUCCESS", "FAILED", "INCONCLUSIVE"):
            errs.append("outcome must be SUCCESS, FAILED or INCONCLUSIVE")
        if self.outcome == "SUCCESS" and not self.failure_evidence:
            errs.append("successful recovery requires failure evidence")
        return errs

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "RecoveryEvent":
        return cls(trigger=d["trigger"], previous_policy_id=d["previous_policy_id"],
                   action=d["action"], outcome=d["outcome"],
                   failure_evidence=dict(d.get("failure_evidence", {})),
                   duration_s=d.get("duration_s"), remaining_uncertainty=d.get("remaining_uncertainty", ""),
                   correlation_id=d.get("correlation_id", ""), record_id=d["record_id"],
                   recorded_at=float(d["recorded_at"]), schema=int(d.get("schema", SCHEMA_VERSION)))


# re-export for callers that reference Lease/Capacity through contracts
__all__ = [
    "SCHEMA_VERSION", "Reliability", "PolicyHealth", "PredictionStatus",
    "ExperienceStatus", "DecisionAction", "OutcomeClass", "ValidationStatus",
    "NetworkState", "PolicyEvaluation", "Prediction", "Experience", "Candidate",
    "ValidationResult", "HistoricalResult", "DecisionResult", "ApplicationResult",
    "ReadbackResult", "Outcome", "RecoveryEvent",
    "Capacity", "Lease", "RatePlan", "TrafficClass",
]
