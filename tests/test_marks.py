"""Tests for the mark encoding.

Pure arithmetic, so these run without root or netlink. The testbed only needs
to prove the kernel honours what this layout specifies -- it should not be
discovering field positions at the same time.
"""

from __future__ import annotations

import unittest

from aciq.marks import (
    CLASS_ADAPTIVE,
    CLASS_BULK,
    CLASS_INTERACTIVE,
    CLASS_LEASED,
    CLASS_MASK,
    CLASS_UNCLASSIFIED,
    CONF_HIGH,
    CONF_MASK,
    CONF_LOW,
    CONF_MEDIUM,
    CONF_NONE,
    LEASE_MASK,
    MARK_RESERVED_MASK,
    REASON_BEHAVIOUR,
    REASON_CORRECTION,
    REASON_DSCP,
    REASON_MASK,
    REASON_BY_TIER,
    REASON_NONE,
    SEEN_BIT,
    MarkEncodingError,
    bucket_confidence,
    class_handle,
    decode,
    encode,
    encode_for_traffic,
    is_untouched,
)
from aciq.model import TrafficClass


class TestLayout(unittest.TestCase):
    def test_fields_do_not_overlap(self):
        """Every field must occupy its own bits. Overlap would let a lease id
        change the class, which no gate check would catch."""
        f = encode(CLASS_LEASED, seen=True, confidence=0.9,
                   reason=REASON_DSCP, lease_id=7)
        d = decode(f)
        self.assertEqual(d.class_id, CLASS_LEASED)
        self.assertTrue(d.seen)
        self.assertEqual(d.confidence, CONF_HIGH)
        self.assertEqual(d.reason, REASON_DSCP)
        self.assertEqual(d.lease_id, 7)

    def test_reserved_bits_are_always_zero(self):
        for cid in (CLASS_UNCLASSIFIED, CLASS_INTERACTIVE, CLASS_ADAPTIVE,
                    CLASS_BULK, CLASS_LEASED):
            for conf in (0.0, 0.55, 0.79, 0.95):
                for rsn in (REASON_NONE, REASON_DSCP, REASON_BEHAVIOUR,
                            REASON_CORRECTION):
                    m = encode(cid, confidence=conf, reason=rsn,
                               lease_id=255 if cid == CLASS_LEASED else 0)
                    self.assertEqual(m & MARK_RESERVED_MASK, 0,
                                     f"reserved bits set for {cid}/{conf}/{rsn}")

    def test_lease_id_uses_the_highest_defined_bit(self):
        m = encode(CLASS_LEASED, lease_id=0xFF)
        self.assertEqual(m & LEASE_MASK, 0x1FE00)
        self.assertEqual(decode(m).lease_id, 0xFF)

    def test_class_id_fits_four_bits(self):
        self.assertEqual(CLASS_MASK, 0xF)
        self.assertEqual(CLASS_LEASED, 4)


