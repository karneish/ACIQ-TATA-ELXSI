"""The corpus collector must START the right generator commands AND keep
direction: the live failures did not stay hypothetical.

Pinned here:
  * the empty-sender-cmd bug (windows launched nothing), and
  * the direction split: an upload window must put most bytes in tx (home
    side pushes payload), a download window in rx. Without this the
    cloud_backup tx-share rule is unreachable BY CONSTRUCTION, which is
    exactly how the first live eval came back 1/6.
"""

from __future__ import annotations

import sys
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


DOWNLOAD = ("udp    17 30 src=203.0.113.2 dst=10.0.1.2 sport=44444 dport=5003 "
            "packets=1000 bytes=2500000 "
            "src=10.0.1.2 dst=203.0.113.2 sport=5003 dport=44444 "
            "packets=800 bytes=60000")

UPLOAD = ("tcp    6 60 src=10.0.1.2 dst=203.0.113.2 sport=55555 dport=5004 "
          "packets=900 bytes=2400000 "
          "src=203.0.113.2 dst=10.0.1.2 sport=5004 dport=55555 "
          "packets=700 bytes=50000")


class TestWiring(unittest.TestCase):
    def setUp(self):
        self.launches: list[list[str]] = []
        self._old = g.subprocess.Popen
        g.subprocess.Popen = self._popen
        self._old_observe = FlowTracker.observe
        FlowTracker.observe = lambda self, text, now: None
        self._old_dirs = g.parse_conntrack_dirs
        g.parse_conntrack_dirs = lambda text: {}

    def tearDown(self):
        g.subprocess.Popen = self._old
        FlowTracker.observe = self._old_observe
        g.parse_conntrack_dirs = self._old_dirs

    def _popen(self, cmd, **kw):
        self.launches.append(cmd)
        return _Proc(cmd)

    def _collect(self, label, plan, tracker):
        return g.collect_window(
            label, plan, g.NSEnv(),
            duration_s=0.2, poll_s=0.05,
            workloads_dir="testbed/workloads", capacity_mbps=100.0,
            tracker=tracker, source=type("S", (), {"read": lambda self: ""})())

    def test_listener_and_sender_are_both_launched(self):
        rows = self._collect("video_call_voice", ("call.py", "call.py", 5001,
                                                  [], False), FlowTracker())
        self.assertEqual(rows, [])
        listeners = [c for c in self.launches if "--listen" in c]
        senders = [c for c in self.launches if "--dst" in c]
        self.assertEqual(len(listeners), 1)
        self.assertEqual(len(senders), 1)
        self.assertIn("call.py", listeners[0][5])
        self.assertIn("--port", senders[0])
        self.assertIn(str(5001), senders[0])
        # the sender runs in the WAN ns, nsexec-prefixed
        self.assertEqual(senders[0][:4], ["ip", "netns", "exec", "wan"])

    def test_rate_cap_flags_reach_the_update_sender(self):
        rows = self._collect(
            "software_update",
            ("bulk.py", "bulk.py", 5004, ["--rate-cap", "8"], False),
            FlowTracker())
        self.assertEqual(rows, [])
        senders = [c for c in self.launches if "--dst" in c]
        self.assertIn("--rate-cap", senders[0])
        self.assertEqual(senders[0][senders[0].index("--rate-cap") + 1], "8")


class TestDirectionTracker(unittest.TestCase):
    def _tracker_with(self, text):
        t = g.DirectionTracker(window=8)
        t.observe(text, 1.0)
        t.observe(text, 2.0)
        t.observe(text, 3.0)
        return t

    def test_download_puts_payload_in_rx(self):
        tr = self._tracker_with(DOWNLOAD)
        f = tr.features("udp|203.0.113.2|44444|10.0.1.2|5003")
        # Flow.identity spelling may differ; fall back to a scan.
        if f is None:
            for k in tr.keys():
                f = tr.features(k)
                if f is not None:
                    break
        self.assertIsNotNone(f)
        self.assertGreater(f.rate_mbps, 0.0)
        self.assertLess(f.tx_bytes, f.rx_bytes)  # client sent only acks

    def test_upload_puts_payload_in_tx(self):
        tr = self._tracker_with(UPLOAD)
        f = None
        for k in tr.keys():
            f = tr.features(k)
            if f is not None:
                break
        self.assertIsNotNone(f)
        self.assertIsInstance(f.tx_bytes, int)
        self.assertGreater(f.rx_bytes, 0)
        self.assertGreater(f.tx_bytes, 0)
        self.assertGreater(f.tx_bytes, f.rx_bytes)  # home pushed the payload


if __name__ == "__main__":
    unittest.main()
