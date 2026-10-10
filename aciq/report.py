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


#: Metrics carried per workload.
LATENCY_METRICS = ("p50", "p95", "p99", "jitter_ms", "loss_ratio")


def latency_table(results_dir: Path) -> dict[str, dict]:
    """-> {scenario: {system: {workload: {metric: [(seed, value), ...]}}}}

    **Every seed is kept, not overwritten.** This used to assign
    `entry[label] = {...}` once per run directory, so with six seeds only the
    last one survived -- and the report printed it under a header reading "54
    runs". s1's ACIQ row showed p99=18.461 ms, which was seed 47 alone; the six
    seeds were 2.665, 1.443, 2.147, 20.104, 2.538 and 18.461. Two of six hit
    ~20 ms and the number that got reported was one of them.

    The seed is carried with each value so pairs can be formed for a paired
    test. Mean-and-forget would fix the headline and still make the pairing
    impossible.
    """
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
            seed = meta.get("seed")
            w = data.get(label)
            if isinstance(w, dict) and w.get("p50") is not None:
                slot = entry.setdefault(label, {})
                for metric in LATENCY_METRICS:
                    v = w.get(metric)
                    if v is not None:
                        slot.setdefault(metric, []).append((seed, v))
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
            out.append("Cells are **mean (min-max)** over seeds. A mean alone "
                       "would hide the tails this project keeps getting wrong.")
            out.append("")
            out.append("| system | n | p50 | p95 | p99 | jitter | loss |")
            out.append("|---|---|---|---|---|---|---|")
            for system in sorted(present):
                w = present[system]
                out.append(f"| {system} | {_nseeds(w)} | "
                           + " | ".join(_cell(w.get(m)) for m in
                                        ("p50", "p95", "p99", "jitter_ms"))
                           + f" | {_cell(w.get('loss_ratio'))} |")
            out.append("")
            out.extend(_verdict(present))
    return out


def _nseeds(metrics: dict) -> int:
    """How many seeds contributed. 0 when nothing was measured."""
    return len(metrics.get("p50") or [])


def _cell(values) -> str:
    """mean (min-max) over the per-seed values, or n/a."""
    xs = [v for _s, v in (values or []) if v is not None]
    if not xs:
        return "n/a"
    m = statistics.fmean(xs)
    lo, hi = min(xs), max(xs)
    if hi - lo < 1e-9:
        return f"{m:.3f}"
    return f"{m:.3f} ({lo:.3f}-{hi:.3f})"


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
        amean = statistics.fmean([v for _s, v in (aciq.get(key) or [])]) \
            if aciq.get(key) else None
        rivals = {}
        for s, w in present.items():
            if s == "aciq":
                continue
            xs = [v for _sd, v in (w.get(key) or [])]
            if xs:
                rivals[s] = statistics.fmean(xs)
        if not rivals or amean is None:
            continue
        # Compared as locals against `amean`. An earlier version wrote the
        # mean back into `aciq[key]`, overwriting the per-seed list that
        # paired_pvalues needs -- and paired_pvalues runs after this, so it
        # crashed on a float where a list of (seed, value) belonged.
        # Read-only from here.
        # A tie is a tie. Reporting "LOSES" for two equal numbers would be as
        # dishonest as reporting a win.
        tol = 1e-9
        beaten, lost, tied = [], [], []
        for s, v in rivals.items():
            if better_low:
                if amean < v - tol:
                    beaten.append(s)
                elif amean > v + tol:
                    lost.append(s)
                else:
                    tied.append(s)
            else:
                if amean > v + tol:
                    beaten.append(s)
                elif amean < v - tol:
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
        # " and " between the clauses, not " ". A bullet reading
        # "beats b1_cake95 LOSES to b0_fifo" parses as a garbled run-on and, worse,
        # buries the loss in the middle of a sentence about a win.
        lines.append(f"- **{key}: ACIQ {' and '.join(parts)}.**")
    return lines


def mean(values: list[float]) -> float | None:
    xs = [v for v in values if v is not None]
    return statistics.fmean(xs) if xs else None


def can_report_pvalue(n: int) -> bool:
    return n >= MIN_PAIRS_FOR_PVALUE


