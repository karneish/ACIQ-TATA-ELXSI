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

from aciq.experiment import git_commit_hash  # noqa: E402
from aciq.fairness import (class_of_label, flow_rates,  # noqa: E402
                           label_carrying, mean_over_time,
                           minimum_over_time, run_demand_fairness, run_fairness, starved_ticks)

NOT_AVAILABLE = "NOT AVAILABLE"

#: Per-tick warm-up exclusion, DECLARED here because it changes several
#: tables at once. The diagnosis (fix 17, diagnosis.md) shows the first ~2 s
#: of per-tick counter rates are a transmitter/counter ramp artefact, not
#: traffic behaviour; every per-tick window in this report therefore starts
#: at t >= 2.0 s. It only ever REMOVES early ticks; it never touches any
#: value at or after the mark.
WARMUP_S = 2.0
#: A per-tick rate computed over dt beyond this is a mean over a genuine
#: poll/reset gap, not a rate; at ~1 s ticks nothing legitimate lives past
#: 3 s. Declared constant, never tuned.
TICK_GAP_MAX_S = 3.0

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
    "b1_cake_oracle": ("CAKE-decl-final (0.95x the protocol's declared FINAL "
                       "rate, from t=0; NOT an oracle for the pre-change "
                       "plateau or for a climbing controller)"),
    "b1_cake_cons": ("CAKE-conservative (0.50x pre-change link, static; the "
                     "declared undershoot probe arm - round-3 params)"),
    "b1_cake_auto": ("CAKE-adaptive (same estimator/governor chain, "
                     "single-class CAKE rebuild per decision; queue "
                     "discipline is the only difference)"),
    "aciq": "ACIQ (controller)",
}
ARM_ORDER = ["b0_fifo", "b1_cake95", "b1_cake_oracle", "b1_cake_cons",
             "b1_cake_auto", "aciq"]


def _parse_ranges(spec: str) -> list[tuple[int, int]]:
    """'0-9,42-51' -> [(0, 9), (42, 51)]"""
    out: list[tuple[int, int]] = []
    for part in spec.split(","):
        part = part.strip()
        if "-" in part:
            lo, hi = part.split("-", 1)
            out.append((int(lo), int(hi)))
        elif part:
            v = int(part)
            out.append((v, v))
    return out


#: Default tracked families, unchanged from the pre-parameterised loader:
#: the matrix reports only the PRE-FIX and POST-FIX bands. The CLI can add
#: DEV/EVAL bands ("task 2: tune on dev, then eval ONCE") without touching
#: anything else: a band is just another named seed family and every table
#: carries its label.
DEFAULT_FAMILY_RANGES: dict[str, str] = {
    "PRE-FIX": "0-9,42-51",
    "POST-FIX": "200-209",
}
#: Preference order for choosing the report's primary band. POST-FIX stays
#: first; extra families follow, so a runs root holding only the dev/eval
#: bands still renders with the honest band labels.
FAMILY_RANK = ("POST-FIX", "EVAL", "DEV", "PRE-FIX")


def s6fam_matches(famname: str, rank: str) -> bool:
    """Family-name match for the S6 protocol split.

    The S6 protocol families are labelled "POST-FIX (protocol: ...)"; the
    declared protocol keeps the bare "POST-FIX" name so every table keyed on
    rank still renders with n=10 cells. Prefix matching stays scoped to S6
    labels only -- no other family uses that spelling.
    """
    return (famname == rank
            or (famname.startswith(rank + " (")
                and "protocol:" in famname))


def load_runs(runs_root: Path) -> tuple[list[dict], list[str]]:
    """POST-FIX-primary view (back-compat; tests grep this signature).
    The per-family breakdown is load_runs_families()."""
    runs, skipped, _fam = load_runs_families(runs_root)
    return runs, skipped


def load_runs_families(
    runs_root: Path,
    family_ranges: dict[str, str] | None = None,
) -> tuple[list[dict], list[str],
           dict[tuple[str, str, str], list[dict]]]:
    """Everything load_runs does, plus the explicit PRE-FIX/POST-FIX split
    so the report can render BOTH generations side by side (task 5: labelled
    blocks -- a reader must never wonder which engine produced a cell).
    `family_ranges` maps FAMILY LABEL -> seed-range spec ('400-409'); it
    REPLACES the default tracked set, never extends it silently."""
    return _load_runs_inner(runs_root, family_ranges)


def _load_runs_inner(
    runs_root: Path,
    family_ranges: dict[str, str] | None = None,
) -> tuple[list[dict], list[str],
           dict[tuple[str, str, str], list[dict]]]:
    """Every directory under runs_root carrying config.json + workloads.json.

    A directory without both is not a complete run; it is skipped and its name
    listed in the report so the skip is visible, never silent.
    """
    famspec = DEFAULT_FAMILY_RANGES if family_ranges is None else family_ranges
    franges: dict[str, list[tuple[int, int]]] = {
        k: _parse_ranges(v) for k, v in famspec.items()}
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
        runs.append({"dir": d.name, "path": d, "cfg": cfg, "wl": wl,
                     "res": res, "samples": samples})
    # Matrix cells must track families explicitly (PRE-FIX vs POST-FIX)
    runs_all = runs
    fam: dict[tuple[str, str], list[tuple[int, dict]]] = {}
    for r in runs_all:
        try:
            seed = int(r["cfg"].get("seed", 0))
        except (TypeError, ValueError) as e:
            skipped.append(f"{r['dir']} (bad seed value: {e})")
            continue
        fam.setdefault((r["cfg"].get("scenario", "?"), r["cfg"].get("system", "?")),
                       []).append((seed, r))
    runs_by_family: dict[tuple[str, str, str], list[dict]] = {}
    dropped = []
    for (sc, sysname), members in sorted(fam.items()):
        # S6 runs split BY PROTOCOL (declaration task3-params.md: no pooling
        # across protocol generations). The older charts mixed two protocols
        # (300-309: 40s run, intent at t~1s, TTL 15s; 310-319: 60s run,
        # intent at t=10s, TTL 20s) into ONE n=20 cell, which pushed n out of
        # the t-table range and hid a protocol change the reader had no way
        # to see. The protocol tuple comes from each run's config.json. The
        # protocol whose tuple matches the current declared protocol feeds
        # the primary "POST-FIX" family (back-compat with every table keyed
        # on rank), and every OTHER protocol generation gets its own labelled
        # family "POST-FIX (protocol ...)".
        if sc == "s6_intent_expire":
            declared = (60.0, 10.0, 20.0)
            proto: dict[tuple[float, float, float], list] = {}
            keep_any = set(s for s, _ in members)
            for _s, r in members:
                key = tuple(float(r["cfg"].get(k) or fallback)
                            for k, fallback in
                            (("duration_s", 40.0), ("intent_at_s", 1.0),
                             ("intent_ttl_s", 15.0)))
                proto.setdefault(key, []).append(r)
            if declared in proto:
                runs_by_family[(sc, sysname, "POST-FIX")] = proto[declared]
                del proto[declared]
            else:      # unseen protocol: keep the pool only if all agree
                tops = sorted(proto.items())
                if len(tops) == 1:
                    runs_by_family[(sc, sysname, "POST-FIX")] = tops[0][1]
                    del proto[tops[0][0]]
            for (dur, at, ttl), rs in sorted(proto.items()):
                runs_by_family[
                    (sc, sysname,
                     f"POST-FIX (protocol: {dur:.0f}s run, intent at "
                     f"{at:.0f}s, TTL {ttl:.0f}s)")] = rs
            dropped.extend([])
            continue
        seeds_all = sorted(s for s, _ in members)
        fam_seeds: dict[str, list[int]] = {}
        for famname, ranges in franges.items():
            fam_seeds[famname] = sorted(
                s for s in seeds_all
                if any(lo <= s <= hi for lo, hi in ranges))
        for famname, fseeds in fam_seeds.items():
            if not fseeds:
                continue
            fset = set(fseeds)
            kept = []
            for s, r in members:
                if s in fset:
                    kept.append(r)
            if kept:
                runs_by_family[(sc, sysname, famname)] = kept
        tracked: dict[str, list[tuple[int, int]]] = franges
        keep_any = set(seeds_all) & {
            s for ranges in tracked.values() for lo, hi in ranges
            for s in range(lo, hi + 1)}
        for s, r in members:
            if s not in keep_any:
                dropped.append(
                    f"{r['dir']} (outside tracked seed families: "
                    + "; ".join(f"{k} {v}" for k, v in famspec.items())
                    + ")")
    skipped.extend(sorted(dropped))
    # Primary band = the first ranked family present (POST-FIX normally).
    # Exact name first; the S6 protocol-labelled spellings only fill a rank
    # when no exact-family run shares it (so the declared protocol family
    # never pools with a legacy one).
    runs = []
    for rank in FAMILY_RANK:
        blocks = [runs_by_family[k] for k in runs_by_family
                  if k[2] == rank]
        if not blocks:
            blocks = [runs_by_family[k] for k in runs_by_family
                      if s6fam_matches(k[2], rank)]
        if blocks:
            runs = [r for blk in blocks for r in blk]
            break
    if not runs:
        runs = runs_all
    # attach family info (same parse, one label per seed)
    for r in runs:
        s = None
        try:
            s = int(r["cfg"].get("seed", 0))
        except (TypeError, ValueError):
            r["_seed_family"] = "UNKNOWN"
            continue
        if r["cfg"].get("scenario") == "s6_intent_expire":
            r["_seed_family"] = "POST-FIX"
        else:
            r["_seed_family"] = "OTHER"
            for famname, ranges in franges.items():
                if any(lo <= s <= hi for lo, hi in ranges):
                    r["_seed_family"] = famname
                    break
    return runs, skipped, runs_by_family


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


_SINK_RE = re.compile(r"\[([\w.-]+) sink\]\s+(\d+)\s+bytes\s+([\d.]+)\s+Mbps")


def sink_mbps(run: dict, label: str) -> tuple[float | None, str]:
    """Receiver-side delivered Mbps for one label, from `<label>.sink.log`.

    The sink (receiver) is the only party that knows what actually ARRIVED;
    sender_mbps says what was pushed. Returns (mbps, basis-note); the note
    says how many sink lines the figure came from, because a label with N
    parallel connections prints N lines and the receiver total is their sum.
    Missing file/line -> (None, reason) and the caller prints NOT AVAILABLE,
    never a fabricated zero.
    """
    p = run.get("path")
    if p is None:
        return None, "no run path recorded"
    logp = Path(p) / f"{label}.sink.log"
    if not logp.exists():
        return None, f"no {logp.name} in the run dir"
    hits = _SINK_RE.findall(logp.read_text(errors="replace"))
    if not hits:
        return None, "sink log has no receiver total line"
    total = sum(float(h[2]) for h in hits)
    basis = ("1 sink line" if len(hits) == 1
             else f"sum of {len(hits)} sink lines")
    return total, basis


_SINK_TS_RE = re.compile(r"\[\s*([\w.-]+) sink\]\s+t=(\S+)\s+cum=(\d+)\s+"
                         r"bytes\s+inst=(\S+) Mbps")

