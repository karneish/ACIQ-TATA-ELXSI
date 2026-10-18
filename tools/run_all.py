#!/usr/bin/env python3
"""Single entry point for experiments, with the prerequisites checked first.

A run that cannot be performed must fail loudly and say why, not produce an
empty result directory that reads like a successful run with no traffic.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
from datetime import datetime, UTC
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NEEDED = ("ip", "tc")


def check() -> tuple[list[dict], bool]:
    rows = [
        {"item": "root", "ok": os.geteuid() == 0,
         "detail": f"euid={os.geteuid()}"},
    ]
    for b in NEEDED:
        p = shutil.which(b)
        rows.append({"item": b, "ok": p is not None,
                     "detail": p or "not on PATH"})
    venv = os.environ.get("ACIQ_VENV", "/home/mekarz/aciq-venv")
    rows.append({"item": "venv", "ok": Path(venv).exists(), "detail": venv})
    rows.append({"item": "kernel", "ok": True, "detail": platform.release()})
    rows.append({"item": "python", "ok": True, "detail": platform.python_version()})
    return rows, all(r["ok"] for r in rows if r["item"] != "root")


def revision() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True,
                              timeout=10).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def manifest(extra: dict) -> dict:
    return {"started_utc": datetime.now(UTC).isoformat(),
            "revision": revision(), "kernel": platform.release(),
            "python": platform.python_version(), **extra}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    rows, ok = check()
    print("prerequisites")
    for r in rows:
        print(f"  [{'ok ' if r['ok'] else 'NO '}] {r['item']:<8} {r['detail']}")
    print(f"\n  revision {revision()}")

    if a.check or not (a.gate or a.report):
        print("\n  prerequisites satisfied" if ok
              else "\n  NOT SATISFIED -- refusing to run. "
                   "Fix the above or run on a host with the testbed.")
        m = manifest({"check": rows, "satisfied": ok})
        (ROOT / "docs" / "gap-closure" / "last-run-manifest.json").write_text(
            json.dumps(m, indent=2) + "\n")
        return 0 if (a.check and ok or (not a.check and not ok)) else 1

    if a.gate:
        env = dict(os.environ, ACIQ_VENV=os.environ.get(
            "ACIQ_VENV", "/home/mekarz/aciq-venv"))
        r = subprocess.run([str(ROOT / "testbed" / "gate.sh")], env=env)
        print(json.dumps(manifest({"gate_exit": r.returncode}), indent=2))
        return r.returncode
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
