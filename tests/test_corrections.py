"""Tests for the correction layer.

The test this file exists to make possible is
`TestCorrectionChangesADecision`: before corrections existed, `classify()`
carried a `correction` field that nothing could ever set, so "allow correction
of misclassification" was unimplemented despite being a stated requirement.

Everything here is filesystem-only: no root, no netlink, no network.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from aciq.classify import FlowFeatures, classify, finalise
from aciq.corrections import (
    SCHEMA_VERSION,
    Correction,
    CorrectionError,
    CorrectionStore,
    parse_correction,
)
from aciq.model import Flow, TrafficClass

SSH = Flow("10.0.1.2", 40000, "203.0.113.9", 22, "tcp")
CALL = Flow("10.0.1.2", 40001, "203.0.113.9", 3478, "udp")


class StoreCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "corrections.jsonl"
        self.addCleanup(self._tmp.cleanup)

    def store(self, now=None, ttl_s=86400.0) -> CorrectionStore:
        return CorrectionStore(self.path, ttl_s=ttl_s, now=now)


class TestRecording(StoreCase):
    def test_records_a_port_scoped_correction(self):
        s = self.store()
        c = s.record(SSH, TrafficClass.BULK, reason="git clone", by="me")
        self.assertEqual(c.cls, TrafficClass.BULK)
        self.assertEqual(c.dport, 22)
        self.assertEqual(c.scope, "port")
        self.assertEqual(c.recorded_by, "me")

    def test_records_host_scope_when_dport_is_none(self):
        s = self.store()
        c = s.record(SSH, TrafficClass.INTERACTIVE, dport=None)
        self.assertIsNone(c.dport)
        self.assertEqual(c.scope, "host")

    def test_file_is_append_only(self):
        """A correction is a statement about a class of traffic, not a snapshot.
        Overwriting would destroy the record an accuracy claim is audited
        against."""
        s = self.store()
        s.record(SSH, TrafficClass.BULK)
        s.record(CALL, TrafficClass.INTERACTIVE)
        s.record(SSH, TrafficClass.ADAPTIVE, dport=None)
        lines = [l for l in self.path.read_text().splitlines() if l.strip()]
        self.assertEqual(len(lines), 3)

    def test_recorrecting_the_same_key_appends_and_last_wins(self):
        s = self.store(now=1000.0)
        s.record(SSH, TrafficClass.BULK, reason="first")
        s2 = self.store(now=1001.0)
        s2.record(SSH, TrafficClass.ADAPTIVE, reason="second")
        c = s2.lookup(SSH)
        self.assertEqual(c.cls, TrafficClass.ADAPTIVE)
        self.assertEqual(c.reason, "second")
        # and the original statement is still on disk
        lines = [l for l in self.path.read_text().splitlines() if l.strip()]
        self.assertEqual(len(lines), 2)

    def test_creates_the_directory(self):
        deep = self.path.parent / "a" / "b" / "corrections.jsonl"
        CorrectionStore(deep).record(SSH, TrafficClass.BULK)
        self.assertTrue(deep.exists())

    def test_refuses_a_correction_with_no_class(self):
        with self.assertRaises(CorrectionError):
            self.store().record(SSH, None)

    def test_ttl_is_applied(self):
        s = self.store(now=1000.0)
        c = s.record(SSH, TrafficClass.BULK, ttl_s=60)
        self.assertEqual(c.expires_at, 1060.0)

    def test_ttl_none_never_expires(self):
        c = self.store(now=1000.0).record(SSH, TrafficClass.BULK, ttl_s=None)
        self.assertIsNone(c.expires_at)


class TestLookup(StoreCase):
    def test_port_scoped_match(self):
        s = self.store()
        s.record(SSH, TrafficClass.BULK)
        self.assertEqual(s.lookup(SSH).cls, TrafficClass.BULK)

    def test_host_scoped_matches_any_port(self):
        """A host-scoped correction must not compare the port, or it stops
        applying the moment the source port changes -- which is every reconnect.
        """
        s = self.store()
        s.record(SSH, TrafficClass.INTERACTIVE, dport=None)
        for dport in (22, 443, 8080):
            f = Flow("10.0.1.2", 5000, "203.0.113.9", dport, "tcp")
            self.assertIsNotNone(s.lookup(f), f"port {dport} should match")

    def test_port_scoped_does_not_leak_to_other_ports(self):
        s = self.store()
        s.record(SSH, TrafficClass.BULK)
        other = Flow("10.0.1.2", 5000, "203.0.113.9", 23, "tcp")
        self.assertIsNone(s.lookup(other))

    def test_no_match_returns_none(self):
        s = self.store()
        s.record(SSH, TrafficClass.BULK)
        self.assertIsNone(s.lookup(CALL))

    def test_source_port_is_never_part_of_the_key(self):
        """Two connections to the same service differ only in sport."""
        s = self.store()
        s.record(SSH, TrafficClass.BULK)
        reconnect = Flow("10.0.1.2", 99999, "203.0.113.9", 22, "tcp")
        self.assertEqual(s.lookup(reconnect).cls, TrafficClass.BULK)

    def test_proto_must_match(self):
        s = self.store()
        s.record(Flow("10.0.1.2", 1, "203.0.113.9", 22, "tcp"),
                 TrafficClass.BULK)
        udp = Flow("10.0.1.2", 1, "203.0.113.9", 22, "udp")
        self.assertIsNone(s.lookup(udp))

    def test_hits_and_misses_counted(self):
        s = self.store()
        s.record(SSH, TrafficClass.BULK)
        s.lookup(SSH)
        s.lookup(CALL)
        self.assertEqual(s.stats.hits, 1)
        self.assertEqual(s.stats.misses, 1)

    def test_specific_beats_host_when_equally_recent(self):
        """An exact port correction is the more deliberate statement."""
        s = self.store(now=1000.0)
        s.record(SSH, TrafficClass.BULK, dport=None, reason="host-wide")
        s.record(SSH, TrafficClass.INTERACTIVE, dport=22, reason="just ssh")
        c = s.lookup(SSH)
        self.assertEqual(c.cls, TrafficClass.INTERACTIVE)
        self.assertEqual(c.reason, "just ssh")

    def test_newer_host_correction_beats_older_port_correction(self):
        """Re-correcting the whole host is a deliberate new intent, so the later
        statement wins even though it is less specific."""
        s = self.store(now=1000.0)
        s.record(SSH, TrafficClass.INTERACTIVE, dport=22, reason="just ssh")
        s2 = self.store(now=2000.0)
        s2.record(SSH, TrafficClass.BULK, dport=None, reason="host-wide, all bulk")
        c = s2.lookup(SSH)
        self.assertEqual(c.cls, TrafficClass.BULK)
        self.assertEqual(c.reason, "host-wide, all bulk")


class TestExpiry(StoreCase):
    def test_expired_correction_stops_applying(self):
        """A correction describes a hypothesis about traffic that will change.
        One that outlives its flow is worse than none."""
        s = self.store(now=1000.0)
        s.record(SSH, TrafficClass.BULK, ttl_s=60)
        live = self.store(now=1050.0)
        self.assertIsNotNone(live.lookup(SSH))
        dead = self.store(now=1100.0)
        self.assertIsNone(dead.lookup(SSH))

    def test_expiry_is_counted(self):
        """So a stale correction is visible rather than merely gone."""
        s = self.store(now=1000.0)
        s.record(SSH, TrafficClass.BULK, ttl_s=60)
        later = self.store(now=2000.0)
        later.lookup(SSH)
        self.assertEqual(later.stats.expired, 1)
        self.assertEqual(later.stats.hits, 0)

    def test_exactly_at_expiry_is_expired(self):
        s = self.store(now=1000.0)
        s.record(SSH, TrafficClass.BULK, ttl_s=60)
        self.assertIsNone(self.store(now=1060.0).lookup(SSH))


class TestMalformed(StoreCase):
    """One bad line must not stop the classifier working."""

    def _write(self, *lines: str):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("\n".join(lines) + "\n")

    def test_bad_json_is_skipped_not_fatal(self):
        self._write("{not json",
                    json.dumps({"src": "a", "dst": "b", "proto": "tcp",
                                "dport": 22, "cls": "bulk_transfer"}))
        s = self.store()
        self.assertEqual(len(s), 1)
        self.assertEqual(s.stats.skipped_malformed, 1)

    def test_missing_field_is_skipped(self):
        self._write(json.dumps({"src": "a", "dst": "b", "proto": "tcp"}))
        s = self.store()
        self.assertEqual(len(s), 0)
        self.assertEqual(s.stats.skipped_malformed, 1)

    def test_unknown_class_is_skipped(self):
        """A typo must not be routed as a class; it must be refused loudly."""
        self._write(json.dumps({"src": "a", "dst": "b", "proto": "tcp",
                                "dport": 22, "cls": "realtime"}))
        s = self.store()
        self.assertEqual(len(s), 0)
        self.assertEqual(s.stats.skipped_malformed, 1)

    def test_out_of_range_port_is_skipped(self):
        self._write(json.dumps({"src": "a", "dst": "b", "proto": "tcp",
                                "dport": 70000, "cls": "bulk_transfer"}))
        s = self.store()
        self.assertEqual(len(s), 0)

    def test_bad_schema_version_is_skipped(self):
        self._write(json.dumps({"src": "a", "dst": "b", "proto": "tcp",
                                "dport": 22, "cls": "bulk_transfer",
                                "schema": 999}))
        s = self.store()
        self.assertEqual(len(s), 0)
        self.assertEqual(s.stats.skipped_malformed, 1)

    def test_comments_and_blank_lines_ignored(self):
        self._write("", "# a note", "   ",
                    json.dumps({"src": "a", "dst": "b", "proto": "tcp",
                                "dport": 22, "cls": "bulk_transfer"}))
        s = self.store()
        self.assertEqual(len(s), 1)
        self.assertEqual(s.stats.skipped_malformed, 0)

    def test_malformed_line_numbers_are_recorded(self):
        self._write("{bad", "{also bad")
        s = self.store()
        self.assertEqual(s.stats.malformed_lines, ["line 1", "line 2"])

    def test_missing_file_is_not_an_error(self):
        s = CorrectionStore(self.path.parent / "absent.jsonl")
        self.assertEqual(len(s), 0)


class TestValidation(unittest.TestCase):
    def _line(self, **kw):
        base = {"src": "a", "dst": "b", "proto": "tcp", "dport": 22,
                "cls": "bulk_transfer"}
        base.update(kw)
        return json.dumps(base)

    def test_valid_line_parses(self):
        c = parse_correction(self._line())
        self.assertEqual(c.cls, TrafficClass.BULK)
        self.assertEqual(c.schema, SCHEMA_VERSION)

    def test_all_classes_accepted(self):
        for tc in TrafficClass:
            c = parse_correction(self._line(cls=tc.value))
            self.assertEqual(c.cls, tc)

    def test_proto_case_normalised(self):
        self.assertEqual(parse_correction(self._line(proto="TCP")).proto, "tcp")

    def test_bool_is_not_an_acceptable_port(self):
        """bool is an int subclass in Python, so `dport: true` would otherwise
        silently become port 1."""
        with self.assertRaises(CorrectionError):
            parse_correction(self._line(dport=True))

    def test_null_port_is_host_scope(self):
        self.assertEqual(parse_correction(self._line(dport=None)).scope, "host")

    def test_not_an_object_is_rejected(self):
        with self.assertRaises(CorrectionError):
            parse_correction("[1,2,3]")

    def test_missing_fields_named_in_the_error(self):
        with self.assertRaises(CorrectionError) as cm:
            parse_correction(json.dumps({"src": "a"}))
        self.assertIn("dst", str(cm.exception))

    def test_error_lists_the_valid_classes(self):
        with self.assertRaises(CorrectionError) as cm:
            parse_correction(self._line(cls="nope"))
        self.assertIn("bulk_transfer", str(cm.exception))


class TestCorrectionChangesADecision(unittest.TestCase):
    """The requirement itself: a correction must demonstrably change a later
    decision. `classify()` accepted `correction` all along; nothing could set it.
    """

    def _features(self, flow: Flow, **kw):
        base = dict(flow=flow, age_s=10.0, packets=1000,
                    rx_bytes=int(80 * 1e6 / 8 * 10), avg_packet_bytes=1400)
        base.update(kw)
        return FlowFeatures(**base)

    def test_inference_alone_puts_a_saturating_flow_in_bulk(self):
        f = self._features(SSH)
        self.assertEqual(finalise(classify(f, 100.0)).cls, TrafficClass.BULK)

    def test_correction_overrides_it_and_survives_finalise(self):
        """finalise() demotes anything below MIN_CONFIDENCE. A user correction
        must not be demoted, or the override would be silently discarded."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.jsonl"
            store = CorrectionStore(path)
            store.record(SSH, TrafficClass.INTERACTIVE, reason="latency-critical")

            c = store.lookup(SSH)
            f = self._features(SSH, correction=c.cls)
            result = finalise(classify(f, 100.0))
            self.assertEqual(result.cls, TrafficClass.INTERACTIVE)
            self.assertEqual(result.confidence, 1.0)
            self.assertEqual(result.tier, "X")

    def test_correction_beats_an_existing_ef_verdict(self):
        """DSCP EF would otherwise classify this as interactive on its own; the
        user's statement must win either way."""
        with tempfile.TemporaryDirectory() as d:
            store = CorrectionStore(Path(d) / "c.jsonl")
            store.record(SSH, TrafficClass.BULK)
            f = self._features(SSH, dscp=46, correction=store.lookup(SSH).cls)
            self.assertEqual(finalise(classify(f, 100.0)).cls, TrafficClass.BULK)

    def test_without_a_correction_the_decision_is_unchanged(self):
        """Control: the override must come from the correction, not from the
        feature construction above."""
        f = self._features(SSH)
        self.assertEqual(finalise(classify(f, 100.0)).cls, TrafficClass.BULK)

    def test_expired_correction_no_longer_changes_the_decision(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.jsonl"
            CorrectionStore(path, now=1000.0).record(
                SSH, TrafficClass.INTERACTIVE, ttl_s=60)
            live = CorrectionStore(path, now=1050.0)
            f = self._features(SSH, correction=live.lookup(SSH).cls)
            self.assertEqual(finalise(classify(f, 100.0)).cls,
                             TrafficClass.INTERACTIVE)
            dead = CorrectionStore(path, now=2000.0)
            gone = dead.lookup(SSH)
            self.assertIsNone(gone, "expired correction must not apply")
            f2 = self._features(SSH, correction=gone.cls if gone else None)
            self.assertEqual(finalise(classify(f2, 100.0)).cls,
                             TrafficClass.BULK)

    def test_host_scoped_correction_survives_a_reconnect(self):
        """The flow that matters: a corrected service must stay corrected after
        the client reconnects on a new source port."""
        with tempfile.TemporaryDirectory() as d:
            store = CorrectionStore(Path(d) / "c.jsonl")
            store.record(SSH, TrafficClass.INTERACTIVE, dport=None)
            for sport in (1, 40000, 65535):
                f = Flow("10.0.1.2", sport, "203.0.113.9", 22, "tcp")
                c = store.lookup(f)
                self.assertIsNotNone(c, f"sport {sport} lost its correction")
                self.assertEqual(c.cls, TrafficClass.INTERACTIVE)


if __name__ == "__main__":
    unittest.main()

class TestClassAliases(unittest.TestCase):
    """An operator reaching for `--as interactive` should not get a usage error.

    TrafficClass values are verbose (`realtime_interactive`), and a correction
    typo that reaches enforcement would route traffic to the wrong class.
    """

    def test_every_alias_resolves(self):
        from aciq.corrections import CLASS_ALIASES, parse_class
        for alias in CLASS_ALIASES:
            self.assertIsInstance(parse_class(alias), TrafficClass, alias)

    def test_aliases_map_to_the_intended_class(self):
        from aciq.corrections import parse_class
        self.assertEqual(parse_class("interactive"), TrafficClass.INTERACTIVE)
        self.assertEqual(parse_class("adaptive"), TrafficClass.ADAPTIVE)
        self.assertEqual(parse_class("bulk"), TrafficClass.BULK)
        self.assertEqual(parse_class("leased"), TrafficClass.LEASED)

    def test_canonical_values_still_work(self):
        from aciq.corrections import parse_class
        for c in TrafficClass:
            self.assertEqual(parse_class(c.value), c)

    def test_case_insensitive(self):
        from aciq.corrections import parse_class
        self.assertEqual(parse_class("INTERACTIVE"), TrafficClass.INTERACTIVE)

    def test_whitespace_tolerated(self):
        from aciq.corrections import parse_class
        self.assertEqual(parse_class("  bulk  "), TrafficClass.BULK)

    def test_unknown_class_raises_and_lists_options(self):
        from aciq.corrections import parse_class
        with self.assertRaises(CorrectionError) as cm:
            parse_class("nonsense")
        msg = str(cm.exception)
        self.assertIn("bulk_transfer", msg)
        self.assertIn("interactive", msg)

    def test_non_string_rejected(self):
        from aciq.corrections import parse_class
        with self.assertRaises(CorrectionError):
            parse_class(3)

    def test_alias_is_stored_canonically(self):
        """The file must stay unambiguous regardless of how it was entered."""
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "c.jsonl"
            CorrectionStore(path).record(SSH, TrafficClass.BULK)
            line = path.read_text().strip()
            self.assertEqual(json.loads(line)["cls"], "bulk_transfer")