#: The sink process starts 1.0 s (launcher's bind sleep) + the scenario's
#: settle time BEFORE the driver's t=0, so the sink's own clock runs AHEAD
#: of the run clock by that much. Declared constant, never fitted.
SINK_CLOCK_LEAD_S = 1.0


#: S6 window split (task3-params.md): the run divides at the intent's own
#: times, not at chosen landmarks. Recovery definitions are the constants
#: tools/verify_s6.py already enforces (90% of the pre-intent receiver
#: median within 5 s of expiry); they are re-declared here so the report
#: table and the verifier cannot drift apart in silence.
S6_RECOVERY_FRAC = 0.90
S6_RECOVERY_LIMIT_S = 5.0

#: S2b (declared docs/evidence/s2b-params.md, before the S2b dataset): the
#: bind criterion is "applied tree within 10% of the link's truth"; there
#: is no per-scenario tuning of it.
S2B_BIND_TOL = 0.10

#: S2b band scenario names, in declared order: the four S2b shapes plus the
#: round-3 DEV shapes (docs/evidence/round3-params.md) and s3_stress (S3
#: with demand above capacity, doced unsatisfied in
#: docs/gap-closure/qos-baseline-comparison.md). Missing scenarios simply
#: do not render (`if not sc_runs: continue`).
S2B_SCENARIOS = ("s2b_step_50", "s2b_step_10", "s2b_step_up_20to100",
                 "s2b_ramp_100to30",
                 "s7_up_20to60", "s7_up_30to100", "s7_rampup_30to100",
                 "s7_down_100to15", "s7_down_100to8", "s3_stress")

#: Flat-link band scenarios: no change event at all, so the step table's
#: bind/tracking columns have no truth change to bind to -- the flat table
#: reports delay and delivered goodput instead (declared, round3-params).
FLAT_SCENARIOS = ("s3_stress",)

#: Sheets the window table reports, verbatim sheet keys as samples.jsonl
#: carries them.
S6_SHEETS = ("video_call_voice", "interactive_gaming", "bulk_download",
             "unknown")


def _window_of(run: dict) -> tuple[float, float, float] | None:
    """(fired, expiry, run_end) in run seconds, or None without an intent."""
    res = run.get("res") if isinstance(run.get("res"), dict) else {}
    intent = res.get("intent") or {}
    fired = intent.get("fired_at_run_t_s")
    ttl = run["cfg"].get("intent_ttl_s")
    if not isinstance(fired, (int, float)):
        return None
    ttl = ttl if isinstance(ttl, (int, float)) else 20.0
    duration = run["cfg"].get("duration_s")
    end = (duration if isinstance(duration, (int, float))
           else (run["samples"][-1]["t"] if run["samples"] else fired + ttl))
    return float(fired), float(fired) + float(ttl), float(end)


def _class_sheet_median(run: dict, window: tuple[float, float],
                        sheet: str, field: str) -> float | None:
    """Median of one per-tick sheet field inside a window. An empty window
    is never reported as 0: None means no ticks carried the value."""
    lo, hi = window
    if hi <= lo:
        return None
    vals = []
    for x in run["samples"]:
        t = x.get("t")
        if not (isinstance(t, (int, float)) and lo <= t < hi):
            continue
        v = (x.get("per_class") or {}).get(sheet) or {}
        w = v.get(field)
        if w is not None:
            vals.append(float(w))
    return statistics.median(vals) if vals else None


def _run_recovery_s(run: dict) -> float | None:
    """Receiver-side seconds from the intent's expiry to the bulk stream at
    >= 90% of its pre-intent median (declared 0.90/5s), or None."""
    w = _window_of(run)
    if w is None:
        return None
    fired, expiry, end = w
    c_bulk, _bb = sink_inst_series(run, "bulk")
    pre = [v for t, v in c_bulk if t < fired]
    med = statistics.median(pre) if pre else 0.0
    if med <= 0:
        return None
    hits = [t for t, v in c_bulk
            if expiry <= t <= expiry + S6_RECOVERY_LIMIT_S
            and v >= S6_RECOVERY_FRAC * med]
    return float(min(hits) - expiry) if hits else None


def _per_arm_recovery(runs_: list[dict]) -> list[float]:
    """Recovery seconds per run; runs without one (no meter / no
    pre-median) drop out, and len() vs n is visible to the reader."""
    return [s for r in runs_
            if (s := _run_recovery_s(r)) is not None]



def s6_verdict_prose(add, grp: list[dict]) -> None:
    """Per-protocol verdict bullets, computed from the runs on disk (never
    pooled with the other generation): whole-run call p95 and game p95 per
    arm, pairwise CI-overlap ACIQ-vs-CAKE-static and ACIQ-vs-B0, and the
    whole-run caveat that these figures include each arm's own launch
    behaviour (the prefix every system pays, quantified in S1/S2)."""
    add("#### Verdict (this protocol, whole-run figures)")
    add("")
    got = {}
    for arm in ARM_ORDER:
        runs_ = [x for x in grp if x["cfg"].get("system") == arm]
        if not runs_:
            continue
        calls = [call_metrics(r["wl"]).get("p95") for r in runs_]
        calls = [c for c in calls if c is not None]
        games = [game_p95(r["wl"]) for r in runs_]
        games = [g for g in games if g is not None]
        got[arm] = (runs_, calls, games)
        add(f"- {ARM_LABELS.get(arm, arm)}: call p95 {fmt(calls)} ms; "
            f"game p95 {fmt(games)} ms")
    if "aciq" in got and "b1_cake95" in got:
        txt = (f"- ACIQ vs CAKE-static call p95 CIs: "
               f"{ci_overlap(got['aciq'][1], got['b1_cake95'][1])}")
        if "b0_fifo" in got:
            txt += ("; ACIQ vs B0: "
                    f"{ci_overlap(got['aciq'][1], got['b0_fifo'][1])}")
        txt += "."
        add(txt)
    add("- caveat: whole-run distributions include each arm's own launch "
        "prefix; the steady-window separation is the S1 section's job "
        "(declared prefix, one number, not tuned per run).")
    add("")


def emit_s6_windows(add, grp: list[dict]) -> None:
    """Before / during / after table for ONE protocol generation.

    Windows come from each run's own intent: [start, fired), [fired,
    fired+ttl), [fired+ttl, end). Per-window END-TO-END call/game p95 is not
    derivable from the committed S6 artefacts (the flow jsons carry
    whole-run distributions only); that cell says NOT AVAILABLE instead of
    reusing the whole-run number. Per-tick per-class goodput medians and the
    router's own per-class probe p95 medians are aggregated to per-window
    mean +/- t-CI across the arm's n=10 runs."""
    add("#### Before / during / after windows (per-window mean +/- t-CI "
        "over the arm's runs; goodput = per-class RECEIVER sheet median "
        "per run, Mbps; probes = the ROUTER's own per-class rtt-p95 sheet "
        f"median per run, ms; recovery target {S6_RECOVERY_FRAC:.0%} of the "
        f"pre-intent receiver median inside {S6_RECOVERY_LIMIT_S:.0f}s of "
        "expiry)")
    add("")
    rows: list[tuple[str, list[list[str]]]] = []
    for arm in ARM_ORDER:
        runs_ = [x for x in grp if x["cfg"].get("system") == arm]
        if not runs_:
            continue
        # windows only make sense where an intent was granted; arms without
        # an intent surface get one honest line, not an empty table
        if not any(_window_of(x) for x in runs_):
            rows.append((ARM_LABELS.get(arm, arm), [[
                "-", "-", "-", "-", "-",
                "no intent surface: windows not applicable"]]))
            continue
        cells: list[list[str]] = []
        cells.append(["window", "call goodput", "game goodput",
                      "bulk goodput", "unknown goodput",
                      "probe rtt p95 (attached sheet)"])
        windows = ("before", "during", "after")
        for wname in windows:
            row = [wname]
            for sheet in ("video_call_voice", "interactive_gaming",
                          "bulk_download", "unknown"):
                vals = _collect_window(runlist=runs_, wname=wname,
                                       sheet=sheet, field="goodput_mbps")
                row.append(fmt(vals, 2) if vals else NOT_AVAILABLE)
            vals = _collect_window(runlist=runs_, wname=wname,
                                   sheet="unknown", field="rtt_p95")
            row.append(fmt(vals, 1) if vals else
                       NOT_AVAILABLE + " (probe sheet has no rtt samples)")
            cells.append(row)
        rec_vals = _per_arm_recovery(runs_)
        cells.append(["bulk recovery from expiry (s), "
                      "90%/5s target, when met",
                      fmt(rec_vals, 2) if rec_vals
                      else (NOT_AVAILABLE
                            + " (no run met the target)")])
        rows.append((ARM_LABELS.get(arm, arm), cells))
    for arm_label, cells in rows:
        add(f"**{arm_label}**")
        add("")
        for cells_row in cells:
            add(row_md(cells_row))
        add("")
    add("- per-window END-TO-END call/game p95/jitter/loss is NOT AVAILABLE "
        "here: the S6 flow jsons store one whole-run distribution each (the "
        "sender prints a single json at exit); per-window end-to-end latency "
        "arrives with the live instrumented trace, not from these artefacts.")
    add("- 'consumed' deliberately dropped as a duplicate of the bulk sheet; "
        "the pre-intent receiver median is already in the verifier's floor "
        "line above.")
    add("")


def _collect_window(runlist: list[dict], wname: str, sheet: str,
                    field: str) -> list[float]:
    """Per-window values across runs: (wname) -> each run's per-window
    median of [sheet][field]."""
    out = []
    for r in runlist:
        w = _window_of(r)
        if w is None:
            continue
        fired, expiry, end = w
        start = max(2.0, r["cfg"].get("settle_s") or 0.0)
        lo_hi = {"before": (start, fired), "during": (fired, expiry),
                 "after": (expiry, end)}[wname]
        v = _class_sheet_median(r, lo_hi, sheet, field)
        if v is not None:
            out.append(v)
    return out


def _s2b_change(run: dict) -> tuple[float, float, float] | None:
    """(change_at, truth_before, truth_after) for a STEP s2b run, or None.

    The step is the run's own declared event: a down-step is the drop; the
    up-step is the recover (its drop is a no-op at the same rate). Read from
    config.json, never from a module constant."""
    cfg = run["cfg"]
    link = cfg.get("link_mbps")
    if cfg.get("ramp_to_mbps") is not None:
        return None
    rec = cfg.get("recover_at_s")
    if rec is not None and cfg.get("recover_to_mbps") is not None:
        return float(rec), float(link), float(cfg["recover_to_mbps"])
    drop_at = cfg.get("drop_at_s")
    if drop_at is not None and cfg.get("drop_mbps") is not None:
        return float(drop_at), float(link), float(cfg["drop_mbps"])
    return None


