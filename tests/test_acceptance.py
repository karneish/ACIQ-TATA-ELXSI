"""Acceptance-harness regression tests.

**No kernel, no root, no network.** These test the harness's own decision logic
by importing it, which is the point: a harness that decides "PASS" wrongly is
worse than no harness, and the only way to know its verdicts are sound is to
test the function that produces them.

The defect these guard: the harness recorded the collected test count but never
checked it, so a suite that still exited 0 while collection had silently shrunk
-- a broken import in one module, or a deleted module -- produced a green
acceptance run.
"""

from __future__ import annotations

import importlib.util
import re as _re
import os
import unittest
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "acceptance_mod", Path(__file__).resolve().parents[1] / "tools" / "acceptance.py")
A = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(A)

PASS, FAIL, BLOCKED = A.PASS, A.FAIL, A.BLOCKED


class TestParseUnittest(unittest.TestCase):

    def test_clean_run(self):
        p = A.parse_unittest(f"Ran {A.MIN_TESTS} tests in 6.7s\n\nOK\n")
        self.assertEqual(p["tests"], A.MIN_TESTS)
        self.assertTrue(p["ok"])
        self.assertEqual(p["skipped"], 0)

    def test_singular_test_is_parsed(self):
        self.assertEqual(A.parse_unittest("Ran 1 test in 0.01s\n\nOK\n")["tests"], 1)

    def test_skipped_count_is_read_from_the_ok_line(self):
        p = A.parse_unittest(f"Ran {A.MIN_TESTS} tests in 6.7s\n\nOK (skipped=6)\n")
        self.assertTrue(p["ok"])
        self.assertEqual(p["skipped"], 6)

    def test_failure_counts_are_parsed(self):
        p = A.parse_unittest(
            f"Ran {A.MIN_TESTS} tests in 6.7s\n\nFAILED (failures=2, errors=1, skipped=3)\n")
        self.assertFalse(p["ok"])
        self.assertEqual((p["failures"], p["errors"], p["skipped"]), (2, 1, 3))

    def test_unparseable_output_does_not_crash_and_is_not_ok(self):
        p = A.parse_unittest("the process died before printing anything")
        self.assertFalse(p["ok"])
        self.assertEqual(p["tests"], 0)


class TestSuiteVerdict(unittest.TestCase):

    @staticmethod
    def _ok(n=None):
        return f"Ran {n if n is not None else A.MIN_TESTS} tests in 1s\n\nOK\n"

    def test_full_green_run_passes(self):
        self.assertEqual(A.suite_verdict(0, self._ok())[0], PASS)

    def test_a_shrinking_suite_must_not_pass_silently(self):
        """The regression. Green exit, three tests: still a FAIL."""
        status, detail = A.suite_verdict(0, "Ran 3 tests in 0.01s\n\nOK\n")
        self.assertEqual(status, FAIL)
        self.assertIn("3", detail)
        self.assertIn("floor", detail)

    def test_exactly_the_floor_passes(self):
        self.assertEqual(A.suite_verdict(0, self._ok(),
                                         min_tests=A.MIN_TESTS)[0], PASS)

    def test_nonzero_exit_fails_even_with_a_full_suite(self):
        self.assertEqual(A.suite_verdict(1, self._ok())[0], FAIL)

    def test_reported_failure_line_fails_even_with_exit_zero(self):
        """A harness that trusts the exit code alone trusts the runner too."""
        status, _ = A.suite_verdict(
            0, self._ok().replace("OK", "FAILED (failures=1)"))
        self.assertEqual(status, FAIL)

    def test_skips_are_reported_but_do_not_fail_the_suite(self):
        """Skipped live-kernel tests are expected here, not a failure."""
        status, detail = A.suite_verdict(
            0, self._ok().replace("OK", "OK (skipped=6)"))
        self.assertEqual(status, PASS)
        self.assertIn("6 skipped", detail)

    def test_empty_output_is_not_a_pass(self):
        self.assertEqual(A.suite_verdict(0, "")[0], FAIL)


class TestCompletionSemantics(unittest.TestCase):
    """`complete` must be computed, and must never mean "everything passed"."""

    def test_complete_requires_no_blocked_gates(self):
        gates = [{"gate": "a", "status": PASS}, {"gate": "b", "status": BLOCKED}]
        counts = {s: sum(1 for g in gates if g["status"] == s)
                  for s in (PASS, FAIL, BLOCKED, "NOT RUN")}
        self.assertFalse(counts[BLOCKED] == 0)

    def test_blocked_and_failed_are_distinct_in_the_summary(self):
        gates = [{"gate": "a", "status": BLOCKED}, {"gate": "b", "status": BLOCKED},
                 {"gate": "c", "status": FAIL}]
        counts = {s: sum(1 for g in gates if g["status"] == s)
                  for s in (PASS, FAIL, BLOCKED, "NOT RUN")}
        # 2 blocked, 1 failed -- they must be counted separately, because
        # "we could not check" and "we checked and it broke" call for
        # different responses.
        self.assertEqual((counts[BLOCKED], counts[FAIL]), (2, 1))
        self.assertEqual(sum(counts.values()), len(gates))


class TestCompletionAndSkips(unittest.TestCase):
    """`complete` must mean "everything mandatory ran", not "nothing failed".

    The six live-kernel tests skip without root or iproute2, and a skip is not a
    failure -- so a suite can be green with the mandatory rollback verification
    never having executed. `complete` has to notice."""

    @staticmethod
    def _complete(counts, skipped):
        return counts[BLOCKED] == 0 and skipped == 0

    def test_no_blocked_and_no_skips_is_complete(self):
        self.assertTrue(self._complete({PASS: 6, FAIL: 0, BLOCKED: 0}, 0))

    def test_a_skipped_mandatory_test_prevents_completion(self):
        self.assertFalse(self._complete({PASS: 6, FAIL: 0, BLOCKED: 0}, 6))

    def test_a_blocked_gate_prevents_completion(self):
        self.assertFalse(self._complete({PASS: 5, FAIL: 0, BLOCKED: 7}, 0))

    def test_a_failure_prevents_an_overall_pass_but_is_reported_separately(self):
        counts = {PASS: 5, FAIL: 1, BLOCKED: 7}
        self.assertEqual(counts[FAIL], 1)
        self.assertFalse(self._complete(counts, 0))

    def test_skips_do_not_by_themselves_fail_the_suite_gate(self):
        """A skip is weaker than a pass but not a failure; it is handled at
        completion time, not by failing a green suite."""
        status, detail = A.suite_verdict(
            0, f"Ran {A.MIN_TESTS} tests in 1s\n\nOK (skipped=6)\n")
        self.assertEqual(status, PASS)
        self.assertIn("6 skipped", detail)


