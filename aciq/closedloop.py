"""M5 -- the closed loop from observation to enforcement.

Three components existed and none of them were connected: `classify` decided a
class, `Corrections` carried user overrides, and `Bridge` installed a per-flow
tc filter. Nothing called them in sequence, so a run produced classifications
that were never enforced and `adaptive_video` reported goodput 0.0 while
labelled as steered.

This module owns the join. It is deliberately free of `tc` calls of its own --
it hands commands to `Bridge` -- and free of root, so the control logic is
testable with a fake executor.

## Why enforcement is opt-in

`enable_enforcement` is off unless asked for. Three reasons, all of them about
not surprising the reader:

* The default tree is the baseline tree. Enforcement changes the shape of what a
  run measures, so a run that silently enforced would not be comparable to the
  v0 baseline it claims to sit beside.
* A mis-wired enforcer silently diverts traffic. A run that reports numbers
  while quietly not enforcing is the failure mode this project has hit twice.
* The gate drives `Bridge` directly. If `Harness` also built one, the gate
  would no longer be testing the path a run uses.

So a run must ask for enforcement, and `Harness.enforcement_enabled` says
plainly whether it got it.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from .bridge import (
    CLASS_ADAPTIVE,
    CLASS_BULK,
    CLASS_INTERACTIVE,
    CLASS_LEASED,
    Bridge,
    FlowKey,
)
from .classify import Classification, FlowFeatures, TrustStore, classify, finalise
from .corrections import CorrectionStore
from .model import TrafficClass

#: TrafficClass -> the bridge's class constant. Read from one table rather than
#: restated: the classifier and the enforcer must never disagree about which id
#: means what, and a duplicated table is a table that will eventually disagree.
#: Note there is no UNCLASSIFIED entry, and that is deliberate: `Classification
#: .cls` is `TrafficClass | None`, and None is how the classifier says "no
#: verdict" -- confidence below 0.5 means UNCLASSIFIED, never guessed. The
#: bridge's own CLASS_UNCLASSIFIED exists to block EF promotion in the nft set
#: and is not a steering destination, so mapping it here would have been wrong.
CLASS_ID_OF = {
    TrafficClass.INTERACTIVE: CLASS_INTERACTIVE,
    TrafficClass.ADAPTIVE: CLASS_ADAPTIVE,
    TrafficClass.BULK: CLASS_BULK,
    TrafficClass.LEASED: CLASS_LEASED,
}


def key_of(f: FlowFeatures) -> FlowKey:
    """The bridge's match key for a flow.

    Only src/dst/proto/dport, deliberately. The classifier distinguishes flows by
    rate and age, but the kernel filter cannot -- a flower filter has no notion
    of either -- so the filter matches the tuple and the classifier decides
    where that tuple points.
    """
    fl = f.flow
    return FlowKey(src=fl.src, dst=fl.dst, proto=fl.proto, dport=fl.dport)


@dataclass
class Verdict:
    """What one enforcement decision did."""

    classification: Classification
    cmds: list[tuple[str, ...]] = field(default_factory=list)
    #: Name for display. None means the classifier declined to classify.
    label: str = "unclassified"
    #: True when an M7 lease, not inference, chose this class.
    leased: bool = False
    #: True when a user correction, not inference, chose the class.
    corrected: bool = False
    #: Class actually handed to the bridge, or None to remove the filter.
    class_id: int | None = None

    @property
    def cls(self) -> TrafficClass | None:
        return self.classification.cls

    @property
    def changed(self) -> bool:
        return bool(self.cmds)

    def __str__(self) -> str:
        src = "correction" if self.corrected else self.classification.tier
        return f"{self.label} ({src}, conf={self.classification.confidence:.2f})"


class ClosedLoop:
    """Turns observed features into installed filters.

    Holds the three components that must agree, so no caller has to remember the
    order or forget a step.
    """

    def __init__(
        self,
        bridge: Bridge,
        corrections: CorrectionStore | None = None,
        trust: TrustStore | None = None,
        capacity_mbps: float = 100.0,
        leases=None,
    ):
        self.bridge = bridge
        self.corrections = corrections if corrections is not None else CorrectionStore()
        # One trust store for the enforcer's lifetime. Per-call construction would
        # reset every source's trust to 1.0 on each tick, so a source that had
        # already lost trust would regain it immediately -- the decay would be
        # inert.
        self.trust = trust if trust is not None else TrustStore()
        self.capacity_mbps = capacity_mbps
        #: True when capacity_mbps came from M2's measurement rather than from
        #: what was configured on class 1:1. Recorded so a report can say which
        #: it was -- classifying against a configured rate is the error M2
        #: exists to prevent, and it should be visible when it happens anyway.
        self.capacity_is_measured = False
        #: M7 leases. None until one is handed in, so a run that never opens the
        #: intent API behaves exactly as before -- no import of intent.py's
        #: semantics, no "unleased" branch taken on every flow, every tick.
        self.leases = leases
        #: Verdicts by flow key, so a caller can see what it last decided.
        self.decisions: dict[FlowKey, Verdict] = {}

    def set_capacity(self, capacity_mbps: float, measured: bool = False) -> None:
        """Feed the capacity the classifier should reason against.

        `measured` records which kind this is. Callers should pass M2's
        measurement; the flag exists so an unavoidable configured-rate fallback
        is visible in a verdict rather than silent.

        An earlier version unconditionally reset `capacity_is_measured` to
        False right after assigning it, so every caller except the harness
        (which worked around the bug by writing the attribute directly) got a
        permanently-False flag — the exact mislabelling M2 exists to prevent.
        """
        self.capacity_mbps = capacity_mbps
        self.capacity_is_measured = bool(measured)

    def apply(self, f: FlowFeatures, now: float | None = None) -> Verdict:
        """Classify one flow and install the verdict.

        `now` is passed through to the correction store so TTL expiry is
        evaluated against the same clock the caller uses everywhere else.
        """
        # M7 first, and before corrections. A lease is a *person* asking for
        # something specific about a specific flow; a correction is a fix to the
        # classifier's reasoning about it. The lease is the more specific,
        # more recent statement of intent, so it wins -- and when it lapses the
        # correction is still there underneath.
        #
        # The lookup used to run unconditionally and overwrite the lease's
        # LEASED marker, so a correction on the same flow silently won while
        # the verdict was still stamped tier "L" with the lease's evidence --
        # the opposite of what the comment claimed, and invisible because no
        # test had a lease and a correction coexisting.
        lease = self.leases.for_flow(f.flow) if self.leases is not None else None
        if lease is not None:
            f = replace(f, correction=TrafficClass.LEASED)

        correction = None if lease is not None else self.corrections.lookup(
            f.flow, now=now)
        if correction is not None:
            # Copy rather than assign: FlowFeatures is a frozen dataclass, and
            # mutating the caller's object would leave a correction stuck on a
            # feature object the caller may reuse for the next tick -- so a
            # correction that expired would keep applying.
            f = replace(f, correction=correction.cls)

        decision = classify(f, capacity_mbps=self.capacity_mbps, trust=self.trust)
        # finalise() is the documented abstention gate: anything below
        # MIN_CONFIDENCE becomes UNCLASSIFIED. classify() happens to never
        # emit a classed verdict below 0.55 today, but relying on that is
        # relying on a constant that a future rule could quietly break — and
        # an unconfident verdict reaching enforcement is exactly what the
        # threshold exists to prevent.
        decision = finalise(decision)
        # classify() reports tier "X" for a user correction; relabel a lease so a
        # verdict can say which kind of override decided it.
        if lease is not None:
            decision = replace(decision, tier="L",
                               evidence=f"M7 lease {lease.id} on "
                                        f"{lease.ip or lease.flow}")

        # A None verdict removes the filter rather than pointing it somewhere.
        # Routing to the HTB default and routing to nowhere are the same outcome
        # for the packet, but the second leaves no state to expire, and the
        # bridge's classify_flow already models it that way.
        class_id = CLASS_ID_OF.get(decision.cls) if decision.cls is not None else None
        # .name.lower(), not .value: the enum's values are the long form
        # ("adaptive_video"), which is right in a report and wrong as a tc/diag
        # label. Kept as one expression so no caller re-derives it.
        label = decision.cls.name.lower() if decision.cls is not None else "unclassified"

        key = key_of(f)
        # A declined verdict for a flow that was never steered is a no-op on the
        # device, but `forget` issues a delete regardless -- deliberately, so a
        # fresh Bridge can release a filter it did not install. Called once per
        # flow per tick, that is a netlink round trip per immature flow per tick
        # for a filter that never existed. So the kernel is left alone unless
        # there is something on it to remove.
        if class_id is None and key.signature not in self.bridge.state.slots:
            verdict = Verdict(classification=decision, cmds=[],
                              corrected=correction is not None, class_id=None,
                              label=label, leased=lease is not None)
            self.decisions[key] = verdict
            return verdict

        cmds = self.bridge.classify_flow(key, class_id, confidence=decision.confidence)

        verdict = Verdict(classification=decision, cmds=cmds,
                          corrected=correction is not None, class_id=class_id,
                          label=label, leased=lease is not None)
        self.decisions[key] = verdict
        return verdict

    def forget(self, f: FlowFeatures) -> list[tuple[str, ...]]:
        """Stop steering a flow -- it closed, or the caller no longer has it."""
        key = key_of(f)
        self.decisions.pop(key, None)
        return self.bridge.forget(key)

    def teardown(self) -> list[tuple[str, ...]]:
        self.decisions.clear()
        return self.bridge.teardown()

#: Historical name. The module was briefly called `enforce`, which collided with
#: tests/test_enforce.py -- an unrelated suite covering the HTB tree path. Both
#: are "enforcement"; only one steers individual flows.
Enforcer = ClosedLoop