def _s2b_truth_fn(run: dict) -> tuple[callable, float]:
    """(truth(t), t_change) for any s2b run -- the ramp version interpolates
    linearly inside the declared window; the steps return the protocol's
    two plateaus."""
    cfg = run["cfg"]
    link = float(cfg.get("link_mbps") or 0.0)
    ramp_to = cfg.get("ramp_to_mbps")
    if ramp_to is not None:
        ramp_at = float(cfg.get("ramp_at_s") or 0.0)
        dur = float(cfg.get("ramp_duration_s") or 0.0)
        to = float(ramp_to)

        def truth(t: float) -> float:
            if t <= ramp_at:
                return link
            frac = ((t - ramp_at) / dur) if dur > 0 else 1.0
            return link + (to - link) * min(1.0, frac)

        return truth, ramp_at
    ch = _s2b_change(run)
    if ch is None:
        return (lambda t: link), 0.0
    at, pre, post = ch

    def truth(t: float) -> float:
        return post if t >= at else pre

    return truth, at


def _s2b_series(run: dict) -> list[tuple[float, float]]:
    """(t, applied_mbps) for the row's "applied" semantics, per ARM.

    ACIQ re-arms every tick, so its samples' capacity_mbps IS the applied
    tree. The CAKE arms shape ONCE at launch into per-class tokens; their
    samples' capacity_mbps carries the launch LINK, never the shaped rate,
    so the applied value comes from config.json's cake_rate_at_apply (the
    artefact states the tree rate). B0 shapes nothing; its samples'
    capacity is its launch set, so the series stands. None capacities drop
    out (the report does not invent a rate for a tick the harness did not
    measure)."""
    out = []
    for s in run["samples"]:
        cap = s.get("capacity_mbps")
        if isinstance(cap, (int, float)) and math.isfinite(float(cap)):
            out.append((float(s["t"]), float(cap)))
    cfg = run["cfg"]
    if cfg.get("system") in ("b1_cake95", "b1_cake_oracle"):
        rate = cfg.get("cake_rate_at_apply")
        if isinstance(rate, (int, float)) and math.isfinite(float(rate)):
            return [(float(s["t"]), float(rate)) for s in run["samples"]
                    if isinstance(s.get("t"), (int, float))]
    return out


def _s2b_bind_s(run: dict) -> float | None:
    """First tick >= change_at satisfying S2B_BIND_TOL of truth, which then
    holds to the END of the run (the declared 'stays there').

    Ramp runs are judged AFTER the ramp completes (the declared rule): the
    truth is a moving target inside the ramp window, and a tick that
    happens to track a moving target says nothing about settling."""
    truth, at = _s2b_truth_fn(run)
    cfg = run["cfg"]
    ramp_to = cfg.get("ramp_to_mbps")
    hold_from = at
    if ramp_to is not None:
        ramp_end = float(at) + float(cfg.get("ramp_duration_s") or 0.0)
        hold_from = ramp_end
    ser = _s2b_series(run)
    ok = None
    for t, cap in ser:
        tv = truth(t)
        if abs(cap - tv) <= S2B_BIND_TOL * tv and t >= hold_from:
            if ok is None:
                ok = t
        else:
            ok = None
    return ok


def _s2b_window_err(run: dict, lo: float, hi: float) -> float | None:
    """Mean |applied - truth| over a window; needs ticks inside it."""
    truth, _at = _s2b_truth_fn(run)
    errs = [abs(cap - truth(t)) for t, cap in _s2b_series(run)
            if lo <= t <= hi]
    return statistics.fmean(errs) if errs else None


def _s2b_final_third(run: dict) -> tuple[float, float]:
    """(lo, hi) of the last third of the run's observed tick range."""
    ser = _s2b_series(run)
    if not ser:
        return 0.0, 0.0
    t0, t1 = ser[0][0], ser[-1][0]
    return t0 + (t1 - t0) * (2.0 / 3.0), t1


def _s2b_sink_last_third(run: dict, label: str = "bulk") -> float | None:
    """Receiver-side delivered Mbps (inst mean) over the run's final third."""
    series, _note = sink_inst_series(run, label)
    if not series:
        return None
    lo, hi = _s2b_final_third(run)
    vals = [v for t, v in series if lo <= t <= hi]
    return statistics.fmean(vals) if vals else None


def _s2b_honesty(run: dict) -> str:
    """ACIQ's declared failure admission (docs/evidence/s2b-params.md):
    machine-computed from the final tick; never a judgement in prose."""
    if not run["samples"]:
        return NOT_AVAILABLE
    last = run["samples"][-1]
    if "estimator_saturated" not in last:
        return NOT_AVAILABLE + " (no saturation signal in the artefact)"
    sat = last.get("estimator_saturated")
    cap = last.get("capacity_mbps")
    truth, _at = _s2b_truth_fn(run)
    tv = truth(last["t"])
    cap_s = (f"{cap:.1f}" if isinstance(cap, (int, float)) else NOT_AVAILABLE)
    conf = last.get("estimator_confidence")
    conf_s = (f", confidence {conf:.2f}"
              if isinstance(conf, (int, float)) else "")
    if sat:
        return (f"final tick: saturated, applied {cap_s} vs truth {tv:.1f}"
                f"{conf_s}")
    err = (abs(cap - tv) / tv * 100.0
           if isinstance(cap, (int, float)) and tv > 0 else None)
    why = (f", {err:.0f}% off truth" if err is not None else "")
    return (f"final tick: UNSATURATED (estimator not saturated at the "
            f"end regime), applied {cap_s} vs truth {tv:.1f}{why}"
            f"{conf_s}")


def _s2b_is_up(run: dict) -> bool | None:
    """True when the run's change event RAISES the link truth (up-step /
    up-ramp), False for a drop, None for flat or ramp_to=None oddities."""
    ch = _s2b_change(run)
    if ch is None:
        return None
    return ch[2] > ch[1]


def _s2b_utilization(run: dict, lo: float, hi: float
                     ) -> tuple[float, float | None] | None:
    """Declared round-3 up-step metric: (applied/truth, delivered/truth)
    over the post-change window [lo, hi].

    applied/truth is the kernel-side series (`_s2b_series`, change-log
    grounded); delivered/truth is receiver-side: the SUM of every label's
    sink inst means over the same window. A run that is not an up-step
    returns None, so callers can print '-' and never imply a utilization
    number for a drop."""
    ch = _s2b_change(run)
    if ch is None or ch[2] <= ch[1]:
        return None
    truth, _at = _s2b_truth_fn(run)
    tv = truth((lo + hi) / 2.0)
    ser = [(t, c) for t, c in _s2b_series(run) if lo <= t <= hi]
    if not ser or tv <= 0:
        return None
    applied_util = statistics.fmean(c for _t, c in ser) / tv
    delivered = 0.0
    have_receiver = False
    for label in sorted((run["wl"] or {}).keys()):
        series, _note = sink_inst_series(run, label)
        vals = [v for t, v in series if lo <= t <= hi]
        if vals:
            have_receiver = True
            delivered += statistics.fmean(vals)
    return (applied_util, delivered / tv if have_receiver else None)


def emit_s2b(add, runs: list[dict]) -> None:
    """One table per declared band scenario; arms are rows, t-CIs at n=10.

    Round-3 rework (docs/evidence/round3-params.md, declared before the
    band): bind prefixed `n/a (up-step)` for up-runs -- "bind" named how
    fast a controller CAME DOWN, not how fast it climbed; climbing is the
    separate utilization column (measures what fraction of the truth was
    actually pulled through, kernel applied AND receiver delivered).
    s3_stress has no change event at all, so it gets a dedicated flat
    table (delay + delivered goodput) instead of step columns that have
    no meaning there."""
    for sc in S2B_SCENARIOS:
        sc_runs = [r for r in runs if r["cfg"].get("scenario") == sc]
        if not sc_runs:
            continue
        add(f"### {sc}")
        add("")
        arms_seen = sorted({r["cfg"].get("system") for r in sc_runs})
        if sc in FLAT_SCENARIOS:
            add(row_md(["arm", "n", "call p95 whole-run (ms)",
                        "game p95 whole-run (ms)",
                        "bulk receiver mean inst (Mbps)",
                        "tv1 / tv2 / tv3 receiver mean inst (Mbps)",
                        "overload note (loaded vs capacity)"]))
            add(row_md(["---"] * 7))
            for arm in [a for a in ARM_ORDER if a in arms_seen]:
                grp = [r for r in sc_runs
                       if r["cfg"].get("system") == arm]
                if not grp:
                    continue
                calls = [call_metrics(r["wl"]).get("p95") for r in grp]
                games = [game_p95(r["wl"]) for r in grp]
                bulks = []
                for r in grp:
                    series, _note = sink_inst_series(r, "bulk")
                    if series:
                        bulks.append(statistics.fmean(
                            v for _t, v in series))
                tvbours = []
                for r in grp:
                    tvs = []
                    for tv in ("tv1", "tv2", "tv3"):
                        series, _note = sink_inst_series(r, tv)
                        if series:
                            tvs.append(statistics.fmean(
                                v for _t, v in series))
                    tvbours.append(" / ".join(
                        f"{v:.2f}" for v in tvs) if tvs else NOT_AVAILABLE)
                link = float(next(iter(r["cfg"].get("link_mbps")
                                       for r in grp if
                                       r["cfg"].get("link_mbps")), 0.0))
                note = (f"flat link truth {link:.0f} Mbps; demand spans "
                        "game + 3 tvs + bulk (see round3-params)")
                add(row_md([ARM_LABELS.get(arm, arm), str(len(grp)),
                            fmt(calls), fmt(games),
                            fmt(bulks, 2) if bulks else NOT_AVAILABLE,
                            "; ".join(tvbours) if any(
                                t != NOT_AVAILABLE for t in tvbours)
                            else NOT_AVAILABLE,
                            note]))
            add("")
            continue
        add(row_md(["arm", "n", "bind_s", "mean |applied-truth| final "
                    "third (Mbps)", "call p95 whole-run (ms)",
                    "bulk receiver mean, final third (Mbps)",
                    "up-step utilization final third "
                    "(applied/truth, delivered/truth)",
                    "ACIQ honesty (final tick)"]))
        add(row_md(["---"] * 8))
        for arm in [a for a in ARM_ORDER if a in arms_seen]:
            grp = [r for r in sc_runs if r["cfg"].get("system") == arm
                   and (_s2b_change(r) is not None
                        or r["cfg"].get("ramp_to_mbps") is not None)]
            if not grp:
                continue
            is_up = all(_s2b_is_up(r) is True for r in grp if
                        r["cfg"].get("ramp_to_mbps") is None) \
                and any(_s2b_is_up(r) is True for r in grp)
            binds = None
            if is_up:
                # Declared (round3-params.md): bind is not a claim the
                # engine makes on an up-move, so the cell says so instead
                # of quietly reporting the recover-gate as if it were a
                # failure to come down.
                bind_str = "n/a (up-step)"
            else:
                binds = [b for r in grp if (b := _s2b_bind_s(r)) is not None]
                bind_str = (fmt(binds, 1) if binds
                            else f"{NOT_AVAILABLE} (0/{len(grp)}"
                                 f" binds met inside the run)")
            errs = [e for r in grp if (e := _s2b_window_err(
                r, *_s2b_final_third(r))) is not None]
            calls = [call_metrics(r["wl"]).get("p95") for r in grp]
            calls = [c for c in calls if c is not None]
            bulks = [b for r in grp if (b := _s2b_sink_last_third(r))
                     is not None]
            utils: list[tuple[float, float | None]] = []
            for r in grp:
                lo, hi = _s2b_final_third(r)
                u = _s2b_utilization(r, lo, hi)
                if u is not None:
                    utils.append(u)
            if utils:
                d_cells = [d for _a, d in utils if d is not None]
                util_str = (f"appl {fmt([a for a, _d in utils], 2)}"
                            + (f" / delv {fmt(d_cells, 2)}"
                               if d_cells else
                               " / delv NOT AVAILABLE (no receiver"
                               " sampler)"))
            elif is_up:
                util_str = (NOT_AVAILABLE
                            + " (no applied series in this window)")
            else:
                util_str = "-"
            extra = ""
            if arm == "aciq":
                seen_rows: list[str] = []
                counts: dict[str, int] = {}
                for r in grp:
                    h = _s2b_honesty(r)
                    counts[h] = counts.get(h, 0) + 1
                for h, k in counts.items():
                    seen_rows.append(f"{h} (n={k})" if k > 1 else h)
                extra = "; ".join(seen_rows)
            add(row_md([
                ARM_LABELS.get(arm, arm),
                str(len(grp)),
                bind_str,
                fmt(errs, 2) if errs else NOT_AVAILABLE,
                fmt(calls),
                fmt(bulks, 2) if bulks else NOT_AVAILABLE,
                util_str,
                extra or "honesty row declared for ACIQ only",
            ]))
        add("")


