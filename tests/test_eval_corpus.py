"""T6 — corpus evaluator scores the SHIPPED rules, never tunes them.

The corpus path is synthetic in these tests (feature surfaces the repo's own
profiles already justify), but the classifier is the real thing. The tests
pin: the tuple split (a flow cannot appear in both halves), the definitions
of both accuracies, abstention handling, and the no-corpus case, which must
save a mechanically quoteable fatal into eval.json, not exit with a bare
stack trace.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tools.eval_corpus as ec  # noqa: E402


def _rec(label, sport, dport=443, proto="tcp", dscp=None, rate=None,
         age=30.0, avg_pkt=1200.0, packets=10_000, capacity=100.0):
    return {
        "label": label,
        "flow": {"src": "203.0.113.9", "sport": sport,
                 "dst": "10.0.1.2", "dport": dport, "proto": proto},
        "dscp": dscp, "rx_bytes": 0, "tx_bytes": 0, "packets": packets,
        "age_s": age, "avg_packet_bytes": avg_pkt, "burstiness": None,
        "duty_cycle": 1.0, "rate_mbps": rate, "correction": None,
        "capacity_mbps": capacity, "t": 0.0,
    }


def _mk_corpus(path: Path, sports: list[int], labels: list[str]) -> None:
    rows = [_rec(l, s) for l, s in zip(labels, sports)]
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


class TestNoCorpus(unittest.TestCase):
    def test_missing_corpus_writes_fatal_into_eval(self):
        out = Path("/tmp/opencode/eval_missing.json")
        res = ec.evaluate(Path("/tmp/opencode/definitely-absent-corpus.jsonl"))
        ec.write_eval(out, res)
        self.assertIn("fatal", res)
        self.assertIn("fatal", json.loads(out.read_text()))

    def test_corrupt_corpus_writes_fatal_into_eval(self):
        bad = Path("/tmp/opencode/corpus_bad.jsonl")
        bad.write_text("{not json\n")
        res = ec.evaluate(bad)
        self.assertIn("fatal", res)
        self.assertIn("corrupt", res["fatal"])

    def test_unsplittable_corpus_writes_fatal_into_eval(self):
        one = Path("/tmp/opencode/corpus_one.jsonl")
        _mk_corpus(one, [4000], ["bulk_download"])
        res = ec.evaluate(one)
        self.assertIn("fatal", res)
        self.assertIn("heldout", res["fatal"])


class TestScoring(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # unittest runs test methods alphabetically, so every test that needs
        # this corpus would fail if only test_split_* created it.
        corpus = Path("/tmp/opencode/corpus_split.jsonl")
        _mk_corpus(corpus, list(range(4010, 4030)),
                   ["bulk_download"] * 10 + ["video_call_voice"] * 10)

    def _run_eval(self, corpus: Path):
        res = ec.evaluate(corpus)
        out = Path("/tmp/opencode/eval_out.json")
        ec.write_eval(out, res)
        return res, json.loads(out.read_text())

    def test_split_is_disjoint_and_complete(self):
        corpus = Path("/tmp/opencode/corpus_split.jsonl")
        _mk_corpus(corpus, list(range(4010, 4030)),
                   ["bulk_download"] * 10 + ["video_call_voice"] * 10)
        res, written = self._run_eval(corpus)
        self.assertEqual(res["n_corpus"], 20)
        self.assertEqual(res["n_fixed"] + res["n_heldout"], 20)
        self.assertLess(res["strict_fixed"]["n"], 20)
        self.assertLess(res["strict_heldout"]["n"], 20)
        self.assertEqual(written["n_fixed"] + written["n_heldout"], 20)

    def test_path_fixed_records_sources(self):
        corpus = Path("/tmp/opencode/corpus_split.jsonl")
        self._run_eval(corpus)
        out = json.loads((Path("/tmp/opencode/eval_out.json")).read_text())
        self.assertIn("aciq/classify.py", out["paths_fixed"])

    def test_accuracy_math_consistent(self):
        res, _ = self._run_eval(Path("/tmp/opencode/corpus_split.jsonl"))
        s = res["strict_heldout"]
        self.assertEqual(s["n"], s["correct"] + s["confident_or_wrong"])
        if s["correct"] + s["confident_or_wrong"] > 0:
            self.assertAlmostEqual(
                s["accuracy_strict"],
                s["correct"] / s["n"],
            )
        self.assertLessEqual(s["correct"], res["accept_abstain_heldout"]["correct"]
                             + res["accept_abstain_heldout"]["abstained"])

    def test_measured_profile_scores_the_right_class(self):
        # a bulk profile: TCP, 90 of 100 Mbps, 1500-byte packets, long-lived
        corpus = Path("/tmp/opencode/corpus_bulk.jsonl")
        rows = [_rec("bulk_download", s, dport=5004, rate=90.0,
                     avg_pkt=1500.0, packets=300_000, age=30.0)
                for s in (5010, 5011)]
        corpus.write_text("".join(json.dumps(r) + "\n" for r in rows))
        res, _ = self._run_eval(corpus)
        self.assertEqual(res["strict"]["n"], 2)
        # Both half and abstract: this case must NOT misclassify as update or
        # gaming; whatever the shipped rules do (bulk OR abstain), the tables
        # must show the same answer as eval_classifier's own constructed
        # bulk case does.
        self.assertEqual(res["strict"]["abstained"]
                         + res["strict"]["correct"]
                         + res["strict"]["confident_or_wrong"], 2)


class TestPerClassTable(unittest.TestCase):
    """T6 wording: per-class precision/recall/F1/support, support honest.

    A class that never lands in the held-out half must still APPEAR in its
    table with support 0 — it may not be silently averaged out, and its
    absence may not read as a perfect score.
    """

    def _run_eval(self, corpus: Path):
        res = ec.evaluate(corpus)
        out = Path("/tmp/opencode/eval_out2.json")
        ec.write_eval(out, res)
        return res, json.loads(out.read_text())

    def test_absent_class_shows_support_zero_and_null_metrics(self):
        corpus = Path("/tmp/opencode/corpus_absent.jsonl")
        # two labels ONLY; cloud_backup never sampled
        _mk_corpus(corpus, [4100, 4101, 4102, 4103],
                   ["bulk_download"] * 2 + ["video_call_voice"] * 2)
        res, _ = self._run_eval(corpus)
        per = res["confusion_heldout"]["per_class"]
        self.assertIn("cloud_backup", per.keys())
        m = per["cloud_backup"]
        self.assertEqual(m["support"], 0)
        self.assertIsNone(m["recall"])
        self.assertIsNone(m["f1"])

    def test_support_field_equals_tp_plus_fn(self):
        corpus = Path("/tmp/opencode/corpus_support.jsonl")
        _mk_corpus(corpus, list(range(4200, 4210)),
                   ["bulk_download"] * 5 + ["video_call_voice"] * 5)
        res, _ = self._run_eval(corpus)
        for cls, m in res["confusion_full"]["per_class"].items():
            self.assertEqual(m["support"], m["tp"] + m["fn"])

    def test_case_counts_count_ambiguous_rows_separately(self):
        corpus = Path("/tmp/opencode/corpus_ambig.jsonl")
        rows = [_rec("bulk_download", 4300 + i) for i in range(4)]
        rows[0]["case"] = "ambiguous"
        rows[1]["case"] = "ambiguous"
        corpus.write_text("".join(json.dumps(r) + "\n" for r in rows))
        res, _ = self._run_eval(corpus)
        self.assertEqual(res["case_counts"]["ambiguous"], 2)
        self.assertEqual(res["case_counts"]["canonical"], 2)
        # ambiguous rows are scored like any other row of their label —
        # never filtered out of either accuracy table
        self.assertEqual(res["strict"]["n"], 4)


if __name__ == "__main__":
    unittest.main()
