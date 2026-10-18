"""Rollback read-back verification.

**All tests in this file are MOCKED.** Every kernel interaction goes through
`FakeRunner`, a Python test double. These tests prove the *decision logic* --
that a rollback whose commands merely ran is not reported as successful, and
that an unverifiable read-back is not laundered into a pass. They prove nothing
about the behaviour of a real kernel; see
`docs/gap-closure/rollback-readback-verification.md` for the live integration
test that does.

The defect being guarded: `_rollback()` discarded every `runner.run()` return
value and returned `True` unconditionally, so a rollback that restored nothing
was indistinguishable from one that restored everything.
"""

from __future__ import annotations

import json
import re
import unittest

from aciq.policy import build_plan
from aciq.shield import Shield
from aciq.tc import build_tree, canon_classid, compare_states
from aciq.txn import (
    COMMANDS_FAILED,
    NO_TARGET,
    PARTIAL,
    UNVERIFIABLE,
    VERIFICATION_FAILED,
    VERIFIED,
    FakeRunner,
    RollbackResult,
    TransactionManager,
)

CAP = 100.0


def plan(cap=CAP, lease=None):
    return build_plan(cap, lease)


def readback_json(tree) -> str:
    out = []
    for c in tree.classes:
        out.append({"kind": "htb", "handle": c.classid,
                    "rate": int(round(c.rate_mbps * 1e6)),
                    "ceil": int(round(c.ceil_mbps * 1e6))})
    return json.dumps(out)


def CommitThen():
    """Commit a plan so a `_last_good` target exists, then swap the runner.

    Rollback is only reachable twice over: once to establish a known-good tree
    and once to have something to restore to. Committing with a healthy runner
    and then faulting a second one is the honest way to reach that state.
    """
    tm = TransactionManager(FakeRunner(auto_readback=True), Shield())
    tm.remember_capacity(CAP)
    out = tm.apply(plan())
    assert out.ok, out.reason
    assert tm._last_good is not None and tm._last_good_state is not None
    return tm


class TestCompareStates(unittest.TestCase):
    """The comparison rules the rollback verdict rests on."""

    def test_identical_states_match(self):
        s = {"1:10": {"rate": 6.0, "ceil": 6.0}}
        self.assertEqual(compare_states(s, dict(s)), ([], []))

    def test_zero_padded_handle_is_semantically_equivalent(self):
        """tc prints 1:0010 and 1:10 for the same class. Normalised, not failed."""
        e = {"1:10": {"rate": 6.0, "ceil": 6.0}}
        bad, unver = compare_states(e, {"1:0010": {"rate": 6.0, "ceil": 6.0}})
        self.assertEqual(bad, [])
        self.assertEqual(unver, [])

    def test_kernel_rounding_within_tolerance_is_not_a_defect(self):
        e = {"1:10": {"rate": 6.0, "ceil": 6.0}}
        bad, _ = compare_states(e, {"1:10": {"rate": 5.9997, "ceil": 6.0004}})
        self.assertEqual(bad, [])

    def test_rate_beyond_tolerance_is_a_mismatch(self):
        e = {"1:10": {"rate": 6.0, "ceil": 6.0}}
        bad, _ = compare_states(e, {"1:10": {"rate": 7.5, "ceil": 6.0}})
        self.assertEqual([(m.classid, m.field) for m in bad],
                         [("1:10", "rate")])

    def test_missing_class_is_a_mismatch_not_a_pass(self):
        bad, _ = compare_states({"1:10": {"rate": 6.0, "ceil": 6.0}}, {})
        self.assertEqual([m.field for m in bad], ["present"])

    def test_residual_class_is_reported(self):
        """An extra class means the prior state was not restored, even though
        every expected class is correct."""
        e = {"1:10": {"rate": 6.0, "ceil": 6.0}}
        bad, _ = compare_states(e, {"1:10": {"rate": 6.0, "ceil": 6.0},
                                    "1:20": {"rate": 4.0, "ceil": 4.0}})
        self.assertEqual([(m.classid, m.field) for m in bad],
                         [("1:20", "residual")])

    def test_invisible_field_is_unverifiable_not_matched(self):
        e = {"1:10": {"rate": 6.0, "ceil": 6.0}}
        bad, unver = compare_states(e, {"1:10": {"ceil": 6.0}})
        self.assertEqual(bad, [])
        self.assertEqual(unver, [("1:10", "rate")])

    def test_canon_classid_leaves_unrelated_shapes_alone(self):
        self.assertEqual(canon_classid("noqueue"), "noqueue")
        self.assertEqual(canon_classid("1:0"), "1:0")
        self.assertEqual(canon_classid(" 1:0010 "), "1:10")


