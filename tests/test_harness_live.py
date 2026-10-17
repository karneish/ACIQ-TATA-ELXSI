"""Unit-level checks on the live harness's out-of-band control.

These do not touch the kernel; they are here because the harness encodes two
decisions that are easy to get wrong and impossible to notice: how the emulated
bottleneck's buffer is sized, and that the bottleneck is installed out of band
so it cannot fight the controller for the same class.
"""
import unittest

from aciq.harness import (BUFFER_S, _MTU_BYTES, _MIN_BUFFER_PACKETS,
                          _netem_limit)


class TestNetemBufferIsRealistic(unittest.TestCase):
    """The emulated link's queue must be sized like a real CPE's.

    This is not cosmetic. A real congested run measured 206 packets median and
    625 at peak sitting in the netem queue, while the controller's OWN queue for
    the interactive class held 0 bytes at every single tick. The ~860 ms p95 was
    therefore almost entirely the testbed's buffer rather than the controller,
    and it inflated all three systems being compared alike.

    A test that cannot fail is what let the original `limit`-less command ship,
    so this asserts the arithmetic directly.
    """

    def test_buffer_is_fifty_ms_at_every_rate_a_scenario_uses(self):
        for rate in (10, 20, 100, 1000):
            with self.subTest(mbps=rate):
                limit = _netem_limit(rate)
                ms = limit * _MTU_BYTES / (rate * 1e6 / 8) * 1000
                self.assertAlmostEqual(ms, BUFFER_S * 1000, delta=5)

    def test_bits_to_bytes_conversion_is_present(self):
        """Guards the exact bug: omitting /8 gives 400 ms, not 50 ms."""
        for rate in (10, 20, 100):
            with self.subTest(mbps=rate):
                limit = _netem_limit(rate)
                without_division = int(rate * 1e6 * BUFFER_S / _MTU_BYTES)
                self.assertLess(limit, without_division,
                                "buffer sizing lost its bits-to-bytes /8")
                self.assertLess(limit * _MTU_BYTES / (rate * 1e6 / 8) * 1000,
                                BUFFER_S * 1000 * 2)

    def test_buffer_is_far_below_netems_default(self):
        """netem defaults to 1000 packets; we must never approach that."""
        for rate in (20, 100):
            with self.subTest(mbps=rate):
                self.assertLess(_netem_limit(rate), 1000)

    def test_floor_dominates_only_below_the_shaping_threshold(self):
        """Below ~4 Mbps the target is unreachable; the floor is the answer.

        Pinned so the floor cannot drift upward unnoticed -- a larger floor
        silently restores the very inflation this work removed.
        """
        self.assertEqual(_netem_limit(1), _MIN_BUFFER_PACKETS)
        self.assertGreater(_netem_limit(10), _MIN_BUFFER_PACKETS,
                           "10 Mbps should be sized by BUFFER_S, not the floor")

    def test_no_scenario_rate_falls_into_the_floor(self):
        """Every rate in the shipped scenarios must hit the real target."""
        for rate in (10, 20, 100):
            with self.subTest(mbps=rate):
                self.assertGreater(_netem_limit(rate), _MIN_BUFFER_PACKETS)


if __name__ == "__main__":
    unittest.main()