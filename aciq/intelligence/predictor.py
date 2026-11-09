"""Module 3 — Predictive Network Degradation Engine (Phase 4).

Deterministic trend analysis over recent `samples.jsonl` rows — no ML, no model
download, no network access. Explains itself via `evidence[]`; when inputs are
missing it says UNCERTAIN instead of guessing.
"""
from __future__ import annotations

import math
from typing import Any

from .config import IntelligenceConfig
from .contracts import NetworkState, Prediction, PredictionStatus


class DegradationPredictor:
    def __init__(self, config: IntelligenceConfig | None = None,
                 horizon_s: float | None = None):
        self.config = config or IntelligenceConfig()
        self.horizon_s = horizon_s if horizon_s is not None else self.config.prediction_horizon_s

    def predict(self, history: list[dict[str, Any]],
                state: NetworkState,
                correlation_id: str = "") -> Prediction:
        """History: recent sample dicts (oldest→newest). Needs ≥3 points."""
        pts = [p for p in history if isinstance(p, dict)]
        now = state.recorded_at
        base = dict(horizon_s=float(self.horizon_s), correlation_id=correlation_id,
                    recorded_at=now)

        if len(pts) < 3:
            return Prediction(status=PredictionStatus.UNCERTAIN, confidence=None,
                              missing_inputs=("history (>=3 points)",), **base)

        def series(name: str) -> list[float]:
            out = []
            for p in pts:
                v = p.get(name)
                if isinstance(v, (int, float)) and math.isfinite(float(v)):
                    out.append(float(v))
            return out

        def slope(name: str) -> float | None:
            vals = series(name)
            if len(vals) < 3:
                return None
            n = len(vals)
            xs = list(range(n))
            mx = sum(xs) / n
            my = sum(vals) / n
            den = sum((x - mx) ** 2 for x in xs)
            return sum((x - mx) * (v - my) for x, v in zip(xs, vals)) / den if den else 0.0

        missing: list[str] = []
        evidence: list[str] = []
        severity = 0.0
        confidence = 0.8  # starts high; each missing signal lowers it

        lat_s = slope("latency_ms")
        if lat_s is None:
            missing.append("latency trend")
            confidence -= 0.2
        elif lat_s > 0.5:
            evidence.append(f"latency rising {lat_s:.2f} ms/tick")
            severity += min(1.0, lat_s / 5.0)

        back_s = slope("backlog_bytes")
        if back_s is None:
            back_s = slope("bottleneck_backlog_bytes")
        if back_s is None:
            missing.append("queue trend")
            confidence -= 0.2
        elif back_s > 5000:
            evidence.append(f"queue growing {back_s:.0f} B/tick")
            severity += min(1.0, back_s / 50000.0)

        cap_s = slope("capacity_mbps")
        if cap_s is not None and cap_s < -1.0:
            evidence.append(f"capacity falling {cap_s:.2f} Mbps/tick")
            severity += min(1.0, abs(cap_s) / 20.0)

        # demand growth: active classes rising
        demands = [len(p.get("per_class") or {}) for p in pts]
        if demands and demands[-1] > demands[0]:
            evidence.append("active classes increasing")

        confidence = max(0.1, min(0.95, confidence))
        severity = max(0.0, min(1.0, severity))

        if severity >= 0.5:
            status = PredictionStatus.HIGH
        elif severity >= 0.2:
            status = PredictionStatus.POTENTIAL
        elif missing:
            status = PredictionStatus.UNCERTAIN
        else:
            status = PredictionStatus.NONE

        if status == PredictionStatus.UNCERTAIN:
            confidence = None  # unknown, never a number on a guess

        return Prediction(status=status, confidence=confidence, severity=severity,
                          evidence=tuple(evidence), missing_inputs=tuple(missing),
                          horizon_s=float(self.horizon_s),
                          correlation_id=correlation_id, recorded_at=now)