class TestVerifiedRollback(unittest.TestCase):
    """1. commands ran AND the state matches."""

    def test_successful_rollback_is_verified(self):
        tm = CommitThen()
        tm.runner = FakeRunner(auto_readback=True)
        tree = build_tree(plan())
        tm._last_good = tm._last_good  # committed above
        res = tm._rollback()
        self.assertTrue(res.ok)
        self.assertEqual(res.outcome, VERIFIED)
        self.assertTrue(res)
        self.assertEqual(res.failed_commands, [])
        self.assertTrue(res.source.startswith("tc-"))


class TestCommandFailure(unittest.TestCase):
    """2, 11. a restore command the kernel refused."""

    def test_rollback_command_failure_is_not_success(self):
        tm = CommitThen()
        tm.runner = FakeRunner(auto_readback=True, fail_on="class add")
        res = tm._rollback()
        self.assertFalse(res.ok)
        self.assertIn(res.outcome, (COMMANDS_FAILED, PARTIAL))
        self.assertTrue(res.failed_commands)

    def test_cleanup_failure_alone_is_still_reported(self):
        """`tc qdisc del` failing is a cleanup failure, not a detail."""
        tm = CommitThen()

        class NoDel(FakeRunner):
            def run(self, argv):
                if "qdisc" in argv and "del" in argv:
                    self.commands.append(argv)
                    return 1, "", "cannot delete qdisc"
                return super().run(argv)

        tm.runner = NoDel(auto_readback=True)
        res = tm._rollback()
        self.assertFalse(res.ok)
        self.assertTrue(any("qdisc del" in f for f in res.failed_commands))

    def test_outcome_rolled_back_is_false_when_commands_failed(self):
        """The Outcome bool must follow the verification, not the attempt."""
        tm = CommitThen()
        tm.runner = FakeRunner(auto_readback=True, fail_on="class add")
        tree = build_tree(plan())

        # Let the first plan commit, then refuse every class add afterwards --
        # which is what makes the apply fail *and* the rollback fail, the case
        # where `rolled_back` used to be reported True regardless.
        class FailLater(FakeRunner):
            dels = 0
            rebuilding = False

            def run(self, argv):
                if "qdisc" in argv and "del" in argv:
                    self.dels += 1
                    if self.dels >= 2:
                        self.rebuilding = True
                if self.rebuilding and "class" in argv and "add" in argv:
                    self.commands.append(argv)
                    return 1, "", "injected apply failure"
                return super().run(argv)

        tm = TransactionManager(FailLater(auto_readback=True), Shield())
        tm.remember_capacity(CAP)
        self.assertTrue(tm.apply(plan()).ok)      # known-good baseline
        # Step past the shield's minimum change window, or the second apply is
        # deferred before it ever reaches the kernel -- which is correct
        # behaviour and would make this test prove nothing.
        out = tm.apply(plan(lease=None), now=tm.clock() + 60.0)
        self.assertFalse(out.ok)
        self.assertFalse(out.rolled_back)
        self.assertIsNotNone(out.rollback)
        self.assertFalse(out.rollback.ok)