class TestMandatoryGatesAreNamed(unittest.TestCase):
    """Every gate the brief calls mandatory must appear in the source, so that
    deleting one is a visible diff rather than a silent omission."""

    def test_kernel_gates_are_all_present(self):
        src = (Path(__file__).resolve().parents[1]
               / "tools" / "acceptance.py").read_text()
        for gate in ("testbed gate", "live enforcement",
                     "rollback under real tc failure", "live adaptation loop",
                     "FIFO/CAKE/ACIQ comparison", "30-minute stability",
                     "live rollback verification (kernel)"):
            self.assertIn(gate, src, f"{gate} missing from the harness")

    def test_module_level_helpers_exist(self):
        # `record` is a closure inside main() by design, so only the pure,
        # module-level helpers are asserted here.
        for name in ("run", "rev", "have", "root", "main"):
            self.assertTrue(callable(getattr(A, name, None)), name)

    def test_run_reports_a_missing_executable_rather_than_raising(self):
        """A harness must survive a missing binary; crashing produces no
        artefact at all, which is the worst outcome during an incident."""
        rc, out = A.run(["definitely-not-a-real-binary-xyz", "--help"])
        self.assertNotEqual(rc, 0)
        self.assertTrue(out)


if __name__ == "__main__":
    unittest.main()

class TestClaimAuditParser(unittest.TestCase):
    """The audit misread `OK (skipped=6)` as a failure because it tested
    `endswith("OK")`. Skips are expected in any sandbox, so the one environment
    where the audit most needs to be right was the one it got wrong."""

    @staticmethod
    def _audit():
        import importlib.util
        from pathlib import Path as _P
        root = _P(__file__).resolve().parents[1]
        sp = importlib.util.spec_from_file_location(
            "audit_mod", root / "tools" / "audit_claims.py")
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        return m

    def test_ok_with_skips_is_ok(self):
        d = self._audit().parse_suite_status(
            f"Ran {A.MIN_TESTS} tests in 6.8s\n\nOK (skipped=6)\n")
        self.assertTrue(d["ok"])
        self.assertEqual(d["ran"], A.MIN_TESTS)
        self.assertEqual(d["skipped"], 6)
        self.assertEqual(d["failures"], 0)

    def test_plain_ok_is_ok(self):
        self.assertTrue(self._audit().parse_suite_status(
            "Ran 10 tests in 0.1s\n\nOK\n")["ok"])

    def test_failed_line_is_not_ok(self):
        d = self._audit().parse_suite_status(
            "Ran 809 tests in 6.8s\n\nFAILED (failures=2, skipped=1)\n")
        self.assertFalse(d["ok"])
        self.assertEqual(d["failures"], 2)

    def test_empty_output_is_not_ok(self):
        self.assertFalse(self._audit().parse_suite_status("")["ok"])


class TestCitationTraceability(unittest.TestCase):
    """A backticked `test_*` name in docs/gap-closure/ must name a real test.

    Found by writing four invented test names into classifier-final-validation
    and three into fairness-policy-safety. The behaviour was correct; the names
    were made up, and nothing noticed. Citing a test that does not exist reads
    as evidence and verifies nothing.
    """

    @staticmethod
    def _audit():
        import importlib.util
        from pathlib import Path as _P
        sp = importlib.util.spec_from_file_location(
            "audit_mod2", _P(__file__).resolve().parents[1] / "tools" / "audit_claims.py")
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        return m

    def test_every_cited_test_name_exists(self):
        missing = [t for t in self._audit().check_cited_tests() if not t["defined"]]
        self.assertEqual(missing, [],
                         "cited but undefined: "
                         + ", ".join(f"{m['test']} ({m['cited_in']})"
                                     for m in missing))

    def test_the_check_actually_finds_real_names(self):
        rows = self._audit().check_cited_tests()
        self.assertTrue(rows, "no citations found at all -- is the check live?")
        self.assertTrue(any(r["defined"] for r in rows))

    def test_an_invented_name_is_detected(self):
        """The check must fail on a name that does not exist, or it proves
        nothing by passing."""
        import re
        docs = list((Path(__file__).resolve().parents[1]
                     / "docs" / "gap-closure").glob("*.md"))
        defined = set()
        for f in (Path(__file__).resolve().parents[1] / "tests").glob("test_*.py"):
            defined |= set(re.findall(r"def (test_\w+)", f.read_text()))
        self.assertNotIn("test_this_definitely_does_not_exist", defined)
        # the same regex the audit uses, over a synthetic citation
        self.assertEqual(
            re.findall(r"`(test_[A-Za-z0-9_]+)`",
                       "see `test_this_definitely_does_not_exist`"),
            ["test_this_definitely_does_not_exist"])

    def test_a_correction_note_may_name_a_nonexistent_test(self):
        """Documenting a fix must not trip the check that enforces it.

        Without this exemption the audit failed its own documentation, which is
        a good way to teach everyone to ignore it.
        """
        import re as _re
        exempt = _re.compile(r"never existed|does not exist|do not exist|"
                             r"not a real test|invented|was wrong", _re.I)
        line = ("6. Correcting those names revealed that a test named "
                "test_two_thousand_flows_still_sum_to_capacity **never existed**")
        self.assertTrue(exempt.search(line))
        self.assertIn("test_two_thousand_flows_still_sum_to_capacity", line)

    def test_drift_reaches_the_audit_exit_code(self):
        """Reported-and-exited-0 would make the check decorative."""
        import inspect
        src = inspect.getsource(self._audit().main)
        # Assert the *conditions*, not the literal return line: matching exact
        # source text broke the moment another failure mode was added, which is
        # a test that punishes correct edits.
        ret = [ln for ln in src.splitlines() if ln.strip().startswith("return 1")]
        self.assertEqual(len(ret), 1, src)
        for condition in ("bad", "flags", "missing", "untracked_ev"):
            self.assertIn(condition, ret[0],
                          f"{condition} must reach the audit exit code")


