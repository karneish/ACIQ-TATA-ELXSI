"""External capacity source: read a link rate from an out-of-band source.

The controller cannot read the bottleneck's configured rate (by design).
An external report may be supplied by provisioning, a probe collector, or a
file written by another process. It is used only to seed recovery targets and
to record provenance -- never fed directly into the live estimate as the answer.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


class ExternalCapacityError(ValueError):
    pass


@dataclass(frozen=True)
class ExternalCapacityReport:
    mbps: float
    source: str = "external"
    t: float = 0.0
    stale_after_s: float | None = None
    metadata: dict | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.mbps, (int, float)) or isinstance(self.mbps, bool):
            raise ExternalCapacityError("mbps must be a number")
        if self.mbps != self.mbps or self.mbps in (float("inf"), float("-inf")):
            raise ExternalCapacityError("mbps must be finite")
        if self.mbps <= 0:
            raise ExternalCapacityError("mbps must be positive")
        if self.mbps > 100000:
            raise ExternalCapacityError("mbps is not plausible")

    def is_stale(self, now: float | None = None) -> bool:
        if self.stale_after_s is None:
            return False
        if self.t <= 0:
            return True
        now = time.time() if now is None else now
        return (now - self.t) > self.stale_after_s


def load_report(path: Path | str, now: float | None = None,
                max_age_s: float = 300.0) -> ExternalCapacityReport | None:
    try:
        raw = json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return None
    if not isinstance(raw, dict):
        return None
    try:
        mbps = raw.get("capacity_mbps", raw.get("mbps"))
        if mbps is None:
            return None
        report = ExternalCapacityReport(
            mbps=float(mbps),
            source=str(raw.get("source", "file")),
            t=float(raw.get("t", raw.get("ts", 0.0))),
            stale_after_s=raw.get("stale_after_s", max_age_s),
            metadata=raw.get("metadata"),
        )
        if report.is_stale(now):
            return None
        return report
    except (TypeError, ValueError, ExternalCapacityError):
        return None


class ExternalCapacitySource:
    def __init__(self, path: Path | str | None = None,
                 loader=load_report, max_age_s: float = 300.0):
        self.path = Path(path) if path is not None else None
        self.loader = loader
        self.max_age_s = max_age_s
        self.last_report: ExternalCapacityReport | None = None

    def report(self, now: float | None = None) -> ExternalCapacityReport | None:
        if self.path is None:
            return None
        r = self.loader(self.path, now=now, max_age_s=self.max_age_s)
        if r is not None:
            self.last_report = r
        return r

    def seed_high_water(self, estimator, now: float | None = None) -> bool:
        r = self.report(now=now)
        if r is None:
            return False
        if hasattr(estimator, "seed_high_water"):
            estimator.seed_high_water(r.mbps)
            return True
        return False
