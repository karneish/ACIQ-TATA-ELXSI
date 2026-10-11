"""Runs tests/test_rollback_live.py against an in-memory kernel double.

**No root, no `tc`, no namespaces.** This exists because the live module had
only ever *skipped*, so its own logic -- the runner protocol, the fault
injection, the assertions -- was completely unexercised. The first time it ran
for real, every test errored on `cannot unpack non-iterable CompletedProcess`.

The double speaks the real `tc`/`ip` CLI shapes, so the parsing under test is
the same code that runs against a kernel. What it does **not** prove is that a
real kernel behaves this way; `test_rollback_live.py` remains the only evidence
for that, and it must still be run under root.

A green run here means "the live test is not broken", not "rollback works".
"""

from __future__ import annotations

import io
import json
import types
import unittest
from unittest import mock

import tests.test_rollback_live as L


class Kernel:
    """Minimal model of `tc` qdisc/class state."""

    def __init__(self) -> None:
        self.qdiscs: dict[str, str] = {}
        self.classes: dict[str, dict[str, float]] = {}

    def clear(self) -> None:
        self.qdiscs.clear()
        self.classes.clear()


K = Kernel()


def _num(tok: str) -> float:
    return float(tok.rstrip("mbit"))


def fake_ns_run(*argv, check: bool = False):
    """Answer the subset of `tc` this module uses, in the real output shapes."""
    a = list(argv)
    kind = None
    if "qdisc" in a:
        kind = "qdisc"
    if "class" in a:
        kind = "class"

    def done(rc=0, out="", err=""):
        return types.SimpleNamespace(returncode=rc, stdout=out, stderr=err)

    if kind == "qdisc" and "del" in a:
        K.clear()
        return done()
    if kind == "qdisc" and "add" in a:
        if "handle" in a:
            h = a.index("handle") + 1
            K.qdiscs[a[h]] = a[h + 1] if h + 1 < len(a) else "?"
        return done()
    if kind == "qdisc" and "show" in a:
        return done(out="".join(f"qdisc {v} {h}: root refcnt 2\n"
                                for h, v in K.qdiscs.items()))
    if kind == "class" and "add" in a:
        cid = a[a.index("classid") + 1]
        K.classes[cid] = {"rate": _num(a[a.index("rate") + 1]),
                          "ceil": _num(a[a.index("ceil") + 1])}
        return done()
    if kind == "class" and "show" in a:
        if "-j" in a:
            return done(out=json.dumps(
                [{"kind": "htb", "handle": k, "rate": int(v["rate"] * 1e6),
                  "ceil": int(v["ceil"] * 1e6)} for k, v in K.classes.items()]))
        # Text is the primary reader in the real code, so model that shape.
        return done(out="".join(
            f"class htb {k} root prio 0 rate {v['rate']:g}Mbit "
            f"ceil {v['ceil']:g}Mbit burst 15Kb\n  Sent 0 bytes 0 pkt\n"
            for k, v in K.classes.items()))
    return done()


class TestLiveModuleAgainstADouble(unittest.TestCase):
    """Executes the real live tests, with only the kernel swapped out."""

    def setUp(self) -> None:
        K.clear()
        self._patches = [
            mock.patch.object(L, "_ns_run", fake_ns_run),
            mock.patch.object(L, "skip_reason", lambda: None),
            mock.patch.object(L, "CREATED", False, create=True),
            mock.patch.object(L, "NS", "fake", create=True),
            mock.patch.object(L, "DEV", "veth-t", create=True),
        ]
        for p in self._patches:
            p.start()
        # the module skips at import time via skipUnless(shutil.which("tc"));
        # re-select the class now that the gate is known to be irrelevant here
        if getattr(L.TestLiveRollback, "__unittest_skip__", False):
            L.TestLiveRollback.__unittest_skip__ = False

    def tearDown(self) -> None:
        for p in self._patches:
            p.stop()

    def _run_live_suite(self) -> unittest.TestResult:
        loader = unittest.TestLoader()
        suite = loader.loadTestsFromTestCase(L.TestLiveRollback)
        return unittest.TextTestRunner(
            stream=io.StringIO(), verbosity=0).run(suite)

    def test_the_live_tests_pass_against_a_faithful_double(self):
        res = self._run_live_suite()
        self.assertTrue(res.wasSuccessful(),
                        f"errors={[str(e) for e in res.errors]} "
                        f"failures={[str(f) for f in res.failures]}")

    def test_the_double_actually_exercises_the_tree(self):
        """Guards against the simulation silently degenerating into a no-op."""
        import aciq.tc
        from aciq.policy import build_plan
        tree = aciq.tc.build_tree(build_plan(100.0))
        L._ns_run("tc", "qdisc", "del", "dev", "veth-t", "root")
        for argv in aciq.tc.render(tree, dev="veth-t"):
            L._ns_run(*argv)
        state = L.tc_state()
        self.assertEqual(sorted(state),
                         sorted(c.classid for c in tree.classes))

    def test_live_module_is_gated_on_a_real_kernel(self):
        """The double must not have disabled the root gate for real runs."""
        src = open(L.__file__).read()
        self.assertIn("skipUnless", src)
        self.assertIn("not root", src)
        self.assertTrue(hasattr(L, "skip_reason"))


class TestLiveModuleHygiene(unittest.TestCase):
    """Static checks that would otherwise only fail on a real host."""

    def test_runner_protocol_returns_a_tuple(self):
        """The original bug: returning CompletedProcess broke every live test."""
        with mock.patch.object(L, "_ns_run", fake_ns_run), \
                mock.patch.object(L, "DEV", "veth-t", create=True):
            r = L.Runner().run(("tc", "qdisc", "show", "dev", "veth-t"))
        self.assertIsInstance(r, tuple)
        self.assertEqual(len(r), 3)
        self.assertIsInstance(r[0], int)

    def test_fault_injection_fires_only_once(self):
        """A fault that re-arms on the rollback's own `qdisc del` would break
        the restore the test exists to check."""
        with mock.patch.object(L, "_ns_run", fake_ns_run):
            K.clear()
            f = L.FlakyRunner({})
            f.run(("tc", "qdisc", "del", "dev", "veth-t", "root"))
            first = f.run(("tc", "class", "add", "dev", "veth-t",
                           "parent", "1:", "classid", "1:10",
                           "rate", "6mbit", "ceil", "6mbit"))
            self.assertNotEqual(first[0], 0, "fault never fired")
            f.run(("tc", "qdisc", "del", "dev", "veth-t", "root"))
            second = f.run(("tc", "class", "add", "dev", "veth-t",
                            "parent", "1:", "classid", "1:10",
                            "rate", "6mbit", "ceil", "6mbit"))
            self.assertEqual(second[0], 0,
                             "fault re-armed and broke the restore")

    def test_nested_runners_accept_the_state_argument(self):
        with mock.patch.object(L, "_ns_run", fake_ns_run):
            self.assertIsNotNone(L.FlakyRunner({}))
            self.assertIsNotNone(L.Runner())


if __name__ == "__main__":
    unittest.main()