"""M1 — flow classification.

Pure decision logic: (flow features, capacity) -> (class, confidence, evidence).

**Wiring.** `classify()` runs on the live path: `closedloop.decide()` calls it
and then applies `finalise()` (the abstention gate — below `MIN_CONFIDENCE`
everything becomes UNCLASSIFIED), `harness.enforce()` reaches `decide()` with
the `FlowFeatures` that `flowtrack` observed, and `experiment._steer()` drives
that chain once per tick. An earlier version of this docstring said the module
was test-only and that only the DSCP-EF filter decided classes; both claims are
obsolete. What remains true is the constraint below.

**Deliberate constraint: the classifier never keys on the test generators' own
ports.** Our workloads listen on 5001-5004; classifying those would give 100%
accuracy on every run and mean nothing. Stage A uses only signals a real
deployment could rely on — DSCP EF, and a small table of well-known signalling
ports. Everything else comes from Stage B behaviour.

---

## What separates the three classes (measured, not assumed)

Thresholds here came from running the generators and sampling at the same
200 ms tick `FlowTracker` uses:

| generator | Mbps | duty cycle | burstiness |
|---|---|---|---|
| call  |  0.09 | 1.00 | 0.16 |
| video |  4.69 | 1.00 | 0.47 |
| bulk  | 88.14 | 1.00 | 0.17 |

**Duty cycle does not separate anything — it is 1.00 for all three**, because
every generator emits continuously at a target rate. An earlier design proposed
separating ADAPTIVE from BULK by on/off pattern; measured, that would have
separated nothing.

**Rate separates them cleanly.** Each threshold is then chosen to match what the
word actually means:

- **bulk is relative** — "bulk" is a claim about the link. The same 88 Mbps
  transfer is a hog on 100 Mbps and a nobody on 1 Gbps, so
  `BULK_MIN_CAPACITY_FRAC` is a fraction of measured capacity.
- **adaptive is absolute** — a stream does not stop being a stream because the
  link got faster, so `ADAPTIVE_MIN_MBPS` is a fixed Mbps figure. An earlier
  version made this relative too (2% of capacity) and classified the measured
  4.69 Mbps stream as UNCLASSIFIED on a 1 Gbps link, where it is only 0.5% of
  capacity. A 1080p stream on a fast line received no class at all.

The consequence is checked directly in `test_classify.py`: the same three flows
must classify identically at 10, 100 and 1000 Mbps.

Burstiness is recorded but **not used as a discriminator**: video's 0.47 is an
artifact of the 6-second ABR ladder stepping, not a property of real streaming.

**Caveat to state in any accuracy report:** `video.py` models a stepped ladder,
so measured separation here will look cleaner than real streaming, whose rate
drifts smoothly. Accuracy measured on this traffic will be optimistic.

## DSCP is treated as a claim, not a fact

A source can set any DSCP value it likes, so `dscp == EF` alone must not be
enough. When a source claims EF but its *measured rate* says otherwise, the two
signals conflict: confidence drops, the flow is not privileged, and the source's
EF trust is decayed so it cannot self-promote indefinitely.

Conflict is judged on **rate**, not packet size. An earlier rule demoted large
packets while claiming EF; that would have broken real video calls, which
routinely carry 1200-1500 byte packets. Packet size now only separates *small*
interactive media from *large* media, and never overrides a rate conflict.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import Classification, Flow, TrafficClass

#: DSCP EF. Real VoIP/video endpoints mark interactive media EF.
DSCP_EF = 46

#: Well-known signalling ports. Deliberately tiny: this is not the main signal.
INTERACTIVE_PORTS = frozenset({3478, 5060, 5061, 5349})
BULK_PORTS = frozenset({873, 3389})  # rsync, RDP-ish bulk

#: Confidence below this means UNCLASSIFIED. Never guessed.
MIN_CONFIDENCE = 0.5

# ---------------------------------------------------------------------------
# Rate thresholds, as a FRACTION OF MEASURED CAPACITY
# ---------------------------------------------------------------------------
#: A flow consuming at least this share of the link is a bulk transfer.
#: Measured: bulk ran at 88.14 Mbps on a 100 Mbps shaper = 0.88.
#: RELATIVE, because "bulk" is intrinsically a claim about the link: the same
#: 88 Mbps transfer is a hog on 100 Mbps and a nobody on 1 Gbps.
BULK_MIN_CAPACITY_FRAC = 0.5

#: Interactivity plausibility, used **only** to test an EF claim -- never to
#: decide the bulk class, which stays capacity-relative by design.
#:
#: The question is "could this plausibly be a conversation?", and it has to be
#: answerable without knowing the link, because a marking is an assertion about
#: the flow, not about the bottleneck. Measured on this project's profiles:
#: call 0.09 Mbps at asymmetry 1.0, video 4.69 Mbps at 22-28, bulk 88 Mbps at
#: 400-1200. A flow far above every interactive rate *and* far more one-way
#: than any conversation is not one, whatever the link can carry.
EF_PLAUSIBLE_MAX_MBPS = 20.0
EF_MIN_ASYMMETRY = 50.00

#: A sustained TCP stream at or above this rate, that is not saturating, is
#: ADAPTIVE (streaming media).
#:
#: ABSOLUTE, unlike the bulk threshold. An earlier version made this relative too
#: (2% of capacity), which classified a 4.69 Mbps stream as UNCLASSIFIED on a
#: 1 Gbps link, because 4.69 Mbps is only 0.5% there. A 1080p stream on a fast
#: line would have received no class at all. A stream's own rate does not stop
#: being a stream because the link got faster, so neither does this threshold.
ADAPTIVE_MIN_MBPS = 0.5

#: Seconds a flow must persist before Stage B will label it.
MIN_AGE_S = 2.0

#: DSCP EF conflict is TWO-SIDED, because the interesting cases are both extremes.
#:
#: Too slow to be real media: an ABSOLUTE floor, not a fraction of capacity. A
#: legitimate call's rate does not scale with link speed -- G.711 is ~87 kbps and
#: a modern audio call ~30 kbps whether the line is 10 Mbps or 1 Gbps. An earlier
#: rule used 2% of capacity, and it flagged the *measured* 0.09 Mbps call as a
#: conflict: the rule punished exactly the traffic it was meant to protect.
EF_SLOW_CONFLICT_MBPS = 0.010

#: Too fast to be believable: claiming EF while consuming most of the link is the
#: actual evasion -- set one DSCP byte on a torrent and inherit interactive
#: weight. Measured: a claimed-EF flow at 90 Mbps on a 100 Mbps link.
EF_FAST_CONFLICT_CAPACITY_FRAC = BULK_MIN_CAPACITY_FRAC

#: Packet sizes. `INTERACTIVE_MAX_AVG_PACKET` was 600, which excluded real video
#: calls: a 720p call routinely sends 1200-1500 byte packets. The upper bound is
#: now a single MTU-sized packet, and size is never used to *demote* a claimed-EF
#: flow — only to prefer small media when the rate is ambiguous.
INTERACTIVE_MAX_AVG_PACKET = 1500
MIN_MEDIA_PACKET_BYTES = 100
MIN_PACKETS = 10

#: Trust decay. A source must mis-claim EF this many times before it stops
#: being believed; each miss multiplies its trust.
TRUST_DECAY_FACTOR = 0.5
MIN_EF_TRUST = 0.25

#: Hard cap on the number of sources the trust store remembers, so a long run
#: with source churn (NAT, DHCP, a spoofing attacker) cannot grow the store
#: without limit. Same scale as the API's MAX_RATE_CLIENTS: this is a memory
#: bound chosen for the box, not a measurement of any network.
MAX_TRUST_SOURCES = 1024


@dataclass(frozen=True)
class FlowFeatures:
    """What Stage B observed about one flow. All fields are behaviour, not identity."""

    flow: Flow
    dscp: int | None = None
    rx_bytes: int = 0
    tx_bytes: int = 0
    packets: int = 0
    age_s: float = 0.0
    avg_packet_bytes: float = 0.0
    #: coefficient of variation of per-sample byte increments. Recorded, not used
    #: as a discriminator — see the module docstring.
    burstiness: float = 0.0
    #: fraction of samples in which bytes moved. Measured 1.00 for every
    #: generator, so it is recorded but not used to separate classes.
    duty_cycle: float = 0.0
    #: user's override for this flow, if any. Takes precedence over everything.
    correction: TrafficClass | None = None

    @property
    def total_bytes(self) -> int:
        return self.rx_bytes + self.tx_bytes

    @property
    def rate_bps(self) -> float:
        return (self.total_bytes * 8) / self.age_s if self.age_s > 0 else 0.0

    @property
    def rate_mbps(self) -> float:
        return self.rate_bps / 1e6

    @property
    def asymmetry(self) -> float:
        """max(rx,tx) / min(rx,tx). 1.0 is perfectly bidirectional.

        The separator between a transfer and a conversation. Deliberately *not*
        duty cycle: measured 1.00 for every generator, because each emits
        continuously at a target rate, so it carries no information at all.
        """
        lo = min(self.rx_bytes, self.tx_bytes)
        if lo <= 0:
            return float("inf")      # strictly one-directional
        return max(self.rx_bytes, self.tx_bytes) / lo

    def looks_interactive(self) -> bool:
        """Could this plausibly be a real-time conversation?

        Rate and direction together. Rate alone would flag a large video stream;
        direction alone would flag any one-way flow including a slow one. A
        conversation is bidirectional and small, and the measured profiles leave
        a wide margin: call 0.09 Mbps / asymmetry 1.0, video 4.69 / 22-28, bulk
        88 / 400-1200.

        Used to test an *EF claim* only. It is deliberately not the bulk rule:
        bulk means hogging the link, which is relative, and these are different
        questions.
        """
        return (self.rate_mbps <= EF_PLAUSIBLE_MAX_MBPS
                and self.asymmetry <= EF_MIN_ASYMMETRY)


class TrustStore:
    """Per-source EF trust. Bounded and in-memory.

    Trust starts at 1.0. Every time a source claims EF and the observed rate
    contradicts that, trust is multiplied by TRUST_DECAY_FACTOR and floored at
    MIN_EF_TRUST. A source that repeatedly mislabels itself therefore cannot keep
    claiming interactive priority — which is the only defence against a device
    setting one DSCP byte and inheriting the best class.

    BOUNDED SOURCE SET

    The three maps are keyed by source address, and a long run can see far more
    distinct sources than any given instant has active: a busy NAT, DHCP churn,
    or an attacker varying the source. "Bounded by construction" was the claim,
    and it was false here — nothing evicted. `max_sources` closes it.

    Eviction drops the *least recently seen* source, not the least trusted. A
    stale entry's forgetting is safe because the default trust is 1.0: a source
    that stopped mislabelling and went away is indistinguishable from a new one,
    and a mislabeller that is still active keeps a fresh `last_seen` and is
    never the victim. Forgetting a *stale* entry therefore cannot help an active
    mislabeller; forgetting by trust could, by evicting a well-behaved source and
    letting a mislabeller's low entry persist.
    """

    def __init__(self, decay: float = TRUST_DECAY_FACTOR,
                 floor: float = MIN_EF_TRUST, max_sources: int = MAX_TRUST_SOURCES):
        self.decay = decay
        self.floor = floor
        self.max_sources = max(1, int(max_sources))
        self._trust: dict[str, float] = {}
        self._claims: dict[str, int] = {}
        self._misses: dict[str, int] = {}
        #: Monotonic counter of the last time each source was touched, for the
        #: bounded-eviction order. A counter rather than a wall clock because
        #: the store has no clock and does not want one.
        self._last_seen: dict[str, int] = {}
        self._clock = 0

    def __len__(self) -> int:
        return len(self._last_seen)

    def _touch(self, source: str) -> None:
        self._clock += 1
        self._last_seen[source] = self._clock
        self._evict_if_over()

    def _evict_if_over(self) -> None:
        """Forget the least-recently-seen sources until under the cap."""
        overflow = len(self._last_seen) - self.max_sources
        if overflow <= 0:
            return
        for source, _ in sorted(self._last_seen.items(), key=lambda kv: kv[1])[:overflow]:
            self._last_seen.pop(source, None)
            self._trust.pop(source, None)
            self._claims.pop(source, None)
            self._misses.pop(source, None)

    def trust(self, source: str) -> float:
        return self._trust.get(source, 1.0)

    def record_claim(self, source: str) -> None:
        self._claims[source] = self._claims.get(source, 0) + 1
        self._touch(source)

    def record_miss(self, source: str) -> float:
        self._misses[source] = self._misses.get(source, 0) + 1
        t = max(self.floor, self.trust(source) * self.decay)
        self._trust[source] = t
        self._touch(source)
        return t

    def stats(self, source: str) -> dict[str, float | int]:
        return {
            "trust": self.trust(source),
            "ef_claims": self._claims.get(source, 0),
            "ef_misses": self._misses.get(source, 0),
        }


def classify(f: FlowFeatures, capacity_mbps: float = 100.0,
             trust: TrustStore | None = None) -> Classification:
    """Decide a class and a confidence. Pure, apart from optional trust decay.

    `capacity_mbps` is the *measured* capacity from M2, never a configured rate.
    """
    # ---- a user's correction always wins -----------------------------------
    if f.correction is not None:
        return Classification(
            flow=f.flow, cls=f.correction, confidence=1.0, tier="X",
            evidence="user correction (overrides all inference)",
        )

    source = f.flow.src
    trust = trust if trust is not None else TrustStore()
    cap = max(capacity_mbps, 1e-9)
    frac = f.rate_mbps / cap
    mature = f.age_s >= MIN_AGE_S and f.packets >= MIN_PACKETS

    # ---- Tier A: a claimed DSCP mark, weighed against observed behaviour ----
    if f.dscp == DSCP_EF:
        trust.record_claim(source)

        # Too slow to be real media.
        too_slow = mature and f.rate_mbps < EF_SLOW_CONFLICT_MBPS
        # Too fast: claiming interactivity while saturating the link.
        too_fast = mature and frac >= EF_FAST_CONFLICT_CAPACITY_FRAC
        # Or not interactive *in shape*, whatever the link looks like. Without
        # this a flow marking itself EF kept interactive priority at 0.95
        # confidence while moving 80 MB in 15 kB packets with 99% one-way
        # asymmetry -- because the only test was "does it saturate the link",
        # and on a 100 Mbps link 24 Mbps does not. An EF claim is an input
        # signal, not proof.
        #
        # `looks_interactive()` tests rate and direction. A *third* signal
        # matters for the claim specifically: real-time media is RTP over UDP,
        # so a reliable TCP stream carrying MTU-sized packets is a video or
        # file transfer whatever its rate. Measured: the adversarial case is
        # tcp/443 at 2.4 Mbps with 3000-byte packets -- low and one-way, so it
        # passed rate+direction, but TCP with full-size payloads is not a
        # conversation. Requiring media shape here is what turns the one
        # high-confidence EF error into a denied claim.
        not_media_shape = (mature and f.flow.proto == "tcp"
                           and f.avg_packet_bytes > INTERACTIVE_MAX_AVG_PACKET / 2)
        not_interactive = mature and (not f.looks_interactive() or not_media_shape)

        if too_fast:
            # The mark is a lie and the measurement is unambiguous. Deny the
            # privilege AND put the flow where its rate puts it, rather than
            # leaving it unclassified -- it is plainly bulk traffic.
            #
            # Confidence is the RATE confidence, not a trust-scaled value: a
            # saturating flow is bulk however little we trust the source that
            # labelled it. Trust still decays, and still gates future EF claims.
            t = trust.record_miss(source)
            return Classification(
                flow=f.flow, cls=TrafficClass.BULK, confidence=0.75, tier="B",
                evidence=(
                    f"dscp/rate conflict: ef claimed but rate "
                    f"{f.rate_mbps:.2f} Mbps is {frac:.2f} of capacity; mark "
                    f"rejected, demoted to bulk on rate evidence; "
                    f"ef trust now {t:.2f}"
                ),
            )

        if too_slow:
            # Not privileged, and not obviously anything else either.
            t = trust.record_miss(source)
            return Classification(
                flow=f.flow, cls=None, confidence=round(0.45 * t, 4), tier="C",
                evidence=(
                    f"dscp/rate conflict: ef claimed but rate "
                    f"{f.rate_mbps:.4f} Mbps is below the "
                    f"{EF_SLOW_CONFLICT_MBPS} Mbps floor for real media; "
                    f"ef trust now {t:.2f}"
                ),
            )

        if not_interactive:
            # The claim is denied. Control falls through to the rate rules below
            # rather than asserting BULK here, because the evidence is "not
            # plausibly interactive", not "bulk": a mislabelled stream is still
            # video, and asserting bulk would be a second guess dressed as a
            # measurement. Trust still decays, so a source that repeats this
            # loses the privilege on its next claim.
            trust.record_miss(source)
        else:
            t = trust.trust(source)
            conf = 0.95 if mature else 0.70
            if t < 0.5:
                conf = min(conf, 0.60)
            return Classification(
                flow=f.flow, cls=TrafficClass.INTERACTIVE, confidence=conf,
                tier="A", evidence=f"dscp=ef({DSCP_EF}), trust={t:.2f}",
            )
        # falls through to the maturity check and the rate rules

    # ---- not enough history yet --------------------------------------------
    if not mature:
        # Not enough evidence yet. Every flow starts here, which is why an
        # unmarked flow spends its first ~2 s in the default class. Stated as a
        # limitation rather than hidden.
        return Classification(
            flow=f.flow, cls=None, confidence=0.35, tier="C",
            evidence=(f"immature: age={f.age_s:.1f}s pkts={f.packets} "
                      f"(need {MIN_AGE_S}s and {MIN_PACKETS} pkts)"),
        )

    # ---- Tier B: rate-relative behaviour, BEFORE the port tables ------------
    # Order matters. A saturating flow is bulk whatever port it uses, so the rate
    # rules must be consulted first; checking ports first would have called a
    # bulk transfer to port 3478 "interactive".
    #
    # Bulk: a single flow taking a large share of the whole link.
    # Deliberately capacity-relative and only capacity-relative. A flow is bulk
    # when it hogs *this* link: 88 Mbps is a hog on a 100 Mbps link and a nobody
    # on a gigabit. An earlier revision added an absolute floor here to make
    # bulk reachable on a wide, lightly-loaded link, and it was wrong -- it
    # contradicted this rule, broke the tests that assert the rule is
    # intentional, and made the class mean "large" instead of "hogging".
    #
    # The evaluation that appeared to show a defect was mislabelling its own
    # cases: a 21 Mbps transfer on a 100 Mbps link is not hogging, so ADAPTIVE
    # was correct. See docs/gap-closure/classifier-before-after.md.
    if frac >= BULK_MIN_CAPACITY_FRAC:
        return Classification(
            flow=f.flow, cls=TrafficClass.BULK, confidence=0.75, tier="B",
            evidence=(f"rate {f.rate_mbps:.2f} Mbps = {frac:.2f} of capacity "
                      f"(>= {BULK_MIN_CAPACITY_FRAC})"),
        )

    # Adaptive: steady TCP consuming a meaningful but not saturating share.
    # This is the class that was previously never emitted at all.
    if (f.flow.proto == "tcp"
            and f.rate_mbps >= ADAPTIVE_MIN_MBPS):
        return Classification(
            flow=f.flow, cls=TrafficClass.ADAPTIVE, confidence=0.60, tier="B",
            evidence=(f"steady tcp at {f.rate_mbps:.2f} Mbps "
                      f"(>= {ADAPTIVE_MIN_MBPS}), {frac:.3f} of capacity, "
                      f"below bulk threshold"),
        )

    # ---- Tier A fallback: well-known signalling ports -----------------------
    # Only reached once the flow is mature and demonstrably not saturating.
    # Symmetric with the bulk rule below: a port may assert a class only where
    # the observed behaviour does not contradict it. Interactive ports used to
    # grant unconditionally, which meant a 21 Mbps one-way transfer on port
    # 3478 was still handed interactive priority -- the same defect as the bulk
    # port, pointed the other way, and it survived because the bulk case was
    # the one that got reported.
    if f.flow.dport in INTERACTIVE_PORTS and f.looks_interactive():
        return Classification(
            flow=f.flow, cls=TrafficClass.INTERACTIVE, confidence=0.85,
            tier="A",
            evidence=(f"well-known interactive port {f.flow.dport} "
                      f"*and* {f.rate_mbps:.2f} Mbps / asymmetry "
                      f"{f.asymmetry:.0f}"),
        )
    if f.flow.dport in BULK_PORTS and (frac >= BULK_MIN_CAPACITY_FRAC
                                       or not f.looks_interactive()):
        # A port may *raise* priority for small, latency-sensitive traffic. It
        # may not *demote* a flow to bulk on its own: an 0.19 Mbps
        # bidirectional flow on port 873 was called bulk at 0.70 confidence,
        # which is a demotion justified by a number in a port table and nothing
        # observed. If the bulk evidence is absent the hint is declined and the
        # flow falls through to the packet-shape rules below.
        return Classification(
            flow=f.flow, cls=TrafficClass.BULK, confidence=0.70,
            tier="A",
            evidence=(f"known bulk port {f.flow.dport} *and* "
                      f"{f.rate_mbps:.2f} Mbps / asymmetry {f.asymmetry:.0f}"),
        )
    # A bulk port is not decisive on its own. Reaching this point means the
    # port said bulk and the behaviour above did not corroborate it, so the
    # port claim is declined and classification continues on the behavioural
    # evidence. It used to be assigned to a local that nothing read, which
    # meant this comment claimed the decline was "said so" when nothing said
    # anything -- the decision was made, then silently discarded. Surfacing it
    # in the evidence string below is what makes the decision auditable.

    # Interactive: small packets, low rate. Size bounds are wide enough to admit
    # a real video call (1200-1500 byte packets), not just audio.
    # udp/443 is deliberately EXCLUDED: that is QUIC, which carries video calls
    # and large downloads alike. Statistically it resembles media, but calling it
    # interactive on packet size alone would be a guess dressed as a decision.
    if (f.flow.proto == "udp"
            and f.flow.dport != 443
            and MIN_MEDIA_PACKET_BYTES <= f.avg_packet_bytes <= INTERACTIVE_MAX_AVG_PACKET
            and f.packets >= MIN_PACKETS):
        return Classification(
            flow=f.flow, cls=TrafficClass.INTERACTIVE, confidence=0.55, tier="B",
            evidence=(f"small media: avg_pkt={f.avg_packet_bytes:.0f}B "
                      f"rate={f.rate_mbps:.3f} Mbps"
                      + (f"; declined bulk-port {f.flow.dport} (port alone "
                         f"insufficient)" if f.flow.dport in BULK_PORTS
                         else "")),
        )

    # ---- Tier C: honest gaps ----------------------------------------------
    if f.flow.proto == "udp" and f.flow.dport == 443:
        return Classification(
            flow=f.flow, cls=None, confidence=0.40, tier="C",
            evidence=("udp/443 ambiguous: no dscp mark and statistics do not "
                      "separate a call from a download"),
        )

    return Classification(
        flow=f.flow, cls=None, confidence=0.30, tier="C",
        evidence=f"insufficient evidence (rate {f.rate_mbps:.2f} Mbps, "
                 f"{frac:.4f} of capacity, proto {f.flow.proto})",
    )


def finalise(c: Classification) -> Classification:
    """Demote anything below MIN_CONFIDENCE to UNCLASSIFIED.

    Separate from classify() so a raw score can be inspected for analysis
    without a mislabelled flow ever reaching enforcement.
    """
    if c.cls is not None and c.confidence >= MIN_CONFIDENCE:
        return c
    return Classification(
        flow=c.flow, cls=None, confidence=c.confidence, tier=c.tier,
        evidence=f"{c.evidence} -> below {MIN_CONFIDENCE}, unclassified",
    )