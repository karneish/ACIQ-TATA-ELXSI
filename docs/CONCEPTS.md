# Concepts - Adaptive QoS Engine

This file explains the project in plain English. It is written for someone who
wants to understand the design, not just copy commands.

> Language note: the brief asks for Thanglish explanations in conversation and
> also asks that all repository files be in English. Those two rules conflict.
> This file follows the repository rule and is English. The conversational
> Thanglish explanation is given in chat. If you explicitly want Thanglish in
> this file, that is an allowed exception; say so.

The one-sentence version:

> A home router cannot treat every packet equally, and it cannot know what a
> packet contains without spying on it. So we read only the envelope, learn how
> each conversation behaves, give each kind of traffic a fair share, protect the
> delay-sensitive traffic, and verify that our change actually helped.

---

## 1. The problem: a busy home link is a shared road

Imagine one narrow road that connects a house to the internet. At the same time:

- a work video call needs small packets every 20 ms;
- a game needs small updates 60 times a second;
- three TVs pull large video chunks;
- a laptop downloads a large ISO;
- a phone uploads a cloud backup;
- a console downloads a software update.

The road can only carry so many cars per second. If everyone pushes at once, the
road fills up. A naive router puts packets in one long queue and sends them in
arrival order. The video call's tiny packet then waits behind a huge download.
That waiting is **latency**. When the waiting time changes from packet to packet,
that is **jitter**. When the queue is full and packets are thrown away, that is
**loss**.

The goal is not "maximum throughput." The goal is "the right traffic gets a good
experience while every class still makes progress."

---

## 2. Why static priority is not enough

A static rule says "video call is always high priority." That sounds fine until:

- nobody is on a call, and a backup could use the whole link;
- three TVs are streaming and all are marked high priority, so nothing is
  actually protected;
- a user starts an important call for 60 minutes and wants a temporary boost;
- the WAN capacity suddenly drops from 100 Mbps to 20 Mbps, so yesterday's
  static rates are now wrong.

Static rules do not know the current situation. An adaptive controller observes,
decides, enforces, and checks the result.

---

## 3. Bufferbloat: the full water tank problem

Think of a pipe with a water tank at the end. If the tank is enormous, the tap
can keep running even when the drain is slow. Nothing overflows, but the water
level (delay) becomes huge. In networking, a large queue is the tank. Throughput
looks fine, but every packet sits in the tank for a long time.

The fix is not "make the tank bigger." The fix is:

1. make the queue shorter (fq_codel or CAKE);
2. keep the bottleneck at our edge, where we control it;
3. shape slightly below the real link rate so the queue forms in our device,
   not in the ISP's equipment.

If we shape at 100% of the link, the ISP's queue may still fill. Shaping at about
90-95% gives our queue room to do its job. That is why the default is not 100%.

---

## 4. Metadata-only classification: read the envelope, not the letter

A packet has an envelope (headers) and a letter (payload). The envelope contains:

- source and destination IP addresses;
- source and destination ports;
- protocol (TCP, UDP, ICMP, ...);
- packet size;
- direction;
- timing between packets;
- DSCP marking, if present.

The letter contains the actual application data. We never open the letter. We do
not decrypt TLS. We do not parse HTTP, DNS, or video manifests. We do not read
SNI. That is a privacy requirement and a hard constraint.

Can we classify from the envelope? Often, yes:

- a call is bidirectional, low-rate, small-packet, steady;
- a game is UDP, small-packet, periodic, low-rate;
- adaptive video is TCP, downlink-heavy, multi-Mbps, chunked;
- a bulk download is TCP, downlink-heavy, long, and saturates the link;
- a software update is often bursty/periodic and finite;
- a cloud backup is uplink-heavy and long.

Some cases are genuinely ambiguous from metadata alone. A large HTTPS download
and a software update can look similar. The classifier must say "I am not sure"
rather than guess. That is what **confidence** and **unknown** are for. A user
correction is the escape hatch.

---

## 5. Flow: one conversation

A **flow** is one conversation, identified by the 5-tuple:

```text
(source IP, source port, destination IP, destination port, protocol)
```

The observer tracks each flow over time. It records:

- bytes per second (rate);
- packets per second;
- average packet size;
- direction (uplink/downlink);
- inter-arrival time (how far apart packets are);
- duration;
- burstiness (how uneven the rate is);
- duty cycle (how often the flow is active).

These are **flow statistics**, not payload.

A flow is not the same as a device. A laptop can have a call, a download, and a
backup at the same time. The controller must handle that.

---

## 6. The seven traffic classes