class TestVerificationFailure(unittest.TestCase):
    """3, 7, 8. commands ran but the kernel is not in the target state."""

    def test_state_unchanged_after_restore_is_not_success(self):
        tm = CommitThen()
        tree = build_tree(plan())

        class Wrong(FakeRunner):
            def run(self, argv):
                joined = " ".join(argv)
                if "class" in argv and "add" in argv:
                    self.commands.append(argv)
                    # accept, but at half the rate the plan asked for
                    a = list(argv)
                    a[a.index("rate") + 1] = f"{CAP * 0.5:g}mbit"
                    return FakeRunner.run(self, tuple(a))
                return super().run(argv)

        tm.runner = Wrong(auto_readback=True)
        res = tm._rollback()
        self.assertFalse(res.ok)
        self.assertEqual(res.outcome, VERIFICATION_FAILED)
        self.assertTrue(res.mismatches)

    def test_residual_class_after_restore_is_detected(self):
        tm = CommitThen()

        class Residue(FakeRunner):
            def run(self, argv):
                if "class" in argv and "add" in argv and self.commands:
                    self.commands.append(argv)
                    super().run(argv)
                    # an extra class the plan never asked for
                    a = list(argv)
                    a[a.index("classid") + 1] = "1:99"
                    a[a.index("rate") + 1] = "1mbit"
                    a[a.index("ceil") + 1] = "1mbit"
                    extra = tuple(a)
                    return FakeRunner.run(self, extra)
                return super().run(argv)

        tm.runner = Residue(auto_readback=True)
        res = tm._rollback()
        self.assertFalse(res.ok)
        self.assertEqual(res.outcome, VERIFICATION_FAILED)
        self.assertTrue(any(m.field == "residual" for m in res.mismatches))

    def test_zero_padded_handles_do_not_trigger_a_false_mismatch(self):
        """The same state, printed the other way, must still verify."""
        tm = CommitThen()

        class Padded(FakeRunner):
            # Reuses the parent's realistic text output and only re-prints the
            # handle zero-padded, so the test exercises handle normalisation
            # rather than a hand-rolled parser fixture.
            def run(self, argv):
                if "class" in argv and "show" in argv and "-j" not in argv:
                    self.commands.append(argv)
                    rc, out, err = super().run(argv)
                    def pad(m):
                        return f"class htb 1:{m.group(1).zfill(4)}"
                    return rc, re.sub(r"class htb 1:(\d+)", pad, out), err
                return super().run(argv)

        tm.runner = Padded(auto_readback=True)
        res = tm._rollback()
        self.assertEqual(res.outcome, VERIFIED, res.reason)


class TestUnverifiable(unittest.TestCase):
    """4, 5. the state could not be inspected, or there is nothing to restore."""

    def test_empty_readback_is_unverifiable_not_a_pass(self):
        tm = CommitThen()
        tm.runner = FakeRunner(auto_readback=False, readback="")
        res = tm._rollback()
        self.assertFalse(res.ok)
        self.assertEqual(res.outcome, UNVERIFIABLE)
        self.assertIn("could not be confirmed", res.reason)

    def test_malformed_readback_is_unverifiable(self):
        tm = CommitThen()
        tm.runner = FakeRunner(auto_readback=False, readback="}{ not json [")
        res = tm._rollback()
        self.assertFalse(res.ok)
        self.assertEqual(res.outcome, UNVERIFIABLE)

    def test_missing_target_state_is_unverifiable(self):
        """Commands replayed with no description of the goal cannot be verified."""
        tm = CommitThen()
        tm._last_good_state = None
        tm.runner = FakeRunner(auto_readback=True)
        res = tm._rollback()
        self.assertFalse(res.ok)
        self.assertEqual(res.outcome, UNVERIFIABLE)
        self.assertIn("unknown", res.reason)

    def test_missing_interface_falls_back_to_safe_state(self):
        """No known-good tree: the ladder is tried and *verified* too."""
        tm = TransactionManager(FakeRunner(auto_readback=True), Shield())
        tm.remember_capacity(CAP)
        res = tm._rollback()
        self.assertTrue(res.ok)
        self.assertEqual(res.outcome, VERIFIED)
        self.assertIn("safe:", res.target)

    def test_safe_state_accepted_but_absent_is_not_success(self):
        class Liar(FakeRunner):
            def run(self, argv):
                if "qdisc" in argv and "show" in argv:
                    self.commands.append(argv)
                    return 0, "", ""          # claims installed, reports nothing
                return super().run(argv)

        tm = TransactionManager(Liar(auto_readback=True), Shield())
        tm.remember_capacity(CAP)
        self.assertFalse(tm.force_safe())
        self.assertIsNone(tm.safe_state_in_force)
        self.assertFalse(tm.last_rollback.ok)

    def test_no_rung_installable_is_reported(self):
        class Dead(FakeRunner):
            def run(self, argv):
                if "qdisc" in argv and "add" in argv:
                    self.commands.append(argv)
                    return 1, "", "kernel refuses every qdisc"
                return super().run(argv)

        tm = TransactionManager(Dead(auto_readback=True), Shield())
        tm.remember_capacity(CAP)
        res = tm.force_safe(result=True)
        self.assertFalse(res.ok)
        self.assertEqual(res.outcome, NO_TARGET)
        self.assertIn("ladder", res.reason)


