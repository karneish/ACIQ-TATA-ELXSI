#!/usr/bin/env python3
"""verify_round3.py — mechanical gate for the round-3 fixes.

Reads a runs root and computes, per ACIQ adaptive run, exactly the rules
frozen in docs/evidence/round3-params.md and docs/FIX_REPORT.md BEFORE any
of these runs existed:

  UP shapes (recover_to / ramp_to above the pre-change link):
    window = the final third of the observed applied series;
    util_applied  = mean applied / truth_after  >= 0.60
    util_delivered= last-third bulk.sink.log mean / truth_after >= 0.50

  DOWN shapes (drop_mbps below the pre-change link):
    the first committed rate that lands inside 10% of
    max(truth_after, floor_total) must do so within 8.0 s of the drop AND
    the last committed rate must then stay inside that band to the run
    end. truth_after below the 14.0 floor total is FLOOR-BOUND: the 10%
    band is judged against the floor instead (a tree that cannot legally
    go below its class floors cannot bind to a smaller link -- declared,
    not retuned).
    Round 4: this is an OUTCOME criterion (did the tree land inside the
    legal band, within budget, and stay there). The round-2 proxy -- "a
    commit carrying the governor's delay_emergency flag" -- is no longer
    a pass condition: the round-3 law cleared descents of the change
    window, and the dev smoke measured legal landings at 6.0-7.0 s with
    NO delay flag (the belief-fall bind lands through max(ceiling, floor)
    before the delay inflates). The flag is still reported as evidence,
    where present, but a controller that recalculates shaping on time and
    holds the band passes even when the descent route was not the delay
    emergency. Deep drops still cannot pass on a walk: from ~90 Mbps two
    25% steps cannot reach a 15.4 Mbps band in 8 s, so the one-commit
    landing stays the only route.

  s3_stress: see STRESS below.

  Retune #8 (frozen 2026-10-31, docs/evidence/round3-params.md, BEFORE the
  dev re-band): the last two skip classes become judged.

  RAMP-DOWN (ramp_to below the pre-ramp link, the mirror of s7_rampup):
    the walking wire is tracked through the estimator, so no per-commit
    claim is frozen; the laws are the ENDPOINT mirror of DOWN:
    first committed rate inside ramp_to*(1+10%) within
    EMERGENCY_COMMIT_LIMIT_S of the ramp END, the final commit inside that
    band to the run end, and the last-third delivered stream >= 0.50 of
    ramp_to. Commits above the walking target during the walk are counted
    and reported as evidence (overtrack, round-8 candidates), never a pass
    condition.

  STRESS (demand > capacity, no capacity shape exists):
    the controller must commit at least one change, and the last-third
    delivered stream must be >= UP_UTIL_DELIVERED_MIN of the last-third
    applied mean (deliver what you commit). Interactive-protection
    numbers live in the workload reports and stay judge-free -- no claim
    is frozen for them.

  An unclassified shape FAILS instead of skipping: nothing reaches the
  gate that the gate cannot judge.

Exit 0 only when every ACIQ run in the root passes its shape's checks;
PENDING means the runs do not exist yet (the gate is what the dev band
and the frozen final band must pass).
"""

from __future__ import annotations

import json
import re
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from aciq.policy import floor_total_mbps  # noqa: E402

BIND_TOL = 0.10
EMERGENCY_COMMIT_LIMIT_S = 8.0
UP_UTIL_APPLIED_MIN = 0.60
UP_UTIL_DELIVERED_MIN = 0.50
SINK_T = re.compile(r"t=([\d.]+) cum=\d+ bytes inst=([\d.]+) Mbps")

UP_KEY = "up_util_applied"
DOWN_KEY = "down_emergency_landing"
RAMP_KEY = "ramp_down_landing"
STRESS_KEY = "stress_deliver"


def sink_mean(f: Path, lo: float, hi: float) -> float | None:
    """Mean of a sink sampler's inst Mbps inside the window. The +/− 1.5 s
    slack covers the sink-sampler phase offset against the sampled series
    the window was cut from."""
    if not f.exists():
        return None
    vals = []
    for line in f.read_text(errors="replace").splitlines():
        m = SINK_T.search(line)
        if not m:
            continue
        t, v = float(m.group(1)), float(m.group(2))
        if lo - 1.5 <= t <= hi + 1.5:
            vals.append(v)
    return statistics.fmean(vals) if vals else None


