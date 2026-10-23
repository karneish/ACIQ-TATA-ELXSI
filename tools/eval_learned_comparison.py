"""Phase 7: learned-vs-rules honesty evaluation on the SAME corpora.

The comparisons the classifer evaluator already renders belong to the RULES.
This adds the learned model (aciq.learned) evaluated on identical corpora,
identical skips, identical abstention rules, and prints the three-way
comparison an honest evaluation needs:

1. rules alone (the shipped classifier, re-run here for the same rows),
2. learned alone (the logistic model, fit on its synthetic set),
3. agreement + disagreement breakdown (which tier decided what).

NO FALSE CLAIMS: it is expected that the learned model cannot see
"software_update" vs "streaming" from the same features the rules use
(neither can the rules in most cases — they abstain); if it fails there it
is wrong with the rules, not deceptively. A learned model whose accuracy
BEATS the rules on `cases()` would deserve suspicion of overfitting the
corpus the rules were written against — which is exactly why the independent
corpus exists and is reported alongside.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from aciq.classify import TrustStore, classify  # noqa: E402

#: The trust store flags used by the classifer evaluator itself — the rules
#: comparison re-runs the SAME configuration the rules-only evaluation uses.
TRUST_DECAY = 0.5
TRUST_FLOOR = 0.25
from aciq.learned import LogisticClassifier  # noqa: E402
from aciq.model import TrafficClass  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
OUT_DIR = ROOT / "data" / "experiments"

ABSTAIN = None


def _score_rules(case, capacity_mbps: float):
    got = classify(case.feats, capacity_mbps, TrustStore(TRUST_DECAY, TRUST_FLOOR))
    return got.cls, got.confidence


def _score_learned(learned: LogisticClassifier, case, capacity_mbps: float):
    pred = learned.predict(case.feats, capacity_mbps)
    return pred.cls, pred.confidence


def evaluate_pair(cases, capacity_mbps: float) -> dict:
    learned = LogisticClassifier().fit()
    rows = []
    for case in cases:
        if (case.rate_relative_to is not None
                and abs(case.rate_relative_to - capacity_mbps) > 1e-6):
            continue
        r_cls, r_conf = _score_rules(case, capacity_mbps)
        l_cls, l_conf = _score_learned(learned, case, capacity_mbps)

        def correct(c):
            if case.truth is None:
                return c is None        # required abstention
            if case.accept_abstention and c is None:
                return True
            return c == case.truth

        rows.append({
            "name": case.name,
            "truth": case.truth.value if case.truth else None,
            "rules_cls": r_cls.value if r_cls else None,
            "rules_correct": correct(r_cls),
            "rules_conf": round(r_conf, 3),
            "learned_cls": l_cls.value if l_cls else None,
            "learned_correct": correct(l_cls),
            "learned_conf": round(l_conf, 3),
            "agree": (r_cls == l_cls),
        })
    def stats(which: str) -> dict:
        cls_key, conf_key = f"{which}_cls", f"{which}_conf"
        corr_key = f"{which}_correct"
        labelled = [r for r in rows if r["truth"] is not None]
        n = len(labelled) or 1
        wrong_confident = [r for r in labelled
                           if r[cls_key] is not None and not r[corr_key]
                           and r[conf_key] >= 0.7]
        return {
            "cases": len(rows),
            "accuracy_on_labelled": round(
                sum(1 for r in labelled if r[corr_key]) / n, 4),
            "high_conf_errors": len(wrong_confident),
            "abstains": sum(1 for r in rows if r[cls_key] is None),
        }
    rules = stats("rules")
    learned_s = stats("learned")
    return {
        "capacity_mbps": capacity_mbps,
        "rules": rules,
        "learned": learned_s,
        "agree_rate": round(
            sum(1 for r in rows if r["agree"]) / (len(rows) or 1), 4),
        "disagreements": [{"name": r["name"], "truth": r["truth"],
                           "rules": r["rules_cls"], "learned": r["learned_cls"]}
                          for r in rows if not r["agree"]],
        "high_conf_disagreements": [
            r for r in rows
            if not r["agree"] and max(r["rules_conf"], r["learned_conf"]) >= 0.7],
    }


def main() -> int:
    from eval_classifier import cases, independent_cases
    out = {}
    for corpus, source in (("constructed", cases),
                           ("independent", independent_cases)):
        for cap in (100.0, 10.0):
            key = f"{corpus}@{cap:g}mbps"
            out[key] = evaluate_pair(source(), cap)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "phase7_learned_vs_rules.json").write_text(
        json.dumps(out, indent=2))
    print(json.dumps({k: {"rules_acc": v["rules"]["accuracy_on_labelled"],
                          "learned_acc": v["learned"]["accuracy_on_labelled"],
                          "agree_rate": v["agree_rate"],
                          "disagreements": len(v["disagreements"])}
                      for k, v in out.items()}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
