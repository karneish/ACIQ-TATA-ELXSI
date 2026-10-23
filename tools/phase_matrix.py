"""Phase 5/6 matrix driver: N seeds x M systems, then paired comparison.

One invocation runs the experiment matrix (real or --dry-run) and then, IF
the runs wrote real results, pairs them BY SEED and renders the Wilcoxon
table from aciq.stats / aciq.compare.

Usage (user run, needs root for real runs):

    sudo env ACIQ_VENV=/home/mekarz/aciq-venv \
        python tools/phase_matrix.py --scenario s2_wan_drop --seeds 0,1,2 \\
            --systems b0_fifo,aciq --drop 20 --drop-at 10 --duration None

    python tools/phase_matrix.py --dry-run --seeds 0,1 --systems b0_fifo,aciq

Design notes:

- pairing is BY SEED only; a run that failed or was skipped leaves its seed
  unpaired and the comparison says so explicitly rather than averaging.
- metrics come from the generators' own reports (workloads.json): for the
  call probe: loss_ratio, p95 latency, jitter; for bulk: sender_mbps as
  reported by the SENDER. Metric definitions live beside the summary so the
  report table can cite exactly what was tested.
- the tool never changes a metric's meaning: it reports what the run
  reported. A run with workloads.json missing its call entry contributes an
  UNPAIRED marker, not a silence.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time

from aciq.experiment import DryLauncher, ExperimentRunner
from aciq.harness import CapacityMode, Harness, SystemSpec

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "data" / "runs"
MATRIX_DIR = ROOT / "data" / "experiments"


SYSTEMS = {
    "b0_fifo": (SystemSpec.B0, CapacityMode.STATIC),
    "b1_cake95": (SystemSpec.B1, CapacityMode.STATIC),
    #: labelled UNREALISTIC UPPER BOUND: cake set to the post-drop capacity
    #: from t=0. Never comparable as a "what a user would have" number.
    "b1_cake_oracle": (SystemSpec.B1_ORACLE, CapacityMode.STATIC),
    "aciq": (SystemSpec.ACIQ, CapacityMode.ADAPTIVE),
}


def load_workload_metrics(run_dir: Path) -> dict[str, dict[str, float]]:
    """Per-workload metrics from the generator's self-report.

    Recorded per-seed per-metric: call.probe_p95_ms, call.probe_loss_pct,
    call.probe_jitter_ms, bulk.sender_mbps. These names are the metric
    definitions for every paired test in the phase 6 comparison.
    """
    wl = run_dir / "workloads.json"
    if not wl.exists():
        return {}
    data = json.loads(wl.read_text())
    out: dict[str, dict[str, float]] = {}
    call = data.get("call")
    if call:
        out["call"] = {
            "probe_p95_ms": float(call.get("p95") or 0.0),
            "probe_p99_ms": float(call.get("p99") or 0.0),
            # loss fraction -> percent: percentages in reports, not odds
            "probe_loss_pct": 100.0 * float(call.get("loss_ratio") or 0.0),
            "probe_jitter_ms": float(call.get("jitter_ms") or 0.0),
        }
    bulk = data.get("bulk")
    if bulk:
        out["bulk"] = {"sender_mbps": float(bulk.get("sender_mbps") or 0.0)}
    return out


def run_matrix(scenario: str, systems: list[str], seeds: list[int],
               out_dir: Path, link_mbps: float = 100.0,
               drop_mbps: float | None = None, drop_at_s: float | None = None,
               recover_at_s: float | None = None,
               dry_run: bool = False, enforce: bool = True,
               results_dir: Path | None = None,
               initial_link_mbps: float | None = None) -> list[dict]:
    """Run the matrix; return the runs' path stems for pairing."""
    results = []
    for seed in seeds:
        for name in systems:
            system, mode = SYSTEMS[name]
            if dry_run:
                from aciq.txn import FakeRunner
                runner = ExperimentRunner(
                    launcher=DryLauncher(),
                    harness=Harness(runner=FakeRunner(auto_readback=True), clock=time.monotonic),
                    real_time=False,
                    source=None, bridge_executor=None,
                    results_dir=results_dir or RUNS_DIR)
            else:
                runner = ExperimentRunner(
                    results_dir=results_dir or RUNS_DIR)
            res = runner.run(
                scenario, system, mode, seed=seed, link_mbps=link_mbps,
                drop_mbps=drop_mbps or link_mbps,
                drop_at_s=drop_at_s,
                recover_at_s=recover_at_s,
                initial_link_mbps=initial_link_mbps,
                enforce=enforce,
            )
            paths = runner.run_paths(scenario, system, mode, seed)
            stem = paths.root.name
            results.append({"seed": seed, "system": name,
                            "scenario": scenario, "mode": mode.value,
                            "path": stem,
                            "result": json.loads(res.to_json())})
            # a real run must never pass as paired if its artefacts are
            # missing: the broken marker is what the table reports, not a
            # silence.
            if not dry_run and not (RUNS_DIR / stem / "workloads.json").exists():
                results.append({"seed": seed, "system": name,
                                "broken": "workloads.json missing"})
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "matrix.json").write_text(json.dumps(results, indent=2))
    return results


