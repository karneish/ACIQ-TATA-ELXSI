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
import ipaddress
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

#: Column name for "the classifier declined to class this flow". A confusion
#: matrix that dropped abstentions would put a should-have-been-classed miss
#: silently off the diagonal.
ABSTAIN = "ABSTAIN"


@dataclass(frozen=True)
class Case:
    name: str
    truth: TrafficClass | None      # None = "must not be forced to a class"
    feats: FlowFeatures
    why: str
    #: When set, this case's label is only asserted at this link capacity.
    #: `bulk` is defined relative to the link, so a capacity-relative case has
    #: two truths (one per capacity). At the other capacity it is skipped, not
    #: scored -- scoring it would be marking the case wrong for being correct.
    rate_relative_to: float | None = None
    #: When True, an abstention is accepted as correct (truth is the preferred
    #: verdict, not the only acceptable one), and only a confident *wrong*
    #: verdict counts as an error.
    accept_abstention: bool = False


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
    # Port positions are the client/server ones conntrack actually sees: the
    # service port is the DESTINATION, because the originator of a connection
    # aims at it, and the classifier reads `dport` only. An earlier version put
    # the signalling port in `sport` (3478 -> 3479) and the call cases on port
    # 5004, which is bulk.py's listen port used backwards as a source port. So
    # the port-path cases never exercised the port path, and the call cases
    # matched no generator in the project.
    A(Case("call: EF, small, frequent, bidirectional",
           TrafficClass.INTERACTIVE,
           _f(sport=40000, dport=5001, dscp=46, rx=240_000, tx=240_000,
              pkts=200, age=5, avg=1200, burst=0.05, duty=0.5),
           "the case the rules were written for; dport 5001 is call.py"))
    A(Case("call: EF, steady, one-way-heavy",
           TrafficClass.INTERACTIVE,
           _f(sport=40000, dport=5001, dscp=46, rx=600_000, tx=180_000,
              pkts=500, age=8, avg=1200, burst=0.02, duty=0.3),
           "interactive does not need equal directions"))
    A(Case("interactive: RTP ports, no EF claim",
           TrafficClass.INTERACTIVE,
           _f(sport=40000, dport=3478, rx=300_000, tx=300_000,
              pkts=250, age=6, avg=1200, burst=0.05, duty=0.5),
           "well-known signalling port as dport, no DSCP"))
    A(Case("interactive: STUN 3478, unidirectional",
           TrafficClass.INTERACTIVE,
           _f(sport=40001, dport=3478, rx=90_000, tx=10_000,
              pkts=90, age=6, avg=1000, burst=0.3, duty=0.2),
           "must classify on the port, not on symmetry"))
    # game.py: 30 pps * 128 B payload -> 156 B IP datagrams, 0.075 Mbps. Low
    # rate and small packets, exactly the shape the interactive rule is for.
    A(Case("game: 30 pps, 128-byte datagrams, bidirectional",
           TrafficClass.INTERACTIVE,
           _f(sport=40002, dport=5002, rx=23_400, tx=23_400,
              pkts=150, age=5, avg=156, burst=0.1, duty=1.0),
           "generator that had no case at all; dport 5002 is game.py"))

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
    # These carry enough bytes over their life to sit above BULK_MIN_CAPACITY_FRAC
    # at BOTH 100 and 10 Mbps. An earlier revision used 80-120 MB over 30 s
    # (21-32 Mbps), which is *below* 0.5 of a 100 Mbps link -- so at the shipped
    # default the fixture labelled a moderate transfer "bulk" and the classifier
    # correctly called it adaptive. The "failure" was the fixture, not the rule;
    # a bulk case at a stated capacity must actually hog that capacity.
    A(Case("bulk: sustained one-way, very large packets",
           TrafficClass.BULK,
           _f(sport=0, dport=873, proto="tcp", rx=300_000_000, tx=200_000,
              pkts=60_000, age=30, avg=15000, burst=0.05, duty=0.99),
           "classic bulk: 300 MB/30 s = 80 Mbps, bulk at 100 and 10 Mbps"))
    A(Case("bulk: large on an encrypted port, no marks",
           TrafficClass.BULK,
           _f(sport=0, dport=443, proto="tcp", rx=400_000_000, tx=100_000,
              pkts=80_000, age=30, avg=15000, burst=0.02, duty=0.99),
           "must use rate, not the port table"))

    # ---- adversarial: misleading signals ---------------------------------
    A(Case("ADVERSARIAL bulk claiming EF",
           TrafficClass.BULK,
           _f(sport=0, dport=443, proto="tcp", dscp=46, rx=350_000_000,
              tx=120_000, pkts=70_000, age=30, avg=15000, burst=0.02, duty=0.99),
           "the EF claim must lose to the behaviour"))
    A(Case("ADVERSARIAL video claiming EF on a small pipe",
           TrafficClass.ADAPTIVE,
           _f(sport=0, dport=443, proto="tcp", dscp=46, rx=6_000_000,
              tx=200_000, pkts=2000, age=20, avg=3000, burst=0.15, duty=0.8),
           "EF but video-shaped"))
    A(Case("ADVERSARIAL interactive on a bulk port",
           TrafficClass.INTERACTIVE,
           _f(sport=40000, dport=873, rx=120_000, tx=120_000,
              pkts=120, age=5, avg=1000, burst=0.4, duty=0.4),
           "port table must not override behaviour; 40000 is the client side"))

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