class TestSeenBit(unittest.TestCase):
    """The bit that distinguishes 'decided unclassified' from 'never looked'."""

    def test_zero_is_untouched(self):
        self.assertTrue(is_untouched(0))
        self.assertTrue(decode(0).is_untouched)

    def test_unclassified_with_seen_is_not_untouched(self):
        m = encode(CLASS_UNCLASSIFIED, seen=True, reason=REASON_BEHAVIOUR)
        self.assertEqual(decode(m).class_id, CLASS_UNCLASSIFIED)
        self.assertFalse(is_untouched(m),
                         "an examined-but-unclassified flow must not fall "
                         "through to the DSCP-EF filter")

    def test_the_two_cases_differ(self):
        """This is the whole reason the bit exists."""
        untouched = 0
        examined = encode(CLASS_UNCLASSIFIED, seen=True)
        self.assertNotEqual(untouched, examined)
        self.assertTrue(is_untouched(untouched))
        self.assertFalse(is_untouched(examined))

    def test_unseen_encodes_to_zero(self):
        self.assertEqual(encode(CLASS_INTERACTIVE, seen=False), 0)

    def test_unseen_discards_confidence_and_reason(self):
        """Confidence describes a decision never made. Encoding it anyway would
        set those bits on a flow nothing knows about, and is_untouched() would
        disagree with the caller."""
        m = encode(CLASS_INTERACTIVE, seen=False, confidence=0.95,
                   reason=REASON_DSCP)
        self.assertEqual(m, 0)
        self.assertTrue(is_untouched(m))

    def test_layout_tiles_bits_0_to_16_with_no_gap(self):
        """Bit 16 once belonged to neither the lease field nor the reserved
        field, because LEASE_MASK was 0xFE00 (bits 9-15) while the docs claimed
        bits 9-16. lease ids <= 127 could not see the bug."""
        covered = (CLASS_MASK | SEEN_BIT | CONF_MASK | REASON_MASK | LEASE_MASK)
        self.assertEqual(covered, 0x1FFFF, f"layout covers 0x{covered:05x}")
        self.assertEqual(MARK_RESERVED_MASK, 0xFFFE0000)
        self.assertEqual(covered | MARK_RESERVED_MASK, 0xFFFFFFFF)

    def test_lease_id_255_occupies_bit_16(self):
        m = encode(CLASS_LEASED, lease_id=255)
        self.assertTrue(m & (1 << 16), "bit 16 must be reachable")
        self.assertEqual(decode(m).lease_id, 255)


