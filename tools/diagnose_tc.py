#!/usr/bin/env python3
"""Dump what `tc` actually prints, inside a throwaway namespace.

Written because tests/test_rollback_live.py failed on a real kernel with
`tc reported no classes: {}` while the controller's own read-back had already
verified the same tree. Two readers disagree about the same kernel, and the
only way to find out which is wrong is to look at the bytes.

Creates its own namespace and removes it on exit. Touches nothing on the host.

    sudo python3 tools/diagnose_tc.py
"""

from __future__ import annotations

import atexit
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

NS = f"aciqdiag{uuid.uuid4().hex[:6]}"
DEV = "veth-d"


def sh(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run(["ip", "netns", "exec", NS, *argv],
                          capture_output=True, text=True, timeout=20)


def cleanup() -> None:
    subprocess.run(["ip", "netns", "del", NS], capture_output=True, timeout=20)
    print(f"\n[cleanup] namespace {NS} removed")


def show(label: str, *argv: str) -> str:
    r = sh(*argv)
    body = (r.stdout or "") + (("\n[stderr] " + r.stderr.strip()) if r.stderr.strip() else "")
    shown = " ".join(argv[1:] if argv and argv[0] == "tc" else argv)
    print(f"\n{'=' * 70}\n{label}\n  $ tc {shown}\n  rc={r.returncode}\n"
          f"{'-' * 70}\n{body if body.strip() else '(no output)'}")
    return r.stdout


def main() -> int:
    atexit.register(cleanup)
    r = subprocess.run(["ip", "netns", "add", NS], capture_output=True,
                       text=True, timeout=20)
    if r.returncode != 0:
        print("cannot create namespace:", r.stderr.strip())
        return 1
    print(f"namespace {NS} created")

    for argv in (["ip", "link", "add", DEV, "type", "veth", "peer", "name", "veth-p"],
                 ["ip", "addr", "add", "10.9.9.1/24", "dev", DEV],
                 ["ip", "link", "set", DEV, "up"],
                 ["ip", "link", "set", "lo", "up"]):
        r = sh(*argv)
        if r.returncode != 0:
            print("setup failed:", " ".join(argv), r.stderr.strip())
            return 1

    from aciq.policy import build_plan
    from aciq.shield import Shield
    from aciq.txn import TransactionManager

    class R:
        def run(self, argv):
            r = sh(*argv)
            return r.returncode, r.stdout or "", r.stderr or ""

    tm = TransactionManager(R(), Shield(), dev=DEV, ns=NS)
    tm.remember_capacity(100.0)

    print("\n### before any policy")
    show("qdisc", "tc", "qdisc", "show", "dev", DEV)

    out = tm.apply(build_plan(100.0), now=1000.0)
    print(f"\n### apply -> ok={out.ok} reason={out.reason!r}")
    print(f"### read-back source used by the controller: "
          f"{getattr(tm, 'last_readback_source', '?')}")
    print(f"### classes the controller believes are present: "
          f"{sorted((tm._last_good_state or {}).keys())}")

    print("\n### raw kernel output, every reader we rely on")
    show("A. text -- primary reader", "tc", "class", "show", "dev", DEV)
    show("B. json -- fallback reader", "tc", "-s", "-j", "class", "show", "dev", DEV)
    show("C. json without -s", "tc", "-j", "class", "show", "dev", DEV)
    show("D. text with -s", "tc", "-s", "class", "show", "dev", DEV)
    show("E. qdisc", "tc", "qdisc", "show", "dev", DEV)

    # what exactly does the failing test's parser see?
    print("\n" + "=" * 70)
    print("what tests/test_rollback_live.py's tc_state() would parse")
    print("=" * 70)
    r = sh("tc", "-s", "-j", "class", "show", "dev", DEV)
    try:
        data = json.loads(r.stdout or "[]")
    except ValueError as e:
        print("  JSON PARSE FAILED:", e)
        print("  raw:", repr(r.stdout[:400]))
        data = None
    if isinstance(data, list):
        print(f"  json is a list of {len(data)} entries")
        for c in data[:6]:
            print("   ", {k: c[k] for k in list(c)[:8]})
        print("  handles seen:", [c.get("handle") for c in data])

    print("\n### after removing the root qdisc")
    sh("tc", "qdisc", "del", "dev", DEV, "root")
    show("qdisc after delete", "tc", "qdisc", "show", "dev", DEV)
    show("class after delete", "tc", "class", "show", "dev", DEV)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())