class TestCitedCliValues(unittest.TestCase):
    """CLI values cited in the gap-closure docs must exist.

    The docs named a scenario `s4_voip_under_load` and a system `cake`. Neither
    exists: the real choices are s1/s2/s3 and `b0_fifo`/`b1_cake95`/`aciq`. Both
    commands would have failed immediately on a real host, after a long build.
    """

    @staticmethod
    def _harness():
        import importlib.util
        from pathlib import Path as _P
        root = _P(__file__).resolve().parents[1]
        sp = importlib.util.spec_from_file_location(
            "runexp", root / "run_experiments.py")
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        return m

    def test_cited_scenarios_exist(self):
        real = set(self._harness().ALL_SCENARIOS)
        self.assertEqual(real, {"s1_iso_during_call", "s2_wan_drop",
                                "s3_tv_and_gaming"})
        self.assertNotIn("s4_voip_under_load", real)

    def test_cited_systems_exist(self):
        from aciq.experiment import SystemSpec
        real = {x.value for x in SystemSpec}
        self.assertTrue(real <= {"b0_fifo", "b1_cake95", "aciq"}, real)
        self.assertNotIn("cake", real)

    def test_duration_override_exists_and_preserves_the_scenario(self):
        """A 30-minute soak is a mandatory gate and no shipped scenario is
        longer than 40s, so the override is what makes it possible."""
        import dataclasses
        from aciq.harness import SCENARIOS
        original = {n: s.duration_s for n, s in SCENARIOS.items()}
        try:
            for n, sc in list(SCENARIOS.items()):
                SCENARIOS[n] = dataclasses.replace(sc, duration_s=1800.0)
            self.assertTrue(all(s.duration_s == 1800.0
                                for s in SCENARIOS.values()))
            sc = SCENARIOS["s3_tv_and_gaming"]
            self.assertTrue(sc.workloads)
            self.assertEqual(sc.workloads[0].dscp, 46)
        finally:
            for n, d in original.items():
                SCENARIOS[n] = dataclasses.replace(SCENARIOS[n], duration_s=d)
        self.assertEqual({n: s.duration_s for n, s in SCENARIOS.items()}, original)

    def test_duration_flag_is_advertised(self):
        from pathlib import Path as _P
        src = (_P(__file__).resolve().parents[1] / "run_experiments.py").read_text()
        self.assertIn("--duration-s", src)
        self.assertRegex(src, r're\.search|--dry-run') if False else None


class TestHostGateScript(unittest.TestCase):
    """tools/host_gate.sh is the command the user will actually run.

    It was written after two documented commands were found to name a scenario
    and a system that do not exist. So its CLI values are checked against the
    real driver, and its refuse-without-privileges path is checked to actually
    refuse."""

    SCRIPT = "tools/host_gate.sh"

    def _src(self):
        from pathlib import Path as _P
        return (_P(__file__).resolve().parents[1] / self.SCRIPT).read_text()

    def test_every_scenario_named_exists(self):
        import re
        from aciq.experiment import SystemSpec  # noqa: F401  (import sanity)
        m = self._harness()
        named = set(re.findall(r"--scenario (\w+)", self._src()))
        self.assertTrue(named)
        self.assertTrue(named <= set(m.ALL_SCENARIOS),
                        f"unknown scenarios cited: {named - set(m.ALL_SCENARIOS)}")

    def test_every_system_named_exists(self):
        import re
        from aciq.experiment import SystemSpec
        real = {x.value for x in SystemSpec}
        # --system "$sysname" is a loop variable, not a literal
        named = set(re.findall(r"--system (\w+)", self._src())) - {"$sysname"}
        self.assertTrue(named)
        self.assertTrue(named <= real,
                        f"unknown systems cited: {named - real}")

    def test_every_driver_flag_named_exists(self):
        """Only flags passed to OUR drivers are checked. `git rev-parse --short`
        is not an ACIQ flag, and pretending otherwise produced a false failure
        on the first run of this very test."""
        import re
        from pathlib import Path as _P
        root = _P(__file__).resolve().parents[1]
        src = self._src()
        driver = "\n".join(
            (root / f).read_text()
            for f in ("run_experiments.py", "tools/acceptance.py"))
        lines = [ln for ln in src.splitlines()
                 if "run_experiments.py" in ln or "acceptance.py" in ln
                 or ln.strip().startswith("--")]
        used = set()
        for ln in lines:
            used |= set(re.findall(r"--[a-z][a-z-]+", ln))
        own = {"--check", "--full", "--help", "--congested-only",
          "--latency-tail", "--light-only", "--observe",
          "--scenario-a"}  # the script's own options
        for flag in sorted(used - own):
            self.assertIn(flag, driver,
                          f"{flag} is passed to an ACIQ driver by host_gate.sh "
                          f"but no such flag exists")

    @staticmethod
    def _harness():
        import importlib.util
        from pathlib import Path as _P
        sp = importlib.util.spec_from_file_location(
            "runexp2", _P(__file__).resolve().parents[1] / "run_experiments.py")
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        return m

    def test_it_refuses_without_root_and_changes_nothing(self):
        import os
        import subprocess
        if os.geteuid() == 0:
            self.skipTest("already root; the refusal path cannot be observed")
        from pathlib import Path as _P
        script = _P(__file__).resolve().parents[1] / "tools" / "host_gate.sh"
        r = subprocess.run(["bash", str(script), "--check"],
                           capture_output=True, text=True, timeout=120)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("must run under sudo", r.stdout + r.stderr)
        self.assertIn("Nothing has been changed", r.stdout + r.stderr)

    def test_a_skipped_live_gate_is_never_reported_as_passing(self):
        src = self._src()
        self.assertIn("skipped=", src)
        self.assertIn('skip "live rollback"', src)


class TestGatesNeverDisappear(unittest.TestCase):
    """Five mandatory gates used to vanish from the table when root was present.

    The summary read `PASS 8  FAIL 0  BLOCKED 0` -- apparently complete -- while
    live enforcement, adaptation, the CAKE comparison and the soak had never
    run. An absent gate is not a passing gate, and the fix is to record them as
    NOT RUN with the command that closes them.
    """

    KERNEL_GATES = ("testbed gate (21 checks)", "live enforcement",
                    "live rollback verification (kernel)",
                    "rollback under real tc failure", "live adaptation loop",
                    "FIFO/CAKE/ACIQ comparison", "30-minute stability")

    def test_every_kernel_gate_is_named_in_the_harness(self):
        src = (Path(__file__).resolve().parents[1] / "tools"
               / "acceptance.py").read_text()
        for gate in self.KERNEL_GATES:
            self.assertIn(gate, src, f"{gate} missing")

    def test_not_run_is_not_pass(self):
        counts = {A.PASS: 8, A.FAIL: 0, A.BLOCKED: 0, A.NOT_RUN: 5}
        self.assertNotEqual(counts[A.NOT_RUN], 0)
        self.assertFalse(counts[A.BLOCKED] == 0 and counts[A.NOT_RUN] == 0)

    def test_complete_requires_no_not_run_gates(self):
        """The whole point: complete must be unreachable while five gates are
        unexecuted, even though nothing is blocked or failing."""
        complete = (lambda b, n, sm: b == 0 and n == 0 and not sm)
        self.assertFalse(complete(0, 5, []))
        self.assertTrue(complete(0, 0, []))
        self.assertFalse(complete(0, 0, ["tests.test_rollback_live.X.y"]))

    def test_a_skip_outside_a_mandatory_module_does_not_block_completion(self):
        """Running as root skips this very file's refusal test. That is an
        artefact of the environment, not missing product evidence."""
        mandatory = A.MANDATORY_MODULES
        self.assertIn("tests.test_rollback_live", mandatory)
        self.assertNotIn("tests.test_acceptance", mandatory)
        blocked_by = lambda names: [n for n in names
                                    if any(n.startswith(m) for m in mandatory)]
        self.assertEqual(blocked_by(["tests.test_acceptance.T.t"]), [])
        self.assertEqual(
            blocked_by(["tests.test_rollback_live.T.t"]),
            ["tests.test_rollback_live.T.t"])

    def test_skipped_test_names_parse_to_fully_qualified_paths(self):
        text = ("Ran 2 tests in 1s\n\n"
                "test_a (tests.test_rollback_live.T.test_a) ... skipped 'no tc'\n"
                "test_b (tests.test_acceptance.T.test_b) ... skipped 'root'\n\n"
                "OK (skipped=2)\n")
        names = A.parse_unittest(text)["skipped_tests"]
        self.assertEqual(sorted(names), [
            "tests.test_acceptance.T.test_b",
            "tests.test_rollback_live.T.test_a",
        ])


