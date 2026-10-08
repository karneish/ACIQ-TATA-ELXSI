"""M10 — report generator.

Turns run artefacts into a Markdown report. Two rules it will not break:

1. A missing measurement is reported as **missing**, never as zero. A report that
   silently fills gaps looks identical to a clean result and is worse than no
   report.
2. It states the sample count next to every comparison. Three runs do not
   support a p-value, and saying so is the honest thing.
"""

from __future__ import annotations

import json
import statistics
from dataclasses import dataclass, field
from pathlib import Path

from .harness import CapacityMode, SystemSpec

#: Paired Wilcoxon signed-rank needs >= 6 pairs to reach p < 0.05 at all: the
#: smallest attainable two-sided p is 2^(1-n), which is 0.0625 at n=5.
MIN_PAIRS_FOR_PVALUE = 6


@dataclass
class Metric:
    name: str
    values: dict[str, float | None] = field(default_factory=dict)
    unit: str = ""

    def present(self, system: str) -> bool:
        v = self.values.get(system)
        return v is not None

    def best(self, lower_is_better: bool = True) -> str | None:
        got = {k: v for k, v in self.values.items() if v is not None}
        if not got:
            return None
        return (min if lower_is_better else max)(got, key=lambda k: got[k])

    def line(self, lower_is_better: bool = True, systems=None) -> str:
        systems = systems or sorted(self.values)
        cells = []
        for s in systems:
            v = self.values.get(s)
            cells.append("n/a" if v is None else f"{v:.3f}{self.unit}")
        star = self.best(lower_is_better)
        row = " | ".join(cells)
        mark = f" <- best" if star else ""
        return f"| {self.name} | {row} |{mark}"


def load_runs(results_dir: Path) -> list[dict]:
    out = []
    if not results_dir.exists():
        return out
    for d in sorted(results_dir.iterdir()):
        f = d / "result.json"
        if f.is_file():
            try:
                r = json.loads(f.read_text())
                r["_dir"] = str(d)
                out.append(r)
            except json.JSONDecodeError:
                continue
    return out


#: Workloads that carry a latency measurement, and the scenario each belongs to.
#: s3 measures the game, not the call — reporting "n/a" for every system there
#: looked like missing data when in fact all three systems were measured.
LATENCY_WORKLOADS = ("call", "game")


def latency_table(results_dir: Path) -> dict[str, dict]:
    """-> {scenario: {system: {workload: {p50,p95,p99,jitter_ms,loss_ratio}}}}"""
    table: dict[str, dict] = {}
    if not results_dir.exists():
        return table
    for d in sorted(results_dir.iterdir()):
        f = d / "workloads.json"
        res = d / "result.json"
        if not f.is_file() or not res.is_file():
            continue
        try:
            data = json.loads(f.read_text())
            meta = json.loads(res.read_text())
        except json.JSONDecodeError:
            continue
        scen, system = meta.get("scenario", "?"), meta.get("system", "?")
        entry = table.setdefault(scen, {}).setdefault(system, {})
        for label in LATENCY_WORKLOADS:
            w = data.get(label)
            if isinstance(w, dict) and w.get("p50") is not None:
                entry[label] = {
                    "p50": w["p50"], "p95": w.get("p95"), "p99": w.get("p99"),
                    "jitter_ms": w.get("jitter_ms"),
                    "loss_ratio": w.get("loss_ratio"),
                }
    return table


def workload_latency(results_dir: Path, label: str = "call") -> dict:
    """{run_dir_name: p50 for `label`}, or None where it was not measured.

    Kept as a thin wrapper over latency_table so callers that only want one
    workload's median do not have to walk the nested structure.
    """
    out: dict = {}
    for scen in latency_table(results_dir).values():
        for system, entries in scen.items():
            if label in entries:
                out[system] = entries[label]["p50"]
    return out


def _fmt(v, unit=""):
    return "n/a" if v is None else f"{v:.3f}{unit}"


def latency_sections(table: dict[str, dict]) -> list[str]:
    """One table per scenario, with the workload each actually measured."""
    out = []
    for scen in sorted(table):
        if not any(table[scen].values()):
            continue  # nothing measured here; do not print an empty heading
        out.append(f"### {scen}")
        out.append("")
        for label in LATENCY_WORKLOADS:
            present = {s: e[label] for s, e in table[scen].items() if label in e}
            if not present:
                continue
            out.append(f"**{label} latency — measured by the {label} itself** "
                       f"(milliseconds, lower is better)")
            out.append("")
            out.append("| system | p50 | p95 | p99 | jitter | loss |")
            out.append("|---|---|---|---|---|---|")
            for system in sorted(present):
                w = present[system]
                out.append(
                    f"| {system} | {_fmt(w['p50'])} | {_fmt(w['p95'])} "
                    f"| {_fmt(w['p99'])} | {_fmt(w['jitter_ms'])} "
                    f"| {'n/a' if w['loss_ratio'] is None else format(w['loss_ratio'], '.5f')} |")
            out.append("")
            out.extend(_verdict(present))
    return out