def emit_sink_starvation(add, runs: list[dict], arms: list[str]) -> None:
    """Receiver-side starvation (round 3, docs/evidence/round3-params.md):
    per-second `*.sink.log` inst rates, EVERY arm including the static
    baselines -- the controller-side series in the fairness section exist
    only on arms that shape a tree, so baseline starvation had nowhere to
    be counted from. Declared basis: series = the label's receiver
    sampler; threshold = 0.2x the SAME-regime median (starvation_threshold
    drop-aware); ticks before the declared warm-up excluded so a launch
    transient cannot count as starvation."""
    add("## Starvation, receiver side (every arm, per-second sink logs)")
    add("")
    add(row_md(["scenario", "arm", "label; starved inst ticks over seeds "
                "(longest streak)"]))
    add(row_md(["---"] * 3))
    any_row = False
    for sc in sorted({r["cfg"].get("scenario", "?") for r in runs}):
        for arm in arms:
            grp = per_arm(sc, arm, runs)
            if not grp:
                continue
            counted: dict[str, list[int]] = {}
            streaks: dict[str, list[int]] = {}
            for r in grp:
                for label in sorted((r["wl"] or {}).keys()):
                    if not isinstance((r["wl"] or {}).get(label), dict):
                        continue
                    series, _note = sink_inst_series(r, label)
                    if not series:
                        continue
                    series = [(t, v) for t, v in series if t >= WARMUP_S]
                    if not series:
                        continue
                    thr = starvation_threshold(
                        series, r["cfg"].get("drop_at_s"))
                    ts = [t for t, v in series if v < thr]
                    # longest run of consecutive one-second samples
                    longest = cur = 0
                    prev = None
                    for t in ts:
                        cur = cur + 1 if (prev is not None
                                          and t - prev <= 1.5) else 1
                        longest = max(longest, cur)
                        prev = t
                    key = label
                    counted.setdefault(key, []).append(len(ts))
                    streaks.setdefault(key, []).append(longest)
            cells = []
            for key in sorted(counted):
                n = sum(counted[key])
                cells.append(f"{key}: {n} tick(s) over "
                             f"{len(counted[key])} seed(s), longest "
                             f"streak {max(streaks[key])} s")
            if not cells:
                cells = [NOT_AVAILABLE + " (no per-second receiver "
                         "sampler in this arm's runs)"]
            else:
                any_row = True
            add(row_md([sc, ARM_LABELS.get(arm, arm), "; ".join(cells[:6])]))
    if not any_row:
        add("- no receiver-side starvation anywhere the sinks printed "
            "per-second series; cells without a sampler print "
            "NOT AVAILABLE above, never an assumed clean bill.")
    add("")


def emit_s3_per_tv(add, runlist: list[dict]) -> None:
    """S3 per-TV delivered goodput (TASK 5a): the three TV streams each get
    their own row basis, computed from that TV's per-second receiver
    sampler (`tvN.sink.log`). The sampler came in with the 2026 protocol;
    runs whose sinks printed only the whole-run total line say NOT
    AVAILABLE rather than reusing the sender's pushed rate. Gaming delay is
    already the dedicated `game p95 ms` column in the arm table above."""
    if not runlist:
        return
    add("#### Per-TV delivered goodput (receiver sampler, mean inst Mbps "
        "whole-run / final third)")
    add("")
    add(row_md(["arm", "n", "tv1", "tv2", "tv3",
                "which band carries the sampler"]))
    add(row_md(["---"] * 6))
    arms_seen = sorted({r["cfg"].get("system") for r in runlist})
    for arm in [a for a in ARM_ORDER if a in arms_seen]:
        grp = [r for r in runlist if r["cfg"].get("system") == arm]
        cells: list[str] = []
        n_with_sampler = 0
        for tv in ("tv1", "tv2", "tv3"):
            vals = []
            ft_vals = []
            n_sampler = 0
            for r in grp:
                series, note = sink_inst_series(r, tv)
                if series:
                    n_sampler += 1
                    vals.append(statistics.fmean(v for _t, v in series))
                    lo, hi = _s2b_final_third(r)
                    ft_vals.append(statistics.fmean(
                        v for t, v in series if lo <= t <= hi))
            if vals:
                n_with_sampler = max(n_with_sampler, n_sampler)
                cells.append(f"{fmt(vals, 2)} / {fmt(ft_vals, 2)}")
            else:
                cells.append(NOT_AVAILABLE
                             + " (no per-second sampler total line)")
        # One run, per-seed inspection, names where the sampler exists --
        # aggregated, not assumed from the first run.
        sampler = (f"per-second (n_sampler={n_with_sampler}/{len(grp)})"
                   if n_with_sampler else "whole-run total only")
        add(row_md([ARM_LABELS.get(arm, arm), str(len(grp)), *cells,
                    sampler]))
    add("- each TV cell is the label's own receiver series; TV streams share "
        "the streaming sheet in the controller's tree, so the SPLIT between "
        "them is a receiver-side fact and the arm-table's streaming-class "
        "counters are the router-side view.")
    add("")


def _call_obs_series(run: dict) -> list[tuple[float, float]] | None:
    """(recv_t, rtt_ms) per packet from call.obs.jsonl (the --observe
    per-packet trace). The writer flushes its tail out of sequence order,
    so the file is sorted by its own seq field first; runs without the
    trace return None and the table says NOT AVAILABLE."""
    p = run.get("path")
    if p is None:
        return None
    f = Path(p) / "call.obs.jsonl"
    if not f.exists():
        return None
    rows = []
    for line in f.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        seq = rec.get("seq")
        rt = rec.get("recv_t")
        rtt = rec.get("rtt_ms")
        if seq is None or rt is None or rtt is None:
            continue
        rows.append((seq, float(rt), float(rtt)))
    rows.sort()
    return [(rt, rtt) for _seq, rt, rtt in rows] or None


def _latency_cell(ser: list[tuple[float, float]] | None, lo: float,
                  hi: float) -> str:
    """One window cell of the per-run call-latency table; module level so
    the loop variable never rides a closure (B023)."""
    w = _window_latency([rtt for t, rtt in ser or []
                         if lo <= t < hi])
    if w is None:
        return NOT_AVAILABLE
    return (f"{w['p50']:.2f}/{w['p95']:.2f}"
            f"/{w['p99']:.2f}/{w['max']:.2f}")


