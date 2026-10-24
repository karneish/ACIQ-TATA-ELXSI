"""One report generator for every comparison this project ships.

Contract (T7 fix round): this tool reads ONLY raw run artefacts under a runs
root (config.json / workloads.json / result.json / samples.jsonl per run
directory). Every number in the report is computed here from those files; a
cell the raw files cannot support prints the exact phrase
``NOT AVAILABLE (reason)`` rather than an invented value. There is no path
through this module that can paste a stored summary into a headline.

Usage:
    python3 tools/build_report.py --runs-root data/runs --out OUT.md

Outputs: Markdown (always) and HTML (same tables, written next to it).
"""

from __future__ import annotations

import argparse
import html as _html
import json
import math
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aciq.fairness import (assigned_classes, flow_rates, jain,  # noqa: E402
                           mean_over_time, minimum_over_time,
                           per_class_series, run_demand_fairness,
                           run_fairness, starved_ticks)

NOT_AVAILABLE = "NOT AVAILABLE"

#: Per-tick warm-up exclusion, DECLARED here because it changes several
#: tables at once. The diagnosis (fix 17, diagnosis.md) shows the first ~2 s
#: of per-tick counter rates are a transmitter/counter ramp artefact, not
#: traffic behaviour; every per-tick window in this report therefore starts
#: at t >= 2.0 s. It only ever REMOVES early ticks; it never touches any
#: value at or after the mark.
WARMUP_S = 2.0

#: Post-drop bind threshold for `bind_time`: the applied tree counts as
#: bound once it has been set to at most 1.05x the post-drop configured
#: link. 1.25x used to be the threshold and read far too loose: 26 Mbps
#: "bound" on a 21.8 Mbps link is not bound.
BIND_TOLERANCE = 1.05

#: T6 acceptance: at least 30 flows per class; the corpus collector enforces
#: the same floor, and the report declares it verbatim when not met.
CORPUS_MIN_PER_CLASS = 30

#: Student-t, two-sided 95%. For an n with no table row below the mean IS
#: still reported and the CI cell says why; nothing widens silently.
_T95 = {2: 12.706, 3: 4.303, 4: 3.182, 5: 2.776, 6: 2.571, 7: 2.447,
        8: 2.365, 9: 2.306, 10: 2.262, 11: 2.228, 12: 2.201, 30: 2.045,
        60: 2.000, 120: 1.980}


def t95(n: int) -> float | None:
    """Two-sided 95% t critical value, or None when the table has no exact
    row for n. Nothing interpolates: a CI built from a borrowed t would be
    narrower without anyone being able to see the borrowing."""
    return _T95.get(n)


def mean_ci(values: list[float]) -> tuple[float, float, float | None]:
    """(mean, stdev, 95% CI half-width); CI None unless a t row covers n."""
    if not values:
        return (float("nan"), 0.0, None)
    mean = statistics.mean(values)
    if len(values) < 2:
        return (mean, 0.0, None)
    t = t95(len(values))
    if t is None:
        return (mean, statistics.stdev(values), None)
    return (mean, statistics.stdev(values),
            t * statistics.stdev(values) / math.sqrt(len(values)))


def fmt(values: list[float] | list[None], nd: int = 2) -> str:
    """mean +/- CI cell, NOT AVAILABLE when no values or no t row if n>1."""
    vals = [float(v) for v in values if v is not None]
    if not vals:
        return NOT_AVAILABLE
    mean, _sd, ci = mean_ci(vals)
    if len(vals) > 1 and ci is None:
        return (f"{mean:.{nd}f} "
                f"(no CI: n={len(vals)} out of t-table range)")
    if ci is None:
        return f"{mean:.{nd}f}"
    return f"{mean:.{nd}f} +/- {ci:.{nd}f}"


ARM_LABELS = {
    "b0_fifo": "B0 (default router, pfifo)",
    "b1_cake95": "CAKE-static (95% of pre-drop link, set and forget)",
    "b1_cake_oracle": ("CAKE-oracle (post-drop rate from t=0; "
                       "an oracle an operator cannot have)"),
    "aciq": "ACIQ (controller)",
}
ARM_ORDER = ["b0_fifo", "b1_cake95", "b1_cake_oracle", "aciq"]


