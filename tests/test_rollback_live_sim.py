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

    #: Off by default because the host does not honour it; see the note below.
    json_mode = False

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
        # A veth reverts to the kernel default, not to nothing at all.
        K.qdiscs["0:"] = "noqueue"
        return done()
    if kind == "qdisc" and "add" in a:
        # A root qdisc REPLACES any existing root. Leaving `noqueue` behind
        # alongside the new one modelled two simultaneous roots, which the
        # kernel never has -- and made the helper report the stale default.
        if "root" in a:
            K.qdiscs = {}
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
        # MEASURED on the real host (iproute2 6.1.0, kernel 7.1.5): `tc -j`
        # is accepted but still prints TEXT. This double used to return JSON
        # for `-j`, which is why it passed while the live test failed for
        # three real tests -- the double was not faithful, and a double that
        # is not faithful is worse than none, because it certifies.
        if "-j" in a and K.json_mode:
            return done(out=json.dumps(
                [{"kind": "htb", "handle": k, "rate": int(v["rate"] * 1e6),
                  "ceil": int(v["ceil"] * 1e6)} for k, v in K.classes.items()]))
        # Text is what the host actually prints, and what the real code reads
        # first. Rates are printed as Kbit, exactly as the host does.
        return done(out="".join(
            f"class htb {k} root prio 0 rate {v['rate'] * 1000:.0f}Kbit "
            f"ceil {v['ceil'] * 1000:.0f}Kbit burst 1600b\n"
            f" Sent 0 bytes 0 pkt (dropped 0, overlimits 0 requeues 0)\n\n"
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

    def test_the_double_matches_what_the_host_actually_prints(self):
        """Regression for the mis-specified double.

        It modelled `tc -j` as returning JSON. On the real host `-j` is
        accepted but prints text, so the double certified a code path the host
        never takes. Rates are also printed as Kbit there, not Mbit."""
        self.assertFalse(K.json_mode,
                         "the host does not honour -j; modelling JSON by "
                         "default would certify a path it never takes")
        with mock.patch.object(L, "_ns_run", fake_ns_run):
            K.clear()
            L._ns_run("tc", "class", "add", "dev", "veth-t", "parent", "1:",
                      "classid", "1:10", "rate", "6mbit", "ceil", "6mbit")
            raw = fake_ns_run("tc", "-s", "-j", "class", "show",
                              "dev", "veth-t").stdout
        self.assertIn("Kbit", raw)
        self.assertEqual(L._mbps("100000Kbit"), 100.0)
        self.assertEqual(L._mbps("53571Kbit"), 53.571)
        self.assertEqual(L._mbps("100Mbit"), 100.0)
        self.assertEqual(L._mbps("6000bit"), 0.006)
        with self.assertRaises(ValueError):
            json.loads(raw)
        # and the live helper recovers from it rather than returning {}
        with mock.patch.object(L, "_ns_run", fake_ns_run), \
                mock.patch.object(L, "DEV", "veth-t", create=True):
            self.assertEqual(L.tc_state()["1:10"]["rate"], 6.0)

    def test_clean_means_noqueue_not_nothing(self):
        self.assertIn("noqueue", L.CLEAN_QDISC_KINDS)

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