"""M1 — flow classification.

Pure decision logic: (flow features, capacity) -> (class, confidence, evidence).

**Wiring.** `classify()` runs on the live path: `closedloop.decide()` calls it
and then applies `finalise()` (the abstention gate — below `MIN_CONFIDENCE`
everything becomes `UNKNOWN`), `harness.enforce()` reaches `decide()` with the
`FlowFeatures` that `flowtrack` observed, and `experiment._steer()` drives that
chain once per tick. `FlowFeatures` itself lives in `aciq.features`; this
module re-exports it because every existing call site imports it from here.

**Deliberate constraint: the classifier never keys on the test generators' own
ports.** Our workloads listen on 5001-5004; classifying those would give 100%
accuracy on every run and mean nothing. Stage A uses only signals a real
deployment could rely on — DSCP EF and a small table of well-known signalling
ports. Everything else comes from Stage B behaviour.

---

## The seven classes and what separates them (measured, not assumed)

Thresholds here came from running the test generators and sampling at the same
200 ms tick `FlowTracker` uses:

| generator | class                  | Mbps  | duty | burstiness |
|-----------|------------------------|-------|------|------------|
| call      | video_call_voice       | 0.09  | 1.00 | 0.16       |
| video     | adaptive_video_streaming | 4.69 | 1.00 | 0.47      |
| bulk      | bulk_download          | 88.14 | 1.00 | 0.17       |

Interactive gaming, software_update and cloud_backup have **no generator** (a
known gap — see the note below and the acceptance TODO). They are covered by
rule logic only, on signals real deployments can carry, and their accuracy is
not yet measured against real traffic.

**Duty cycle does not separate anything — it is 1.00 for all three**, because
every generator emits continuously at a target rate. An earlier design proposed
separating streaming from bulk by on/off pattern; measured, that would have
separated nothing.

**Rate separates the measured three cleanly.** Each threshold matches what the
word actually means:

- **bulk_download is relative** — "bulk" is a claim about the link. The same
  88 Mbps transfer is a hog on 100 Mbps and a nobody on 1 Gbps, so
  `BULK_MIN_CAPACITY_FRAC` is a fraction of measured capacity.
- **adaptive_video_streaming is absolute** — a stream does not stop being a
  stream because the link got faster, so `STREAMING_MIN_MBPS` is a fixed Mbps
  figure. An earlier version made this relative too (2% of capacity) and
  classified the measured 4.69 Mbps stream as UNKNOWN on a 1 Gbps link. A
  1080p stream on a fast line received no class at all.

The consequence is checked directly in `test_classify.py`: the same three flows
must classify identically at 10, 100 and 1000 Mbps.

## The unmeasured classes — stated as a limit, not hidden

- **interactive_gaming** needs per-packet timing (regular small packets at
  tens of packets per second). That is only available from the header observer
  (`aciq.observer`); conntrack alone cannot see it, so any gaming verdict is
  refused where the extended fields are absent — the rule never guesses.
- **cloud_backup** needs direction: an upstream-biased TCP upload rule. The
  conntrack fallback reports only totals today (rx=that total, tx=0), so
  `down_share` is None there and the rule cannot fire; it fires only where the
  observer provided real direction split.
- **software_update vs adaptive_video_streaming** is the weakest separation in
  the rule base: a chunked stream shows a higher CV of byte increments
  (measured ~0.47 for the video generator) while a constant-rate update is
  smooth. When burstiness is unknown the rule answers STREAMING — the
  default that abandons the smallest class — and never claims an update on
  unknown evidence.

**Caveat to state in any accuracy report:** `generators/` models a stepped
ladder, so measured separation here will look cleaner than real streaming,
whose rate drifts smoothly. Accuracy measured on this traffic is optimistic.

## DSCP is treated as a claim, not a fact

A source can set any DSCP value it likes, so `dscp == EF` alone must not be
enough. When a source claims EF but its *measured rate* says otherwise, the two
signals conflict: confidence drops, the flow is not privileged, and the
source's EF trust is decayed so it cannot self-promote indefinitely.

Conflict is judged on **rate**, not packet size. An earlier rule demoted large
packets while claiming EF; that would have broken real video calls, which
routinely carry 1200-1500 byte packets. Packet size now only separates *small*
interactive media from *large* media, and never overrides a rate conflict.
"""

from __future__ import annotations

from .features import FlowFeatures
from .model import Classification, TrafficClass

