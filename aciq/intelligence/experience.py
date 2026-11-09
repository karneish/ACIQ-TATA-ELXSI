"""Experience Repository (Phase 3, Module 4).

Append-only JSONL at `data/experiences.jsonl` by default — same storage pattern
as `aciq/corrections.py`: single-write + fsync, no locking, concurrent readers
never block. The store is stateless: every read hits disk, so a restart loses
nothing and a corrupt line never terminates a read.

Safety rules (spec §§13, 25):
* Records that fail schema or contract validation are **quarantined** (counted,
  listed, skipped) — never repaired, never promoted.
* `SIMULATION_ONLY` / `PREDICTION_ONLY` / `INCOMPLETE` are **never** returned as
  evidence of real success, and never outrank a MEASURED record.
* Retrieval is similarity-ranked and *explained*; low similarity returns
  "insufficient evidence", never a forced match.
"""
from __future__ import annotations

import json
import math
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .contracts import (
    SCHEMA_VERSION,
    DecisionResult,
    Experience,
    ExperienceStatus,
)
from .config import IntelligenceConfig

DEFAULT_PATH = Path("data/experiences.jsonl")
_MEASURED = (ExperienceStatus.SUCCESS, ExperienceStatus.FAILED, ExperienceStatus.RECOVERY)


@dataclass
class LoadStats:
    loaded: int = 0
    skipped_malformed: int = 0
    skipped_wrong_version: int = 0
    skipped_invalid: int = 0
    quarantined: list[str] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.quarantined is None:
            self.quarantined = []


@dataclass
class RetrievedExperience:
    experience: Experience
    score: float  # 0..1
    explanation: str


def _similarity(query: dict[str, Any], exp: Experience) -> tuple[float, list[str], list[str]]:
    """Score one experience against a query context. Returns (score, matched, differed)."""
    ctx = exp.network_context
    matched: list[str] = []
    differed: list[str] = []

    def _close(name: str, a: float | None, b: float | None, tol: float) -> bool:
        if a is None or b is None:
            return False
        return abs(float(a) - float(b)) <= tol

    q_cap = query.get("capacity_mbps")
    e_cap = ctx.get("capacity_mbps")
    if _close("capacity", q_cap, e_cap, 20.0):
        matched.append("capacity")
    else:
        differed.append("capacity")

    for dim, tol in (("latency_ms", 10.0), ("jitter_ms", 5.0), ("loss_ratio", 0.05)):
        if _close(dim, query.get(dim), ctx.get(dim), tol):
            matched.append(dim)
        else:
            differed.append(dim)

    # Per-class demand overlap (Jaccard over classes present in both).
    q_dem = set((query.get("demand") or {}).keys())
    e_dem = set((ctx.get("demand") or {}).keys())
    if q_dem and e_dem:
        if q_dem & e_dem:
            matched.append("demand")
        else:
            differed.append("demand")
    if query.get("intent_label") and ctx.get("intent_label") == query["intent_label"]:
        matched.append("intent")

    if not matched:
        return 0.0, matched, differed
    score = len(matched) / max(1, len(matched) + len(differed))
    return score, matched, differed