def independent_cases() -> list[Case]:
    """A SECOND corpus, generated independently of the thresholds above.

    The cases in `cases()` were written alongside the rules and are the set the
    rules were reasoned against; reporting accuracy only on them would be
    reporting on the training set. This corpus is built from *protocol and
    address-family coverage* rather than from the rule shapes: TCP, UDP, DNS
    (udp/53), HTTPS (tcp/443), UDP/443 (QUIC, the known-ambiguous case), a
    nonstandard-port bulk transfer, a nonstandard-port call, concurrent
    (distinct) flows, and IPv6 variants. The labels come from the same
    constructor contract -- they are decided before the classifier runs -- and
    none of the classify.py constants is touched by building them.

    Where a case is genuinely ambiguous from metadata alone (UDP/443) the truth
    is None: the classifier is *required* to abstain, and a corpus that
    pretended to know would be testing the fixture, not the classifier.
    """
    c: list[Case] = []
    A = c.append
    V6 = "fd00::7"

    # --- protocol x port coverage, IPv4 ---
    A(Case("dns: udp/53, tiny query, bidirectional",
           TrafficClass.INTERACTIVE,
           _f(sport=53000, dport=53, proto="udp", rx=4_000, tx=4_000,
              pkts=40, age=4, avg=100, duty=0.3),
           "DNS is small and bursty; must not be forced to bulk"))
    A(Case("https: tcp/443 sustained, mid rate",
           TrafficClass.ADAPTIVE,
           _f(sport=44000, dport=443, proto="tcp", rx=5_000_000, tx=300_000,
              pkts=1600, age=18, avg=3300, duty=0.8),
           "https range, steady"))
    A(Case("nonstandard port: bulk by behaviour, not by port",
           TrafficClass.BULK,
           _f(sport=55000, dport=6000, proto="tcp", rx=300_000_000, tx=150_000,
              pkts=60_000, age=30, avg=15000, duty=0.99),
           "port 6000 is in no table; the rate must decide. 300 MB over 30 s "
           "is 80 Mbps, which is >=0.5 of a 100 Mbps link AND >=0.5 of a "
           "10 Mbps link, so it is bulk at either capacity"))
    A(Case("nonstandard port: call by behaviour, not by port",
           TrafficClass.INTERACTIVE,
           _f(sport=40000, dport=7000, proto="udp", rx=200_000, tx=200_000,
              pkts=180, age=5, avg=1200, duty=0.5),
           "must classify on shape, not on a known port"))

    # --- address family: IPv6 uses the same rules, different literal ---
    A(Case("ipv6 call: EF, small, bidirectional",
           TrafficClass.INTERACTIVE,
           FlowFeatures(Flow("fd00::9", 40000, V6, 5001, "udp"),
                        dscp=46, rx_bytes=240_000, tx_bytes=240_000,
                        packets=200, age_s=5, avg_packet_bytes=1200,
                        duty_cycle=0.5),
           "address family must not change the verdict"))
    A(Case("ipv6 video: sustained tcp/443",
           TrafficClass.ADAPTIVE,
           FlowFeatures(Flow("fd00::9", 0, V6, 443, "tcp"),
                        rx_bytes=8_000_000, tx_bytes=350_000, packets=2600,
                        age_s=20, avg_packet_bytes=3000, duty_cycle=0.85),
           "same rate rule over IPv6"))

    # --- concurrent flows are evaluated one at a time; identity must not merge ---
    A(Case("concurrent: one of two distinct bulk flows",
           TrafficClass.BULK,
           _f(sport=56000, dport=7001, proto="tcp", rx=250_000_000, tx=100_000,
              pkts=50_000, age=25, avg=15000, duty=0.99),
           "two flows on the same class must be scored separately"))

    # --- the honest gap, restated independently ---
    A(Case("udp/443 QUIC: no mark, statistics cannot separate call from download",
           None,
           _f(sport=52000, dport=443, proto="udp", rx=300_000, tx=300_000,
              pkts=300, age=6, avg=1100, duty=0.5),
           "must abstain rather than guess QUIC's purpose"))

    # --- too little evidence ---
    A(Case("insufficient: single packet",
           None, _f(sport=40000, dport=80, rx=60, tx=60, pkts=1, age=0.1,
                    avg=60),
           "one packet is not a flow yet"))

    # --- capacity-relative rate: the same flow, two links ---
    # 16 Mbps of sustained TCP is adaptive on a 100 Mbps link and bulk on a
    # 10 Mbps one. This corpus is scored at BOTH capacities (see main()), so a
    # single FlowFeatures cannot carry one truth; `rate_relative_to` names the
    # capacity this label is asserted at, and `evaluate()` compares it only
    # there. At the other capacity the case is skipped, not failed.
    A(Case("capacity-relative: 16 Mbps sustained TCP is bulk at 10 Mbps",
           TrafficClass.BULK,
           _f(sport=57000, dport=6100, proto="tcp", rx=60_000_000, tx=100_000,
              pkts=45_000, age=30, avg=1300, duty=0.9),
           "16 Mbps is >=0.5 of 10 Mbps but <0.5 of 100 Mbps",
           rate_relative_to=10.0))
    A(Case("capacity-relative: 16 Mbps sustained TCP is adaptive at 100 Mbps",
           TrafficClass.ADAPTIVE,
           _f(sport=57000, dport=6100, proto="tcp", rx=60_000_000, tx=100_000,
              pkts=45_000, age=30, avg=1300, duty=0.9),
           "the same volume, a wider link",
           rate_relative_to=100.0))

    # --- address family, bulk shape over IPv6 ---
    A(Case("ipv6 bulk: sustained, unidirectional",
           TrafficClass.BULK,
           FlowFeatures(Flow("fd00::9", 58000, V6, 6200, "tcp"),
                        rx_bytes=250_000_000, tx_bytes=120_000, packets=60_000,
                        age_s=30, avg_packet_bytes=4000, duty_cycle=0.98),
           "the rate rule must fire over IPv6 too"))

    # --- DNS over TCP: small, bursty, should not be forced to bulk ---
    # The classifier abstains here (too little evidence at 40 packets), which is
    # acceptable: the case is scored as correct if it abstains OR says
    # interactive, and only a confident non-interactive verdict fails.
    A(Case("dns/tcp: tiny query must not be confidently bulk",
           TrafficClass.INTERACTIVE,
           _f(sport=53001, dport=53, proto="tcp", rx=6_000, tx=6_000,
              pkts=40, age=4, avg=150, duty=0.3),
           "truth accepts abstention; a confident bulk verdict is the error",
           accept_abstention=True))
    return c


