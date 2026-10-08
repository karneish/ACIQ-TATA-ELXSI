"""M1 classifier tests.

Thresholds are grounded in measurements taken from the generators at the same
200 ms tick FlowTracker uses:

    generator   Mbps   duty   burstiness
    call        0.09   1.00   0.16
    video       4.69   1.00   0.47
    bulk       88.14   1.00   0.17

Duty cycle is 1.00 for all three, so it is recorded but never used to separate
classes. That is asserted here so the finding is not lost.
"""

from __future__ import annotations

import unittest

from aciq.classify import (
    ADAPTIVE_MIN_MBPS,
    BULK_MIN_CAPACITY_FRAC,
    DSCP_EF,
    EF_FAST_CONFLICT_CAPACITY_FRAC,
    EF_SLOW_CONFLICT_MBPS,
    INTERACTIVE_MAX_AVG_PACKET,
    MIN_AGE_S,
    MIN_CONFIDENCE,
    MIN_EF_TRUST,
    MIN_PACKETS,
    TRUST_DECAY_FACTOR,
    FlowFeatures,
    TrustStore,
    classify,
    finalise,
)
from aciq.model import Classification, Flow, TrafficClass

CAP = 100.0
CALL = Flow("10.0.1.2", 50000, "203.0.113.2", 3478, "udp")


def feats(**kw) -> FlowFeatures:
    base = dict(flow=CALL)
    base.update(kw)
    return FlowFeatures(**base)


def mature(**kw) -> FlowFeatures:
    """A flow with enough history to be judged, at a given Mbps rate."""
    rate = kw.pop("mbps", 1.0)
    f = dict(kw)
    f.setdefault("age_s", MIN_AGE_S + 1)
    f.setdefault("packets", MIN_PACKETS * 5)
    # size the byte count from the SAME age the features report, otherwise the
    # implied rate is inflated by the ratio of the two
    f.setdefault("rx_bytes", int(rate * 1e6 / 8 * f["age_s"]))
    return feats(**f)


class TestMeasuredBasis(unittest.TestCase):
    def test_duty_cycle_does_not_separate_classes(self):
        """Measured 1.00 for call, video and bulk alike. Any rule keyed on duty
        cycle would separate nothing."""
        for rate in (0.09, 4.69, 88.14):
            f = mature(mbps=rate, duty_cycle=1.0)
            self.assertEqual(f.duty_cycle, 1.0)
        # and the classifier must reach the right answer despite identical duty
        calls = classify(mature(mbps=0.09, flow=CALL, avg_packet_bytes=200))
        videos = classify(mature(mbps=4.69,
                                 flow=Flow("10.0.1.2", 1, "1.1.1.1", 443, "tcp")))
        bulks = classify(mature(mbps=88.14,
                                flow=Flow("10.0.1.2", 1, "1.1.1.1", 443, "tcp")))
        self.assertEqual(calls.cls, TrafficClass.INTERACTIVE)
        self.assertEqual(videos.cls, TrafficClass.ADAPTIVE)
        self.assertEqual(bulks.cls, TrafficClass.BULK)


class TestAdaptiveIsNowEmitted(unittest.TestCase):
    """The class that was previously never produced by the classifier."""

    def test_steady_tcp_below_bulk_threshold_is_adaptive(self):
        f = mature(mbps=4.69, flow=Flow("10.0.1.2", 1, "1.1.1.1", 443, "tcp"))
        c = classify(f)
        self.assertEqual(c.cls, TrafficClass.ADAPTIVE)
        self.assertEqual(c.tier, "B")

    def test_saturating_flow_is_bulk_not_adaptive(self):
        f = mature(mbps=88.14, flow=Flow("10.0.1.2", 1, "1.1.1.1", 443, "tcp"))
        self.assertEqual(classify(f).cls, TrafficClass.BULK)

    def test_very_low_rate_tcp_is_not_adaptive(self):
        """Below the absolute floor: too small to be a stream."""
        f = mature(mbps=0.4, flow=Flow("10.0.1.2", 1, "1.1.1.1", 443, "tcp"))
        self.assertNotEqual(classify(f).cls, TrafficClass.ADAPTIVE)


