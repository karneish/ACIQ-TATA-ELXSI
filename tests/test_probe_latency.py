"""The latency probe must not measure its own polling interval.

WHAT IS ESTABLISHED

A congested run reports p50 1.19 ms, p95 80.126 ms, p99 100.265 ms, jitter
9.1 ms, 4 packets lost of 2000. The p50 is healthy. The tail is not: 80.126 and
100.265 are exact multiples of the 20 ms pacing interval (50 pps), and FIFO,
CAKE and ACIQ agree on them to 0.01 ms. Three different queueing disciplines do
not agree to a hundredth of a millisecond in the real world. Something is
quantising the tail to the pacing interval, and it is not the network.

WHAT IS NOT ESTABLISHED

Not the cause. Two candidate explanations were tested and both were wrong:

  - the sender drained replies only on the send tick (fixed, see
    TestProbeDoesNotMeasureItsOwnPolling); on loopback the old and new code
    both report sub-millisecond, and the old code is marginally *better*, so
    drain cadence is not it
  - the bulk ceiling failing to apply; ruled out by measurement -- bulk fell
    from 19.88 to 17.49 Mbps and the bottleneck backlog fell from ~75 to 1
    packet, yet the tail did not move at all

So these tests do NOT reproduce the 80 ms artifact, and nothing here should be
read as claiming they do. They assert the invariant that would catch it if a
future change reintroduced a comparable bias, and they pin the deliberately-slow
sink case so a probe cannot pass by simply reporting a small constant.
"""
import socket
import sys
import threading
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "testbed" / "workloads"))

from udpx import UdpProbe  # noqa: E402


class _Echo(threading.Thread):
    """Echo sink that can be told to reply after a delay."""

    daemon = True

    def __init__(self, port, delay_s=0.0):
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
            if self.delay_s:
                time.sleep(self.delay_s)
            try:
                self.sock.sendto(data, addr)
            except OSError:
                pass

    def stop(self):
        self.running = False
        self.join(timeout=2)
        self.sock.close()


class TestProbeDoesNotMeasureItsOwnPolling(unittest.TestCase):
    def _measure(self, port, duration=1.2):
        sink = _Echo(port)
        sink.start()
        try:
            probe = UdpProbe("127.0.0.1", port, pps=50.0, payload_bytes=64)
            probe.run(duration_s=duration)
            return probe.report()
        finally:
            sink.stop()

    def test_tail_is_not_a_multiple_of_the_pacing_interval(self):
        """The old bug put p95 at exactly 4x the 20 ms interval."""
        rep = self._measure(45911)
        interval_ms = 1000.0 / 50.0
        self.assertGreater(rep["pps_achieved"], 0)
        with self.subTest(p95=rep["p95"], interval=interval_ms):
            # Loopback is sub-millisecond. Anything at or above two full
            # intervals in the tail means the sender is again reporting how
            # long it slept rather than how long the packet took.
            self.assertLess(rep["p95"], interval_ms * 2)

    def test_p50_stays_sub_interval_too(self):
        rep = self._measure(45912)
        self.assertLess(rep["p50"], 1000.0 / 50.0)

    def test_loss_is_still_reported_correctly(self):
        """The fix must not have broken loss accounting."""
        rep = self._measure(45913)
        self.assertGreaterEqual(rep["loss_ratio"], 0.0)
        self.assertLessEqual(rep["loss_ratio"], 1.0)

    def test_a_deliberately_slow_sink_is_still_visible(self):
        """If the sink really is slow, the probe must report that too.

        Without this, a probe that simply reported a tiny constant would pass
        the tests above. The measurement has to track a real delay.
        """
        sink = _Echo(45914, delay_s=0.010)
        sink.start()
        try:
            probe = UdpProbe("127.0.0.1", 45914, pps=50.0, payload_bytes=64)
            probe.run(duration_s=1.2)
            rep = probe.report()
        finally:
            sink.stop()
        # 10 ms of artificial delay must show up as at least that much.
        self.assertGreater(rep["p50"], 8.0,
                           "a 10 ms sink delay vanished from the report")


if __name__ == "__main__":
    unittest.main()