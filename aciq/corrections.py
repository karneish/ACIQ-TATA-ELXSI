"""User corrections to classification. A Tata requirement, and the reason any
later accuracy comparison would be credible.

You cannot compare a classifier against ground truth if there is no ground truth
and no way to fix it. `classify()` has honoured a `FlowFeatures.correction` field
all along; nothing was ever able to set it. This module is that missing half.

## Storage

Append-only JSONL at `data/corrections.jsonl`, one object per line. Append-only
is a deliberate choice:

- A correction is a **statement about a class of traffic**, not about one packet
  batch. If it were overwritten, the record of what was misclassified and when
  would be lost, and an accuracy claim could not be audited afterwards.
- Concurrent readers never block. A rewrite-in-place would need locking for a
  file that a CLI writes and the classifier reads on every tick.

Each line carries `recorded_at` and `recorded_by`, because a correction nobody
attributed is not usable as ground truth.

## What a correction matches on

`Flow` carries a source port, so `Flow.key` is per-*connection*. A correction
aimed at "all video from this host" would otherwise need re-issuing for every
new source port, which no user will do twice.

So a correction may match on:

| fields | scope |
|---|---|
| src + dst + proto + dport | one service on one host (the default) |
| src + dst + proto | every flow from that host pair, any port |

Source port is **never** part of a match key, because it changes on every
reconnect and would make corrections useless.

## Trust

A correction overrides inference completely -- `finalise()` cannot demote it,
because a user said so. That is the point, and it is also the risk: a wrong
correction silently degrades QoS with no confidence signal left to catch it.

Two guards, both cheap:

- `expires_at` is honoured. A correction is a hypothesis about a flow, and
  flows change; a correction that outlives the flow it was made for is worse
  than no correction. Default lifetime is finite for exactly this reason.
- Every lookup records whether it hit, so a stale correction is visible in the
  counters rather than only in principle.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .model import Flow, TrafficClass

#: Where corrections live. Append-only JSONL.
DEFAULT_PATH = Path("data/corrections.jsonl")

#: Seconds a correction stays valid. Finite by default: a correction describes a
#: hypothesis about traffic that will change. `None` means forever, and must be
#: asked for explicitly.
DEFAULT_TTL_S = 86400.0

#: Sentinel for "caller did not specify a port". Distinct from None, which
#: means host scope.
_UNSET = object()

#: Bumped when the on-disk shape changes, so an old file is rejected with a
#: clear reason instead of being misread.
SCHEMA_VERSION = 1

#: Minimum seconds between live-reload stat() calls. `lookup` runs per flow per
#: tick, so the check is throttled; the CLI writes corrections while the
#: process runs, and a store that only reads its file at construction silently
#: ignores every correction made after startup.
RELOAD_CHECK_S = 1.0

#: A protocol token: what conntrack can print (`\w+`) after lowercasing.
#: Shape-checked rather than from a fixed list — an allow-list would silently
#: skip corrections for any protocol the testbed has not seen (gre, esp. ...),
#: which looks exactly like "the user's correction did nothing".
_PROTO_RE = re.compile(r"[a-z0-9]{1,16}")


#: Friendly aliases for the enum values. `TrafficClass` values are verbose
#: (`realtime_interactive`, `adaptive_video`); an operator reaching for
#: `--as interactive` should not be punished with a usage error for it. The
#: canonical value is what gets written to disk, so the file stays unambiguous.
CLASS_ALIASES: dict[str, str] = {
    "interactive": "realtime_interactive",
    "realtime": "realtime_interactive",
    "adaptive": "adaptive_video",
    "video": "adaptive_video",
    "bulk": "bulk_transfer",
    "transfer": "bulk_transfer",
    # deliberately no "leased"/"lease" alias: see _reject_leased.
}


def canonical_ip(value: object, what: str = "address") -> str:
    """The canonical textual form of an IP address.

    Matching compares strings, so `2001:DB8::1` on disk and `2001:db8:0:0:0:0:0:1`
    from conntrack are two keys that never meet — a correction that silently
    never fires, indistinguishable from a misclassification. Canonicalising
    both sides at the boundary removes the whole family.
    """
    try:
        return str(ipaddress.ip_address(value))  # type: ignore[arg-type]
    except ValueError as e:
        raise CorrectionError(
            f"{what} {value!r} is not a valid IPv4 or IPv6 address") from e


def _ips_equal(a: str, b: str) -> bool:
    if a == b:
        return True
    try:
        return ipaddress.ip_address(a) == ipaddress.ip_address(b)
    except ValueError:
        return False


def _reject_leased(cls: TrafficClass) -> TrafficClass:
    """A correction may not mint lease capacity.

    LEASED is not a traffic class a user can observe and opine about; it is
    the marker the *lease book* attaches, with an id, a weight and an expiry
    that the shield and the plan both reason about. Accepting it on this path
    would let a JSONL line put flows into the leased class with no lease
    behind it: reserved bandwidth with nobody responsible for releasing it.
    """
    if cls is TrafficClass.LEASED:
        raise CorrectionError(
            "leased_flow cannot be set by a correction; leases are created "
            "through the lease book (intent API) with an id, weight and "
            "expiry")
    return cls


def _reject_leased_value(value: object) -> None:
    if str(value).strip().lower() in ("leased_flow", "leased", "lease"):
        _reject_leased(TrafficClass.LEASED)


def parse_class(value: str) -> TrafficClass:
    """Resolve a class name or alias to a TrafficClass.

    Raises CorrectionError listing the acceptable values, rather than letting a
    typo become a class that routes traffic wrongly.
    """
    if not isinstance(value, str):
        raise CorrectionError(f"class must be a string, got {type(value).__name__}")
    _reject_leased_value(value)
    candidate = CLASS_ALIASES.get(value.strip().lower(), value.strip().lower())
    try:
        return _reject_leased(TrafficClass(candidate))
    except ValueError as e:
        allowed = ", ".join(sorted(
            {*(c.value for c in TrafficClass if c is not TrafficClass.LEASED),
             *CLASS_ALIASES}))
        raise CorrectionError(f"unknown class {value!r}; must be one of: {allowed}") from e


class CorrectionError(ValueError):
    """Raised rather than written. A malformed correction that reaches
    enforcement would route traffic on a user's typo."""