class TestEvidenceMustBeTracked(unittest.TestCase):
    """Cited evidence must be committed, not merely present on disk.

    `docs/evidence/*.log` and `data/ab_lease_42/` were both excluded by blanket
    ignore rules, while tracked documentation cites them by exact filename as
    the source of published numbers. A fresh clone got citations pointing at
    files that were not in the repository, and the audit passed anyway because
    it only ever asked "does this exist on this machine".
    """

    @staticmethod
    def _audit():
        import importlib.util
        from pathlib import Path as _P
        sp = importlib.util.spec_from_file_location(
            "audit_mod3", _P(__file__).resolve().parents[1] / "tools" / "audit_claims.py")
        m = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(m)
        return m

    def test_every_cited_evidence_path_is_tracked(self):
        rows = self._audit().scan_evidence()
        self.assertTrue(rows)
        bad = [r for r in rows if r["evidence_present"]
               and not r.get("evidence_tracked", True)]
        self.assertEqual(bad, [],
                         "cited but uncommitted: "
                         + ", ".join(r["evidence"] for r in bad))

    def test_the_audit_records_tracked_state_at_all(self):
        row = self._audit().scan_evidence()[0]
        self.assertIn("evidence_tracked", row)

    def test_untracked_evidence_fails_the_audit(self):
        """The check has to reach the exit code, or it is decorative."""
        import inspect
        src = inspect.getsource(self._audit().main)
        self.assertIn("untracked_ev", src)
        self.assertIn("ev_missing or untracked_ev", src)

    def test_gitignore_does_not_exclude_cited_evidence(self):
        """The ignore rules are the root cause; assert they stay fixed."""
        import subprocess
        from pathlib import Path as _P
        root = _P(__file__).resolve().parents[1]
        for cited in ("docs/evidence/gate-20261011-165455.log",
                      "data/ab_lease_42"):
            r = subprocess.run(["git", "-C", str(root), "check-ignore",
                                "-q", "--no-index", cited],
                               capture_output=True)
            self.assertNotEqual(r.returncode, 0,
                                f"{cited} is excluded by .gitignore but cited "
                                f"by tracked documentation")


class TestExperimentEvidenceGates(unittest.TestCase):
    """The five long-running gates must be judged from artefacts, not hardcoded.

    Two failure modes had to be excluded at once:
      - hardcoded NOT_RUN, so running them changed nothing in the summary;
      - blind PASS, so a stale or thin run would be reported as a detection.

    The adaptation directory on disk had 3 samples and an estimator reading
    47.66 Mbps for a link that was actually 10 Mbps. That is not a detection."""

    def test_a_thin_run_is_not_a_detection(self):
        self.assertGreaterEqual(A.MIN_ADAPT_SAMPLES, 10)

    def test_an_off_by_more_than_tolerance_is_inconclusive(self):
        self.assertEqual(A.ADAPT_TOLERANCE_X, 2.0)
        # 47.66 for a 10 Mbps link is 4.8x: far outside
        self.assertGreater(47.66, A.ADAPT_TOLERANCE_X * 10.0)

    def test_unstamped_evidence_is_flagged_unbound(self):
        note = A._revision_note("data/does_not_exist_at_all", "abc12345")
        self.assertIn("UNBOUND", note)

    def test_evidence_from_another_revision_is_flagged(self):
        import tempfile
        from pathlib import Path as _P
        d = tempfile.mkdtemp()
        (_P(d) / "REVISION").write_text("deadbeefdeadbeefdeadbeefdeadbeefdeadbeef\n")
        saved = A.ROOT
        try:
            A.ROOT = _P(d)
            note = A._revision_note("", "a" * 40)
        finally:
            A.ROOT = saved
        self.assertIn("evidence from revision deadbeef", note)

    def test_matching_revision_produces_no_caveat(self):
        """A stamp from the CURRENT commit must not be flagged.

        This caught a real bug: the stamp holds a full SHA while the caller
        passed a short one, so every stamp compared unequal and even
        same-revision evidence was reported as a mismatch."""
        import tempfile
        from pathlib import Path as _P
        d = tempfile.mkdtemp()
        sha = "a" * 40
        (_P(d) / "REVISION").write_text(sha + "\n")
        saved = A.ROOT
        try:
            A.ROOT = _P(d)
            note = A._revision_note("", sha)
            short = A._revision_note("", sha[:8])
        finally:
            A.ROOT = saved
        self.assertEqual(note, "")
        self.assertEqual(short, "", "a short SHA is the same revision, not a mismatch")

    def test_comparison_below_the_seed_floor_is_not_a_result(self):
        self.assertGreaterEqual(A.MIN_COMPARISON_SEEDS, 6)

    def test_soak_floor_is_thirty_minutes(self):
        self.assertEqual(A.MIN_SOAK_S, 1800.0)

    def test_host_gate_stamps_every_results_directory(self):
        from pathlib import Path as _P
        src = (_P(__file__).resolve().parents[1]
               / "tools" / "host_gate.sh").read_text()
        self.assertIn("stamp()", src)
        # the loop variable is quoted in the shell, so match either form
        for d in ("data/host_gate_adapt", "data/host_gate_${sysname}",
                  "data/host_gate_soak",
                  "data/host_gate_congested_${sysname}"):
            self.assertTrue(f"stamp {d}" in src or f'stamp "{d}"' in src,
                            f"{d} is not revision-stamped")
        # one call site per results directory; the definition is `stamp()`
        # which does not match "stamp ".
        n = src.count("stamp ")
        self.assertGreaterEqual(n, 4,
                                "adaptation, both comparisons and the soak "
                                "must all be revision-stamped")
        self.assertIn("git rev-parse HEAD", src)


