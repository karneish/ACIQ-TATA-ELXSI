"""Intelligence layer configuration (Phase 3).

Every operational parameter lives here, validated at startup. No hardcoded
magic numbers elsewhere in `aciq/intelligence/`. Defaults are documented in
`docs/intelligence/phase3-foundation.md`.
"""
from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .contracts import SCHEMA_VERSION


@dataclass(frozen=True)
class IntelligenceConfig:
    """All tunables for the intelligence layer, with safe defaults."""

    schema: int = SCHEMA_VERSION
    # prediction
    prediction_horizon_s: float = 60.0
    # freshness: a measurement older than this cannot justify a change
    freshness_limit_s: float = 5.0
    # candidates
    max_candidates: int = 5
    min_hold_s: float = 30.0
    # verification / recovery
    verification_window_s: float = 30.0
    recovery_attempt_limit: int = 3
    recovery_cooldown_s: float = 30.0
    # experience retention
    retention_max_records: int = 5000
    # similarity gate for retrieval
    similarity_threshold: float = 0.6
    # safety: headroom kept under estimated capacity
    capacity_margin_fraction: float = 0.05
    # storage
    experience_path: str = "data/experiences.jsonl"
    decisions_path: str = "data/intelligence/decisions.jsonl"

    def errors(self) -> list[str]:
        errs: list[str] = []
        if self.schema != SCHEMA_VERSION:
            errs.append(f"schema must be {SCHEMA_VERSION}")
        def _pos(name: str, v: float) -> None:
            if not isinstance(v, (int, float)) or not math.isfinite(float(v)) or float(v) < 0:
                errs.append(f"{name} must be finite and >= 0")
        for name in ("prediction_horizon_s", "freshness_limit_s", "min_hold_s",
                     "verification_window_s", "recovery_cooldown_s",
                     "capacity_margin_fraction"):
            _pos(name, float(getattr(self, name)))
        if self.prediction_horizon_s <= 0:
            errs.append("prediction_horizon_s must be > 0")
        if not isinstance(self.max_candidates, int) or isinstance(self.max_candidates, bool) \
                or not (1 <= self.max_candidates <= 20):
            errs.append("max_candidates must be an int in [1, 20]")
        if not isinstance(self.recovery_attempt_limit, int) \
                or isinstance(self.recovery_attempt_limit, bool) \
                or not (1 <= self.recovery_attempt_limit <= 10):
            errs.append("recovery_attempt_limit must be an int in [1, 10]")
        if not isinstance(self.retention_max_records, int) \
                or isinstance(self.retention_max_records, bool) \
                or self.retention_max_records < 100:
            errs.append("retention_max_records must be an int >= 100")
        if not (0.0 < self.similarity_threshold <= 1.0):
            errs.append("similarity_threshold must be in (0, 1]")
        if not (0.0 <= self.capacity_margin_fraction < 1.0):
            errs.append("capacity_margin_fraction must be in [0, 1)")
        if not self.experience_path or not self.decisions_path:
            errs.append("storage paths must be non-empty")
        return errs

    def is_valid(self) -> bool:
        return not self.errors()

    def validate(self) -> None:
        errs = self.errors()
        if errs:
            raise ValueError(f"IntelligenceConfig invalid: {errs}")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IntelligenceConfig":
        known = {f for f in cls.__dataclass_fields__}
        unknown = set(d) - known
        if unknown:
            raise ValueError(f"unknown config keys: {sorted(unknown)}")
        cfg = cls(**dict(d))
        cfg.validate()
        return cfg

    def load(self, path: Path | str) -> None:  # pragma: no cover - CLI hook
        raise NotImplementedError("use IntelligenceConfig.from_file()")

    @classmethod
    def from_file(cls, path: Path | str) -> "IntelligenceConfig":
        text = Path(path).read_text(encoding="utf-8")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"config file {path} is not valid JSON: {e}") from e
        if not isinstance(data, dict):
            raise ValueError(f"config file {path} must contain a JSON object")
        unknown = set(data) - set(cls.__dataclass_fields__)
        if unknown:
            raise ValueError(f"config file {path}: unknown keys {sorted(unknown)}")
        return cls.from_dict(data)
