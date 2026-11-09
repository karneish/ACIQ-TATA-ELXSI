"""Phase 3: config, experience persistence, retrieval, audit log (temp dirs only)."""
import json
import tempfile
import unittest
from pathlib import Path

from aciq.intelligence.config import IntelligenceConfig
from aciq.intelligence.contracts import (
    DecisionAction,
    DecisionResult,
    Experience,
    ExperienceStatus,
    SCHEMA_VERSION,
)
from aciq.intelligence.experience import DecisionLogger, ExperienceStore

NOW = 1_700_000_000.0


def _exp(status=ExperienceStatus.SUCCESS, cap=100.0, lat=5.0, recorded=NOW, measured=True):
    ctx = {"capacity_mbps": cap, "latency_ms": lat, "jitter_ms": 1.0,
           "loss_ratio": 0.0, "demand": {"video_call_voice": 1.0}}
    outcome = {"measured": {"latency_ms": lat}} if measured else {}
    return Experience(status=status, network_context=ctx,
                      outcome_context=outcome, recorded_at=recorded)


class TestConfig(unittest.TestCase):
    def test_defaults_valid(self):
        cfg = IntelligenceConfig()
        self.assertTrue(cfg.is_valid())

    def test_bad_values_rejected(self):
        for kwargs in ({"max_candidates": 0}, {"max_candidates": 99},
                       {"similarity_threshold": 0.0}, {"similarity_threshold": 2.0},
                       {"capacity_margin_fraction": 1.0},
                       {"retention_max_records": 10},
                       {"recovery_attempt_limit": 0}):
            cfg = IntelligenceConfig(**kwargs)
            self.assertFalse(cfg.is_valid(), kwargs)
            with self.assertRaises(ValueError):
                cfg.validate()

    def test_roundtrip_and_unknown_key_rejected(self):
        cfg = IntelligenceConfig()
        back = IntelligenceConfig.from_dict(cfg.to_dict())
        self.assertEqual(back, cfg)
        with self.assertRaises(ValueError):
            IntelligenceConfig.from_dict({**cfg.to_dict(), "unknown_key": 1})

    def test_from_file_and_bad_json(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "cfg.json"
            p.write_text(json.dumps(IntelligenceConfig().to_dict()))
            self.assertTrue(IntelligenceConfig.from_file(p).is_valid())
            p.write_text("{not json")
            with self.assertRaises(ValueError):
                IntelligenceConfig.from_file(p)


class TestExperienceStore(unittest.TestCase):
    def _store(self, d):
        return ExperienceStore(Path(d) / "experiences.jsonl")

    def test_append_roundtrip_and_restart(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.append(_exp())
            store.append(_exp(status=ExperienceStatus.FAILED, cap=20.0, lat=50.0))
            # restart: brand-new store object reads the same file
            records, stats = self._store(d).load_all()
            self.assertEqual(stats.loaded, 2)
            self.assertEqual({r.status for r in records},
                             {ExperienceStatus.SUCCESS, ExperienceStatus.FAILED})

    def test_invalid_record_rejected_not_written(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            bad = _exp(measured=False)  # SUCCESS without measured -> invalid
            with self.assertRaises(ValueError):
                store.append(bad)
            records, stats = store.load_all()
            self.assertEqual(records, [])

    def test_corrupt_lines_quarantined(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.append(_exp())
            with open(store.path, "a") as f:
                f.write("{not json\n")
                f.write(json.dumps({"schema": 999, "foo": 1}) + "\n")
                f.write(json.dumps({"schema": 1, "record_id": "x"}) + "\n")
            records, stats = store.load_all()
            self.assertEqual(len(records), 1)
            self.assertEqual(stats.skipped_malformed, 1)
            self.assertEqual(stats.skipped_wrong_version, 1)
            self.assertEqual(stats.skipped_invalid, 1)
            self.assertEqual(len(stats.quarantined), 3)

    def test_simulation_never_outranks_measured(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.append(_exp(status=ExperienceStatus.SIMULATION_ONLY,
                              measured=False))
            store.append(_exp())  # measured twin, same context
            q = {"capacity_mbps": 100.0, "latency_ms": 5.0, "jitter_ms": 1.0,
                 "loss_ratio": 0.0, "demand": {"video_call_voice": 1.0}}
            got = store.retrieve(q)
            self.assertTrue(got)
            self.assertIn(got[0].experience.status,
                          (ExperienceStatus.SUCCESS, ExperienceStatus.FAILED))

    def test_poor_match_returns_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.append(_exp(cap=100.0, lat=5.0))
            q = {"capacity_mbps": 5.0, "latency_ms": 200.0, "jitter_ms": 90.0,
                 "loss_ratio": 0.9, "demand": {"bulk_download": 5.0}}
            self.assertEqual(store.retrieve(q), [])

    def test_retrieval_explains_similarity(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.append(_exp())
            q = {"capacity_mbps": 100.0, "latency_ms": 5.0, "jitter_ms": 1.0,
                 "loss_ratio": 0.0, "demand": {"video_call_voice": 1.0}}
            got = store.retrieve(q)
            self.assertTrue(got)
            self.assertIn("capacity", got[0].explanation)
            self.assertGreaterEqual(got[0].score, 0.6)

    def test_retention_archives_and_keeps_newest(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            for i in range(5):
                store.append(_exp(recorded=NOW + i))
            backup = store.prune(keep=2)
            self.assertIsNotNone(backup)
            self.assertTrue(Path(backup).exists())
            records, _ = store.load_all()
            self.assertEqual(len(records), 2)
            self.assertEqual(backup.parent, Path(d))

    def test_prune_noop_under_limit(self):
        with tempfile.TemporaryDirectory() as d:
            store = self._store(d)
            store.append(_exp())
            self.assertIsNone(store.prune(keep=5000))


class TestDecisionLogger(unittest.TestCase):
    def test_append_and_reload(self):
        with tempfile.TemporaryDirectory() as d:
            log = DecisionLogger(Path(d) / "decisions.jsonl")
            dec = DecisionResult(action=DecisionAction.RETAIN,
                                 current_policy_id="p0", reason="healthy",
                                 correlation_id="life1", recorded_at=NOW)
            log.append(dec)
            loaded = log.load_all()
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].action, DecisionAction.RETAIN)
            self.assertEqual(loaded[0].correlation_id, "life1")

    def test_corrupt_line_never_crashes_read(self):
        with tempfile.TemporaryDirectory() as d:
            log = DecisionLogger(Path(d) / "decisions.jsonl")
            with open(log.path, "w") as f:
                f.write("{broken\n")
            self.assertEqual(log.load_all(), [])

    def test_invalid_decision_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            log = DecisionLogger(Path(d) / "decisions.jsonl")
            bad = DecisionResult(action=DecisionAction.SELECT,
                                 current_policy_id="p0", reason="x",
                                 recorded_at=NOW)  # SELECT without candidate
            with self.assertRaises(ValueError):
                log.append(bad)


if __name__ == "__main__":
    unittest.main()