@dataclass(frozen=True)
class Correction:
    """One recorded override."""

    src: str
    dst: str
    proto: str
    #: None = match every port for this host pair
    dport: int | None
    cls: TrafficClass
    reason: str = ""
    recorded_at: float = 0.0
    recorded_by: str = ""
    expires_at: float | None = None
    schema: int = SCHEMA_VERSION

    @property
    def scope(self) -> str:
        return "port" if self.dport is not None else "host"

    @property
    def key(self) -> tuple[str, str, str, int | None]:
        return (self.src, self.dst, self.proto, self.dport)

    def matches(self, flow: Flow, now: float | None = None) -> bool:
        """Does this correction apply to `flow`?

        Port-scoped corrections must match the port. Host-scoped ones ignore it
        entirely -- never compare, because a reconnect changes the source port
        and a port-insensitive correction would stop applying.

        Addresses compare as addresses, not as strings: `2001:DB8::1` and
        `2001:db8:0:0:0:0:0:1` are the same host.
        """
        if not _ips_equal(self.src, flow.src) or not _ips_equal(self.dst, flow.dst):
            return False
        if self.proto != flow.proto:
            return False
        if self.dport is not None and self.dport != flow.dport:
            return False
        if self.expires_at is not None:
            now = time.time() if now is None else now
            if now >= self.expires_at:
                return False
        return True


@dataclass
class CorrectionStats:
    """Observability. A correction nobody looks at is a correction nobody
    notices has gone stale."""

    loaded: int = 0
    skipped_malformed: int = 0
    hits: int = 0
    misses: int = 0
    expired: int = 0
    malformed_lines: list[str] = field(default_factory=list)