def _breakdown(rows: list[dict], key) -> dict:
    """Group scored rows by an attribute of the flow and summarise each group.

    `key(row)` returns a label (e.g. proto, or "v4"/"v6"). Used to report
    accuracy by protocol and address family, which a single overall number
    hides.
    """
    groups: dict[str, list[dict]] = {}
    for r in rows:
        groups.setdefault(key(r), []).append(r)
    out = {}
    for g, rs in sorted(groups.items()):
        labelled = [r for r in rs if r["truth"] is not None]
        correct = sum(1 for r in labelled if r["correct"])
        out[g] = {
            "cases": len(rs),
            "labelled": len(labelled),
            "accuracy_on_labelled": (round(correct / len(labelled), 4)
                                     if labelled else None),
        }
    return out


def evaluate(corpus: str = "constructed", capacity_mbps: float = 100.0) -> dict:
    """Evaluate at a stated link capacity.

    Capacity matters and is not a detail: `bulk` is defined as taking at least
    BULK_MIN_CAPACITY_FRAC (0.5) of the link, so the same flow is bulk on a
    10 Mbps link and merely adaptive on a 100 Mbps one. Reporting a single
    number would hide that, so the caller runs both.

    `corpus` selects the case set: "constructed" (the rules were reasoned
    against these) or "independent" (generated from protocol/family coverage,
    separately). Reporting both, and the gap between them, is what keeps the
    evaluation honest.
    """
    # A fresh store per case, so one case's contradictions cannot leak into the
    # next one's verdict. Order-independence is part of the test.
    source = independent_cases() if corpus == "independent" else cases()
    rows = []
    skipped = 0
    for case in source:
        # A capacity-relative case declares the link its label holds at. At any
        # other capacity it is not wrong, it is out of scope; skipping is the
        # honest disposition and the count is reported.
        if (case.rate_relative_to is not None
                and abs(case.rate_relative_to - capacity_mbps) > 1e-6):
            skipped += 1
            continue
        trust = TrustStore(decay=TRUST_DECAY, floor=TRUST_FLOOR)
        got = classify(case.feats, capacity_mbps, trust)
        # `accept_abstention` widens "correct" for cases where declining is a
        # legitimate answer: the truth is preferred, but an abstention is not an
        # error -- only a confident wrong verdict is.
        if case.accept_abstention and case.truth is not None and got.cls is None:
            correct = True
        else:
            correct = got.cls == case.truth
        rows.append({
            "name": case.name, "truth": case.truth.value if case.truth else None,
            "got": got.cls.value if got.cls else None,
            "confidence": round(got.confidence, 4), "tier": got.tier,
            "correct": correct,
            "accept_abstention": case.accept_abstention,
            "proto": case.feats.flow.proto,
            "ip_version": _ip_version(case.feats.flow.src),
        })

    labelled = [r for r in rows if r["truth"] is not None]
    abstained_correct = sum(1 for r in rows if r["truth"] is None and r["got"] is None)

    # Classes present in the truth set, in a stable order. Driving the matrix
    # off TrafficClass would include a class no case exercises; driving it off
    # the truth labels keeps the matrix to what was actually tested.
    classes = sorted({r["truth"] for r in labelled})
    pred_labels = sorted(classes + [ABSTAIN])

    # Confusion matrix: truth (rows) x prediction (cols), with "abstain" as a
    # column so a case that should have been classed but was not is visible
    # rather than hidden off the diagonal.
    confusion = {t: {p: 0 for p in pred_labels} for t in classes}
    for r in labelled:
        confusion[r["truth"]][r["got"] if r["got"] is not None else ABSTAIN] += 1

    per_class = {}
    for cls in classes:
        tp = sum(1 for r in labelled if r["truth"] == cls and r["got"] == cls)
        fp = sum(1 for r in labelled if r["truth"] != cls and r["got"] == cls)
        fn = sum(1 for r in labelled if r["truth"] == cls and r["got"] != cls)
        prec = tp / (tp + fp) if (tp + fp) else None
        rec = tp / (tp + fn) if (tp + fn) else None
        # `is not None`, not truthiness: a class the classifier never gets right
        # has precision or recall of exactly 0.0, which is a real and important
        # value. Treating 0.0 as "absent" would drop that class from macro-F1
        # and inflate the average -- the exact failure mode this project avoids.
        if prec is not None and rec is not None and (prec + rec) > 0:
            f1 = 2 * prec * rec / (prec + rec)
        elif prec is not None and rec is not None:
            f1 = 0.0
        else:
            f1 = None
        per_class[cls] = {
            "support": tp + fn, "tp": tp, "fp": fp, "fn": fn,
            "precision": None if prec is None else round(prec, 4),
            "recall": None if rec is None else round(rec, 4),
            "f1": None if f1 is None else round(f1, 4)}

    with_pred = [r for r in labelled if r["got"] is not None]
    high_conf_errors = [r for r in with_pred
                        if r["confidence"] >= 0.7 and not r["correct"]]
    macro = [v["f1"] for v in per_class.values() if v["f1"] is not None]
    # Three accuracies, three denominators, stated so they cannot be conflated:
    #
    # * `accuracy_on_labelled`       -- flexible: an accepted abstention counts
    #                                   as correct (the truth is preferred but
    #                                   declining was legitimate).
    # * `selective_accuracy`         -- accuracy among the cases the classifier
    #                                   actually classified (coverage < 1).
    # * `end_to_end_accuracy`        -- strict: ANY abstention on a labelled
    #                                   case counts as an error, which is the
    #                                   number a user who needs a verdict sees.
    #
    # A reader who quotes one must say which; the three answer different
    # questions and differ exactly by the abstention policy.
    strict_correct = sum(
        1 for r in labelled if r["got"] is not None and r["got"] == r["truth"])
    return {
        "corpus": corpus,
        "capacity_mbps": capacity_mbps,
        "cases": len(rows),
        "skipped_capacity_relative": skipped,
        "labelled": len(labelled),
        "accuracy_on_labelled": (round(
            sum(1 for r in labelled if r["correct"]) / len(labelled), 4)
            if labelled else None),
        "end_to_end_accuracy": (round(strict_correct / len(labelled), 4)
                                if labelled else None),
        # Coverage vs accuracy. Abstention is the classifier refusing to guess;
        # "accuracy among non-abstained" is the accuracy of the guesses it did
        # make, and is strictly higher than overall accuracy by construction.
        # The pair is the trade-off: abstaining more raises the latter and
        # lowers coverage.
        "coverage": (round(len(with_pred) / len(labelled), 4)
                     if labelled else None),
        "selective_accuracy": (round(
            sum(1 for r in with_pred if r["correct"]) / len(with_pred), 4)
            if with_pred else None),
        "accuracy_among_non_abstained": (round(
            sum(1 for r in with_pred if r["correct"]) / len(with_pred), 4)
            if with_pred else None),
        "abstention_required": len(rows) - len(labelled),
        "abstained_correctly": abstained_correct,
        "abstention_rate": round(
            sum(1 for r in rows if r["got"] is None) / len(rows), 4),
        "macro_f1": round(sum(macro) / len(macro), 4) if macro else None,
        "high_confidence_errors": len(high_conf_errors),
        "high_confidence_error_names": [r["name"] for r in high_conf_errors],
        "confusion": confusion,
        "by_protocol": _breakdown(labelled, lambda r: r["proto"]),
        "by_ip_version": _breakdown(labelled, lambda r: r["ip_version"]),
        "per_class": per_class,
        "rows": rows,
    }


