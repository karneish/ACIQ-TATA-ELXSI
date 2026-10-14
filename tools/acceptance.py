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
MIN_TESTS = 892


#: Test modules covering mandatory release requirements. A skip in one of
#: these means the requirement is unverified, whatever the reason.
MANDATORY_MODULES = ("tests.test_rollback_live",)


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
    # Which tests were skipped, as fully-qualified names, so a skip can be
    # attributed to a module rather than merely counted.
    names = []
    for m in re.finditer(r"^(test_\w+) \((tests[\w.]+)\)\s+\.\.\.\s+skipped",
                         text, re.M):
        # the parenthesised group is the full dotted path including the method
        names.append(m.group(2))
    out["skipped_tests"] = names
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


#: Minimum paired seeds before a FIFO/CAKE/ACIQ comparison means anything.
#: The report refuses to emit a p-value below 6; 7 is what the gate collects.
MIN_COMPARISON_SEEDS = 6
#: Minimum soak duration for a stability claim, in seconds.
MIN_SOAK_S = 1800.0
#: A run with fewer observations than this has not converged, whatever the
#: estimator happened to print. The adaptation evidence on disk had 3.
MIN_ADAPT_SAMPLES = 10
#: Estimator further than this multiple of the true post-drop capacity is not a
#: detection, it is a guess.
ADAPT_TOLERANCE_X = 2.0


def _results(sub: str) -> list[dict]:
    """Every result.json under a results directory, parsed."""
    import json as _json
    out = []
    for f in sorted((ROOT / sub).glob("*/result.json")):
        try:
            d = _json.loads(f.read_text())
            # Stamp the run directory so evidence can be tied to a revision.
            d["_dir"] = str(f.parent.relative_to(ROOT))
            out.append(d)
        except (OSError, ValueError):
            continue
    return out


def _stamped_revision(sub: str) -> str:
    """The revision `host_gate.sh` recorded when it produced this evidence."""
    p = ROOT / sub / "REVISION"
    try:
        return p.read_text().strip()
    except OSError:
        return ""


def _revision_note(sub: str, current: str) -> str:
    """Say which revision the evidence came from, or that it is unbound.

    An evidence directory with no revision stamp cannot be attributed to any
    commit, and combining it with a current-revision report is exactly what
    makes a release claim unfalsifiable.
    """
    got = _stamped_revision(sub)
    if not got:
        return " [UNBOUND: no REVISION stamp]"
    # Prefix-tolerant on purpose. The stamp is written with `git rev-parse HEAD`
    # (full SHA) while callers naturally hold the short form, and comparing them
    # for equality made *every* stamp look like a mismatch -- including evidence
    # produced by the commit being reported on. A revision prefix is the same
    # revision.
    if got == current or got.startswith(current) or current.startswith(got):
        return ""
    return f" [evidence from revision {got[:8]}, not {current[:8]}]"