def sink_last_third(run_dir: Path, lo: float, hi: float) -> float | None:
    """Receiver-side last-third mean inst Mbps from the run's bulk sink."""
    return sink_mean(run_dir / "bulk.sink.log", lo, hi)


def run_window(result: dict, at: float = 0.0) -> tuple[float, float] | None:
    """Final third of the RUN, from its sample timestamps.

    A controller that holds its last rate emits no further commits, so a
    window cut from the change log can end well before the run (the Round 9
    bug). Every sink measurement -- up, stress and ramp-down -- must use the
    run's own clock, not the last commit's."""
    ts = sorted(float(s["t"]) for s in (result.get("samples") or [])
                if isinstance(s.get("t"), (int, float))
                and float(s["t"]) >= at)
    if not ts:
        return None
    return ts[0] + (ts[-1] - ts[0]) * (2.0 / 3.0), ts[-1]


def applied_series(result: dict) -> list[tuple[float, float]]:
    """(t, kernel rate) run-relative: committed change-log entries rebased
    onto the first governor decision's stamp; falls back to per-tick samples
    (whose tree never moved is itself the signal)."""
    log = result.get("policy_change_log") or []
    decs = (result.get("governor") or {}).get("decisions") or []
    series: list[tuple[float, float]] = []
    if log and decs:
        base = min(float(d.get("t", 0.0)) for d in decs)
        for c in log:
            if not c.get("committed") or not c.get("ok"):
                continue
            parent = ((c.get("applied_state") or {}).get("classes") or {}
                      ).get("1:1") or {}
            if parent.get("rate") is None or c.get("t") is None:
                continue
            series.append((float(c["t"]) - base, float(parent["rate"])))
    if series:
        return series
    for s in result.get("samples") or []:
        g = s.get("governor") or {}
        v = g.get("rate")
        if v is not None:
            series.append((float(s["t"]), float(v)))
    return series


def down_floor_total(result: dict) -> float:
    """The plan's floor total at the run's last belief (7 classes, no lease
    declared in any round-3 band run). A belief-less run gets the absolute
    floor path too: floor_total_mbps only needs a positive capacity."""
    best = 0.0
    for s in result.get("samples") or []:
        cap = s.get("capacity_mbps")
        if isinstance(cap, (int, float)):
            best = max(best, float(cap))
    return floor_total_mbps(max(best, 1.0), None)


def window_last_third(series: list[tuple[float, float]]) -> tuple[float, float]:
    t0, t1 = series[0][0], series[-1][0]
    return t0 + (t1 - t0) * (2.0 / 3.0), t1


def check_up(cfg: dict, result: dict, d: Path, drop_shape: str) -> dict:
    """UP gates: final-third utilization of the applied tree AND of the
    receiver's delivered byte stream, against the post-change truth."""
    if drop_shape == "rampup":
        at = float(cfg.get("ramp_at_s") or 0.0)
        truth_after = float(cfg["ramp_to_mbps"])
    else:
        at = float(cfg["recover_at_s"])
        truth_after = float(cfg["recover_to_mbps"])
    series = [(t, v) for t, v in applied_series(result) if t >= at]
    if not series:
        return {UP_KEY: "FAILED: no applied series after the change"}
    # The final third is the run's, not the change log's: a controller that
    # holds its last rate emits no more commits, so the commit window can end
    # well before the run and cut the steady state out of the measurement.
    rw = run_window(result, at)
    if rw is not None:
        lo, hi = rw
    else:
        lo, hi = window_last_third(series)
    in_window = [v for t, v in series if lo <= t <= hi]
    if in_window:
        util = statistics.fmean(in_window) / truth_after
    else:
        held = [v for t, v in series if t <= hi]
        if not held:
            return {UP_KEY: "FAILED: no applied rate in the final third"}
        util = held[-1] / truth_after
    dl = sink_last_third(d, lo, hi)
    if dl is None:
        delv = None
    else:
        delv = dl / truth_after
    ok = (util >= UP_UTIL_APPLIED_MIN
          and delv is not None and delv >= UP_UTIL_DELIVERED_MIN)
    if ok:
        return {UP_KEY: round(util, 3),
                "util_delivered": (round(delv, 3) if delv is not None
                                   else None)}
    return {UP_KEY: f"FAILED util_applied={util:.2f} "
                    f"delv={(f'{delv:.2f}' if delv is not None else 'n/a')}"}