def _window_latency(v: list[float]) -> dict | None:
    if not v:
        return None
    v = sorted(v)
    n = len(v)
    return {"p50": v[n // 2],
            "p95": v[min(n - 1, int(0.95 * n))],
            "p99": v[min(n - 1, int(0.99 * n))],
            "max": v[-1], "n": n}


def emit_call_obs(add, runlist: list[dict]) -> None:
    """Time-resolved call latency (TASK 6): per-packet rtt trace split
    into declared windows (before/at the first capacity change, then
    thirds). Whole-run percentiles name WHAT they integrate over but not
    WHEN they happened; this table answers 'when'. Only runs that carry
    call.obs.jsonl (the --observe trace) can appear: a run without the
    trace contributes absence, not a whole-run number in disguise."""
    if not runlist:
        return
    with_trace = [r for r in runlist if _call_obs_series(r) is not None]
    add("#### Time-resolved call latency (per-packet trace, --observe "
        "runs only; p50/p95/p99/max in ms per run)")
    add("")
    if not with_trace:
        add(f"{NOT_AVAILABLE} (no run in this band carries "
            "call.obs.jsonl; live --observe runs add it, and this "
            "table refuses whole-run distributions in its place)")
        add("")
        return
    add(row_md(["run", "whole run", "first 10 s", "second 10 s",
                "third 10 s"]))
    add(row_md(["---"] * 5))
    for r in sorted(with_trace, key=lambda x: x["dir"]):
        ser = _call_obs_series(r)
        cells = []
        for lo, hi in ((0.0, float("inf")), (0.0, 10.0), (10.0, 20.0),
                       (20.0, 30.0)):
            cells.append(_latency_cell(ser, lo, hi))
        add(row_md([r["dir"], *cells]))


def sink_inst_series(run: dict, label: str) -> tuple[
        list[tuple[float, float]], str]:
    """Per-second receiver-side instant rate series for one label (TASK 4).

    Source: the sampler every sink prints since sinksample.py --
    `[<kind> sink] t=<s> cum=<b> bytes inst=<Mbps> Mbps`. The sampler's own
    contract: printed inst k measures the interval SINCE the previous print,
    the first print's interval starting at sink-clock 0. inst k therefore
    covers (t[k-1], t[k]] with t[0] = 0, and the pair carries the interval's
    START: (t[k-1], inst[k]). Every start is remapped to the RUN clock (the
    sink was born SINK_CLOCK_LEAD_S + settle before the run's t=0), and
    pairs whose interval started before the run are dropped uniformly --
    they measure lab startup, not the run. Declared in the note, never
    tuned per run.
    """
    p = run.get("path")
    if p is None:
        return [], "no run path recorded"
    logp = Path(p) / f"{label}.sink.log"
    if not logp.exists():
        return [], f"no {logp.name} in the run dir"
    ts: list[float] = []
    vs: list[float] = []
    for hit in _SINK_TS_RE.finditer(logp.read_text(errors="replace")):
        try:
            t_v = float(hit.group(2))
            v_v = float(hit.group(4))
        except ValueError:
            continue        # t and inst are appended TOGETHER or not at all
        ts.append(t_v)
        vs.append(v_v)
    if len(vs) < 2:
        return [], (f"sink log has {len(vs)} usable sampler line(s); need >=2")
    lead = SINK_CLOCK_LEAD_S
    wl = run.get("cfg") if isinstance(run.get("cfg"), dict) else {}
    settle = wl.get("settle_s")
    if isinstance(settle, (int, float)):
        lead += float(settle)
    starts = [0.0] + ts[:-1]
    pairs = [(starts[i] - lead, vs[i])
             for i in range(len(vs)) if starts[i] - lead >= 0.0]
    return pairs, (f"{len(pairs)} per-second intervals on the run clock "
                   f"(sink clock lead {lead:.1f}s; pre-run intervals "
                   "dropped)")


def starvation_threshold(series: list[tuple[float, float]],
                         drop_at: float | None) -> float:
    """0.2 x median, computed over the SAME regime the verdict reads.

    A run with a mid-run capacity drop has two regimes; a whole-window
    median mixes them so every post-drop tick reads as starved against a
    pre-drop median. Where the run declares a drop, the median is the
    post-drop regime's own median -- otherwise the whole window's.
    """
    vals = [v for t, v in series
            if drop_at is None or t >= float(drop_at)]
    if not vals:
        vals = [v for _, v in series]
    return 0.2 * statistics.median(vals)

def run_sink_rates(run: dict) -> dict[str, tuple[float | None, str]]:
    """Receiver-side delivered Mbps per label (TASK 5a: keep tree counters
    separate; the sender/tree numbers stay in their own columns)."""
    out: dict[str, tuple[float | None, str]] = {}
    for label, rep in sorted((run["wl"] or {}).items()):
        if not isinstance(rep, dict):
            continue
        out[label] = sink_mbps(run, label)
    return out


def applied_capacity_series(run: dict) -> list[tuple[float, float]]:
    """(t, capacity the KERNEL was actually set to) on the run-relative axis.

    WHY THIS ORDER: the flag that was once preferred here (`governor.rate`
    per tick) is the DECIDED rate, and for legacy POST-FIX runs it differs
    from the kernel for the whole delay window (decided 19.43-ish, kernel
    stuck at 64.67). The truth of a bind claim is what tc carried
    (`result.json.policy_change_log[*].applied_state`), never what the
    governor intended.

    The log's timestamps are host-monotonic; they are rebased to the
    run-relative axis by subtracting the first governor decision's stamp
    (samples carry t=0 at the first tick; the two stamps agree to <0.01 s).
    Baselines have no governor and an empty change log, so they fall back
    to the per-tick samples (their tree never moves, which is the point).
    """
    res = run.get("res") or {}
    log = res.get("policy_change_log") or []
    decs = (res.get("governor") or {}).get("decisions") or []
    if log and decs:
        base = min(float(d.get("t", 0.0)) for d in decs)
        out = []
        for c in log:
            if not c.get("committed") or not c.get("ok"):
                continue
            cls = ((c.get("applied_state") or {}).get("classes") or {})
            parent = cls.get("1:1") or {}
            cap = parent.get("rate")
            if cap is None:
                continue
            t_log = c.get("t")
            if t_log is None:
                continue
            out.append((float(t_log) - base, float(cap)))
        if out:
            return out
    out = []
    for s in run["samples"]:
        t = s.get("t")
        if t is None:
            continue
        cap = None
        g = s.get("governor") or {}
        if isinstance(g, dict):
            for k in ("rate", "ceiling_mbps"):
                v = g.get(k)
                if v is not None:
                    try:
                        cap = float(v)
                        break
                    except Exception:
                        pass
        if cap is None:
            cap = s.get("applied_capacity_mbps") or s.get("applied_rate_mbps")
        if cap is None:
            cap = s.get("capacity_mbps")
        if cap is None:
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


def warmup_all(samples: list[dict]) -> list[dict]:
    """Drop the declared warm-up SAMPLE ROWS (not a value series).

    Same constant, applied one level up so `label_carrying` can pick its
    carrying class from only the post-warm-up ticks."""
    out = []
    for s in samples:
        t = s.get("t")
        if isinstance(t, (int, float)) and t >= WARMUP_S:
            out.append(s)
    return out


#: A tree rebuild DELETES and re-adds the qdisc, which resets EVERY counter on
#: the device. The tick that straddles a rebuild therefore houses a link
#: whose rx/tx bytes went BACKWARDS -- a measured, clock-free signature of
#: "attributed goodput at this tick is a reset artefact, not silence".
def analysis_samples(run: dict) -> list[dict]:
    """Sample rows the per-tick verdicts are computed over, exclusions DECLARED:

    1. warm-up (t >= WARMUP_S) -- counter-ramp artefact, diagnosis fix 17;
    2. t <= configured duration -- post-run tail excluded (workload finished);
    3. ticks whose link counters went BACKWARDS -- the qdisc was rebuilt
       between ticks (del/re-add resets every counter), so all per-class
       goodput at that tick is attribution reset, not a delivery gap;
    4. the raw tick right after such a reset -- the collector computed its
       rate from the reset-tick counters, so the number spans the reset gap
       and is a rebuild artefact, not the rate of those seconds;
    5. gap rates: a tick whose recorded rate was computed over
       dt > TICK_GAP_MAX_S is regime-mixed (poll gap or reset recovery);
       at ~1 s ticks a rate past 3 s is a mean over a gap, not a rate;
    6. boundaries: a tick whose rate interval (t - dt_raw, t] crosses a
       scenario boundary (the capacity drop at `drop_at_s`, or the recovery
       step) straddles two regimes, so it is neither pre nor post value;
       excluded from BOTH sides symmetrically.

    dt is taken from the RAW sample chain -- the collector computed the
    rates against raw[i-1], so that is the only dt the rate facts speak
    for. Every exclusion above is printed with the tables that use it.
    """
    raw = run["samples"]
    if not raw:
        return []
    dur = run["cfg"].get("duration_s")
    bound = sorted({float(v) for key in ("drop_at_s", "recover_at_s")
                    for v in (run["cfg"].get(key),)
                    if isinstance(v, (int, float))})
    # rate facts per raw index (the collector's own arithmetic, replayed)
    meta: list[tuple[float | None, bool, bool]] = []   # dt, rate_invalid, crossed
    for i, x in enumerate(raw):
        t = x.get("t")
        if not isinstance(t, (int, float)) or i == 0:
            meta.append((None, False, False))       # no rate fact at raw[0]
            continue
        pt = raw[i - 1].get("t")
        dt = (t - pt) if isinstance(pt, (int, float)) else None
        prx = (raw[i - 1].get("link") or {}).get("rx_bytes")
        rx = (x.get("link") or {}).get("rx_bytes")
        spans_reset = (isinstance(prx, (int, float))
                       and isinstance(rx, (int, float)) and rx < prx)
        invalid = (dt is None or dt <= 0 or dt > TICK_GAP_MAX_S
                   or spans_reset)
        crossed = (dt is not None and any(pt < b <= t for b in bound))
        meta.append((dt, invalid, crossed))
    # deferred rule: the POST-reset tick keeps its place but its rate was
    # computed from the reset's own counters, so mark it too
    rate_bad: list[bool] = [m[1] for m in meta]
    for i, (_, spans_reset, _) in enumerate(meta):
        if spans_reset and i + 1 < len(raw):
            rate_bad[i + 1] = True
    out: list[dict] = []
    for i, x in enumerate(raw):
        t = x.get("t")
        if isinstance(dur, (int, float)) and isinstance(t, (int, float)) \
                and t > float(dur):
            continue
        if isinstance(t, (int, float)) and t < WARMUP_S:
            continue
        if rate_bad[i] or meta[i][2]:
            continue
        out.append(x)
    return out


#: Grace before a generator's own stop: the last second of a workload's life
#: is teardown (rate collapse on sender exit) and it hit every arm at the
#: same tick, so it is excluded uniformly. Declared, uniform, never tuned.
TEARDOWN_GRACE_S = 1.0


def label_window(run: dict, label: str,
                 base: list[dict] | None = None) -> list[dict]:
    """Per-LABEL time window: up to the label generator's own lifetime.

    `elapsed_s` in workloads.json is the generator's own measured runtime. A
    verdict about a label measured after its own traffic stopped describes
    nothing about the label. Capped also by the run's configured duration.
    TEARDOWN_GRACE_S (=1.0, declared) trims the final second of the sender's
    own life as well: the last tick before a generator stops is teardown
    (rate collapse on fin/sender exit) and it hit EVERY arm at the same tick,
    so it is excluded uniformly rather than scored.
    """
    if base is None:
        base = analysis_samples(run)
    rep = (run["wl"] or {}).get(label)
    el = rep.get("elapsed_s") if isinstance(rep, dict) else None
    dur = run["cfg"].get("duration_s")
    hi = None
    for v in (el, dur):
        if isinstance(v, (int, float)):
            hi = float(v) - TEARDOWN_GRACE_S if hi is None \
                else min(hi, float(v) - TEARDOWN_GRACE_S)
    if hi is None:
        return list(base)
    return [x for x in base
            if isinstance(x.get("t"), (int, float)) and x["t"] < hi]


def _post_drop(series: list[tuple[float, float]],
               drop_at: float) -> list[tuple[float, float]]:
    return [(t, v) for t, v in series if t >= float(drop_at) and t >= WARMUP_S]


#: Per-tick bulk attribution by arm: ACIQ's tree maps bulk onto its own
#: class; the baselines run ONE aggregate leaf. From fix 18 that leaf is
#: sampled under `unknown` (BASELINE_HANDLE_MAP); artefacts from before it
#: stored the same aggregate under `software_update`, so the fallback is
#: legacy-labelled and the report says so wherever it is used.
def bulk_tick_series(run: dict) -> tuple[str, list[tuple[float, float]]] | None:
    """(carrying class, per-tick series) for the bulk label, or None.

    CARRYING, not assigned-first. A no-enforcement run steers the whole link
    into the router's `unknown`/legacy aggregate while the assigned
    `bulk_download` sheet reads an empty queue; picking assigned-first
    reported a solid "0.00 Mbps post-drop bulk" for exactly those runs --
    an empty sheet mistaken for an unmeasured transfer. Same carrying rules
    as the starvation/minima tables (`label_carrying`: assigned + fallback
    classes, winner by highest mean). The key is returned so every consumer
    prints WHICH sheet the number came from."""
    base = analysis_samples(run)
    rep = (run.get("wl") or {}).get("bulk") or {"kind": "bulk"}
    cand = label_carrying(base, "bulk", rep)
    if cand is None:
        return None
    _mean, key, series = cand
    return key, series


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


def bind_time(run: dict, tol: float = BIND_TOLERANCE) -> float | None:
    """Seconds from the drop to the first tick the APPLIED tree has been set
    at/below tol * post-drop capacity.

    replaces the old 1.25x `adaptation_time`: boundaries that loose counted
    a tree at 26 Mbps as "adapted" on a 21.8 Mbps link. Baselines have no
    such tick under a drop (that is not a metric failure, it is the
    finding)."""
    cfg, drop_at = run["cfg"], run["cfg"].get("drop_at_s")
    post = cfg.get("drop_mbps")
    if drop_at is None or post is None or not post:
        return None
    thresh = float(post) * float(tol)
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
    (ma, _sda, cia), (mb, _sdb, cib) = mean_ci(a), mean_ci(b)
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
    if v is None or base in (None,):
        return NOT_AVAILABLE, ""
    if not (math.isfinite(v) and math.isfinite(base)):
        return NOT_AVAILABLE, ""
    a, b = float(v), float(base)
    if b == 0:
        if a == 0:
            return "0.0x", "same"
        if lower_is_better:
            arrow = "worse" if a > 0 else "better"
        else:
            arrow = "better" if a > 0 else "worse"
        shown = abs(a) / 1e-18
        return (">20x" if shown >= 20 else f"{shown:.1f}x", arrow)
    ratio = a / abs(b)
    if ratio == 0:
        if lower_is_better:
            return ("100.0% better", "better")
        return ("-100.0%", "worse")
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
                 s5_json: Path | None = None,
                 s6_json: Path | None = None,
                 family_ranges: dict[str, str] | None = None) -> str:
    famspec = DEFAULT_FAMILY_RANGES if family_ranges is None else family_ranges
    runs, skipped, runs_by_family = load_runs_families(runs_root,
                                                       family_ranges)
    scen = scenarios_of(runs) or sorted({k[0] for k in runs_by_family})
    sys_of_run = lambda r: r["cfg"].get("system", "")
    present = sorted({sys_of_run(r) for r in runs})
    arms = [a for a in ARM_ORDER if a in present] + \
           [a for a in present if a not in ARM_ORDER]

    lines: list[str] = []
    add = lines.append

    def run_hash(r: dict) -> str:
        """A run's engine commit, result.json first (the stamped
        RunResult field), config.json as fallback; runs generated before
        round-3 stamping say so by their null hash, never silently."""
        res = r.get("res") if isinstance(r.get("res"), dict) else {}
        h = res.get("commit_hash") or r["cfg"].get("commit_hash")
        return h if h else "no-hash (pre-round-3 artefact)"

    h_top = git_commit_hash()
    add("# Results (generated, no summarised files consulted)")
    add("")
    add(f"Runs root: `{runs_root}` | runs used: {len(runs)} | "
        f"scenarios: {', '.join(scen) or 'none'}")
    add("")
    if h_top:
        add(f"Generated from engine commit `{h_top}`. Every section header "
            "below stamps the commit(s) of the runs it renders; a frozen "
            "final band may ONLY claim PASS/FAIL if every run in it "
            "carries this same hash — any mismatch is flagged per band "
            "and per scenario, never pooled silently.")
        add("")
    if skipped:
        add(f"Skipped {len(skipped)} incomplete-only directory names: "
            + ", ".join(f"`{s}`" for s in skipped))
        add("")
    if skipped:
        from collections import Counter
        reasons = Counter()
        for sx in skipped:
            if "outside tracked seed families" in sx or "outside matrix seed family" in sx:
                reasons["outside tracked seed families"] += 1
            elif "special-condition" in sx:
                reasons["special-condition run"] += 1
            elif "missing config" in sx or "missing workloads" in sx:
                reasons["missing required files"] += 1
            elif "bad seed" in sx:
                reasons["bad seed"] += 1
            else:
                reasons["other"] += 1
        add("**Skipped directories (summary):**")
        for k,v in sorted(reasons.items()):
            add(f"- {k}: {v}")
        add(f"- total skipped: {len(skipped)}")
        add("")

    # ---- scenario x arm table (labelled PRE-FIX / POST-FIX blocks) ---------
    add("## Delay and throughput, every scenario x arm (mean +/- 95% CI over "
        "seeds; t(9)=2.262 for n=10)")
    add("")
    add("Every block below carries an explicit band label, derived from the "
        "seed family recorded at load time: `POST-FIX` (seeds 200-209, the "
        "controller after the redesign commits), `PRE-FIX` (legacy seeds "
        "0-9/42-51), `DEV` and `EVAL` (the task-2 protocol: parameters were "
        "fixed on the DEV band seeds 400-409 BEFORE the EVAL band seeds "
        "500-509 was run ONCE; nothing between them was tuned). A reader "
        "never inherits a number of unknown provenance: the label sits "
        "directly above the table. The comparison sections further down use "
        "the primary band only.")
    add("")
    add("Bulk has TWO columns on purpose (TASK 5a): `sender` is what the "
        "generator pushed, `receiver/sink` is what the receiver's sink log "
        "totalled -- the delivered number, used for any bulk claim. The "
        "post-drop column stays on the TREE counters and is named so: the "
        "three are different instruments and are never blended.")
    add("")

    def fam_seed_label(famname: str) -> str:
        if famspec and famname in famspec:
            return f"{famname}, seeds {famspec[famname]}"
        return famname

    def emit_arm_table(add, sc: str, runlist: list[dict]) -> None:
        add(row_md(["arm", "n", "call p95 ms", "call jitter ms",
                    "call loss %", "game p95 ms", "bulk Mbps (sender)",
                    "bulk Mbps (receiver/sink)",
                    "post-drop bulk (tree)",
                    "jain (workload-rate Jain)", "jain (demand-normalized)"]))
        add(row_md(["---"] * 11))
        for arm in arms:
            grp = per_arm(sc, arm, runlist)
            if not grp:
                continue
            calls = [call_metrics(r["wl"]) for r in grp]
            games = [game_p95(r["wl"]) for r in grp]
            bulks = [bulk_mbps(r["wl"]) for r in grp]
            # TASK 5(a): the receiver's own delivered figure, from the label's
            # sink log. Reported NEXT TO the sender number, never blended:
            # "what was pushed" and "what arrived" are different facts.
            sinks = [sink_mbps(r, "bulk")[0] for r in grp]
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
                fmt(sinks),
                fmt(pd_bulks) if any(v is not None for v in pd_bulks) \
                    else "(no drop scenario)",
                fmt(jains, 3),
                fmt(djains, 3),
            ]))

    famspec_out = famspec if famspec is not None else DEFAULT_FAMILY_RANGES
    for sc in scen:
        primary_fam = next((rank for rank in FAMILY_RANK
                            if any(k[0] == sc and k[2] == rank
                                   for k in runs_by_family)), None)
        lab = famspec_out.get(primary_fam, primary_fam)
        add(f"### {sc} (primary band: {primary_fam} ({lab}))")
        add("")
        hset_sc = sorted({run_hash(r) for r in runs
                          if r["cfg"].get("scenario") == sc})
        stamps = ", ".join(f"`{h}`" for h in hset_sc)
        suffix = (" — MIXED COMMITS: not one frozen run; do not mix these "
                  "numbers into a single claim."
                  if len(hset_sc) > 1 else
                  (" — matches this report's engine commit."
                   if hset_sc == [h_top] and h_top else
                   " — provenance only (pre-round-3 artefact or an older "
                   "engine): shows nothing about the current engine."))
        add(f"- commit provenance: {stamps}{suffix}")
        add("")
        emit_arm_table(add, sc, runs)
        add("")
        if sc == "s3_tv_and_gaming":
            emit_s3_per_tv(add, [r for r in runs
                                 if r["cfg"].get("scenario") == sc])
            add("")
        if sc in ("s1_iso_during_call", "s2_wan_drop",
                  "s4_capacity_recovery"):
            emit_call_obs(add, [r for r in runs
                                if r["cfg"].get("scenario") == sc])
            add("")
        for rank in FAMILY_RANK:
            if rank == primary_fam:
                continue
            sec = [r for k, v in runs_by_family.items()
                   if k[0] == sc and s6fam_matches(k[2], rank)
                   for r in v]
            if sec:
                add(f"### {sc} ({fam_seed_label(rank)})")
                add("")
                hset_sec = sorted({run_hash(r) for r in sec})
                stamps_sec = ", ".join(f"`{h}`" for h in hset_sec)
                suffix_sec = (" — MIXED COMMITS: not one frozen run."
                              if len(hset_sec) > 1 else "")
                add(f"- commit provenance: {stamps_sec}{suffix_sec}"
                    + ("" if h_top else " (engine hash unknown)"))
                add("")
                emit_arm_table(add, sc, sec)
                add("")
                if sc == "s3_tv_and_gaming":
                    emit_s3_per_tv(add, sec)
                    add("")
                if sc in ("s1_iso_during_call", "s2_wan_drop",
                          "s4_capacity_recovery"):
                    emit_call_obs(add, sec)
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
                        if a95 else NOT_AVAILABLE,
                        dbk,
                        ci_overlap(via_int(base_bulk), via_int(bulks))
                        if abk else NOT_AVAILABLE]))
            bulk_label = "post-drop bulk Mbps" if sc_has_drop \
                else "bulk Mbps"
            # The direction is the ARROW the delta itself returns, not a
            # "-" prefix: a "57.0x" factor cell is a loss when the arrow
            # says "worse", and the "-" heuristic silently missed that --
            # which is how a CAKE-static latency win in S1 could fade out
            # of the honest column.
            lost = [(name, shown) for name, shown, arrow in
                    (("call p95", d95, a95), (bulk_label, dbk, abk))
                    if arrow == "worse"]
            if lost:
                worse_rows.append(row_md(
                    [sc, ARM_LABELS.get(arm, arm),
                     " and ".join(f"{name} {shown}" for name, shown
                                  in lost)]))
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

    # ---- where CAKE-static wins (the specific rival) ---------------------
    add("## Where CAKE-static wins")
    add("")
    add("The honest column above lists every rival; this one isolates the "
        "set-and-forget rival that matters for the design claim. A CAKE "
        "win on a metric is stated here verbatim; nothing is re-derived "
        "and nothing is argued away. CI overlap of the underlying seed "
        "samples is in the table above (`CI overlap?` column).")
    add("")
    add(row_md(["scenario", "metric where CAKE-static beats ACIQ",
                "see column in the ACIQ-vs-every table"]))
    add(row_md(["---"] * 3))
    cake_rows = [r for r in worse_rows if "CAKE-static" in r]
    (lines.extend(cake_rows) if cake_rows else add("(none in these runs)"))
    add("")

    # ---- adaptation + accuracy ------------------------------------------
    add("## ACIQ adaptation and capacity accuracy (from the same runs above)")
    add("")
    add(row_md(["scenario", "n", "bind: drop -> first applied "
                               "<=1.05x post-drop (s)",
                "bind: drop -> first applied <=1.25x post-drop (s)",
                "final estimate",
                "configured end link", "estimate error %"]))
    add(row_md(["---"] * 7))
    for sc in scen:
        grp = per_arm(sc, "aciq", runs)
        if not grp:
            continue
        ads = [bind_time(r, tol=1.05) for r in grp]
        ads25 = [bind_time(r, tol=1.25) for r in grp]
        ests, links, errs = [], [], []
        for r in grp:
            res = r["res"] or {}
            est, end = res.get("estimator_mbps"), res.get("link_end_mbps")
            if est is not None and end:
                ests.append(float(est))
                links.append(float(end))
                errs.append(abs(float(end) - float(est)) / float(end) * 100)
        adds = [float(a) for a in ads if a is not None]
        adds25 = [float(a) for a in ads25 if a is not None]
        if adds:
            mean_ads = f"{statistics.mean(adds):.2f} (n={len(adds)})"
        elif len(grp) and all(r["cfg"].get("mode") == "static" for r in grp):
            mean_ads = NOT_AVAILABLE + " (static/baseline)"
        elif grp:
            mean_ads = ("no post-drop applied tree at/below "
                        "1.05x post-drop link in any seed")
        else:
            mean_ads = NOT_AVAILABLE
        if adds25:
            mean_ads25 = f"{statistics.mean(adds25):.2f} (n={len(adds25)})"
        elif len(grp) and all(r["cfg"].get("mode") == "static" for r in grp):
            mean_ads25 = NOT_AVAILABLE + " (static/baseline)"
        elif grp:
            mean_ads25 = ("no post-drop applied tree at/below "
                          "1.25x post-drop link in any seed")
        else:
            mean_ads25 = NOT_AVAILABLE
        if ests:
            acc = "; ".join(
                f"{e:.2f}/{l:.1f} ({er:.1f}% off)" for e, l, er in
                zip(ests[:3], links[:3], errs[:3], strict=True))
            acc = (f"mean abs {statistics.mean(errs):.1f}% "
                   f"(seed0: {acc.split('; ')[0]})")
        else:
            acc = NOT_AVAILABLE + " (no result.json)"
        add(row_md([sc, str(len(grp)), mean_ads, mean_ads25,
                    fmt(ests) if ests else NOT_AVAILABLE,
                    fmt(links, 1) if links else NOT_AVAILABLE, acc]))

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
    else:
        # CPU context (declared, round3-params.md): compare the two
        # ADAPTIVE engines directly, per shared scenario. The round-2 live
        # band showed a ~3x CPU fraction step; the report records the
        # measured ratio and the direction, but the EXPLANATION must come
        # from the artifacts (profiles, decision/policy logs), never be
        # asserted in prose here.
        cpu_by: dict[str, dict[str, float]] = {}
        for a_ in ("aciq", "b1_cake_auto"):
            for sc_ in scen:
                grp_ = per_arm(sc_, a_, runs)
                cf_ = [r["res"]["resources"].get("cpu_mean_frac")
                       for r in grp_ if (r["res"] or {}).get("resources")]
                cf_ = [c for c in cf_ if c is not None]
                if cf_:
                    cpu_by.setdefault(a_, {})[sc_] = statistics.fmean(cf_)
        if "aciq" in cpu_by and "b1_cake_auto" in cpu_by:
            common = [sc_ for sc_ in cpu_by["aciq"]
                      if sc_ in cpu_by["b1_cake_auto"]]
            ratios = [cpu_by["b1_cake_auto"][sc_] / cpu_by["aciq"][sc_]
                      for sc_ in common if cpu_by["aciq"][sc_] > 0]
            if ratios:
                per_sc = ", ".join(
                    f"{sc_} {ratio:.2f}x" for sc_, ratio
                    in zip(common, ratios, strict=True))
                add(f"- CPU context (adaptive vs adaptive): CAKE-adaptive "
                    f"runs at {statistics.fmean(ratios):.2f}x the ACIQ CPU "
                    f"fraction on the shared scenario(s): {per_sc}. The "
                    "cause must be read from the artifacts (CPU profile, "
                    "decision cadence), not assumed.")
    add("")

    # ---- fairness detail -------------------------------------------------
    add("## Fairness detail (workload-rate Jain; per-class minima over "
        "ASSIGNED classes only, same scope for every mode)")
    add("")
    add(row_md(["scenario", "arm", "n", "jain mean +/- CI",
                "demand-jain mean +/- CI", "flows used",
                "min over time (per label, via carrying class)"]))
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
            mins: list[str] = []
            for r in grp:
                if not r["samples"]:
                    continue
                # Per LABEL (TASK 5b): the class the router's data says
                # actually carried the label, not the class the policy map
                # claims. POST-FIX S1's bulk rode `unknown` while its
                # assigned class read 0 -- a per-assigned-class min of 0
                # described the empty queue, not the download.
                for label, rep in sorted((r["wl"] or {}).items()):
                    if not isinstance(rep, dict):
                        continue
                    cand = label_carrying(label_window(r, label),
                                          label, rep)
                    if cand is None:
                        continue
                    _m, via, series = cand
                    v = minimum_over_time(series)
                    if v is not None:
                        suffix = "" if via == (class_of_label(label, rep) or "") \
                            else f" via {via}"
                        mins.append(f"{label}{suffix}={v:.3g}")
            add(row_md([sc, ARM_LABELS.get(arm, arm), str(len(grp)),
                        fmt(jains, 3), fmt(djains, 3),
                        fmt([float(x) for x in nf], 1),
                        "; ".join(mins[:6]) if mins else
                        (NOT_AVAILABLE + " (no assigned-class series in this"
                         " arm's samples)")]))
    add("")
    add("Starvation (TASK 5b, fixed basis): per LABEL, over the class the "
        "data says carried the traffic (assigned class, or the router's "
        "`unknown`/legacy aggregate when the label's traffic rode there -- "
        "chosen by highest mean, and the carrying class is named). A label "
        "starved in tick t if its per-tick goodput fell below 20% of its "
        "REGIME median -- in a drop scenario the median is the POST-DROP "
        "regime's own median, so the shaped link rate can never masquerade "
        "as starvation; without a drop it is the whole window's. The cell "
        "lists the starved timestamps counted over seeds. With no series at "
        "all the cell prints NOT AVAILABLE, never an empty claim.")
    add("")
    add(row_md(["scenario", "arm", "starved ticks per label (via carrying class)"]))
    add(row_md(["---"] * 3))
    st_any = False
    row_cache: list[str] = []
    for sc in scen:
        for arm in arms:
            grp = per_arm(sc, arm, runs)
            if not grp or not any(r["samples"] for r in grp):
                continue
            cells = []
            counted: dict[str, list[int]] = {}
            first_ts: dict[str, float] = {}
            n_series = 0            # seeds where the carrying series exists
            for r in grp:
                for label, rep in sorted((r["wl"] or {}).items()):
                    if not isinstance(rep, dict):
                        continue
                    cand = label_carrying(label_window(r, label), label, rep)
                    if cand is None:
                        continue
                    n_series += 1
                    _m, via, series = cand
                    thr = starvation_threshold(
                        series, r["cfg"].get("drop_at_s"))
                    ts = starved_ticks(series, thr)
                    key = f"{label} via {via}"
                    if ts:
                        counted.setdefault(key, []).append(len(ts))
                        first_ts.setdefault(key, ts[0])
            for key in sorted(counted):
                st_any = True
                cells.append(f"{key}: {sum(counted[key])} ticks over "
                             f"{len(counted[key])} seed(s), "
                             f"first t={first_ts[key]:.1f}")
            if not cells:
                # A computed negative is a RESULT, not missing data: say so
                # with the evidence count, and reserve NOT AVAILABLE for the
                # case where there is no series to judge at all.
                if n_series:
                    cells = [f"no starving tick in {n_series} seed x label "
                             "series (regime-aware threshold, declared "
                             "window)"]
                else:
                    cells = [NOT_AVAILABLE + " (no carrying-class series in "
                             "this arm's samples)"]
            row_cache.append(row_md([sc, ARM_LABELS.get(arm, arm),
                                     "; ".join(cells[:8])]))
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
    add("Further declared exclusions (TASK 5b): (1) ticks at or beyond the "
        "label generator's own measured lifetime (`elapsed_s`, capped by the "
        "scenario duration) -- a verdict about a label after its traffic "
        "stopped describes nothing about the label; (2) ticks whose link "
        "counters went BACKWARDS -- a qdisc del/re-add resets every counter "
        "on the device, so that tick's per-class goodput is a reset "
        "artefact, not a delivery gap. Stars and minima are computed over "
        "what remains; nothing is excluded silently.")
    add("")

    # ---- S6: the intent scenario (TASK 4) ---------------------------------
    # Protocol split (ours, task3-params): the older charts pooled two S6
    # protocol generations into one n=20 cell. Each generation now renders
    # its own block, with its name in the header, and the
    # before / during / after window table sits beside the grant/revert
    # evidence instead of an aggregate that mixes both lives of the intent.
    s6_groups: dict[str, list[dict]] = {}
    for k, v in runs_by_family.items():
        if k[0] != "s6_intent_expire":
            continue
        label = ("current protocol: 60s run, intent at t=10, TTL 20s"
                 if k[2] == "POST-FIX"
                 else k[2].replace("POST-FIX ", "").strip("()"))
        s6_groups.setdefault(label, []).extend(v)
    if s6_groups:
        add("## S6 intent scenario (real API intent, TTL expiry "
            "inside the run, auto-revert)")
        add("")
        add("One intent is requested at the run's declared --intent-at on "
            "the operator's real surface (IntentService, the exact "
            "upstream-declared code path the HTTP handler calls: POST "
            "/intent, target device, weight 0.5). Both endpoints of the "
            "intent's life are measured: held while live, auto-reverted at "
            "expiry (LeaseBook's implicit sweep plus the per-tick "
            "sync_lease), and the recovery window after expiry. The two S6 "
            "protocol generations are SEPARATE (legacy: 40s run, intent at "
            "t~1s, TTL 15s; current: 60s run, intent at t=10s, TTL 20s) -- "
            "no pooling, and with n=10 per arm every CI is a real t-table "
            "interval. Receiver evidence is the per-second sink sampler; "
            "the floors line is a FLOOR line, not a preference claim: on a "
            "healthy link a reserve must not starve the other classes, and "
            "the reserved device must actually receive bytes. The s6 "
            "summary file is quoted when present; the table never infers "
            "what the verifier measured.")
        add("")
        if s6_json and Path(s6_json).exists():
            try:
                s6sum = json.loads(Path(s6_json).read_text())
                add(f"- verifier verdict (tools/verify_s6.py, via "
                    f"`{s6_json}`): "
                    f"`{json.dumps({k: v for k, v in s6sum.items()})}`")
            except json.JSONDecodeError as e:
                add(f"- s6 summary unreadable: {e}")
        else:
            add(f"- s6 summary: {NOT_AVAILABLE} "
                "(no `data/experiments/s6/s6_summary.json`; the live "
                "script writes it after the verifier runs)")
        add("")
        for proto_label, grp in s6_groups.items():
            add(f"### S6 protocol: {proto_label} (n={len(grp)} "
                f"across {len({x['cfg'].get('system') for x in grp})} arms)")
            add("")
            # arm metrics for THIS protocol only (t-table CIs at n=10)
            emit_arm_table(add, "s6_intent_expire", grp)
            add("")
            add("#### Intent life (grant / auto-revert / floors) — same "
                "protocol generation")
            add("")
            add(row_md(
                ["arm",
                 "intent (verdict from result.json)",
                 "auto-revert (lease_active evidence, ticks)",
                 "receiver inst in window: game min / bulk min (floors)",
                 "declared"]))
            add(row_md(["---"] * 5))
            for arm in arms:
                fgrp = [x for x in grp if x["cfg"].get("system") == arm]
                if not fgrp:
                    add(row_md([ARM_LABELS.get(arm, arm),
                                "NOT AVAILABLE (no s6 run in this protocol)",
                                "-", "-", "declared intent-incapable"]))
                    continue
                def _collapse(cells: list[str]) -> str:
                    if len(set(cells)) == 1:
                        return f"{cells[0]} (n={len(cells)} seeds)"
                    return "; ".join(cells)
                granted_c: list[str] = []
                revert_c: list[str] = []
                floor_c: list[str] = []
                for r in fgrp:
                    res = r.get("res") if isinstance(r.get("res"), dict) else {}
                    intent = res.get("intent") or {}
                    s = r["samples"]
                    fired = intent.get("fired_at_run_t_s")
                    held = intent.get("in_effect_s")
                    ttl = r["cfg"].get("intent_ttl_s") or 20.0
                    if res.get("system") != "aciq":
                        gran = ("declared: no intent surface"
                                if intent.get("supported") is False
                                else NOT_AVAILABLE + " (no declaration)")
                        granted_c.append(gran)
                        revert_c.append("-")
                        floor_c.append("-")
                        continue
                    note = intent.get("note") or ""
                    if fired is None or not isinstance(fired, (int, float)):
                        granted_c.append(NOT_AVAILABLE + " (" + note[:50] + ")")
                        revert_c.append("-")
                        floor_c.append("-")
                        continue
                    if "GRANTED" not in note:
                        granted_c.append(f"NOT granted at t={fired:.1f}s "
                                         f"({note[:60]})")
                        revert_c.append("-")
                        floor_c.append("-")
                        continue
                    granted_c.append(f"granted t={fired:.1f}s, in-effect "
                                     f"{held if held is not None else 0:.0f}s "
                                     f"(TTL {ttl:.0f}s)")
                    inside = sorted(x["t"] for x in s
                                    if x.get("lease_active") is True
                                    and fired <= x["t"] <= fired + ttl)
                    after = sorted(x["t"] for x in s
                                   if x.get("lease_active") is True
                                   and x["t"] > fired + ttl + 2.5)
                    if inside and not after:
                        revert_c.append(
                            f"ok: last active t={inside[-1]:.0f}s, clear after "
                            f"{fired + ttl:.0f}s")
                    elif inside and after:
                        revert_c.append(f"FAILED: still active at t={after[0]:.0f}s")
                    else:
                        revert_c.append(NOT_AVAILABLE
                                        + " (lease never observed active)")
                    c_game, _bg = sink_inst_series(r, "game")
                    c_bulk, _bb = sink_inst_series(r, "bulk")

                    def _in(sr, lo, hi):
                        return [v for t, v in sr if lo <= t <= hi]

                    gvals = _in(c_game, fired, fired + ttl)
                    bvals = _in(c_bulk, fired, fired + ttl)
                    pre_bulk = _in(c_bulk, 0.0, fired)
                    med = statistics.median(pre_bulk) if pre_bulk else 0.0
                    if gvals and bvals:
                        bulk_ok = (med <= 0) or (min(bvals) >= 0.1 * med)
                        floor_c.append(
                            f"game {min(gvals):.2f} Mbps "
                            f"(>0: {'PASS' if min(gvals) > 0 else 'FAIL'}); "
                            f"bulk {min(bvals):.2f} Mbps (>=10% of pre-median "
                            f"{med:.2f}: {'PASS' if bulk_ok else 'FAIL'})")
                    else:
                        floor_c.append(NOT_AVAILABLE
                                       + " (no per-second sink sampler data in "
                                       "the window)")
                add(row_md([ARM_LABELS.get(arm, arm),
                            _collapse(granted_c) if granted_c else "-",
                            _collapse(revert_c) if revert_c else "-",
                            _collapse(floor_c) if floor_c else "-",
                            "ACIQ: intent surface" if arm == "aciq" else
                            "declared intent-incapable"]))
            add("")
            emit_s6_windows(add, grp)
            s6_verdict_prose(add, grp)
        add("")
        add("- the two protocols are never pooled: every cell above is "
            f"computed inside one generation ({len(s6_groups)} generation(s) "
            "on disk).")
        add("")

    # ---- S2b / round-3 generalization band --------------------------------
    if any(r["cfg"].get("scenario", "").startswith(("s2b_", "s7_"))
           or r["cfg"].get("scenario") in FLAT_SCENARIOS for r in runs):
        add("## Step/demand generalization band (evaluation-only; "
            "docs/evidence/s2b-params.md + docs/evidence/round3-params.md, "
            "declared BEFORE these runs)")
        add("")
        add("The shipped controller runs unchanged on capacity changes it "
            "was never tuned on: two down-step magnitudes, a 5x up-step, "
            "and a continuous 20 s ramp -- plus the round-3 DEV shapes "
            "(s7_* up/down steps and ramps, s3_stress) and the two "
            "queue-discipline-only arms (CAKE-conservative / "
            "CAKE-adaptive). Seeds 800-809 configured per scenario (the "
            "DEV band, seed names in each run dir). CAKE-static is "
            "applied once at launch and never re-applied: that is its "
            "declared semantics, and this band exists to surface the "
            "consequences. Definitions: bind = first tick at which the "
            "applied tree sits within 10% of the link's truth and stays "
            "there (down-moves only; up-moves print `n/a (up-step)` and "
            "are judged by the utilization column: applied/truth and "
            "receiver delivered/truth over the final third); tracking "
            "error = mean |applied - truth| over the ramp window; "
            "estimate error = same over the final third. Where ACIQ "
            "fails, the row says so.")
        add("")
        h_band = git_commit_hash()
        if h_band:
            add(f"Engine commit at generation time: `{h_band}` — a run "
                "whose result carries a different commit_hash is "
                "SUPERSEDED, listed under 'commit provenance' below and "
                "never pooled into a numeric cell with a newer commit.")
        add("")
        emit_s2b(add, runs)
        emit_sink_starvation(add, runs, arms)
        add("")

    # ---- commit provenance --------------------------------------------------
    add("## Commit provenance (declared; every run's engine hash)")
    add("")
    add(row_md(["scenario", "arm", "n runs", "commit_hash", "verdict"]))
    add(row_md(["---"] * 5))
    hash_groups: dict[tuple[str, str, str], int] = {}
    for r in runs:
        key = (r["cfg"].get("scenario", "?"), r["cfg"].get("system", "?"),
               run_hash(r))
        hash_groups[key] = hash_groups.get(key, 0) + 1
    for (sc, sysname, h), n in sorted(hash_groups.items()):
        if h_top and h == h_top:
            verdict = "current: trusted for a frozen final band claim"
        elif h == "no-hash (pre-round-3 artefact)":
            verdict = "pre-round-3 run: no hash on record; provenance unknown"
        else:
            verdict = ("SUPERSEDED: different engine commit than this "
                       "report; keep its numbers visibly apart (never "
                       "mixed into one claim with a current run)")
        add(row_md([sc, ARM_LABELS.get(sysname, sysname), str(n),
                    f"`{h}`", verdict]))
    add("")
    add("- pooling rule (binding): a numeric cell in this report may mix "
        "runs across seeds of ONE band, but never across commit hashes; "
        "the section headers above flag mixed-commit scenarios so a mixed "
        "cell is traceable to its provenance lines.")
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
        if "strict_heldout" in ev and not ev.get("fatal"):
            sho = ev["strict_heldout"]
            # THE headline is the BROAD held-out number (docs/evidence/
            # task4-params.md: the taxonomy the plan actually acts on);
            # the narrow figure sits beside it with its error mode, never
            # instead of it. Two numbers total: both held-out, both printed
            # in this paragraph, so no reader has to hunt through dumps.
            bho = ev.get("broad_heldout") or {}
            add(f"- HEADLINE (fresh held-out, tuple-split by flow, no "
                f"threshold tuned on this half): broad-taxonomy accuracy "
                f"{bho.get('accuracy_strict') if bho else NOT_AVAILABLE} "
                f"on n={bho.get('n') if bho else NOT_AVAILABLE} "
                f"({bho.get('correct') if bho else NOT_AVAILABLE} correct, "
                f"{bho.get('abstained') if bho else NOT_AVAILABLE} "
                "abstained); narrow-taxonomy accuracy "
                f"{sho.get('accuracy_strict')} on the same rows "
                f"({sho.get('correct')} correct, {sho.get('abstained')} "
                "abstained). The FULL-corpus figures below are context, "
                "not the verdict: the held-out half is the one the "
                "classifier never shaped.")
        for key in ("broad_heldout", "broad_accept_abstain_heldout",
                    "calibration_heldout", "confidently_wrong_heldout",
                    "strict", "strict_fixed", "strict_heldout",
                    "accept_abstain", "accept_abstain_heldout",
                    "confusion", "confusion_heldout",
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
                    counts_txt = json.dumps(counts.get("per_label", {}))
                    add(f"- per-class floor {CORPUS_MIN_PER_CLASS}: met "
                        f"(counts: `{counts_txt}`)")
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
        # TASK 5: time-to-safe-state. The injection moment is the run's
        # first committed tick after arm; safe is the rollback replay of
        # last-good through the kernel. Both come from samples.jsonl
        # policy_outcome stamps, never from the controller's own summary.
        timing: list[str] = []
        for d in sorted(runs_root.iterdir()):
            if not d.is_dir():
                continue
            cfg_p = d / "config.json"
            try:
                _cfg = json.loads(cfg_p.read_text()) if cfg_p.exists() else {}
            except (OSError, json.JSONDecodeError):
                _cfg = {}  # interrupted run (0-byte config): skip, don't crash
            if not _cfg.get("inject_fail_apply"):
                continue
            arm_t = roll_t = None
            try:
                for line in (d / "samples.jsonl").read_text(
                        errors="replace").splitlines():
                    if not line.strip():
                        continue
                    s = json.loads(line)
                    po = s.get("policy_outcome") or {}
                    t = s.get("t")
                    if po.get("rolled_back") and roll_t is None:
                        roll_t = t
                    elif po.get("committed") and po.get("ok") and \
                            arm_t is None:
                        arm_t = t
            except (OSError, json.JSONDecodeError) as e:
                timing.append(f"{d.name}: unreadable ({e})")
                continue
            if arm_t is None or roll_t is None:
                timing.append(f"{d.name}: {NOT_AVAILABLE} "
                              "(no armed-apply/rollback stamps)")
            else:
                timing.append(f"{d.name}: "
                              f"{(roll_t - arm_t):.3f} s (arm->rollback)")
        if timing:
            add("")
            add("**Time to safe state (S5c injected failed apply; "
                "rollback = the kernel back on last-good):**")
            for t in timing:
                add(f"- {t}")
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
    ap.add_argument("--s6-json", type=Path,
                    default=ROOT / "data/experiments/s6/s6_summary.json")
    ap.add_argument("--legacy-seeds", default="0-9,42-51",
                    help="Seed ranges considered PRE-FIX (informational)")
    ap.add_argument("--postfix-seeds", default="200-209",
                    help="Seed ranges considered POST-FIX (informational)")
    ap.add_argument("--dev-seeds", default=None,
                    help="Optional DEV band seed ranges (e.g. '400-409'); "
                         "adds a DEV family so the report can show the band "
                         "parameters were fixed on, visibly apart")
    ap.add_argument("--eval-seeds", default=None,
                    help="Optional EVAL band seed ranges (e.g. '500-509'); "
                         "the band that is run ONCE, never tuned against")
    a = ap.parse_args(argv)
    famspec = dict(DEFAULT_FAMILY_RANGES)
    for name, spec in (("DEV", a.dev_seeds), ("EVAL", a.eval_seeds)):
        if spec:
            famspec[name] = spec
    build_report(a.runs_root, a.out, a.eval_json, a.s5_json, a.s6_json,
                 famspec)
    print(f"report written: {a.out} (+html)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
