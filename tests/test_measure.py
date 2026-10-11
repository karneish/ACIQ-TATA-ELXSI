"""Deterministic tests for the measurement arithmetic.

Every test here feeds a synthetic trace with a known answer. No sockets, no
clock, no `tc`. If these fail the reporting is wrong regardless of what the
network did.

The traces are the acceptance criteria of §5.7: known RTT, controlled loss,
duplicates, reordering, incomplete windows, and implausible samples.
"""

from __future__ import annotations

import unittest

from aciq.measure import (
    INSUFFICIENT_SAMPLES,
    MAX_PLAUSIBLE_RTT_MS,
    MIN_SAMPLES_FOR_PERCENTILES,
    NOT_MEASURED,
    VALID,
    Metrics,
    Observation,
    compute,
    dedupe,
    jitter,
    loss_ratio,
    percentile,
)


def _obs(n, rtt_ms, start=0.0, step=0.02, lost=()):
    """n observations, i-th with round trip `rtt_ms` (+i); `lost` are missing."""
    out = []
    for i in range(n):
        sent = start + i * step
        recv = None if i in lost else sent + (rtt_ms + i) / 1000.0
        out.append(Observation(seq=i, sent_mono_s=sent, recv_mono_s=recv))
    return out


class TestRtt(unittest.TestCase):
    def test_a_flat_path_reports_its_delay_at_every_percentile(self):
        # rtts are 10..49 ms over 40 samples; nearest-rank p50 is xs[19] = 29.
        m = compute(_obs(40, 10.0))
        self.assertAlmostEqual(m.rtt_p50_ms, 29.0, delta=0.01)
        self.assertAlmostEqual(m.rtt_p95_ms, 47.0, delta=0.01)
        self.assertAlmostEqual(m.rtt_p99_ms, 49.0, delta=0.01)
        self.assertLess(m.rtt_p95_ms, m.rtt_p99_ms)

    def test_one_way_delay_is_not_claimed(self):
        """No synchronised clocks exist across the namespaces, so every latency
        figure here is round trip. The field is named rtt_* for that reason."""
        m = compute(_obs(30, 5.0))
        for f in ("rtt_p50_ms", "rtt_p95_ms", "rtt_p99_ms"):
            self.assertIsNotNone(getattr(m, f))
        self.assertNotIn("one_way", repr(m.to_dict()))

    def test_a_missing_reply_is_not_an_rtt(self):
        o = Observation(seq=1, sent_mono_s=0.0, recv_mono_s=None)
        self.assertIsNone(o.rtt_ms)
        self.assertTrue(o.lost)


class TestPercentiles(unittest.TestCase):
    def test_nearest_rank_does_not_invent_a_value(self):
        xs = [1.0, 2.0, 3.0, 4.0]
        self.assertEqual(percentile(xs, 50), 2.0)
        self.assertEqual(percentile(xs, 100), 4.0)
        self.assertEqual(percentile(xs, 0), 1.0)

    def test_too_few_samples_gives_none_not_a_number(self):
        m = compute(_obs(MIN_SAMPLES_FOR_PERCENTILES - 1, 4.0))
        self.assertIsNone(m.rtt_p50_ms)
        self.assertIsNone(m.rtt_p95_ms)
        self.assertEqual(m.status, INSUFFICIENT_SAMPLES)

    def test_exactly_the_minimum_is_enough(self):
        m = compute(_obs(MIN_SAMPLES_FOR_PERCENTILES, 4.0))
        self.assertIsNotNone(m.rtt_p50_ms)
        self.assertEqual(m.status, VALID)

    def test_empty_input_is_not_measured_not_zero(self):
        m = compute([])
        self.assertEqual(m.status, NOT_MEASURED)
        self.assertIsNone(m.rtt_p50_ms)
        self.assertIsNone(m.loss_ratio)
        self.assertIsNone(m.jitter_ms)


class TestJitter(unittest.TestCase):
    def test_constant_delay_is_zero_jitter(self):
        """Zero is a real measurement here, not a missing value."""
        obs = [Observation(seq=i, sent_mono_s=i * 0.02,
                           recv_mono_s=i * 0.02 + 0.010) for i in range(20)]
        self.assertAlmostEqual(jitter(obs), 0.0, places=9)   # exact float noise

    def test_alternating_delay_reports_the_mean_swing(self):
        obs = [Observation(seq=i, sent_mono_s=i * 0.02,
                           recv_mono_s=i * 0.02 + (0.010 if i % 2 else 0.020))
               for i in range(20)]
        # jitter() is in milliseconds, same unit as rtt_ms: 20/10 ms alternating.
        self.assertAlmostEqual(jitter(obs), 10.0, places=6)

    def test_one_sample_has_no_jitter(self):
        self.assertIsNone(jitter(_obs(1, 5.0)))

    def test_jitter_ignores_a_paused_sample(self):
        base = [Observation(seq=i, sent_mono_s=i * 0.02,
                            recv_mono_s=i * 0.02 + 0.010) for i in range(20)]
        paused = list(base)
        paused.insert(10, Observation(seq=999, sent_mono_s=10.0,
                                      recv_mono_s=10.0 + MAX_PLAUSIBLE_RTT_MS + 1))
        self.assertAlmostEqual(jitter(paused), 0.0, places=9)