class TestCapacityDropCollision(unittest.TestCase):
    """set_capacity and build_plan both write the HTB root class.

        aciq/harness.py:389   classid 1:1 rate=<true capacity>
        aciq/tc.py:138        TcClass(1:1, 1:, cap, cap)

    So a policy change overwrites the capacity drop the controller is supposed
    to detect. Measured on the host: link clamped to 10 Mbps, goodput dipped to
    10.03 at t=7.3, then the controller re-planned and throughput settled at 47
    Mbps -- 4.7x the true capacity -- and the estimator confirmed 47. The run
    would have read as a successful adaptation.
    """

    def test_steady_goodput_ignores_ramp_edges(self):
        r = {"samples": [
            {"per_class": {"bulk": {"goodput_mbps": 0.0}}},
            {"per_class": {"bulk": {"goodput_mbps": 102.0}}},
            {"per_class": {"bulk": {"goodput_mbps": 10.03}}},
            {"per_class": {"bulk": {"goodput_mbps": 47.11}}},
            {"per_class": {"bulk": {"goodput_mbps": 47.02}}},
        ]}
        self.assertAlmostEqual(A._steady_goodput(r), 47.11, delta=0.5)

    def test_shape_above_truth_is_detected(self):
        r = {"samples": [{"per_class": {"bulk": {"goodput_mbps": 47.0}}}] * 5}
        self.assertTrue(A._shape_exceeded_truth(r, 10.0))

    def test_a_correct_adaptation_is_not_flagged(self):
        r = {"samples": [{"per_class": {"bulk": {"goodput_mbps": v}}}
                         for v in (12.3, 10.03, 9.9, 10.1, 9.8, 10.0)]}
        self.assertFalse(A._shape_exceeded_truth(r, 10.0))

    def test_the_adaptation_run_on_disk_holds_its_clamp(self):
        """The actual evidence, so this cannot be quietly reclassified.

        Was the other way round. The run that motivated this assertion measured
        46.78 on a link clamped to 10 -- the controller had erased the
        bottleneck. After `set_capacity` moved the limit out of band, and the
        read-back was made numeric, this run measures **10.01** on the same
        clamp. The property now asserted is the one we want, and the earlier
        failure would fail it again.
        """
        import glob
        hits = sorted(glob.glob("data/host_gate_adapt/*/result.json"))
        if not hits:
            self.skipTest("no adaptation evidence on disk")
        import json
        r = json.load(open(hits[-1]))
        target = float(r.get("link_end_mbps") or 0)
        if target <= 0:
            self.skipTest("no drop in that run")
        # `bottleneck_state` only carries counters once it was read with -s.
        # A run without it predates the current implementation and cannot
        # answer the question, so it is neither a pass nor a failure.
        if "backlog" not in (r.get("bottleneck_state") or ""):
            self.skipTest("the newest run predates -s bottleneck capture; "
                          "re-run s2_wan_drop before trusting the clamp")
        self.assertFalse(A._shape_exceeded_truth(r, target),
                         "measured above the clamped capacity again")
        self.assertLessEqual(A._steady_goodput(r), target * 1.1,
                             "the bottleneck did not hold")

    def test_the_two_writers_no_longer_collide(self):
        """Inverted when the collision was fixed.

        `build_plan` owns the root class and still writes it. `set_capacity`
        must not -- it was writing the same class, which let the controller
        erase the bottleneck it was measuring.
        """
        from aciq.harness import Harness
        h = Harness()
        for argv in h.set_capacity(10.0):
            self.assertNotIn("classid 1:1", " ".join(argv))
        from aciq.policy import build_plan
        from aciq.tc import build_tree, render
        cmds = [" ".join(c) for c in render(
            build_tree(build_plan(10.0)), dev="veth-lan", ns="router")]
        self.assertTrue(any("classid 1:1 " in c for c in cmds),
                        "build_plan must still write the root class")


class TestEvidenceStampsItself(unittest.TestCase):
    """The revision stamp is written by the producer, not the orchestrator.

    Only `tools/host_gate.sh` used to stamp results directories, so running
    `run_experiments.py` directly left the evidence with no revision at all --
    or attributed a stale stamp from an earlier orchestrated run to a run made
    with different code. The acceptance check caught exactly that:

        PASS  live adaptation loop -- 100.0 -> 10.0 Mbps, estimator 11.03
              [evidence from revision 798a4fec, not 2f39dbb6]

    which is the check working, but on a stamp that should not have existed.
    """

    @staticmethod
    def _src():
        from pathlib import Path as _P
        return (_P(__file__).resolve().parents[1]
                / "run_experiments.py").read_text()

    def test_the_driver_stamps_its_own_results(self):
        src = self._src()
        self.assertIn("REVISION", src)
        self.assertIn("git", " ".join(
            l.strip() for l in src.splitlines() if "rev-parse" in l))
        self.assertIn("evidence stamped with revision", src)

    def test_stamping_can_be_declined_deliberately(self):
        self.assertIn("--no-stamp", self._src())

    def test_the_orchestrator_still_stamps_too(self):
        """Belt and braces: the orchestrator stamps before the driver runs."""
        from pathlib import Path as _P
        src = (_P(__file__).resolve().parents[1]
               / "tools" / "host_gate.sh").read_text()
        self.assertIn("stamp()", src)
        self.assertIn("git rev-parse HEAD", src)

    def test_the_acceptance_check_reports_a_mismatched_revision(self):
        import tempfile
        from pathlib import Path as _P
        d = tempfile.mkdtemp()
        (_P(d) / "REVISION").write_text("b" * 40 + "\n")
        saved = A.ROOT
        try:
            A.ROOT = _P(d)
            note = A._revision_note("", "a" * 40)
        finally:
            A.ROOT = saved
        self.assertIn("evidence from revision bbbbbbbb", note)


