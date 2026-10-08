"""Reading real qdisc state back from the kernel.

Three sources, ordered by what has actually been verified on this machine:

1. ``tc class show`` **text** — verified by gate check 10. This is the only
   source confirmed to print per-class `rate` and `ceil`, which is what M4's
   read-back verification needs.
2. ``pyroute2`` NetNS — verified by gate check 8. Gives per-class
   bytes/packets/drops/overlimits/backlog via ``TCA_STATS2``, which is what M2
   and M5 need. It does **not** expose rates.
3. ``tc -s -j`` JSON — **never verified on this machine**, and it was silently
   returning empty, which made every policy apply look like a read-back
   mismatch. Kept last, as a fallback only.

That ordering is not a preference. An unverified path that returns empty is
worse than no path, because it looks like a real answer.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, field

#: `class htb 1:10 root prio 0 rate 40Mbit ceil 100Mbit burst 15Kb ...`
_CLASS_RE = re.compile(
    r"^class\s+\S+\s+(?P<classid>[\da-fx:]+)\s+.*?\brate\s+(?P<rate>[\d.]+\w*)"
    r"(?:.*?\bceil\s+(?P<ceil>[\d.]+\w*))?"
)
#: `Sent 1234 bytes 5 pkt (dropped 1, overlimits 2 requeues 3)`
_SENT_RE = re.compile(
    r"Sent\s+(?P<bytes>\d+)\s+bytes\s+(?P<packets>\d+)\s+pkt\s+"
    r"\(dropped\s+(?P<drops>\d+),\s+overlimits\s+(?P<overlimits>\d+)"
)
_BACKLOG_RE = re.compile(r"backlog\s+(?P<backlog>\d+)[bB]")

_UNIT_MBPS = {
    "bit": 1e-6,
    "kbit": 1e-3,
    "Kbit": 1e-3,
    "mbit": 1.0,
    "Mbit": 1.0,
    "gbit": 1e3,
    "Gbit": 1e3,
}


def _to_mbps(token: str) -> float:
    m = re.match(r"([\d.]+)(\w+)", token)
    if not m:
        return 0.0
    return float(m.group(1)) * _UNIT_MBPS.get(m.group(2), 1.0)


@dataclass
class ClassState:
    classid: str
    rate_mbps: float | None = None
    ceil_mbps: float | None = None
    rx_bytes: int = 0
    packets: int = 0
    drops: int = 0
    overlimits: int = 0
    backlog_bytes: int = 0


def parse_class_text(raw: str) -> dict[str, ClassState]:
    """Parse `tc class show dev X` text output.

    Rate and ceil come from the class line; counters from the following Sent
    line. Both are needed by different consumers and both are present in text
    output, which is why this is the primary source.
    """
    out: dict[str, ClassState] = {}
    current: ClassState | None = None
    for line in raw.splitlines():
        stripped = line.strip()
        m = _CLASS_RE.match(stripped)
        if m and stripped.startswith("class"):
            cid = m.group("classid")
            current = ClassState(
                classid=cid,
                rate_mbps=_to_mbps(m.group("rate")),
                ceil_mbps=_to_mbps(m.group("ceil")) if m.group("ceil") else None,
            )
            out[cid] = current
            continue
        if current is None:
            continue
        s = _SENT_RE.search(stripped)
        if s:
            current.rx_bytes = int(s.group("bytes"))
            current.packets = int(s.group("packets"))
            current.drops = int(s.group("drops"))
            current.overlimits = int(s.group("overlimits"))
            continue
        b = _BACKLOG_RE.search(stripped)
        if b and current.backlog_bytes == 0:
            current.backlog_bytes = int(b.group("backlog"))
    return out


def parse_class_json(raw: str) -> dict[str, ClassState]:
    """Fallback parser. Only trusted if it yields handles."""
    try:
        items = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    if isinstance(items, dict):
        items = [items]
    out: dict[str, ClassState] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        h = it.get("handle")
        if h is None:
            continue
        cid = h if isinstance(h, str) else _decode_classid(int(h))
        stats = it.get("stats") or it.get("stats2") or {}
        entry = ClassState(
            classid=cid,
            rate_mbps=(float(it["rate"]) / 1e6) if isinstance(it.get("rate"), (int, float)) else None,
            ceil_mbps=(float(it["ceil"]) / 1e6) if isinstance(it.get("ceil"), (int, float)) else None,
        )
        if isinstance(stats, dict):
            entry.rx_bytes = int(stats.get("bytes") or 0)
            entry.drops = int(stats.get("drops") or 0)
            entry.overlimits = int(stats.get("overlimits") or 0)
            entry.backlog_bytes = int(stats.get("backlog") or 0)
        out[cid] = entry
    return out


def _decode_classid(handle: int) -> str:
    """65552 -> '1:10'. HTB encodes major in the high 16 bits, minor in the low."""
    return f"{handle >> 16:x}:{handle & 0xFFFF:x}"


def read_class_state(
    dev: str = "veth-lan",
    ns: str | None = "router",
    runner=subprocess.run,
) -> tuple[dict[str, ClassState], str]:
    """Return (state, source_name). Source name goes into the audit log so a
    report can say which reader produced the numbers."""
    pre = ("ip", "netns", "exec", ns) if ns else ()

    def _run(argv):
        try:
            r = runner(list(argv), capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return 1, ""
        return r.returncode, r.stdout or ""

    rc, out = _run(pre + ("tc", "class", "show", "dev", dev))
    if rc == 0 and out:
        state = parse_class_text(out)
        if state:
            return state, "tc-text"

    rc, out = _run(pre + ("tc", "-s", "-j", "class", "show", "dev", dev))
    if rc == 0 and out:
        state = parse_class_json(out)
        if state:
            return state, "tc-json"
    return {}, "none"