def _pair_grouped(results: list[dict], baseline: str,
                  runs_dir: Path | None = None) -> list[dict]:
    """Group the matrix by scenario, pair each scenario independently.

    Comparisons across scenario boundaries would mix a 20→100 recovery edge
    with a 100→20 drop edge; the Wilcoxon pairing is per-edge only.
    """
    out: list[dict] = []
    scenarios = sorted({r.get("scenario", "?") for r in results})
    for sc in scenarios:
        rows_sc = [r for r in results if r.get("scenario", "?") == sc]
        for row in paired_table(rows_sc, baseline, runs_dir,
                                scenario_name=sc):
            row["scenario"] = sc
            out.append(row)
    return out


def paired_table(results: list[dict], baseline: str = "b0_fifo",
                 runs_dir: Path | None = None,
                 scenario_name: str | None = None) -> list[dict]:
    """Seed pairing + Wilcoxon per metric per workload.

    `results` is the matrix's own JSON; metric values are read back from the
    actual run artefacts on disk, so the table can never disagree with the
    run directory. Multiple scenarios in one matrix are grouped: every row
    carries its scenario, so a recovery-edge number can never be compared
    against a drop-edge table row.
    """
    if scenario_name is None and any("scenario" in r for r in results):
        return _pair_grouped(results, baseline, runs_dir)
    return _paired_one_scenario(results, baseline, runs_dir, scenario_name)


def _paired_one_scenario(results: list[dict], baseline: str,
                         runs_dir: Path | None = None,
                         scenario_name: str | None = None) -> list[dict]:
    out = []
    systems = sorted({r["system"] for r in results})
    if baseline not in systems:
        raise ValueError(f"baseline {baseline} not in matrix")
    seed_of_system: dict[str, dict[int, Path]] = {}
    for r in results:
        run_dir = (runs_dir or RUNS_DIR) / r["path"]
        if run_dir.exists():
            seed_of_system.setdefault(r["system"], {})[int(r["seed"])] = run_dir
    engine_names = [s for s in systems if s != baseline]
    for engine in engine_names:
        src = seed_of_system.get(baseline, {})
        als = seed_of_system.get(engine, {})
        if not src or not als:
            continue
        for workload in ("call", "bulk"):
            shared = sorted(set(src) & set(als))
            base_vals = [load_workload_metrics(src[s]) for s in shared]
            eng_vals = [load_workload_metrics(als[s]) for s in shared]
            metrics = sorted({m for d in base_vals + eng_vals
                              for m in d.get(workload, {})})
            for metric in metrics:
                pairs = [tuple(
                    (d.get(workload, {}).get(metric, None)
                     if d.get(workload, {}).get(metric, None) is not None
                     else None) for d in (db, de))
                    for db, de in zip(base_vals, eng_vals)]
                missing = [s for s, (a, b) in zip(shared, pairs)
                           if a is None or b is None]
                clean = [(a, b) for (a, b) in pairs
                         if a is not None and b is not None]
                row = {"engine": engine, "workload": workload,
                       "metric": metric, "pairs": len(clean),
                       "missing": missing}
                if scenario_name is not None:
                    row["scenario"] = scenario_name
                if clean:
                    try:
                        from aciq.compare import compare_runs
                        cmp_ = compare_runs(
                            [{"seed": s, metric: a}
                             for s, (a, _b) in zip(shared, clean)],
                            [{"seed": s, metric: b}
                             for s, (_a, b) in zip(shared, clean)],
                            metric)
                        row.update({
                            "baseline_median": cmp_.baseline_median,
                            "engine_median": cmp_.engine_median,
                            "median_delta": cmp_.median_delta,
                            "wilcoxon_p": cmp_.wilcoxon.p_two_sided,
                            "wilcoxon_n": cmp_.wilcoxon.n,
                            "dropped_zero_pairs":
                                cmp_.wilcoxon.dropped_zero_pairs,
                        })
                    except ValueError as e:
                        row.update({"error": str(e)})
                out.append(row)
    return out