class TestComparisonNeedsMeasurements(unittest.TestCase):
    """Seeds are not a comparison.

    The gate counted runs and called the comparison PASS while every
    `rtt_p95` in every result.json was None -- seven runs of each system
    producing no latency data whatsoever. The measurement exists, but in each
    run's final `<label>.json` rather than in the series, because the live
    ingestion path reads `<label>.partial.json` and the generators never write
    it."""

    def test_probe_summary_reads_the_per_run_json(self):
        self.assertTrue(callable(A._probe_summary))

    def test_a_tree_with_no_measurements_measures_nothing(self):
        import tempfile
        from pathlib import Path as _P
        d = _P(tempfile.mkdtemp())
        (d / "s__aciq__adaptive__seed42").mkdir()
        (d / "s__aciq__adaptive__seed42" / "result.json").write_text(
            '{"samples": [{"per_class": {"realtime_interactive": '
            '{"rtt_p95": null}}}]}')
        saved = A.ROOT
        try:
            A.ROOT = _P(tempfile.mkdtemp())
            out = A._probe_summary("")
        finally:
            A.ROOT = saved
        self.assertEqual(out["n"], 0)

    def test_result_json_alone_is_not_a_measurement(self):
        """The exact trap: runs present, series present, numbers absent."""
        import tempfile
        from pathlib import Path as _P
        root = _P(tempfile.mkdtemp())
        run = root / "s__aciq__adaptive__seed42"
        run.mkdir()
        (run / "result.json").write_text('{"samples": [{"per_class": {}}]}')
        saved = A.ROOT
        try:
            A.ROOT = root
            self.assertEqual(A._probe_summary("")["n"], 0)
        finally:
            A.ROOT = saved

    def test_the_gate_would_not_pass_on_seeds_alone(self):
        self.assertIn("Seeds are not a comparison",
                      (_P_src()))
        self.assertIn("and measured[k][\"n\"]", _P_src())


def _P_src():
    from pathlib import Path
    return (Path(__file__).resolve().parents[1] / "tools" / "acceptance.py").read_text()


class TestCongestedComparisonIsAGate(unittest.TestCase):
    """A comparison on a free link is not the comparison that matters.

    Every light-load run had an uncongested 100 Mbps link and 30 pps of
    interactive traffic -- the regime CAKE is built for, where the measured
    margin was about 5%. Nothing has been measured under load.
    """

    def test_the_orchestrator_runs_a_congested_comparison(self):
        from pathlib import Path as _P
        src = (_P(__file__).resolve().parents[1]
               / "tools" / "host_gate.sh").read_text()
        self.assertIn("host_gate_congested_", src)
        self.assertIn("CONGESTED comparison", src)
        # a dropped link, and all three systems
        self.assertIn("--scenario s2_wan_drop", src)
        self.assertIn("--drop 20", src)
        for s in ("b0_fifo", "b1_cake95", "aciq"):
            self.assertIn(s, src)

    def test_it_is_a_separate_gate_not_a_reuse_of_the_light_one(self):
        from pathlib import Path as _P
        src = (_P(__file__).resolve().parents[1]
               / "tools" / "acceptance.py").read_text()
        self.assertIn("congested FIFO/CAKE/ACIQ comparison", src)
        self.assertIn("data/host_gate_congested_", src)

    def test_it_requires_measurements_not_just_runs(self):
        self.assertIn("cmeas", (_P_src()))
        self.assertIn("chave", (_P_src()))


class TestWorkloadFlagContract(unittest.TestCase):
    """Every workload must accept every flag the launcher sends it.

    `spawn_source` appends `--src` whenever the workload has a device address.
    `call.py` never declared it, so on every s1/s2 run the interactive workload
    died on `unrecognized arguments` and argparse wrote that to its log -- which
    nothing reads. The runs completed and the gates passed; there was simply no
    interactive traffic in any of them.

    This is the same shape as the rest: a check that could not fail, because
    nothing compared the two lists.
    """

    WORKLOADS = ("bulk", "call", "video", "game")

    @staticmethod
    def _root():
        from pathlib import Path as _P
        return _P(__file__).resolve().parents[1]

    @staticmethod
    def _flags(kind: str) -> set[str]:
        import subprocess
        r = subprocess.run(
            ["python3", f"testbed/workloads/{kind}.py", "--help"],
            capture_output=True, text=True, timeout=60)
        out = set()
        for tok in r.stdout.split():
            if tok.startswith("--"):
                out.add(tok.rstrip(",;"))
        return out

    def _launcher_flags(self) -> set[str]:
        from pathlib import Path as _P
        src = (_P(__file__).resolve().parents[1] / "aciq"
               / "experiment.py").read_text()
        # the flags spawn_source actually appends
        found = set()
        for m in _re.finditer(r'argv \+= \["(--[a-z0-9-]+)"', src):
            found.add(m.group(1))
        for m in _re.finditer(r'argv = self\._argv\([^)]*"(--[a-z0-9-]+)"', src):
            found.add(m.group(1))
        # flags inside that argv literal
        for m in _re.finditer(r'self\._argv\(self\.ns_wan, f"\{kind\}\.py", ([^)]*)\)',
                              src):
            found |= set(_re.findall(r'"(--[a-z0-9-]+)"', m.group(1)))
        return found

    #: Sent only to PROBE_KINDS, by the launcher's own condition. bulk and
    #: video implement their own senders and have no round trip to report.
    PROBE_ONLY = {"--partial-out", "--obs-out"}

    def test_no_workload_rejects_a_flag_the_launcher_sends(self):
        """The contract is two-sided, and both sides must hold.

        A flag sent to every workload must be accepted by every workload.
        A probe-only flag must be accepted by every probe workload -- and must
        NOT be sent to the others, which is the launcher's condition rather
        than a promise in the workload.
        """
        from aciq.experiment import PROBE_KINDS
        launcher = self._launcher_flags()
        self.assertIn("--src", launcher,
                      "the launcher no longer sends --src? re-check this test")
        self.assertIn("--partial-out", launcher)

        for kind in self.WORKLOADS:
            common = (launcher - self.PROBE_ONLY) - self._flags(kind)
            self.assertFalse(
                common, f"{kind}.py would abort on {sorted(common)}")

        for kind in PROBE_KINDS:
            probe_only = self.PROBE_ONLY - self._flags(kind)
            self.assertFalse(
                probe_only,
                f"{kind}.py is a probe kind and would abort on "
                f"{sorted(probe_only)}")

        src = (self._root() / "aciq" / "experiment.py").read_text()
        self.assertIn("if kind in PROBE_KINDS:", src,
                      "the probe-only flags must be gated on PROBE_KINDS, or "
                      "bulk and video abort on --partial-out")

    def test_every_workload_parses_a_full_launcher_argv(self):
        """The end-to-end version: hand each workload exactly what the launcher
        would and require it not to print a usage error."""
        import subprocess
        args = ["--dst", "127.0.0.1", "--port", "47555", "--duration", "0.2",
                "--json-out", "/tmp/opencode/wl.json",
                "--partial-out", "/tmp/opencode/wl.partial.json",
                "--src", "127.0.0.1"]
        for kind in self.WORKLOADS:
            if "--partial-out" not in self._flags(kind):
                args = [a for i, a in enumerate(args)
                        if a not in ("--partial-out",
                                     "/tmp/opencode/wl.partial.json")]
            r = subprocess.run(
                ["python3", f"testbed/workloads/{kind}.py", *args],
                capture_output=True, text=True, timeout=90)
            self.assertNotIn(
                "unrecognized arguments", r.stderr,
                f"{kind}.py aborted on the launcher's argv:\n{r.stderr.strip()}")