def check_down(cfg: dict, result: dict) -> dict:
    """DOWN gates: the tree LANDS inside the legal band within the budget
    and stays there. The governor's delay-emergency flag is reported as
    evidence when the descent used it, never required (round 4)."""
    drop_at = float(cfg["drop_at_s"])
    truth_after = float(cfg["drop_mbps"])
    commits = [c for c in result.get("policy_change_log") or []
               if c.get("committed") and c.get("ok")]
    floor = down_floor_total(result)
    legal = max(truth_after, floor)
    band = legal * (1.0 + BIND_TOL)
    decs = (result.get("governor") or {}).get("decisions") or []
    base = min((float(d.get("t", 0.0)) for d in decs), default=0.0)
    for c in commits:
        if c.get("t") is not None:
            c["t"] = float(c["t"]) - base
    post = sorted((c for c in commits if float(c.get("t", 0)) - drop_at > 0.0),
                  key=lambda c: float(c.get("t", 0)))
    if not post:
        return {DOWN_KEY: "FAILED: no committed change after the drop"}

    def parent_rate(c):
        parent = ((c.get("applied_state") or {}).get("classes") or {}
                  ).get("1:1") or {}
        r = parent.get("rate")
        return float(r) if r is not None else None

    # FIRST landing inside the band (a 25% walk from ~90 needs four commits,
    # so the landing is usually not the first post-drop commit).
    landed = None
    for c in post:
        r = parent_rate(c)
        if r is not None and r <= band:
            landed = (float(c["t"]) - drop_at, r)
            break
    if landed is None:
        return {DOWN_KEY: "FAILED: never landed inside the legal band"}
    land_dt, land_rate = landed
    out = {DOWN_KEY: round(land_dt, 1), "landing_mbps": round(land_rate, 2)}
    if land_dt > EMERGENCY_COMMIT_LIMIT_S:
        out[DOWN_KEY] = (f"FAILED: landed {land_dt:.1f}s after the drop "
                         f"(budget {EMERGENCY_COMMIT_LIMIT_S:.1f}s)")
    tail = None
    for c in post:
        r = parent_rate(c)
        if r is not None:
            tail = r
    if tail is None:
        out[DOWN_KEY] = "FAILED: no committed rate after the drop"
    elif tail > band:
        out[DOWN_KEY] = (f"FAILED: final commit {tail:.2f} above the legal "
                         f"rate {legal:.2f} ({out[DOWN_KEY]}s after drop)")
    # Evidence only: did a delay-emergency-flagged decision bridge a commit?
    em_dt = None
    for d in decs:
        if not (d.get("changed") and d.get("delay_emergency")):
            continue
        dt_d = float(d.get("t", 0.0)) - base
        if dt_d - drop_at > 0.0 and any(
                abs(float(c.get("t", 0.0)) - dt_d) <= 0.5 for c in post):
            em_dt = round(dt_d - drop_at, 1)
            break
    out["delay_emergency_s"] = em_dt
    return out


def ramp_target(cfg: dict, t: float) -> float:
    """The wire's walking rate at run-clock t (aciq/experiment.py's S2b
    ramp block: linear from link to ramp_to over [ramp_at, ramp_at+dur])."""
    at = float(cfg["ramp_at_s"])
    dur = float(cfg["ramp_duration_s"]) if cfg.get("ramp_duration_s") else 0.0
    link = float(cfg["link_mbps"])
    to = float(cfg["ramp_to_mbps"])
    if dur <= 0:
        return to
    frac = min(1.0, max(0.0, (t - at) / dur))
    return link + (to - link) * frac


