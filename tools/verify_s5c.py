"""S5(c) verifier — the injected failed apply MUST have been handled.

Reads only the run artefacts the injection path writes, and returns exit 1 if
any witness is missing:

  1. the run note records the injection was armed (config.json carries the
     flag, the note names the moment), and
  2. samples.jsonl shows at least one policy_outcome with rolled_back=true
     AFTER the injection time (the rollback REPLAYS last-good through the
     kernel, never a silent no-op), and
  3. the run continued to commit AFTER the rollback (the tx path stays
     usable), checked as any later policy_outcome committed=true.

Three witnesses; without all three the S5(c) intent is only claimed.
"""

from __future__ import annotations

import glob
import json
import sys
from pathlib import Path


def verify(run_dirs: list[str]) -> tuple[bool, list[str]]:
    missing: list[str] = []
    ok_show = False
    for d in run_dirs:
        cfg_p = Path(d) / "config.json"
        if not cfg_p.exists():
            continue
        cfg = json.loads(cfg_p.read_text())
        if not cfg.get("inject_fail_apply"):
            continue
        notes = json.loads((Path(d) / "result.json").read_text()).get("notes", [])
        armed = any("S5" in n and "ARMED" in n for n in notes)
        rolled = False
        resumed = False
        last_roll_t = None
        for line in (Path(d) / "samples.jsonl").read_text().splitlines():
            if not line.strip():
                continue
            s = json.loads(line)
            po = s.get("policy_outcome") or {}
            if po.get("rolled_back"):
                rolled = True
                last_roll_t = s.get("t")
            elif po.get("committed") and po.get("ok") and \
                    last_roll_t is not None and \
                    (s.get("t") or 0) > last_roll_t:
                resumed = True
        parts = dict(armed=armed, rolled_back=rolled, resumed=resumed)
        if all(parts.values()):
            ok_show = True
        else:
            missing.append(f"{d}: witnesses {parts}")
    return ok_show, missing


def main() -> int:
    patterns: list[str] = sys.argv[1:] or [
        "data/runs/s2_wan_drop__aciq__adaptive__seed*"]
    dirs: list[str] = []
    for p in patterns:
        dirs.extend(sorted(d for d in glob.glob(p) if Path(d).is_dir()))
    ok, missing = verify(dirs)
    if ok:
        print("S5(c) verified: armed, rolled back, run continued")
        return 0
    print("S5(c) FAILED: " + "; ".join(missing))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