| Class | Real-world example | Typical metadata shape |
|---|---|---|
| `video_call_voice` | Zoom/Teams call, VoIP | Bidirectional, small packets, steady ~20 ms, low rate, DSCP EF possible |
| `interactive_gaming` | Console/PC game | UDP, small packets, periodic ~60 Hz, low rate, bursty |
| `adaptive_video_streaming` | Netflix/YouTube on a TV | TCP, downlink, multi-Mbps, large packets, chunked, long |
| `bulk_download` | Large ISO or game download | TCP, downlink, long, saturates the link |
| `software_update` | OS/app update | TCP, often bursty/periodic, finite, can look like bulk |
| `cloud_backup` | Phone/PC backup | TCP, uplink-heavy, long, large packets |
| `unknown` | Anything uncertain | Low confidence or conflicting signals |

`leased_flow` is **not** a classifier class. It is a policy overlay: when a user
temporarily asks for a specific device or flow to be protected, the enforcer can
route it to a dedicated leased class. The underlying class still has its floor.

---

## 7. Confidence and calibration

A classifier that always says "100% sure" is dangerous. We want a number that
means something:

- `0.9` should be right about 90% of the time when it says `0.9`;
- below a threshold (for example `0.5`), the answer becomes `unknown`;
- a wrong high-confidence answer is worse than an honest "I don't know."

**Calibration** checks whether the confidence number matches reality. If the
classifier says `0.8` on 100 flows and only 50 are correct, it is overconfident.
We measure this with a reliability table, Brier score, and expected calibration
error (ECE).

**User correction** is part of the design, not a patch. If the classifier says
"bulk" but the user knows it is a work call, the correction API stores that
decision and applies it to future matching flows. Corrections expire, because
traffic changes.

---

## 8. Capacity estimation: how fast is the road today?

The WAN link is not always the speed printed on the contract. It changes with
ISP congestion, Wi-Fi, and the access technology. The controller must estimate
the **current** capacity, not read a configured number.

Inputs:

- passive goodput (how many bytes actually crossed the bottleneck);
- queue depth/backlog;
- drops and overlimits;
- latency under load (RTT rises when a queue is building).

If the link is idle, we must not "learn" that it is slow. If it is saturated, the
queue and latency signals tell us. A sudden drop from 100 to 20 Mbps should be
detected quickly, and the shaper should follow it down without overshooting.

The estimate has a confidence. A low-confidence estimate should not cause a
large, irreversible policy change.

---

## 9. Policy engine: a thermostat with memory

The policy engine is a state machine, not a pile of `if` statements. The required
states are:

| State | Meaning |
|---|---|
| `INIT` | Load configuration, validate, snapshot current state |
| `NORMAL` | Link is healthy; normal class shares |
| `CONGESTED` | Saturation/latency is high; reduce/reshape |
| `INTENT_ACTIVE` | A temporary user request is active; protect it within bounds |
| `RECALIBRATING` | Capacity changed; wait for a stable estimate |
| `SAFE_MODE` | A fault occurred; known safe queue, no special classes |
| `ROLLING_BACK` | The verifier said "worse"; restore the previous policy |

A thermostat analogy: it does not switch the heater on and off every second. It
has hysteresis (a dead band) and a minimum time between changes. Without that, the
policy **flaps**: up, down, up, down, creating instability. We measure the number
of policy changes per minute.

Every state transition has:

- a trigger (what happened);
- a guard (is it safe/allowed?);
- an action (what policy to apply);
- a reason (written to the audit log).

---

## 10. Enforcement: lanes and a toll booth

Linux `tc` is the tool that shapes traffic. The plan uses:

- **HTB** (Hierarchical Token Bucket) to give each class a guaranteed rate and a
  ceiling. Think of lanes with a minimum speed and a maximum speed.
- **fq_codel** or **CAKE** as the leaf queue. These keep queues short and fair.
  CAKE is often better for a home link; fq_codel is a safe default.
- **ifb** for the download direction. Shaping ingress is awkward because the
  router receives packets before it can queue them. ifb redirects ingress traffic
  to a virtual device so it can be shaped.
- **nftables/fwmark** to mark flows so `tc` can route them to the right class.
- **DSCP** as a hint, never as trust. A device can lie about DSCP.

Enforcement must be:

- **atomic as possible**: save a snapshot, apply the whole tree, read it back;
- **verified**: compare the kernel's rates/ceilings to the plan;
- **reversible**: on mismatch or failure, restore the snapshot;
- **safe**: if recovery fails, apply a known safe state (one fq_codel/CAKE root,
  no special classes);
- **bounded**: never jump from 100 Mbps to 1 Mbps in one step;
- **observable**: every decision has a structured log with a reason.

---

## 11. Closed loop: did it actually help?

Applying a policy is not success. Success is a measured improvement.

The loop is:

```text
observe -> classify -> estimate capacity -> decide
   -> enforce -> verify before/after -> rollback if worse
```

The verifier compares a window before the change with a window after it. It looks
at latency, jitter, loss, throughput, queue depth, and fairness. It returns:

- **improved**;
- **not improved** (no meaningful change);
- **worse**.

