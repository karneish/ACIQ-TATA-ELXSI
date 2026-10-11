"""M8 -- a read-only dashboard with inline SVG charts.

Six panels, per `docs/architecture.md`: latency, jitter, loss, throughput, queue
depth, fairness.

## Strictly read-only

The requirement is not "does not currently write" but "**can never** write". So
this module:

* imports nothing from `harness`, `txn`, `tc` or `bridge` -- the wiring is
  checked by a test that greps the module's imports, because an import is the
  only way a later edit could reach a `tc` call from here;
* renders a snapshot passed in. It cannot reach the kernel because it has no
  reference to anything that can.

The one thing it writes is a file, via `write_snapshot` -- to wherever the caller
says. That is a file, not a policy.

## No JavaScript

Inline SVG and one `<meta>` refresh. A dashboard that needs a CDN is a dashboard
that stops working on an air-gapped host, which is exactly where this project is
demonstrated. Trade-off accepted: charts update by page reload, not by a
websocket.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

#: Panel height in user units. SVG viewBox units, not pixels; the page scales.
PANEL_W = 420
PANEL_H = 140
PAD_L = 46
PAD_R = 10
PAD_T = 10
PAD_B = 22

#: The six panels the architecture requires, in order.
PANELS = (
    ("latency", "Latency (ms)"),
    ("jitter", "Jitter (ms)"),
    ("loss", "Loss ratio"),
    ("throughput", "Throughput (Mbps)"),
    ("queue_depth", "Queue depth (bytes)"),
    ("fairness", "Fairness (Jain, 1.0 = fair)"),
)

_CLASS_COLOURS = {
    "realtime_interactive": "#c0392b",
    "adaptive_video": "#2e86c1",
    "bulk_transfer": "#7f8c8d",
    "leased_flow": "#8e44ad",
    "link": "#2c3e50",
}


def esc(s) -> str:
    return html.escape(str(s), quote=True)


@dataclass
class Series:
    """One named line on a panel."""

    label: str
    points: Sequence[tuple[float, float]] = ()
    colour: str = "#2c3e50"

    @property
    def values(self) -> list[float]:
        return [v for _t, v in self.points]


def _fmt(v: float) -> str:
    if abs(v) >= 100:
        return f"{v:.0f}"
    if abs(v) >= 1:
        return f"{v:.2f}"
    return f"{v:.3f}"


def panels_from_samples(samples: Iterable[dict], classes: Sequence[str] = ()) -> dict:
    """Turn `samples.jsonl` rows into per-panel series.

    Accepts the shape the experiment already writes, so the dashboard reads the
    real artefacts rather than a parallel format that could drift from them.

    Built as a dict of (panel, class) -> list of (t, value), then projected into
    Series at the end. Appending to a Series while discovering the series exists
    is how the first version of this ended up appending to a throwaway object and
    losing the points.
    """
    rows = list(samples)
    names = list(classes) or sorted({k for r in rows for k in (r.get("per_class") or {})})

    #: panel -> class -> [(t, value)]
    acc: dict[str, dict[str, list[tuple[float, float]]]] = {}

    def put(panel: str, label: str, t: float, v) -> None:
        if v is None:
            return
        acc.setdefault(panel, {}).setdefault(label, []).append((t, float(v)))

    #: panel -> metric, straight from the collector's field names.
    per_class_metrics = (
        ("latency", "rtt_p95"),
        ("jitter", "jitter_ms"),
        ("loss", "loss_ratio"),
        ("queue_depth", "backlog_bytes"),
        ("throughput", "goodput_mbps"),
    )

    for r in rows:
        t = float(r.get("t", 0.0))
        pc = r.get("per_class") or {}
        for cls in names:
            m = pc.get(cls) or {}
            for panel, field in per_class_metrics:
                put(panel, cls, t, m.get(field))
        # Fairness is a property of the link, not of a class.
        put("fairness", "fairness", t, r.get("fairness"))

    out: dict[str, list[Series]] = {}
    for panel, by_label in acc.items():
        out[panel] = [Series(label, pts, _CLASS_COLOURS.get(label, "#2c3e50"))
                      for label, pts in by_label.items()]
    return out



# --------------------------------------------------------------------------
# Geometry
# --------------------------------------------------------------------------

def _nice_step(span: float, target: int) -> float:
    """A round tick step (1/2/5 x 10^n) covering `span` in about `target` steps.

    Round steps because an axis labelled 0, 3.37, 6.74, 10.11 is technically
    informative and practically unreadable.
    """
    if span <= 0:
        return 1.0
    raw = span / max(1, target)
    mag = 10 ** int(_floor_log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        if raw <= m * mag:
            return m * mag
    return 10 * mag


def _floor_log10(v: float) -> float:
    import math
    return math.floor(math.log10(v)) if v > 0 else 0


def _ticks(lo: float, hi: float, target: int = 5) -> list[float]:
    """Tick values spanning [lo, hi], inclusive of both ends where possible."""
    if hi <= lo:
        return [lo]
    step = _nice_step(hi - lo, target)
    start = step * (lo / step)
    # Start a step or two below so the axis does not begin at a round number that
    # sits above the real minimum -- which would clip the first data points.
    start -= 2 * step
    out, v = [], start
    while v <= hi + step * 0.5:
        if v >= lo - 1e-12:
            out.append(round(v, 10))
        v += step
    return out


def _bounds(series: Sequence[Series]) -> tuple[float, float, float, float]:
    """-> (t0, t1, v0, v1). Shared by the scale and the ticks so the axis and
    the plot can never disagree about where the data is."""
    xs = [t for s in series for t, _v in s.points]
    ys = [v for s in series for v in s.values]
    if not xs or not ys:
        return 0.0, 1.0, 0.0, 1.0
    t0, t1 = min(xs), max(xs)
    v0, v1 = min(ys), max(ys)
    if t1 <= t0:
        t1 = t0 + 1.0
    if v1 <= v0:
        # A flat line is common. Padding symmetrically would put the axis at
        # -0.5..0.5 and label a *negative* latency, which reads as a measurement
        # rather than as the absence of one. Latency, jitter and loss are not
        # negative, so the floor stays at zero and only the head grows.
        head = 1.0 if v1 == 0 else abs(v1) * 0.1
        v1 = v0 + head
    return t0, t1, v0, v1


# --------------------------------------------------------------------------
# Panel rendering
# --------------------------------------------------------------------------

def render_panel(name: str, title: str, series: Sequence[Series],
                 width: int = PANEL_W, height: int = PANEL_H,
                 events: Sequence[dict] = ()) -> str:
    """One panel: labelled axes on both sides, gridlines, series, event marks.

    The x axis is labelled in seconds because a chart of a run whose main feature
    happens *at a time* is unreadable without one -- and the capacity drop, the
    single most important moment on every one of these charts, had no mark on it.
    """
    t0, t1, lo, hi = _bounds(series)
    # Snap the axis top to the next round tick. Without this the highest tick
    # sits above the data and is clipped away, leaving the top of the panel
    # ungridded -- which reads as a rendering fault rather than as padding.
    # Round the axis top *up* to a tick. Snapping only when the top tick already
    # exceeded the data left the panel's top strip ungridded whenever the tick
    # fell just short of the maximum -- which reads as a rendering fault.
    step = _nice_step(hi - lo, 5)
    if step > 0:
        import math
        top = math.ceil(hi / step - 1e-9) * step
        if top > hi:
            hi = top
    yticks = _ticks(lo, hi, target=5)
    plot_w = width - PAD_L - PAD_R
    plot_h = height - PAD_T - PAD_B

    def X(t: float) -> float:
        return PAD_L + (t - t0) / (t1 - t0) * plot_w

    def Y(v: float) -> float:
        return PAD_T + plot_h - (v - lo) / (hi - lo) * plot_h

    p = [f'<svg class="panel" viewBox="0 0 {width} {height}" width="100%" '
         f'preserveAspectRatio="xMidYMid meet" role="img" '
         f'aria-label="{esc(title)} time series">']

    # Horizontal gridlines + value labels.
    for v in yticks:
        y = Y(v)
        if not (PAD_T - 1 <= y <= PAD_T + plot_h + 1):
            continue
        p.append(f'<line class="grid" x1="{PAD_L}" y1="{y:.1f}" '
                 f'x2="{width - PAD_R}" y2="{y:.1f}"/>')
        p.append(f'<text class="axis" x="{PAD_L - 6}" y="{y + 3.5:.1f}" '
                 f'text-anchor="end">{_fmt(v)}</text>')

    # Vertical gridlines + time labels.
    for t in _ticks(t0, t1, target=5):
        x = X(t)
        if not (PAD_L - 1 <= x <= width - PAD_R + 1):
            continue
        p.append(f'<line class="grid" x1="{x:.1f}" y1="{PAD_T}" '
                 f'x2="{x:.1f}" y2="{PAD_T + plot_h}"/>')
        p.append(f'<text class="axis" x="{x:.1f}" y="{height - 6}" '
                 f'text-anchor="middle">{t:g}s</text>')

    # Event markers -- the drop, a lease change. Without these the charts show
    # a step and no explanation for it.
    for ev in events:
        if not (t0 <= ev["t"] <= t1):
            continue
        x = X(ev["t"])
        p.append(f'<line class="event" x1="{x:.1f}" y1="{PAD_T}" '
                 f'x2="{x:.1f}" y2="{PAD_T + plot_h}">'
                 f'<title>{esc(ev["label"])}</title></line>')
        p.append(f'<text class="evlabel" x="{x + 3:.1f}" y="{PAD_T + 9}">'
                 f'{esc(ev["label"])}</text>')

    flat_zero = all(all(v == 0 for _t, v in s.points)
                    for s in series if s.points)
    if flat_zero and any(s.points for s in series):
        # Latency, jitter and loss are identically zero in every run this project
        # has produced -- the generators do not report per-flow RTT to the
        # collector. Drawing that as a line at zero on a padded axis is worse
        # than drawing nothing: it reads as "measured zero latency".
        p.append(f'<text class="empty" x="{width / 2:.0f}" y="{height / 2 - 6:.0f}" '
                 f'text-anchor="middle">not measured</text>')
        p.append(f'<text class="empty2" x="{width / 2:.0f}" y="{height / 2 + 10:.0f}" '
                 f'text-anchor="middle">every sample reported exactly 0</text>')
        p.append("</svg>")
        return "".join(p)

    if not any(s.points for s in series):
        p.append(f'<text class="empty" x="{width / 2:.0f}" y="{height / 2:.0f}" '
                 f'text-anchor="middle">no data</text>')
        p.append("</svg>")
        return "".join(p)

    for s in series:
        if not s.points:
            continue
        d = " ".join(("M" if i == 0 else "L") + f"{X(t):.1f},{Y(v):.1f}"
                     for i, (t, v) in enumerate(s.points))
        colour = _CLASS_COLOURS.get(s.label, s.colour)
        # <title> gives a native hover tooltip without a line of JavaScript.
        p.append(f'<path class="line" d="{d}" fill="none" stroke="{colour}" '
                 f'stroke-width="1.7" stroke-linejoin="round" '
                 f'stroke-linecap="round">'
                 f'<title>{esc(s.label)}</title></path>')
        # Marker at the end: a flat line still has to show that it drew something.
        lt, lv = s.points[-1]
        p.append(f'<circle cx="{X(lt):.1f}" cy="{Y(lv):.1f}" r="2.6" '
                 f'fill="{colour}"><title>{esc(s.label)} {lv:.4g}</title></circle>')

    p.append("</svg>")
    return "".join(p)


# --------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------

def summary_tiles(rows: Sequence[dict]) -> list[tuple[str, str, str]]:
    """-> [(label, value, hint)]. The first thing a reader wants and the answer
    to "did anything actually happen"."""
    out: list[tuple[str, str, str]] = []
    if not rows:
        return [("samples", "0", "no samples read")]

    span = max(float(r.get("t", 0.0)) for r in rows)
    out.append(("samples", str(len(rows)), f"over {span:.1f}s"))

    good: list[float] = []
    for r in rows:
        pc = r.get("per_class") or {}
        good.append(sum(float(m.get("goodput_mbps") or 0.0) for m in pc.values()))
    if good:
        peak = max(good)
        mean = sum(good) / len(good)
        out.append(("peak throughput", f"{peak:.2f} Mb/s",
                    f"mean {mean:.2f} Mb/s"))

    caps = [float(r.get("capacity_mbps") or 0.0) for r in rows]
    cap = max(caps)
    if cap > 0:
        out.append(("capacity (M2)", f"{cap:.2f} Mb/s",
                    "measured, not configured"))
    else:
        out.append(("capacity (M2)", "not measured",
                    "no saturated sample in this run"))

    changes = 0
    for r in rows:
        changes += int(bool((r.get("verdicts") or {})))
    if changes:
        out.append(("flows steered", str(changes), "ticks with a verdict"))

    cpu = [float(r.get("cpu_fraction") or 0.0) for r in rows]
    if max(cpu) > 0:
        out.append(("cpu overhead", f"{100 * max(cpu):.2f}%", "peak"))

    return out


def detect_events(rows: Sequence[dict], configured: Sequence[dict] = ()) -> list[dict]:
    """Marks worth drawing. Configured events are honoured first; the drop is
    then inferred from where the link rate first falls, so a run that was
    launched without --drop-at still shows what happened."""
    events = [dict(e) for e in configured]
    have = {round(float(e["t"]), 1) for e in events}

    # Infer the drop: the first sample after which throughput never returns to
    # its earlier level. Cheap, and better than no mark at all.
    if not any("drop" in e["label"].lower() for e in events):
        rates = []
        prev_t = prev_b = None
        for r in rows:
            lk = r.get("link") or {}
            t, b = float(r.get("t", 0.0)), lk.get("rx_bytes")
            if prev_b is not None and b is not None and t > prev_t and t > prev_t:
                dt = t - prev_t
                if dt > 0:
                    rates.append((t, (b - prev_b) * 8 / dt / 1e6))
            prev_t, prev_b = t, b
        if len(rates) > 6:
            early = max(v for _t, v in rates[:4])
            for i in range(4, len(rates)):
                if all(v <= early * 0.6 for _t, v in rates[i:]):
                    t, v = rates[i]
                    if round(t, 1) not in have:
                        events.append({"t": t,
                                       "label": f"cap -> {v:.0f} Mb/s"})
                    break
    return sorted(events, key=lambda e: e["t"])


# --------------------------------------------------------------------------
# Page
# --------------------------------------------------------------------------

CSS = """
:root{
  color-scheme:light dark;
  --bg:#f4f6f9; --card:#fff; --ink:#12161c; --muted:#5b6472;
  --line:#e2e6ec; --grid:#eceff3; --accent:#2f6feb; --event:#e0483c;
}
*{box-sizing:border-box}
body{font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;
     background:var(--bg);color:var(--ink);padding:22px 20px 34px}
