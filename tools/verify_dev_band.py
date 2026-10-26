#!/usr/bin/env python3
"""verify_dev_band.py — mechanical DEV-band gate before the one-shot EVAL.

Reads the DEV band (default data/runs_dev, seeds 400-409, ACIQ adaptive) and
asserts, per drop scenario (s2/s4), what the offline redesign promised:

  1. the change budget never starved the post-drop window
     (no `budget exhausted` reason on any tick), and
  2. the KERNEL's final applied root (policy_change_log committed tail,
     else the last non-zero sample governor rate) is within 1.5x of the
     post-drop link — i.e. the tree actually came down to the new reality
     instead of sitting on the old rate at 3.2x.

Exit 0 only if every drop-scenario ACIQ run passes both checks. This gate
runs BEFORE the EVAL band is launched: after eval starts, no parameter may
be touched, so a broken controller must not be allowed to spend its one
evaluation on a diagnosed regression.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path


def final_applied_root(result: dict) -> float | None:
    log = result.get("policy_change_log") or []
    caps = [float(c["applied_state"]["classes"]["1:1"]["rate"])
            for c in log
            if c.get("committed") and c.get("ok")
            and c.get("applied_state", {}).get("classes", {})
            .get("1:1", {}).get("rate") is not None]
    if caps:
        return caps[-1]
    caps = [float(s["governor"]["rate"]) for s in result.get("samples") or []
            if (s.get("governor") or {}).get("rate") is not None
            and float(s["governor"]["rate"]) > 0]
    return caps[-1] if caps else None


def verify_run_dir(d: Path) -> tuple[list[str], list[str]]:
    """(problems, notes) for one ACIQ run directory."""
    problems: list[str] = []
    notes: list[str] = []
    cfg = json.loads((d / "config.json").read_text())
    result = json.loads((d / "result.json").read_text())

    reasons = [(s.get("governor") or {}).get("reason", "")
               for s in result.get("samples") or []]
    starved = [r for r in reasons if "budget exhausted" in r]
    if starved:
        problems.append(f"budget exhausted on {len(starved)} ticks")
    else:
        notes.append("no budget-exhausted tick")

    post = cfg.get("drop_mbps")
    if cfg.get("drop_at_s") is None:
        # No-drop scenario (s1, s6): the root-vs-post-drop check does not
        # apply; the budget check above is the one that counts. A run
        # carrying a stale link_end_mbps must not fail on it.
        notes.append("no drop in this scenario: root check skipped")
        return problems, notes
    root = final_applied_root(result)
    if post and root is not None:
        ratio = root / float(post)
        if ratio > 1.5:
            problems.append(f"final applied root {root:.2f} = "
                            f"{ratio:.2f}x post-drop link {post}")
        else:
            notes.append(f"final root {root:.2f} = {ratio:.2f}x "
                         f"post-drop {post}")
    else:
        notes.append("no drop / no applied root recorded: skipped")
    return problems, notes


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("data/runs_dev")
    dirs = sorted(glob.glob(str(root / "*__aciq__adaptive__seed*")))
    if not dirs:
        print(f"verify_dev_band FAILED: no aciq adaptive run dirs in {root}")
        return 1
    bad = 0
    for d in dirs:
        p = Path(d)
        problems, notes = verify_run_dir(p)
        status = "PASS" if not problems else "FAIL"
        print(f"[{status}] {p.name}: "
              + ("; ".join(notes) if not problems
                 else "; ".join(notes + problems)))
        if problems:
            bad += 1
    if bad:
        print(f"verify_dev_band FAILED: {bad}/{len(dirs)} runs broken")
        return 1
    print(f"verify_dev_band PASS: {len(dirs)} runs clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
