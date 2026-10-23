"""bulk.py's --rate-cap pacing: the cap must HOLD until the class passes
50% of capacity, else an update window swallows everything and the whole
corpus collapses into bulk_download (live evidence, first run: 5/6 wrong).
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from testbed.workloads.bulk import BLOCK, rate_cap_pace  # noqa: E402


class _Clock:
    def __init__(self):
        self.t = 100.0

    def monotonic(self):
        return self.t


class TestRateCapPace(unittest.TestCase):
    def test_early_window_sleeps_to_hold_the_cap(self):
        # 2 MB total sent right away, cap 20 Mbps: the byte clock says 0.8 s
        # of time is owed for those bytes, so the pacer sleeps the
        # max-shifted remainder, and not more.
        clock = _Clock()
        sleeps: list[float] = []

        def fake_sleep(s):
            sleeps.append(s)
            clock.t += s

        rate_cap_pace(sent=2_000_000, t0=clock.t, end=None, now=clock.t,
                      cap=20.0, sleep=fake_sleep, monotonic=clock.monotonic)
        self.assertAlmostEqual(sleeps[0], 0.5, places=2)

    def test_cap_reached_means_no_sleep(self):
        clock = _Clock()
        sleeps: list[float] = []

        def fake_sleep(s):
            sleeps.append(s)
            clock.t += s

        # 1 MB sent, 8 Mbps cap -> the byte clock says 1.0 s of time owed;
        # pretend 1.2 s really elapsed: the cap is being held, no sleep.
        rate_cap_pace(sent=1_000_000, t0=clock.t, end=None, now=clock.t + 1.2,
                      cap=8.0, sleep=fake_sleep, monotonic=clock.monotonic)
        self.assertEqual(sleeps, [])

    def test_uncapped_line_never_sleeps(self):
        clock = _Clock()
        sleeps: list[float] = []

        def fake_sleep(s):
            sleeps.append(s)

        rate_cap_pace(sent=BLOCK, t0=clock.t, end=None, now=clock.t + 0.01,
                      cap=None, sleep=fake_sleep, monotonic=clock.monotonic)
        self.assertEqual(sleeps, [])


if __name__ == "__main__":
    unittest.main()
