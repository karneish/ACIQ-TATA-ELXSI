"""Offline evaluation of the router-vantage classifier corpus.

Input: corpus.jsonl written by tools/gen_corpus.py (flat records, one flow
each, WITH the label it was generated under).

Contract (T6 fix round):
  - The thresholds are the ones shipped in aciq/classify.py. They were fixed
    on the constructed corpus BEFORE this data existed; nothing here tunes
    them. The paths that define the rule base are recorded in `paths_fixed`.
  - The corpus is split by flow TUPLE (port-preserving): records whose flow
    tuple key hashes into the fixed half train nothing (there is no training)
    but are the sanity half; the held-out half is scored separately. A tuple
    split means the same flow can never represent both halves — that is the
    leak the old "one number for everything" hid.
  - Two accuracies, per the acceptance list: STRICT (an abstain on a
    labelled flow is an error) and ABSTENTION-AWARE (abstain is neither
    correct nor wrong; accuracy excludes it). Both tables, plus the
    confusion matrix, go in eval.json verbatim. build_report.py copies the
    file; nobody edits the numbers between here and the report.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aciq.classify import classify  # noqa: E402
from aciq.features import Flow, FlowFeatures  # noqa: E402
from aciq.classify import TrustStore  # noqa: E402
from aciq.model import TrafficClass, broad_class  # noqa: E402
import tools.gen_corpus as g  # noqa: E402

#: The rule base is defined by exactly this file and its constants. Written
#: into eval.json so the report can name the frozen rule set, not 'rules'.
FIXED_SOURCES = ["aciq/classify.py", "aciq/features.py",
                 "aciq/model.py:BROAD_TAXONOMY"]

ABSTAIN = "?abstain"

#: Calibration binning (docs/evidence/task4-params.md, declared before the
#: fresh corpus): predicted confidence is binned and each bin's empirical
#: accuracy is reported with it. Bins are the same for every corpus; nothing
#: here tunes on a result.
BIN_EDGES = (0.0, 0.2, 0.4, 0.6, 0.8, 1.0)


def tuple_key(rec: dict) -> str:
    f = rec["flow"]
    return hashlib.sha256(
        "\x1f".join((f["src"], f["dst"], str(f["sport"]), str(f["dport"]),
                     f["proto"])).encode()).hexdigest()


def rebuild_features(rec: dict) -> FlowFeatures:
    fl = rec["flow"]
    return FlowFeatures(
        flow=Flow(src=fl["src"], dst=fl["dst"], sport=fl["sport"],
                  dport=fl["dport"], proto=fl["proto"]),
        dscp=rec.get("dscp"), rx_bytes=rec.get("rx_bytes", 0),
        tx_bytes=rec.get("tx_bytes", 0), packets=rec.get("packets", 0),
        age_s=rec.get("age_s", 0.0),
        avg_packet_bytes=rec.get("avg_packet_bytes", 0.0),
        burstiness=rec.get("burstiness"), duty_cycle=rec.get("duty_cycle"),
        correction=rec.get("correction"),
    )


def load_corpus(path: Path) -> tuple[list[dict], str | None]:
    if not path.exists():
        return [], (f"no corpus file at {path} — run the live "
                    "corpus step (make corpus-collect) first")
    rows: list[dict] = []
    try:
        for line in path.read_text().splitlines():
            if line.strip():
                rows.append(json.loads(line))
    except json.JSONDecodeError as e:
        return [], f"corpus corrupt ({type(e).__name__}: {e})"
    return rows, None


def evaluate(corpus_path: Path, seed: int = 7) -> dict:
    rows, fatal = load_corpus(corpus_path)
    if fatal:
        return {"fatal": fatal}
    held = set()
    for r in rows:
        b = int(tuple_key(r), 16)
        # port-complete split: tuple halves, same rule every run
        if (b ^ seed) & 1:
            held.add(r["label"] + "\x1f" + tuple_key(r))
    fixed, heldout = [], []
    seen: set[str] = set()
    for r in rows:
        k = r["label"] + "\x1f" + tuple_key(r)
        if k in seen:        # one flow, one record: a duplicate tuple cannot
            continue         # represent the same flow twice without inflating
        seen.add(k)
        (heldout if k in held else fixed).append(r)
    if not fixed or not heldout:
        return {"fatal": f"corpus too small to split "
                f"(fixed={len(fixed)}, heldout={len(heldout)}; "
                f"need >=1 record in BOTH; collected {len(rows)} flows)"}

    corpus_classes = sorted({r["label"] for r in rows})
    out: dict = {
        "n_corpus": len(rows), "n_fixed": len(fixed),
        "n_heldout": len(heldout), "paths_fixed": FIXED_SOURCES,
        "corpus_classes": corpus_classes,
        "case_counts": {
            "canonical": sum(1 for r in rows if r.get("case") != "ambiguous"),
            "ambiguous": sum(1 for r in rows if r.get("case") == "ambiguous"),
        },
        "capacity_note":
            "capacity_mbps travels with each record; bulk is relative to it",
    }
    out["strict"] = _score(fixed + heldout, abstention=False)
    out["strict_fixed"] = _score(fixed, abstention=False)
    out["strict_heldout"] = _score(heldout, abstention=False)
    out["accept_abstain"] = _score(fixed + heldout, abstention=True)
    out["accept_abstain_fixed"] = _score(fixed, abstention=True)
    out["accept_abstain_heldout"] = _score(heldout, abstention=True)
    # PRIMARY claim (task4-params.md): the same splits under the declared BROAD
    # taxonomy. The score() above stays narrow side-by-side.
    out["broad"] = _score(fixed + heldout, abstention=False, broad=True)
    out["broad_fixed"] = _score(fixed, abstention=False, broad=True)
    out["broad_heldout"] = _score(heldout, abstention=False, broad=True)
    out["broad_accept_abstain"] = _score(fixed + heldout, abstention=True,
                                         broad=True)
    out["broad_accept_abstain_heldout"] = _score(heldout, abstention=True,
                                                 broad=True)
    rows_heldout = _rows(heldout)
    out["calibration_heldout"] = _calibration(rows_heldout)
    out["calibration_fixed"] = _calibration(_rows(fixed))
    out["confidently_wrong_heldout"] = _confidently_wrong(rows_heldout)
    conf = {}
    # the class universe is the committed collection plan: labels the plan
    # declares must appear in every per-class table even with support 0
    plan_labels = sorted({**g.CORPUS_PLAN, **g.AMBIGUOUS_PLAN})
    for target_name, part in (("confusion_full", fixed + heldout),
                              ("confusion_heldout", heldout)):
        # every corpus class present in the per-class table, support 0
        # included — an absent class must be visible, not silently averaged
        # out of honesty.
        conf[target_name] = _confusion(part, plan_labels)
    out.update(conf)
    return out


def _rows(records: list[dict]) -> list[dict]:
    got = []
    for r in records:
        trust = TrustStore()
        cl = classify(rebuild_features(r), r.get("capacity_mbps", 100.0),
                      trust)  # threshold set shipped; no tuning here
        got.append({
            "label": r["label"], "got": cl.cls.value if cl.cls else None,
            "label_broad": broad_class(r["label"]),
            "got_broad": broad_class(cl.cls.value) if cl.cls else None,
            "confidence": round(cl.confidence, 4),
            "tier": cl.tier, "evidence": cl.evidence,
            "flow": r["flow"], "capacity_mbps": r.get("capacity_mbps"),
        })
    return got


def _score(records: list[dict], abstention: bool, broad: bool = False) -> dict:
    rows = _rows(records)
    n = len(rows)
    right = wrong = ab = 0
    truth_key, got_key = (("label_broad", "got_broad") if broad
                          else ("label", "got"))
    for r in rows:
        truth, got = r[truth_key], r[got_key]
        if got == truth:
            right += 1
        elif got is None:
            if abstention:
                ab += 1
            else:
                wrong += 1
        else:
            wrong += 1
    return {
        "n": n, "correct": right, "abstained": ab, "confident_or_wrong": wrong,
        "accuracy_strict": (right / n) if n else None,
        "accuracy_excl_abstain":
            (right / (right + wrong)) if (right + wrong) else None,
    }


def _calibration(rows: list[dict]) -> list[dict]:
    """Predicted confidence vs realized accuracy, per declared bin."""
    bins = []
    for lo, hi in zip(BIN_EDGES, BIN_EDGES[1:]):
        top_incl = hi == BIN_EDGES[-1]
        sel = [r for r in rows if r["got"] is not None and
               (lo <= r["confidence"] < hi if not top_incl
                else lo <= r["confidence"] <= hi)]
        n = len(sel)
        correct = sum(1 for r in sel if r["got"] == r["label"])
        bins.append({
            "lo": lo, "hi": hi, "n": n, "correct": correct,
            "empirical_accuracy": round(correct / n, 4) if n else None,
            "mean_predicted": (round(sum(r["confidence"] for r in sel) / n, 4)
                               if n else None),
        })
    return bins


def _confidently_wrong(rows: list[dict]) -> list[dict]:
    """Every held-out flow the classifier confidently (>= 0.70) and wrongly
    put in a class, with the tuple it needs to be interrogable (declared cut:
    task4-params.md). Abstention is absent by construction."""
    wrong = []
    for r in rows:
        if r["got"] is not None and r["got"] != r["label"] \
                and r["confidence"] >= 0.70:
            fl = r["flow"]
            wrong.append({
                "label": r["label"], "got": r["got"], "confidence": r["confidence"],
                "proto": fl.get("proto"), "sport": fl.get("sport"),
                "dport": fl.get("dport"),
                "capacity_mbps": r.get("capacity_mbps"),
                "evidence": r.get("evidence"),
            })
    wrong.sort(key=lambda w: (-w["confidence"], w["label"]))
    return wrong


def _confusion(records: list[dict], all_classes: list[str] | None = None) -> dict:
    rows = _rows(records)
    classes = sorted({r["label"] for r in rows} |
                     {r["got"] for r in rows if r["got"]})
    if all_classes:
        classes = sorted(set(classes) | set(all_classes))
    conf = {t: {p: 0 for p in classes if p != t} | {t: 0}
            | {ABSTAIN: 0} for t in classes}
    for r in rows:
        truth = r["label"]
        conf[truth][r["got"] if r["got"] is not None else ABSTAIN] += 1
    per = {}
    for t in classes:
        tp = conf[t][t]
        fp = sum(conf[o].get(t, 0) for o in classes if o != t)
        fn = sum(conf[t].get(o, 0) for o in classes if o != t
                 ) + conf[t].get(ABSTAIN, 0)
        if tp + fn:
            rec = tp / (tp + fn)
            f1 = None
        else:
            # support 0: the class never appears — reported as absent, NOT
            # as a perfect score, so an unseen class cannot inflate the mean.
            rec = None
            f1 = None
        if tp + fp:
            prec = tp / (tp + fp)
        else:
            prec = None
            f1 = None
        if rec is not None and prec is not None and rec + prec:
            f1 = 2 * rec * prec / (rec + prec)
        per[t] = {"tp": tp, "fp": fp, "fn": fn,
                  "support": tp + fn,
                  "precision": prec, "recall": rec, "f1": f1}
    return {"classes": classes, "matrix": conf, "per_class": per}


def write_eval(out: Path, result: dict) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=1, sort_keys=False) + "\n")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", type=Path, default=ROOT / "data/experiments"
                    "/classifier_corpus/corpus.jsonl")
    ap.add_argument("--out", type=Path, default=ROOT / "data/experiments"
                    "/classifier_corpus/eval.json")
    a = ap.parse_args()
    result = evaluate(a.corpus)
    write_eval(a.out, result)
    if "fatal" in result:
        print(f"eval NOT ABLE to run: {result['fatal']}")
        print(f"(reason recorded in {a.out})")
        return 0
    broad = result["broad_heldout"]
    print(f"held-out BROAD strict acc: "
          f"{broad['accuracy_strict']:.3f} over n={broad['n']} "
          f"(primary, task4-params.md)")
    strict = result["strict_heldout"]
    print(f"held-out narrow strict acc: "
          f"{strict['accuracy_strict']:.3f} over n={strict['n']}")
    ab = result["broad_accept_abstain_heldout"]
    print(f"held-out broad accept-abstain acc: "
          f"{ab['accuracy_excl_abstain']} "
          f"(abstained {ab['abstained']}/{ab['n']})")
    bad: list[str] = []
    for cls, m in result["confusion_heldout"]["per_class"].items():
        if m["support"]:
            shown = (f"{m['f1']:.3f}" if m["f1"] is not None else "abstained")
            print(f"  {cls}: n={m['support']} f1={shown}")
            if m["f1"] is None or m["f1"] < 0.5:
                bad.append(cls)
        else:
            print(f"  {cls}: support 0 (not sampled held-out)")
    if bad:
        print("WEAK CLASSES (f1 < 0.5 or never correct) — reported as measured:",
              ", ".join(bad))
    print("eval.json ->", a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