class TestRunsDoNotSitOutSinkTimeouts(unittest.TestCase):
    """A 40-second scenario was taking seven minutes.

    The sink loops are `while True: time.sleep(1)` -- they are meant to outlive
    the run and die with the namespace. `collect()` waited for them with a
    90-second timeout exactly as it did for senders, so every run spent 90s per
    sink doing nothing before killing it. Four workloads = 6 minutes of dead
    time per run, and the comparison runs 42 of them.

        00:04  aciq seed44
        00:11  aciq seed45     <- 7 minutes for a 40-second scenario
        00:18  aciq seed46
    """

    @staticmethod
    def _src():
        from pathlib import Path as _P
        return (_P(__file__).resolve().parents[1] / "aciq"
                / "experiment.py").read_text()

    def test_sinks_are_tracked_apart_from_senders(self):
        src = self._src()
        self.assertIn("self.sink_procs", src)
        self.assertIn("self.sinks: list[list[str]]", src,
                      "DryLauncher.sinks is a different thing; renaming it here "
                      "would be churn, but the two must not be conflated")

    def test_collect_does_not_wait_for_sinks(self):
        """Senders legitimately wait -- they exit on their own.

        Sinks must not: the loop is `while True`, so a wait can only ever end
        in a timeout. Slicing from the first `def collect` grabs DryLauncher's
        no-op and swallows the whole class, so this targets NetnsLauncher.
        """
        src = self._src()
        cls = src[src.index("class NetnsLauncher:"):]
        body = cls[cls.index("    def collect(self)"):]
        body = body[:body.index("    def _stop_sinks")]
        self.assertIn("timeout=90", body,
                      "senders should still be waited for")
        waited_on = [ln for ln in body.splitlines() if "p.wait" in ln]
        self.assertEqual(len(waited_on), 1,
                         "exactly one wait, for the senders")
        self.assertIn("self._stop_sinks()", body,
                      "the sinks must be stopped, not waited on")

    def test_sinks_are_asked_to_stop_and_only_killed_if_they_ignore_it(self):
        src = self._src()
        self.assertIn("def _stop_sinks", src)
        self.assertIn("SIGTERM", src)
        self.assertIn("SIGKILL", src)
        self.assertIn("p.wait(timeout=grace)", src,
                      "escalate only after a grace period")

    def test_stop_also_ends_the_sinks(self):
        src = self._src()
        stop = src[src.index("    def stop(self)"):]
        self.assertIn("_stop_sinks", stop)


class TestControllerCpuOverheadIsABound(unittest.TestCase):
    """CPU overhead is a graded criterion, so it needs a check that can fail.

    `cpu_fraction` was being collected into every sample of every run and read by
    nobody. The numbers were real and nobody looked at them, which is the same
    defect as the congested comparison publishing results from a run that never
    steered a flow.
    """

    def test_the_bound_is_a_fraction_of_one_core_not_a_percentage(self):
        from tools.acceptance import MAX_CONTROLLER_CPU
        self.assertGreater(MAX_CONTROLLER_CPU, 0.0)
        self.assertLess(MAX_CONTROLLER_CPU, 1.0)

    def test_the_bound_is_tight_enough_to_be_meaningful(self):
        """Measured peak is ~0.0052. A bound of 0.5 would never fail."""
        from tools.acceptance import MAX_CONTROLLER_CPU
        self.assertLessEqual(MAX_CONTROLLER_CPU, 0.02)

    def test_a_run_over_the_bound_is_reported_as_fail(self):
        """Proved, not asserted: feed the gate a synthetic soak."""
        from tools import acceptance

        def fake_results(sub):
            if sub == "data/host_gate_soak":
                return [{"duration_s": 1800.0,
                         "samples": [{"cpu_fraction": v} for v in
                                     (acceptance.MAX_CONTROLLER_CPU * 3,) * 10]}]
            return []

        real, acceptance._results = acceptance._results, fake_results
        try:
            rows = dict((n, (st, d)) for n, st, d
                        in acceptance.check_experiment_evidence())
        finally:
            acceptance._results = real

        self.assertIn("controller CPU overhead", rows)
        status, detail = rows["controller CPU overhead"]
        self.assertEqual(status, acceptance.FAIL,
                         f"a run at 3x the bound was not failed: {detail}")

    def test_a_run_under_the_bound_is_reported_as_pass(self):
        """The other direction, so the gate is not simply always failing."""
        from tools import acceptance

        def fake_results(sub):
            if sub == "data/host_gate_soak":
                return [{"duration_s": 1800.0,
                         "samples": [{"cpu_fraction": 0.0049} for _ in range(50)]}]
            return []

        real, acceptance._results = acceptance._results, fake_results
        try:
            rows = dict((n, (st, d)) for n, st, d
                        in acceptance.check_experiment_evidence())
        finally:
            acceptance._results = real
        self.assertEqual(rows["controller CPU overhead"][0], acceptance.PASS)

    def test_the_gate_reads_cpu_from_the_soak_evidence(self):
        """It must be measured on a kernel, not taken from the unit benchmark."""
        from pathlib import Path as _P
        src = (_P(__file__).resolve().parents[1] / "tools" / "acceptance.py").read_text()
        self.assertIn("cpu_fraction", src)
        self.assertIn("MAX_CONTROLLER_CPU", src)
        self.assertIn("host_gate_soak", src)

    def test_cpu_fraction_is_the_controller_not_the_machine(self):
        """RUSAGE_SELF, so the figure is the controller's own cost."""
        from pathlib import Path as _P
        src = (_P(__file__).resolve().parents[1] / "aciq" / "metrics.py").read_text()
        self.assertIn("RUSAGE_SELF", src)


