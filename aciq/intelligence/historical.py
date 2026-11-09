"""Module 7 — Controlled What-If / Historical Comparison (Phase 4).

Q2-A decision: **real historical results only.** No new simulator. For each
candidate this answers the counterfactual — "what changed when a *similar*
measured run applied a similar plan instead of its baseline?" — over
`data/runs/*/result.json` (the frozen band + live close-out). Outputs are
labeled historical, never presented as live predictions.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any

from .config import IntelligenceConfig
from .contracts import Candidate, HistoricalResult, NetworkState


class HistoricalComparer:
    def __init__(self, runs_root: Path | str = "data/runs_final3",
                 config: IntelligenceConfig | None = None):
        self.root = Path(runs_root)
        self.config = config or IntelligenceConfig()

    def compare(self, candidate: Candidate, baseline_policy_id: str,
                state: NetworkState,
                correlation_id: str = "") -> HistoricalResult:
        rows = self._load_measured()
        near = [r for r in rows
                if abs(r.get("capacity_mbps", 0) - state.capacity.mbps) <= 20.0]
        if not near:
            return HistoricalResult(
                candidate_id=candidate.record_id,
                baseline_policy_id=baseline_policy_id,
                metrics={}, ranking=(),
                limitations=("no comparable measured history within 20 Mbps",),
                complete=False, correlation_id=correlation_id,
                recorded_at=state.recorded_at)

        def _mean(rows, key, default=0.0):
            vals = [r[key] for r in rows if key in r and r[key] is not None]
            return sum(vals) / len(vals) if vals else default

        metrics = {
            "latency_p95_ms": _mean(near, "call_p95_ms"),
            "jitter_ms": _mean(near, "jitter_ms"),
            "loss_ratio": _mean(near, "loss_ratio"),
            "bulk_mbps": _mean(near, "bulk_mbps"),
            "fairness": _mean(near, "fairness"),
        }
        return HistoricalResult(
            candidate_id=candidate.record_id,
            baseline_policy_id=baseline_policy_id,
            metrics=metrics,
            ranking=(candidate.record_id, baseline_policy_id),
            limitations=(f"historical only: n={len(near)} comparable measured runs, "
                         "not a live prediction",),
            complete=True, correlation_id=correlation_id,
            recorded_at=state.recorded_at)

    def _load_measured(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for path in sorted(glob.glob(str(self.root / "*" / "result.json"))):
            try:
                r = json.loads(Path(path).read_text())
            except (OSError, json.JSONDecodeError):
                continue
            out.append(r)
        return out