.wrap{max-width:1500px;margin:0 auto}
header{display:flex;flex-wrap:wrap;align-items:baseline;gap:10px;margin:0 0 4px}
h1{font-size:21px;font-weight:650;margin:0;letter-spacing:-.01em}
.badge{font-size:11px;font-weight:600;color:var(--muted);border:1px solid var(--line);
       border-radius:999px;padding:2px 9px;background:var(--card)}
.sub{color:var(--muted);margin:0 0 18px;font-size:13px}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(158px,1fr));
       gap:10px;margin:0 0 18px}
.tile{background:var(--card);border:1px solid var(--line);border-radius:9px;
      padding:10px 13px}
.tile .k{font-size:11px;text-transform:uppercase;letter-spacing:.05em;
         color:var(--muted)}
.tile .v{font-size:19px;font-weight:640;margin-top:2px;
         font-variant-numeric:tabular-nums}
.tile .h{font-size:11px;color:var(--muted);margin-top:1px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(470px,1fr));gap:14px}
.panel{width:100%;height:auto;display:block;background:var(--card);
       border:1px solid var(--line);border-radius:9px}
.ptitle{font:600 12.5px system-ui;fill:var(--ink)}
.axis{font:10.5px ui-monospace,SFMono-Regular,monospace;fill:var(--muted)}
.empty{font:13px system-ui;fill:var(--muted);font-weight:600}
.empty2{font:11px system-ui;fill:var(--muted);opacity:.75}
.grid{stroke:var(--grid)}
.evlabel{font:600 9.5px system-ui;fill:var(--event)}
.event{stroke:var(--event);stroke-width:1.1;stroke-dasharray:3 3;opacity:.8}
.legend{display:flex;flex-wrap:wrap;gap:16px;margin:16px 0 0;font-size:12.5px;
        color:var(--muted)}
