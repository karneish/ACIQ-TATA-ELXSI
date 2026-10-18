"""M4 — the tc tree: declarative spec and command rendering. Pure.

Separated from execution so the whole enforcement path is testable without
root. Nothing here runs a command.

Two gate-measured HTB constraints shape this module:

1. A class borrows past its parent's `rate` up to its own `ceil`. A 20 Mbps
   parent with `ceil 99/97` children delivered **28.5 Mbps**. So every ceil in
   the tree is clamped to the link capacity.
2. HTB's `default` class **cannot be changed on a live qdisc**
   ("Change operation not supported"). So changing the default means rebuilding
   the whole tree — which is why rendering always emits a complete tree rather
   than a diff, and why M9 has to be able to roll a rebuild back.

Leaf qdisc handles are derived from the classid so they are unique per device.
(An earlier draft used the same handle for two leaves, which fails EEXIST.)
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import RatePlan, TrafficClass

#: root qdisc handle and the class HTB sends unclassified traffic to
ROOT_HANDLE = "1:"
DEFAULT_CLASS = "30"

#: HTB class ids. The leased flow gets its own so a lease can be measured
#: separately from the class it resembles.
CLASS_IDS: dict[TrafficClass, str] = {
    TrafficClass.INTERACTIVE: "1:10",
    TrafficClass.ADAPTIVE: "1:20",
    TrafficClass.BULK: "1:30",
    TrafficClass.LEASED: "1:40",
}
ROOT_CLASS_ID = "1:1"
BARE_CLASS_ID = "1:"

#: Filter priorities. `tc` evaluates filters in ASCENDING priority, so a filter
#: at a higher number is consulted later -- and therefore only ever reached if
#: nothing above it matched.
#:
#: The DSCP-EF filters were previously prio 1/2, which put them ahead of
#: everything. That was harmless when mark-driven filters did not exist. Now
#: that the nftables bridge installs mark filters at prio 10-14, leaving EF at
#: 1/2 would silently pre-empt them: a flow the bridge had explicitly placed in
#: `unclassified` would still be promoted to EF priority, which is precisely the
#: evasion `marks.py` and the two-sided EF conflict rule exist to prevent.
#:
#: Shared with `bridge.py` by import, so the two cannot drift apart.
DSCP_FILTER_PRIO = {"ip": 30, "ipv6": 31}


def leaf_args(leaf) -> tuple[str, ...]:
    """Normalise a leaf qdisc spec into separate argv elements.

    A spec must never reach subprocess as ONE argument. `"cake bandwidth
    95mbit"` passed as a single token makes tc search for a qdisc kind with that
    entire string, and it fails with *"Specified qdisc kind is unknown"* — which
    looks exactly like a missing kernel module and sent the investigation after
    modprobe instead of after the argument list.
    """
    if leaf is None:
        return ()
    if isinstance(leaf, str):
        return tuple(leaf.split())
    return tuple(leaf)


@dataclass(frozen=True)
class TcClass:
    classid: str
    parent: str
    rate_mbps: float
    ceil_mbps: float
    leaf: tuple[str, ...] | str | None = None
    cls: TrafficClass | None = None

    @property
    def leaf_handle(self) -> str:
        # "1:10" -> "10:" ; "1:" -> "1:" ; keeps handles unique per device
        return self.classid.split(":", 1)[1] + ":" if ":" in self.classid else "1:"


@dataclass(frozen=True)
class TcFilter:
    priority: int
    protocol: str  # "ip" | "ipv6"
    flowid: str

    @property
    def command_tail(self) -> tuple[str, ...]:
        """u32 for IPv4, flower for IPv6: `u32 match ip dsfield` does not match
        IPv6 traffic, which is why gate check 14 uses flower."""
        if self.protocol == "ipv6":
            return ("flower", "ip_tos", "0xb8/0xfc", "flowid", self.flowid)
        return ("u32", "match", "ip", "dsfield", "0xb8", "0xfc", "flowid", self.flowid)


@dataclass(frozen=True)
class TcTree:
    """A complete qdisc tree. Always rendered whole, never diffed."""

    capacity_mbps: float
    default_class: str = DEFAULT_CLASS
    classes: tuple[TcClass, ...] = ()
    filters: tuple[TcFilter, ...] = ()

    def class_for(self, cls: TrafficClass) -> TcClass | None:
        for c in self.classes:
            if c.cls is cls:
                return c
        return None

    def total_rate(self) -> float:
        return sum(c.rate_mbps for c in self.classes if c.parent != BARE_CLASS_ID)


def _mbit(v: float) -> str:
    return f"{v:.4f}mbit"


def build_tree(
    plan: RatePlan,
    leaf: tuple[str, ...] | str = "fq_codel",
    with_filters: bool = True,
) -> TcTree:
    """Render a RatePlan into a complete tc tree.

    Ceilings come from the plan and are clamped to capacity regardless of what
    it asked for: a ceil above the bottleneck is a measured way to exceed the
    link (28.5 Mbps on a 20 Mbps parent).

    They were previously *discarded* here -- `min(cap, cap)`, literally the
    capacity twice -- so any ceiling computed by build_plan never reached the
    kernel. Measured consequence: bulk carried 19.88 Mbps against a planned
    ceil of 17, the bottleneck queue stayed pinned at its limit, and the call's
    p95 came out identical for FIFO, CAKE and ACIQ. A policy computed
    correctly and then thrown away by the renderer is worse than not computing
    it, because the tests on the plan still pass.
    """
    cap = plan.capacity_mbps
    classes: list[TcClass] = [
        TcClass(ROOT_CLASS_ID, BARE_CLASS_ID, cap, cap, cls=None)
    ]
    for cls, rate in plan.rates.items():
        cid = CLASS_IDS.get(cls)
        if cid is None:
            continue
        # Fall back to capacity if the plan somehow has no ceiling for a class
        # it has a rate for, so this can never produce an unenforceable plan.
        ceil = plan.ceils.get(cls, cap)
        classes.append(
            TcClass(
                classid=cid,
                parent=ROOT_CLASS_ID,
                rate_mbps=rate,
                ceil_mbps=min(cap, max(rate, ceil)),
                leaf=leaf_args(leaf),
                cls=cls,
            )
        )

    filters: list[TcFilter] = []
    if with_filters and TrafficClass.INTERACTIVE in plan.rates:
        filters.append(TcFilter(DSCP_FILTER_PRIO["ip"], "ip",
                                CLASS_IDS[TrafficClass.INTERACTIVE]))
        filters.append(TcFilter(DSCP_FILTER_PRIO["ipv6"], "ipv6",
                                CLASS_IDS[TrafficClass.INTERACTIVE]))

    return TcTree(capacity_mbps=cap, classes=tuple(classes), filters=tuple(filters))


def render(tree: TcTree, dev: str = "veth-lan", ns: str | None = "router") -> list[tuple[str, ...]]:
    """Render the tree to tc argument vectors, in dependency order.

    Order matters: root qdisc, then classes parent-before-child, then filters,
    then leaf qdiscs. tc needs each parent to exist before its child.
    """
    pre = ("ip", "netns", "exec", ns) if ns else ()
    cmds: list[tuple[str, ...]] = []

    cmds.append(pre + ("tc", "qdisc", "add", "dev", dev, "root",
                       "handle", ROOT_HANDLE, "htb", "default", tree.default_class))
    for c in sorted(tree.classes, key=lambda x: (len(x.parent), x.classid)):
        cmds.append(pre + ("tc", "class", "add", "dev", dev, "parent", c.parent,
                           "classid", c.classid, "htb",
                           "rate", _mbit(c.rate_mbps), "ceil", _mbit(c.ceil_mbps)))
    for f in sorted(tree.filters, key=lambda x: x.priority):
        cmds.append(pre + ("tc", "filter", "add", "dev", dev, "parent", ROOT_HANDLE,
                           "protocol", f.protocol, "prio", str(f.priority),
                           *f.command_tail))
    for c in tree.classes:
        spec = leaf_args(c.leaf)
        if spec:
            cmds.append(pre + ("tc", "qdisc", "add", "dev", dev, "parent", c.classid,
                               "handle", c.leaf_handle, *spec))
    return cmds


# --------------------------------------------------------------------------
# read-back verification
# --------------------------------------------------------------------------
@dataclass
class Mismatch:
    classid: str
    field: str
    expected: float
    actual: float


def parse_class_state(state) -> dict[str, dict[str, float]]:
    """Normalise read-back state into {classid: {rate, ceil}} in **Mbps**.

    Accepts the ClassState mapping produced by aciq.qdisc (text or JSON
    sourced). Values are None when the reader did not report them, so
    verification can distinguish "wrong rate" from "reader cannot see rates".
    """
    out: dict[str, dict[str, float]] = {}
    for cid, cs in state.items():
        entry: dict[str, float] = {}
        if getattr(cs, "rate_mbps", None) is not None:
            entry["rate"] = cs.rate_mbps
        if getattr(cs, "ceil_mbps", None) is not None:
            entry["ceil"] = cs.ceil_mbps
        out[cid] = entry
    return out


#: 1% tolerance. tc rounds to whatever precision it likes, so exact equality
#: would fail on formatting alone.
RATE_TOLERANCE = 0.01


def verify(tree: TcTree, state: dict[str, dict[str, float]],
           unverifiable: list | None = None) -> list[Mismatch]:
    """Compare intended tree against read-back state. Empty list means match."""
    unverifiable = [] if unverifiable is None else unverifiable
    bad: list[Mismatch] = []
    for c in tree.classes:
        got = state.get(c.classid)
        if got is None:
            bad.append(Mismatch(c.classid, "present", 1.0, 0.0))
            continue
        for key, want_mbps in (("rate", c.rate_mbps), ("ceil", c.ceil_mbps)):
            have = got.get(key)
            if have is None:
                # The reader cannot see this field. That is a weaker guarantee,
                # not a wrong rate, so it must not fail the whole verification —
                # but it must also not read as a pass, so it is recorded.
                unverifiable.append((c.classid, key))
                continue
            want = want_mbps
            if abs(have - want) > RATE_TOLERANCE * max(want, 1.0):
                bad.append(Mismatch(c.classid, key, want_mbps, have))
    return bad


def canon_classid(cid: str) -> str:
    """Normalise a class handle to `major:minor` with no leading zeros.

    tc prints minor handles zero-padded and unpadded depending on version and
    on how the class was created (`1:0010` vs `1:10`), so a literal string
    comparison reports a mismatch where the kernel state is identical. This is
    the one textual difference treated as equivalent; nothing else is.
    """
    cid = str(cid).strip()
    if ":" not in cid:
        return cid
    major, _, minor = cid.partition(":")
    minor = minor.strip()
    if minor.isdigit():
        minor = minor.lstrip("0") or "0"
    return f"{major.strip()}:{minor}"


def compare_states(expected: dict, actual: dict,
                   tol: float | None = None) -> tuple[list[Mismatch], list]:
    """Compare two canonical read-back states. -> (mismatches, unverifiable).

    Used for rollback, where both sides are *observations* rather than an
    intention and a measurement, so the direction of the comparison differs
    from `verify()` and the failure modes differ with it:

      - a class present in `actual` but not `expected` is **residue**, and is
        reported. Rollback that leaves an extra class behind has not restored
        the prior state even though every expected class is correct.
      - a field the reader cannot see is *unverifiable*, which is reported
        separately and must not be counted as either a match or a mismatch.
      - a class missing entirely from `actual` is a mismatch, not a shrug.

    Rounding is absorbed by the same 1% tolerance `verify()` uses, so a kernel
    that reports 6.0 where 5.9997 was asked for is not a defect.
    """
    tol = RATE_TOLERANCE if tol is None else tol
    bad: list[Mismatch] = []
    unver: list[tuple[str, str]] = []
    exp = {canon_classid(k): v for k, v in expected.items()}
    act = {canon_classid(k): v for k, v in actual.items()}
    for cid, want in exp.items():
        got = act.get(cid)
        if got is None:
            bad.append(Mismatch(cid, "present", 1.0, 0.0))
            continue
        for key in ("rate", "ceil"):
            if want.get(key) is None:
                continue
            have = got.get(key)
            if have is None:
                unver.append((cid, key))
                continue
            w = want[key]
            if abs(have - w) > tol * max(w, 1.0):
                bad.append(Mismatch(cid, key, w, have))
    for cid in act:
        if cid not in exp:
            bad.append(Mismatch(cid, "residual", 0.0, 1.0))
    return bad, unver


def unverified_fields(tree, state) -> list[tuple[str, str]]:
    """(classid, field) pairs the reader could not confirm. Reported, not hidden."""
    out = []
    for c in tree.classes:
        got = state.get(c.classid)
        if got is None:
            continue
        for key in ("rate", "ceil"):
            if got.get(key) is None:
                out.append((c.classid, key))
    return out
