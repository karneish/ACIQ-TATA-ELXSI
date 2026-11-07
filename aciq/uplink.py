"""Uplink shaping: shape the egress uplink queue identically to downlink.

Uplink shaping reuses the same HTB tree on the uplink interface with the
provisioned uplink rate. Pure rate computation; the kernel apply is via the
existing txn path.
"""
from __future__ import annotations

def uplink_rates(uplink_mbps: float, plan_rates: dict, default_rate: float) -> dict:
    """Clamp per-class rates to the uplink ceiling."""
    cap = max(float(uplink_mbps), 0.0)
    out = {}
    for cls, r in (plan_rates or {}).items():
        out[cls] = min(float(r), cap) if cap > 0 else float(r)
    out.setdefault('default', default_rate if cap == 0 else min(float(default_rate), cap))
    return out
