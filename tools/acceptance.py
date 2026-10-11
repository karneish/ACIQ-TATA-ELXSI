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
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "artifacts" / "validation"

PASS, FAIL, BLOCKED, NOT_RUN = "PASS", "FAIL", "BLOCKED", "NOT RUN"


#: Floor on collected tests. Not a substitute for checking the exit code -- it
#: catches the quieter failure where the suite still exits 0 but collection has
#: silently shrunk (a broken import in one test module drops it, and `discover`
#: reports the rest as a success). Without a floor, deleting a whole test module
#: would still produce a green acceptance run.
MIN_TESTS = 832


def parse_unittest(text: str) -> dict:
    """Extract outcome from unittest output. Pure, so it can be unit-tested."""
    out = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0,
           "ok": False, "summary": ""}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Ran ") and " test" in line:
            parts = line.split()
            for i, tok in enumerate(parts):
                if tok == "test" or tok == "tests":
                    try:
                        out["tests"] = int(parts[i - 1])
                    except (ValueError, IndexError):
                        pass
                    break
            out["summary"] = line
        elif line.startswith("FAILED") or line.startswith("OK"):
            out["ok"] = line.startswith("OK")
            if line.startswith("FAILED"):
                out["ok"] = False
    # Counts appear as `OK (skipped=6)` or `FAILED (failures=2, skipped=1)`.
    for field in ("failures", "errors", "skipped"):
        m = re.search(rf"{field}=(\d+)", text)
        if m:
            out[field] = int(m.group(1))
    return out


def suite_verdict(rc: int, text: str, min_tests: int = MIN_TESTS) -> tuple:
    """(status, detail) for the test-suite gate. Skips and low counts count."""
    p = parse_unittest(text)
    if rc != 0 or not p["ok"]:
        return FAIL, (f"exit {rc}, {p['summary'] or 'unittest reported failure'}")
    if p["tests"] < min_tests:
        # green, but too few tests to mean anything
        return FAIL, (f"only {p['tests']} tests collected, floor is {min_tests}; "
                      f"a shrinking suite must not pass silently")
    detail = f"{p['tests']} tests"
    if p["skipped"]:
        detail += f", {p['skipped']} skipped"
    return PASS, detail


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


def sudo_ok() -> bool:
    """Is a usable, non-interactive sudo available?

    `sudo -v && python3 tools/acceptance.py` refreshes the sudo timestamp but
    leaves the *harness* running as the invoking user, so a harness that only
    checked euid reported every mandatory gate BLOCKED even though root was one
    command away. BLOCKED is the honest answer for "I cannot run this"; using an
    available sudo first is simply trying.
    """
    if root() or shutil.which("sudo") is None:
        return False
    return subprocess.run(["sudo", "-n", "true"], capture_output=True,
                          timeout=10).returncode == 0


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
    ap.add_argument("--min-tests", type=int, default=MIN_TESTS,
                    help="floor on collected tests (default %(default)s)")
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
    status, detail = suite_verdict(rc, txt, a.min_tests)
    p = parse_unittest(txt)
    record("unit+integration+socket", status, f"{detail}, exit {rc}",
           "unittest.log")
    env["tests"] = p

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
    elevate = sudo_ok()
    if missing or not (root() or elevate):
        why = []
        if missing:
            why.append("missing " + ", ".join(missing))
        if not root() and not elevate:
            why.append(f"euid={os.geteuid()}, need 0 and no cached sudo; "
                       f"run `sudo python3 tools/acceptance.py`")
        if platform.machine() and os.path.exists("/.dockerenv"):
            why.append("container")
        detail = "; ".join(why)
        for g in ("testbed gate (21 checks)", "live enforcement",
                  "live rollback verification (kernel)",
                  "rollback under real tc failure", "live adaptation loop",
                  "FIFO/CAKE/ACIQ comparison", "30-minute stability"):
            record(g, BLOCKED, detail)
    else:
        sudo_argv = [] if root() else ["sudo", "-n"]
        rc2, txt2 = run(sudo_argv + [sys.executable, "-m", "unittest",
                                     "tests.test_rollback_live", "-v"])
        (outdir / "rollback-live.log").write_text(txt2)
        record("live rollback verification (kernel)", PASS if rc2 == 0 else FAIL,
               "tc read-back in an isolated namespace", "rollback-live.log")
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
    # A complete acceptance run has no BLOCKED gates *and* no skipped tests.
    #
    # The second half matters as much as the first. The six live-kernel tests
    # skip whenever root or iproute2 is missing, and `suite_verdict` counts a
    # skipped run as PASS because a skip is not a failure. So a run could
    # report `complete: true` while the mandatory rollback verification had in
    # fact never executed -- the exact substitution of "did not run" for
    # "passed" that this harness exists to prevent.
    mandatory_skipped = int(env.get("tests", {}).get("skipped", 0))
    env["skipped"] = mandatory_skipped
    env["complete"] = counts[BLOCKED] == 0 and mandatory_skipped == 0
    (outdir / "acceptance.json").write_text(json.dumps(env, indent=2) + "\n")
    if a.out:
        Path(a.out).write_text(json.dumps(env, indent=2) + "\n")

    print(f"\n  PASS {counts[PASS]}  FAIL {counts[FAIL]}  "
          f"BLOCKED {counts[BLOCKED]}  NOT RUN {counts[NOT_RUN]}")
    if mandatory_skipped:
        print(f"  {mandatory_skipped} test(s) skipped -- not counted as passed")
    print(f"  complete acceptance run: {env['complete']}")
    print(f"  evidence: {outdir.relative_to(ROOT)}/")
    return 0 if counts[FAIL] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())