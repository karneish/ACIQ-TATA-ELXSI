"""The capacity estimator must be fed DELIVERED load, not OFFERED load.

The defect this closes:

    estimator   22.39 Mbps   on a link that was 20 Mbps
    goodput     19.98 Mbps   -> the link was saturated
    netem queue filled      -> the latency tail appeared (p95 70.8 ms against a
                              p50 of 1.18 ms)

The estimator was fed `rx_bytes` on `veth-lan`, which is upstream of the netem
bottleneck at `veth-w`. A packet counted there has been *handed to* the queue,
not delivered by it, so everything the queue later dropped was already in the
figure. That is offered load.

Because bulk's ceiling is a fraction of the estimate, a 12% over-read became a
12% larger bulk share, which saturated the link, which filled the queue, which
produced the tail. The smoothing was not at fault: ALPHA_DOWN 0.6 against
ALPHA_UP 0.1 biases the estimate downward.

These tests are unit-level and kernel-free. They cannot prove the 22.39 becomes
20.0 on hardware -- that needs a run -- but they pin the parsing, the fallback
and the refusal to feed the estimator a zero.
"""
import unittest

from aciq.harness import Harness
from aciq.metrics import BottleneckDropSource

# Verbatim shapes from `tc -s qdisc show dev <bottleneck>` on this host.
NETEM_REAL = """qdisc netem 8001: root refcnt 2 limit 83
  Sent 82913218 bytes 59214 pkt (dropped 91, overlimits 1052 requeues 0)
  backlog 0b 0p requeues 0
"""

NETEM_QUEUEING = """qdisc netem 8001: root refcnt 2 limit 83
  Sent 82913218 bytes 59214 pkt (dropped 91, overlimits 0 requeues 0)
  backlog 495b 3p requeues 0
"""


def _runner(stdout):
    class R:
        returncode = 0

        def __call__(self, cmd, **kw):
            r = R()
            r.stdout, r.stderr = stdout, ""
            return r
    return R()


class TestDeliveredBytes(unittest.TestCase):
    def _src(self, out):
        return BottleneckDropSource(runner=_runner(out))

    def test_parses_delivered_bytes_from_real_output(self):
        self.assertEqual(self._src(NETEM_REAL).delivered_bytes(), 82913218)

    def test_parses_when_the_queue_is_backed_up(self):
        self.assertEqual(self._src(NETEM_QUEUEING).delivered_bytes(), 82913218)

    def test_absent_sent_field_returns_none_not_zero(self):
        """Zero would mean 'nothing got through' and collapse the estimate."""
        self.assertIsNone(self._src("qdisc pfifo 1: root\n").delivered_bytes())

    def test_never_returns_the_configured_rate(self):
        """The class exists so the estimator cannot read its own answer."""
        src = self._src("qdisc netem 8001: root limit 83 rate 20mbit\n"
                        "  Sent 5000 bytes 4 pkt\n")
        self.assertEqual(src.delivered_bytes(), 5000)
        self.assertNotIn("20", str(src.delivered_bytes()))

    def test_command_error_returns_none(self):
        class Boom:
            returncode = 1
            stdout = stderr = ""

            def __call__(self, cmd, **kw):
                return self
        self.assertIsNone(BottleneckDropSource(runner=Boom()).delivered_bytes())


class TestEstimatorPrefersDeliveredOverOffered(unittest.TestCase):
    def test_delivered_rate_is_computed_from_two_samples(self):
        h = Harness.__new__(Harness)
        h._bottleneck = None
        src = _runner(NETEM_REAL)
        vals = iter(["Sent 1000000 bytes 700 pkt", "Sent 3000000 bytes 2100 pkt"])
        h._bottleneck_drops = lambda: BottleneckDropSource(
            runner=lambda cmd, **kw: type("R", (), {
                "returncode": 0, "stdout": next(vals), "stderr": ""})())
        # First call has no previous sample, so it must report no reading.
        self.assertIsNone(h.bottleneck_delivered_mbps(1.0))
        # 2,000,000 bytes over 1 s = 16 Mbps.
        self.assertAlmostEqual(h.bottleneck_delivered_mbps(1.0), 16.0, places=6)

    def test_counter_going_backwards_reports_no_reading(self):
        """A qdisc replaced between ticks makes the delta meaningless."""
        h = Harness.__new__(Harness)
        vals = iter(["Sent 3000000 bytes", "Sent 1000000 bytes"])
        h._bottleneck_drops = lambda: BottleneckDropSource(
            runner=lambda cmd, **kw: type("R", (), {
                "returncode": 0, "stdout": next(vals), "stderr": ""})())
        h.bottleneck_delivered_mbps(1.0)
        self.assertIsNone(h.bottleneck_delivered_mbps(1.0),
                          "a backwards counter must not be read as capacity")

    def test_zero_dt_reports_no_reading(self):
        h = Harness.__new__(Harness)
        vals = iter(["Sent 1000000 bytes", "Sent 2000000 bytes"])
        h._bottleneck_drops = lambda: BottleneckDropSource(
            runner=lambda cmd, **kw: type("R", (), {
                "returncode": 0, "stdout": next(vals), "stderr": ""})())
        h.bottleneck_delivered_mbps(1.0)
        self.assertIsNone(h.bottleneck_delivered_mbps(0.0))


if __name__ == "__main__":
    unittest.main()