class TestIdempotenceAndExceptions(unittest.TestCase):
    """10, 12, 13."""

    def test_repeated_rollback_converges_on_the_same_verdict(self):
        tm = CommitThen()
        tm.runner = FakeRunner(auto_readback=True)
        first = tm._rollback()
        second = tm._rollback()
        third = tm._rollback()
        self.assertEqual(first.outcome, VERIFIED)
        self.assertEqual(second.outcome, VERIFIED)
        self.assertEqual(third.outcome, VERIFIED)

    def test_repeated_rollback_on_unverifiable_stays_unverifiable(self):
        tm = CommitThen()
        tm.runner = FakeRunner(auto_readback=False, readback="")
        verdicts = {tm._rollback().outcome for _ in range(3)}
        self.assertEqual(verdicts, {UNVERIFIABLE})

    def test_exception_during_readback_is_not_swallowed(self):
        """A reader that explodes must not become a silent success."""
        tm = CommitThen()

        class Explode(FakeRunner):
            def run(self, argv):
                if "class" in argv and "show" in argv:
                    raise RuntimeError("tc exploded")
                return super().run(argv)

        tm.runner = Explode(auto_readback=True)
        with self.assertRaises(RuntimeError):
            tm._rollback()

    def test_original_error_is_preserved_when_rollback_also_fails(self):
        """The apply failure is the operator's first question; a bad rollback
        must not overwrite it."""
        tm = CommitThen()

        class Dead(FakeRunner):
            def run(self, argv):
                self.commands.append(argv)
                return 1, "", "injected total failure"

        tm.runner = Dead()
        out = tm.apply(plan(), now=tm.clock() + 60.0)
        self.assertFalse(out.ok)
        self.assertIn("injected total failure", out.reason)
        self.assertFalse(out.rolled_back)
        self.assertIsNotNone(out.rollback)
        self.assertFalse(out.rollback.ok)


class TestDiagnostics(unittest.TestCase):
    """14. the evidence must reach the audit log."""

    def test_failed_verification_is_recorded_in_the_audit(self):
        tm = CommitThen()

        class Wrong(FakeRunner):
            def run(self, argv):
                if "class" in argv and "add" in argv and self.commands:
                    self.commands.append(argv)
                    a = list(argv)
                    a[a.index("rate") + 1] = "1mbit"
                    return FakeRunner.run(self, tuple(a))
                return super().run(argv)

        tm.runner = Wrong(auto_readback=True)
        tm.apply(plan(), now=tm.clock() + 60.0)
        events = [e for e in tm.audit if e["event"].startswith("rollback_")]
        self.assertTrue(events, tm.audit)
        self.assertTrue(any(e["event"] == "rollback_verification_failed"
                            for e in events))
        bad = [e for e in events if e["event"] == "rollback_verification_failed"][0]
        self.assertTrue(bad["mismatches"])
        self.assertTrue(bad["reason"])

    def test_successful_rollback_is_recorded(self):
        tm = CommitThen()
        tm.runner = FakeRunner(auto_readback=True)
        tm._rollback()
        self.assertTrue(any(e["event"] == "rollback_verified" for e in tm.audit))

    def test_diagnostics_do_not_leak_the_environment(self):
        """The reason is written into an artefact. It must not carry a shell
        environment or credentials along with it."""
        tm = CommitThen()
        tm.runner = FakeRunner(auto_readback=False, readback="")
        res = tm._rollback()
        blob = " ".join([res.reason, str(res.failed_commands), str(res.source)])
        for leak in ("HOME", "PATH=", "TOKEN", "PASSWORD", "SECRET", "/home/"):
            self.assertNotIn(leak, blob)

    def test_rollback_result_is_falsey_only_when_not_verified(self):
        self.assertFalse(RollbackResult(False, VERIFICATION_FAILED))
        self.assertTrue(RollbackResult(True, VERIFIED))


