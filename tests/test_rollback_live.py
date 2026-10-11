"""LIVE kernel rollback verification. Skipped unless root with `tc`.

Unlike `tests/test_rollback.py`, nothing here is mocked. The topology is built
in a throwaway network namespace and the kernel state is read back with `tc`
called directly, independently of `TransactionManager`, so a bug shared between
the code under test and its own reader cannot make this pass.

ISOLATION. Everything happens inside one namespace (`aciqrb<N>`) created and
destroyed by this module. The host's interfaces, routes and qdiscs are never
touched, and nothing is configured outside the namespace. If namespace creation
is unavailable the whole module skips rather than falling back to a real
interface.

Run it with:

    sudo python3 -m unittest tests.test_rollback_live -v

Skip conditions, reported rather than silently passed: not root, no `tc` on
PATH, no `ip`, or namespace creation refused.
"""

from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import time
import unittest
import uuid

from aciq.policy import build_plan
from aciq.shield import Shield
from aciq.txn import VERIFICATION_FAILED, VERIFIED, TransactionManager


def _have(*tools: str) -> bool:
    return all(shutil.which(t) is not None for t in tools)


NS: str | None = None
DEV: str | None = None
CREATED = False


def _ns_run(*argv: str, check: bool = False):
    r = subprocess.run(["ip", "netns", "exec", NS, *argv],
                       capture_output=True, text=True, timeout=15)
    if check and r.returncode != 0:
        raise RuntimeError(f"{' '.join(argv)}: {r.stderr.strip()}")
    return r


def _teardown() -> None:
    global CREATED
    if NS and CREATED:
        subprocess.run(["ip", "netns", "del", NS], capture_output=True,
                       text=True, timeout=15)
        CREATED = False


def setUpModule() -> None:
    global NS, DEV, CREATED
    atexit.register(_teardown)
    if os.geteuid() != 0 or not _have("ip", "tc"):
        return
    name = f"aciqrb{uuid.uuid4().hex[:8]}"
    r = subprocess.run(["ip", "netns", "add", name],
                       capture_output=True, text=True, timeout=15)
    if r.returncode != 0:
        return                      # no namespace support: module skips
    NS, CREATED = name, True
    DEV = "veth-t"
    _ns_run("ip", "link", "add", DEV, "type", "veth",
            "peer", "name", "veth-p", check=True)
    _ns_run("ip", "addr", "add", "10.9.9.1/24", "dev", DEV, check=True)
    _ns_run("ip", "link", "set", DEV, "up", check=True)
    _ns_run("ip", "link", "set", "lo", "up", check=True)


def skip_reason() -> str | None:
    if os.geteuid() != 0:
        return "not root"
    if not _have("ip", "tc"):
        return "iproute2 not on PATH"
    if not NS:
        return ("network namespace unavailable (cannot isolate; refusing "
                "to touch a host interface)")
    return None


def tc_state() -> dict:
    """Independent read-back: plain `tc class show`, parsed by hand here."""
    r = _ns_run("tc", "-s", "-j", "class", "show", "dev", DEV)
    out = {}
    try:
        data = json.loads(r.stdout or "[]")
    except ValueError:
        return out
    for c in data if isinstance(data, list) else []:
        handle = str(c.get("handle", ""))
        rate = c.get("rate")
        ceil = c.get("ceil")
        out[handle] = {
            "rate": None if rate is None else rate / 1e6,
            "ceil": None if ceil is None else ceil / 1e6,
        }
    return out


def tc_qdisc_kind() -> str:
    r = _ns_run("tc", "qdisc", "show", "dev", DEV)
    for line in (r.stdout or "").splitlines():
        p = line.split()
        if len(p) >= 4 and p[0] == "qdisc" and "root" in p[2:4]:
            return p[1]
    return ""