.legend span{display:inline-flex;align-items:center;gap:6px}
.sw{width:12px;height:3px;border-radius:2px;display:inline-block}
.legend b{color:var(--ink);font-weight:600;font-variant-numeric:tabular-nums}
.foot{color:var(--muted);font-size:11.5px;margin-top:14px}
@media (prefers-color-scheme:dark){
  :root{--bg:#0e1116;--card:#171b22;--ink:#e8ecf1;--muted:#98a2b3;
        --line:#252b34;--grid:#21262e;--accent:#5b8dff;--event:#ff6b5e}
}
@media (max-width:520px){
  body{padding:14px 12px 24px}
  .grid{grid-template-columns:1fr}
}
"""


def render_page(panels: dict, subtitle: str = "", refresh_s: int = 0,
                summary: Sequence[tuple[str, str, str]] = (),
                events: Sequence[dict] = ()) -> str:
    """The whole page. `panels` is the dict from `panels_from_samples`."""
    tiles = "".join(
        f'<div class="tile"><div class="k">{esc(k)}</div>'
        f'<div class="v">{esc(v)}</div>'
        f'<div class="h">{esc(h)}</div></div>'
        for k, v, h in summary)

    body = []
    for key, title in PANELS:
        body.append(render_panel(key, title, panels.get(key) or [],
                                 events=events))

    # Legend carries each series' current value, so a reader gets the number
    # without tracing a line to its right-hand edge.
    seen: dict[str, Series] = {}
    for key, _t in PANELS:
        for s in panels.get(key, []):
            if s.points:
                seen.setdefault(s.label, s)
    legend = "".join(
        f'<span><i class="sw" style="background:{_CLASS_COLOURS.get(s.label, s.colour)}">'
        f'</i>{esc(_pretty(s.label))} <b>{_fmt(s.points[-1][1])}</b></span>'
        for s in seen.values())

    meta = (f'<meta http-equiv="refresh" content="{max(1, refresh_s)}">'
            if refresh_s else "")
    live = ('<span class="badge">live</span>' if refresh_s else
            '<span class="badge">snapshot</span>')
    ev = "".join(f'<div>{esc(e["label"])} at t={float(e["t"]):g}s</div>'
                 for e in events)

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">{meta}
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ACIQ dashboard</title><style>{CSS}</style></head>
<body><div class="wrap">
<header><h1>ACIQ dashboard</h1>{live}</header>
<p class="sub">{esc(subtitle)}</p>
<div class="tiles">{tiles}</div>
<div class="grid">{"".join(body)}</div>
<div class="legend">{legend}</div>
<p class="foot">Read-only (M8). Inline SVG, no JavaScript, no external requests.
{" Marked events: " + ev if ev else ""}</p>
</div></body></html>"""


_PRETTY = {
    "realtime_interactive": "interactive",
    "adaptive_video": "video (ABR)",
    "bulk_transfer": "bulk",
    "leased_flow": "leased",
    "fairness": "fairness",
}


def _pretty(label: str) -> str:
    return _PRETTY.get(label, label)


def build_from_samples(rows: Iterable[dict], subtitle: str = "",
                       refresh_s: int = 0,
                       events: Sequence[dict] = ()) -> str:
    rows = list(rows)
    classes = sorted({k for r in rows for k in (r.get("per_class") or {})})
    ev = detect_events(rows, events)
    return render_page(panels_from_samples(rows, classes), subtitle, refresh_s,
                       summary=summary_tiles(rows), events=ev)


def write_snapshot(rows: Iterable[dict], path: Path | str,
                   subtitle: str = "", refresh_s: int = 0,
                   events: Sequence[dict] = ()) -> Path:
    """Render a snapshot to disk. The only write this module performs."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_from_samples(rows, subtitle, refresh_s, events))
    return p