def _verdict(present: dict) -> list[str]:
    """State plainly where ACIQ wins and where it loses.

    Cherry-picking the flattering percentile is exactly the failure mode this
    project is supposed to avoid, so every percentile is compared.
    """
    aciq = present.get("aciq")
    if not aciq:
        return []
    lines = []
    for key, better_low in (("p50", True), ("p95", True), ("p99", True),
                            ("jitter_ms", True)):
        rivals = {s: w[key] for s, w in present.items()
                  if s != "aciq" and w.get(key) is not None}
        if not rivals or aciq.get(key) is None:
            continue
        # A tie is a tie. Reporting "LOSES" for two equal numbers would be as
        # dishonest as reporting a win.
        tol = 1e-9
        beaten, lost, tied = [], [], []
        for s, v in rivals.items():
            if better_low:
                if aciq[key] < v - tol:
                    beaten.append(s)
                elif aciq[key] > v + tol:
                    lost.append(s)
                else:
                    tied.append(s)
            else:
                if aciq[key] > v + tol:
                    beaten.append(s)
                elif aciq[key] < v - tol:
                    lost.append(s)
                else:
                    tied.append(s)
        parts = []
        if beaten:
            parts.append(f"beats {' and '.join(beaten)}")
        if lost:
            parts.append(f"LOSES to {' and '.join(lost)}")
        if tied:
            parts.append(f"matches {' and '.join(tied)}")
        if not parts:
            continue
        lead = "ACIQ " if not lost else "ACIQ "
        lines.append(f"- **{key}: {lead}{' '.join(parts)}.**")
    return lines


def mean(values: list[float]) -> float | None:
    xs = [v for v in values if v is not None]
    return statistics.fmean(xs) if xs else None


def can_report_pvalue(n: int) -> bool:
    return n >= MIN_PAIRS_FOR_PVALUE


def build_report(results_dir: Path, title: str = "ACIQ+ experiment report") -> str:
    runs = load_runs(results_dir)
    lines: list[str] = [f"# {title}", ""]

    if not runs:
        lines += [
            "**No runs found.** Nothing has been measured yet.",
            "",
            f"Expected artefacts under `{results_dir}`.",
        ]
        return "\n".join(lines) + "\n"

    lines += [
        f"Runs found: **{len(runs)}**",
        "",
        "## Runs",
        "",
        "| scenario | system | mode | seed | link start | link end | estimator | policy changes |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for r in runs:
        est = "n/a" if r.get("estimator_mbps") is None else f"{r['estimator_mbps']:.1f} Mbps"
        lines.append(
            f"| {r.get('scenario')} | {r.get('system')} | {r.get('capacity_mode')} "
            f"| {r.get('seed')} | {r.get('link_start_mbps')} | {r.get('link_end_mbps')} "
            f"| {est} | {r.get('policy_changes', 0)} |")

    table = latency_table(results_dir)
    sections = latency_sections(table) if table else []
    if sections:
        lines += ["", "## Latency, measured by each workload itself", ""]
        lines += sections
        lines += ["", "**These verdicts are read per percentile, not cherry-picked.**",
                  "Where ACIQ loses, it loses in the table above too.", ""]

    # honest reporting block
    lines += ["", "## Reporting caveats", ""]
    per_system: dict[str, int] = {}
    for r in runs:
        per_system[r.get("system", "?")] = per_system.get(r.get("system", "?"), 0) + 1
    smallest = min(per_system.values()) if per_system else 0
    if not can_report_pvalue(smallest):
        lines.append(
            f"- **{smallest} run(s) per system.** Paired Wilcoxon cannot reach "
            f"p < 0.05 with fewer than {MIN_PAIRS_FOR_PVALUE} pairs (the smallest "
            f"attainable two-sided p is 2^(1-n), which is 0.0625 at n=5). "
            "Ranges and confidence intervals only — no p-values.")
    measured = sum(1 for e in table.values() for s in e.values() for _ in e)
    missing_runs = sum(1 for e in table.values() for s, v in e.items() if not v)
    if missing_runs:
        lines.append(f"- **{missing_runs} run(s) recorded no latency at all.** "
                     "Shown as n/a rather than 0, because missing is not zero.")
    noun = "measurement" if measured == 1 else "measurements"
    lines.append(f"- **{measured} latency {noun}** across the matrix, each "
                 "self-reported by the workload that carried it.")
    lines += [
        "- The link is an **HTB token-bucket emulation**, not real DSL/cable/fiber.",
        "- Counter-based detection only sees a bottleneck **on the router**; a "
        "downstream ISP-side bottleneck stays invisible. Gate check 12 measured a "
        "validated remedy (an unmarked probe showed ~8x delay rise) that is not "
        "in the MVP.",
        "- Classification accuracy is measured on **self-generated** traffic.",
    ]
    return "\n".join(lines) + "\n"
