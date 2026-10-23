"""Offline tests for aciq.watchdog -- no root, no netlink.

The live behaviour (a real SIGTERM forces teardown inside a kernel that
already has the filter) is proved by the gate's watchdog check, not here; the
handler mechanics themselves are fully assertable offline.
"""

from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import tempfile
import unittest

from aciq.watchdog import Watchdog


class FakeSignaller:
    """Records subscriptions; lets a test deliver a signal manually."""

    def __init__(self):
        self.handlers = {}
        self.itimer = None

    def signal(self, sig, handler):
        self.handlers[sig] = handler

    def setitimer(self, which, seconds):
        self.itimer = seconds


class TestHandlerMechanics(unittest.TestCase):
    def make(self, safe, timeout=None, re_raise=False):
        g = FakeSignaller()
        w = Watchdog(safe, timeout_s=timeout, signaller=g, re_raise=re_raise)
        w.install()
        return w, g

    def test_installs_term_int_and_alrm(self):
        g = FakeSignaller()
        w = Watchdog(lambda: None, timeout_s=2.0, signaller=g, re_raise=False)
        w.install()
        self.assertIn(signal.SIGTERM, g.handlers)
        self.assertIn(signal.SIGINT, g.handlers)
        self.assertIn(signal.SIGALRM, g.handlers)
        self.assertEqual(g.itimer, 2.0)

    def test_no_timeout_when_unset(self):
        g = FakeSignaller()
        Watchdog(lambda: None, signaller=g, re_raise=False).install()
        self.assertNotIn(signal.SIGALRM, g.handlers)

    def test_safe_fn_runs_there_is_no_exit_masking_recorded(self):
        calls = []
        w, g = self.make(lambda: calls.append(1))
        g.handlers[signal.SIGTERM](signal.SIGTERM, None)
        self.assertEqual(calls, [1])
        self.assertEqual(w.reason, "sigterm")
        self.assertTrue(w.engaged)

    def test_idempotent_latch(self):
        calls = []
        w, g = self.make(lambda: calls.append(1))
        g.handlers[signal.SIGTERM](signal.SIGTERM, None)
        g.handlers[signal.SIGINT](signal.SIGINT, None)
        self.assertEqual(calls, [1], "the safe path must run exactly once")

    def test_exception_in_safe_path_is_swallowed_and_reported(self):
        from unittest.mock import patch
        def bad():
            raise RuntimeError("gone down, but keep deleting")
        w, g = self.make(bad)
        lines = []
        with patch("builtins.print") as rec:
            g.handlers[signal.SIGTERM](signal.SIGTERM, None)
        for call in rec.call_args_list:
            args, _ = call
            lines.append(" ".join(str(a) for a in args))
        self.assertEqual(w.reason, "sigterm")
        self.assertTrue(contains(lines, "RuntimeError"),
                        "handler failure must be visible: " + str(lines))


def contains(buf, needle):
    return any(needle in x for x in buf)

    def test_timeout_means_alrm(self):
        calls = []
        w, g = self.make(lambda: calls.append(1), timeout=1.0)
        g.handlers[signal.SIGALRM](signal.SIGALRM, None)
        self.assertEqual(calls, [1])
        self.assertEqual(w.reason, "timeout")

    def test_disarm_cancels_the_timer(self):
        g = FakeSignaller()
        w = Watchdog(lambda: None, timeout_s=1.0, signaller=g, re_raise=False)
        w.install()
        w.disarm()
        self.assertEqual(g.itimer, 0.0)


class TestRealSignalDelivery(unittest.TestCase):
    """A real SIGTERM kills the process AFTER the safe path ran."""

    def test_sigterm_runs_safe_fn_then_exits_with_the_signal(self):
        with tempfile.TemporaryDirectory() as d:
            marker = os.path.join(d, "safe.path")
            lines = [
                "import sys, time",
                "sys.path.insert(0, %r)" % os.getcwd(),
                "from aciq.watchdog import Watchdog",
                "open(%r, 'w').write('safe')" % marker,
                "Watchdog("
                "lambda: open(%r, 'a').write('done'), re_raise=True)"
                ".install()" % marker,
                "print('armed', flush=True)",
                "time.sleep(30)",
            ]
            code = "\n".join(lines)
            p = subprocess.Popen([sys.executable, "-c", code],
                                 cwd=os.getcwd(),
                                 stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
            # Wait for the armed line so the handler is guaranteed installed.
            p.stdout.readline()
            p.terminate()
            o, e = p.communicate(timeout=10)
            # subprocess reports "died from SIGTERM" as -15; a shell displays
            # the same death as exit status 143 (128+15). Assert the truth,
            # not the convenient spelling.
            self.assertEqual(p.returncode, -signal.SIGTERM,
                             "exit must BE the signal, not a synthetic code")
            self.assertIn("force-safe path engaged", o)
            content = open(marker).read()
            self.assertEqual(content, "safedone")


if __name__ == "__main__":
    unittest.main()
