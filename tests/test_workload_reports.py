"""Generator report contracts.

Regression guard: bulk.py and video.py once referenced an undefined `state`
after `--listen` was split out, which crashed the sender. Their reports now
carry sender-side facts only, because the sink runs in another namespace and
the sender cannot observe what arrived.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

W = Path(__file__).resolve().parent.parent / "testbed" / "workloads"


def tree_of(name: str):
    return ast.parse((W / name).read_text())


def main_body(name: str) -> ast.FunctionDef:
    mod = tree_of(name)
    for node in ast.walk(mod):
        if isinstance(node, ast.FunctionDef) and node.name == "main":
            return node
    raise AssertionError("no main()")


class TestGeneratorsCompile(unittest.TestCase):
    def test_all_parse(self):
        for f in W.glob("*.py"):
            ast.parse(f.read_text())


class TestNoUndefinedState(unittest.TestCase):
    def test_bulk_references_no_bare_state(self):
        """The crash that killed the first real bulk workload."""
        src = (W / "bulk.py").read_text()
        self.assertNotIn("state.get(", src)

    def test_video_references_no_bare_state(self):
        self.assertNotIn("state.get(", (W / "video.py").read_text())


class TestReportContracts(unittest.TestCase):
    def test_bulk_reports_sender_side_fields(self):
        src = (W / "bulk.py").read_text()
        for key in ("sent_bytes", "elapsed_s", "sender_mbps"):
            self.assertIn(f'"{key}"', src)

    def test_video_reports_sender_side_fields(self):
        src = (W / "video.py").read_text()
        for key in ("sent_bytes", "elapsed_s", "sender_mbps"):
            self.assertIn(f'"{key}"', src)

    def test_receiver_throughput_is_not_claimed_by_the_sender(self):
        """Reporting a received_bytes the sender cannot know would be a
        fabricated number in the report."""
        self.assertNotIn('"received_bytes"', (W / "bulk.py").read_text())
        self.assertNotIn('"received_bytes"', (W / "video.py").read_text())


class TestConnectRetry(unittest.TestCase):
    def test_tcp_senders_retry_their_connect(self):
        """A single refused connect silently dropped the whole workload."""
        for name in ("bulk.py", "video.py"):
            self.assertIn("for _ in range(20)", (W / name).read_text(), name)


if __name__ == "__main__":
    unittest.main()