class ExperienceStore:
    """Append-only JSONL store. Stateless across restarts."""

    def __init__(self, path: Path | str = DEFAULT_PATH,
                 config: IntelligenceConfig | None = None):
        self.path = Path(path)
        self.config = config or IntelligenceConfig()

    # -- write -------------------------------------------------------------
    def append(self, experience: Experience) -> None:
        experience.validate()
        d = experience.to_dict()
        d["schema"] = SCHEMA_VERSION
        line = json.dumps(d, sort_keys=True) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    # -- read --------------------------------------------------------------
    def load_all(self) -> tuple[list[Experience], LoadStats]:
        """Read every line. Corrupt lines are quarantined, never raised."""
        out: list[Experience] = []
        stats = LoadStats()
        if not self.path.exists():
            return out, stats
        for lineno, raw in enumerate(self.path.read_text(encoding="utf-8").splitlines(), 1):
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                stats.skipped_malformed += 1
                stats.quarantined.append(f"line {lineno}: not JSON")
                continue
            if not isinstance(data, dict) or data.get("schema") != SCHEMA_VERSION:
                stats.skipped_wrong_version += 1
                stats.quarantined.append(f"line {lineno}: wrong/missing schema")
                continue
            try:
                exp = Experience.from_dict(data)
                exp.validate()
            except (KeyError, TypeError, ValueError) as e:
                stats.skipped_invalid += 1
                stats.quarantined.append(f"line {lineno}: {e}")
                continue
            out.append(exp)
            stats.loaded += 1
        return out, stats

    # -- retrieval ---------------------------------------------------------
    def retrieve(self, query: dict[str, Any], limit: int = 5) -> list[RetrievedExperience]:
        """Most similar MEASURED experiences first, explained. Empty = no evidence.

        SIMULATION_ONLY / PREDICTION_ONLY / INCOMPLETE are never returned as
        primary evidence; they surface only when nothing measured exists, and
        even then flagged in the explanation.
        """
        records, _ = self.load_all()
        measured = [r for r in records if r.status in _MEASURED]
        pool = measured if measured else [
            r for r in records
            if r.status in (ExperienceStatus.SIMULATION_ONLY, ExperienceStatus.PREDICTION_ONLY)
        ]
        ranked: list[RetrievedExperience] = []
        for exp in pool:
            score, matched, differed = _similarity(query, exp)
            if score < self.config.similarity_threshold:
                continue
            why = f"matched {','.join(matched)}; differed {','.join(differed) or 'none'}"
            if exp.status not in _MEASURED:
                why += f"; WARN {exp.status.value} is not measured evidence"
            ranked.append(RetrievedExperience(exp, round(score, 4), why))
        ranked.sort(key=lambda r: (r.score, r.experience.recorded_at), reverse=True)
        return ranked[: max(0, limit)]

    # -- retention ---------------------------------------------------------
    def prune(self, keep: int | None = None) -> Path | None:
        """Keep newest `keep` records; archive the rest to a timestamped backup.

        Returns the backup path, or None when nothing was pruned.
        """
        keep = keep if keep is not None else self.config.retention_max_records
        records, _ = self.load_all()
        if len(records) <= keep:
            return None
        cut = len(records) - keep
        archive = records[:cut]
        kept = records[cut:]
        backup = self.path.with_name(
            f"{self.path.name}.bak-{int(time.time())}.jsonl")
        with open(backup, "w", encoding="utf-8") as f:
            for exp in archive:
                f.write(json.dumps(exp.to_dict(), sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            for exp in kept:
                f.write(json.dumps(exp.to_dict(), sort_keys=True) + "\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)
        return backup


# --------------------------------------------------------------------------
# decision audit log (separate file chosen by the author)
# --------------------------------------------------------------------------

class DecisionLogger:
    """Append-only `data/intelligence/decisions.jsonl`.

    One line per DecisionResult — the audit trail behind "why did ACIQ do
    that?" (spec §23). Same atomic-append pattern as the Experience store.
    """

    def __init__(self, path: Path | str = "data/intelligence/decisions.jsonl"):
        self.path = Path(path)

    def append(self, decision: DecisionResult) -> None:
        decision.validate()
        d = decision.to_dict()
        d["schema"] = SCHEMA_VERSION
        line = json.dumps(d, sort_keys=True) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())

    def load_all(self) -> list[DecisionResult]:
        out: list[DecisionResult] = []
        if not self.path.exists():
            return out
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            if not raw.strip():
                continue
            try:
                d = json.loads(raw)
            except json.JSONDecodeError:
                continue  # audit log must never crash the loop
            if not isinstance(d, dict) or d.get("schema") != SCHEMA_VERSION:
                continue
            try:
                rec = DecisionResult.from_dict(d)
                rec.validate()
            except (KeyError, TypeError, ValueError):
                continue
            out.append(rec)
        return out