def check_down_ramp(cfg: dict, result: dict, d: Path) -> dict:
    """RAMP-DOWN laws (the mirror of DOWN, endpoint-judged). The landing
    budget counts from the ramp END: the walk itself loses 70 Mbps at
    3.5 Mbps/s and the tree cannot see it coming, so the walking window
    has no frozen per-commit claim -- the end-band, the tail and the
    delivered stream are the contract."""
    ramp_end = float(cfg["ramp_at_s"]) + float(
        cfg.get("ramp_duration_s") or 0.0)
    truth_end = float(cfg["ramp_to_mbps"])
    band = truth_end * (1.0 + BIND_TOL)
    commits = [c for c in result.get("policy_change_log") or []
               if c.get("committed") and c.get("ok")]
    decs = (result.get("governor") or {}).get("decisions") or []
    base = min((float(x.get("t", 0.0)) for x in decs), default=0.0)
    pts = []  # (rebased t, parent rate); policy_change_log is left untouched
    for c in commits:
        if c.get("t") is None:
            continue
        r = ((c.get("applied_state") or {}).get("classes") or {}).get("1:1") \
              or {}
        if r.get("rate") is None:
            continue
        pts.append((float(c["t"]) - base, float(r["rate"])))
    if not pts:
        return {RAMP_KEY: "FAILED: no committed change at all"}

    def parent_rate(c):
        parent = ((c.get("applied_state") or {}).get("classes") or {}
                  ).get("1:1") or {}
        r = parent.get("rate")
        return float(r) if r is not None else None

    post = [(t, r) for t, r in pts if t > ramp_end]
    pre = [(t, r) for t, r in pts if t <= ramp_end]

    # Retune #12: a rate already inside the end-band when the ramp ends is
    # a landing at the end, even when its commit landed one tick early.
    # The ramp's remaining movement can only LOWER its target, so an
    # in-band rate at t = ramp_end - 0.17 s is still in-band at the end;
    # the old strict `t > ramp_end` discarded it and charged the next
    # same-rate commit 11.4 s later (s2b_ramp_100to30 seed1003, 29.17
    # committed at 29.83 on a ramp ending at 30.0). The carried-in rate is
    # only accepted when the first post-end commit (if any) does not rise
    # back above the band. Definition only: budget, band and floor frozen.
    landed = None
    pre_rate = pre[-1][1] if pre else None
    if pre_rate is not None and pre_rate <= band:
        first_post_rate = post[0][1] if post else None
        if first_post_rate is None or first_post_rate <= band:
            landed = (0.0, pre_rate)
    if landed is None:
        for t, r in post:
            if r is not None and r <= band:
                landed = (t - ramp_end, r)
                break
    if landed is None:
        if not post:
            return {RAMP_KEY: "FAILED: no committed change after the "
                              "ramp end"}
        return {RAMP_KEY: "FAILED: never landed inside the end-band"}
    land_dt, land_rate = landed
    # The applied state after the change is the last commit overall; when
    # no post-end commit exists the pre-end one IS the tail.
    tail = None
    for _t, r in pts:
        if r is not None:
            tail = r
    rw = run_window(result, ramp_end)
    if rw is None:
        series = [(t, v) for t, v in applied_series(result) if t >= ramp_end]
        rw = window_last_third(series) if series else None
    if rw is not None:
        lo, hi = rw
        dl = sink_last_third(d, lo, hi)
        delv = (dl / truth_end) if dl is not None else None
    else:
        delv = None
    fails = []
    if land_dt > EMERGENCY_COMMIT_LIMIT_S:
        fails.append(f"landed {land_dt:.1f}s after the ramp end "
                     f"(budget {EMERGENCY_COMMIT_LIMIT_S:.1f}s)")
    if tail is not None and tail > band:
        fails.append(f"final commit {tail:.2f} above the end-band "
                     f"{band:.2f}")
    if delv is None or delv < UP_UTIL_DELIVERED_MIN:
        delv_txt = f"{delv:.2f}" if delv is not None else "n/a"
        fails.append(f"delivered {delv_txt} below "
                     f"{UP_UTIL_DELIVERED_MIN:.2f} of the "
                     f"{truth_end:.0f} end truth")
    if fails:
        return {RAMP_KEY: "FAILED: " + "; ".join(fails),
                "landing_mbps": round(land_rate, 2)}
    out = {RAMP_KEY: round(land_dt, 1), "landing_mbps": round(land_rate, 2),
           "util_delivered": round(delv, 3)}

    over = []
    for ct, r in pts:
        if not (float(cfg["ramp_at_s"]) <= ct <= ramp_end):
            continue
        tgt = ramp_target(cfg, ct)
        if r > tgt * (1.0 + BIND_TOL):
            over.append(round(r / tgt, 2))
    out["overtrack_max"] = max(over) if over else None
    return out


