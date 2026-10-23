"""Device identity: stable MAC addresses mapped to current addresses.

An IP is not a device. DHCP hands it out, it changes on reconnect, and a lease
written for yesterday's address steers nothing today. A MAC is the stable name
the network already uses. This module keeps that mapping explicit and small so
the intent API can resolve a person's device before it becomes a lease.
"""

from __future__ import annotations

import ipaddress
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

_MAC_RE = re.compile(r"^[0-9a-f]{2}(?::[0-9a-f]{2}){5}$")
_NEIGH_RE = re.compile(
    r"^(?P<ip>\S+)\s+dev\s+(?P<iface>\S+)\s+lladdr\s+"
    r"(?P<mac>[0-9a-fA-F:-]{17})\s+(?P<state>\S+)", re.MULTILINE)


class IdentityError(ValueError):
    pass


def normalize_mac(value: object) -> str:
    if not isinstance(value, str):
        raise IdentityError(f"MAC must be a string, got {type(value).__name__}")
    s = value.strip().lower().replace("-", ":")
    if not _MAC_RE.fullmatch(s):
        raise IdentityError(f"{value!r} is not a MAC address")
    return s


def canonical_ip(value: object) -> str:
    try:
        return str(ipaddress.ip_address(value))  # type: ignore[arg-type]
    except ValueError as e:
        raise IdentityError(f"{value!r} is not an IPv4/IPv6 address") from e


def _looks_like_mac(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        normalize_mac(value)
        return True
    except IdentityError:
        return False


@dataclass(frozen=True)
class Device:
    mac: str
    ip: str | None = None
    hostname: str | None = None
    iface: str | None = None
    last_seen: float = 0.0
    source: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "mac", normalize_mac(self.mac))
        if self.ip is not None:
            object.__setattr__(self, "ip", canonical_ip(self.ip))
        if self.hostname is not None:
            object.__setattr__(self, "hostname", str(self.hostname)[:255])
        if self.iface is not None:
            object.__setattr__(self, "iface", str(self.iface)[:64])
        if self.source:
            object.__setattr__(self, "source", str(self.source)[:64])

    def to_dict(self) -> dict:
        return asdict(self)


class DeviceRegistry:
    def __init__(self, devices=()):
        self._by_mac: dict[str, Device] = {}
        for d in devices:
            if isinstance(d, Device):
                self._by_mac[d.mac] = d
            elif isinstance(d, dict):
                self.upsert(**d)
            else:
                raise IdentityError(f"cannot load device from {type(d).__name__}")

    def upsert(self, mac, ip=None, hostname=None, iface=None,
               last_seen=0.0, source="") -> Device:
        mac = normalize_mac(mac)
        prev = self._by_mac.get(mac)
        if prev is not None:
            ip = prev.ip if ip is None else ip
            hostname = prev.hostname if hostname is None else hostname
            iface = prev.iface if iface is None else iface
            last_seen = max(prev.last_seen, float(last_seen or 0.0))
            source = source or prev.source
        d = Device(mac=mac, ip=ip, hostname=hostname, iface=iface,
                   last_seen=float(last_seen or 0.0), source=source)
        self._by_mac[mac] = d
        return d

    def by_mac(self, mac) -> Device | None:
        try:
            return self._by_mac.get(normalize_mac(mac))
        except IdentityError:
            return None

    def by_ip(self, ip) -> Device | None:
        try:
            want = canonical_ip(ip)
        except IdentityError:
            return None
        for d in self._by_mac.values():
            if d.ip == want:
                return d
        return None

    def resolve(self, value) -> Device | None:
        if _looks_like_mac(value):
            return self.by_mac(value)
        return self.by_ip(value)

    def resolve_ip(self, value) -> str | None:
        d = self.resolve(value)
        return d.ip if d is not None else None

    def devices(self) -> list[Device]:
        return sorted(self._by_mac.values(), key=lambda d: d.mac)

    def __len__(self) -> int:
        return len(self._by_mac)

    def load_json(self, path: Path | str) -> DeviceRegistry:
        raw = json.loads(Path(path).read_text())
        rows = raw.get("devices", []) if isinstance(raw, dict) else raw
        if not isinstance(rows, list):
            raise IdentityError("device file must be a list or {'devices': [...]}")
        for row in rows:
            if not isinstance(row, dict):
                raise IdentityError("each device must be an object")
            self.upsert(row.get("mac"), ip=row.get("ip"),
                        hostname=row.get("hostname"), iface=row.get("iface"),
                        last_seen=row.get("last_seen", 0.0),
                        source=row.get("source", "file"))
        return self

    def from_neigh_text(self, text: str, now: float = 0.0,
                        iface: str | None = None) -> DeviceRegistry:
        for m in _NEIGH_RE.finditer(text or ""):
            self.upsert(m.group("mac"), ip=m.group("ip"),
                        iface=iface or m.group("iface"),
                        last_seen=now, source="neigh")
        return self


def load(path: Path | str) -> DeviceRegistry:
    return DeviceRegistry().load_json(path)
