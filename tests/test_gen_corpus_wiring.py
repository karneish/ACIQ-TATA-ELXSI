"""The corpus collector must START the right generator commands.

The live failure this pins: once `start_sender` ran, `sender_cmd` was an
EMPTY list (computed into a different local), so the first window died in
subprocess.Popen before anything was collected. A test that only checks
"runs without rows" would have passed with that bug OFFLINE and failed only
on the host — the wiring itself is the contract.
"""

from __future__ import annotations

import sys
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tools.gen_corpus as g  # noqa: E402
from aciq.flowtrack import FlowTracker  # noqa: E402


class _Proc:
    def __init__(self, cmd):
        self.cmd = cmd

    def terminate(self): pass

    def kill(self): pass

    def wait(self, timeout=None): return 0


class TestWiring(unittest.TestCase):
    def setUp(self):
        self.launches: list[list[str]] = []

        def popen(cmd, **kw):
            self.launches.append(cmd)
            return _Proc(cmd)

        self._old = g.subprocess.Popen
        g.subprocess.Popen = popen

        class FakeSource:
            def __init__(self, ns="router"):
                self.read = lambda: ""

        self._FakeSource = FakeSource
        self._old_tracker = FlowTracker.observe
        FlowTracker.observe = lambda self, text, now: None

    def tearDown(self):
        g.subprocess.Popen = self._old
        FlowTracker.observe = self._old_tracker

    def test_listener_and_sender_are_both_launched(self):
        rows = g.collect_window(
            "video_call_voice", ("call.py", "call.py", 5001), g.NSEnv(),
            duration_s=0.2, poll_s=0.05,
            workloads_dir="testbed/workloads", capacity_mbps=100.0,
            tracker=FlowTracker(), source=self._FakeSource())
        self.assertEqual(rows, [])
        listeners = [c for c in self.launches if "--listen" in c]
        senders = [c for c in self.launches if "--dst" in c]
        self.assertEqual(len(listeners), 1)
        self.assertEqual(len(senders), 1)
        self.assertIn("call.py", listeners[0][5])
        self.assertIn("--port", senders[0])
        self.assertIn(str(5001), senders[0])
        # the sender runs in the WAN ns, nsexec-prefixed
        self.assertEqual(senders[0][:4],
                         ["ip", "netns", "exec", "wan"])


if __name__ == "__main__":
    unittest.main()
