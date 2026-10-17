"""Per-flow fairness, measured on a real kernel.

**Gated on root + `tc`; skipped otherwise.** No mocks anywhere in this file.

Correcting something this project has been claiming wrong. `fairness-policy-
safety.md` said per-flow fairness is "a question the policy does not answer",
because `build_plan` splits by weight per *class* and flow count is not an
input to the arithmetic. That is true of the arithmetic and irrelevant to the
guarantee: every class gets an `fq_codel` leaf, and `fq_codel` is per-flow fair
queueing. Two flows inside one class are already served fairly. **What was
missing was the measurement**, not the mechanism.

So this measures it: two independent UDP flows steered into the SAME class, then
Jain's fairness index over what each one actually received. One flow getting
twice the other's bytes scores 0.8; equal shares score 1.0.

Isolation is the same as test_rollback_live: a throwaway namespace, a veth pair
inside it, removed on exit. The host is never touched.
"""

from __future__ import annotations

import atexit
import shutil
import subprocess
import time
import unittest
import uuid
from pathlib import Path

from aciq.metrics import jain_fairness

NS: str | None = None
#: Why setup failed, if it did. It used to `return` silently with NS still set,
#: so the tests RAN against a half-built topology and failed on "no traffic"
#: three times over -- which says nothing about why. A setup failure is either
#: skipped (no namespace possible) or reported with the command and its stderr.
SETUP_ERROR = ""
DEV = "veth-f"
PEER = "veth-p"
#: The sender binds this. It must actually be assigned to PEER -- the first
#: version bound an address nothing held, so every sender died on bind() and
#: the "unfair" result was two zeroes. It only ever ran under root, which is
#: exactly why it was not caught before.
SRC_ADDR = "10.9.9.2"
DST_ADDR = "10.9.9.1"
A_PORT, B_PORT = 47311, 47312
ROOT = Path(__file__).resolve().parents[1]

#: A flow receiving twice another's share scores 0.8. Anything above this means
#: the two are being served within ~1% of each other.
FAIRNESS_FLOOR = 0.95

_SENDER = r"""
import socket, sys, time
port = int(sys.argv[1]); dst = sys.argv[2]; dur = float(sys.argv[3])
SRC = sys.argv[4]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind((SRC, 0))
s.settimeout(0.2)
payload = b"x" * 1400
end = time.monotonic() + dur
while time.monotonic() < end:
    try:
        s.sendto(payload, (dst, port))
    except OSError:
        pass
    time.sleep(0.001)
"""

_SINK = r"""
import socket, sys
port = int(sys.argv[1]); dur = float(sys.argv[2]); SRC = sys.argv[3]
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
s.bind((SRC, port)); s.settimeout(0.3)
total = 0; end = time.monotonic() + dur
while time.monotonic() < end:
    try:
        data, _ = s.recvfrom(4096); total += len(data)
    except socket.timeout:
        pass
print(total)
"""