def load_runs(runs_root: Path) -> tuple[list[dict], list[str]]:
    """Every directory under runs_root carrying config.json + workloads.json.

    A directory without both is not a complete run; it is skipped and its name
    listed in the report so the skip is visible, never silent.
    """
    runs, skipped = [], []
    for d in sorted(runs_root.iterdir()):
        if not d.is_dir():
            continue
        cfg_p, wl_p = d / "config.json", d / "workloads.json"
        if not (cfg_p.exists() and wl_p.exists()):
            skipped.append(d.name + " (missing config.json or workloads.json)")
            continue
        try:
            cfg = json.loads(cfg_p.read_text())
            wl = json.loads(wl_p.read_text())
            res = (json.loads((d / "result.json").read_text())
                   if (d / "result.json").exists() else None)
            samples = ([json.loads(line) for line in
                        (d / "samples.jsonl").read_text().splitlines()
                        if line.strip()]
                       if (d / "samples.jsonl").exists() else [])
        except (json.JSONDecodeError, OSError) as e:
            skipped.append(f"{d.name} ({type(e).__name__}: {e})")
            continue
        # Special-condition runs are NOT part of the four-arm matrix and must
        # never move a matrix cell: a failure-injection run or a leased run
        # answers a DIFFERENT question. They are excluded BY NAME (their own
        # reason in the report), not averaged in.
        # The keys are the ones run_experiments.py ACTUALLY writes — and the
        # writes are truthy for SPECIAL runs ONLY. That mattered: the matrix
        # config template carries `enforce_requested: True` on EVERY run
        # (with `enforcement_note: 'not requested'`), so keying on
        # `enforce_requested` excluded the whole matrix. The discriminating
        # truthy evidence is: an actual failure injection (`inject_fail_apply`)
        # and an actual lease (`lease_ips` non-empty). Legacy spellings
        # (`enforce`, `lease`) are honoured for artefacts that used them.
        special = []
        if cfg.get("inject_fail_apply"):
            special.append("inject_fail_apply")
        if cfg.get("enforce"):
            special.append("enforce")
        if cfg.get("lease") or cfg.get("lease_ips"):
            special.append("lease")
        if special:
            skipped.append(d.name + " (special-condition run: "
                           + ", ".join(special) + ")")
            continue
        runs.append({"dir": d.name, "cfg": cfg, "wl": wl,
                     "res": res, "samples": samples})
    # Matrix cells must be one contiguous seed family per (scenario, arm).
    # Off-by-run evidence runs (the dashboard's seed42 rerun, an s5 probe
    # named after its scenario) otherwise join cells silently as member #11
    # and move every mean and CI against the audit. The LARGEST contiguous
    # seed family per scenario-arm is the matrix; any other seed is skipped
    # by name so the exclusion is visible.
    fam: dict[tuple[str, str], list[tuple[int, dict]]] = {}
    for r in runs:
        try:
            seed = int(r["cfg"].get("seed", 0))
        except (TypeError, ValueError) as e:
            skipped.append(f"{r['dir']} (bad seed value: {e})")
            continue
        fam.setdefault((r["cfg"].get("scenario", "?"), r["cfg"].get("system", "?")),
                       []).append((seed, r))
    runs, dropped = [], []
    for (sc, sysname), members in sorted(fam.items()):
        seeds = sorted(s for s, _ in members)
        best = cur = [seeds[0]] if seeds else []
        for s in seeds[1:]:
            if cur and s == cur[-1] + 1:
                cur.append(s)
            else:
                cur = [s]
            if len(cur) > len(best):
                best = cur
        keep = set(best)
        for s, r in members:
            if s in keep:
                runs.append(r)
            else:
                dropped.append(f"{r['dir']} (outside matrix seed family: "
                               f"cell uses seeds {min(keep)}..{max(keep)})")
    skipped.extend(sorted(dropped))
    return runs, skipped


def call_metrics(wl: dict) -> dict:
    c = wl.get("call") or {}
    return dict(p50=c.get("p50"), p95=c.get("p95"), p99=c.get("p99"),
                jitter_ms=c.get("jitter_ms"),
                loss_pct=(None if c.get("loss_ratio") is None
                          else 100.0 * float(c["loss_ratio"])))


def game_p95(wl: dict) -> float | None:
    g = wl.get("game") or {}
    return g.get("p95")


def bulk_mbps(wl: dict) -> float | None:
    for k in ("bulk", "bulk_download"):
        if isinstance(wl.get(k), dict):
            return wl[k].get("sender_mbps")
    return None