if __name__ == "__main__":
    unittest.main()

class NoRatesBase(FakeRunner):
    """A reader that reports classes but never their rates."""

    def run(self, argv):
        if "class" in argv and "show" in argv:
            self.commands.append(argv)
            return 0, ("" if "-j" not in argv
                       else TestVacuousVerification.NO_RATE_READBACK), ""
        return super().run(argv)


class TestVacuousVerification(unittest.TestCase):
    """A comparison with nothing to compare must not read as a pass.

    Found by tracing where the rollback target comes from, as the brief asks:
    `_last_good_state` is the read-back captured at commit, and `verify()`
    deliberately tolerates fields the reader cannot see. So a commit under a
    reader that reports classes but no rates stores a baseline with **no
    comparable fields**, and `compare_states` then returns an empty mismatch
    list -- meaning "nothing was wrong", not "everything matched".
    """

    NO_RATE_READBACK = json.dumps(
        [{"kind": "htb", "handle": h} for h in ("1:1", "1:10", "1:20", "1:30")])

    def _blind_commit(self):
        tm = TransactionManager(NoRatesBase(), Shield())
        tm.remember_capacity(CAP)
        out = tm.apply(plan(), now=1000.0)
        self.assertTrue(out.ok)
        # the commit succeeded, but stored nothing comparable
        self.assertEqual(tm._last_good_state,
                         {"1:1": {}, "1:10": {}, "1:20": {}, "1:30": {}})
        return tm

    def test_a_baseline_with_no_comparable_fields_is_not_a_pass(self):
        tm = self._blind_commit()
        res = tm._rollback()
        self.assertFalse(res.ok)
        self.assertEqual(res.outcome, UNVERIFIABLE)
        self.assertIn("no comparable", res.reason)
        self.assertIn("not a match", res.reason)

    def test_outcome_rolled_back_is_false_when_nothing_was_comparable(self):
        """The verdict must reach Outcome.rolled_back, not just the audit log."""
        tm = self._blind_commit()

        class FailNext(NoRatesBase):
            """Same blind reader, but the next apply is refused."""
            def run(self, argv):
                if "class" in argv and "add" in argv and self.commands:
                    self.commands.append(argv)
                    return 1, "", "injected apply failure"
                return super().run(argv)

        tm.runner = FailNext()
        out = tm.apply(plan(), now=2000.0)
        self.assertFalse(out.ok)
        self.assertIsNotNone(out.rollback)
        self.assertEqual(out.rollback.outcome, UNVERIFIABLE)
        self.assertFalse(out.rolled_back,
                         "a rollback that compared nothing must not be "
                         "reported as rolled back")

    def test_a_partially_visible_baseline_still_verifies(self):
        """The fix must not reject a baseline where only *some* fields are
        invisible -- that is a weaker but genuine comparison."""
        tm = CommitThen()
        good = dict(tm._last_good_state)
        partial = {k: dict(v) for k, v in good.items()}
        first = sorted(partial)[0]
        partial[first] = {}                      # this class reports no rates
        tm._last_good_state = partial
        tm.runner = FakeRunner(auto_readback=True)
        res = tm._rollback()
        self.assertEqual(res.outcome, VERIFIED, res.reason)

    def test_comparable_pairs_counts_only_shared_fields(self):
        from aciq.txn import _comparable_pairs
        self.assertEqual(_comparable_pairs(
            {"1:10": {"rate": 6.0, "ceil": 6.0}}, {"1:10": {"rate": 6.0}}), 1)
        self.assertEqual(_comparable_pairs(
            {"1:10": {"rate": 6.0}}, {"1:10": {}}), 0)
        self.assertEqual(_comparable_pairs({}, {}), 0)
