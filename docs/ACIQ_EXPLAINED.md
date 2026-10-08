# ACIQ — Explained in Simple English

This document explains the project from the very beginning: what problem we are
solving, what the solution is, and exactly how it works. Every Linux command and
every technical term is explained in brackets the first time it appears.

Every **number** quoted was really measured on the project's own testbed, and the
file that measured it is named. But three parts of the **system** are described
here that do not yet run, and they are marked `[NOT WIRED]` at every mention:

- the behavioural classifier (M1) — built and unit-tested, but never called
  during a run, so it does not influence enforcement;
- `ADAPTIVE` and `LEASED` — the classes exist and are given bandwidth, but
  nothing routes traffic into them;
- the correction file — described, never written.

So the measured system is **DSCP-EF filtering + HTB + `fq_codel`**. The evidence
is `docs/WIRING_AUDIT.md`, which audits every module for whether it is *connected
to the runtime* as well as whether it exists and has tests.


## Contents

1. [The problem, explained](#1-the-problem-explained)
2. [The Linux tools used, explained](#2-the-linux-tools-used-explained)
3. [The solution, step by step](#3-the-solution-step-by-step)
4. [What measurement taught us](#4-what-measurement-taught-us)
5. [What we actually measured](#5-what-we-actually-measured)
6. [Honest limitations](#6-honest-limitations)
7. [One-paragraph summary](#7-one-paragraph-summary)


## 1. The problem, explained

### 1.1 The situation

Picture a normal home. One internet line comes into the house. Suppose it is
100 Mbps. At the same moment, everybody in the house is using it:

- Someone is on a **video call**. It needs very little data, but it needs it to
  arrive *quickly*.
- A child is **playing a game**. Again small data, but delay and jitter (variation
  in delay) make it unplayable.
- Three people are **streaming TV**. These need a steady, medium amount of
  bandwidth.
- A phone is **downloading a 5 GB backup**. It is greedy and does not care about
  delay at all.

All four of these want the **whole** pipe. There is only one pipe.


### 1.2 Why buying more bandwidth does not fix it

The obvious fix is to buy a faster line. But bandwidth does not fix delay. The
real enemy is **bufferbloat**. Here it is in plain words.

- Your line can carry 100 Mbps.
- The backup download tries to send at 1000 Mbps.
- The router has a **queue**. A queue is just a waiting area in memory where
  packets wait their turn. This one is 1000 packets deep.
- Every packet the backup sends gets dumped into that queue.
- Your video call's packet arrives and has to join the **back of a 1000-packet
  line**.

A packet at the back of a 1000-packet queue waits behind 1000 other packets. That
waiting time *is* the delay. **A big queue is what causes the delay.** Getting a
bigger pipe makes it worse, because a bigger pipe feeds a bigger queue faster.

**The proof, from this project's own test data.**

Scenario 1 is a call plus a bulk download, both on the same 100 Mbps link. Only
the queueing method differs.

| System | Call latency (median) |
|---|---|
| B0 — `pfifo`, a plain first-in-first-out queue | **120.051 ms** |
| ACIQ — shaped, with a guaranteed share per traffic type | **0.259 ms** |

Same link. Same call. Same bytes. **464 times worse** purely because of how the
queue was built.

That single comparison is the entire problem. You paid for 100 Mbps, and your
call is unusable.


### 1.3 The three ways normal home routers fail at this

**Failure 1 — Static priority rules cannot decide what matters *right now*.**

Routers let you say "calls are priority 1, everything else is priority 2". But
that rule is fixed in advance. At 8 pm there are three TVs, one game and one
backup running, and no call at all. A static rule has no idea that tonight the
*game* matters more than the *TV*. It cannot adapt to what the household is
actually doing.

**Failure 2 — Nobody knows how fast the line really is.**

The router is *configured* for 100 Mbps. But the modem supplied by the internet
provider might actually be delivering 20 Mbps right now, because of a
neighbouring house, a DSL resync, or congestion at peak hour. The router has no
idea. So it hands out bandwidth shares based on a number that is a **lie**.

And there is a danger in trying to fix this. If the system tries to discover the
real speed and guesses even slightly wrong in the low direction, it will shrink
the shares, which fills the queues more, which *looks* like even more congestion,
which shrinks the shares further. This is a feedback loop, and it is called a
**death spiral**. It is not theoretical. It really happened in this project: a
100 Mbps link was estimated down to **7.2 Mbps** inside a single 40-second run.
See section 4.4.

**Failure 3 — "Boost this device" buttons break fairness permanently.**

Routers do have a prioritise-this-device feature. The problem is that it has
**no time limit and no minimum guarantee**. Press it once and go to bed; it is
still high priority tomorrow morning. Meanwhile the traffic you pushed down now
gets **nothing, ever**. One person in the house can permanently starve everyone
else with three clicks.


### 1.4 What the brief demands

The case study requires the solution to do all of the following.

1. Classify traffic **without reading or decrypting payloads** (privacy).
2. **Estimate** the real link capacity.
3. **Shape** the link with queues so delay stays low.
4. **Prove** it works, with measurements rather than claims.
5. Offer **temporary intent** (a user boost) **while staying fair**.
6. Be built as **independent modules**, each with stated inputs, outputs, failure
   handling and success conditions.
7. Support **IPv4 and IPv6**.
8. **Roll back** safely, and never starve any class.
9. Compare against a **deterministic baseline** and an optional **AI/ML**
   alternative.
10. Be **observable, reversible and reproducible**.


## 2. The Linux tools used, explained

Everything happens inside the Linux kernel's **traffic control** system, often
shortened to `tc`. This section explains every tool the project uses, what it is,
and why it was chosen.


### 2.1 `tc` — traffic control

```
tc qdisc add dev veth-lan root handle 1: htb default 30
```

> **What it is.** `tc` is the kernel's built-in packet scheduling and queueing
> system. Every shaping decision in this project is made by it.
>
> **Why it is used.** It is standard, it lives in the kernel, and it shapes traffic
> at line rate. A normal user-space program could never keep up with gigabit
> speeds, but `tc` does it without using any CPU of its own.


### 2.2 `netns` — network namespaces

```
ip netns add client
ip netns add router
ip netns add wan
```

> **What it is.** Separate, completely isolated mini-network stacks. Each
> namespace has its own network interfaces, its own routes, its own firewall, and
> its own `tc` rules. They cannot see each other.
>
> **Why it is used.** To test a three-device setup on a **laptop**, we need three
> separate machines. Namespaces give us a fake household and a fake internet
> provider in software, so the laptop's own real internet connection is never
> touched.


### 2.3 `veth` — virtual Ethernet cables

```
ip link add veth-lan type veth peer name veth-c
```

> **What it is.** A software network cable. Whatever goes in one end comes out the
> other end.
>
> **Why it is used.** They physically connect the three namespaces into a line:
> `client` <-> `router` <-> `wan`. This builds the home network without any
> hardware.


### 2.4 `htb` — hierarchical token bucket

```
tc class add dev veth-lan parent 1:1 classid 1:10 htb rate 40mbit ceil 99mbit
```

> **What it is.** The main bandwidth allocator. You declare a tree of "buckets",
> called classes. Each class gets two numbers: a **rate**, which is the amount it
> is guaranteed, and a **ceil**, which is the most it is ever allowed to borrow.
>
> **Why it is used.** This is the only kernel tool that can **divide** one link
> between competing traffic types. It costs no CPU because it runs in the kernel.


### 2.5 `fq_codel` — fair queueing with controlled delay

```
tc qdisc add dev veth-lan parent 1:10 handle 10: fq_codel
```

> **What it is.** The algorithm that sits *inside* a class. It keeps the queue
> deliberately **short**, and sends packets fairly.
>
> **Why it is used.** `htb` decides *who gets how much*. `fq_codel` decides *how
> much delay that costs*. **Together, these two are the bufferbloat fix.**
> `htb` alone would still allow a large queue. `fq_codel` alone could not divide
> the bandwidth.


### 2.6 `cake` — the strong baseline (called B1)

```
tc qdisc add dev veth-lan root handle 1: cake bandwidth 95mbit
```

> **What it is.** A single, very capable all-in-one fair queue. Modern, popular,
> and it gets a great deal right.
>
> **Why it is used.** This is the **honest competitor**. Any new QoS system has to
> prove it beats `cake`, and `cake` is the obvious answer someone would give if
> asked "why not just use an existing tool". So we measure against it, and we
> report the places where `cake` **wins**. It did win, twice.


### 2.7 `pfifo` — the weak baseline (called B0)

```
tc qdisc add dev veth-lan parent 1:30 handle 30: pfifo limit 1000
```

> **What it is.** A plain first-in-first-out queue. 1000 packets deep. Whatever
> arrives first leaves first.
>
> **Why it is used.** This is what a **cheap consumer router** does. It is included
> deliberately so we can **demonstrate** the bufferbloat the whole project exists
> to fix. Comparing only against `cake` would hide the problem entirely.


### 2.8 `netem` — network emulator

```
tc qdisc replace dev veth-lan parent 1:30 handle 40: netem delay 20ms
```

> **What it is.** It adds artificial delay, jitter or packet loss, to make a test
> link behave like a real wide-area link.
>
> **Why it is used.** To make the test realistic. There is one strict rule in this
> project: **`netem` is used for delay and loss only, never to set the speed.**
> Speed is always set with `htb`, so that every system being compared faces exactly
> the same bottleneck.


### 2.9 `conntrack` — connection tracking

```
conntrack -L -p udp
```

> **What it is.** The kernel's table of every connection passing through, with a
> **running byte counter for each connection**, for both IPv4 and IPv6.
>
> **Why it is used.** This is how the project classifies traffic **without reading
> a single byte of payload**. The system sees only "this connection has moved 4.3
> megabytes so far". It never sees what was inside. This satisfies the privacy
> requirement by construction, not merely by promise.


### 2.10 `tc -s class show` — reading counters back

```
tc -s class show dev veth-lan
```

> **What it is.** Prints every class along with its live counters: bytes sent,
> packets, drops, **overlimits**, and backlog.
>
> **Why it is used.** These numbers are the **only** input the capacity estimator
> is allowed to read. It looks at what the link actually **did**, never at what it
> was **told** to do. That distinction is the whole reason the capacity estimate can
> be trusted.


### 2.11 `u32` and `flower` — the traffic routers

```
tc filter add dev veth-lan parent 1: protocol ip  prio 1 u32  match ip dsfield 0xb8 0xfc flowid 1:10
tc filter add dev veth-lan parent 1: protocol ipv6 prio 2 flower ip_tos 0xb8/0xfc flowid 1:10
```

> **What it is.** Rules that look at packet **headers only** and send matching
> packets into a class. The value `0xb8` is the DSCP mark for "Expedited
> Forwarding", abbreviated EF. This is the standard label that real voice and
> video endpoints put on their media.
>
> **Why it is used.** Two separate filters are needed. The `u32` rule cannot see
> IPv6 traffic at all, so IPv6 requires the `flower` rule. This was measured, not
> assumed (gate check 14).


### 2.12 `iperf3` — the trusted speedometer

```
iperf3 -c 10.0.1.2 -t 25 -f m
```

> **What it is.** A standard tool that floods a link and reports the speed actually
> achieved, in Mbps.
>
> **Why it is used.** When verifying that the testbed's bottleneck really works, we
> do not trust our own counters to measure speed. `iperf3` is the yardstick we
> measure ourselves against.


### 2.13 `ethtool -K` — turning off hardware shortcuts

```
ethtool -K veth-lan gro off gso off tso off
```

> **What it is.** This disables "offload" features, where the kernel is allowed to
> merge many small packets into one large packet before sending.
>
> **Why it is used.** Offloading **lies about packet counts and sizes**. The
> classifier in this project reasons about average packet size and burstiness. If
> the kernel has merged thirty small packets into one giant one, those measurements
> become fiction. Offloads are therefore switched off on **all four** ends of the
> testbed, so the numbers are real.


## 3. The solution, step by step

The solution has five working parts, plus a reporting part.

- **M1 — Classifier:** decides what kind of traffic this is.
- **M2 — Capacity estimator:** works out how fast the line really is.
- **M3 — Policy engine:** decides the fair shares.
- **M4 — Enforcement:** applies them to the kernel.
- **M9 — Shield and transaction manager:** makes sure nothing breaks.
- **M5 — Metrics, M6 — experiments, M10 — report:** measure and publish.


### 3.1 Step 1 — Classify the traffic (M1) · `[NOT WIRED]`

Files: `aciq/classify.py`, `aciq/flowtrack.py`

> **This step does not run.** `classify()` is called only from `tests/test_classify.py`.
> Neither `classify.py` nor `flowtrack.py` appears in the import chain from
> `run_experiments.py`. The 28 tests pass, so the logic is correct — it is simply
> never invoked, and therefore never affects what `tc` enforces.
>
> What actually decides classes in a real run is the DSCP-EF filter, and nothing
> else: `aciq/tc.py` emits exactly two filters, both matching DSCP EF, both to
> class `1:10`. Everything else falls to the HTB default class `1:30` (BULK).

**Goal.** For each connection, decide which of three buckets it belongs to.
`[NOT WIRED — and as a result ADAPTIVE never receives traffic, because nothing
routes to class 1:20. Measured: `adaptive_video: goodput 0.0` in every sample.
LEASED, class 1:40, has the same problem.]`

- `INTERACTIVE` — calls and games. Needs low delay.
- `ADAPTIVE` — video streaming. Needs steady bandwidth.
- `BULK` — downloads and updates. Needs to be held back.

There is a fourth class, `LEASED`, which is created only while a user has
requested a boost.

**How the decision is made, in three tiers of confidence.**

**Tier A — read the labels the sender already put on the packets.** Highest
confidence.

- **DSCP 46, which is EF** means INTERACTIVE, confidence **0.95**. Real voice and
  video endpoints mark their media this way. This is the standard and correct
  signal, so we trust it strongly.
- **Well-known signalling ports** — 3478 (STUN), 5060, 5061 (SIP), 5349 — mean
  INTERACTIVE, confidence **0.85**.

**Tier B — read the behaviour, from counters only.** Here the system watches one
connection over about ten samples and works out four things:

- **Rate** — how many bits per second it is moving.
- **Average packet size** — total bytes divided by total packets.
- **Burstiness** — are the byte counts steady, or lumpy?
- **Duty cycle** — what fraction of samples saw any bytes move at all?

Then it applies thresholds:

- Large packets, **1200 bytes or more**, steady (**duty cycle 0.8 or more**), and
  old enough (**3 seconds or more**), means BULK, confidence **0.65**.
- Small packets, **600 bytes or less**, over UDP, with **10 packets or more**,
  means INTERACTIVE, confidence **0.55**.

**Why average packet size is the key signal.** A video call sends many **small**
packets, for example 300 bytes, fifty times a second. A file download sends
**full 1500-byte** packets as fast as the link allows. That one number separates
the two reliably, and it comes from the kernel's own packet counter. No payload is
ever touched.

**Tier C — say "I don't know", honestly.**

```
UDP/443: no DSCP mark, and the statistics do not separate a call from a download
```

The result is confidence **0.40**, class **none**, with the reason recorded.

**Why this matters so much.** A confident wrong label is *worse* than an honest
gap. If we guess INTERACTIVE on a large download, we hand it a protected share
and starve the actual call. So anything below **0.5 confidence** is demoted to
**UNCLASSIFIED** (`aciq/classify.py`, function `finalise`). We never guess.

**One deliberate design decision.** The classifier **ignores our own test ports**.

The test traffic generators normally listen on ports 5001 to 5004. If the
classifier keyed on those, it would score **100% accuracy on every single run**, and
that number would mean absolutely nothing. So the ports are randomised per seed,
and classification is forced to rest on behaviour and DSCP only. **We make our own
accuracy number harder to earn on purpose.**

The classifier also *would* keep a **correction file** at `data/corrections.jsonl`,
where a user's manual override is recorded and changes later decisions.
`[NOT WIRED]` — no code writes that file, and `data/corrections.jsonl` does not
exist. This is also a requirement in the brief ("classifiers must expose
confidence and allow correction of misclassification"). Confidence **is**
implemented and tested; correction is not implemented at all.


### 3.2 Step 2 — Work out how fast the line really is (M2)

File: `aciq/capacity.py`

**Goal.** Find the true capacity from evidence, without cheating.

**The cheating rule, and this is important.** M2 is **forbidden from reading the
configured rate of class 1:1**, which is the class that represents the link. The
data structure it accepts, called `Measurement`, has **no field for the configured
rate at all**. It physically cannot read the answer.

Why this matters: the configured rate *is* the answer. If the estimator read it,
then "adaptation time" would be zero and the entire test would be meaningless.

**The signal used.** We read the **parent** class, which is class 1:1, and which
*is* the emulated link. From it we read the `overlimits` counter and the `dropped`
counter.

- `overlimits` means "a class inside me wanted more than I guaranteed it, and I
  said no."
- **The link is full when overlimits are happening at a high rate.**

**The threshold, chosen from measurement, not taste.**

```
SAT_OVERLIMIT_MIN = 3000 overlimits per second
```

The three measured situations:

| Measured situation | Overlimits per second |
|---|---|
| 100 Mbps link genuinely full, with bulk saturating it | **5127 to 6485** |
| 20 Mbps link saturated (gate check 12) | **24803 to 65101** |
| 100 Mbps link only about 10% loaded, classes merely rate-limited | **170 to 1313** |

The two populations, "really full" and "not really full", are separated by roughly
**four times** at the closest point. Below 3000 per second we say "not full". At or
above 3000 per second we say "full".

**We only read the parent's counters. We ignore the children's entirely.** The
reason for this is the worst bug in the project, explained in section 4.4.

**Four guards against noise.**

1. **Saturation gate.** Never learn from an idle link. If nobody is downloading,
   then the throughput we see is just how much people *asked* for, not how fast the
   line is. Idle samples **decay confidence** by 0.15 instead of inventing a number.
2. **A two-sample streak is required** (`SAT_STREAK_REQUIRED = 2`). One burst is not
   a reading.
3. **Asymmetric smoothing.** When capacity **falls**, move fast, with a factor of
   0.6. When capacity **rises**, move slowly, with a factor of 0.1. The reasoning is
   practical: users are already hurting when capacity drops, so react at once.
   Nobody is harmed by being slow to believe good news.
4. **Hysteresis of plus or minus 10 percent, plus a 5-second minimum gap.** Do not
   chase small wiggles, and do not change policy more than once every 5 seconds.
   Oscillation is treated as a failure, not a feature.

**The optional CUSUM detector** (`CusumDriftDetector` in `aciq/capacity.py`) exists
for **gradual** drift, such as a link that slowly degrades over hours. It is
deliberately **not** the main detector, because the 100-to-20 drop is a sudden step
that the smoothing already catches instantly. CUSUM earns its place only on slow
drift, where no single sample stands out.

It is also **busy-gated**: it refuses to look at samples from an idle link, because
an idle link's throughput falling toward zero is not a capacity collapse. Feeding
it idle data produces false alarms.

**What happens when the link drops from 100 to 20 Mbps.** The estimator walks the
estimate down, M3 recalculates the shares, and M4 rewrites the `tc` tree, all within
seconds, with no human involved.


### 3.3 Step 3 — Decide the shares (M3)

File: `aciq/policy.py`

**This is a pure function.** It takes a capacity and a lease, and returns a plan. It
never touches the kernel. That is deliberate: it is exactly why the
anti-starvation guarantee can be tested on any machine, without root.

**The base weights.**

```
INTERACTIVE : 8.0
ADAPTIVE    : 4.0
BULK        : 2.0
```

**Every class keeps a floor, and the floor is never removed.**

```
floor = max(2 Mbps, 5 percent of the link capacity)
```

**Why this exists.** This is the formal answer to "do not let low-priority traffic
starve". Bulk keeps **at least** 2 Mbps no matter what else is happening. It can be
slowed down. It can never be deleted.

One note on wording, because it matters: the project deliberately avoids the word
"leftovers". The floor is a **guarantee**, not a bonus.

**Two invariants that must never break.**

```
1. the sum of all child rates  <=  the link capacity
2. every child ceil           <=  the link capacity
```

**Why invariant 2 exists.** This was measured, not theorised. The testbed set the
parent to 20 Mbps but left the children with ceilings of 99 Mbps. The delivered
throughput was **28.5 Mbps on a 20 Mbps link.** A ceiling set above the bottleneck
is not harmless spare room; it is a way for traffic to exceed the link. See section
4.1.

**What happens if the link is too small for all the floors.** Suppose the capacity
is 3 Mbps and three classes each need a 2 Mbps floor, which is 6 Mbps needed. The
floors are **scaled down proportionally**, and a flag `degraded = True` is set. We
admit that the link is too small to protect everyone, rather than quietly breaking
our own invariant.

**The Lease, which is the user-facing feature.**

A lease is **not a priority boost**. It is a bounded, weighted, **time-boxed**
share, calculated like this:

```
LEASED = INTERACTIVE weight x (1 + LAMBDA x weight)      LAMBDA = 0.5
       = 8 x (1 + 0.5 x 0.4)
       = 9.6
```

**A warning about this formula, and it should never be "simplified".** The
obvious-looking version, `LEASED = LAMBDA x weight`, gives `0.5 x 0.4 = 0.2`. Bulk's
weight is **2.0**. So the lease would become the **lowest** priority class in the
entire system, weaker than the very traffic it was meant to protect. The unit tests
caught this mistake. The weight must stay anchored to the class the lease actually
promotes.

**The lease's properties.**

- It gets its **own class, `1:40`**, rather than boosting an existing class. This
  way a lease can be measured separately from the class it resembles.
- A **device** lease is resolved to that device's live conntrack flows. The
  dominant flow is given the sub-class `1:40`.
- It **expires automatically** after `ttl_s`, which defaults to 90 seconds. A
  forgotten request **cannot** permanently harm the household.
- The **revert on expiry is verified** by the shield, not assumed.
- If **leases overlap** on the same target, the most recent one wins. This is
  documented behaviour, not an accident.
- **Floors are never touched.** A lease borrows from spare capacity. It never takes
  from another class's guarantee.


### 3.4 Step 4 — Actually apply it (M4)

Files: `aciq/tc.py` for the pure tree, `aciq/txn.py` for execution

**M4 is the only module in the whole project that touches the kernel.** This is an
architectural rule, and it is enforced by review.

**The tree it builds.**

```
root qdisc  1:     htb default 30
  and class 1:1    rate = capacity         <- this IS the link
    |
    +-- class 1:10  INTERACTIVE   rate = large share   ceil = capacity   leaf fq_codel
    +-- class 1:20  ADAPTIVE      rate = medium share   ceil = capacity   leaf fq_codel
    +-- class 1:30  BULK          rate = small share    ceil = capacity   leaf fq_codel
    +-- class 1:40  LEASED        (only while a lease is active)

filters:  DSCP EF  ->  1:10      (u32 for IPv4, flower for IPv6)
```

**Three real-world constraints shaped this module, all measured.**

1. **Ceilings are always clamped to the capacity.** Measured proof in section 4.1:
   a ceiling above the bottleneck lets traffic exceed the link.

2. **The tree is always rendered whole, never patched.** This is because HTB's
   `default` class **cannot be changed on a live qdisc**:

   ```
   tc qdisc change dev veth-lan root handle 1: htb default 50
   -> the kernel replies: "Change operation not supported by specified qdisc"
   ```

   So any policy change is a **full rebuild**. That is why M9's transaction manager
   has to be able to roll a rebuild back, which it does by storing the entire list
   of commands from the last known-good state.

3. **Leaf handles must be unique per device.** Class `1:10` gets leaf handle `10:`,
   class `1:20` gets `20:`, and so on. An earlier draft reused one handle for two
   leaves, which failed with an "already exists" error.

**Then it reads back and verifies.** After applying the plan, M4 re-reads
`tc -s class show` and compares what it **asked for** against what the kernel
**actually did**, using a tolerance of **1 percent**. The tolerance is necessary
because `tc` rounds its output however it likes, so an exact comparison would fail
on formatting alone.

A mismatch is not a warning. It triggers a rollback.

**One more honest detail.** If the reader **cannot see** a value at all, that is
recorded as "unverifiable". That is a weaker guarantee than a match, so it must not
be allowed to pass silently, and it must not be reported as a failure of the rate.
It is reported separately, and never hidden.


### 3.5 Step 5 — Measure it honestly (M5)

File: `aciq/metrics.py`

**The single most important structural fact in the whole design.**

> **M5 is the only component that ever handles latency, jitter and loss. And it
> hands those numbers to the *evaluation*, never to the capacity estimator.**

This is enforced **by the type system**, not by discipline. Two different data
types exist:

- `ClassCounters` holds kernel counters: bytes, drops, overlimits, backlog. **It
  has no latency field at all.**
- `EvaluationData` holds latency, jitter and loss, measured by the traffic
  generators themselves.

The estimator's function accepts only a `Measurement`, which is built from
`ClassCounters`. **There is no way to leak evaluation data into the estimator even
by accident.** If anyone ever wanted to combine them, it would take a deliberate,
visible change to the code.

**Why this rule exists.** If the estimator could see latency, it would be measuring
the symptom it is supposed to fix. The whole point of this project is to estimate
capacity from queue counters alone. Keeping the two apart makes that claim
verifiable by reading the types.

**What M5 produces, per class, every second.**

Goodput (useful throughput), drop rate, overlimit rate, backlog, round-trip time at
the 50th, 95th and 99th percentiles, jitter, and loss ratio. Plus a **Jain fairness
index** across classes, and the controller's own CPU usage.

The Jain index is defined as `(sum of values) squared, divided by (number of values
times the sum of their squares)`. 1.0 is perfectly fair. Its useful property is that
it never reaches 0: a single hog scores roughly 1 divided by n, not zero, so it
cannot be confused with "no data".

**Two real bugs this component already caught and fixed.**

- **Without the `-s` flag**, `tc class show` prints only the configuration line and
  **no `Sent` line at all**. Every counter therefore read as 0.0, while the classes
  themselves parsed perfectly. The classes looked fine and the numbers were all
  zero.
- **`tc -s -j`, the JSON version, never worked on this machine** and silently
  returned nothing. That made every policy apply look like a read-back failure, and
  made the first real experiment report no per-class data whatsoever.

The fix: plain text is now the primary reader, JSON is the fallback, and **the name
of the reader that actually answered is written into the audit log**. An unverified
path that returns empty is worse than no path at all, because it looks like a real
answer.

**Honest CPU measurement.** The `getrusage` system call reports CPU time, but the
kernel updates it only at scheduler-tick granularity. Over a very short measurement
window, the CPU delta can be **larger** than the wall-clock delta, producing a
fraction above 1.0, which is meaningless. Below 0.05 seconds the collector reports
**0.0** rather than a fabricated figure. CPU overhead is a graded metric, so it has
to be either right or absent.


### 3.6 Step 6 — Never break it (M9, the shield and the transaction)

Files: `aciq/txn.py`, `aciq/shield.py`

**The transaction.**

```
snapshot  ->  apply  ->  read back and verify  ->  [mismatch?]  ->  rollback  ->  safe state
```

**Five veto rules, each using data we actually have.**

| Number | What is vetoed | Why |
|---|---|---|
| 1 | A class below its floor, checked against the **scaled** floor when the plan is degraded | Low-priority traffic must never be starved |
| 2 | Child rates that add up to more than the link capacity | That would exceed the link |
| 3 | More than one policy change in any 5-second window | Oscillation is a failure, not a feature |
| 4 | The read-back does not match what was applied | The kernel did not do what we asked |
| 5 | Drop or overlimit **rate** above 5000 per second | We are causing harm, not fixing it |

**Two deliberate non-vetoes, and this is the subtle part of the design.**

**Interactive delay is not a veto.** Delay rises *precisely* when capacity has
dropped and the policy is out of date. A veto on delay would block **the exact
change that fixes the problem.** The project rule is written plainly in
`aciq/shield.py`: *veto conditions must never include the symptom the system exists
to resolve.* Delay is reported as a diagnostic instead.

**Backlog is not a veto.** It was measured at **zero throughout a saturated link**,
because `fq_codel` deliberately keeps queues short. A backlog veto would therefore
almost never fire, and a rule that never fires reads as protection that is not there.
That is the worst kind of lie, so backlog is reported as a diagnostic only.

**Veto severity, a real and necessary distinction.**

- **Deferred** means "not yet". You are inside the change window. This is the
  mechanism working correctly. Escalating this to a fault would put the shield into
  fault mode during perfectly normal operation, and it would then refuse
  legitimate work.
- **Fault** means something is genuinely broken, or the kernel failed. Only these
  trip the shield.

**The fault and recovery state machine.**

```
MONITOR  ---breach--->  FAULT_PENDING
                          safe state applied IMMEDIATELY, alarm raised

FAULT_PENDING  ---retry due--->  retry
                 backoff 1s -> 2s -> 4s -> 8s -> 16s -> 60s cap

FAULT_PENDING  ---retry budget exhausted--->  SAFE_HELD
                                              alarm latched

SAFE_HELD  ---manual reset--->  MONITOR
```

**The rules behind it.**

- **Three breaches in 60 seconds** moves into `FAULT_PENDING`. Being in fault means
  "pinned to the safe state **with automatic recovery**", not "waiting for a human".
- **The retry budget beats the time window.** `MAX_RETRIES = 5` means five
  consecutive failed recovery attempts. A rolling 60-second window would have been a
  bug: once the backoff reaches 60 seconds, each retry lands inside its own fresh
  window, the counter never reaches five, and the system retries **forever**. The
  unit tests pin this behaviour down.
- **The budget resets only after 300 seconds** of sustained health, measured while
  in the normal monitoring state. Time passing on its own never resets it.
- **`SAFE_HELD` is a safe state, not a lock.** The safe plan **stays applied and
  keeps running.** Adaptive shaping is *suspended, not disabled*. The household is
  never left unshaped. The alarm is latched and visible through the status API, the
  dashboard banner and the audit log, and **manual reset is the only thing that
  clears it**. That is correct, because `SAFE_HELD` cannot accumulate sustained
  health and therefore can never clear itself.

**The safe state has no class breakdown, and that is a measured necessity.**

The safe state exists to protect the household when something is *already wrong*.
So it must be the thing **most likely to succeed**. The original design rolled back
*into the same broken command*: the safe tree contained class `1:30`, and `1:30`
was exactly what the kernel was refusing. It reported failure and left the household
**unshaped at the worst possible moment**.

So the safe state now escalates down a ladder of increasingly simple things, each
rung measured to work on this machine:

| Rung | Command | Gate evidence |
|---|---|---|
| 1 | `cake bandwidth 0.95 x capacity` at the root | check 9 delivered **90.8 Mbps** |
| 2 | `fq_codel` at the root | plain fair queueing, no rate limit |
| 3 | `pfifo limit 1000` at the root | check 10b |

Losing the class breakdown is an **accepted cost. During a fault, protection beats
classification.**

If all three rungs fail, the rollback **reports failure honestly** rather than
claiming success.

**Audit log.** Every event is written with a timestamp: committed, vetoed,
deferred, read-back mismatch, apply failed, read-back partial. The reader source
that answered is recorded too. This is what makes the system observable.


### 3.7 Step 7 — Run the experiments (M6)

Files: `aciq/harness.py` for the logic, `aciq/experiment.py` for execution

**The one invariant this module exists to protect.**

> **`set_capacity(C)` changes ONLY class 1:1. It never rescales the children.**

This is not a style preference. Gate runs 1 and 2 measured that changing the parent
rate alone does **not** cap throughput, because a child can borrow past its parent's
rate. If the harness rescaled the children, it would bypass M2 and M3 **entirely**,
and "adaptation time" would be a measurement of the test harness rather than of the
system.

**Three delivery modes, and this is where the honesty lives.**

| Mode | Who knows the new capacity? | Why it exists |
|---|---|---|
| `static` | Nobody. Baselines keep their old settings. | Realistic. A static router does not learn that its link got slower. |
| `informed` | The baseline is **handed** the new capacity instantly. | An **oracle that no real device is.** It exists to answer the question "why not just use cake?" |
| `adaptive` | Nobody. M2 must work it out from counters alone. | This is the actual contribution being measured. |

**The sequence of one run.**

```
1. write config.json      <- before anything runs, so even a crashed run is reproducible
2. build the system tree at the starting capacity
3. launch the receivers first, then wait 1 second  <- or senders race and fail
4. settle: interactive traffic only, measurement switched off
5. launch all senders, then sample every 1 second for the whole run
6. at the drop time: change ONLY the link
7. collect each workload's own self-measured report
8. write samples.jsonl, workloads.json, result.json
```

**Why step 3 launches receivers first.** The receivers bind to their ports and the
senders connect to them. If both start at the same instant, the sender arrives
before the listener and dies with "connection refused". That failure looks exactly
like "the bulk transfer had no effect on the link", which is a completely
misleading conclusion.

**Why step 4 runs interactive traffic only during settle.** The settle period exists
to let the shaping tree and the interactive path reach steady state before bulk
arrives. If bulk also ran during settle, the transient being avoided would be the
very transient bulk causes, and settling would simply be hiding the effect we want
to measure. Running only interactive traffic means every system starts from an
identical condition, and bulk still arrives during the measured window.

**A real bug this step caught.** Without a settle period, the first packets raced a
flooding bulk transfer, which produced a **19 millisecond p99 outlier** against
cake's 1.5 milliseconds. That was a false result, and the settle phase removed it.

**Reproducibility.** Each run is seeded. Ports are drawn from a seeded random
generator starting at 5100, so no workload is identified by its port. The full
configuration is written to disk before the run starts, so a run that crashes in the
middle is still reproducible from its own artefacts.


### 3.8 Step 8 — Report it honestly (M10)

File: `aciq/report.py`

**Two rules this component will not break.**

1. **A missing measurement is reported as missing, never as zero.** A report that
   silently fills its gaps looks identical to a clean result, and is worse than no
   report at all.
2. **It states the sample count next to every comparison.**

**The statistics rule that is often ignored.**

```
MIN_PAIRS_FOR_PVALUE = 6
```

For a paired Wilcoxon signed-rank test, the smallest attainable two-sided p-value is
`2` raised to the power of `1 minus n`, where n is the number of pairs.

- With n = 5, that is **0.0625**, which is mathematically **incapable** of reaching
  p below 0.05.
- With n = 6, it is 0.03125, which can.

So with fewer than 6 pairs, the project reports **ranges and confidence intervals,
and never p-values.** You cannot reach statistical significance with five samples,
so it says so rather than pretending otherwise.

**The verdict logic checks every percentile, not the flattering one.** Cherry-
picking the median and hiding the tail is exactly the failure mode this project
exists to avoid. All four measures, p50, p95, p99 and jitter, are compared for every
scenario.

**And a tie is reported as a tie.** Calling two equal numbers a loss would be as
dishonest as claiming a win that did not happen.


## 4. What measurement taught us

This is the most valuable part of the project. Almost nothing here began as theory.
These are the things we got **wrong first**, then measured, then fixed.


### 4.1 Lowering the parent rate does not cap the link

**Setup.** Parent class `1:1` dropped from 100 to 20 Mbps. Children left at rates of
40 and 30, with ceilings of 99 and 97.

**Result. 28.5 Mbps delivered on a 20 Mbps link.**

**Why.** HTB lets a child **borrow past its parent's rate**, up to the child's own
`ceil`. The parent rate is not a ceiling. The child's `ceil` is the real limit.

**What changed.** M3's second invariant was born directly from this. Every child
`ceil` must be less than or equal to capacity, and child rates must be rescaled so
they add up to no more than capacity.


### 4.2 Changing HTB's default class is impossible

```
tc qdisc change dev veth-lan root handle 1: htb default 50
-> "Change operation not supported by specified qdisc"
```

**What changed.** M4 always renders a **complete tree**, never a diff. And M9's
transaction must be able to roll back a full rebuild, which is why the transaction
manager stores the entire rendered command list from the last known-good state, not
just a record of what changed.


### 4.3 An EF probe measures protection, not saturation

The original plan was to send a marked probe packet in the **protected** interactive
class and watch its delay rise. Measured on a genuinely saturated 20 Mbps link, with
an idle baseline of 0.051 ms:

| Signal | Result | Verdict |
|---|---|---|
| `overlimits` per class | **24803 rising to 65101** over 25 seconds | **PRIMARY.** Huge, unambiguous, already present in `tc -s`. |
| `dropped` | 0 rising to **252** | primary, corroborating |
| **EF probe, class 1:10** | 0.051 rising to **0.070 ms** | **REJECTED. No signal at all.** |
| Unmarked probe, class 1:30 | 0.051 rising to **0.405 ms, about 8 times** | validated fallback, not needed |
| `backlog` | **0 throughout** | **REJECTED** |

**Why the EF probe failed, in plain words.** A packet in the protected class is being
protected *from* the congestion. Its delay stays low **because the system is working
properly.** So the measurement was reporting the protection, not the congestion. The
project records plainly that the reviewer's reasoning was correct and the original
probe design was wrong.

**What changed.** M2 ships on **drop rate plus overlimit rate only. No probe at all.**
The benefits are real: no probe traffic, no probe overhead to account for in the CPU
numbers, and no extra privilege needed. The unmarked probe stays documented as a
validated remedy for the limitation that remains.


### 4.4 The M2 death spiral, where 100 Mbps collapsed to 7.2 Mbps

This was the worst bug in the project, and the most instructive.

**Measured, in scenario 3. Three TVs plus a gaming session, offering about 10.5 Mbps
on a 100 Mbps link.**

```
100 -> 24.6 -> 13.3 -> 10.8 -> 7.2 Mbps      4 policy changes
```

**The cause, which is a feedback loop with four steps.**

1. M2 summed the **child** `overlimits` counters and read them as congestion.
2. A child's overlimits rise when **that child** exceeds its own guaranteed rate.
   This happens **routinely on an almost idle link**, because several classes
   compete for 100 Mbps and two of them will briefly hit their guarantees.
3. M2 therefore shrank the capacity estimate. M3 then shrank all the class rates.
   Smaller guarantees mean classes hit them more often, so **overlimits went up**.
4. M2 shrank again. And again. Collapse.

**The first fix attempt was to use the parent class only. It was not sufficient.**
Because HTB attributes a child's borrow to the parent as well. A parent's overlimits
rise when a child is backlogged and borrowing. So "the parent is busy" does not mean
"the link is full". The estimate still ended at 7.2 Mbps.

**The final fix was to use the parent's overlimit *rate*, above a threshold taken
from measurement.** The magnitude separates the two populations. Child overlimits are
**ignored entirely**.

**Replayed against the real recorded data:**

| Scenario | Before the fix | After the fix |
|---|---|---|
| s1, link genuinely full | 100.7 | **99.9, correctly saturated** |
| s3, about 10 percent loaded | 7.2, with 4 changes | **0.0, with 0 changes** |
| s2, dropping to 20 | 52.7 | **32.4, stepping down** |

**The honest limitation that this does not fix.** Separating "the link is full" from
"a class is merely rate-limited" by magnitude works for these two measured
populations, but it is a **threshold fitted to observed data, not a proof.** A link
pushed just 1 percent over its limit by *many* children rather than one would look
exactly like scenario 1. Distinguishing them in general requires the delay-based
signal, which is out of scope for this version. The important improvement is that
this is now a **demonstrated** limitation rather than an assumed one, and a
demonstrated limitation with a validated remedy is a far stronger position in a
report than an unproven worry.


### 4.5 One argument too many, the bug that looked like a missing kernel module

Passing `"cake bandwidth 95mbit"` as a **single** argument makes `tc` search for a
qdisc kind literally named `cake bandwidth 95mbit`. It fails with:

```
Specified qdisc kind is unknown
```

That error looks **exactly** like a missing kernel module. It sent the investigation
after `modprobe` instead of after the argument list, which cost real time.

**What changed.** The function `leaf_args` in `aciq/tc.py` now normalises every leaf
specification into **separate arguments**, always. A comment in that file records the
incident so it cannot be reintroduced.


### 4.6 The testbed depended on residue from a previous run

Baseline B1 failed with "Specified qdisc kind is unknown" for `cake`, even though
`modprobe sch_cake` reported success and **the identical command had passed inside the
gate script**.

**The cause.** The gate script had its own list of modules to load. `setup.sh` had
**none**. The required kernel features were present only because an earlier gate run
had happened to load them.

The principle, recorded in the project: **a testbed that depends on residue from a
previous run is not reproducible.**

**What changed.** `testbed/setup.sh` now loads all ten required modules itself and
**warns by name** if any one fails.


### 4.7 Other measured corrections

| Finding | Where it is handled |
|---|---|
| `tc -s -j class show` silently returns **empty** on this host, so every read-back looked like a mismatch | `aciq/qdisc.py`. Plain text is now primary. |
| Without `-s`, `tc class show` prints **no `Sent` line**, so every counter read 0.0 | `aciq/metrics.py` |
| Sender sockets race the listener and die with "connection refused", which looks exactly like "bulk had no effect" | `testbed/workloads/bulk.py` retries 20 times |
| A long socket read timeout silently throttles the sending cadence | `testbed/workloads/udpx.py` uses a 0.5 ms drain timeout |
| The `u32` rule **cannot** see IPv6, so IPv6 needs the `flower` rule | `aciq/tc.py`, and gate check 14 |
| Runs leak into each other: run 1's change-window timestamp vetoes run 2's first change as "rate limited" | `Harness.reset_for_run` |
| The number of tokens before `src=` in a conntrack line differs by protocol and TCP state, so requiring a fixed count **silently dropped every TCP flow**, which is most real traffic | `aciq/flowtrack.py` makes the state token optional |
| The send loop must catch up against a fixed start time, or a busy loop silently under-sends and reports a rate far below the configured one | `testbed/workloads/udpx.py` |
| Counter resets must read as zero, never as negative throughput | `aciq/metrics.py` |
| A metrics collector that crashes on malformed input loses the whole run, so parsing is tolerant and reads missing values as zero | `aciq/metrics.py`, `aciq/qdisc.py` |


## 5. What we actually measured

> **System version: v0.** See `data/baselines/v0/` and the `v0-baseline` tag.
>
> These numbers come from the system described at the top of this file:
> **DSCP-EF filtering + HTB + `fq_codel`**. The behavioural classifier did not
> run, no lease was exercised, and in scenario 3 the three video streams were
> classified **BULK** rather than ADAPTIVE.
>
> One seed per configuration. Paired Wilcoxon cannot reach p < 0.05 below 6
> pairs, so no significance claim is made — only ranges and the raw values.

Six runs, seed 42. Full results are in `data/REPORT.md`. Raw per-second data is in
`data/runs/<run name>/`.

**Scenario 1: a call plus a bulk download on a 100 Mbps link.** Milliseconds, lower
is better.

| System | p50 | p95 | p99 | jitter |
|---|---|---|---|---|
| ACIQ | 0.259 | **0.345** | **0.410** | **0.043** |
| B0, `pfifo` | **120.051** | 120.428 | 121.355 | 0.788 |
| B1, `cake` | **0.257** | 0.409 | 0.513 | 0.065 |

**The verdict, stated exactly as measured.** ACIQ **loses at p50 to cake by 0.002
milliseconds**, which is a statistical tie, and **beats both at p95, p99 and
jitter.** That loss appears in the report and in the table, not buried in a footnote.
That is the entire point.

**Scenario 3: three TVs plus a gaming session.** Milliseconds, lower is better.

| System | p50 | p95 | p99 | jitter |
|---|---|---|---|---|
| ACIQ | **0.219** | **0.455** | 1.268 | 0.381 |
| B0, `pfifo` | 0.465 | 33.556 | 33.720 | 5.816 |
| B1, `cake` | 0.451 | 0.606 | **0.819** | **0.168** |

**The verdict.** ACIQ beats both at p50 and p95, and **loses at p99 and jitter to
cake.** Reported plainly, in the same way.

**The honest headline.** ACIQ's win over `pfifo` is **catastrophic and
unambiguous**: 120 ms down to 0.26 ms at the median in scenario 1, and 33.7 ms down
to 1.3 ms at p99 in scenario 3. Against `cake`, ACIQ is **competitive rather than
dominant**. It wins the tail in scenario 1 and wins the median in scenario 3, and
loses p99 and jitter in scenario 3.

**What has not been measured yet.**

- Capacity adaptation. Scenario 2, the 100-to-20 drop, was never run to completion,
  so there is no adaptation-time or policy-change-stability result.
- Lease behaviour. The lease code and its mathematics are tested, but no lease has
  been exercised on the live testbed yet.
- Classification accuracy against ground truth.
- CPU overhead figures.
- In scenario 3, ACIQ's estimator reads "not available", which means **M2 never
  reached saturation in that scenario.**
- One run directory, `s1_iso_during_call__b1_cake95__static__seed42`, has no
  `result.json`. That run was interrupted, and the existing report predates it.


## 6. Honest limitations

These are stated up front because they are real.

1. **The slow line is an `htb` token-bucket emulation, not real DSL, cable or
   fiber.** It does not model ISP overhead or modem behaviour.
2. **Counters only see a bottleneck that is *on the router*.** In a real home the
   bottleneck is usually the modem or the ISP side, where router counters show
   nothing at all. A real product needs a delay-based signal for this. A validated
   remedy is documented, an unmarked probe giving about an 8 times delay rise, but it
   is not in this version.
3. **Idle links.** Passive estimation is only valid while the link is busy. Idle
   samples decay the confidence rather than inventing a number.
4. **Self-generated traffic.** Classification accuracy is measured on traffic this
   project created itself, so it will look better than on real homes. The
   **UDP/443 case, a call versus a download, remains genuinely unresolved** and is
   reported as a measured residual rather than hidden.
5. **`cake` may win**, and it did, at two percentiles.
6. **Only 2 runs per system, 1 seed.** Paired Wilcoxon needs at least 6 pairs to
   reach p below 0.05 at all, so the report gives ranges only, with no p-values.
7. **Out of scope:** Wi-Fi airtime and WMM, ISP-side policing, TR-069 and TR-369,
   certification, speeds above 1 Gbps, encrypted DNS, QUIC port hiding, and real
   customer-premises hardware.
8. **Missing documents.** Both `PLAN.md` and `README.md` refer to `docs/setup.md`,
   `docs/limitations.md` and `docs/licenses.md`. None of those three exist yet.
9. **`README.md` is out of date.** It states 152 tests, there are 260. It also says
   no experimental results exist, but both the 14-check gate and six runs have
   completed.


## 7. One-paragraph summary

A home's internet pipe is shared by a call, three TVs, a game and a backup download,
and because routers build **large queues**, the backup's thousand packets end up
sitting in front of the call's packets, which turns a 100 Mbps line into a 120 ms
call. Existing routers cannot fix this, because static priority rules cannot know
what matters **at this moment**, because they are configured with a bandwidth number
that may be a lie, and because their "boost this device" buttons have neither a time
limit nor a minimum guarantee, so one person can permanently starve the household.
**ACIQ** fixes this in five steps. It **classifies** each connection using only
headers and counter behaviour, never touching a payload, and says "I don't know"
rather than guessing. It **estimates the real capacity** from the link's own
congestion counters, and is forbidden from ever reading the configured rate so that
its own test cannot be faked. It **splits the link** by weight with a **floor that is
never removed**, so no class is ever starved. It **lets a user grant a lease**, a
bounded, weighted, **self-expiring** boost on its own class, so a forgotten request
cannot harm anyone. And it wraps every change in a **shield** that vetoes any plan
breaching a floor or an invariant, verifies that the kernel did what it was told,
rolls back to an **escalating safe state** on any fault, and recovers automatically
with backoff. Every one of those design decisions is justified by a **measurement**,
including the 28.5 Mbps that proved ceilings must be clamped to capacity, the empty
JSON output that proved counters must be read as text, the probe that measured no
signal at all, and the death spiral that collapsed 100 Mbps to 7.2 Mbps and taught
us that only the **parent's** overlimit rate means the link is genuinely full.