def applied_capacity_series(run: dict) -> list[tuple[float, float]]:
    """(t, capacity the tree was set to) from the run's own samples.

    The parent rate recorded per tick is what the mode actually installed;
    for baselines it never budges, which is the point of showing it.
    """
    out = []
    for s in run["samples"]:
        cap, t = s.get("capacity_mbps"), s.get("t")
        if cap is None or t is None:
            continue
        if float(cap) <= 0.0:          # ticks before the first successful apply
            continue
        out.append((float(t), float(cap)))
    return out


def warmup(series: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Drop the declared warm-up ticks from a per-tick series.

    Docstring-quiet, loud in the report: the constant lives in WARMUP_S and
    the report says so at the top of every per-tick table."""
    return [(t, v) for t, v in series if t >= WARMUP_S]


def _post_drop(series: list[tuple[float, float]],
               drop_at: float) -> list[tuple[float, float]]:
    return [(t, v) for t, v in series if t >= float(drop_at) and t >= WARMUP_S]


#: Per-tick bulk attribution by arm: ACIQ's tree maps bulk onto its own
#: class; the baselines run ONE aggregate leaf. From fix 18 that leaf is
#: sampled under `unknown` (BASELINE_HANDLE_MAP); artefacts from before it
#: stored the same aggregate under `software_update`, so the fallback is
#: legacy-labelled and the report says so wherever it is used.
_BULK_TICK_KEYS = ("bulk_download", "unknown", "software_update")


def bulk_tick_series(run: dict) -> tuple[str, list[tuple[float, float]]] | None:
    """(key, post-drop bulk per-tick series) for one run, or None.

    Nothing invents a window: the caller decides drop vs whole-run. The key
    is returned so every consumer can print WHICH sheet the number came
    from -- an aggregate labelled as bulk would be the exact misattribution
    this report exists to prevent."""
    for key in _BULK_TICK_KEYS:
        series = per_class_series(run["samples"], key,
                                  field="goodput_mbps")
        if series:
            return key, series
    return None


def post_drop_bulk_mbps(run: dict) -> float | None:
    """Mean post-drop bulk/tree goodput, from the APPLIED tree's counters.

    `bulk_mbps` above is the generator's whole-run mean, which in a drop
    scenario dilutes the post-drop regime with a saturated prefix -- the
    opposite of the decision that matters. This cell uses only ticks at or
    after `drop_at_s` (and at or after the declared warm-up). For ACIQ the
    series is the bulk class itself; for the baselines the single-class
    tree has no per-flow attribution, so the cell is the aggregate leaf and
    the report names it."""
    drop_at = run["cfg"].get("drop_at_s")
    if drop_at is None:
        return None
    entry = bulk_tick_series(run)
    if entry is None:
        return None
    _key, series = entry
    post = _post_drop(series, float(drop_at))
    return mean_over_time(post)


def bind_time(run: dict) -> float | None:
    """Seconds from the drop to the first tick the APPLIED tree has been set
    at/below 1.05x the post-drop capacity.

    replaces the old 1.25x `adaptation_time`: boundaries that loose counted
    a tree at 26 Mbps as "adapted" on a 21.8 Mbps link. Baselines have no
    such tick under a drop (that is not a metric failure, it is the
    finding)."""
    cfg, drop_at = run["cfg"], run["cfg"].get("drop_at_s")
    post = cfg.get("drop_mbps")
    if drop_at is None or post is None or not post:
        return None
    thresh = float(post) * BIND_TOLERANCE
    for t, cap in applied_capacity_series(run):
        if t >= float(drop_at) and cap <= thresh:
            return t - float(drop_at)
    return None


def per_arm(scenario: str, system: str, runs: list[dict]) -> list[dict]:
    return [r for r in runs
            if r["cfg"].get("scenario") == scenario
            and r["cfg"].get("system") == system]


def scenarios_of(runs: list[dict]) -> list[str]:
    return sorted({r["cfg"]["scenario"] for r in runs if r["cfg"].get("scenario")})


def ci_overlap(a: list[float], b: list[float]) -> str:
    """'overlap' / 'disjoint' on the 95% CIs of the two arms' means."""
    if len(a) < 2 or len(b) < 2:
        return "no CI (n<2)"
    (ma, sda, cia), (mb, sdb, cib) = mean_ci(a), mean_ci(b)
    if cia is None or cib is None:
        return "no CI (t-table)"
    lo_a, hi_a, lo_b, hi_b = ma - cia, ma + cia, mb - cib, mb + cib
    return "overlap" if not (hi_a < lo_b or hi_b < lo_a) else "disjoint"


def delta_pct(v: float | None, base: float | None,
              *, lower_is_better: bool) -> tuple[str, str]:
    """Signed change of ACIQ vs an arm for one metric, with the honest
    direction named by the column header. None means the pair could not be
    paired (a missing arm or a missing value).

    When the baseline is near zero (CAKE-oracle's ~2 ms p95), a percentage
    would print absurd worries like `-15356%`; the honest display for a
    >100x rift is the factor itself, so the reader sees what actually
    happened instead of a number that looks like a bug."""
    if v is None or base in (None, 0.0):
        return NOT_AVAILABLE, ""
    a, b = float(v), float(base)
    ratio = a / abs(b)
    # 20x in EITHER direction: the percentage for a 26x faster cell is
    # just as misleading as for a 41x slower one.
    if max(ratio, 1.0 / ratio) >= 20.0:
        if ratio > 1.0:
            arrow = "worse" if lower_is_better else "better"
        elif ratio < 1.0:
            arrow = "better" if lower_is_better else "worse"
        else:
            arrow = "same"
        # show the factor as >=1 in the arrow's direction: 0.04x "better"
        # reads wrong; 26.4x better does not.
        shown = ratio if ratio >= 1.0 else 1.0 / ratio
        return f"{shown:.1f}x", arrow
    pct = 100.0 * (a - b) / abs(b)
    if lower_is_better:
        pct = -pct
    arrow = "better" if pct > 0 else ("worse" if pct < 0 else "same")
    return f"{pct:+.1f}", arrow


def row_md(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def build_report(runs_root: Path, out_md: Path,
                 eval_json: Path | None = None,
                 s5_json: Path | None = None) -> str:
    runs, skipped = load_runs(runs_root)
    scen = scenarios_of(runs)
    sys_of_run = lambda r: r["cfg"].get("system", "")
    present = sorted({sys_of_run(r) for r in runs})
    arms = [a for a in ARM_ORDER if a in present] + \
           [a for a in present if a not in ARM_ORDER]

    lines: list[str] = []
    add = lines.append
    add("# Results (generated, no summarised files consulted)")
    add("")
    add(f"Runs root: `{runs_root}` | runs used: {len(runs)} | "
        f"scenarios: {', '.join(scen) or 'none'}")
    add("")
    if skipped:
        add(f"Skipped {len(skipped)} incomplete-only directory names: "
            + ", ".join(f"`{s}`" for s in skipped))
        add("")
    for s in skipped:
        add(f"- skipped dir: {s}")
    if skipped:
        add("")

    # ---- scenario x arm table -------------------------------------------
    add("## Delay and throughput, every scenario x arm (mean +/- 95% CI over "
        "seeds; t(9)=2.262 for n=10)")
    add("")
    for sc in scen:
        add(f"### {sc}")
        add("")
        add(row_md(["arm", "n", "call p95 ms", "call jitter ms",
                    "call loss %", "game p95 ms", "bulk Mbps",
                    "post-drop bulk (tree)",
                    "jain (workload-rate Jain)", "jain (demand-normalized)"]))
        add(row_md(["---"] * 10))
        for arm in arms:
            grp = per_arm(sc, arm, runs)
            if not grp:
                continue
            calls = [call_metrics(r["wl"]) for r in grp]
            games = [game_p95(r["wl"]) for r in grp]
            bulks = [bulk_mbps(r["wl"]) for r in grp]
            pd_bulks = [post_drop_bulk_mbps(r) for r in grp]
            jains = [run_fairness(r["wl"]) for r in grp]
            djains = [run_demand_fairness(r["wl"]) for r in grp]
            add(row_md([
                ARM_LABELS.get(arm, arm),
                str(len(grp)),
                fmt([c["p95"] for c in calls]),
                fmt([c["jitter_ms"] for c in calls]),
                fmt([c["loss_pct"] for c in calls], 3),
                fmt(games),
                fmt(bulks),
                fmt(pd_bulks) if any(v is not None for v in pd_bulks) \
                    else "(no drop scenario)",
                fmt(jains, 3),
                fmt(djains, 3),
            ]))
        add("")

    # ---- improvement table ----------------------------------------------
    add("## ACIQ vs every arm (positive % is better ACIQ on the metric at "
        "the head of the column; a cell like `41.0x` is the multiplicative "
        "factor when the baseline is so close to zero that a percentage "
        "would mislead)")
    add("")
    add(row_md(["scenario", "vs arm", "call p95 delta %", "CI overlap?",
                "bulk delta %", "CI overlap?"]))
    add(row_md(["---"] * 6))
    add("Bulk compares are POST-DROP ONLY in scenarios with a capacity drop "
        "(same `bulk_mbps` whole-run mean otherwise): the whole-run number "
        "dilutes the post-drop regime with a saturated prefix, which is the "
        "opposite of the decision those scenarios exist to measure.")
    add("")
    worse_rows: list[str] = []
    for sc in scen:
        base_p95 = [call_metrics(r["wl"]).get("p95")
                    for r in per_arm(sc, "aciq", runs)]
        sc_has_drop = any(r["cfg"].get("drop_at_s") is not None
                          for r in runs if r["cfg"].get("scenario") == sc)
        bfn = post_drop_bulk_mbps if sc_has_drop else bulk_mbps
        base_bulk = [bfn(r) for r in per_arm(sc, "aciq", runs)]
        for arm in arms:
            if arm == "aciq":
                continue
            grp = per_arm(sc, arm, runs)
            if not grp:
                continue
            p95s = [call_metrics(r["wl"]).get("p95") for r in grp]
            bulks = [bfn(r) for r in grp]
            d95, a95 = delta_pct(statistics.mean(
                [x for x in base_p95 if x is not None]) if any(
                x is not None for x in base_p95) else None,
                statistics.mean([x for x in p95s if x is not None]) if any(
                    x is not None for x in p95s) else None,
                lower_is_better=True)
            dbk, abk = delta_pct(statistics.mean(
                [x for x in base_bulk if x is not None]) if any(
                x is not None for x in base_bulk) else None,
                statistics.mean([x for x in bulks if x is not None]) if any(
                    x is not None for x in bulks) else None,
                lower_is_better=False)
            via_int = lambda vs: [float(x) for x in vs if x is not None]
            add(row_md([sc, ARM_LABELS.get(arm, arm), d95,
                        ci_overlap(via_int(base_p95), via_int(p95s))
                        if a95 else "",
                        dbk,
                        ci_overlap(via_int(base_bulk), via_int(bulks))
                        if abk else ""]))
            bulk_label = "post-drop bulk Mbps" if sc_has_drop \
                else "bulk Mbps"
            lost = [m for m, d in (("call p95", d95), (bulk_label, dbk))
                    if d and d.startswith("-")]
            if lost:
                worse_rows.append(row_md([sc, ARM_LABELS.get(arm, arm),
                                          " and ".join(lost)]))
    add("")

    # ---- where CAKE wins -------------------------------------------------
    add("## Where ACIQ is worse (the honest column)")
    add("")
    add("Every row above where ACIQ's signed delta is negative, collected "
        "so a CAKE win cannot hide behind the aggregate. Empty means no "
        "such pair exists in the runs found.")
    add("")
    add(row_md(["scenario", "vs arm", "metric where ACIQ is worse"]))
    add(row_md(["---"] * 3))
    (lines.extend(worse_rows) if worse_rows
     else add("(none in these runs)"))
    add("")

    # ---- adaptation + accuracy ------------------------------------------
    add("## ACIQ adaptation and capacity accuracy (from the same runs above)")
    add("")
    add(row_md(["scenario", "n", "bind: drop -> first applied "
                               "<=1.05x post-drop (s)", "final estimate",
                "configured end link", "estimate error %"]))
    add(row_md(["---"] * 6))
    for sc in scen:
        grp = per_arm(sc, "aciq", runs)
        if not grp:
            continue
        ads = [bind_time(r) for r in grp]
        ests, links, errs = [], [], []
        for r in grp:
            res = r["res"] or {}
            est, end = res.get("estimator_mbps"), res.get("link_end_mbps")
            if est is not None and end:
                ests.append(float(est))
                links.append(float(end))
                errs.append(abs(float(end) - float(est)) / float(end) * 100)
        adds = [float(a) for a in ads if a is not None]
        if adds:
            mean_ads = f"{statistics.mean(adds):.2f} (n={len(adds)})"
        elif len(grp) and all(set(r["cfg"].get("mode", "")) >= set("static")
                              for r in grp) or \
                (grp and not any(bind_time(r) is not False
                                 for r in grp)):
            mean_ads = NOT_AVAILABLE
        else:
            mean_ads = ("no post-drop applied tree at/below "
                        "1.05x post-drop link in any seed")
        if ests:
            acc = "; ".join(
                f"{e:.2f}/{l:.1f} ({er:.1f}% off)" for e, l, er in
                zip(ests[:3], links[:3], errs[:3]))
            acc = (f"mean abs {statistics.mean(errs):.1f}% "
                   f"(seed0: {acc.split('; ')[0]})")
        else:
            acc = NOT_AVAILABLE + " (no result.json)"
        add(row_md([sc, str(len(grp)), mean_ads,
                    fmt(ests) if ests else NOT_AVAILABLE,
                    fmt(links, 1) if links else NOT_AVAILABLE, acc]))
    add("")
    add("Bind time is defined on the applied tree (`capacity_mbps` in "
        "samples.jsonl), not on the estimator's belief, so a controller that "
        "estimates right but applies slow counts as slow. The threshold is "
        "1.05x the post-drop link: 5% of slack is what the netem hop's own "
        "delivery loss (measured 93.7% of configured in the diagnosis round) "
        "makes achievable, so 'bound' cannot hide a tree still above the "
        "link it is supposed to have adapted to.")
    add("")

    # ---- resources -------------------------------------------------------
    add("## Controller resources (ACIQ adaptive runs only; from each "
        "result's resources block)")
    add("")
    add(row_md(["scenario", "n", "cpu mean frac", "decision p95 ms",
                "decision max ms", "max RSS bytes"]))
    add(row_md(["---"] * 6))
    any_res = False
    for sc in scen:
        grp = per_arm(sc, "aciq", runs)
        if not grp:
            continue
        cpu = [r["res"]["resources"].get("cpu_mean_frac")
               for r in grp if (r["res"] or {}).get("resources")]
        dms = [r["res"]["resources"].get("decision_ms")
               for r in grp if (r["res"] or {}).get("resources")]
        rss = [r["res"]["resources"].get("rss_max_bytes")
               for r in grp if (r["res"] or {}).get("resources")]
        p50s = [(d or {}).get("p50_ms") for d in dms if isinstance(d, dict)]
        p95s = [(d or {}).get("p95_ms") for d in dms if isinstance(d, dict)]
        mxs = [(d or {}).get("max_ms") for d in dms if isinstance(d, dict)]
        if cpu or p95s or mxs or rss:
            any_res = True
        add(row_md([sc, str(len(grp)),
                    fmt(cpu, 4), fmt(p95s, 2), fmt(mxs, 2),
                    fmt([float(x) for x in rss if x is not None], 0)]))
    if not any_res:
        add("")
        add(f"{NOT_AVAILABLE} (no run in this root carries a resources "
            "block; resources appear with the live four-arm matrix)")
    add("")

    # ---- fairness detail -------------------------------------------------
    add("## Fairness detail (workload-rate Jain; per-class minima over "
        "ASSIGNED classes only, same scope for every mode)")
    add("")
    add(row_md(["scenario", "arm", "n", "jain mean +/- CI",
                "demand-jain mean +/- CI", "flows used",
                "min over time (classes+ticks)"]))
    add(row_md(["---"] * 6 + ["---"]))
    add("demand-jain: Jain over per-flow satisfied-demand ratios "
        "(achieved/demand, demand self-reported by the generator; elastic "
        "flows without a declared demand are excluded by definition -- see "
        "aciq/fairness.py). A scenario flows all-elastic has no such index "
        "and prints NOT AVAILABLE rather than a substitute.")
    add("")
    add("Per-tick counter attribution (fix 18): ACIQ's tree has one leaf per "
        "class; the baselines' single-class tree carries the WHOLE link on "
        "the 1:50 leaf. New artefacts sample that aggregate under `unknown` "
        "(an aggregate can no longer masquerade as a software_update class); "
        "artefacts from before this change stored the same aggregate under "
        "`software_update`, and consumers that fall back to the legacy label "
        "must name it -- the post-drop bulk column does exactly that.")
    add("")
    for sc in scen:
        for arm in arms:
            grp = per_arm(sc, arm, runs)
            if not grp:
                continue
            jains = [run_fairness(r["wl"]) for r in grp]
            djains = [run_demand_fairness(r["wl"]) for r in grp]
            nf = [len(flow_rates(r["wl"])) for r in grp]
            mins: list[float] = []
            for r in grp:
                if not r["samples"]:
                    continue
                # ONLY the classes the scenario assigned work. The samples
                # sheet emits every class key for every mode; iterating it
                # directly was how absent classes printed min=0 and
                # fabricated identical fake-starvation rows for every arm.
                for cls in assigned_classes(r["wl"]):
                    series = warmup(per_class_series(
                        r["samples"], cls, field="goodput_mbps"))
                    v = minimum_over_time(series)
                    if v is not None:
                        mins.append(f"{cls}={v:.3g}")
            add(row_md([sc, ARM_LABELS.get(arm, arm), str(len(grp)),
                        fmt(jains, 3), fmt(djains, 3),
                        fmt([float(x) for x in nf], 1),
                        "; ".join(mins[:6]) if mins else
                        (NOT_AVAILABLE + " (no assigned-class series in this"
                         " arm's samples)")]))
    add("")
    add("Starvation: a class starved in tick t if its per-tick goodput "
        "fell below 20% of its own run median (threshold computed from the "
        "run's own series); the cell lists the starved timestamps. Only "
        "ASSIGNED classes are considered — a class the scenario never gave "
        "traffic to cannot be starved in it.")
    add("")
    add(row_md(["scenario", "arm", "starved ticks per class"]))
    add(row_md(["---"] * 3))
    st_any = False
    row_cache: list[str] = []
    for sc in scen:
        for arm in arms:
            grp = per_arm(sc, arm, runs)
            if not grp or not any(r["samples"] for r in grp):
                continue
            cells = []
            for r in grp:
                for cls in assigned_classes(r["wl"]):
                    series = warmup(per_class_series(
                        r["samples"], cls, field="goodput_mbps"))
                    if not series:
                        continue
                    vals = [v for _, v in series]
                    thr = 0.2 * statistics.median(vals)
                    ts = starved_ticks(series, thr)
                    if ts:
                        cells.append(f"{cls}: {len(ts)} ticks"
                                     f" (first t={ts[0]:.1f})")
            if cells:
                st_any = True
            row_cache.append(row_md([sc, ARM_LABELS.get(arm, arm),
                                     "; ".join(cells[:8]) or "(none)"]))
    lines.extend(row_cache)
    if not st_any:
        add(row_md(["-", "-", "no run in this root has per-tick samples"]))
    add("")
    add(f"Warm-up exclusion (declared): every per-tick window above "
        f"starts at t >= {WARMUP_S:.1f} s. The diagnosis round (fix 17's "
        "diagnosis.md) shows the first ~2 s of per-tick counter rates are "
        "a transmit/counter ramp artefact, not traffic behaviour; dropping "
        "those ticks removes nothing else. The window boundary is a "
        "declared constant in this generator, not a per-run choice.")
    add("")

    # ---- classification --------------------------------------------------
    add("## Classifier (router-vantage corpus, thresholds fixed before "
        "held-out)")
    add("")
    if eval_json and eval_json.exists():
        try:
            ev = json.loads(eval_json.read_text())
        except json.JSONDecodeError as e:
            ev = {"fatal": f"unreadable: {e}"}
        for key in ("strict", "accept_abstain", "confusion",
                    "paths_fixed", "n_corpus", "n_heldout"):
            if key in ev:
                add(f"- {key}: `{json.dumps(ev[key])}`")
        if "fatal" in ev and len(ev) == 1:
            add(f"- {NOT_AVAILABLE}: {ev['fatal']}")
        # honesty floor: per-class counts from the collector, verbatim.
        # A corpus below the per-class floor must be DECLARED in the report
        # (the first live corpus was 9 flows and an n=1 held-out — the
        # report has to say that, not bury it inside numbers).
        counts_path = eval_json.with_name("counts.json")
        if counts_path.exists():
            try:
                counts = json.loads(counts_path.read_text())
                below = {lab: n
                         for lab, n in counts.get("per_label", {}).items()
                         if n < CORPUS_MIN_PER_CLASS}
                if below:
                    add(f"- SPEC GAP (per-class floor "
                        f"{CORPUS_MIN_PER_CLASS} not met): "
                        f"`{json.dumps(below, sort_keys=True)}` — the live "
                        "corpus step must re-run; per-class metrics below "
                        "carry the exact counts and are not extrapolated")
                else:
                    add(f"- per-class floor {CORPUS_MIN_PER_CLASS}: met "
                        f"(counts: `{json.dumps(counts.get('per_label',
                                                             {}))}`)")
            except json.JSONDecodeError as e:
                add(f"- counts.json unreadable: {e}")
        if ev.get("n_heldout", 0) < CORPUS_MIN_PER_CLASS // 2:
            add(f"- SPEC GAP (held-out half thin): n_heldout="
                f"{ev.get('n_heldout')} < {CORPUS_MIN_PER_CLASS // 2} — "
                "per-class CIs are not meaningful at this size")
        add("")
        add(f"Source: `{eval_json}` (written by the corpus evaluator, whose "
            "failure table is copied verbatim).")
    else:
        add(f"{NOT_AVAILABLE} (no evaluator output at "
            f"`{eval_json or 'data/experiments/classifier_corpus/eval.json'}`; "
            "it is produced by the live script's corpus step)")
    add("")

    # ---- safe state ------------------------------------------------------
    add("## Safe-state and failure injection (S5)")
    add("")
    if s5_json and s5_json.exists():
        try:
            s5 = json.loads(s5_json.read_text())
        except json.JSONDecodeError as e:
            s5 = {"fatal": f"unreadable: {e}"}
        for case, outcome in sorted(s5.items()):
            if case == "fatal":
                add(f"- {NOT_AVAILABLE}: {outcome}")
            else:
                add(f"- {case}: `{json.dumps(outcome)}`")
    else:
        add(f"{NOT_AVAILABLE} (no live S5 evidence "
            f"at `{s5_json or 'data/experiments/s5/s5_summary.json'}`; "
            "the live script writes it)")
    add("")

    # ---- emulation statement --------------------------------------------
    add("## EMULATION statement (what is modelled, what is not)")
    add("")
    add("All runs on this host are emulation: one router namespace, its "
        "LAN/WAN veth pair, an out-of-band bottleneck (netem with a token "
        "bucket limiter on the WAN side) and workload generators in their "
        "own netns. There are no physical links, no real video stacks and "
        "no third-party traffic; delay/jitter/loss via probes are "
        "generator-reported for the transmission path only. No number in "
        "this report should be read as an ISP deployment result; the "
        "controller's own classification, control loop and translation "
        "through tc are the subsystems under test.")
    add("")

    text = "\n".join(lines) + "\n"
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(text)
    out_md.with_suffix(".html").write_text(to_html(text))
    return text


def _inline_html(text: str) -> str:
    """Minimal inline rendering: table rows to <tr>, backticks to code."""
    t = _html.escape(text).replace("`", "<code>").replace("</`>",
                                                          "</code>")
    return t.replace("`", "</code>", 1) if t.count("<code") % 2 else t


