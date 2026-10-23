"""Tests for aciq.stats and aciq.compare: exact stats, honest pairing.

Expected values are worked out BY HAND below so a formula bug reproduces as
a discrepancy rather than matching itself. The six-pair hand-computation is
the classic textbook one (differences 6, 8, 10, 47, 192, -88 from Lehmann's
chapter), whose exact two-sided p = 0.3125.

The enumeration is 2^n, so all tests stay under n=10 (a few seconds total).
"""

from __future__ import annotations

import unittest

from aciq.compare import compare_runs
from aciq.stats import wilcoxon_signed_rank


class TestWilcoxon(unittest.TestCase):
    def test_all_positive_gives_max_w(self):
        # all six diffs positive: W+ = 21, the largest possible; p = 2/64
        r = wilcoxon_signed_rank([(10.0, 11.0)] * 6)
        # careful: identical means SAME rank each; textook distinct values:
        r = wilcoxon_signed_rank([(1, 2), (2, 4), (3, 7), (4, 9), (5, 12),
                                  (6, 15)])
        self.assertEqual(r.n, 6)
        self.assertEqual(r.w_plus, 21.0)
        self.assertEqual(r.p_two_sided, round(2 / 64, 6))

    def test_lehmann_pairs(self):
        # diffs 6,8,10,47,192,-88; |diff| ranks: 6→1,8→2,10→3,47→4,88→5,192→6
        # so W+ = 1+2+3+4+6 = 16. Exact two-sided: outcomes with weight ≤ 5
        # numbered by hand: {}, {1},{2},{3},{4},{5},{1,2},{1,3},{1,4},{2,3}
        # = 10 on each tail → p = 20/64 = 0.3125 (this is the classic value
        # for this data set, reproduced here by enumeration).
        r = wilcoxon_signed_rank([(1, 7), (2, 10), (3, 13), (4, 51), (5, 197),
                                  (6, -82)])
        # recompute rank set: 88 ranks 5th, 192 ranks 6th
        self.assertEqual(r.w_plus, 16.0)
        self.assertEqual(r.p_two_sided, 0.3125)

    def test_nines_game_extreme(self):
        # n=1: p = 2/2 = 1 (a single pair can never be significant)
        r = wilcoxon_signed_rank([(1.0, 9.0)])
        self.assertEqual(r.p_two_sided, 1.0)

    def test_all_ties(self):
        r = wilcoxon_signed_rank([(5, 5)] * 4)
        self.assertEqual(r.n, 0)
        self.assertEqual(r.p_two_sided, 1.0)
        self.assertIn("tied", r.note)

    def test_zero_pairs_are_dropped_and_counted(self):
        r = wilcoxon_signed_rank([(1, 1), (2, 5), (3, 6), (4, 7), (5, 8),
                                  (6, 9), (7, 10), (8, 11)])
        self.assertEqual(r.dropped_zero_pairs, 1)
        self.assertEqual(r.n, 7)               # ranks 1..7 redistributed

    def test_tied_ranks_average(self):
        # diffs +1, +1 → both get rank 1.5; W+ = 3, p = 2/4
        r = wilcoxon_signed_rank([(0, 1), (0, 2)])
        self.assertEqual(r.w_plus, 3.0)
        self.assertEqual(r.p_two_sided, 0.5)

    def test_refuses_garbage(self):
        with self.assertRaises(ValueError):
            wilcoxon_signed_rank([])
        with self.assertRaises(ValueError):
            wilcoxon_signed_rank([(1, float("nan"))])


class _Run:
    def __init__(self, seed: int, **vals):
        self.seed = seed
        self.__dict__.update(vals)


class TestCompare(unittest.TestCase):
    def test_pairing_is_by_seed_not_index(self):
        # engines' seeds deliberately come in a different ORDER than the
        # baseline's: pairing by index would pair 0 with 3 and so on.
        base = [_Run(i, goodput=10.0 + i) for i in range(4)]
        eng = [_Run(s, goodput=12.0 + s) for s in [3, 2, 1, 0]]
        c = compare_runs(base, eng, "goodput")
        self.assertEqual(c.n_pairs, 4)
        self.assertEqual(c.unpaired_seeds, [])
        # every pair is (b, b+2): rank ties everywhere (all diffs equal),
        # so W+ collapses to one null value → p = 2/16: enumeration, not a
        # tie-at-zero situation (a constant offset is NOT a zero diff).
        self.assertEqual(c.median_delta, 2.0)
        self.assertEqual(c.wilcoxon.p_two_sided, 0.125)

    def test_unpaired_seeds_listed(self):
        base = [_Run(0, x=1.0), _Run(1, x=2.0), _Run(2, x=3.0)]
        eng = [_Run(1, x=2.5), _Run(2, x=3.5)]     # seed 0 engine missing
        c = compare_runs(base, eng, "x")
        self.assertEqual(c.n_pairs, 2)
        self.assertEqual(c.unpaired_seeds, ["0"])

    def test_significant_engine_win(self):
        # baseline ~10 everywhere, engine 15-100% higher on every seed
        base = [_Run(i, goodput=10.0) for i in range(6)]
        eng = [_Run(i, goodput=10.0 + 2.0 + 0.1 * i) for i in range(6)]
        c = compare_runs(base, eng, "goodput")
        # all six diffs positive → p = 2/64 ≈ 0.03125
        self.assertEqual(c.wilcoxon.p_two_sided, round(2 / 64, 6))
        self.assertTrue(c.as_p(0.05))
        self.assertFalse(c.as_p(0.01))

    def test_metric_glue_dict_records(self):
        c = compare_runs([{"seed": 0, "p95": 40.0}, {"seed": 1, "p95": 44.0}],
                         [{"seed": 0, "p95": 36.0}, {"seed": 1, "p95": 40.0}],
                         "p95")
        self.assertEqual(c.baseline_median, 42.0)
        self.assertEqual(c.engine_median, 38.0)
        self.assertEqual(c.median_delta, -4.0)

    def test_no_shared_seeds_refused(self):
        with self.assertRaises(ValueError):
            compare_runs([_Run(0, x=1)], [_Run(5, x=2)], "x")


if __name__ == "__main__":
    unittest.main()
