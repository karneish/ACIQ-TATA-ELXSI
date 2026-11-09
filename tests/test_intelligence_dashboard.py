"""Phase 7: intelligence dashboard panels (additive, read-only)."""
import unittest

from aciq.dashboard import PANELS, build_from_samples
from aciq.intelligence.dashboard import (
    intelligence_summary,
    prediction_panel,
    render_intelligence_section,
)

SAMPLES = [
    {"t": 0.0, "capacity_mbps": 100.0,
     "intelligence": {"severity": 0.1},
     "per_class": {"video_call_voice": {"goodput_mbps": 0.1, "rtt_p95": 5.0,
                                        "jitter_ms": 1.0, "loss_ratio": 0.0,
                                        "backlog_bytes": 0}}},
    {"t": 1.0, "capacity_mbps": 90.0,
     "intelligence": {"severity": 0.4},
     "per_class": {"video_call_voice": {"goodput_mbps": 0.1, "rtt_p95": 8.0,
                                        "jitter_ms": 2.0, "loss_ratio": 0.0,
                                        "backlog_bytes": 0}}},
]
DECISIONS = [{"action": "retain", "reason": "healthy",
              "recorded_at": 1_700_000_000.0, "selected_candidate_id": None}]
EXPERIENCES = [{"status": "success",
                "outcome_context": {"measured": {"latency_ms": 5.0}}}]


class TestIntelligenceDashboard(unittest.TestCase):
    def test_empty_renders_nothing(self):
        self.assertEqual(render_intelligence_section([], [], []), "")

    def test_section_present_with_badges(self):
        html = render_intelligence_section(SAMPLES, DECISIONS, EXPERIENCES)
        self.assertIn("Intelligence layer", html)
        self.assertIn("Estimated", html)   # prediction panel badge
        self.assertIn("Observed", html)    # decision tiles
        self.assertIn("Verified", html)    # measured experience

    def test_prediction_panel_carries_series(self):
        key, title, series = prediction_panel(SAMPLES)
        self.assertIn("Estimated", title)
        self.assertIn("severity", [s.label for s in series])
        self.assertIn("capacity", [s.label for s in series])

    def test_summary_counts_actions_and_statuses(self):
        tiles = intelligence_summary(DECISIONS, EXPERIENCES)
        joined = " ".join(f"{k} {v} {h}" for k, v, h in tiles)
        self.assertIn("1 decisions", joined)
        self.assertIn("success=1", joined)

    def test_base_page_unchanged_by_default(self):
        html = build_from_samples(SAMPLES)
        self.assertNotIn("Intelligence layer", html)
        self.assertEqual(html.count('class="panel"'), 6)

    def test_base_page_with_intelligence_section(self):
        section = render_intelligence_section(SAMPLES, DECISIONS, EXPERIENCES)
        html = build_from_samples(SAMPLES, intelligence=section)
        self.assertIn("Intelligence layer", html)
        self.assertEqual(html.count('class="panel"'), 7)  # 6 base + prediction

    def test_panels_tuple_untouched(self):
        self.assertEqual([k for k, _ in PANELS],
                         ["latency", "jitter", "loss", "throughput",
                          "queue_depth", "fairness"])


if __name__ == "__main__":
    unittest.main()