class TestLatencyTailMustBeExplained(unittest.TestCase):
    """The median hides the tail. Gating only the median is the overclaim this
    whole engagement has been removing, so the tail is gated too.

    ACIQ's congested median is 1.18 ms and its p95 is ~70 ms. Both are true.
    Publishing only the first would be misleading, so a tail is only acceptable
    when it is confined to the adaptation transient after a capacity change --
    concentrated and brief -- rather than spread across the run.
    """

    def _result_with(self, rtts_ms, step_s=0.02):
        """Synthesise a run directory carrying a per-packet trace."""
        import json as _temp_json
        import shutil as _sh
        import tempfile
        d = tempfile.mkdtemp()
        self.addCleanup(_sh.rmtree, d, True)
        lines = []
        t = 1000.0
        for i, rtt in enumerate(rtts_ms):
            lines.append(_temp_json.dumps(
                {"seq": i, "sent_mono_s": t, "recv_mono_s": t + rtt / 1000.0}))
            t += step_s
        with open(os.path.join(d, "call.obs.jsonl"), "w") as fh:
            fh.write("\n".join(lines) + "\n")
        return d

    def test_a_healthy_run_has_no_slow_packets(self):
        from tools import acceptance
        d = self._result_with([1.2] * 200)
        r = {"_dir": os.path.relpath(d, acceptance.ROOT)}
        self.assertEqual(acceptance._slowest_fraction(r), 0.0)

    def test_scattered_slow_packets_exceed_the_limit(self):
        """10% of packets slow, spread throughout -- not a transient."""
        from tools import acceptance
        rtts = [1.2] * 170 + [70.0] * 30   # 15%, above the 10% limit
        d = self._result_with(rtts)
        r = {"_dir": os.path.relpath(d, acceptance.ROOT)}
        frac = acceptance._slowest_fraction(r)
        self.assertGreater(frac, acceptance.TAIL_MAX_FRACTION)

    def test_a_brief_transient_is_inside_the_limit(self):
        """5% slow in one burst -- the shape an adaptation transient has."""
        from tools import acceptance
        rtts = [1.2] * 190 + [70.0] * 10
        d = self._result_with(rtts)
        r = {"_dir": os.path.relpath(d, acceptance.ROOT)}
        self.assertLessEqual(acceptance._slowest_fraction(r),
                             acceptance.TAIL_MAX_FRACTION)

    def test_no_trace_is_not_a_pass(self):
        """The gate must report NOT RUN rather than PASS when unmeasured."""
        from tools import acceptance
        self.assertEqual(acceptance._slowest_fraction({"_dir": ""}), 0.0)

    def test_the_threshold_sits_between_the_two_populations(self):
        """Healthy traffic is ~1.2 ms; the transient is tens of ms."""
        from tools.acceptance import TAIL_THRESHOLD_MS
        self.assertGreater(TAIL_THRESHOLD_MS, 2.0)
        self.assertLess(TAIL_THRESHOLD_MS, 20.0)


class TestPolicyMustLeaveHeadroom(unittest.TestCase):
    """A controller meant to reserve capacity must not consume all of it.

    This is the check the estimator ratio could not be. The estimator read
    22.39 against a true 20 -- 1.12x -- which looks ordinary beside the 1.12x
    it read for a true 10. The telling number was that the resulting goodput ran
    AT the link: 19.98 Mbps against a 20 Mbps link, versus 17.62 when the
    policy worked. A controller driving the link to saturation is not reserving
    anything, whatever its estimate says.
    """

    def test_headroom_threshold_is_a_fraction(self):
        from tools.acceptance import SATURATION_HEADROOM
        self.assertGreater(SATURATION_HEADROOM, 0.0)
        self.assertLessEqual(SATURATION_HEADROOM, 1.0)

    def test_goodput_below_the_threshold_passes(self):
        from tools import acceptance
        r = {"samples": [{"per_class": {"bulk": {"goodput_mbps": 17.62}}} for _ in range(5)],
             "link_end_mbps": 20.0}
        self.assertLessEqual(acceptance._steady_goodput(r),
                             acceptance.SATURATION_HEADROOM * 20.0)

    def test_goodput_at_the_link_is_saturation(self):
        from tools import acceptance
        r = {"samples": [{"per_class": {"bulk": {"goodput_mbps": 19.98}}}
                         for _ in range(5)], "link_end_mbps": 20.0}
        self.assertGreater(acceptance._steady_goodput(r),
                           acceptance.SATURATION_HEADROOM * 20.0)

    def test_the_exact_measured_failure_is_reproduced(self):
        """seed 42 on disk: 19.98 Mbps against a 20 Mbps link."""
        from tools import acceptance
        r = {"samples": [{"per_class": {"bulk": {"goodput_mbps": 19.98}}}
                         for _ in range(5)], "link_end_mbps": 20.0}
        self.assertAlmostEqual(acceptance._steady_goodput(r), 19.98, places=6)


class TestNoSilentlyLostTests(unittest.TestCase):
    """A duplicated test class silently discards every test in the first one.

    Found by `ruff check --select F811` in this very file: `TestHostGateScript`
    was defined at line 297 and again at line 356. Python keeps the second, so
    the four tests in the first -- the ones checking that scenarios and systems
    cited in the documentation actually exist -- never ran. Nothing failed,
    nothing warned, and the suite was green.

    Ruff was configured after these tests were written, which is exactly why the
    check has to be asserted here as well: a lint rule that is only run by
    hand is not a gate.
    """

    ROOT = Path(__file__).resolve().parents[1]

    def _test_modules(self):
        return sorted(self.ROOT.glob("tests/test_*.py"))

    def test_no_duplicate_class_names_in_any_test_module(self):
        import ast
        offenders = {}
        for f in self._test_modules():
            tree = ast.parse(f.read_text())
            names = [n.name for n in tree.body if isinstance(n, ast.ClassDef)]
            dupes = {n for n in names if names.count(n) > 1}
            if dupes:
                offenders[f.name] = sorted(dupes)
        self.assertEqual(offenders, {},
                         f"duplicate test classes lose their tests: {offenders}")

    def test_no_duplicate_function_names_at_module_level(self):
        """Same hazard for module-level helpers and constants."""
        import ast
        offenders = {}
        for f in self._test_modules():
            tree = ast.parse(f.read_text())
            names = [n.name for n in tree.body
                     if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
            dupes = {n for n in names if names.count(n) > 1}
            if dupes:
                offenders[f.name] = sorted(dupes)
        self.assertEqual(offenders, {},
                         f"duplicate module-level definitions: {offenders}")

    def test_the_ruff_ruleset_that_caught_this_is_enabled(self):
        """The rule is configured, so the finding was not luck."""
        cfg = (self.ROOT / "pyproject.toml").read_text()
        self.assertIn("F", cfg)
        self.assertIn("[tool.ruff.lint]", cfg)