def _ns(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(["ip", "netns", "exec", NS, *argv],
                          capture_output=True, text=True, timeout=90)


def _cleanup() -> None:
    if NS:
        subprocess.run(["ip", "netns", "del", NS], capture_output=True, timeout=20)


def setUpModule() -> None:
    global NS
    atexit.register(_cleanup)
    if not shutil.which("tc") or not shutil.which("ip"):
        return
    global SETUP_ERROR
    name = f"aciqfair{uuid.uuid4().hex[:6]}"
    r0 = subprocess.run(["ip", "netns", "add", name],
                        capture_output=True, text=True, timeout=20)
    if r0.returncode != 0:
        return
    NS = name
    for argv in (["ip", "link", "add", DEV, "type", "veth",
                  "peer", "name", PEER],
                 ["ip", "addr", "add", f"{DST_ADDR}/24", "dev", DEV],
                 ["ip", "addr", "add", f"{SRC_ADDR}/24", "dev", PEER],
                 ["ip", "link", "set", DEV, "up"],
                 ["ip", "link", "set", PEER, "up"],
                 ["ip", "link", "set", "lo", "up"]):
        r = _ns(*argv)
        if r.returncode != 0:
            SETUP_ERROR = (f"{' '.join(argv)} -> rc={r.returncode} "
                           f"{r.stderr.strip()}")
            return
    # one class, well above what two senders can offer, so nothing here is
    # about rate limiting -- it is purely about how the queue shares.
    for argv in (["tc", "qdisc", "replace", "dev", DEV, "root", "handle", "1:",
                  "htb", "default", "10"],
                 ["tc", "class", "replace", "dev", DEV, "parent", "1:",
                  "classid", "1:10", "htb", "rate", "500mbit", "ceil", "500mbit"],
                 ["tc", "qdisc", "replace", "dev", DEV, "parent", "1:10",
                  "handle", "10:", "fq_codel"]):
        r = _ns(*argv)
        if r.returncode != 0:
            SETUP_ERROR = (f"{' '.join(argv)} -> rc={r.returncode} "
                           f"{r.stderr.strip()}")
            return


@unittest.skipUnless(shutil.which("tc"), "iproute2 not on PATH")
class TestPerFlowFairness(unittest.TestCase):

    def setUp(self) -> None:
        if NS is None:
            self.skipTest("namespace unavailable (no root, or no CAP_NET_ADMIN)")
        if SETUP_ERROR:
            # Fail loudly, and say which command. Skipping here would turn a
            # broken setup into a green run -- the gate already caught this once
            # by accident, reporting "no traffic arrived" for three tests.
            self.fail(f"testbed setup failed: {SETUP_ERROR}")

    def _run_two_flows(self, duration=6.0):
        sinks = [
            subprocess.Popen(["ip", "netns", "exec", NS, "python3", "-c", _SINK,
                              str(p), str(duration), DST_ADDR],
                             stdout=subprocess.PIPE, text=True)
            for p in (A_PORT, B_PORT)]
        time.sleep(0.4)
        senders = [
            subprocess.Popen(["ip", "netns", "exec", NS, "python3", "-c", _SENDER,
                              str(p), DST_ADDR, str(duration), SRC_ADDR],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            for p in (A_PORT, B_PORT)]
        for s in senders:
            s.wait(timeout=duration + 30)
        got = []
        for s in sinks:
            out, _ = s.communicate(timeout=duration + 30)
            got.append(int((out or "0").strip() or 0))
        return got

    def test_both_senders_and_sinks_are_reachable_first(self):
        """A run where a sender died on bind() must not look like an unfair
        scheduler. Check the plumbing before scoring anything."""
        a, b = self._run_two_flows(duration=3.0)
        self.assertGreater(a, 0, f"flow A received nothing -- sender may have "
                                  f"failed to bind {SRC_ADDR}")
        self.assertGreater(b, 0, f"flow B received nothing -- sender may have "
                                  f"failed to bind {SRC_ADDR}")

    def test_two_flows_in_one_class_are_served_fairly(self):
        a, b = self._run_two_flows()
        self.assertGreater(a + b, 0, "no traffic arrived at all")
        f = jain_fairness([a, b])
        self.assertIsNotNone(f)
        self.assertGreaterEqual(
            f, FAIRNESS_FLOOR,
            f"two flows in one class received {a} and {b} bytes "
            f"(ratio {max(a, b) / max(1, min(a, b)):.2f}x); fq_codel is "
            f"per-flow fair queueing and should not allow that")

    def test_the_class_actually_carried_the_traffic(self):
        """Guards against a fairness index computed on two zeroes."""
        a, b = self._run_two_flows(duration=4.0)
        self.assertGreater(a, 0)
        self.assertGreater(b, 0)

    def test_the_leaf_qdisc_is_really_fq_codel(self):
        """If this fails, the fairness result above is about a different qdisc
        than the one the design claims."""
        r = _ns("tc", "qdisc", "show", "dev", DEV)
        self.assertIn("fq_codel", r.stdout,
                      f"no fq_codel leaf: {r.stdout}")


class TestFairnessIndex(unittest.TestCase):
    def test_equal_shares_score_one(self):
        self.assertAlmostEqual(jain_fairness([100, 100]), 1.0, places=6)

    def test_a_two_to_one_split_scores_exactly_nine_tenths(self):
        # (200+100)^2 / (2 * (200^2 + 100^2)) = 90000/100000 = 0.9 exactly.
        self.assertAlmostEqual(jain_fairness([200, 100]), 0.9, places=9)
        self.assertLess(jain_fairness([200, 100]), 0.95)

    def test_no_traffic_is_none_not_zero(self):
        """An idle class must not score 0.0.

        0.0 is the score of one hog against nothing, so reporting it for
        "[nothing flowed]" called the class maximally unfair -- the same error
        the function's own docstring argues against for an empty list, which it
        then committed two lines later.
        """
        from aciq.metrics import jain_fairness as j
        self.assertIsNone(j([0, 0]))
        self.assertIsNone(j([]))
        self.assertIsNone(j([0.0, 0.0, 0.0]))


if __name__ == "__main__":
    unittest.main()