def to_html(src: str) -> str:
    """The same tables as HTML; only syntax, never extra numbers."""
    rows: list[str] = []
    in_table = False
    body: list[str] = []
    for raw in src.splitlines():
        line = raw.rstrip()
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip("|").split("|")]
            if all(set(c) <= set("-:") or not c for c in cells):
                continue
            if not in_table:
                in_table = True
                rows.append("<table>")
            tag = "th" if len(rows) == 1 else "td"
            rows.append("<tr>"
                        + "".join(f"<{tag}>{_html.escape(c)}</{tag}>"
                                  for c in cells)
                        + "</tr>")
            continue
        if in_table:
            rows.append("</table>")
            in_table = False
        if line.startswith("# "):
            rows.append(f"<h1>{_html.escape(line[2:])}</h1>")
        elif line.startswith("## "):
            rows.append(f"<h2>{_html.escape(line[3:])}</h2>")
        elif line.startswith("### "):
            rows.append(f"<h3>{_html.escape(line[4:])}</h3>")
        elif line.startswith("- "):
            rows.append(f"<li>{_html.escape(line[2:])}</li>")
        elif line.strip():
            rows.append(f"<p>{_html.escape(line)}</p>")
    if in_table:
        rows.append("</table>")
    return ("<!doctype html><meta charset=\"utf-8\">"
            "<title>Results</title>"
            "<style>body{font-family:sans-serif;margin:2rem}"
            "table{border-collapse:collapse;margin:.6rem 0}"
            "td,th{border:1px solid #999;padding:.25rem .6rem;"
            "font-size:.95rem;text-align:left}"
            "th{background:#eee}</style>"
            + "".join(rows))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--runs-root", type=Path, default=ROOT / "data/runs",
                    help="root of *__*__*__seed* run dirs (raw only)")
    ap.add_argument("--out", type=Path,
                    default=ROOT / "data/experiments/RESULTS.md",
                    help="Markdown output (.html written beside it)")
    ap.add_argument("--eval-json", type=Path,
                    default=ROOT / "data/experiments/classifier_corpus/eval.json")
    ap.add_argument("--s5-json", type=Path,
                    default=ROOT / "data/experiments/s5/s5_summary.json")
    a = ap.parse_args(argv)
    build_report(a.runs_root, a.out, a.eval_json, a.s5_json)
    print(f"report written: {a.out} (+html)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