class TestCapacityRelativeThresholds(unittest.TestCase):
    """Thresholds are fractions of measured capacity, not absolute Mbps."""

    def test_same_flow_classifies_differently_by_capacity(self):
        flow = Flow("10.0.1.2", 1, "1.1.1.1", 443, "tcp")
        # 30 Mbps is bulk on a 40 Mbps link, adaptive on a 100 Mbps link
        self.assertEqual(
            classify(mature(mbps=30, flow=flow), capacity_mbps=40.0).cls,
            TrafficClass.BULK)
        self.assertEqual(
            classify(mature(mbps=30, flow=flow), capacity_mbps=100.0).cls,
            TrafficClass.ADAPTIVE)

    def test_fraction_boundaries(self):
        flow = Flow("10.0.1.2", 1, "1.1.1.1", 443, "tcp")
        at_bulk = BULK_MIN_CAPACITY_FRAC * CAP
        self.assertEqual(classify(mature(mbps=at_bulk, flow=flow)).cls,
                         TrafficClass.BULK)
        just_under = BULK_MIN_CAPACITY_FRAC * CAP - 0.01
        self.assertEqual(classify(mature(mbps=just_under, flow=flow)).cls,
                         TrafficClass.ADAPTIVE)

    def test_zero_capacity_does_not_crash(self):
        f = mature(mbps=10, flow=Flow("10.0.1.2", 1, "1.1.1.1", 443, "tcp"))
        self.assertIsNotNone(classify(f, capacity_mbps=0.0).cls)

    def test_media_classes_are_capacity_invariant(self):
        """The property that the absolute/relative split exists to protect.

        A purely relative ADAPTIVE threshold classified the 4.69 Mbps stream as
        UNCLASSIFIED at 1 Gbps, because 4.69 is 0.5% there. A 1080p stream on a
        fast line got no class at all. Call and video must not drift with link
        speed.
        """
        cases = [
            ("call", 0.09, "udp", 3478, TrafficClass.INTERACTIVE),
            ("video", 4.69, "tcp", 443, TrafficClass.ADAPTIVE),
        ]
        for name, mbps, proto, dport, expect in cases:
            for cap in (10.0, 100.0, 1000.0):
                f = mature(mbps=mbps,
                           flow=Flow("10.0.1.2", 50000, "203.0.113.2", dport, proto))
                self.assertEqual(finalise(classify(f, capacity_mbps=cap)).cls,
                                 expect, f"{name} at {cap} Mbps")

    def test_bulk_class_is_deliberately_capacity_relative(self):
        """The flip side, asserted so the asymmetry is intentional and visible:
        88 Mbps is a hog on a 100 Mbps link and a nobody on a gigabit, so it
        stops being BULK as the link grows. This is the design, not a bug."""
        flow = Flow("10.0.1.2", 50000, "203.0.113.2", 443, "tcp")
        self.assertEqual(classify(mature(mbps=88.14, flow=flow),
                                  capacity_mbps=100.0).cls,
                         TrafficClass.BULK)
        self.assertEqual(classify(mature(mbps=88.14, flow=flow),
                                  capacity_mbps=1000.0).cls,
                         TrafficClass.ADAPTIVE)

    def test_bulk_threshold_is_relative_adaptive_is_absolute(self):
        flow = Flow("10.0.1.2", 1, "1.1.1.1", 443, "tcp")
        # 300 Mbps: adaptive on 1 Gbps, bulk on a 1 Gbps->no, on 500 Mbps link
        self.assertEqual(classify(mature(mbps=300, flow=flow),
                                  capacity_mbps=1000.0).cls,
                         TrafficClass.ADAPTIVE)
        self.assertEqual(classify(mature(mbps=300, flow=flow),
                                  capacity_mbps=500.0).cls,
                         TrafficClass.BULK)
        # a 0.4 Mbps stream is below the absolute floor at any capacity
        self.assertNotEqual(classify(mature(mbps=0.4, flow=flow),
                                     capacity_mbps=1000.0).cls,
                            TrafficClass.ADAPTIVE)


class TestVideoCallNotBroken(unittest.TestCase):
    """Regression guard. The old rule was `avg_packet <= 600`, which excluded a
    720p video call (1200-1500 byte packets)."""

    def test_large_packet_video_call_is_interactive_when_marked(self):
        f = mature(dscp=DSCP_EF, avg_packet_bytes=1400, mbps=2.0)
        c = classify(f)
        self.assertEqual(c.cls, TrafficClass.INTERACTIVE)

    def test_large_packet_interactive_udp_qualifies(self):
        f = mature(flow=Flow("10.0.1.2", 1, "1.1.1.1", 40000, "udp"),
                   avg_packet_bytes=1400, mbps=2.0)
        self.assertEqual(classify(f).cls, TrafficClass.INTERACTIVE)

    def test_upper_bound_is_mtu_sized_not_600(self):
        self.assertGreater(INTERACTIVE_MAX_AVG_PACKET, 1300)