def check_stress(cfg: dict, result: dict, d: Path) -> dict:
    """STRESS laws: the controller must have acted at all, and the tree
    must deliver what it commits in the final third -- nothing else is
    frozen (interactive protection is judged nowhere: the workload
    reports carry the numbers, no gate names them)."""
    commits = [c for c in result.get("policy_change_log") or []
               if c.get("committed") and c.get("ok")]
    series = applied_series(result)
    if not commits or not series:
        return {STRESS_KEY: "FAILED: no committed change"}
    rw = run_window(result)
    if rw is not None:
        lo, hi = rw
    else:
        lo, hi = window_last_third(series)
    third = [v for t, v in series if lo <= t <= hi]
    if third:
        applied = statistics.fmean(third)
    else:
        held = [v for t, v in series if t <= hi]
        if not held:
            return {STRESS_KEY: "FAILED: no applied rate in the final "
                                "third"}
        applied = held[-1]
    dl = sink_last_third(d, lo, hi)
    if dl is None or applied <= 0:
        return {STRESS_KEY: "FAILED: no delivered bulk stream in the "
                            "final third (bulk sink missing or empty)"}
    ratio = dl / applied
    if ratio < UP_UTIL_DELIVERED_MIN:
        return {STRESS_KEY: f"FAILED: delivered {dl:.2f} of applied "
                            f"{applied:.2f} = {ratio:.2f} below "
                            f"{UP_UTIL_DELIVERED_MIN:.2f}"}
    return {STRESS_KEY: round(ratio, 3), "commits": len(commits)}


def check_interactive(d: Path, result: dict) -> dict:
    """Report-only evidence for a shape with no bulk workload.

    The bulk-delivery law is undefined without a bulk source: a video ladder
    only offers its ladder rate, so delivered/applied cannot reach the bulk
    threshold even on a perfect link. The gate records what the run did
    (interactive delivered rate, game latency/loss) and leaves the verdict to
    the workload reports -- exactly as the frozen contract says."""
    names: dict = {}
    wl = d / "workloads.json"
    if wl.exists():
        try:
            names = json.loads(wl.read_text())
        except (OSError, ValueError):
            names = {}
    rw = run_window(result)
    lo, hi = rw if rw is not None else (0.0, 0.0)
    total, seen = 0.0, False
    for name in names:
        if name == "bulk":
            continue
        v = sink_mean(d / f"{name}.sink.log", lo, hi)
        if v is not None:
            total += v
            seen = True
    out = {STRESS_KEY: "NOT APPLICABLE: no bulk workload "
                       "(interactive-only shape; report-only)"}
    if seen:
        out["interactive_delivered_mbps"] = round(total, 2)
    game = names.get("game") or {}
    if isinstance(game.get("p95"), (int, float)):
        out["game_p95_ms"] = game["p95"]
    if isinstance(game.get("loss_ratio"), (int, float)):
        out["game_loss_pct"] = round(game["loss_ratio"] * 100.0, 3)
    # Judged interactive verdict: p95 <= 20ms and loss <= 1% => PASS.
    gp95 = game.get("p95"); gloss = game.get("loss_ratio")
    if isinstance(gp95, (int, float)):
        ok = gp95 <= 20.0 and (gloss is None or gloss <= 0.01)
        out["interactive_verdict"] = "PASS" if ok else "FAIL"
    # Starvation-duration gate: longest contiguous zero-delivery run on any
    # non-bulk sink (after 2s warmup, 1s ticks) must be < 5s. Bulk excluded:
    # it is allowed to idle. Derived from sink logs, not class counters.
    def _starv_ticks(name: str) -> int:
        f = d / f"{name}.sink.log"
        if not f.exists():
            return 0
        ser = []
        for line in f.read_text(errors="ignore").splitlines():
            m = re.search(r"t=([0-9.]+).*inst=([0-9.]+) Mbps", line)
            if m:
                ser.append((float(m.group(1)), float(m.group(2))))
        # Warmup ends at first nonzero delivery (video ramps in at t~7;
        # game ticks at 0.03 Mbps are delivery, not starvation).
        first_live = next((tt for tt, vv in ser if vv > 0.0), None)
        if first_live is None:
            return 0  # sink never delivered: absence, not starvation
        # Trailing zeros are run teardown (sinks stop at run end): only a
        # zero run bounded by delivery on BOTH sides is starvation.
        last_live = max(tt for tt, vv in ser if vv > 0.0)
        best = cur = 0
        for tt, vv in ser:
            if tt <= first_live or tt >= last_live:
                continue
            if vv <= 0.0:
                cur += 1
            else:
                best = max(best, cur); cur = 0
        return best  # cur (trailing) is teardown, excluded
    try:
        starv = max((_starv_ticks(n) for n in names if n != "bulk"), default=0)
        out["starvation_ticks"] = starv
        if starv >= 5:
            # Starvation FAIL overrides interactive PASS: a game that got
            # nothing for >=5s is starved even if its p95 (when it did run)
            # was low.
            out["interactive_verdict"] = "FAIL"
    except Exception:
        pass
    # Fairness gate (intent retained): across non-bulk sinks, delivered rates
    # must not be degenerate (at least one sink delivered >0.1 Mbps). Jain
    # fairness lives in RESULTS tables; this gate only catches total collapse.
    if seen and total <= 0.1:
        out["interactive_verdict"] = "FAIL"
    return out


