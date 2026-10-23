"""Corpus shapes the collector produces must separate under the SHIPPED
rules. After the live corpus round came back 5/6-wrong, the window shapes
proved internally confusable: update/backup shared a saturating generator,
and uploads could not exist because conntrack direction was collapsed. The
shapes here are exactly what the fixed collector yields (rate-capped smooth
update; home-initiated upload; both directions split by DirectionTracker)
and classify() is called with capacity fixed, no trust, no correction.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aciq.classify import classify  # noqa: E402
from aciq.features import FlowFeatures  # noqa: E402
from aciq.flowtrack import Flow  # noqa: E402
from aciq.model import TrafficClass  # noqa: E402


def _shape(flow: Flow, tx: int, rx: int, burst: float | None,
           rate: float) -> FlowFeatures:
    """age_s is derived so the feature's own rate property equals `rate`;
    no attribute hacks."""
    total = tx + rx
    age = (total * 8 / 1e6) / rate
    return FlowFeatures(flow=flow, tx_bytes=tx, rx_bytes=rx,
                        packets=round(total / 1200), age_s=age,
                        avg_packet_bytes=1200.0, burstiness=burst,
                        duty_cycle=1.0)


class TestCorpusShapes(unittest.TestCase):
    def test_rate_capped_smooth_update_is_software_update(self):
        flow = Flow(src="203.0.113.2", sport=44444, dst="10.0.1.2",
                    dport=5004, proto="tcp")
        f = _shape(flow, tx=1_000_000, rx=19_000_000, burst=0.05,
                   rate=8.0)
        out = classify(f, capacity_mbps=100.0)
        self.assertEqual(out.cls, TrafficClass.SOFTWARE_UPDATE)

    def test_chunky_midrate_is_streaming_not_update(self):
        flow = Flow(src="203.0.113.2", sport=44444, dst="10.0.1.2",
                    dport=5003, proto="tcp")
        f = _shape(flow, tx=1_200, rx=35_000_000, burst=0.8,
                   rate=21.5)
        out = classify(f, capacity_mbps=100.0)
        self.assertEqual(out.cls, TrafficClass.STREAMING)

    def test_saturating_download_is_bulk(self):
        flow = Flow(src="203.0.113.2", sport=44444, dst="10.0.1.2",
                    dport=5004, proto="tcp")
        f = _shape(flow, tx=1_000_000, rx=228_000_000, burst=0.05,
                   rate=95.0)
        out = classify(f, capacity_mbps=100.0)
        self.assertEqual(out.cls, TrafficClass.BULK_DOWNLOAD)

    def test_home_initiated_upload_is_cloud_backup(self):
        flow = Flow(src="10.0.1.2", sport=44444, dst="203.0.113.2",
                    dport=5004, proto="tcp")
        f = _shape(flow, tx=19_000_000, rx=1_000_000, burst=0.05,
                   rate=8.0)
        out = classify(f, capacity_mbps=100.0)
        self.assertEqual(out.cls, TrafficClass.CLOUD_BACKUP)


if __name__ == "__main__":
    unittest.main()
