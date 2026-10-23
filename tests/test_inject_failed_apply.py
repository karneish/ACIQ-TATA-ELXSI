"""S5(c) — the failed-apply injection must be honest offline AND in-kernel.

Contract: `inject_failed_apply_once` makes the NEXT tc command fail exactly
once; the transaction must (a) report ok=False with a kernel-visible reason,
(b) roll back to the last-good state so the classes that existed before the
failure exist again, and (c) keep working afterwards. Refusing to arm twice is
part of the contract: a wrapper swapped in silently would defer the "failure"
to a later apply and nobody would notice the test stopped testing.
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aciq.policy import build_plan  # noqa: E402
from aciq.shield import Shield  # noqa: E402
from aciq.txn import FakeRunner, TransactionManager  # noqa: E402


class TestInjectFailedApply(unittest.TestCase):
    def _txn(self):
        return TransactionManager(FakeRunner(auto_readback=True),
                                  Shield(), clock=time.monotonic)

    def test_full_cycle(self):
        t = self._txn()
        self.assertTrue(t.apply(build_plan(20.0, None), now=0.0).ok)
        self.assertTrue(t.inject_failed_apply_once())
        out = t.apply(build_plan(10.0, None), now=10.0)
        self.assertFalse(out.ok)
        self.assertTrue(out.kernel_touched, "the failed apply rebuilt the qdisc first")
        self.assertIn("injected failure", out.reason)
        rb = t.last_rollback
        self.assertIsNotNone(rb)
        self.assertTrue(rb.ok, "rollback replays last-good through live commands")
        # last-good REPLAYS the good tree, so the rung is the normal commit
        # path; safe_state_in_force is reserved for the no-last-good ladder.
        self.assertTrue(t.last_rollback.ok)
        self.assertEqual(len(t._read_classes()), 8, "classes restored")
        self.assertEqual(len(t._read_classes()), 8, "classes restored")
        # and the next ordinary apply works, through the same still-live pass-through
        self.assertTrue(t.apply(build_plan(10.0, None), now=20.0).ok)

    def test_arming_twice_is_refused(self):
        t = self._txn()
        self.assertTrue(t.inject_failed_apply_once())
        self.assertFalse(t.inject_failed_apply_once())

    def test_one_shot_persists_through_subsequent_uses(self):
        t = self._txn()
        t.apply(build_plan(20.0, None), now=0.0)
        t.inject_failed_apply_once()
        t.apply(build_plan(10.0, None), now=10.0)     # failure fires here
        # second apply: no second failure
        out = t.apply(build_plan(10.0, None), now=20.0)
        self.assertTrue(out.ok)
        self.assertIsNone(out.reason or None)


if __name__ == "__main__":
    unittest.main()
