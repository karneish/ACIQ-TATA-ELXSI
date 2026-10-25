#!/usr/bin/env python3
"""sinksample.py — per-second receiver-side sampling for every workload sink.

The sink logs used to say only what had arrived by process teardown. A verdict
about "what the receiver saw during the intent window" needs a TIME SERIES, so
every sink prints, at a fixed cadence, one line:

    [<kind> sink] t=<elapsed> cum=<bytes> inst=<Mbps> Mbps

cum = bytes received since sink start; inst = Mbps received over the
interval since the previous line. The line format is deliberately distinct
from the end-of-connection summary lines (no "N bytes X.XX Mbps") so the
existing totals parser never double counts them: totals keep coming only
from connection-close lines.

`get_bytes` is a callable returning the live cumulative byte count; the
TCP sinks feed it a shared dict looked up incrementally per chunk read, the
UDP echo sink its own `bytes` attribute. `stop`, when given, ends sampling;
without it the thread lives for the process (sinks are meant to outlive the
run and be killed with the namespace).
"""

from __future__ import annotations

import threading
import time


def sampler(kind: str, get_bytes, every_s: float = 1.0,
            stop: threading.Event | None = None,
            monotonic=time.monotonic, sleep=time.sleep) -> threading.Thread:
    """Start a daemon thread printing one receiver line per `every_s`.

    A long interval means the sink saw nothing; the inst line prints 0.0 for
    it rather than hiding it -- an unlogged silent second is how a delivery
    gap disappears from the evidence.
    """
    def _run() -> None:
        t0 = monotonic()
        prev_t, prev_b = 0.0, get_bytes()
        while stop is None or not stop.is_set():
            sleep(every_s)
            now = monotonic()
            b = get_bytes()
            dt = now - prev_t
            inst = 0.0 if dt <= 0 else (b - prev_b) * 8 / dt / 1e6
            print(f"[{kind} sink] t={now - t0:.2f} cum={b} bytes "
                  f"inst={inst:.2f} Mbps", flush=True)
            prev_t, prev_b = now, b

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    return th
