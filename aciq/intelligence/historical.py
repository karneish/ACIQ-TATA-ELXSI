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
        self._rows_cache: list[dict[str, Any]] | None = None

    @staticmethod
    def _capacity_of(r: dict[str, Any]) -> float | None:
        # Semantics (verified against live result.json): link_end_mbps is the
        # run's final applied link rate = the scenario truth (100 for s1, 20
        # for a 100→20 drop, 100 after recovery). estimator_mbps is the
        # estimator's internal reading, which *lags* truth (75.4 vs 100) and
        # is therefore only a fallback, never the comparability axis.
        for key in ("link_end_mbps", "estimator_mbps"):
            v = r.get(key)
            if isinstance(v, (int, float)) and v > 0:
                return float(v)
        return None

    def compare(self, candidate: Candidate, baseline_policy_id: str,
                state: NetworkState,
                correlation_id: str = "") -> HistoricalResult:
        rows = [r for r in self._load_measured()
                if self._capacity_of(r) is not None]
        near = [r for r in rows
                if abs(self._capacity_of(r) - state.capacity.mbps) <= 20.0]
        if not near:
            return HistoricalResult(
                candidate_id=candidate.record_id,
                baseline_policy_id=baseline_policy_id,
                metrics={}, ranking=(),
                limitations=("no comparable measured history within 20 Mbps",),
                complete=False, correlation_id=correlation_id,
                recorded_at=state.recorded_at)

        def _mean(vals: list[float]) -> float:
            return sum(vals) / len(vals)

        # Metrics come from the workload reports beside result.json
        # (call.json / bulk.json) — result.json carries no outcome metrics.
        metrics: dict[str, float] = {}
        lat, jit, loss, bulk = [], [], [], []
        for r in rows:
            if r not in near:
                continue
            run_dir = r.get("_dir")
            if not run_dir:
                continue
            call = self._read_json(Path(run_dir) / "call.json")
            bulk_rep = self._read_json(Path(run_dir) / "bulk.json")
            if call:
                if call.get("p95") is not None:
                    lat.append(float(call["p95"]))
                if call.get("jitter_ms") is not None:
                    jit.append(float(call["jitter_ms"]))
                if call.get("loss_ratio") is not None:
                    loss.append(float(call["loss_ratio"]))
            if bulk_rep and bulk_rep.get("sender_mbps") is not None:
                bulk.append(float(bulk_rep["sender_mbps"]))
        if lat:
            metrics["latency_p95_ms"] = _mean(lat)
        if jit:
            metrics["jitter_ms"] = _mean(jit)
        if loss:
            metrics["loss_ratio"] = _mean(loss)
        if bulk:
            metrics["bulk_mbps"] = _mean(bulk)
        # NOTE: per-run fairness is not recorded per run (fairness.py computes
        # it cross-mode); it is intentionally absent here — never fabricated.
        return HistoricalResult(
            candidate_id=candidate.record_id,
            baseline_policy_id=baseline_policy_id,
            metrics=metrics,
            ranking=(candidate.record_id, baseline_policy_id),
            limitations=(f"historical only: n={len(near)} comparable measured runs, "
                         "not a live prediction",),
            complete=True, n_comparable=len(near),
            correlation_id=correlation_id,
            recorded_at=state.recorded_at)

    def _load_measured(self) -> list[dict[str, Any]]:
        # cached: the runs tree does not change during a run
        if self._rows_cache is not None:
            return self._rows_cache
        out: list[dict[str, Any]] = []
        for path in sorted(glob.glob(str(self.root / "*" / "result.json"))):
            try:
                r = json.loads(Path(path).read_text())
            except (OSError, json.JSONDecodeError):
                continue
            r["_dir"] = str(Path(path).parent)  # internal: locate workload reports
            out.append(r)
        self._rows_cache = out
        return out

    @staticmethod
    def _read_json(path: Path) -> dict[str, Any] | None:
        try:
            d = json.loads(path.read_text())
        except (OSError, json.JSONDecodeError):
            return None
        return d if isinstance(d, dict) else None