class TestLoss(unittest.TestCase):
    def test_no_loss_is_zero(self):
        self.assertEqual(loss_ratio(_obs(20, 5.0)), 0.0)

    def test_a_known_drop_is_counted(self):
        m = compute(_obs(20, 5.0, lost={0, 1, 2, 3, 4}))   # 5 of 20
        self.assertAlmostEqual(m.loss_ratio, 0.25)

    def test_in_flight_packets_are_not_lost_packets(self):
        """A run's last packets have not returned when the window closes. Counting
        them as lost produces a loss spike at the end of every run -- an artefact
        of the window, not of the link."""
        obs = _obs(20, 5.0)
        without = loss_ratio(obs, in_flight=0)
        with_inflight = loss_ratio(obs, in_flight=5)
        self.assertEqual(without, 0.0)
        self.assertEqual(with_inflight, 0.0)
        self.assertNotEqual(loss_ratio(_obs(20, 5.0, lost={16, 17, 18, 19}), 0),
                            with_inflight)

    def test_all_lost_is_total_loss_not_missing(self):
        m = compute(_obs(20, 5.0, lost=set(range(20))))
        self.assertEqual(m.loss_ratio, 1.0)
        self.assertIsNone(m.rtt_p50_ms)

    def test_loss_survives_when_latency_does_not(self):
        m = compute(_obs(30, 5.0, lost=set(range(10))))
        self.assertEqual(m.valid, 20)                       # >= the minimum
        self.assertEqual(m.status, VALID)
        self.assertAlmostEqual(m.loss_ratio, 10 / 30)


class TestDuplicates(unittest.TestCase):
    def test_a_duplicate_is_not_counted_twice(self):
        obs = _obs(10, 5.0)
        obs.append(obs[3])            # exact repeat
        unique, dups, _ = dedupe(obs)
        self.assertEqual(len(unique), 10)
        self.assertEqual(dups, 1)

    def test_a_duplicate_does_not_deflate_loss(self):
        obs = _obs(20, 5.0, lost={0, 1, 2})
        before = loss_ratio(obs)
        obs = obs + [obs[5], obs[5], obs[5]]
        self.assertEqual(loss_ratio(dedupe(obs)[0]), before)

    def test_the_first_reply_wins_for_a_repeated_sequence(self):
        """A duplicate reply is not a second measurement. Order decides, so the
        answer does not depend on which copy the network happened to deliver
        first."""
        # First occurrence wins, so a duplicate cannot reduce reported delay.
        long_ = Observation(seq=7, sent_mono_s=1.0, recv_mono_s=1.020)
        short = Observation(seq=7, sent_mono_s=1.0, recv_mono_s=1.001)
        self.assertAlmostEqual(dedupe([long_, short])[0][0].rtt_ms, 20.0)
        self.assertAlmostEqual(dedupe([short, long_])[0][0].rtt_ms, 1.0)

    def test_reordering_is_counted_not_penalised(self):
        # Reordering is counted in arrival order, so a swap is visible. The
        # first version counted inversions after sorting, which is structurally
        # always zero.
        obs = _obs(10, 5.0)
        obs[4], obs[5] = obs[5], obs[4]
        unique, _d, reordered = dedupe(obs)
        self.assertEqual(len(unique), 10)
        self.assertEqual(reordered, 1)
        self.assertEqual([o.seq for o in unique], list(range(10)))

    def test_reordering_does_not_invent_loss(self):
        obs = _obs(20, 5.0)
        obs.reverse()
        self.assertEqual(loss_ratio(dedupe(obs)[0]), 0.0)


class TestOutliers(unittest.TestCase):
    def test_an_implausible_sample_is_discarded(self):
        obs = _obs(30, 5.0)
        obs[15] = Observation(seq=15, sent_mono_s=0.3,
                              recv_mono_s=0.3 + MAX_PLAUSIBLE_RTT_MS / 1000 + 1)
        m = compute(obs)
        self.assertEqual(m.discarded_outlier, 1)
        self.assertLess(m.rtt_p95_ms, 100.0)

    def test_a_negative_rtt_is_impossible_and_discarded(self):
        obs = _obs(20, 5.0)
        obs[3] = Observation(seq=3, sent_mono_s=1.0, recv_mono_s=0.9)
        self.assertEqual(compute(obs).discarded_outlier, 1)


class TestAccounting(unittest.TestCase):
    def test_counts_add_up(self):
        m = compute(_obs(30, 5.0, lost={0, 1}))
        self.assertEqual(m.expected, 30)
        self.assertEqual(m.received, 28)
        self.assertEqual(m.valid, 28)

    def test_window_is_the_span_of_the_observations(self):
        m = compute(_obs(30, 5.0))
        self.assertAlmostEqual(m.window_s, 29 * 0.02, places=6)

    def test_every_derived_figure_is_recomputable_from_the_raw_stream(self):
        """§5.7: derived metrics must be reconstructible. Metrics carries
        everything needed to check the arithmetic."""
        m = compute(_obs(40, 8.0))
        d = m.to_dict()
        for k in ("rtt_p50_ms", "rtt_p95_ms", "rtt_p99_ms", "jitter_ms",
                  "loss_ratio", "expected", "received", "valid", "status"):
            self.assertIn(k, d)
        self.assertEqual(d["expected"], m.expected)

    def test_a_metric_is_never_zero_when_it_is_missing(self):
        """The defect this module exists to prevent."""
        m = compute([])
        for f in ("rtt_p50_ms", "rtt_p95_ms", "rtt_p99_ms", "jitter_ms",
                  "loss_ratio"):
            self.assertIsNone(getattr(m, f),
                             f"{f} defaulted instead of reporting unavailable")
        self.assertFalse(m.usable)


if __name__ == "__main__":
    unittest.main()