class CorrectionStore:
    """Reads `corrections.jsonl` and answers "what did the user say about this
    flow?".

    Loads the whole file once and keeps it in memory. The classifier asks this
    per flow per tick, so re-reading a file each time would make file I/O the
    hot path of the classifier.
    """

    def __init__(self, path: Path | str = DEFAULT_PATH, ttl_s: float = DEFAULT_TTL_S,
                 now: float | None = None):
        self.path = Path(path)
        self.ttl_s = ttl_s
        self._now = now
        self.stats = CorrectionStats()
        self._by_key: dict[tuple[str, str, str, int | None], Correction] = {}
        #: mtime the in-memory copy was loaded at; a change means the CLI wrote
        self._mtime: int | None = None
        #: last time maybe_reload() stat() the file (throttled, see RELOAD_CHECK_S)
        self._last_reload_check: float = float("-inf")
        self.reload()

    # -- reading -----------------------------------------------------------
    def reload(self) -> CorrectionStore:
        """Re-read the file. Called at construction and by the live-reload
        check whenever the file's mtime changes.

        Hit/miss/expired counters survive a reload: they describe what the
        *process* has seen, not what the file contains, and losing them on
        every external write would make the staleness counters useless exactly
        when someone is editing corrections.
        """
        prev = self.stats
        self.stats = CorrectionStats(hits=prev.hits, misses=prev.misses,
                                     expired=prev.expired)
        self._by_key.clear()
        if not self.path.exists():
            self._mtime = None
            return self
        with self.path.open(encoding="utf-8") as fh:
            for lineno, line in enumerate(fh, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    c = parse_correction(line)
                except CorrectionError:
                    # A bad line must not take down classification. It is counted
                    # and skipped, and the reason is kept for the log.
                    self.stats.skipped_malformed += 1
                    self.stats.malformed_lines.append(f"line {lineno}")
                    continue
                # last write wins for the same key: a user re-correcting the same
                # flow means the newer statement
                self._by_key[c.key] = c
                self.stats.loaded += 1
        self._note_file_mtime()
        return self

    def _note_file_mtime(self) -> None:
        try:
            self._mtime = self.path.stat().st_mtime_ns
        except OSError:
            self._mtime = None

    def maybe_reload(self, now: float | None = None) -> bool:
        """Reload if the file changed on disk. Throttled to RELOAD_CHECK_S.

        Without this, the store reads its file once at construction and every
        correction the CLI records afterwards is invisible to the running
        classifier -- the correction is in the file, counted in the CLI's
        output, and simply never applies.
        """
        if now is None:
            now = self._now if self._now is not None else time.time()
        if now - self._last_reload_check < RELOAD_CHECK_S:
            return False
        self._last_reload_check = now
        try:
            mtime = self.path.stat().st_mtime_ns
        except OSError:
            mtime = None
        if mtime == self._mtime:
            return False
        self.reload()
        return True

    # -- writing -----------------------------------------------------------
    def record(self, flow: Flow, cls: TrafficClass, reason: str = "",
               by: str = "user", dport: int | None | object = _UNSET,
               ttl_s: float | None | object = _UNSET) -> Correction:
        """Append a correction. Creates `data/` if needed.

        `dport` defaults to the flow's port. Pass `dport=None` explicitly for
        host scope. A plain `None` default would have conflated "not specified"
        with "every port", silently turning a host-wide correction into a
        single-port one.

        `ttl_s` defaults to the *store's* ttl_s, for the same reason and with the
        same `_UNSET` sentinel: it used to default to DEFAULT_TTL_S directly, so
        `CorrectionStore(ttl_s=60)` kept corrections alive for 24 hours and the
        caller's TTL was silently discarded. `ttl_s=None` means never expires.
        """
        if cls is None:
            raise CorrectionError("a correction must name a class")
        _reject_leased(cls)
        now = time.time() if self._now is None else self._now
        ttl = self.ttl_s if ttl_s is _UNSET else ttl_s
        expires = None if ttl is None else now + ttl
        # Canonical at the write, so a later lookup (which canonicalises the
        # flow side) meets it as the same string.
        src = canonical_ip(flow.src, "flow source")
        dst = canonical_ip(flow.dst, "flow destination")
        if not _PROTO_RE.fullmatch(str(flow.proto).strip().lower()):
            raise CorrectionError(
                f"flow protocol {flow.proto!r} is not a valid protocol name")
        c = Correction(
            src=src, dst=dst, proto=str(flow.proto).strip().lower(),
            dport=flow.dport if dport is _UNSET else dport,  # type: ignore[arg-type]
            cls=cls, reason=reason, recorded_at=now,
            recorded_by=by, expires_at=expires,
        )
        self._append(c)
        self._by_key[c.key] = c
        self.stats.loaded += 1
        return c

    def _append(self, c: Correction) -> None:
        """Append one line, atomically enough for our purpose.

        Opened in append mode and written with a single `write` of a line that
        already ends in a newline, so a concurrent reader sees either the whole
        line or none of it. The temp-file-and-rename dance used for whole-file
        rewrites is deliberately not used: it would replace the file and defeat
        the append-only property.
        """
        self.path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(asdict(c), sort_keys=True) + "\n"
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(line)
            fh.flush()
            os.fsync(fh.fileno())
        # Our own write must not trigger a reload on the next lookup: the
        # in-memory copy already has it, and a reload would reset the file
        # counters for nothing.
        self._note_file_mtime()

    # -- lookup ------------------------------------------------------------
    def lookup(self, flow: Flow, now: float | None = None) -> Correction | None:
        """The correction for this flow, or None.

        Port-scoped wins over host-scoped: the more specific statement is the
        more deliberate one. If someone corrected a specific port and then
        corrected the whole host, the host correction is the newer intent, so
        the *later recorded* one wins instead. That is resolved by `recorded_at`.
        """
        if now is None:
            now = self._now if self._now is not None else time.time()

        # Live reload: the CLI records while this process runs. Throttled
        # inside maybe_reload, so the per-flow cost is a comparison.
        self.maybe_reload(now)

        try:
            fsrc = canonical_ip(flow.src, "flow source")
            fdst = canonical_ip(flow.dst, "flow destination")
        except CorrectionError:
            # A live flow whose address does not parse matches nothing. Never
            # raise into the classification loop over a comparison.
            self.stats.misses += 1
            return None

        exact = self._by_key.get((fsrc, fdst, flow.proto, flow.dport))
        host = self._by_key.get((fsrc, fdst, flow.proto, None))

        best: Correction | None = None
        for cand in (exact, host):
            if cand is None:
                continue
            if cand.expires_at is not None and now >= cand.expires_at:
                self.stats.expired += 1
                continue
            # Strictly-greater, not >=: `exact` is visited first, so on an equal
            # timestamp the more specific port-scoped statement wins. That is the
            # safer default -- a narrower correction disturbs less traffic. A
            # host-scoped correction recorded strictly later still wins, because
            # re-correcting the whole host is a deliberate new intent.
            if best is None or cand.recorded_at > best.recorded_at:
                best = cand

        if best is None:
            self.stats.misses += 1
        else:
            self.stats.hits += 1
        return best

    def corrections_for(self) -> list[Correction]:
        return list(self._by_key.values())

    def __len__(self) -> int:
        return len(self._by_key)


def parse_correction(line: str) -> Correction:
    """Parse and validate one JSONL line.

    Validated field by field. A correction that reaches enforcement unvalidated
    would route traffic on a typo, and the failure would look like a
    misclassification rather than a bad file.
    """
    try:
        d = json.loads(line)
    except json.JSONDecodeError as e:
        raise CorrectionError(f"not valid JSON: {e}") from e
    if not isinstance(d, dict):
        raise CorrectionError("correction must be a JSON object")

    missing = [k for k in ("src", "dst", "proto", "cls") if k not in d]
    if missing:
        raise CorrectionError(f"missing field(s): {', '.join(missing)}")

    _reject_leased_value(d["cls"])
    try:
        cls = _reject_leased(TrafficClass(d["cls"]))
    except ValueError as e:
        allowed = ", ".join(c.value for c in TrafficClass
                            if c is not TrafficClass.LEASED)
        raise CorrectionError(
            f"unknown class {d['cls']!r}; must be one of: {allowed}") from e

    src = canonical_ip(d["src"], "src")
    dst = canonical_ip(d["dst"], "dst")

    proto = str(d["proto"]).strip().lower()
    if not _PROTO_RE.fullmatch(proto):
        raise CorrectionError(
            f"proto {d['proto']!r} is not a valid protocol name "
            "(expected letters/digits, e.g. tcp or udp)")

    dport = d.get("dport")
    if dport is not None:
        if not isinstance(dport, int) or isinstance(dport, bool):
            raise CorrectionError(f"dport must be an integer or null, got {dport!r}")
        if not 0 <= dport <= 65535:
            raise CorrectionError(f"dport {dport} outside 0..65535")

    schema = d.get("schema", SCHEMA_VERSION)
    if schema != SCHEMA_VERSION:
        raise CorrectionError(
            f"schema version {schema} != {SCHEMA_VERSION}; this file was written "
            f"by a different version")

    for f in ("recorded_at",):
        if f in d and not isinstance(d[f], (int, float)):
            raise CorrectionError(f"{f} must be a number")
    if "expires_at" in d and d["expires_at"] is not None:
        if not isinstance(d["expires_at"], (int, float)):
            raise CorrectionError("expires_at must be a number or null")

    return Correction(
        src=src, dst=dst, proto=proto,
        dport=dport, cls=cls, reason=str(d.get("reason", "")),
        recorded_at=float(d.get("recorded_at", 0.0)),
        recorded_by=str(d.get("recorded_by", "")),
        expires_at=d.get("expires_at"),
        schema=SCHEMA_VERSION,
    )