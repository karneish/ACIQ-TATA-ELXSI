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

from aciq.fairness import (assigned_classes, class_of_label, flow_rates,  # noqa: E402
                           jain, label_carrying, mean_over_time,
                           minimum_over_time, per_class_series,
                           run_demand_fairness, run_fairness, starved_ticks)

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
        # S6 runs on their own 300-309 family: they are neither a PRE-FIX
        # repeat nor a POST-FIX rerun of an existing family; their purpose
        # (intent grant/revert) does not depend on the fix timeline.
        if sc == "s6_intent_expire":
            keep_any = set(s for s, _ in members)
            runs_by_family[(sc, sysname, "POST-FIX")] = [r for _, r in members]
            dropped.extend([])
            continue
        seeds_all = sorted(s for s, _ in members)
        post_seeds = sorted([s for s in seeds_all if 200 <= s <= 209])
        pre_seeds = sorted([s for s in seeds_all if (0 <= s <= 9) or (42 <= s <= 51)])
        for famname, fseeds in [("POST-FIX", post_seeds), ("PRE-FIX", pre_seeds)]:
            if not fseeds:
                continue
            fset = set(fseeds)
            kept = []
            for s, r in members:
                if s in fset:
                    kept.append(r)
            if kept:
                runs_by_family[(sc, sysname, famname)] = kept
        keep_any = set(post_seeds) | set(pre_seeds)
        for s, r in members:
            if s not in keep_any:
                dropped.append(f"{r['dir']} (outside tracked seed families: "
                               f"not in POST-FIX 200-209 or PRE-FIX 0-9/42-51)")
    skipped.extend(sorted(dropped))
    # Prefer POST-FIX as primary
    runs = []
    for k in runs_by_family:
        if k[2] == "POST-FIX":
            runs.extend(runs_by_family[k])
    if not runs:
        for k in runs_by_family:
            if k[2] == "PRE-FIX":
                runs.extend(runs_by_family[k])
    if not runs:
        runs = runs_all
    # attach family info
    for r in runs:
        try:
            s = int(r["cfg"].get("seed", 0))
            if r["cfg"].get("scenario") == "s6_intent_expire":
                r["_seed_family"] = "POST-FIX"
            elif 200 <= s <= 209:
                r["_seed_family"] = "POST-FIX"
            elif 0 <= s <= 9 or 42 <= s <= 51:
                r["_seed_family"] = "PRE-FIX"
            else:
                r["_seed_family"] = "OTHER"
        except Exception:
            r["_seed_family"] = "UNKNOWN"
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
    """(t, capacity the tree was set to) from the run's own samples.

    The parent rate recorded per tick is what the mode actually installed;
    for baselines it never budges, which is the point of showing it.
    """
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
                 s6_json: Path | None = None) -> str:
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

    # ---- scenario x arm table (POST-FIX primary) -------------------------------------------
    add("## Delay and throughput, every scenario x arm (mean +/- 95% CI over "
        "seeds; t(9)=2.262 for n=10)")
    add("")
    add("Bulk has TWO columns on purpose (TASK 5a): `sender` is what the "
        "generator pushed, `receiver/sink` is what the receiver's sink log "
        "totalled -- the delivered number, used for any bulk claim. The "
        "post-drop column stays on the TREE counters and is named so: the "
        "three are different instruments and are never blended.")
    add("")
    for sc in scen:
        add(f"### {sc}")
        add("")
        add(row_md(["arm", "n", "call p95 ms", "call jitter ms",
                    "call loss %", "game p95 ms", "bulk Mbps (sender)",
                    "bulk Mbps (receiver/sink)",
                    "post-drop bulk (tree)",
                    "jain (workload-rate Jain)", "jain (demand-normalized)"]))
        add(row_md(["---"] * 11))
        for arm in arms:
            grp = per_arm(sc, arm, runs)
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
                zip(ests[:3], links[:3], errs[:3]))
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
    add(f"Further declared exclusions (TASK 5b): (1) ticks at or beyond the "
        f"label generator's own measured lifetime (`elapsed_s`, capped by the "
        f"scenario duration) -- a verdict about a label after its traffic "
        f"stopped describes nothing about the label; (2) ticks whose link "
        f"counters went BACKWARDS -- a qdisc del/re-add resets every counter "
        f"on the device, so that tick's per-class goodput is a reset "
        f"artefact, not a delivery gap. Stars and minima are computed over "
        f"what remains; nothing is excluded silently.")
    add("")

    # ---- S6: the intent scenario (TASK 4) ---------------------------------
    if any(r["cfg"].get("scenario") == "s6_intent_expire" for r in runs):
        add("## S6 intent scenario (TASK 4: real API intent, TTL expiry "
            "inside the run, auto-revert)")
        add("")
        add("One intent is requested at t~1s on the operator's real surface "
            "(IntentService, the exact upstream-declared code path the HTTP "
            "handler calls: POST /intent, target device, weight 0.5, TTL "
            "15s). The 40s scenario makes the TTL expire INSIDE the run, so "
            "both endpoints of the intent's life are measured: held while "
            "live, auto-reverted at expiry (LeaseBook's implicit sweep plus "
            "the per-tick sync_lease). Receiver evidence is the per-second "
            "sink sampler; the floors line is a FLOOR line, not a preference "
            "claim: on a healthy link a reserve must not starve the other "
            "classes, and the reserved device must actually receive bytes. "
            "The s6 summary file is quoted when present; the table never "
            "infers what the verifier measured.")
        add("")
        add(row_md(
            ["arm",
             "intent (verdict from result.json)",
             "auto-revert (lease_active evidence, ticks)",
             "receiver inst in window: game min / bulk min (floors)",
             "declared"]))
        add(row_md(["---"] * 5))
        if s6_json and Path(s6_json).exists():
            try:
                s6sum = json.loads(Path(s6_json).read_text())
                add(f"- verifier verdict (tools/verify_s6.py, via "
                    f"`{s6_json}`): "
                    f"`{json.dumps({k: v for k, v in s6sum.items()})}`")
            except json.JSONDecodeError as e:
                add(f"- s6 summary unreadable: {e}")
        elif any(r["cfg"].get("scenario") == "s6_intent_expire"
                 for r in runs):
            add(f"- s6 summary: {NOT_AVAILABLE} "
                "(no `data/experiments/s6/s6_summary.json`; the live "
                "script writes it after the verifier runs)")
        add("")
        for arm in arms:
            grp = [x for x in runs if x["cfg"].get("scenario")
                   == "s6_intent_expire"
                   and x["cfg"].get("system") == arm]
            if not grp:
                add(row_md([ARM_LABELS.get(arm, arm),
                            "NOT AVAILABLE (no s6 run dir)", "-", "-",
                            "declared intent-incapable"]))
                continue
            def _collapse(cells: list[str]) -> str:
                if len(set(cells)) == 1:
                    return f"{cells[0]} (n={len(cells)} seeds)"
                return "; ".join(cells)
            granted_c: list[str] = []
            revert_c: list[str] = []
            floor_c: list[str] = []
            for r in grp:
                res = r.get("res") if isinstance(r.get("res"), dict) else {}
                intent = res.get("intent") or {}
                s = r["samples"]
                fired = intent.get("fired_at_run_t_s")
                held = intent.get("in_effect_s")
                ttl = r["cfg"].get("intent_ttl_s") or 15.0
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
            add(f"- HEADLINE (fresh held-out, tuple-split by flow, no "
                f"threshold tuned on this half): strict accuracy "
                f"{sho.get('accuracy_strict')} on n={sho.get('n')} "
                f"({sho.get('correct')} correct, {sho.get('abstained')} "
                f"abstained). The FULL-corpus figures below are context, "
                "not the verdict: the held-out half is the one the "
                "classifier never shaped.")
        for key in ("strict", "strict_fixed", "strict_heldout",
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
    ap.add_argument("--s6-json", type=Path,
                    default=ROOT / "data/experiments/s6/s6_summary.json")
    ap.add_argument("--legacy-seeds", default="0-9,42-51",
                    help="Seed ranges considered PRE-FIX (informational)")
    ap.add_argument("--postfix-seeds", default="200-209",
                    help="Seed ranges considered POST-FIX (informational)")
    a = ap.parse_args(argv)
    build_report(a.runs_root, a.out, a.eval_json, a.s5_json, a.s6_json)
    print(f"report written: {a.out} (+html)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