def render_report(rows: list[dict]) -> str:
    """Markdown summary of the paired comparison. Only measured numbers from
    the rows; a row with missing pairs or an error prints the reason, never
    an average swept under the rug."""
    if not rows:
        return "# Phase 6 comparison\n\n(no paired rows; matrix incomplete)\n"
    lines = ["# Phase 6: baselines vs engine, paired by seed", ""]
    scen = None
    for r in sorted(rows, key=lambda r: (r.get("scenario", "?"), r["workload"], r["metric"])):
        if r.get("scenario") != scen:
            scen = r.get("scenario")
            lines += [f"## {scen}", "",
                      "| engine | workload | metric | pairs | base med | engine med | Δ | p (exact Wilcoxon) | notes |",
                      "|---|---|---|---|---|---|---|---|---|"]
        if r.get("error") or r["missing"]:
            lines.append(f"| {r['engine']} | {r['workload']} | {r['metric']} |"
                         f" {r['pairs']} | - | - | - | - |"
                         f" {'error: ' + r['error'] if r.get('error') else 'missing seeds ' + ','.join(map(str, r['missing']))} |")
            continue
        lines.append(
            f"| {r['engine']} | {r['workload']} | {r['metric']} | {r['pairs']} |"
            f" {r['baseline_median']} | {r['engine_median']} | {r['median_delta']:+.4g} |"
            f" {r['wilcoxon_p']:g} |"
            f" n={r['wilcoxon_n']}, dropped-zero-pairs={r['dropped_zero_pairs']} |")
    lines += ["", "Exact enumeration, no normal approximation; and a smaller"
              " `p` is reported as computed, not rounded to a symbol."]
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenarios", default="s2_wan_drop",
                    help="comma-separated scenario names, run in order")
    ap.add_argument("--systems", default="b0_fifo,aciq")
    ap.add_argument("--seeds", default="0,1,2,3,4,5,6,7,8,9")
    ap.add_argument("--link-mbps", type=float, default=100.0)
    ap.add_argument("--drop-mbps", type=float, default=None)
    ap.add_argument("--drop-at", type=float, default=None)
    ap.add_argument("--recover-at", type=float, default=None)
    ap.add_argument("--no-enforce", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out", default=str(MATRIX_DIR / "phase5"))
    ap.add_argument("--runs-dir", default=None,
                    help="override the runs artefact dir (smoke tests)")
    ap.add_argument("--baseline", default="b0_fifo")
    ap.add_argument("--compare-only", action="store_true",
                    help="pair from existing matrix.json, run nothing")
    a = ap.parse_args()

    out_dir = Path(a.out)
    seeds = [int(s) for s in a.seeds.split(",") if s.strip()]
    systems = a.systems.split(",")
    if a.compare_only:
        results = json.loads((out_dir / "matrix.json").read_text())
    else:
        results = []
        for sc in a.scenarios.split(","):
            sc = sc.strip()
            # s4_capacity_recovery needs the initial link for the estimator's
            # recovery target; other scenarios ignore it.
            results.extend(run_matrix(
                sc, systems, seeds, out_dir,
                link_mbps=a.link_mbps,
                drop_mbps=a.drop_mbps or a.link_mbps,
                drop_at_s=a.drop_at,
                recover_at_s=a.recover_at,
                initial_link_mbps=a.link_mbps if sc.startswith("s4") else None,
                dry_run=a.dry_run, enforce=not a.no_enforce,
                results_dir=Path(a.runs_dir) if a.runs_dir else None))
    table = paired_table(results, runs_dir=Path(a.runs_dir)
                         if a.runs_dir else None,
                         baseline=a.baseline)
    (out_dir / "comparison.json").write_text(json.dumps(table, indent=2))
    (out_dir / "comparison.md").write_text(render_report(table))
    print(json.dumps({
        "matrix_runs": len(results),
        "comparison_rows": len(table),
        "rows": table,
    }, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
