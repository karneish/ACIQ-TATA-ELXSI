"""Tests for the classifier evaluation harness (tools/eval_classifier.py).

The evaluation is a *claim*: "the classifier is X% accurate". These tests hold
the harness to its own honesty rules so the number cannot drift into flattery:

* the two corpora must be distinct (the tuned set and the independent set),
* every required abstention must be counted as such,
* the confusion matrix must agree with the per-class counts,
* coverage and accuracy-among-non-abstained must be internally consistent,
* accuracy must not be a property of the fixture's own arithmetic.
"""

from __future__ import annotations

import unittest

from tools.eval_classifier import (
    ABSTAIN,
    cases,
    evaluate,
    independent_cases,
)


class TestTheCorporaAreDistinct(unittest.TestCase):
    def test_the_independent_corpus_is_not_the_tuned_one(self):
        """Reporting accuracy only on the cases the rules were reasoned against
        would be reporting on the training set."""
        tuned = {c.name for c in cases()}
        indep = {c.name for c in independent_cases()}
        self.assertEqual(tuned & indep, set(), "corpora overlap")

    def test_the_independent_corpus_covers_both_protocols_and_families(self):
        """Protocol and IP-version coverage is the point of a second corpus."""
        feats = [c.feats for c in independent_cases()]
        protos = {f.flow.proto for f in feats}
        self.assertIn("tcp", protos)
        self.assertIn("udp", protos)
        srcs = [f.flow.src for f in feats]
        self.assertTrue(any(":" in s for s in srcs), "no IPv6 case in corpus")


class TestTheMetricsAreInternallyConsistent(unittest.TestCase):
    def test_the_confusion_matrix_matches_the_per_class_counts(self):
        r = evaluate("constructed", 100.0)
        for cls, v in r["per_class"].items():
            row = r["confusion"][cls]
            self.assertEqual(sum(row.values()), v["support"],
                             f"{cls}: matrix row != support")
            self.assertEqual(row[cls], v["tp"], f"{cls}: diagonal != tp")
            # fn is everything in the truth row that was not the correct class,
            # including abstentions.
            self.assertEqual(sum(c for k, c in row.items() if k != cls), v["fn"])

    def test_abstain_is_a_confusion_column(self):
        """A matrix that dropped abstentions would hide a should-have-been-
        classed miss off the diagonal."""
        r = evaluate("constructed", 100.0)
        for row in r["confusion"].values():
            self.assertIn(ABSTAIN, row)

    def test_coverage_and_accuracy_are_consistent(self):
        for corpus in ("constructed", "independent"):
            r = evaluate(corpus, 100.0)
            # accuracy among non-abstained >= accuracy on labelled, always:
            # abstaining can only remove difficult cases from the denominator.
            if r["coverage"] is not None and r["coverage"] < 1.0:
                self.assertGreaterEqual(r["accuracy_among_non_abstained"],
                                        r["accuracy_on_labelled"])

    def test_the_three_accuracies_use_the_stated_denominators(self):
        """Selective, end-to-end and flexible accuracy must be three different
        numbers whenever the classifier abstains on a labelled case. If they are
        ever silently equal on the independent corpus the abstention policy has
        been flattened and the report's three-way distinction is a fiction."""
        r = evaluate("independent", 100.0)
        self.assertEqual(r["selective_accuracy"], r["accuracy_among_non_abstained"])
        # End-to-end is strict: an accepted abstention is still an error there.
        self.assertLessEqual(r["end_to_end_accuracy"], r["accuracy_on_labelled"])
        # Coverage < 1 on this corpus, so the strict number is strictly lower.
        self.assertLess(r["coverage"], 1.0)
        self.assertLess(r["end_to_end_accuracy"], r["selective_accuracy"])

    def test_every_required_abstention_is_honoured(self):
        for corpus in ("constructed", "independent"):
            for cap in (100.0, 10.0):
                r = evaluate(corpus, cap)
                self.assertEqual(r["abstained_correctly"],
                                 r["abstention_required"],
                                 f"{corpus}@{cap}: a required abstention was "
                                 f"forced to a class")


class TestTheClassifierMeetsItsDocumentedBehaviour(unittest.TestCase):
    def test_no_high_confidence_errors_on_either_corpus(self):
        """A wrong call at >=0.7 confidence is the dangerous kind: it reaches
        enforcement looking confident."""
        for corpus in ("constructed", "independent"):
            for cap in (100.0, 10.0):
                r = evaluate(corpus, cap)
                self.assertEqual(r["high_confidence_errors"], 0,
                                 f"{corpus}@{cap}: {r['high_confidence_error_names']}")

    def test_accuracy_on_the_independent_corpus_is_honest(self):
        r = evaluate("independent", 100.0)
        # No labelled case may be misclassified. This is the hard invariant.
        self.assertEqual(r["accuracy_on_labelled"], 1.0)
        # Macro F1 is bounded, not pinned to 1.0: the independent corpus now
        # contains a boundary case (tiny DNS-over-TCP) for which abstention is an
        # accepted answer, which legitimately lowers recall for one class. A
        # corpus that scored 1.0 only by never containing a hard case would be a
        # weaker test, not a stronger one.
        self.assertGreaterEqual(r["macro_f1"], 0.95)
        self.assertEqual(r["high_confidence_errors"], 0)

    def test_by_ip_version_is_reported(self):
        r = evaluate("independent", 100.0)
        self.assertIn("v4", r["by_ip_version"])
        self.assertIn("v6", r["by_ip_version"])

    def test_by_protocol_is_reported(self):
        r = evaluate("constructed", 100.0)
        self.assertIn("tcp", r["by_protocol"])
        self.assertIn("udp", r["by_protocol"])


if __name__ == "__main__":
    unittest.main()
