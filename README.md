# ACIQ — Adaptive Classification & Intent-aware QoS

Prototype for *Case Study 3: Adaptive QoS Engine for Mixed Home Broadband Traffic*.

A QoS controller for a home broadband link that classifies traffic into three
classes, estimates the real link capacity, shares the line fairly, and lets a
user grant a **time-boxed lease** to one device or flow.

> **Status: in progress. No experimental results yet.**
> The testbed gate has not been run. Every performance number in this repo is a
> *target*, not a measurement. See `PLAN.md`.

## What exists right now

| Path | State |
|------|-------|
| `PLAN.md` | Full design, 14-check gate, limitations |
| `testbed/setup.sh`, `gate.sh`, `cleanup.sh` | Written, syntax-checked, **never executed** |
| `aciq/model.py` | Shared dataclasses |
| `aciq/policy.py` | **M3** — the policy engine and lease maths |
| `aciq/metrics.py` | **M5** — metrics collector, injectable counter source |
| `aciq/classify.py` | **M1** — classification rules, confidence, honest UDP/443 gap |
| `aciq/flowtrack.py` | **M1** — conntrack parsing and per-flow behaviour |
| `aciq/capacity.py` | **M2** — capacity estimation from counters only, no probe |
| `aciq/tc.py` | **M4** — declarative qdisc tree + command rendering, pure |
| `aciq/shield.py` | **M9** — veto rules and the fault/recovery state machine |
| `aciq/txn.py` | **M9** — snapshot, apply, verify, roll back, escalating safe state |
| `docs/architecture.md` | System diagram + module contracts (M1/M2 DRAFT) |
| `tests/` | **152 passing tests**, no root required |
| `testbed/workloads/` | 4 generators + selftest, **18 checks passing** |

Deliberately **not** built yet, because their design depends on gate results
that have not been produced:

- **M6** experiment harness — needed before any measured result
- M4 (enforcement) and M9 (transaction + shield) are **done**; the vertical slice
  works end to end with fault injection verified
- M1, M2, M3 and M5 are all **done**. M1 uses conntrack (confirmed by the gate);
  M2 uses drop/overlimit counters with **no probe** (check 12 measured it)

## Quick start

```bash
python3 -m unittest discover -s tests -v   # 152 tests, no root
python3 testbed/workloads/selftest.py      # 18 generator checks, no root
```

Both run entirely on loopback. Neither touches the network.

## Running the testbed gate

Needs root and a real Linux host with `iproute2`, `sch_netem`, `sch_cake`,
`sch_fq_codel`, `nf_conntrack`, `iperf3`, `nftables`, `conntrack`, `ethtool`.

```bash
sudo apt update && sudo apt install -y iproute2 iperf3 conntrack ethtool nftables python3-venv
chmod +x testbed/*.sh
bash -n testbed/*.sh
python3 -m venv ~/aciq-venv && ~/aciq-venv/bin/pip install pyroute2

sudo ./testbed/setup.sh && sudo ip netns list && sudo ./testbed/cleanup.sh
sudo env ACIQ_VENV=/home/YOU/aciq-venv ./testbed/gate.sh
sudo ./testbed/cleanup.sh
```

Everything runs inside three namespaces (`client`, `router`, `wan`) built on
veth pairs. **Your real network and interfaces are not touched.**

`cleanup.sh` runs `pkill -x iperf3`, which will kill any iperf3 you started
yourself. Intended for a test machine.

## The idea in one paragraph

On a home line, a call, a game, three TVs and a large download all want the same
pipe. Static priority rules cannot decide what matters at a given moment, and
high throughput alone is not enough — large queues are what add delay and
jitter. ACIQ estimates the real capacity from queue counters, gives each class a
weighted share with a **floor that is never removed**, and lets a user grant a
**lease**: a bounded, weighted, time-boxed boost to one device or flow. The
lease expires on its own, so a forgotten request can never permanently harm the
household, and no class can be starved.

## Known limitations

Stated up front because they are real:

- The slow link is an **HTB token-bucket emulation**, not real DSL/cable/fiber.
- Counter-based capacity detection only sees a bottleneck **on the router**. In
  a real home it is usually the modem or ISP side, where router counters show
  nothing. Closing this needs a delay-based signal — see gate check 12.
- Passive estimation is valid only while the link is busy.
- Traffic is synthetic and self-generated, so classification accuracy measured
  here will look better than on real homes.

## Layout

```
PLAN.md                  design, gate definition, limitations, traceability
aciq/
  model.py               dataclasses: Flow, Class, Lease, RatePlan, Sample
  policy.py              M3: floors, weights, lease, TWO capacity invariants
  classify.py            M1: DSCP/port rules + behaviour, confidence, honest gap
  flowtrack.py           M1: conntrack parsing, per-flow behaviour accumulation
  capacity.py            M2: counter-only capacity estimation, saturation-gated
  tc.py                  M4: declarative qdisc tree, rendering, read-back verify
  shield.py              M9: veto rules, fault modes, backoff, retry budget
  txn.py                 M9: transaction, rollback, escalating safe state
  metrics.py             M5: counters -> rates, percentiles, fairness, CPU
tests/
  test_policy.py         24 tests incl. both invariants and the 100 -> 20 rescale
  test_metrics.py        27 tests: rate derivation, tc JSON parsing, separation
  test_classify.py       28 tests, parsing real gate conntrack output (v4 + v6)
  test_capacity.py       27 tests: idle blindness, hysteresis, dwell, CUSUM
  test_enforce.py        48 tests: tree render, verify, vetoes, fault injection
docs/
  architecture.md        system diagram + module contracts
testbed/
  setup.sh               namespaces, veths, IPv4+IPv6, offloads off
  gate.sh                14 checks, stops at first failure
  cleanup.sh             idempotent teardown
  workloads/
    udpx.py              UDP echo engine: self-measured RTT/jitter/loss
    call.py              voice/video call, ~1 packet per 20 ms
    game.py              real-time game, 30 pps
    video.py             adaptive-bitrate TCP stream
    bulk.py              saturating bulk transfer
    selftest.py          18 checks, loopback only
```

## Third-party licences

`pyroute2` (BSD-3-Clause) is the only non-stdlib dependency in the MVP. Nothing
is vendored or redistributed. See `docs/licenses.md` once written.

## Testbed gate: 14/14 passing

The gate ran clean. Findings that changed the design, all measured:

- conntrack gives per-flow byte counters over IPv4 **and** IPv6
- HTB lets a class borrow **past its parent's rate**, up to its own `ceil` — a
  20 Mbps parent with `ceil 99/97` children delivered **28.5 Mbps**
- a flow is bounded by **its own class `ceil`**, not the parent rate
- HTB's `default` class **cannot be changed on a live qdisc**; the tree must be
  rebuilt, which M9's transaction must be able to roll back
- saturation is visible in `overlimits` (24803 → 65101), so **M2 needs no probe**;
  an EF probe in the protected class showed no signal, confirming that delay
  measured inside a protected class reports protection, not saturation