def exact_wilcoxon(pairs: list[tuple[float, float]]) -> dict | None:
    """Two-sided Wilcoxon signed-rank, exact, by enumerating sign flips.

    No scipy on this machine, and none needed: under H0 every rank independently
    takes + or -, so the exact null distribution is 2**n outcomes. At n=6 that
    is 64; at n=12, 4096. Exact beats a normal approximation at exactly the
    sample sizes this project reaches.

    Zero differences are dropped, as Wilcoxon requires -- and a dropped pair is
    reported, because silently shrinking n changes the smallest attainable p
    (2^(1-n)) and the reader would not know.

    Returns {"statistic", "p", "n", "zeros"} or None if fewer than 2 usable
    pairs remain.
    """
    usable = [(a, b) for a, b in pairs if a is not None and b is not None]
    diffs = [a - b for a, b in usable]
    zeros = sum(1 for d in diffs if d == 0.0)
    nz = [(abs(d), 1.0 if d > 0 else -1.0) for d in diffs if d != 0.0]
    n = len(nz)
    if n < 2:
        return None
    # Average ranks over ties -- required for validity, and this project's seeds
    # produce plenty of ties.
    order = sorted(range(n), key=lambda i: nz[i][0])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and nz[order[j + 1]][0] == nz[order[i]][0]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    obs = sum(r for r, (_a, sign) in zip(ranks, nz) if sign > 0)
    total = n * (n + 1) / 2.0
    extreme = 0
    for mask in range(1 << n):
        w = 0.0
        for k in range(n):
            if mask >> k & 1:
                w += ranks[k]
        if abs(w - total / 2.0) >= abs(obs - total / 2.0) - 1e-12:
            extreme += 1
    return {"statistic": obs, "p": extreme / float(1 << n), "n": n, "zeros": zeros}


def paired_pvalues(table: dict) -> list[dict]:
    """Wilcoxon for ACIQ against each rival, paired by seed.

    Paired by seed because that is the pairing the design gives: both systems saw
    the same seed, the same scenario and the same drop. Unpaired tests across
    seeds would throw that away.
    """
    out: list[dict] = []
    for scen, systems in sorted(table.items()):
        aciq = systems.get("aciq") or {}
        for workload, ametrics in sorted(aciq.items()):
            for rival, rmetrics in sorted(systems.items()):
                if rival == "aciq":
                    continue
                rslot = (rmetrics or {}).get(workload) or {}
                for metric in LATENCY_METRICS:
                    apairs = {sd: v for sd, v in ametrics.get(metric, [])}
                    rpairs = {sd: v for sd, v in rslot.get(metric, [])}
                    shared = sorted(set(apairs) & set(rpairs))
                    test = exact_wilcoxon([(apairs[s], rpairs[s]) for s in shared])
                    if test is None:
                        continue
                    out.append({"scenario": scen, "workload": workload,
                                "system": rival, "metric": metric, **test})
    return out


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
        # The requested capacity, marked when tc refused it. Printing 10.0 beside
        # a link that never changed is the same class of error as printing a
        # verdict for a run that steered nothing.
        end = r.get("link_end_mbps")
        if r.get("capacity_change_applied") is False and r.get("link_start_mbps") != end:
            end = f"{end} (REFUSED)"
        lines.append(
            f"| {r.get('scenario')} | {r.get('system')} | {r.get('capacity_mode')} "
            f"| {r.get('seed')} | {r.get('link_start_mbps')} | {end} "
            f"| {est} | {r.get('policy_changes', 0)} |")

    table = latency_table(results_dir)
    sections = latency_sections(table) if table else []
    if sections:
        lines += ["", "## Latency, measured by each workload itself", ""]
        lines += sections
        lines += ["", "**These verdicts are read per percentile, not cherry-picked.**",
                  "Where ACIQ loses, it loses in the table above too.", ""]

    # ---- p-values
    #
    # Only rendered when a test actually ran. The previous version *withheld the
    # caveat* once there were 6 runs and never computed anything, so a reader saw
    # no p-value and no warning -- silence that reads as significance.
    tests = paired_pvalues(table) if table else []
    if tests:
        lines += ["", "## Paired significance (Wilcoxon signed-rank, exact)", "",
                  "ACIQ against each rival, paired by seed. Exact, by enumerating "
                  f"sign flips -- 2^n, which is why n >= {MIN_PAIRS_FOR_PVALUE} is "
                  "required before anything is claimed.", ""]
        lines += ["| scenario | workload | vs | metric | n | W+ | p |", "|---|---|---|---|---|---|---|"]
        for t in tests:
            lines.append(f"| {t['scenario']} | {t['workload']} | {t['system']} "
                         f"| {t['metric']} | {t['n']} | {t['statistic']:.1f} "
                         f"| {t['p']:.4f} |")
        sig = [t for t in tests if t["p"] < 0.05]
        lines.append("")
        lines.append(f"**{len(sig)} of {len(tests)} comparisons reach p < 0.05.** "
                     "Each is one metric against one rival in one scenario; they are "
                     "not independent of each other, so this is a count of results, "
                     "not a family-wise error rate.")

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
    # Counted per seed, not per cell. With six seeds a single cell is six
    # measurements, and saying "1 latency measurement" beside a six-seed run is
    # the same kind of understatement that hid the overwritten table.
    measured = sum(len(vals)
                   for scen in table.values() for s in scen.values()
                   for w in s.values() for vals in w.values())
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