class TestDscpConflictJudgedOnRate(unittest.TestCase):
    """Not on packet size — that would demote real video calls."""

    def test_ef_at_near_zero_rate_conflicts(self):
        """Below the absolute floor for real media."""
        c = classify(mature(dscp=DSCP_EF, avg_packet_bytes=200, mbps=0.005))
        self.assertIsNone(c.cls)
        self.assertIn("conflict", c.evidence)

    def test_ef_saturating_the_link_is_demoted_to_bulk(self):
        """The actual evasion: set one DSCP byte on a torrent and inherit
        interactive weight. Must NOT come back INTERACTIVE."""
        c = classify(mature(dscp=DSCP_EF, avg_packet_bytes=1400, mbps=90.0))
        self.assertEqual(c.cls, TrafficClass.BULK)
        self.assertIn("conflict", c.evidence)

    def test_fast_conflict_survives_finalise(self):
        """Confidence reflects certainty about the RATE, not about trust. A
        saturating flow is bulk however little the source is trusted, so it must
        not decay to UNCLASSIFIED and lose its class."""
        c = finalise(classify(mature(dscp=DSCP_EF, avg_packet_bytes=1400,
                                      mbps=90.0)))
        self.assertEqual(c.cls, TrafficClass.BULK)

    def test_fast_conflict_still_decays_trust(self):
        """Even though confidence holds, the source is believed less next time."""
        t = TrustStore()
        f = mature(dscp=DSCP_EF, avg_packet_bytes=1400, mbps=90.0)
        classify(f, trust=t)
        self.assertLess(t.trust(f.flow.src), 1.0)

    def test_legitimate_call_at_measured_rate_is_interactive(self):
        """Regression guard for the measured 0.09 Mbps call. An earlier 2%-of-
        capacity rule wrongly flagged this as a conflict."""
        c = classify(mature(dscp=DSCP_EF, avg_packet_bytes=200, mbps=0.09))
        self.assertEqual(c.cls, TrafficClass.INTERACTIVE)

    def test_legitimate_video_call_rate_is_interactive(self):
        c = classify(mature(dscp=DSCP_EF, avg_packet_bytes=1400, mbps=2.0))
        self.assertEqual(c.cls, TrafficClass.INTERACTIVE)

    def test_slow_floor_is_absolute_not_capacity_relative(self):
        """A call's rate does not scale with link speed, so neither may the floor."""
        slow = mature(dscp=DSCP_EF, avg_packet_bytes=200, mbps=0.09)
        self.assertEqual(classify(slow, capacity_mbps=100.0).cls,
                         TrafficClass.INTERACTIVE)
        self.assertEqual(classify(slow, capacity_mbps=1000.0).cls,
                         TrafficClass.INTERACTIVE)
        self.assertEqual(classify(slow, capacity_mbps=10.0).cls,
                         TrafficClass.INTERACTIVE)

    def test_fast_conflict_is_capacity_relative(self):
        """Saturation IS relative: 90 Mbps is fine on a gigabit link."""
        f = mature(dscp=DSCP_EF, avg_packet_bytes=1400, mbps=90.0)
        self.assertEqual(classify(f, capacity_mbps=100.0).cls,
                         TrafficClass.BULK)
        self.assertEqual(classify(f, capacity_mbps=1000.0).cls,
                         TrafficClass.INTERACTIVE)

    def test_conflict_thresholds(self):
        self.assertAlmostEqual(EF_SLOW_CONFLICT_MBPS, 0.010)
        self.assertAlmostEqual(EF_FAST_CONFLICT_CAPACITY_FRAC,
                               BULK_MIN_CAPACITY_FRAC)

    def test_immature_ef_flow_is_not_judged_a_conflict(self):
        """A flow that just started has no rate yet; calling it a conflict
        would penalise every new call."""
        f = feats(dscp=DSCP_EF, avg_packet_bytes=200, packets=2, age_s=0.1,
                  rx_bytes=100)
        c = classify(f)
        self.assertEqual(c.cls, TrafficClass.INTERACTIVE)


class TestTrustDecay(unittest.TestCase):
    def test_repeated_misclaim_lowers_confidence(self):
        t = TrustStore()
        f = mature(dscp=DSCP_EF, avg_packet_bytes=200, mbps=0.005)
        first = classify(f, trust=t)
        for _ in range(3):
            last = classify(f, trust=t)
        self.assertLess(last.confidence, first.confidence)
        self.assertIsNone(last.cls)

    def test_trust_floors(self):
        t = TrustStore()
        for _ in range(50):
            t.record_miss("10.0.1.2")
        self.assertGreaterEqual(t.trust("10.0.1.2"), MIN_EF_TRUST)

    def test_decay_factor_is_applied_once(self):
        t = TrustStore()
        self.assertAlmostEqual(t.record_miss("a"), TRUST_DECAY_FACTOR)
        self.assertAlmostEqual(t.record_miss("a"), TRUST_DECAY_FACTOR ** 2)

    def test_trust_is_per_source(self):
        t = TrustStore()
        for _ in range(4):
            t.record_miss("10.0.1.2")
        self.assertEqual(t.trust("10.0.1.9"), 1.0)

    def test_stats_recorded(self):
        t = TrustStore()
        t.record_claim("a"); t.record_miss("a")
        s = t.stats("a")
        self.assertEqual(s["ef_claims"], 1)
        self.assertEqual(s["ef_misses"], 1)

    def test_honest_flow_does_not_lose_trust(self):
        t = TrustStore()
        classify(mature(dscp=DSCP_EF, avg_packet_bytes=200, mbps=2.0), trust=t)
        self.assertEqual(t.trust(CALL.src), 1.0)