__all__ = ["FlowFeatures", "TrustStore", "classify", "finalise", *[
    name for name in (
        "DSCP_EF", "INTERACTIVE_PORTS", "BULK_PORTS", "MIN_CONFIDENCE",
        "BULK_MIN_CAPACITY_FRAC", "EF_PLAUSIBLE_MAX_MBPS",
        "EF_MIN_ASYMMETRY", "STREAMING_MIN_MBPS", "ADAPTIVE_MIN_MBPS",
        "MIN_AGE_S", "EF_SLOW_CONFLICT_MBPS",
        "EF_FAST_CONFLICT_CAPACITY_FRAC", "INTERACTIVE_MAX_AVG_PACKET",
        "MIN_MEDIA_PACKET_BYTES", "MIN_PACKETS", "TRUST_DECAY_FACTOR",
        "MIN_EF_TRUST", "MAX_TRUST_SOURCES", "GAMING_MAX_MEDIAN_PKT_BYTES",
        "GAMING_MIN_PPS", "GAMING_MIN_REGULARITY", "GAMING_MAX_RATE_MBPS",
        "UPLOAD_BIAS", "CHUNKED_BURSTINESS", "UPDATE_KNOWN_SMOOTH_MBPS",
    )]]

#: DSCP EF. Real VoIP/video endpoints mark interactive media EF.
DSCP_EF = 46

#: Well-known signalling ports. Deliberately tiny: this is not the main signal.
INTERACTIVE_PORTS = frozenset({3478, 5060, 5061, 5349})
BULK_PORTS = frozenset({873, 3389})  # rsync, RDP-ish bulk

#: Confidence below this means the class is refused and the flow is UNKNOWN.
#: Never guessed.
MIN_CONFIDENCE = 0.5

#: Declared 2026-10-26 (docs/evidence/task2-params.md #9): a strict-class
#: claim that only reached tier B and carries less confidence than this is
#: hedged to the fair best-effort leaf instead of steered into the strict
#: class. 0.60 clears the declarations the rulebase asserts at 0.60 and
#: above (streaming 0.60, bulk 0.75, port-backed interactive 0.85, mature EF
#: 0.95) and hedges exactly the shape-only claims measured too weak to fire
#: a per-flow priority (small-media video_call at 0.55, software_update at
#: 0.55). Operator corrections and leases are never hedged.
STRICT_MIN_CONFIDENCE = 0.60

#: Tier "P" marks a PROVISIONAL claim (docs/evidence/task2-params.md #8): a
#: first-packet verdict from an unambiguous mark or public signalling port,
#: issued before `MIN_AGE_S` maturity. It routes to the class's own
#: per-flow fq_codel leaf, and the mature rules decide the final class from
#: the moment the per-tick evidence clears them.
PROVISIONAL_TIER = "P"

# ---------------------------------------------------------------------------
# Rate thresholds, as a FRACTION OF MEASURED CAPACITY
# ---------------------------------------------------------------------------
#: A flow consuming at least this share of the link is a bulk_download.
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
#: adaptive_video_streaming (streaming media).
#:
#: ABSOLUTE, unlike the bulk threshold. An earlier version made this relative too
#: (2% of capacity), which classified a 4.69 Mbps stream as UNKNOWN on a
#: 1 Gbps link, because 4.69 Mbps is only 0.5% there. A 1080p stream on a fast
#: line would have received no class at all. A stream's own rate does not stop
#: being a stream because the link got faster, so neither does this threshold.
STREAMING_MIN_MBPS = 0.5

#: Historical name kept as an alias: the old docs and some tool code still say
#: ADAPTIVE. It now points at the same threshold.
ADAPTIVE_MIN_MBPS = STREAMING_MIN_MBPS

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

# ---------------------------------------------------------------------------
# interactive_gaming — needs the header observer, conntrack cannot see it
# ---------------------------------------------------------------------------
#: A game's packets are small: median wire size stays under ~120 B (payload
#: 10-60 B plus UDP/IP headers). Call audio is heavier (~100-250 B with
#: RTP+headers) but overlaps; size alone separates a *fraction* of games, so
#: gaming requires the timing hints as well and is otherwise never claimed.
GAMING_MAX_MEDIAN_PKT_BYTES = 120.0

#: A game fires 25+ packets per second (20 Hz game state, 60 Hz at the top
#: end). Call audio is ~50 pps at 20 ms sampling... at the same order. Gaming
#: claims only clear the timing hints together, and confidence stays modest.
GAMING_MIN_PPS = 25.0

#: Regular emission: 1 - CV of inter-arrival times. A game ticks metronomically
#: (>= 0.7); a call's speech burst breaks that. When the hint is unavailable
#: the gaming branch is never taken.
GAMING_MIN_REGULARITY = 0.5

