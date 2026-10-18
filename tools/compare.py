#!/usr/bin/env python3
"""Produce a multi-system comparison report with paired significance tests.

WHY THIS EXISTS

The brief's central methodological requirement is to compare against a
deterministic baseline and show the model improves a measurable outcome. Every
comparison gate writes each system into its own results directory, so a crashed
system cannot corrupt another's evidence -- which is correct, and had a
consequence nobody noticed:

    build_report() reads exactly one directory

So every report the generator ever produced contained ACIQ alone. The `systems`
table never held more than one entry, `paired_pvalues()` never ran, and no
p-value was ever printed. The baseline comparison existed only as numbers typed
by hand into a Markdown document.

This reads several directories at once, merges them read-only, and reuses the
existing table, section and Wilcoxon code unchanged.

    sudo tools/compare.py --congested
    sudo tools/compare.py --light
    sudo tools/compare.py --out /tmp/cmp.md --congested
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from aciq.report import compare_report  # noqa: E402

#: Gate name -> results directory prefix. The order fixes the table's column
#: order, so ACIQ leads and the baselines follow.
GATES = {
    "congested": "host_gate_congested",
    "light": "host_gate",
}
SYSTEMS = ("aciq", "b0_fifo", "b1_cake95")


def dirs_for(gate: str) -> dict[str, Path]:
    prefix = GATES[gate]
    return {s: ROOT / "data" / f"{prefix}_{s}" for s in SYSTEMS}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--congested", action="store_true",
                    help="compare on a dropped 20 Mbps link (s2_wan_drop)")
    ap.add_argument("--light", action="store_true",
                    help="compare at 100 Mbps (s3_tv_and_gaming)")
    ap.add_argument("--out", default=str(ROOT / "data" / "COMPARISON.md"))
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()

    if not (a.congested or a.light):
        ap.error("choose at least one of --congested / --light")

    chunks = []
    for gate, title in (("congested", "Congested link (100 -> 20 Mbps)"),
                        ("light", "Light load (100 Mbps)")):
        if not (a.congested and gate == "congested") and \
           not (a.light and gate == "light"):
            continue
        dirs = dirs_for(gate)
        present = {k: v for k, v in dirs.items() if v.exists()}
        missing = sorted(set(dirs) - set(present))
        if missing:
            # Stated, not silently skipped: an absent baseline must not read
            # as a comparison that happened.
            print(f"[warn] {gate}: no evidence for {missing}", file=sys.stderr)
        if not present:
            continue
        chunks.append(compare_report(present, f"ACIQ+ — {title}"))

    if not chunks:
        print("No comparison evidence found. Run: "
              "sudo tools/host_gate.sh --congested-only", file=sys.stderr)
        return 1

    body = "\n\n---\n\n".join(chunks)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(body)
    if not a.quiet:
        print(f"comparison written to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())