class TestUserCorrection(unittest.TestCase):
    """Tata requires correction of misclassification."""

    def test_correction_overrides_inference(self):
        f = mature(mbps=88.14, flow=Flow("10.0.1.2", 1, "1.1.1.1", 443, "tcp"),
                   correction=TrafficClass.INTERACTIVE)
        c = classify(f)
        self.assertEqual(c.cls, TrafficClass.INTERACTIVE)
        self.assertEqual(c.confidence, 1.0)
        self.assertEqual(c.tier, "X")

    def test_correction_overrides_a_udf443_guess(self):
        f = mature(flow=Flow("10.0.1.2", 1, "1.1.1.1", 443, "udp"),
                   correction=TrafficClass.INTERACTIVE, avg_packet_bytes=800)
        self.assertEqual(classify(f).cls, TrafficClass.INTERACTIVE)


class TestImmatureFlows(unittest.TestCase):
    def test_new_flow_is_not_guessed(self):
        c = classify(feats(dscp=None, avg_packet_bytes=300, packets=1, age_s=0.2))
        self.assertIsNone(c.cls)
        self.assertIn("immature", c.evidence)

    def test_immature_is_a_documented_cost(self):
        """Every unmarked flow spends its first ~2 s unclassified, which in
        enforcement means sitting in the default class. Stated as a cost."""
        c = classify(feats(packets=3, age_s=0.5, avg_packet_bytes=300))
        self.assertIsNone(c.cls)


class TestHonestGaps(unittest.TestCase):
    def test_udp443_without_dscp_stays_unclassified(self):
        """QUIC: statistically media-like, but it also carries downloads.
        Classifying it on packet size alone would be a guess."""
        f = mature(flow=Flow("10.0.1.2", 1, "1.1.1.1", 443, "udp"),
                   avg_packet_bytes=800)
        c = classify(f)
        self.assertIsNone(c.cls)
        self.assertIn("ambiguous", c.evidence)

    def test_large_udp443_still_unclassified(self):
        f = mature(flow=Flow("10.0.1.2", 1, "1.1.1.1", 443, "udp"),
                   avg_packet_bytes=1400)
        self.assertIsNone(classify(f).cls)

    def test_udp443_below_adaptive_floor_is_unclassified(self):
        f = mature(flow=Flow("10.0.1.2", 1, "1.1.1.1", 443, "udp"),
                   avg_packet_bytes=800, mbps=0.5)
        self.assertIsNone(classify(f).cls)

    def test_small_non443_udp_is_interactive(self):
        """RTP media is what the heuristic is actually for."""
        f = mature(flow=Flow("10.0.1.2", 1, "1.1.1.1", 5004, "udp"),
                   avg_packet_bytes=800, mbps=2.0)
        self.assertEqual(classify(f).cls, TrafficClass.INTERACTIVE)

    def test_finalise_demotes_below_threshold(self):
        """A class below MIN_CONFIDENCE must never reach enforcement."""
        c = Classification(flow=CALL, cls=TrafficClass.INTERACTIVE,
                           confidence=0.3, tier="B", evidence="weak")
        self.assertIsNone(finalise(c).cls)
        self.assertIn(f"below {MIN_CONFIDENCE}", finalise(c).evidence)

    def test_finalise_keeps_a_confident_class(self):
        c = Classification(flow=CALL, cls=TrafficClass.BULK,
                           confidence=0.9, tier="B", evidence="saturating")
        self.assertEqual(finalise(c).cls, TrafficClass.BULK)


class TestNoGeneratorPorts(unittest.TestCase):
    def test_generator_ports_are_not_in_the_rule_tables(self):
        from aciq.classify import BULK_PORTS, INTERACTIVE_PORTS
        for p in (5001, 5002, 5003, 5004):
            self.assertNotIn(p, INTERACTIVE_PORTS)
            self.assertNotIn(p, BULK_PORTS)


if __name__ == "__main__":
    unittest.main()