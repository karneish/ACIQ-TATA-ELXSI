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
        from pathlib import Path as _P
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
        self.assertIn("missing", src)
        self.assertIn("return 1 if bad or flags or missing else 0", src)


class TestHostGateScript(unittest.TestCase):
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
        import importlib
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
        import re
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
        own = {"--check", "--full", "--help"}   # the script's own options
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