class TestConfidenceBuckets(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(bucket_confidence(0.0), CONF_NONE)
        self.assertEqual(bucket_confidence(0.01), CONF_LOW)
        self.assertEqual(bucket_confidence(0.59), CONF_LOW)
        self.assertEqual(bucket_confidence(0.60), CONF_MEDIUM)
        self.assertEqual(bucket_confidence(0.79), CONF_MEDIUM)
        self.assertEqual(bucket_confidence(0.80), CONF_HIGH)
        self.assertEqual(bucket_confidence(1.0), CONF_HIGH)

    def test_boundary_belongs_to_the_higher_bucket(self):
        self.assertEqual(bucket_confidence(0.60), bucket_confidence(0.6000001))
        self.assertEqual(bucket_confidence(0.80), bucket_confidence(0.8000001))

    def test_all_buckets_round_trip(self):
        for conf in (0.0, 0.3, 0.65, 0.99):
            m = encode(CLASS_ADAPTIVE, confidence=conf)
            self.assertEqual(decode(m).confidence, bucket_confidence(conf))

    def test_confidence_survives_with_a_reason(self):
        m = encode(CLASS_BULK, confidence=0.95, reason=REASON_BEHAVIOUR)
        self.assertEqual(decode(m).confidence, CONF_HIGH)
        self.assertEqual(decode(m).reason, REASON_BEHAVIOUR)


class TestReasons(unittest.TestCase):
    def test_tiers_map_to_reasons(self):
        self.assertEqual(REASON_BY_TIER["A"], REASON_DSCP)
        self.assertEqual(REASON_BY_TIER["B"], REASON_BEHAVIOUR)
        self.assertEqual(REASON_BY_TIER["C"], REASON_BEHAVIOUR)
        self.assertEqual(REASON_BY_TIER["X"], REASON_CORRECTION)

    def test_every_tier_the_classifier_emits_has_a_reason(self):
        for tier in ("A", "B", "C", "X"):
            self.assertIn(tier, REASON_BY_TIER)

    def test_reason_names(self):
        m = encode(CLASS_INTERACTIVE, reason=REASON_DSCP)
        self.assertEqual(decode(m).reason_name, "dscp")


class TestValidation(unittest.TestCase):
    """Invalid input must raise, not truncate. A truncated class id sends traffic
    to a class nobody configured and nothing notices."""

    def test_reserved_class_id_rejected(self):
        for cid in (5, 9, 15):
            with self.assertRaises(MarkEncodingError):
                encode(cid)

    def test_class_id_above_nibble_rejected(self):
        with self.assertRaises(MarkEncodingError):
            encode(16)
        with self.assertRaises(MarkEncodingError):
            encode(-1)

    def test_reason_out_of_range_rejected(self):
        with self.assertRaises(MarkEncodingError):
            encode(CLASS_BULK, reason=4)

    def test_lease_id_out_of_range_rejected(self):
        with self.assertRaises(MarkEncodingError):
            encode(CLASS_LEASED, lease_id=256)
        with self.assertRaises(MarkEncodingError):
            encode(CLASS_LEASED, lease_id=-1)

    def test_lease_on_a_non_lease_class_rejected(self):
        with self.assertRaises(MarkEncodingError):
            encode(CLASS_INTERACTIVE, lease_id=3)

    def test_decode_out_of_range_rejected(self):
        for bad in (-1, 1 << 32):
            with self.assertRaises(MarkEncodingError):
                decode(bad)

    def test_seen_bit_constant(self):
        self.assertEqual(SEEN_BIT, 0x10)


class TestTrafficClassMapping(unittest.TestCase):
    def test_all_three_classes_map(self):
        for tc in TrafficClass:
            if tc is None:
                continue
            d = decode(encode_for_traffic(tc, confidence=0.9))
            self.assertTrue(d.seen)

    def test_none_means_examined_and_unclassified(self):
        d = decode(encode_for_traffic(None, confidence=0.4,
                                      reason=REASON_BEHAVIOUR))
        self.assertEqual(d.class_id, CLASS_UNCLASSIFIED)
        self.assertTrue(d.seen)

    def test_distinct_class_ids(self):
        ids = {decode(encode_for_traffic(tc)).class_id
               for tc in TrafficClass if tc is not None}
        self.assertEqual(len(ids), 4, "all four TrafficClass values including LEASED must have distinct ids")


class TestClassHandle(unittest.TestCase):
    """`tc fw` must match the class field alone."""

    def test_handle_masks_to_class_bits(self):
        self.assertEqual(class_handle(CLASS_INTERACTIVE), "0x01/0x0f")
        self.assertEqual(class_handle(CLASS_BULK), "0x03/0x0f")
        self.assertEqual(class_handle(CLASS_UNCLASSIFIED), "0x00/0x0f")

    def test_handle_ignores_confidence_reason_and_lease(self):
        """Two marks differing only in confidence/reason/lease must produce the
        SAME handle, or each combination needs its own filter."""
        a = class_handle(CLASS_INTERACTIVE)
        for conf, rsn, lease in ((0.95, REASON_DSCP, 0),
                                 (0.30, REASON_BEHAVIOUR, 0),
                                 (0.70, REASON_CORRECTION, 0)):
            m = encode(CLASS_INTERACTIVE, confidence=conf, reason=rsn,
                       lease_id=lease)
            self.assertEqual(m & CLASS_MASK, CLASS_INTERACTIVE)
            self.assertEqual(a, "0x01/0x0f")

    def test_reserved_class_has_no_handle(self):
        with self.assertRaises(MarkEncodingError):
            class_handle(7)


class TestRoundTrip(unittest.TestCase):
    def test_exhaustive_over_defined_fields(self):
        for cid in (CLASS_UNCLASSIFIED, CLASS_INTERACTIVE, CLASS_ADAPTIVE,
                    CLASS_BULK, CLASS_LEASED):
            for seen in (True, False):
                for conf in (0.0, 0.55, 0.9):
                    for rsn in (REASON_NONE, REASON_DSCP, REASON_BEHAVIOUR,
                                REASON_CORRECTION):
                        lease = (cid * 7 % 256) if cid == CLASS_LEASED else 0
                        m = encode(cid, seen=seen, confidence=conf, reason=rsn,
                                   lease_id=lease)
                        d = decode(m)
                        self.assertEqual(d.seen, seen)
                        self.assertEqual(d.raw, m)
                        if seen:
                            self.assertEqual(d.class_id, cid)
                            self.assertEqual(d.reason, rsn)
                            self.assertEqual(d.confidence,
                                             bucket_confidence(conf))
                            self.assertEqual(d.lease_id, lease)
                        else:
                            self.assertEqual(m, 0)


if __name__ == "__main__":
    unittest.main()