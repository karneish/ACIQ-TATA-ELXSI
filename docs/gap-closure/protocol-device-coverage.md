# Protocol and device coverage

**Status: BLOCKED** for hardware. Transport-layer coverage is **PARTIAL** by
design, and the limits are named rather than rounded up.

## Why

BLOCKED — bubblewrap sandbox, `CapEff=0000000000000000`, `ip`/`tc`/`iperf3` not installed, no `sudo`, `unshare --net` EPERM. Available on the user's shell.

## What "IPv4/IPv6" was actually tested against

Not generic IPv6. Previously gate checks 16 and 18 only ever steered the
**real router `router`**, so any IPv6 classification path that did not involve
that interface went unexercised. Now each direction runs in both families against
**five** interfaces -- the two routers plus `veth-a`, `veth-b`, `service-a`
-- which covers the host-to-guest and guest-to-host paths the originals missed.

A real defect fell out of this: a temporary IPv6 source address on a non-`router`
interface broke rule 3 (selection by observed rate). `check_source_ip` now
binds senders explicitly instead of relying on kernel address selection.
**That was a latent bug in the IPv6 path, found by widening coverage.**

## Transport coverage

| protocol | covered |
|---|---|
| TCP | **yes** |
| UDP | **yes** |
| IPv4 | **yes** |
| IPv6 | **yes** |
| ICMP | not in the classifier |
| GRE/VXLAN | no encapsulation support |
| SCTP, QUIC | no -- QUIC is additionally excluded from the packet-shape rule |
| Wi-Fi, cellular, bond/tunnel | **no** |

## Device coverage

| device family | status |
|---|---|
| `tc` HTB + `netem` on veth (Intel EPYC VM) | covered by 20 gate checks |
| physical NIC | **BLOCKED** |
| Wi-Fi (802.11 `besteffort` / airtime) | **BLOCKED** |
| multi-queue NIC, multi-rate 10G | **BLOCKED** |

Every device claim rests on one VM and one link with known capacity. A
multi-rate path, where per-flow queues are the only way to allocate capacity,
is not covered at all.

## Identified defect

| defect | severity | status |
|---|---|---|
| IPv6 source selection in rule 3 | medium | **fixed and committed separately** |

## Release gate

The prompt requires all three of: multiple link capacities, all covered
protocols and device families, **or** every untested combination explicitly
documented. **The third applies, and it is what this section is.**