def check_experiment_evidence() -> list[tuple]:
    """Turn real experiment artefacts into gate verdicts.

    The five long-running gates were recorded as NOT RUN because nothing in the
    harness runs them. But the opposite is equally wrong: once someone HAS run
    them, the harness kept saying NOT RUN, because it never looked at what was
    on disk. So `sudo tools/host_gate.sh --full` would produce the evidence and
    change nothing in the summary.

    Each gate below states exactly what artefact counts as evidence and what
    would make it insufficient. A directory with the right name is not evidence;
    a partially-completed comparison is reported as INCONCLUSIVE rather than
    quietly counted.
    """
    rows: list[tuple] = []

    # 1. live enforcement -- the 21-check traffic gate
    log = None
    for cand in sorted((ROOT / "docs" / "evidence").glob("gate-*.log")):
        log = cand
    if log is None:
        rows.append(("live enforcement", NOT_RUN,
                     "no docs/evidence/gate-*.log; run sudo tools/host_gate.sh"))
    else:
        txt = log.read_text(errors="replace")
        fails = txt.count("[FAIL]")
        measured = txt.count("[MEASURED]")
        passed = txt.count("[PASS]")
        if fails:
            rows.append(("live enforcement", FAIL,
                         f"{fails} FAIL in {log.name}"))
        else:
            rows.append(("live enforcement", PASS,
                         f"{passed} PASS, {measured} MEASURED, 0 FAIL ({log.name})"))

    # 2. rollback under real tc failure -- the live rollback log
    rl = sorted((ROOT / "docs" / "evidence").glob("rollback-live-*.log"))
    if not rl:
        rows.append(("rollback under real tc failure", NOT_RUN,
                     "no docs/evidence/rollback-live-*.log"))
    else:
        txt = rl[-1].read_text(errors="replace")
        if "skipped=" in txt.splitlines()[-1] if txt.strip() else True:
            rows.append(("rollback under real tc failure", NOT_RUN,
                         f"{rl[-1].name}: live tests skipped, no evidence"))
        elif "OK" in txt.splitlines()[-1] if txt.strip() else False:
            rows.append(("rollback under real tc failure", PASS,
                         f"live rollback tests passed ({rl[-1].name})"))
        else:
            rows.append(("rollback under real tc failure", FAIL,
                         f"{rl[-1].name} did not pass"))

    # 3. live adaptation -- a capacity drop that was actually detected
    cur = rev()[:8]
    res = _results("data/host_gate_adapt")
    if not res:
        rows.append(("live adaptation loop", NOT_RUN,
                     "no data/host_gate_adapt; run: sudo tools/host_gate.sh --full"))
    else:
        r = res[0]
        applied = r.get("capacity_change_applied")
        est = r.get("estimator_mbps")
        target = r.get("link_end_mbps")
        n = len(r.get("samples") or [])
        note = _revision_note("data/host_gate_adapt", cur)
        detail = (f"{r.get('link_start_mbps')} -> {target} Mbps, "
                  f"estimator {est}, {n} samples{note}")
        if not applied:
            rows.append(("live adaptation loop", FAIL,
                         f"capacity change was not applied: "
                         f"{r.get('capacity_change_error') or 'no detail'}{note}"))
        elif est is None:
            rows.append(("live adaptation loop", FAIL,
                         f"estimator produced no reading after the drop{note}"))
        elif n < MIN_ADAPT_SAMPLES:
            # Not FAIL -- the run happened -- but not a detection either.
            rows.append(("live adaptation loop", NOT_RUN,
                         f"only {n} samples (need {MIN_ADAPT_SAMPLES}); the "
                         f"estimator has not converged, so this is INCONCLUSIVE "
                         f"rather than a detection{note}"))
        elif _shape_exceeded_truth(r, float(target)):
            # The tell-tale of the set_capacity/controller-write collision: the
            # measured throughput ends up ABOVE the capacity the link was
            # clamped to. That is not an adaptation, it is the controller having
            # overwritten the bottleneck it was supposed to be measuring.
            shape = _steady_goodput(r)
            rows.append(("live adaptation loop", FAIL,
                         f"measured {shape:.1f} Mbps on a link clamped to "
                         f"{target} Mbps: the policy write overwrote the "
                         f"capacity drop (1:1 is written by both the plan and "
                         f"set_capacity); adaptation is UNTESTABLE until the "
                         f"bottleneck is enforced out of band"))
        elif target and est > ADAPT_TOLERANCE_X * float(target):
            rows.append(("live adaptation loop", NOT_RUN,
                         f"estimator reported {est} Mbps for a link that is "
                         f"{target} Mbps ({est / float(target):.1f}x off); "
                         f"INCONCLUSIVE, not a detection{note}"))
        else:
            rows.append(("live adaptation loop", PASS, detail))

    # 4. FIFO / CAKE / ACIQ comparison
    dirs = {"b0_fifo": "data/host_gate_b0_fifo",
            "b1_cake95": "data/host_gate_b1_cake95",
            "aciq": "data/host_gate_aciq"}
    counts = {k: len(_results(v)) for k, v in dirs.items()}
    have = {k: v for k, v in counts.items() if v}
    if not have:
        rows.append(("FIFO/CAKE/ACIQ comparison", NOT_RUN,
                     "no comparison runs; run: sudo tools/host_gate.sh --full"))
    elif len(have) < 3:
        rows.append(("FIFO/CAKE/ACIQ comparison", NOT_RUN,
                     f"only {sorted(have)} present; all three systems required "
                     f"({counts})"))
    elif min(have.values()) < MIN_COMPARISON_SEEDS:
        rows.append(("FIFO/CAKE/ACIQ comparison", NOT_RUN,
                     f"{min(have.values())} paired seeds, need "
                     f"{MIN_COMPARISON_SEEDS}; a comparison below that is "
                     f"INCONCLUSIVE, not a result"))
    else:
        notes = {_revision_note(v, rev()[:8]) for v in dirs.values()}
        rows.append(("FIFO/CAKE/ACIQ comparison", PASS,
                     ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
                     + " paired seeds" + "".join(sorted(notes))))

    # 5. sustained stability
    res = _results("data/host_gate_soak")
    if not res:
        rows.append(("30-minute stability", NOT_RUN,
                     "no data/host_gate_soak; run: sudo tools/host_gate.sh --full"))
    else:
        r = res[0]
        dur = float(r.get("duration_s") or 0.0)
        if dur < MIN_SOAK_S:
            rows.append(("30-minute stability", NOT_RUN,
                         f"soak ran {dur:.0f}s, need {MIN_SOAK_S:.0f}s; a "
                         f"shorter run is not a stability result"))
        else:
            rows.append(("30-minute stability", PASS,
                         f"{dur:.0f}s sustained, "
                         f"{r.get('policy_changes')} policy changes"
                         + _revision_note("data/host_gate_soak", rev()[:8])))
    return rows


