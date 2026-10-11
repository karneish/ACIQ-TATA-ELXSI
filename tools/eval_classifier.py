#!/usr/bin/env python3
"""Classifier evaluation against ground truth that does not come from itself.

§8.2 is explicit that labels must be generated from the controlled test
workload, not from the classifier's own predictions, and that the split must be
separate from anything tuned on it. Both are honoured here:

* every case is *constructed* from a known generator profile (call, game, video,
  bulk) -- the label is a property of how the flow was built, decided before the
  classifier ran;
* the thresholds in `aciq/classify.py` are not touched by this script, and the
  cases include shapes the rules were never written against.

Run:  python3 tools/eval_classifier.py [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aciq.classify import TrustStore, classify      # noqa: E402
from aciq.flowtrack import Flow, FlowFeatures        # noqa: E402
from aciq.model import TrafficClass                  # noqa: E402

#: The trust store starts empty, so an EF claim begins at full trust and has to
#: earn its way down. That is the state a fresh controller is actually in.
TRUST_DECAY = 0.5
TRUST_FLOOR = 0.25


@dataclass(frozen=True)
class Case:
    name: str
    truth: TrafficClass | None      # None = "must not be forced to a class"
    feats: FlowFeatures
    why: str


def _f(src="203.0.113.4", sport=5000, dport=443, proto="udp",
       dscp=None, rx=0, tx=0, pkts=0, age=5.0, avg=0.0,
       burst=0.0, duty=0.0, correction=None) -> FlowFeatures:
    return FlowFeatures(Flow(src, sport, "10.0.1.2", dport, proto),
                        dscp=dscp, rx_bytes=rx, tx_bytes=tx, packets=pkts,
                        age_s=age, avg_packet_bytes=avg, burstiness=burst,
                        duty_cycle=duty, correction=correction)


def cases() -> list[Case]:
    c: list[Case] = []
    A = c.append

    # ---- true interactive -----------------------------------------------
    A(Case("call: EF, small, frequent, bidirectional",
           TrafficClass.INTERACTIVE,
           _f(sport=5004, dport=5005, dscp=46, rx=240_000, tx=240_000,
              pkts=200, age=5, avg=1200, burst=0.05, duty=0.5),
           "the case the rules were written for"))
    A(Case("call: EF, steady, one-way-heavy",
           TrafficClass.INTERACTIVE,
           _f(sport=5004, dport=5005, dscp=46, rx=600_000, tx=180_000,
              pkts=500, age=8, avg=1200, burst=0.02, duty=0.3),
           "interactive does not need equal directions"))
    A(Case("interactive: RTP ports, no EF claim",
           TrafficClass.INTERACTIVE,
           _f(sport=3478, dport=3479, rx=300_000, tx=300_000,
              pkts=250, age=6, avg=1200, burst=0.05, duty=0.5),
           "well-known signalling port, no DSCP"))
    A(Case("interactive: STUN 3478, unidirectional",
           TrafficClass.INTERACTIVE,
           _f(sport=3478, dport=3479, rx=90_000, tx=10_000,
              pkts=90, age=6, avg=1000, burst=0.3, duty=0.2),
           "must classify on the port, not on symmetry"))

    # ---- true adaptive video --------------------------------------------
    A(Case("video: sustained, large, few bytes per packet",
           TrafficClass.ADAPTIVE,
           _f(sport=0, dport=443, proto="tcp", rx=9_000_000, tx=400_000,
              pkts=3000, age=20, avg=3000, burst=0.1, duty=0.9),
           "high rate, low interactivity"))
    A(Case("video: over TLS port, no marks",
           TrafficClass.ADAPTIVE,
           _f(sport=0, dport=443, proto="tcp", rx=14_000_000, tx=500_000,
              pkts=4000, age=25, avg=3500, burst=0.15, duty=0.85),
           "443 is not identity, but it is not nothing either"))
    A(Case("video: ramping (ABR ladder)",
           TrafficClass.ADAPTIVE,
           _f(sport=0, dport=443, proto="tcp", rx=4_000_000, tx=150_000,
              pkts=1400, age=15, avg=2800, burst=0.2, duty=0.7),
           "mid-ramp rate, still clearly a stream"))

    # ---- true bulk -------------------------------------------------------
    A(Case("bulk: sustained one-way, very large packets",
           TrafficClass.BULK,
           _f(sport=0, dport=873, proto="tcp", rx=80_000_000, tx=200_000,
              pkts=20_000, age=30, avg=15000, burst=0.05, duty=0.99),
           "classic bulk"))
    A(Case("bulk: large on an encrypted port, no marks",
           TrafficClass.BULK,
           _f(sport=0, dport=443, proto="tcp", rx=120_000_000, tx=100_000,
              pkts=30_000, age=30, avg=15000, burst=0.02, duty=0.99),
           "must use rate, not the port table"))

    # ---- adversarial: misleading signals ---------------------------------
    A(Case("ADVERSARIAL bulk claiming EF",
           TrafficClass.BULK,
           _f(sport=0, dport=443, proto="tcp", dscp=46, rx=90_000_000,
              tx=120_000, pkts=25_000, age=30, avg=15000, burst=0.02, duty=0.99),
           "the EF claim must lose to the behaviour"))
    A(Case("ADVERSARIAL video claiming EF on a small pipe",
           TrafficClass.ADAPTIVE,
           _f(sport=0, dport=443, proto="tcp", dscp=46, rx=6_000_000,
              tx=200_000, pkts=2000, age=20, avg=3000, burst=0.15, duty=0.8),
           "EF but video-shaped"))
    A(Case("ADVERSARIAL interactive on a bulk port",
           TrafficClass.INTERACTIVE,
           _f(sport=873, dport=873, rx=120_000, tx=120_000,
              pkts=120, age=5, avg=1000, burst=0.4, duty=0.4),
           "port table must not override behaviour"))

    # ---- too little evidence: must abstain, not guess --------------------
    A(Case("insufficient: 3 packets", None,
           _f(sport=40000, dport=40001, rx=300, tx=300, pkts=3, age=0.4,
              avg=100, burst=0.0, duty=0.0),
           "below MIN_PACKETS; guessing would be a fabrication"))
    A(Case("insufficient: too young", None,
           _f(sport=40000, dport=40002, rx=50_000, tx=50_000, pkts=200,
              age=0.3, avg=250, burst=0.0, duty=0.0),
           "below MIN_AGE_S"))
    A(Case("insufficient: idle, tiny, no ports, no marks", None,
           _f(sport=51234, dport=54321, rx=120, tx=120, pkts=1, age=0.2,
              avg=120),
           "no evidence at all"))

    # ---- correction overrides --------------------------------------------
    # The label is the *operator's* decision, not the rate: a correction exists
    # precisely to override what the rate would have said. An earlier version of
    # this file labelled it BULK and then counted the override as an error.
    A(Case("correction overrides what the rate would say",
           TrafficClass.ADAPTIVE,
           _f(sport=0, dport=443, proto="tcp", rx=90_000_000, tx=100_000,
              pkts=25_000, age=30, avg=15000, correction=TrafficClass.ADAPTIVE),
           "an operator correction must win, and be marked tier X"))
    return c


def evaluate(capacity_mbps: float = 100.0) -> dict:
    """Evaluate at a stated link capacity.

    Capacity matters and is not a detail: `bulk` is defined as taking at least
    BULK_MIN_CAPACITY_FRAC (0.5) of the link, so the same flow is bulk on a
    10 Mbps link and merely adaptive on a 100 Mbps one. Reporting a single
    number would hide that, so the caller runs both.
    """
    # A fresh store per case, so one case's contradictions cannot leak into the
    # next one's verdict. Order-independence is part of the test.
    rows = []
    for case in cases():
        trust = TrustStore(decay=TRUST_DECAY, floor=TRUST_FLOOR)
        got = classify(case.feats, capacity_mbps, trust)
        rows.append({
            "name": case.name, "truth": case.truth.value if case.truth else None,
            "got": got.cls.value if got.cls else None,
            "confidence": round(got.confidence, 4), "tier": got.tier,
            "correct": got.cls == case.truth,
        })

    labelled = [r for r in rows if r["truth"] is not None]
    abstained_correct = sum(1 for r in rows if r["truth"] is None and r["got"] is None)

    per_class = {}
    for cls in TrafficClass:
        tp = sum(1 for r in labelled if r["truth"] == cls.value and r["got"] == cls.value)
        fp = sum(1 for r in labelled if r["truth"] != cls.value and r["got"] == cls.value)
        fn = sum(1 for r in labelled if r["truth"] == cls.value and r["got"] != cls.value)
        prec = tp / (tp + fp) if (tp + fp) else None
        rec = tp / (tp + fn) if (tp + fn) else None
        f1 = (2 * prec * rec / (prec + rec)) if prec and rec else None
        per_class[cls.value] = {
            "support": tp + fn, "tp": tp, "fp": fp, "fn": fn,
            "precision": None if prec is None else round(prec, 4),
            "recall": None if rec is None else round(rec, 4),
            "f1": None if f1 is None else round(f1, 4)}

    with_pred = [r for r in labelled if r["got"] is not None]
    high_conf_errors = [r for r in with_pred
                        if r["confidence"] >= 0.7 and not r["correct"]]
    macro = [v["f1"] for v in per_class.values() if v["f1"] is not None]
    return {
        "capacity_mbps": capacity_mbps,
        "cases": len(rows),
        "labelled": len(labelled),
        "accuracy_on_labelled": round(
            sum(1 for r in labelled if r["correct"]) / len(labelled), 4),
        "abstention_required": len(rows) - len(labelled),
        "abstained_correctly": abstained_correct,
        "abstention_rate": round(
            sum(1 for r in rows if r["got"] is None) / len(rows), 4),
        "macro_f1": round(sum(macro) / len(macro), 4) if macro else None,
        "high_confidence_errors": len(high_conf_errors),
        "high_confidence_error_names": [r["name"] for r in high_conf_errors],
        "per_class": per_class,
        "rows": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args()
    print("Classifier evaluation (ground truth from the constructed workload)")
    both = {}
    for cap in (100.0, 10.0):
        r = evaluate(cap)
        both[str(cap)] = r
        print(f"\n=== link capacity {cap:g} Mbps "
              f"({'the shipped default' if cap == 100 else 'what --drop 10 produces'}) ===")
        _report(r)
    if a.json:
        Path(a.json).write_text(json.dumps(both, indent=2) + "\n")
        print(f"\n  wrote {a.json}")
    return 0


def _report(r: dict) -> None:
    print(f"  cases {r['cases']}   labelled {r['labelled']}")
    print(f"  accuracy on labelled cases : {r['accuracy_on_labelled']}")
    print(f"  macro F1                    : {r['macro_f1']}")
    print(f"  abstention rate             : {r['abstention_rate']}")
    print(f"  required to abstain, did so : {r['abstained_correctly']}"
          f"/{r['abstention_required']}")
    print(f"  high-confidence errors      : {r['high_confidence_errors']}")
    for n in r["high_confidence_error_names"]:
        print(f"      {n}")
    print()
    print("  per class:")
    for cls, v in r["per_class"].items():
        print(f"    {cls:<20} support {v['support']:>2}  "
              f"P {v['precision']}  R {v['recall']}  F1 {v['f1']}")
    print()
    print("  every case:")
    for row in r["rows"]:
        mark = "ok " if row["correct"] else "ERR"
        print(f"    {mark} {row['name'][:52]:<52} "
              f"truth={str(row['truth']):<20} got={str(row['got']):<20} "
              f"conf={row['confidence']:.2f} tier={row['tier']}")


if __name__ == "__main__":
    raise SystemExit(main())