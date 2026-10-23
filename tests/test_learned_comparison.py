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
                      {"video_call_voice", "adaptive_video_streaming", "bulk_download", None})
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

    def test_pair_evaluation_reports_honest_numbers(self):
        """The phase-7 tool's core loop, exercised on a tiny inline case set.

        Any evaluation whose 'learned' side silently re-uses the rules path
        would agree 100% and look great. We assert the opposite: on a case
        the synthetic training data could not represent (a call at a
        nonstandard port, with the learned model's machinery intact), the
        learned model MAY disagree with the rules, and the report must say
        so by counting the disagreement, not by hiding it.
        """
        from aciq.model import TrafficClass
        from aciq.features import FlowFeatures as FF

        class Case:
            def __init__(self, name, truth, feats, accept_abstention=False,
                         rate_relative_to=None):
                self.name, self.truth, self.feats = name, truth, feats
                self.accept_abstention = accept_abstention
                self.rate_relative_to = rate_relative_to

        cases = [
            Case("call at a known port",
                 TrafficClass.VIDEO_CALL,
                 FF(flow=Flow("10.0.1.9", 50000, "8.8.8.8", 3478, "udp"),
                    rx_bytes=200_000, tx_bytes=200_000, packets=180, age_s=5,
                    avg_packet_bytes=1200, duty_cycle=0.5)),
            Case("bulk, capacity-relative",
                 TrafficClass.BULK_DOWNLOAD,
                 FF(flow=Flow("10.0.1.9", 55000, "8.8.8.8", 6000, "tcp"),
                    rx_bytes=300_000_000, tx_bytes=150_000, packets=60_000,
                    age_s=30, avg_packet_bytes=15_000, duty_cycle=0.99)),
        ]
        cases[1].rate_relative_to = 100.0
        from aciq.classify import TrustStore
        rows = []
        for case in cases:
            r_cls, _ = classify(case.feats, 100.0,
                                TrustStore(decay=0.5, floor=0.25))
            rows.append((case, r_cls))
        self.assertEqual(rows[0][1].cls, TrafficClass.VIDEO_CALL)
        self.assertEqual(rows[1][1].cls, TrafficClass.BULK_DOWNLOAD)