#: A game is bandwidth-light. Above this the flow is a stream or a transfer,
#: whatever its packets look like.
GAMING_MAX_RATE_MBPS = 5.0

# ---------------------------------------------------------------------------
# cloud_backup / software_update — direction and smoothness hints
# ---------------------------------------------------------------------------
#: A backup is upstream-biased: if the request direction carries this share of
#: the flow's bytes and it is a sustained TCP stream, it is a cloud_backup.
UPLOAD_BIAS = 0.8

#: Chunked streaming produces a high CV of byte increments (video generator
#: 0.47). A *known-smooth* TCP mid-rate stream below this CV is claimed as a
#: software update; when the CV is unknown the streaming answer is kept.
CHUNKED_BURSTINESS = 0.3

#: A software update is a heavyweight download: a mere trickle does not get a
#: update claim just because it is smooth. Matches STREAMING_MIN_MBPS today.
UPDATE_KNOWN_SMOOTH_MBPS = STREAMING_MIN_MBPS

#: Trust decay. A source must mis-claim EF this many times before it stops
#: being believed; each miss multiplies its trust.
TRUST_DECAY_FACTOR = 0.5
MIN_EF_TRUST = 0.25

#: Hard cap on the number of sources the trust store remembers, so a long run
#: with source churn (NAT, DHCP, a spoofing attacker) cannot grow the store
#: without limit. Same scale as the API's MAX_RATE_CLIENTS: this is a memory
#: bound chosen for the box, not a measurement of any network.
MAX_TRUST_SOURCES = 1024


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