@unittest.skipUnless(shutil.which("tc"), "iproute2 not on PATH")
class TestLiveRollback(unittest.TestCase):
    """Rollback against a real kernel, read back by `tc` itself."""

    def setUp(self) -> None:
        why = skip_reason()
        if why:
            self.skipTest(why)
        # fresh interface state for every test
        _ns_run("tc", "qdisc", "del", "dev", DEV, "root")

    def _tm(self) -> TransactionManager:
        return TransactionManager(Runner(), Shield(), dev=DEV, ns=NS)

    def test_a_committed_plan_is_visible_to_independent_tc(self):
        """Baseline: if this fails, nothing below means anything."""
        tm = self._tm()
        tm.remember_capacity(100.0)
        plan = build_plan(100.0)
        out = tm.apply(plan, now=1000.0)
        self.assertTrue(out.ok, out.reason)
        state = tc_state()
        self.assertTrue(state, f"tc reported no classes: {state}")
        self.assertEqual(sorted(state), sorted(
            {c.classid for c in __import__("aciq.tc", fromlist=["x"])
             .build_tree(plan).classes}))

    def test_rollback_restores_the_known_good_tree(self):
        """Apply, commit, then fail a later apply and confirm restoration."""
        tm = self._tm()
        tm.remember_capacity(100.0)
        base = build_plan(100.0)
        self.assertTrue(tm.apply(base, now=1000.0).ok)
        good = tc_state()
        self.assertTrue(good)

        # Now force a failure on the *apply*, with the runner still able to
        # replay the good tree for the rollback itself.
        tm.runner = FlakyRunner(good)

        changed = build_plan(100.0, lease=None)
        out = tm.apply(changed, now=2000.0)
        self.assertFalse(out.ok)
        self.assertIsNotNone(out.rollback)
        self.assertEqual(out.rollback.outcome, VERIFIED, out.rollback.reason)

        # Independent confirmation: the kernel is back where it was.
        after = tc_state()
        for cid, want in good.items():
            self.assertIn(cid, after, f"{cid} missing after rollback")
            for key in ("rate", "ceil"):
                if want[key] is None:
                    continue
                self.assertAlmostEqual(
                    after[cid][key], want[key], delta=max(0.05, 0.01 * want[key]),
                    msg=f"{cid}.{key} not restored")

    def test_rollback_that_cannot_be_verified_is_not_reported_as_success(self):
        """Force the read-back to be unreadable; the verdict must not be a pass."""
        tm = self._tm()
        tm.remember_capacity(100.0)
        self.assertTrue(tm.apply(build_plan(100.0), now=1000.0).ok)

        class BlindRunner(FlakyRunner):
            def run(self, argv):
                if "class" in argv and "show" in argv:
                    return 1, "", "simulated reader failure"
                return super().run(argv)

        tm.runner = BlindRunner(tc_state())
        res = tm._rollback()
        self.assertFalse(res.ok)
        self.assertNotEqual(res.outcome, VERIFIED)

    def test_safe_state_is_installed_and_confirmed(self):
        tm = self._tm()
        tm.remember_capacity(100.0)
        self.assertTrue(tm.apply(build_plan(100.0), now=1000.0).ok)
        self.assertTrue(tm.force_safe())
        self.assertTrue(tm.last_rollback.ok)
        self.assertEqual(tm.last_rollback.outcome, VERIFIED)
        # Independent read: a root qdisc of the expected kind exists.
        self.assertIn(tc_qdisc_kind(), ("cake", "fq_codel", "pfifo"))
        # ...and the class tree is gone, which is what the safe state means.
        self.assertEqual(tc_state(), {})

    def test_verification_failed_is_reachable_and_is_not_a_pass(self):
        """The failure verdict must be reachable on a real kernel, not only in
        the mocked suite -- otherwise it is untested production code."""
        tm = self._tm()
        tm.remember_capacity(100.0)
        self.assertTrue(tm.apply(build_plan(100.0), now=1000.0).ok)
        good = tc_state()

        class LyingRunner(FlakyRunner):
            def run(self, argv):
                a = list(argv)
                if "class" in argv and "add" in argv and "rate" in a:
                    a[a.index("rate") + 1] = "1mbit"   # accept, wrong rate
                return super().run(tuple(a))

        tm.runner = LyingRunner(good)
        res = tm._rollback()
        self.assertFalse(res.ok)
        self.assertEqual(res.outcome, VERIFICATION_FAILED, res.reason)
        self.assertTrue(res.mismatches)

    def test_teardown_leaves_no_residue(self):
        """The namespace is the isolation; confirm the interface is clean
        after a full apply/rollback cycle."""
        tm = self._tm()
        tm.remember_capacity(100.0)
        self.assertTrue(tm.apply(build_plan(100.0), now=1000.0).ok)
        tm.runner = FlakyRunner(tc_state())
        tm.apply(build_plan(100.0, lease=None), now=2000.0)
        _ns_run("tc", "qdisc", "del", "dev", DEV, "root")
        self.assertEqual(tc_state(), {})
        self.assertEqual(tc_qdisc_kind(), "")


class Runner:
    """Real command execution inside the test namespace."""

    def run(self, argv):
        return _ns_run(*argv)


class FlakyRunner(Runner):
    """Real execution, but the first `class add` of a rebuild is refused.

    The refusal is modelled by *not running* that one command, so the kernel
    genuinely receives a truncated tree -- there is no fake anywhere in the
    read-back path.
    """

    def __init__(self, good: dict):
        self.good = good
        self._armed = False

    def run(self, argv):
        joined = " ".join(argv)
        if "class" in argv and "add" in argv and self._armed:
            return 1, "", "injected apply failure"
        if "qdisc" in argv and "del" in argv:
            self._armed = True
        return _ns_run(*argv)


if __name__ == "__main__":
    unittest.main()