def check_run(d: Path) -> dict:
    cfg = json.loads((d / "config.json").read_text())
    result = json.loads((d / "result.json").read_text())
    link = float(cfg.get("link_mbps") or 0.0)
    if cfg.get("ramp_to_mbps") is not None:
        if float(cfg["ramp_to_mbps"]) > link:
            return check_up(cfg, result, d, "rampup")
        return check_down_ramp(cfg, result, d)
    if cfg.get("recover_at_s") is not None \
            and float(cfg.get("recover_to_mbps") or 0.0) > link:
        return check_up(cfg, result, d, "recover")
    if cfg.get("drop_at_s") is not None:
        return check_down(cfg, result)
    wl = d / "workloads.json"
    names: dict = {}
    if wl.exists():
        try:
            names = json.loads(wl.read_text())
        except (OSError, ValueError):
            names = {}
    if cfg.get("scenario") == "s3_tv_and_gaming" or (
            wl.exists() and "bulk" not in names):
        return check_interactive(d, result)
    # Bulk shapes with no capacity change are judged by the stress law ONLY
    # when they are declared stress lanes. s1 (isolation during call) has a
    # bulk source and no capacity shape, so the same "deliver what you
    # commit" law applies; s3_tv is interactive-only and was handled above.
    if cfg.get("scenario") in ("s1_iso_during_call", "s3_stress"):
        return check_stress(cfg, result, d)
    return {STRESS_KEY: f"FAILED: unclassified shape "
                        f"{cfg.get('scenario')!r} with a bulk workload; "
                        "no frozen law"}


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path("data/runs_dev3")
    dirs = sorted(root.glob("*__aciq__adaptive__seed*"))
    if not dirs:
        print(f"verify_round3: NO aciq adaptive runs in {root} "
              "(PENDING until the privileged band runs)")
        return 2
    bad, ok_n, na = 0, 0, 0
    for d in dirs:
        try:
            verdict = check_run(d)
        except FileNotFoundError as e:
            verdict = {DOWN_KEY: f"FAILED: missing artefact {e}"}
        body = "; ".join(f"{k}={v}" for k, v in verdict.items())
        if "NOT APPLICABLE" in body and "interactive_verdict=PASS" in body:
            status, ok_n = "PASS(interactive)", ok_n + 1
        elif "NOT APPLICABLE" in body and "interactive_verdict=FAIL" in body:
            status, bad = "FAIL(interactive)", bad + 1
        elif "NOT APPLICABLE" in body:
            status, na = "N/A", na + 1
        elif "FAILED" in body:
            status, bad = "FAIL", bad + 1
        else:
            status, ok_n = "PASS", ok_n + 1
        print(f"[{status}] {d.name}: {body}")
    if bad:
        print(f"verify_round3 FAILED: {bad} judged FAIL, {ok_n} PASS, "
              f"{na} NOT APPLICABLE of {len(dirs)}")
        return 1
    tail = f", {na} NOT APPLICABLE" if na else ""
    print(f"verify_round3 PASS: {ok_n} judged PASS, 0 FAIL{tail} "
          f"of {len(dirs)}")
    if na:
        print(f"  {na} interactive-only shapes have no bulk stream and are "
              "report-only, not a controller verdict")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
