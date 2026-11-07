"""IPv6 scenario coverage helper: build IPv6 flow tuples.

Pure helper so scenarios can declare IPv6 workloads. The enforcement path
already emits `protocol ipv6` flower filters; this only constructs tuples
for the experiment driver.
"""
from __future__ import annotations

def ipv6_flow(src: str, dst: str, sport: int, dport: int, proto: str = 'tcp') -> dict:
    return {'src': src, 'dst': dst, 'sport': int(sport), 'dport': int(dport), 'proto': proto, 'family': 'ipv6'}
