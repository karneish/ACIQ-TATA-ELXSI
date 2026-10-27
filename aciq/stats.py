"""Paired statistics, offline and threshold-free.

Phase 6 needs one primary test: the Wilcoxon signed-rank test over paired
runs (same seed, baseline vs engine), because run-by-run goodput medians are
paired, non-Gaussian data with n=10 — a t-test would be a category error and
n=10 has no honest asymptotic shortcut.

The implementation here is EXACT for n <= 20: the null distribution of W+ is
enumerated over all 2^n sign assignments, which is at most a million terms
and takes well under a second in pure Python. No normal approximation is
used at any n, so no continuous correction inflates a small difference into
significance.

Contracts:

- pairs must be PAIRS: same seed, same scenario, only the system differs.
  `wilcoxon_signed_rank` refuses unbalanced/None-led input rather than
  silently averaging in what it had.
- ties at zero: dropped from ranking (the classic convention), and the
  returned record says how many were dropped, because a 10-pair test with 4
  zero pairs is a 6-pair test.
- ties within |diff|: average ranks.
- p-value: two-sided, by full enumeration; the report also gives W+ itself
  so the evidence file shows the raw STATISTIC, not just a probability.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass


@dataclass(frozen=True)
class WilcoxonResult:
    n: int                 # non-zero pairs actually ranked
    dropped_zero_pairs: int
    w_plus: float          # sum of ranks of positive diffs
    p_two_sided: float
    note: str = ""

    @property
    def significant(self) -> bool | None:
        """Boolean only with a stated threshold; None demands one."""
        return None

    def as_p(self, threshold: float) -> bool:
        """Significant under EXPLICITLY PASSED threshold. No default."""
        return self.p_two_sided < threshold


def _ranks_of(abs_diffs: list[float]) -> list[float]:
    """Average ranks (1-based) with ties split evenly."""
    order = sorted(range(len(abs_diffs)), key=lambda i: abs_diffs[i])
    ranks = [0.0] * len(abs_diffs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and abs(abs_diffs[order[j + 1]] -
                                         abs_diffs[order[i]]) < 1e-12:
            j += 1
        avg = (i + j) / 2.0 + 1.0     # ranks i..j → 1-based average
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def wilcoxon_signed_rank(pairs: list[tuple[float, float]]) -> WilcoxonResult:
    """Exact two-sided Wilcoxon signed-rank p for paired samples.

    `pairs`: (baseline, engine) for each seed. Raises ValueError on an empty
    list or non-finite values — this module has no "graceful nonsense" mode.
    """
    if not pairs:
        raise ValueError("no pairs given")
    diffs = []
    zeros = 0
    for a, b in pairs:
        d = b - a
        for v in (a, b):
            if not math.isfinite(v):
                raise ValueError(f"non-finite pair value: {pairs}")
        if d == 0.0:
            zeros += 1
            continue
        diffs.append(d)
    n = len(diffs)
    if n == 0:
        return WilcoxonResult(0, zeros, 0.0, 1.0,
                              "all pairs tied; no test possible")
    ranks = _ranks_of([abs(d) for d in diffs])
    w_plus_obs = sum(r for r, d in zip(ranks, diffs, strict=True) if d > 0)
    # null distribution of W+ over every sign pattern, exact
    total = 2 ** n
    count_ge = 0
    for signs in itertools.product((1, -1), repeat=n):
        w = sum(r for r, s in zip(ranks, signs, strict=True) if s > 0)
        # two-sided distance of W+ from its null mean n(n+1)/4
        if abs(w - n * (n + 1) / 4.0) >= abs(w_plus_obs - n * (n + 1) / 4.0) \
                - 1e-12:
            count_ge += 1
    return WilcoxonResult(n, zeros, round(w_plus_obs, 3),
                          round(count_ge / total, 6),
                          "exact signed-rank, no normal approximation")
