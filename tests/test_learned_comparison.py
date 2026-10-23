from __future__ import annotations

import unittest

from aciq.classify import classify, finalise
from aciq.flowtrack import FlowFeatures
from aciq.learned import LogisticClassifier, compare
from aciq.model import Flow


def f(**kw):
    base = dict(flow=Flow("10.0.1.2", 40000, "203.0.113.9", 443, "tcp"),
                age_s=10.0, packets=1000, rx_bytes=10_000_000,
                avg_packet_bytes=1000)
    base.update(kw)
    return FlowFeatures(**base)


class TestLearnedClassifier(unittest.TestCase):
    def test_trains_deterministically(self):
        m1 = LogisticClassifier().fit()
        m2 = LogisticClassifier().fit()
        self.assertEqual(m1.weights, m2.weights)

    def test_produces_a_verdict_without_using_the_rule_path(self):
        m = LogisticClassifier().fit()
        res = m.predict(f(), 100.0)
        self.assertIn(res.cls.value if res.cls else None,
                      {"realtime_interactive", "adaptive_video", "bulk_transfer", None})
        self.assertIsInstance(res.confidence, float)

    def test_comparison_runs_against_the_rule_based_classifier(self):
        m = LogisticClassifier().fit()
        cases = [
            ("call", f(flow=Flow("10.0.1.2", 40000, "203.0.113.9", 5001, "udp"),
                       dscp=46, rx_bytes=240_000, tx_bytes=240_000, packets=200,
                       age_s=5, avg_packet_bytes=1200), 100.0),
            ("bulk", f(flow=Flow("10.0.1.2", 0, "203.0.113.9", 443, "tcp"),
                       rx_bytes=300_000_000, tx_bytes=200_000, packets=60000,
                       age_s=30, avg_packet_bytes=15000), 100.0),
        ]
        rows = compare(lambda feats, cap: finalise(classify(feats, cap)), m, cases)
        self.assertEqual(len(rows), 2)
        self.assertTrue(all(hasattr(r, "agree") for r in rows))


if __name__ == "__main__":
    unittest.main()