If it is worse, the controller rolls back. If the measurement is invalid (too few
samples, missing probe), it must say "not measured", never "zero". Zero is a real
number; missing is not.

---

## 12. Temporary intent: a reserved lane, not a permanent takeover

A user may say: "I have a work call for the next 60 minutes; please protect it."

The intent API creates a **time-boxed** request:

- target: a class, a device, or a flow;
- weight/priority;
- TTL (time to live), with a maximum bound;
- a minimum guaranteed share for every other class.

The intent is not a permanent priority boost. It expires automatically. If the
process crashes, the intent is not allowed to persist forever. The policy engine
recomputes shares so that the protected target improves, but no other class is
starved. Fairness is checked with Jain's index and per-class minimum throughput.

---

## 13. Fairness: what "no starvation" means

Jain's fairness index is a number between 0 and 1:

- `1.0` means every competing flow/device gets an equal share;
- lower values mean some flows get much more than others.

But perfect equality is not always the goal. A call needs only a small rate; a
bulk download can use the rest. The real requirement is **no starvation**: every
class keeps a minimum guaranteed share, and a temporary intent cannot reduce any
class below that floor. We report both Jain's index and the minimum throughput of
every class.

---

## 14. The testbed: a laboratory, not a real ISP

The testbed is a set of Linux network namespaces on one VM:

- home clients (laptop, gaming, three TVs, backup/updates);
- an edge/router namespace where the controller and `tc` live;
- a WAN emulation namespace with HTB rate and netem delay/loss/jitter;
- a server namespace that generates the services.

This is **EMULATION**. It is not a real home router, Wi-Fi, DOCSIS/FTTH access
network, or ISP. The report must label it clearly. The model is useful because it
is reproducible and inspectable; its limitations are that radio effects, real
ISP scheduling, proprietary hardware, and scale are not represented.

Ground truth is known because we generate the traffic. That lets us measure
classification accuracy honestly. We still avoid classifying by the generator's
own port number, because that would be circular.

---

## 15. Measurement terms

| Term | Meaning |
|---|---|
| p50 / p95 / p99 | The value below which 50%/95%/99% of samples fall. p99 is a tail-latency measure. |
| Jitter | Variation in latency between packets. Mean absolute difference of consecutive RTTs. |
| Loss | `1 - received / expected`, excluding packets still in flight at the window boundary. |
| Throughput / goodput | Useful delivered rate, not the configured rate. |
| Queue depth / backlog | Bytes waiting in the queue. Large backlog means bufferbloat. |
| Jain index | Fairness across flows: `(sum x)^2 / (n * sum x^2)`. |
| Confidence interval | A range that expresses uncertainty around a mean. With 10 seeds we report 95% CI, not a false sense of precision. |
| Calibration | Whether predicted confidence matches observed accuracy. |
| Detection time | Seconds from a capacity step to the estimator/policy reacting. |
| Stabilisation time | Seconds until the policy stops changing after an event. |
| Overshoot | How far a rate change goes past the target before settling. |
| Flapping | Repeated policy changes in a short window. |

---

## 16. Reproducibility

A result is only useful if someone else can reproduce it. Every run records:

- the git revision;
- exact tool versions (`tc`, `ip`, `nft`, `iperf3`, `conntrack`, Python);
- the seed;
- the impairment config (rate, delay, loss, jitter, step time);
- the traffic generator config;
- the policy plan and state transitions;
- raw CSV/JSONL;
- a manifest with hashes.

No number is typed into a report by hand. The report generator reads the raw
data. If a measurement is missing, the report says so.

---

## 17. What "production" would require (short version)

This is a reference prototype. A real product would need:

- hardware validation on actual routers and Wi-Fi;
- ISP/access-network testing;
- kernel/eBPF performance work at gigabit rates;
- secure boot, signed updates, key management, and a threat model;
- multi-tenant isolation and privacy review;
- certification (electrical, radio, safety, regulatory);
- integration with vendor firmware, TR-069/TR-369, or cloud management;
- large-scale soak, fuzzing, and rollback drills.

Those will be documented in `docs/LIMITATIONS.md` (to be written) in a later phase. Do not present
the emulation as production evidence.

### Fix-round note (2026-10-23): which FSM the CODE actually has

The state table above is the CONCEPT document's design ideal. The measured
implementation a reader must reconcile with `docs/modules.md` is SMALLER:
the measurement controller has 4 states (`STABLE/ARMED/COOLDOWN/SLEEPING`)
and the safety shield has 3 (`MONITOR/FAULT_PENDING/SAFE_HELD`). Capacity
adaptation, congestion reshaping and safe-mode force are performed by the
same `TransactionManager.apply/force_safe` path rather than by dedicated
policy states. Any doc claims naming 7+ policy states as the shipped FSM
are stale; the unit-tested truth is in `docs/modules.md`.