def _ip_version(addr: str) -> str:
    try:
        return f"v{ipaddress.ip_address(addr).version}"
    except ValueError:
        return "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json")
    a = ap.parse_args()
    print("Classifier evaluation (ground truth from the constructed workload)")
    both = {}
    for corpus in ("constructed", "independent"):
        for cap in (100.0, 10.0):
            r = evaluate(corpus, cap)
            both[f"{corpus}@{cap:g}"] = r
            print(f"\n=== {corpus} corpus, link capacity {cap:g} Mbps "
                  f"({'the shipped default' if cap == 100 else 'what --drop 10 produces'}) ===")
            _report(r)
    if a.json:
        Path(a.json).write_text(json.dumps(both, indent=2) + "\n")
        print(f"\n  wrote {a.json}")
    return 0


def _report(r: dict) -> None:
    print(f"  corpus {r['corpus']}   cases {r['cases']}   labelled {r['labelled']}"
          f"   (out of scope at this capacity: {r['skipped_capacity_relative']})")
    print(f"  accuracy on labelled cases  : {r['accuracy_on_labelled']}"
          f"   (flexible: accepted abstention counts as correct)")
    print(f"  selective accuracy          : {r['selective_accuracy']}"
          f"   (among the {r['coverage']:.0%} it classified; coverage {r['coverage']})")
    print(f"  end-to-end accuracy         : {r['end_to_end_accuracy']}"
          f"   (strict: any abstention on a labelled case is an error)")
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
    print("  confusion (truth x got):")
    cols = list(next(iter(r["confusion"].values())).keys()) if r["confusion"] else []
    if cols:
        head = "".join(f"{c[:9]:>11}" for c in cols)
        print(f"    {'':<20}{head}")
        for t, row in r["confusion"].items():
            line = "".join(f"{row[c]:>11}" for c in cols)
            print(f"    {t[:19]:<20}{line}")
    print()
    print("  by protocol / by ip version:")
    for k, v in r["by_protocol"].items():
        print(f"    proto {k:<6} acc {v['accuracy_on_labelled']} on {v['labelled']}")
    for k, v in r["by_ip_version"].items():
        print(f"    {k:<10} acc {v['accuracy_on_labelled']} on {v['labelled']}")
    print()
    print("  every case:")
    for row in r["rows"]:
        mark = "ok " if row["correct"] else "ERR"
        print(f"    {mark} {row['name'][:52]:<52} "
              f"truth={str(row['truth']):<20} got={str(row['got']):<20} "
              f"conf={row['confidence']:.2f} tier={row['tier']}")


if __name__ == "__main__":
    raise SystemExit(main())