def _looks_like_game(f: FlowFeatures) -> bool:
    """The gaming shape, strictly.

    Every one of these needs the header observer's extended hints. With a bare
    conntrack record (``pkt_size_median``/``iat_regularity``/``pps`` all None)
    the answer is False — gaming is never claimed from summary counters alone,
    because call audio sits inside the same size pps and would misclassify.
    """
    if f.pkt_size_median is None or f.iat_regularity is None or f.pps is None:
        return False
    if f.pkt_size_median > GAMING_MAX_MEDIAN_PKT_BYTES:
        return False
    if f.iat_regularity < GAMING_MIN_REGULARITY:
        return False
    if f.pps < GAMING_MIN_PPS or f.rate_mbps > GAMING_MAX_RATE_MBPS:
        return False
    return f.rate_mbps >= 0.0


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

    # ---- not enough history yet --------------------------------------------
    if not mature:
        # Provisional (declared, #8): an unambiguous MARK or public signalling
        # PORT claims its class from the first packet, when the claim is one
        # the mature rule would also grant on rate evidence. Confidence 0.50,
        # tier "P"; the hedge (#9) leaves tier P alone and the per-tick
        # maturity gate decides the final class. A gaming-shaped flow is
        # pulled out first, exactly as the mature EF rule does, and a gaming
        # claim needs its timing hints like the mature one does. A flow
        # without such a signal stays in the default class, whose leaf is
        # per-flow fair.
        if _looks_like_game(f) and f.dscp == DSCP_EF:
            return Classification(
                flow=f.flow, cls=TrafficClass.GAMING, confidence=0.50,
                tier=PROVISIONAL_TIER,
                evidence=(
                    "provisional before maturity: dscp=ef, gaming shape "
                    f"(median {f.pkt_size_median:.0f}B @ {f.pps:.0f}pps)"),
            )
        if ((f.dscp == DSCP_EF and f.rate_mbps <= EF_PLAUSIBLE_MAX_MBPS)
                or (f.flow.dport in INTERACTIVE_PORTS
                    and f.rate_mbps <= EF_PLAUSIBLE_MAX_MBPS)):
            return Classification(
                flow=f.flow, cls=TrafficClass.VIDEO_CALL, confidence=0.50,
                tier=PROVISIONAL_TIER,
                evidence=(
                    "provisional before maturity: "
                    + (f"dscp=ef({DSCP_EF})" if f.dscp == DSCP_EF
                       else f"interactive port {f.flow.dport}")
                    + f", rate {f.rate_mbps:.3f} Mbps, age "
                    f"{f.age_s:.1f}s pkts {f.packets}"),
            )
        # Not enough evidence yet. Every flow starts here, which is why an
        # unmarked flow spends its first ~2 s in the default class. Stated as a
        # limitation rather than hidden.
        return Classification(
            flow=f.flow, cls=None, confidence=0.35, tier="C",
            evidence=(f"immature: age={f.age_s:.1f}s pkts={f.packets} "
                      f"(need {MIN_AGE_S}s and {MIN_PACKETS} pkts)"),
        )

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
            # leaving it unclassified -- it is plainly bulk_download.
            #
            # Confidence is the RATE confidence, not a trust-scaled value: a
            # saturating flow is bulk however little we trust the source that
            # labelled it. Trust still decays, and still gates future EF claims.
            t = trust.record_miss(source)
            return Classification(
                flow=f.flow, cls=TrafficClass.BULK_DOWNLOAD, confidence=0.75,
                tier="B",
                evidence=(
                    f"dscp/rate conflict: ef claimed but rate "
                    f"{f.rate_mbps:.2f} Mbps is {frac:.2f} of capacity; mark "
                    f"rejected, demoted to bulk_download on rate evidence; "
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
            # Among plausible-EF flows, pull gaming out where the extended
            # hints say so. Without them (conntrack-only path) this is a video
            # call, which is exactly what the legacy behaviour covered.
            if _looks_like_game(f):
                return Classification(
                    flow=f.flow, cls=TrafficClass.GAMING, confidence=conf,
                    tier="A", evidence=(
                        f"dscp=ef({DSCP_EF}), trust={t:.2f}, gaming shape "
                        f"(median {f.pkt_size_median:.0f}B @ "
                        f"{f.pps:.0f}pps, regularity "
                        f"{f.iat_regularity:.2f})"),
                )
            return Classification(
                flow=f.flow, cls=TrafficClass.VIDEO_CALL, confidence=conf,
                tier="A", evidence=f"dscp=ef({DSCP_EF}), trust={t:.2f}",
            )
        # falls through to the maturity check and the rate rules

    # ---- Tier B: rate-relative behaviour, BEFORE the port tables ------------
    # Order matters. A saturating flow is bulk whatever port it uses, so the rate
    # rules must be consulted first; checking ports first would have called a
    # bulk transfer to port 3478 "interactive".
    #
    # Bulk_download: a single flow taking a large share of the whole link.
    # Deliberately capacity-relative and only capacity-relative. A flow is bulk
    # when it hogs *this* link: 88 Mbps is a hog on a 100 Mbps link and a nobody
    # on a gigabit. An earlier revision added an absolute floor here to make
    # bulk reachable on a wide, lightly-loaded link, and it was wrong -- it
    # contradicted this rule, broke the tests that assert the rule is
    # intentional, and made the class mean "large" instead of "hogging".
    #
    # The evaluation that appeared to show a defect was mislabelling its own
    # cases: a 21 Mbps transfer on a 100 Mbps link is not hogging, so STREAMING
    # was correct.
    if frac >= BULK_MIN_CAPACITY_FRAC:
        return Classification(
            flow=f.flow, cls=TrafficClass.BULK_DOWNLOAD, confidence=0.75,
            tier="B",
            evidence=(f"rate {f.rate_mbps:.2f} Mbps = {frac:.2f} of capacity "
                      f"(>= {BULK_MIN_CAPACITY_FRAC})"),
        )

    # cloud_backup: a sustained TCP upload. Only where the source really saw
    # direction (down_share/tx_bytes are None on the conntrack fallback) — the
    # rule waits for real evidence rather than firing on absent tx counters.
    if f.tx_bytes > 0 and f.flow.proto == "tcp":
        share_tx = f.tx_bytes / max(f.total_bytes, 1)
        if share_tx >= UPLOAD_BIAS and f.rate_mbps >= STREAMING_MIN_MBPS:
            return Classification(
                flow=f.flow, cls=TrafficClass.CLOUD_BACKUP, confidence=0.60,
                tier="B",
                evidence=(f"upstream-biased tcp upload: tx share {share_tx:.2f} "
                          f"(>= {UPLOAD_BIAS}) at {f.rate_mbps:.2f} Mbps"),
            )

    # Streaming vs software_update: a sustained TCP stream consuming a
    # meaningful but not saturating share. This is the weakest separation in
    # the rule base and it is guarded by burstiness, which conntrack-only
    # features leave unset:
    #   burstiness unknown -> STREAMING (the dominant common cause), update
    #       never claimed on unknown evidence;
    #   burstiness known and chunky (>= CHUNKED_BURSTINESS) -> STREAMING;
    #   burstiness known and smooth (< CHUNKED_BURSTINESS) -> the constant-
    #       mid-rate shape, claimed as software_update at modest confidence.
    if f.flow.proto == "tcp" and f.rate_mbps >= STREAMING_MIN_MBPS:
        if f.burstiness is None or f.burstiness >= CHUNKED_BURSTINESS:
            sub = "" if f.burstiness is None else \
                f"burstiness {f.burstiness:.2f} >= {CHUNKED_BURSTINESS}, "
            return Classification(
                flow=f.flow, cls=TrafficClass.STREAMING, confidence=0.60,
                tier="B",
                evidence=(f"steady tcp at {f.rate_mbps:.2f} Mbps "
                          f"(>= {STREAMING_MIN_MBPS}), {frac:.3f} of capacity, "
                          f"below bulk threshold; {sub}streaming"),
            )
        if f.rate_mbps >= UPDATE_KNOWN_SMOOTH_MBPS:
            return Classification(
                flow=f.flow, cls=TrafficClass.SOFTWARE_UPDATE,
                confidence=0.55, tier="B",
                evidence=(f"smooth constant-rate tcp at "
                          f"{f.rate_mbps:.2f} Mbps, burstiness "
                          f"{f.burstiness:.2f} < {CHUNKED_BURSTINESS} "
                          f"(no chunk laddering: update-shaped); user "
                          f"correction may pin streaming"),
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
            flow=f.flow, cls=TrafficClass.VIDEO_CALL, confidence=0.85,
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
            flow=f.flow, cls=TrafficClass.BULK_DOWNLOAD, confidence=0.70,
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
    #
    # Where the header observer supplied per-packet hints, a *regular, tiny,
    # frequent* flow is pulled out as interactive_gaming first (see
    # _looks_like_game); call audio and gaming are the same size, so this needs
    # the timing hint and is refused without it.
    in_media_band = (MIN_MEDIA_PACKET_BYTES <= f.avg_packet_bytes
                     <= INTERACTIVE_MAX_AVG_PACKET)
    is_game = _looks_like_game(f)
    if (f.flow.proto == "udp"
            and f.flow.dport != 443
            and f.packets >= MIN_PACKETS
            and (in_media_band or is_game)):
        if is_game:
            # Gaming-shaped flows often sit below the 100 B media floor, which
            # exists to keep tiny control traffic out of the call class; the
            # gaming decision uses its own median-size and timing evidence.
            return Classification(
                flow=f.flow, cls=TrafficClass.GAMING, confidence=0.65,
                tier="B",
                evidence=(f"small media: avg_pkt={f.avg_packet_bytes:.0f}B "
                          f"rate={f.rate_mbps:.3f} Mbps; gaming shape "
                          f"(median {f.pkt_size_median:.0f}B @ {f.pps:.0f}pps, "
                          f"regularity {f.iat_regularity:.2f})"),
            )
        return Classification(
            flow=f.flow, cls=TrafficClass.VIDEO_CALL, confidence=0.55, tier="B",
            evidence=(f"small media: avg_pkt={f.avg_packet_bytes:.0f}B "
                      f"rate={f.rate_mbps:.3f} Mbps"
                      + (f"; declined bulk-port {f.flow.dport} (port alone "
                         f"insufficient)" if f.flow.dport in BULK_PORTS
                         else "")),

        )

    # ---- Tier C: honest gaps ----------------------------------------------
    # These are classified KNOWN-UNKNOWN, never guessed: an abstention, not a
    # low-confidence guess of some class.
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
    """Refuse anything below MIN_CONFIDENCE as UNKNOWN.

    Separate from classify() so a raw score can be inspected for analysis
    without a mislabelled flow ever reaching enforcement.

    Declared 2026-10-26 (#9): a strict-class claim that never rose above tier
    B and carries less confidence than STRICT_MIN_CONFIDENCE is hedged to the
    fair best-effort leaf. The hedge NEVER touches an operator correction
    (tier X) or lease (tier L) -- intent is not inference -- and never a
    provisional claim, whose risk policy is per-flow fair routing itself.
    The would-have-been class survives in `strict_class` for the artefact.
    """
    if c.cls is not None and c.confidence >= MIN_CONFIDENCE:
        hedge = (c.tier == "B"
                 and c.confidence < STRICT_MIN_CONFIDENCE
                 and not c.hedged)
        if hedge:
            return Classification(
                flow=c.flow, cls=TrafficClass.UNKNOWN,
                confidence=c.confidence, tier=c.tier,
                evidence=f"{c.evidence} -> hedged below "
                         f"{STRICT_MIN_CONFIDENCE} to the fair best-effort "
                         f"leaf ({c.cls.name})",
                hedged=True, strict_class=c.cls.name,
            )
        return c
    return Classification(
        flow=c.flow, cls=TrafficClass.UNKNOWN, confidence=c.confidence,
        tier=c.tier, evidence=f"{c.evidence} -> below {MIN_CONFIDENCE}, "
                              f"unknown",
    )
