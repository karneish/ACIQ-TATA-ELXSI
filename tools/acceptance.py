#!/usr/bin/env python3
"""Single acceptance workflow.

Runs every gate the environment supports, in a deterministic order, and records
each as PASS, FAIL, BLOCKED or NOT RUN with the reason.

The distinction that matters: **a missing tool or a missing privilege is BLOCKED,
never PASS.** An acceptance run that cannot distinguish "the gate passed" from
"the gate could not run" is worse than no acceptance run, because it converts an
environmental limit into a green tick.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "validation"

PASS, FAIL, BLOCKED, NOT_RUN = "PASS", "FAIL", "BLOCKED", "NOT RUN"


def rev() -> str:
    try:
        return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                              capture_output=True, text=True, timeout=10
                              ).stdout.strip() or "unknown"
    except (OSError, subprocess.SubprocessError):
        return "unknown"


def have(tool: str) -> bool:
    return shutil.which(tool) is not None


def root() -> bool:
    return os.geteuid() == 0


def run(cmd: list[str], timeout: int = 900) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True,
                           timeout=timeout)
        return r.returncode, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        return 124, "timeout"
    except OSError as e:
        return 127, str(e)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", help="write the JSON summary here")
    a = ap.parse_args()

    run_id = rev()[:8]
    outdir = OUT / run_id
    outdir.mkdir(parents=True, exist_ok=True)
    env = {
        "run_id": run_id, "revision": rev(),
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "kernel": platform.release(), "python": platform.python_version(),
        "uid": os.geteuid(), "hostname": platform.node(),
    }
    gates: list[dict] = []

    def record(name, status, detail="", log=""):
        gates.append({"gate": name, "status": status, "detail": detail[:400],
                      "log": log})
        mark = {PASS: "PASS   ", FAIL: "FAIL   ", BLOCKED: "BLOCKED",
                NOT_RUN: "NOTRUN"}.get(status, "?")
        print(f"  [{mark}] {name}" + (f"  -- {detail[:110]}" if detail else ""))

    print(f"ACIQ acceptance -- revision {run_id}\n")

    # 1. unit + integration + socket
    print("phase 1: environment-independent tests")
    rc, txt = run([sys.executable, "-m", "unittest", "discover",
                   "-s", "tests", "-t", "."])
    (outdir / "unittest.log").write_text(txt)
    n = 0
    for line in txt.splitlines():
        if line.startswith("Ran ") and " test" in line:
            n = int(line.split()[1])
    record("unit+integration+socket", PASS if rc == 0 else FAIL,
           f"{n} tests, exit {rc}", "unittest.log")

    # 2. metric integrity, independently
    print("\nphase 2: metric integrity")
    rc, txt = run([sys.executable, "-m", "unittest", "tests.test_measure",
                   "tests.test_measure_integration", "-v"])
    (outdir / "metric-integrity.log").write_text(txt)
    record("metric integrity", PASS if rc == 0 else FAIL,
           "arithmetic + socket recomputation", "metric-integrity.log")

    # 3. api security
    print("\nphase 3: api security")
    rc, txt = run([sys.executable, "-m", "unittest", "tests.test_api_security",
                   "-v"])
    (outdir / "api-security.log").write_text(txt)
    record("api security", PASS if rc == 0 else FAIL,
           "auth, bind policy, rate limit, audit", "api-security.log")

    # 4. classifier
    print("\nphase 4: classifier")
    rc, txt = run([sys.executable, str(ROOT / "tools" / "eval_classifier.py"),
                   "--json", str(outdir / "classifier-evaluation.json")])
    (outdir / "classifier-eval.log").write_text(txt)
    record("classifier evaluation", PASS if rc == 0 else FAIL,
           "16 constructed cases, two capacities", "classifier-eval.log")

    # 5. benchmarks
    print("\nphase 5: benchmarks")
    rc, txt = run([sys.executable, str(ROOT / "tools" / "bench.py"),
                   "--json", str(outdir / "benchmark.json")])
    (outdir / "benchmark.log").write_text(txt)
    record("control-plane benchmark", PASS if rc == 0 else FAIL, "", "benchmark.log")

    # 6. kernel-dependent gates
    print("\nphase 6: kernel-dependent gates")
    missing = [t for t in ("ip", "tc") if not have(t)]
    if missing or not root():
        why = []
        if missing:
            why.append("missing " + ", ".join(missing))
        if not root():
            why.append(f"euid={os.geteuid()}, need 0")
        if platform.machine() and os.path.exists("/.dockerenv"):
            why.append("container")
        detail = "; ".join(why)
        for g in ("testbed gate (21 checks)", "live enforcement",
                  "rollback under real tc failure", "live adaptation loop",
                  "FIFO/CAKE/ACIQ comparison", "30-minute stability"):
            record(g, BLOCKED, detail)
    else:
        rc, txt = run(["sudo", "env",
                       f"ACIQ_VENV={os.environ.get('ACIQ_VENV', '/home/mekarz/aciq-venv')}",
                       "./testbed/gate.sh"])
        (outdir / "gate.log").write_text(txt)
        record("testbed gate (21 checks)", PASS if rc == 0 else FAIL,
               f"exit {rc}", "gate.log")

    # 7. claim audit
    print("\nphase 7: claim audit")
    rc, txt = run([sys.executable, str(ROOT / "tools" / "audit_claims.py")])
    (outdir / "claim-audit.log").write_text(txt)
    record("claim audit", PASS if rc == 0 else FAIL,
           "constants, evidence, red-flag phrases", "claim-audit.log")

    counts = {s: sum(1 for g in gates if g["status"] == s)
              for s in (PASS, FAIL, BLOCKED, NOT_RUN)}
    env["finished_utc"] = datetime.now(timezone.utc).isoformat()
    env["gates"] = gates
    env["counts"] = counts
    # A complete acceptance run has no BLOCKED gates. Saying otherwise would be
    # the one dishonest thing this harness exists to prevent.
    env["complete"] = counts[BLOCKED] == 0
    (outdir / "acceptance.json").write_text(json.dumps(env, indent=2) + "\n")
    if a.out:
        Path(a.out).write_text(json.dumps(env, indent=2) + "\n")

    print(f"\n  PASS {counts[PASS]}  FAIL {counts[FAIL]}  "
          f"BLOCKED {counts[BLOCKED]}  NOT RUN {counts[NOT_RUN]}")
    print(f"  complete acceptance run: {env['complete']}")
    print(f"  evidence: {outdir.relative_to(ROOT)}/")
    return 0 if counts[FAIL] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())