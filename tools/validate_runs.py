#!/usr/bin/env python3
"""Validate experiment run artifacts into ARTIFACT/VALID/PASSING classes.

Rules are derived from the run schema (config.json + result.json) and the
dev-band layout (data/runs_dev3/<scenario>__<arm>__<mode>__seedN/):
  ARTIFACT COMPLETE : result.json parses
  VALID             : identity/scenario/seed match config.json, provenance
                      (commit_hash) present, finite numerics, no negative
                      goodput/backlog, sample coverage, no capacity error
  PASSING           : VALID and no execution-failure indications
                      (acceptance thresholds are NOT judged here; the
                      existing gates e.g. tools/verify_round3.py own those)

Usage: python3 tools/validate_runs.py [runs-root ...]   (default data/runs_dev3)
Writes reports/experiment_validation_report.{json,md}.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import time as _time
from collections import defaultdict

DIR_RE = re.compile(r"^(?P<sc>.+)__(?P<arm>.+)__(?P<mode>.+)__seed(?P<seed>\d+)$")


def finite(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(float(x))


def check_run(run_dir):
    """Return (stage, checks) — stage in artifact/valid/passing/missing/invalid."""
    run_dir = str(run_dir)
    checks = {}
    rp = os.path.join(run_dir, "result.json")
    cp = os.path.join(run_dir, "config.json")
    if not os.path.exists(rp):
        return "artifact-missing", {"error": "result.json absent"}
    try:
        res = json.load(open(rp))
    except Exception as e:  # noqa: BLE001
        return "artifact-invalid", {"error": f"result.json parse: {e}"}

    m = DIR_RE.match(os.path.basename(run_dir.rstrip("/")))
    if not m:
        return "artifact-invalid", {"error": "run dir name not sceded"}
    ok = True
    reasons = []

    # identity vs config.json (if present) vs dir name
    conf = None
    if os.path.exists(cp):
        try:
            conf = json.load(open(cp))
        except Exception as e:  # noqa: BLE001
            reasons.append(f"config.json parse: {e}")
            ok = False
    for key in ("scenario", "system", "seed"):
        v = res.get(key)
        dv = int(m.group("seed")) if key == "seed" else m.group("sc" if key == "scenario" else "arm")
        if v != dv:
            reasons.append(f"result.{key}={v!r} != dir {dv!r}")
            ok = False
        if conf is not None and conf.get(key) != v:
            reasons.append(f"config.{key}={conf.get(key)!r} != result {v!r}")
            ok = False
    if conf is not None:
        if res.get("capacity_mode") not in (None, conf.get("mode")):
            reasons.append("capacity_mode != config.mode")
            ok = False
        if finite(conf.get("link_mbps")) and res.get("link_start_mbps") != conf.get("link_mbps"):
            reasons.append("link_start_mbps != config.link_mbps")
            ok = False
        # NOTE: link_end_mbps semantics are scenario-specific (step_up runs the
        # link UP to conf.ramp-like values; drop_mbps is not a universal
        # end-state). Only record, never enforce, to avoid schema conflicts.
        checks["link_end_mbps"] = res.get("link_end_mbps")

    # provenance
    ch = res.get("commit_hash")
    if not (isinstance(ch, str) and re.fullmatch(r"[0-9a-f]{7,40}", ch)):
        reasons.append(f"bad commit_hash {ch!r}")
        ok = False
    if conf is not None:
        cch = conf.get("commit_hash")
        if isinstance(cch, str) and isinstance(ch, str) and not ch.startswith(cch[:7]):
            reasons.append("result commit_hash != config commit_hash")
            ok = False

    # numerics / coverage
    dur = res.get("duration_s")
    if not finite(dur) or dur <= 0:
        reasons.append(f"bad duration_s {dur!r}")
        ok = False
    samples = res.get("samples")
    if not isinstance(samples, list) or not samples:
        reasons.append("samples empty")
        ok = False
    else:
        span = samples[-1].get("t", 0) - samples[0].get("t", 0)
        if finite(dur) and span < 0.5 * dur:
            reasons.append(f"sample span {span:.1f}s < half of duration {dur:.1f}s")
            ok = False
        for i, sm in enumerate(samples):
            if not (finite(sm.get("t")) or sm.get("t") is None):
                reasons.append(f"sample[{i}] t invalid")
                ok = False
                break
            pc = sm.get("per_class") or {}
            for cls, mtr in pc.items():
                for k in ("goodput_mbps", "drop_rate_per_s", "overlimit_rate_per_s", "backlog_bytes"):
                    v = mtr.get(k)
                    if v is None:
                        continue
                    if not finite(v) or v < 0:
                        reasons.append(f"sample[{i}].{cls}.{k}={v!r} invalid")
                        ok = False
                        break
                if not ok:
                    break
            if not ok:
                break
        est = res.get("estimator_mbps")
        if est is not None and not finite(est):
            reasons.append(f"estimator_mbps {est!r} invalid")
            ok = False

    # execution failure indications (artifact still VALID; not PASSING)
    err = res.get("capacity_change_error") or ""
    stage_ok = not err
    bstate = res.get("bottleneck_state") or ""
    if not bstate:
        reasons.append("bottleneck_state absent")
        ok = False

    failed = len(reasons) > 0
    if failed:
        return "invalid", {"checks": checks, "failures": reasons}
    if not stage_ok:
        return "valid-with-execution-error", {"failures": reasons}
    if conf is not None and conf.get("inject_fail_apply"):
        return "passing-failure-drill", {"note": "configured failure-injection run; PASS here means executed-as-designed"}
    return "passing", {"failures": []}


def _head():
    """Short HEAD of the tree this validation ran against (None when git is
    unavailable; the field must exist, not silently vanish)."""
    try:
        r = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"],
                                    text=True, timeout=5)
        return r.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="*", default=["data/runs_dev3"])
    ap.add_argument("--out", default="reports/experiment_validation_report")
    args = ap.parse_args(argv)

    stats = defaultdict(int)
    per = defaultdict(lambda: defaultdict(int))
    details = []
    for root in args.roots:
        if not os.path.isdir(root):
            continue
        for name in sorted(os.listdir(root)):
            rd = os.path.join(root, name)
            if not os.path.isdir(rd) or not DIR_RE.match(name):
                continue
            stage, info = check_run(rd)
            stats[stage] += 1
            m = DIR_RE.match(name)
            per[(m.group("sc"), m.group("arm"))][stage] += 1
            if stage not in ("passing",):
                details.append({"run": name, "stage": stage, **info})

    total = sum(stats.values())
    summary = {
        "planned_seed_runs": total,
        "artifact_complete_runs": total,
        "valid_runs": stats["passing"] + stats["passing-failure-drill"],
        "passing_runs": stats["passing"],
        "failure_drill_runs": stats["passing-failure-drill"],
        "invalid_runs": stats["invalid"],
        "artifact_incomplete_runs": stats["artifact-missing"],
        "unknown_runs": stats["artifact-invalid"],
    }
    out = {
        "generated_at": _time.strftime("%Y-%m-%dT%H:%M:%S+00:00",
                                      _time.gmtime()),
        "revision": _head(),
        "summary": summary,
        "per_cell": {f"{s}__{a}": dict(v) for (s, a), v in sorted(per.items())},
        "problem_runs": details,
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    json.dump(out, open(args.out + ".json", "w"), indent=2, sort_keys=True)

    lines = ["# Experiment validation report", "",
             f"Roots: {', '.join(args.roots)}", "",
             "| metric | count |", "|---|---|"]
    for k, v in summary.items():
        lines.append(f"| {k} | {v} |")
    lines += ["", "## Per-cell", "", "| cell | value |", "|---|---|"]
    for cell, v in sorted(out["per_cell"].items()):
        lines.append(f"| {cell} | {json.dumps(v, sort_keys=True)} |")
    if details:
        lines += ["", "## Problem runs", ""]
        for d in details:
            lines.append(f"- {d['run']}: {d['stage']} — {d.get('error') or d.get('failures')}")
    open(args.out + ".md", "w").write("\n".join(lines) + "\n")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