def _steady_goodput(result: dict) -> float:
    """Median throughput over the middle of the run, ignoring ramp edges."""
    import statistics
    vals = [sum((v or {}).get("goodput_mbps", 0.0)
                for v in (s.get("per_class") or {}).values())
            for s in (result.get("samples") or [])]
    vals = [v for v in vals if v > 0.0]
    return statistics.median(vals) if vals else 0.0


def _shape_exceeded_truth(result: dict, target: float) -> bool:
    """Did steady-state throughput end up above the emulated capacity?

    `set_capacity` implements the bottleneck by writing the HTB root class
    rate, and `build_plan` writes the same class from the capacity estimate. So
    a policy change overwrites the drop, the link stops being 10 Mbps, and the
    estimator then faithfully reports the larger number. Without this check the
    run reads as a clean adaptation rather than as a broken experiment.
    """
    return _steady_goodput(result) > target * ADAPT_TOLERANCE_X


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
    try:
        outdir.mkdir(parents=True, exist_ok=True)
        probe = outdir / ".writable"
        probe.write_text("")
        probe.unlink()
    except PermissionError:
        # Running once under sudo leaves root-owned evidence here, and the next
        # unprivileged run then dies with a bare PermissionError that looks like
        # an unrelated bug. Say what happened and what to do about it.
        print(f"cannot write evidence to {outdir}")
        print("  it was probably created by an earlier `sudo` run and is owned "
              "by root.")
        print(f"  fix: sudo chown -R $(id -u):$(id -g) {outdir}")
        print("  or re-run the whole harness as: sudo python3 tools/acceptance.py")
        return 1
    except OSError as e:
        print(f"cannot prepare {outdir}: {e}")
        return 1
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
                   "-s", "tests", "-t", ".", "-v"])
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

        # The five long-running gates are NOT done by anything above. They used
        # to simply not appear in the table when root was available, which is
        # the worst behaviour this harness could have: the summary looked
        # complete -- 8 PASS, 0 BLOCKED -- while five mandatory gates had never
        # run. An absent gate is not a passing gate.
        # Judged from artefacts on disk, so that running them actually closes
        # them. Previously these were hardcoded NOT_RUN, which meant
        # `host_gate.sh --full` could produce the evidence and change nothing.
        for g, st, detail in check_experiment_evidence():
            record(g, st, detail)

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
    # A skip is only disqualifying if it hides a *mandatory* gate. Running as
    # root skips test_acceptance's own "refuses without root" test -- that is an
    # artefact of the environment, not missing evidence about the product, and
    # treating it as blocking would make `complete` unreachable in exactly the
    # environment where it should become reachable.
    skipped = int(env.get("tests", {}).get("skipped", 0))
    skipped_mandatory = [n for n in env.get("tests", {}).get("skipped_tests", [])
                         if any(n.startswith(m) for m in MANDATORY_MODULES)]
    env["skipped"] = skipped
    env["skipped_mandatory"] = skipped_mandatory
    env["complete"] = (counts[BLOCKED] == 0
                       and counts[NOT_RUN] == 0
                       and not skipped_mandatory)
    (outdir / "acceptance.json").write_text(json.dumps(env, indent=2) + "\n")
    if a.out:
        Path(a.out).write_text(json.dumps(env, indent=2) + "\n")

    print(f"\n  PASS {counts[PASS]}  FAIL {counts[FAIL]}  "
          f"BLOCKED {counts[BLOCKED]}  NOT RUN {counts[NOT_RUN]}")
    if skipped:
        detail = (f"{skipped} test(s) skipped"
                  + (f", {len(skipped_mandatory)} of them mandatory"
                     if skipped_mandatory else " (none mandatory)"))
        print(f"  {detail} -- not counted as passed")
    print(f"  complete acceptance run: {env['complete']}")
    print(f"  evidence: {outdir.relative_to(ROOT)}/")
    return 0 if counts[FAIL] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())