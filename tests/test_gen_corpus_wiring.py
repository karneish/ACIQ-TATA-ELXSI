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

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tools.gen_corpus as g  # noqa: E402

import tempfile  # noqa: E402

# was a hardcoded path into the agent sandbox scratch dir; a per-test
# temp dir is portable
BASE = Path(tempfile.mkdtemp(prefix="aciq-gen-"))
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

    def _collect(self, label, plan, tracker, **kw):
        return g.collect_window(
            label, plan, g.NSEnv(),
            duration_s=0.2, poll_s=0.05,
            workloads_dir="testbed/workloads", capacity_mbps=100.0,
            tracker=tracker, source=type("S", (), {"read": lambda self: ""})(),
            **kw)

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

    def test_multi_flow_window_launches_one_pair_per_flow_on_distinct_ports(self):
        """T6 volume: 30 flows per class requires one fly-by pair per flow.

        The first live corpus shipped NINE rows total because one window ran
        one flow. The collector must launch N listener/sender pairs and put
        flow i on base_port+i so a stale conntrack entry from flow i can
        never be re-read as flow i+1's data.
        """
        rows = self._collect(
            "bulk_download", ("bulk.py", "bulk.py", 5004, [], False),
            FlowTracker(), flows=3)
        self.assertEqual(rows, [])
        listeners = [c for c in self.launches if "--listen" in c]
        senders = [c for c in self.launches if "--dst" in c]
        self.assertEqual(len(listeners), 3)
        self.assertEqual(len(senders), 3)
        self.assertEqual({c[-1] for c in listeners}, {"5004", "5005", "5006"})
        for i, s in enumerate(senders):
            self.assertIn("--port", s)
            self.assertIn(str(5004 + i), s)


class TestAmbiguousPlan(unittest.TestCase):
    """The ambiguous windows must exist BY CONSTRUCTION, not by luck."""

    def test_ambiguous_windows_are_declared_for_three_classes(self):
        labels = set(g.AMBIGUOUS_PLAN)
        self.assertIn("bulk_download", labels)
        self.assertIn("adaptive_video_streaming", labels)
        self.assertIn("software_update", labels)

    def _extra(self, label):
        return g.AMBIGUOUS_PLAN[label][0][3]

    def test_ambiguous_bulk_sits_below_the_frac_floor_by_rate(self):
        extra = self._extra("bulk_download")
        self.assertIn("--rate-cap", extra)
        self.assertEqual(extra[extra.index("--rate-cap") + 1], "40")
        _, n = g.AMBIGUOUS_PLAN["bulk_download"]
        self.assertGreaterEqual(n, 10)

    def test_ambiguous_update_is_low_rate_and_labeled_by_its_class(self):
        extra = self._extra("software_update")
        self.assertEqual(extra[extra.index("--rate-cap") + 1], "3")
        _, n = g.AMBIGUOUS_PLAN["software_update"]
        self.assertGreaterEqual(n, 10)


class TestPerClassFloor(unittest.TestCase):
    """The corpus must FAIL LOUDLY below 30 flows per class.

    The first live corpus quietly shipped 9 flows and an n=1 eval; the
    floor makes quiet fail into loud fail.
    """

    def test_missing_or_short_class_is_reported(self):
        msg = g.enforce_min_counts({"bulk_download": 9}, 30, ["bulk_download"])
        self.assertIn("bulk_download=9<30", msg)
        self.assertIsNone(g.enforce_min_counts(
            {"bulk_download": 30}, 30, ["bulk_download"]))
        absent = g.enforce_min_counts({}, 30, ["cloud_backup"])
        self.assertIn("cloud_backup=0<30", absent)

    def test_collect_all_refuses_to_write_a_short_corpus(self):
        calls: list[tuple[str, int, str]] = []

        def fake(label, plan, env, duration_s, poll_s, wl, cap, flows=0,
                 case="canonical", port_offset=0):
            calls.append((label, flows, case, port_offset))
            return [{"label": label, "case": case} for _ in range(flows)]

        orig = g.collect_window
        g.collect_window = fake
        out = BASE / "corpus_short" / "corpus.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            rc = g.collect_all(out, flows_per_class=3, min_per_class=30)
        finally:
            g.collect_window = orig
        self.assertEqual(rc, 1)
        counts = json.loads(
            (out.parent / "counts.json").read_text())
        self.assertEqual(counts["n_total"],
                         sum(flows for _lbl, flows, _case, _off in calls))
        # canonical windows ran with the class floor they were ASKED for
        for label, flows, case, off in calls:
            self.assertEqual(off, 0, "default collection uses no offset")
            if case == "canonical":
                self.assertEqual(flows, 3)
            else:
                self.assertEqual(case, "ambiguous")

    def test_collect_all_passes_at_the_floor(self):
        def fake(label, plan, env, duration_s, poll_s, wl, cap, flows=0,
                 case="canonical", port_offset=0):
            return [{"label": label, "case": case} for _ in range(flows)]

        orig = g.collect_window
        g.collect_window = fake
        out = BASE / "corpus_ok" / "corpus.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        try:
            rc = g.collect_all(out, flows_per_class=30, min_per_class=30)
        finally:
            g.collect_window = orig
        self.assertEqual(rc, 0)
        counts = json.loads((out.parent / "counts.json").read_text())
        self.assertGreaterEqual(counts["per_label"]["bulk_download"], 30)


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
