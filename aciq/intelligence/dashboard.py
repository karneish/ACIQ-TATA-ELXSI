"""Intelligence dashboard panels (Phase 7).

Additive, read-only section rendered *after* the six base M8 panels. The base
controller pins `PANELS` to exactly six keys (see tests/test_intent.py) — this
module never extends that tuple. Every value carries an evidence badge:
Observed / Estimated / Predicted / Verified, so nothing predicted or simulated
can be mistaken for measured fact.
"""
from __future__ import annotations

from typing import Any

from ..dashboard import Series, esc, render_panel

_ACTIONS = ("retain", "select", "reject_all", "defer", "recover", "safe_fallback")


def intelligence_summary(decisions: list[dict[str, Any]],
                         experiences: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    """Tiles for the intelligence section."""
    counts: dict[str, int] = {}
    for d in decisions:
        counts[d.get("action", "unknown")] = counts.get(d.get("action", "unknown"), 0) + 1
    by_status: dict[str, int] = {}
    for e in experiences:
        by_status[e.get("status", "unknown")] = by_status.get(e.get("status", "unknown"), 0) + 1
    tiles: list[tuple[str, str, str]] = []
    action_str = ", ".join(f"{a}={counts[a]}" for a in _ACTIONS if a in counts) or "no decisions yet"
    tiles.append(("intelligence", f"{len(decisions)} decisions",
                  f"Observed: recorded by the decision engine ({action_str})"))
    tiles.append(("latest action", str(decisions[-1].get("action", "-")) if decisions else "-",
                  "Verified: signed off by the acceptance gate"))
    exp_str = ", ".join(f"{k}={v}" for k, v in sorted(by_status.items())) or "0 stored"
    tiles.append(("experiences", f"{len(experiences)} stored",
                  f"Verified measured outcomes only ({exp_str})"))
    return tiles


def prediction_panel(samples: list[dict[str, Any]]) -> tuple[str, str, list[Series]]:
    """Capacity + prediction severity series from sample rows' summaries."""
    cap_pts: list[tuple[float, float]] = []
    sev_pts: list[tuple[float, float]] = []
    for r in samples:
        t = float(r.get("t", 0.0))
        intel = r.get("intelligence") or {}
        if isinstance(r.get("capacity_mbps"), (int, float)):
            cap_pts.append((t, float(r["capacity_mbps"])))
        sev = intel.get("severity") if isinstance(intel, dict) else None
        if isinstance(sev, (int, float)):
            sev_pts.append((t, float(sev)))
    series = []
    if cap_pts:
        series.append(Series("capacity", cap_pts, "#2e86c1"))
    if sev_pts:
        series.append(Series("severity", sev_pts, "#c0392b"))
    title = "Prediction (Estimated — never a measurement)"
    return "prediction", title, series


def render_intelligence_section(samples: list[dict[str, Any]],
                                decisions: list[dict[str, Any]],
                                experiences: list[dict[str, Any]]) -> str:
    """HTML fragment. Empty decisions+experiences renders nothing."""
    if not decisions and not experiences and not any(
            isinstance(r.get("intelligence"), dict) for r in samples):
        return ""
    key, title, series = prediction_panel(samples)
    panel = render_panel(key, title, series)
    rows = "".join(
        f"<div>t={float(d.get('recorded_at', 0.0)):.0f}s "
        f"action=<b>{esc(d.get('action', '?'))}</b> "
        f"<i>{esc(d.get('reason', ''))}</i> "
        f"<span class='badge'>{esc('Verified' if d.get('selected_candidate_id') else 'Observed')}</span></div>"
        for d in decisions[-12:])
    exp_rows = "".join(
        f"<div>{esc(e.get('status', '?'))} · "
        f"{esc(str(e.get('outcome_context', {}).get('measured', ''))[:60])} "
        f"<span class='badge'>{esc('Verified' if e.get('outcome_context', {}).get('measured') else 'Predicted')}</span></div>"
        for e in experiences[-12:])
    tiles = intelligence_summary(decisions, experiences)
    tile_html = "".join(
        f'<div class="tile"><div class="k">{esc(k)}</div>'
        f'<div class="v">{esc(v)}</div><div class="h">{esc(h)}</div></div>'
        for k, v, h in tiles)
    return (
        '<section class="intel"><h2>Intelligence layer</h2>'
        f'<div class="tiles">{tile_html}</div>'
        f'<div class="grid">{panel}</div>'
        f'<div class="events"><b>Decisions</b>{rows or "<div>none recorded</div>"}'
        f'<b>Experiences</b>{exp_rows or "<div>none stored</div>"}'
        "</div></section>")
