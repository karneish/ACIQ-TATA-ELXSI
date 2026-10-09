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


def _scale(series: Sequence[Series], w: int, h: int) -> tuple[float, float, float, float]:
    """-> (x0, y0, dx, dy). Times are positions, not indices, so a gap in the
    samples reads as a gap on the chart rather than being compressed away."""
    xs = [t for s in series for t, _v in s.points]
    ys = [v for s in series for v in s.values]
    if not xs or not ys:
        return 0.0, 0.0, 1.0, 1.0
    t0, t1 = min(xs), max(xs)
    lo, hi = min(ys), max(ys)
    if t1 == t0:
        t1 = t0 + 1.0
    if hi == lo:
        # A flat line at zero is the commonest real case; give it a visible band
        # instead of dividing by zero and drawing nothing.
        lo, hi = lo - 0.5, hi + 0.5
    x0 = PAD_L
    y0 = PAD_T + PANEL_H - PAD_B - PAD_T
    dx = (w - PAD_L - PAD_R) / (t1 - t0)
    dy = (PANEL_H - PAD_T - PAD_B) / (hi - lo)
    return x0, y0, dx, dy


def render_panel(name: str, title: str, series: Sequence[Series],
                 width: int = PANEL_W, height: int = PANEL_H) -> str:
    """One panel as a standalone `<svg>` string."""
    x0, y0, dx, dy = _scale(series, width, height)
    lo = min((v for s in series for v in s.values), default=0.0)
    hi = max((v for s in series for v in s.values), default=1.0)
    if hi == lo:
        lo, hi = lo - 0.5, hi + 0.5

    def xy(t: float, v: float) -> tuple[float, float]:
        return x0 + (t - min((tt for s in series for tt, _ in s.points), default=0.0)) * dx, \
               y0 - (v - lo) * dy

    parts = [
        f'<svg class="panel" viewBox="0 0 {width} {height}" width="100%" '
        f'height="{height}" role="img" aria-label="{esc(title)}">',
        f'<rect x="0" y="0" width="{width}" height="{height}" fill="#fbfbfd" '
        f'stroke="#d8dce3"/>',
        f'<text x="{PAD_L}" y="{PAD_T + 8}" class="ptitle">{esc(title)}</text>',
    ]

    # gridlines at 0 / mid / max, labelled -- an unlabelled axis is decoration
    for frac in (0.0, 0.5, 1.0):
        v = lo + (hi - lo) * frac
        y = y0 - (v - lo) * dy
        parts.append(f'<line x1="{x0}" y1="{y:.1f}" x2="{width - PAD_R}" y2="{y:.1f}" '
                     f'class="grid"/>')
        parts.append(f'<text x="4" y="{y + 4:.1f}" class="axis">{_fmt(v)}</text>')

    for s in series:
        if not s.points:
            continue
        d = " ".join(("M" if i == 0 else "L") + f"{xy(t, v)[0]:.1f},{xy(t, v)[1]:.1f}"
                     for i, (t, v) in enumerate(s.points))
        colour = _CLASS_COLOURS.get(s.label, s.colour)
        parts.append(f'<path d="{d}" fill="none" stroke="{colour}" stroke-width="1.6"/>')
        # Last point marked, so a flat line still shows it drew something.
        lt, lv = s.points[-1]
        parts.append(f'<circle cx="{xy(lt, lv)[0]:.1f}" cy="{xy(lt, lv)[1]:.1f}" '
                     f'r="2.4" fill="{colour}"/>')

    if not any(s.points for s in series):
        parts.append(f'<text x="{width / 2}" y="{height / 2}" class="empty" '
                     f'text-anchor="middle">no data</text>')
    parts.append("</svg>")
    return "".join(parts)


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


CSS = """
:root{color-scheme:light dark}
body{font:14px/1.45 system-ui,sans-serif;margin:0;padding:18px;background:#fff;color:#1b1f24}
h1{font-size:19px;margin:0 0 2px}
.sub{color:#5b6472;margin:0 0 16px;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(420px,1fr));gap:14px}
.panel{background:#fbfbfd;border:1px solid #d8dce3;border-radius:6px}
.ptitle{font:600 12px system-ui;fill:#1b1f24}
.axis{font:10px ui-monospace,monospace;fill:#5b6472}
.empty{font:12px system-ui;fill:#8a929e}
.legend{display:flex;flex-wrap:wrap;gap:12px;margin:14px 0 0;font-size:12px;color:#3c444f}
.legend span{display:inline-flex;align-items:center;gap:5px}
.sw{width:11px;height:11px;border-radius:2px;display:inline-block}
@media (prefers-color-scheme:dark){
 body{background:#12151a;color:#e6e9ee}
 .panel{background:#1a1e25;border-color:#2b313a}
 .ptitle{fill:#e6e9ee}.axis{fill:#8a929e}.grid{stroke:#2b313a}
}
"""


def render_page(panels: dict, subtitle: str = "", refresh_s: int = 0) -> str:
    """The whole page. `panels` is the dict from `panels_from_samples`."""
    body = []
    for key, title in PANELS:
        series = panels.get(key) or []
        body.append(render_panel(key, title, series))
    legend = "".join(
        f'<span><i class="sw" style="background:{c}"></i>{esc(n)}</span>'
        for n, c in _CLASS_COLOURS.items()
        if any(s.label == n for k in PANELS for s in panels.get(k[0], [])))
    meta = f'<meta http-equiv="refresh" content="{max(1, refresh_s)}">' if refresh_s else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">{meta}
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>ACIQ dashboard</title><style>{CSS}</style></head>
<body>
<h1>ACIQ dashboard <span class="sub">(M8 &mdash; read-only)</span></h1>
<p class="sub">{esc(subtitle)}</p>
<div class="grid">{"".join(body)}</div>
<div class="legend">{legend}</div>
</body></html>"""


def build_from_samples(rows: Iterable[dict], subtitle: str = "",
                       refresh_s: int = 0) -> str:
    classes = sorted({k for r in rows for k in (r.get("per_class") or {})})
    return render_page(panels_from_samples(rows, classes), subtitle, refresh_s)


def write_snapshot(rows: Iterable[dict], path: Path | str,
                   subtitle: str = "", refresh_s: int = 0) -> Path:
    """Render a snapshot to disk. The only write this module performs."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_from_samples(rows, subtitle, refresh_s))
    return p