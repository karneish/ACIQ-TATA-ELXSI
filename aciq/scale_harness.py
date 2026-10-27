"""Scale harness: run a fixed number of flows in a replayed model.

Physical hardware, Wi-Fi, DOCSIS, multi-tenant ISP shaping cannot be exercised
in this shell. This harness models 50, 100, and 500 flows using the same
classifier, intent, and correction logic so behaviour is deterministic and
repeatable; it labels results as simulated.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from dataclasses import dataclass

from .classify import classify, finalise
from .flowtrack import FlowFeatures
from .intent import LeaseBook
from .model import Flow, TrafficClass
from .policy import build_plan
from .shield import Shield


@dataclass(frozen=True)
class ScaleCase:
    name: str
    flow_count: int
    flow: Flow
    age_s: float
    packets: int
    rx_bytes: int
    tx_bytes: int
    avg_packet_bytes: int
    target_class: TrafficClass | None


CASES = [
    ScaleCase("interactive_call", 50, Flow("10.0.1.2", 40000, "203.0.113.9", 5001, "udp"),
              10, 800, 960000, 960000, 1200, TrafficClass.VIDEO_CALL),
    ScaleCase("video_stream", 100, Flow("10.0.1.10", 0, "198.51.100.5", 443, "tcp"),
              30, 6000, 18000000, 900000, 3150, TrafficClass.STREAMING),
    ScaleCase("bulk_download", 500, Flow("10.0.2.3", 0, "203.0.113.50", 873, "tcp"),
              60, 200000, 3000000000, 400000, 15000, TrafficClass.BULK_DOWNLOAD),
]


class ScaleHarness:
    def __init__(self, capacity_mbps: float = 100.0):
        self.capacity_mbps = capacity_mbps

    def run(self) -> dict:
        results = []
        for case in CASES:
            trust = None
            from aciq.classify import TrustStore
            trust = TrustStore()
            feats = [FlowFeatures(case.flow, age_s=case.age_s,
                                  packets=case.packets, rx_bytes=case.rx_bytes,
                                  tx_bytes=case.tx_bytes,
                                  avg_packet_bytes=case.avg_packet_bytes)
                     for _ in range(case.flow_count)]
            classified = [finalise(classify(f, self.capacity_mbps, trust))
                          for f in feats]
            accepted = sum(1 for c in classified if c.cls is not None)
            correct = sum(1 for c in classified
                          if case.target_class is not None and c.cls == case.target_class)
            labelled = case.flow_count if case.target_class is not None else 0
            plan = build_plan(self.capacity_mbps)
            shield = Shield()
            violations = shield.veto_plan(plan)
            book = LeaseBook()
            results.append({
                "name": case.name,
                "flow_count": case.flow_count,
                "labelled": labelled,
                "classified": accepted,
                "correct_on_labelled": correct,
                "accuracy_on_labelled": (round(correct / labelled, 4)
                                        if labelled else None),
                "coverage": round(accepted / case.flow_count, 4),
                "plan_ok": len(violations) == 0,
                "leases_active": len(book.active()),
                "simulated": True,
            })
        return {
            "kind": "simulated_scale_replay",
            "capacity_mbps": self.capacity_mbps,
            "generated_at": time.time(),
            "results": results,
        }

    def write_report(self, path) -> str:
        rep = self.run()
        out = Path(path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rep, indent=2) + "\n")
        return str(out)
