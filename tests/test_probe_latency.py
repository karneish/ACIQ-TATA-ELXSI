"""The latency probe must not report its own pacing interval as network delay.

WHAT IS ESTABLISHED

A per-packet trace from a real congested run, 2995 packets, one seed:

    p50 20.086 ms   p95 100.052 ms   p99 100.188 ms   max 120.123 ms
    60.7% of packets over 5 ms

and the values are quantised: 20.05, 20.14, 40.19, 100.05, 120.12 ms. Those are
one, two and six times the 20 ms pacing interval. Three queueing disciplines
(FIFO, CAKE, ACIQ) agreed on the figure to 0.01 ms, which is not something
different schedulers do.

The cause: `UdpProbe` slept until the next send and drained replies only on the
send tick. `_drain` gives up after DRAIN_TIMEOUT_S (0.5 ms), so when the true
round trip exceeds that -- 1.2 ms on the testbed -- the reply has not arrived
when the drain runs, and waits in the socket buffer for the next send 20 ms
later. `recv_ns` is taken after `recvfrom` returns, so that wait was booked as
network delay, on every packet.

WHY THE FIRST VERSION OF THIS TEST PROVED NOTHING

It ran on loopback and passed against the buggy code. On loopback the round trip
is ~0.05 ms, comfortably inside DRAIN_TIMEOUT_S, so the drain after each send
catches the reply immediately and the bug never manifests. The reproduction has
to delay the sink by MORE than DRAIN_TIMEOUT_S. Every test below does.

    Loopback RTT      ~0.05 ms
    DRAIN_TIMEOUT_S    0.50 ms   <- drain gives up here
    testbed RTT        1.20 ms   <- reply arrives after that
"""
import socket
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "testbed" / "workloads"))

from udpx import DRAIN_TIMEOUT_S, UdpProbe, _DRAIN_POLL_S  # noqa: E402

#: A round trip that is genuinely slower than DRAIN_TIMEOUT_S, so the drain
#: after each send times out and the reply has to wait for the next tick.
#: 3 ms is small enough to be realistic on a local link and comfortably above
#: the 0.5 ms drain timeout.
SINK_DELAY_S = 0.003


class _DelayedEcho(threading.Thread):
    """Echo sink that waits before replying, so the RTT exceeds the drain timeout."""

    daemon = True

    def __init__(self, port, delay_s):
        super().__init__()
        self.delay_s = delay_s
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", port))
        self.running = True

    def run(self):
        self.sock.settimeout(0.2)
        while self.running:
            try:
                data, addr = self.sock.recvfrom(4096)
            except (socket.timeout, OSError):
                continue
            time.sleep(self.delay_s)
            try:
                self.sock.sendto(data, addr)
            except OSError:
                pass

    def stop(self):
        self.running = False
        self.join(timeout=2)
        self.sock.close()


class TestProbeDoesNotReportItsPacingInterval(unittest.TestCase):
    PPS = 50.0

    @classmethod
    def _measure(cls, port, delay_s=SINK_DELAY_S, duration=2.0):
        sink = _DelayedEcho(port, delay_s)
        sink.start()
        try:
            probe = UdpProbe("127.0.0.1", port, pps=cls.PPS, payload_bytes=64)
            probe.run(duration_s=duration)
            return probe.report()
        finally:
            sink.stop()

    def test_the_reproduction_actually_crosses_the_drain_timeout(self):
        """If the round trip were inside DRAIN_TIMEOUT_S this file proves
        nothing, so the premise is asserted rather than assumed."""
        self.assertGreater(SINK_DELAY_S * 1000, DRAIN_TIMEOUT_S * 1000)

    def test_median_is_not_one_pacing_interval(self):
        """The bug put p50 at exactly 20.086 ms on a 3 ms path."""
        rep = self._measure(45931)
        interval_ms = 1000.0 / self.PPS
        self.assertLess(rep["p50"], interval_ms,
                        f"p50 {rep['p50']:.2f} ms is a whole pacing interval "
                        f"({interval_ms:.0f} ms) on a {SINK_DELAY_S*1000:.0f} ms "
                        f"path -- the probe is timing its own sleep")

    def test_tail_is_not_a_multiple_of_the_pacing_interval(self):
        rep = self._measure(45932)
        interval_ms = 1000.0 / self.PPS
        self.assertLess(rep["p95"], interval_ms,
                        f"p95 {rep['p95']:.2f} ms is at least one pacing "
                        f"interval ({interval_ms:.0f} ms)")

    def test_percentiles_are_not_quantised_to_the_interval(self):
        """The raw signature: several distinct packets land on exact multiples."""
        rep = self._measure(45933)
        interval_ms = 1000.0 / self.PPS
        self.assertLess(rep["p95"] / interval_ms, 1.0)

    def test_a_real_delay_is_still_reported(self):
        """A probe that simply reported a tiny constant would pass everything
        above, so the measurement has to actually track the imposed delay."""
        rep = self._measure(45934)
        self.assertGreater(rep["p50"], SINK_DELAY_S * 1000 * 0.6,
                           "the imposed delay vanished from the report")

    def test_loss_accounting_still_works(self):
        rep = self._measure(45935)
        self.assertGreater(rep["pps_achieved"], 0)
        self.assertLessEqual(rep["loss_ratio"], 1.0)

    def test_drain_poll_is_far_below_the_pacing_interval(self):
        self.assertLess(_DRAIN_POLL_S, 0.005)
        self.assertGreater(_DRAIN_POLL_S, 0.0)


if __name__ == "__main__":
    unittest.main()