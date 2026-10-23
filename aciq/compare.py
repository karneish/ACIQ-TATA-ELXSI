"""Paired-engine comparison glue for phase 5/6 evidence: baseline vs engine
per metric, with the Wilcoxon signed-rank result attached.

`compare_runs` takes lists of per-seed result objects that both expose the
same metric, each carrying its seed id; the pairing rule is by SEED — pairing
by index would silently test wrong pairs the day one run failed and produced
n-1 results. A missing partner is reported as UNPAIRED, never averaged into
the neighbour.
"""

from __future__ import annotations

from dataclasses import dataclass

from .stats import WilcoxonResult, wilcoxon_signed_rank


@dataclass
class MetricComparison:
    metric: str
    n_pairs: int
    unpaired_seeds: list[str]
    baseline_median: float
    engine_median: float
    median_delta: float           # engine - baseline (positive = engine higher)
    wilcoxon: WilcoxonResult

    def as_p(self, threshold: float) -> bool:
        return self.wilcoxon.as_p(threshold)


def _median(xs: list[float]) -> float:
    xs = sorted(xs)
    n = len(xs)
    if n == 0:
        raise ValueError("no values")
    if n % 2:
        return xs[n // 2]
    return (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def compare_runs(baseline_runs: list, engine_runs: list, metric: str) -> MetricComparison:
    """Pair per-seed results by seed and test one metric.

    Both records must expose an int-like `seed` attribute (RunResult carries
    it; anything else must mimic it) and the metric as a float attribute or
    dict key.
    """
    def value_of(run):
        if isinstance(metric, str) and hasattr(run, metric):
            return float(getattr(run, metric))
        if isinstance(run, dict):
            return float(run[metric])
        raise ValueError(f"cannot read metric {metric!r} from {run!r}")

    def seed_of(run):
        s = run.get("seed") if isinstance(run, dict) else getattr(run, "seed", None)
        return None if s is None else int(s)

    base = {seed_of(r): value_of(r) for r in baseline_runs}
    eng = {seed_of(r): value_of(r) for r in engine_runs}
    both = sorted(set(base) & set(eng))
    unpaired = sorted(str(s) for s in set(base) ^ set(eng))
    if not both:
        raise ValueError("no seeds shared by baseline and engine")
    pairs_list = [(base[s], eng[s]) for s in both]
    return MetricComparison(
        metric=metric,
        n_pairs=len(both),
        unpaired_seeds=unpaired,
        baseline_median=round(_median([base[s] for s in both]), 4),
        engine_median=round(_median([eng[s] for s in both]), 4),
        median_delta=round(_median([e - b for b, e in pairs_list]), 4),
        wilcoxon=wilcoxon_signed_rank(pairs_list),
    )
