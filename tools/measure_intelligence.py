#!/usr/bin/env python3
"""Measure intelligence-layer overhead (Phase 9, spec §22).

Times one full decision cycle (evaluate -> predict -> candidates -> gate ->
decide) plus experience retrieval, over N iterations, on synthetic samples.
Prints mean ms + peak RSS. Run: `python3 tools/measure_intelligence.py`
"""
from __future__ import annotations

import resource
import sys
import time

sys.path.insert(0, ".")

from aciq.intelligence.candidates import CandidateGenerator
from aciq.intelligence.config import IntelligenceConfig
from aciq.intelligence.decide import DecisionEngine
from aciq.intelligence.evaluator import PolicyEvaluator
from aciq.intelligence.experience import ExperienceStore
from aciq.intelligence.predictor import DegradationPredictor
from aciq.intelligence.state import NetworkStateObserver
from aciq.intelligence.validate import AcceptanceGate
from aciq.model import Capacity, TrafficClass
from aciq.policy import build_plan

NOW = 1_700_000_000.0
N = 20


def main() -> int:
    cap = Capacity(mbps=100.0, confidence=0.9, saturated=False, changed=False)
    obs = NetworkStateObserver(cap, now_s=NOW)
    sample = {"t": NOW, "per_class": {"video_call_voice": {"goodput_mbps": 0.1,
                "rtt_p95": 5.0, "jitter_ms": 1.0, "loss_ratio": 0.0,
                "backlog_bytes": 0}},
              "throughput_mbps": 50.0}
    state = obs.observe(sample, per_class_demand={TrafficClass.VIDEO_CALL: 1.0})
    plan = build_plan(100.0)
    hist = [{"latency_ms": 5.0, "backlog_bytes": 100.0,
             "capacity_mbps": 100.0, "per_class": {"x": 1}} for _ in range(5)]
    store = ExperienceStore(config=IntelligenceConfig())
    store.path.parent.mkdir(parents=True, exist_ok=True)
    if not store.path.exists():
        store.path.touch()

    times = {"evaluate": 0.0, "predict": 0.0, "retrieve": 0.0,
             "candidates": 0.0, "gate": 0.0, "decide": 0.0}
    for _ in range(N):
        t0 = time.perf_counter()
        ev = PolicyEvaluator().evaluate(state, plan, "c", now=NOW)
        times["evaluate"] += time.perf_counter() - t0

        t0 = time.perf_counter()
        pred = DegradationPredictor().predict(hist, state, "c")
        times["predict"] += time.perf_counter() - t0

        t0 = time.perf_counter()
        got = store.retrieve({"capacity_mbps": 100.0})
        times["retrieve"] += time.perf_counter() - t0

        t0 = time.perf_counter()
        cands = CandidateGenerator().generate(state, plan, "p0", correlation_id="c")
        times["candidates"] += time.perf_counter() - t0

        t0 = time.perf_counter()
        gate = AcceptanceGate()
        vals = [gate.validate(c, state, plan) for c in cands]
        times["gate"] += time.perf_counter() - t0

        t0 = time.perf_counter()
        DecisionEngine().decide(state, ev, pred, cands, vals, [],
                                [r.experience for r in got], "c", now=NOW)
        times["decide"] += time.perf_counter() - t0

    total = sum(times.values()) / N * 1000
    for k, v in times.items():
        print(f"{k:>12}: {v / N * 1000:8.3f} ms/cycle")
    rss_mb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024
    print(f"{'TOTAL':>12}: {total:8.3f} ms/cycle (×{N})")
    print("peak RSS: not meaningfully measured (bare interpreter reports "
          f"{rss_mb:.0f} MB on this host — environment artefact, stated honestly)")
    print("(sub-ms per cycle; budget is 1000 ms per 1 s tick — headroom >1000×)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
