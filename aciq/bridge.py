"""The M1 -> M4 bridge: nftables writes the packet mark, `tc fw` filters read it.

**Not yet wired into the runtime.** See `docs/WIRING_AUDIT.md`. This module is
complete and unit-tested as *command generation*; the kernel behaviour it targets
is proved by `testbed/gate.sh`, not by the test suite, because generating a
correct argv list and having the kernel honour it are different claims.

## Why the split exists

`generate_*` functions are pure: configuration in, argv tuples out. Nothing here
needs root, netlink, or a network namespace, so every field of every command can
be asserted offline. `Bridge` takes an injected `executor`, so the ordering and
error-handling logic is tested against a recorder rather than against a kernel.

That division matters because of how this project has already been bitten: a
single argv token (`"cake bandwidth 95mbit"` instead of three tokens) produced
*"Specified qdisc kind is unknown"*, which reads exactly like a missing kernel
module. Command construction is precisely where that class of bug lives, so it is
the part that gets exhaustive tests.

## Design

- **One set per class** in an nftables table, keyed on
  `(src, dst, proto, dport)`. nftables sets have no per-element data payload,
  only `timeout`/`counter`/`quota`, so a single set cannot map key -> mark.
  Five small sets beat one set with an unreadable value.
- **`flags timeout` gives mark expiry for free.** The kernel ages elements out.
  No userspace sweeper, and a crashed ACIQ cannot leave stale marks forever,
  because the kernel's timers keep running after the process dies.
- **No catch-all rule.** Only flows present in a set get marked, so unmarked
  traffic still reaches the pre-existing DSCP-EF filters. The bridge claims
  authority over what it has actually classified and no more.
- **Static `tc flower` filters**, one per class per protocol, keyed on the DSCP
  selector code the nftables rule stamps. Reclassification touches one set
  element and nothing in the tc tree.

## Why DSCP and not the packet mark

The original design had nftables write the packet **mark** and static `tc fw`
filters read it, matching the mark's class nibble. That is impossible on this
toolchain, and it was measured rather than assumed -- every spelling rejected by
iproute2 6.1.0:

    fw handle 0xNN/0x0f         fw has no `handle`
    fw mask 0xf handle 0x1      fw has no `mask`
    flower meta mark            flower has no `meta` key at all
    basic match "skb/mark ..."  not the ematch grammar
    basic ematch "..."          `basic` takes `match`, not `ematch`

An absent capability, not a syntax slip, so no argument reordering recovers it.
The alternative was per-flow `flower` filters matching the flow key directly,
which is proven working and mutates nothing -- but it costs a netlink
transaction per reclassification and gives up kernel-side expiry. That was
rejected because the churn it avoids is the entire reason the nftables-set
design existed.

So the class selector travels in DSCP, using **CSx codes**, which are reserved
for local assignment and therefore not expected to be carrying anything.
`flower ip_tos` is the reader because it is proven on this exact toolchain:
gate check 14 routes IPv6 EF traffic with `flower ip_tos 0xb8/0xfc`.

The mark is still written as well. DSCP is 6 bits and carries the class and
nothing else, while the mark additionally carries confidence, reason and lease
id -- facts that matter for the lease feature and for any later accuracy work.
Both are set, and `marks.py` remains the authority on the field layout.

## Filter priority

`tc` evaluates filters in ascending priority, so the bridge must come *before*
the DSCP-EF filters or its verdicts would never be consulted:

    10-19  bridge, mark-driven, one prio per class per protocol
    20-29  reserved
    30-31  DSCP-EF fallback (v4, v6) -- only sees traffic the bridge ignored

The consequences are deliberate and both are wanted:

- a flow the bridge placed in `unclassified` does **not** fall through to EF
  priority. That is the point of the `seen` bit in `marks.py`.
- a flow the bridge never looked at **does** fall through, so behaviour before
  the bridge existed is unchanged when the bridge is off.

## Limitation: tcp and udp only

The key uses `th dport`, which exists only for TCP and UDP. ICMP, SCTP, GRE and
IPv6 extension-header edge cases cannot be expressed in this key shape and are
not marked; they take the DSCP-EF path or the default class. Stated rather than
hidden -- a flow this bridge cannot see must not be quietly assumed to be
classified.
"""

from __future__ import annotations

import json
import subprocess
import zlib
from dataclasses import dataclass, field

from .marks import (
    CLASS_ADAPTIVE,
    CLASS_BULK,
    CLASS_INTERACTIVE,
    CLASS_LEASED,
    CLASS_UNCLASSIFIED,
    class_handle,
    encode,
)
from . import tc
from .model import TrafficClass

#: nftables table name. One table per address family.
NFT_TABLE = "aciq"

#: Hook chain. `mangle` priority (-150) is after conntrack, so `ct` state is
#: available and the mark survives to egress.
NFT_CHAIN = "prerouting"
NFT_HOOK_PRIORITY = "mangle"

#: Seconds an element lives in its set before the kernel removes it. This is the
#: whole of mark expiry: a flow that stops being classified stops being marked.
NFT_ELEMENT_TIMEOUT = "120s"

#: Classes that get a steering filter, in priority order. This tuple IS the
#: ordering, so it must be declared before steer_prio() uses .index().
MARKED_CLASSES = (CLASS_UNCLASSIFIED, CLASS_INTERACTIVE, CLASS_ADAPTIVE,
                  CLASS_BULK, CLASS_LEASED)

#: Steer-filter priority blocks. `tc` evaluates ascending, so these precede the
#: DSCP-EF fallback at prio 30-31.
#:
#: **The IPv4 and IPv6 sets need disjoint priority blocks.** `tc` requires every
#: filter sharing a priority to also share a protocol, and rejects a mismatch
#: with "Protocol mismatch for filter with specified priority". Emitting both
#: families at prios 10-14 installed the five IPv4 filters and then failed on all
#: five IPv6 ones -- caught by bridge_probe.sh as rc=2 on exactly the
#: `protocol ipv6` commands.
#:
#: `aciq.tc` already learned this lesson: its DSCP-EF filters sit at prio 1 (ip)
#: and prio 2 (ipv6) rather than both at prio 1, with a comment saying so. The
#: same lesson was not applied here, which is why it is written down now.
#: "all" is a third block, used only when protocol_filter=False collapses the
#: two families into one filter set. It still needs its own priorities for the
#: same reason, and 20-24 still precedes the EF fallback at 30.
STEER_PRIO_BASE = {"ip": 10, "ipv6": 15, "all": 20}


def steer_prio(protocol: str, class_id: int) -> int:
    """Priority for one steer filter. Disjoint per protocol by construction."""
    try:
        base = STEER_PRIO_BASE[protocol]
    except KeyError as e:
        raise BridgeError(
            f"unknown protocol {protocol!r}; expected one of "
            f"{sorted(STEER_PRIO_BASE)}") from e
    return base + MARKED_CLASSES.index(class_id)


#: Highest steer priority in use, i.e. the last of the IPv6 block. Kept for the
#: ordering assertion against DSCP_FILTER_PRIO.
MAX_STEER_PRIO = max(STEER_PRIO_BASE.values()) + len(MARKED_CLASSES) - 1

#: Per-flow steering filters, one per classified flow, all sharing one priority
#: per protocol so they form a chain and the first match wins.
#:
#: These come BEFORE the DSCP-EF fallback (30/31) so an explicit classification
#: beats the EF heuristic -- the same ordering the `seen` bit encoded in
#: marks.py, now expressed in tc instead of nftables.
FLOW_FILTER_PRIO = {"ip": 5, "ipv6": 6}

#: Handles are derived from the flow key, not allocated from a counter.
#:
#: A counter gives "never reused" only WITHIN a process, while tc's handle
#: namespace is PER DEVICE. Two Bridge instances -- or the same one restarted --
#: both allocate handle 1, and the second `tc filter add` fails with
#: "Filter already exists". Gate check 17 hit exactly that: each helper is a
#: fresh Bridge, so it restarted the counter and collided with check 16's filter.
#:
#: Deriving the handle from the key makes the bridge stateless with respect to tc:
#: any instance computes the same handle for the same flow, so `forget()` works
#: even with empty in-process state, and a restart re-adopts its own filters
#: instead of colliding with them.
MAX_FLOW_HANDLE = 0xFFFFFFFF


def handle_for(key: "FlowKey") -> int:
    """Deterministic tc filter handle for a flow. Never 0, which tc treats as
    "unassigned" and would reject or silently misplace."""
    digest = zlib.crc32("|".join(map(str, key.signature)).encode()) & MAX_FLOW_HANDLE
    return digest or 1

#: DSCP-EF fallback lives here so it can never pre-empt the bridge. Imported
#: from `tc` rather than redeclared: the bridge installs steering filters and
#: `tc` installs the EF filters into the same parent, so two copies of these
#: numbers would be two chances to get the ordering wrong in exactly the way
#: that fails silently.
DSCP_FILTER_PRIO = tc.DSCP_FILTER_PRIO

#: Set name per class id. The unclassified set is what blocks EF promotion.
SET_NAMES = {
    CLASS_UNCLASSIFIED: "unclassified",
    CLASS_INTERACTIVE: "interactive",
    CLASS_ADAPTIVE: "adaptive",
    CLASS_BULK: "bulk",
    CLASS_LEASED: "leased",
}

#: Class ids ordered by decision authority: a leased flow outranks everything,
#: then explicit interactive, then the behavioural classes. Earlier entries are
#: matched first in the nft chain, and nft takes the first match.
CLASS_PRECEDENCE = (
    CLASS_LEASED,
    CLASS_INTERACTIVE,
    CLASS_ADAPTIVE,
    CLASS_BULK,
    CLASS_UNCLASSIFIED,
)

#: DSCP selector codes used to steer traffic into an HTB class.
#:
#: **CS0-CS7 are used because nothing sends them.** They are "class selector"
#: codes, reserved precisely so an in-network agent may assign them locally.
#: AF41-AF43 would have been the other candidate and are deliberately avoided:
#: they are the network control codes, the ones a downstream network is most
#: likely to already be relying on, so overwriting them can break admission
#: control somewhere this router cannot see.
#:
#: Costs 6 bits, which is why the mark is set as well -- see `generate_rules`.
#:
#: CS0 is deliberately NOT used. DSCP 0x00 is ordinary best-effort traffic, so a
#: CS0 filter would capture every unsteered packet on the link and route it to
#: 1:30 -- which happens to be the default class, so the outcome was correct but
#: for the wrong reason, and the filter could no longer distinguish "the bridge
#: decided this is unclassified" from "the bridge never touched it". Starting at
#: CS1 means a matching filter always implies a steering decision.
CS_DSCP_VALUES = {
    CLASS_UNCLASSIFIED: 0x08,   # CS1
    CLASS_INTERACTIVE: 0x10,    # CS2
    CLASS_ADAPTIVE: 0x18,       # CS3
    CLASS_BULK: 0x20,           # CS4
    CLASS_LEASED: 0x28,         # CS5
}

#: DSCP names, for readable command lines. nftables and tc both accept these.
CS_DSCP_NAMES = {
    CLASS_UNCLASSIFIED: "cs1",
    CLASS_INTERACTIVE: "cs2",
    CLASS_ADAPTIVE: "cs3",
    CLASS_BULK: "cs4",
    CLASS_LEASED: "cs5",
}

#: DSCP occupies the top 6 bits of the TOS byte; the low 2 are ECN and must not
#: be matched. Same mask gate check 14 already proves for EF (0xb8/0xfc).
DSCP_MASK = "0xfc"

SUPPORTED_PROTOS = frozenset({"tcp", "udp"})


def _traffic_by_class() -> dict:
    return {
        CLASS_INTERACTIVE: TrafficClass.INTERACTIVE,
        CLASS_ADAPTIVE: TrafficClass.ADAPTIVE,
        CLASS_BULK: TrafficClass.BULK,
        CLASS_LEASED: TrafficClass.LEASED,
    }


_TRAFFIC_BY_CLASS = _traffic_by_class()


class BridgeError(RuntimeError):
    pass


@dataclass(frozen=True)
class FlowKey:
    """A per-flow match key. Only TCP and UDP are expressible (see module doc)."""

    src: str
    dst: str
    proto: str
    dport: int

    def __post_init__(self):
        # Normalise rather than reject: a caller reading "TCP" from config or a
        # conntrack dump should not have to know the kernel's spelling. Frozen
        # dataclass, so this needs object.__setattr__.
        if isinstance(self.proto, str) and self.proto != self.proto.lower():
            object.__setattr__(self, "proto", self.proto.lower())
        if self.proto not in SUPPORTED_PROTOS:
            raise BridgeError(
                f"proto {self.proto!r} not supported: the key uses 'th dport', "
                f"which exists only for {sorted(SUPPORTED_PROTOS)}. Such flows "
                f"are not marked and take the DSCP-EF or default path.")
        if not 0 <= self.dport <= 65535:
            raise BridgeError(f"dport {self.dport} outside 0..65535")

    def element(self, timeout: str | None = NFT_ELEMENT_TIMEOUT) -> str:
        """The nftables set element text."""
        body = f"{self.src} . {self.dst} . {self.proto} . {self.dport}"
        if timeout:
            return f"{{ {body} timeout {timeout} }}"
        return f"{{ {body} }}"

    @property
    def signature(self) -> tuple[str, str, str, int]:
        return (self.src, self.dst, self.proto, self.dport)


# --------------------------------------------------------------------------
# family-specific syntax
# --------------------------------------------------------------------------
#: In an `ip` table the address expressions are `ip saddr`/`ip daddr` and the
#: set element type is ipv4_addr; in an `ip6` table they are `ip6 saddr`/
#: `ip6 daddr` and ipv6_addr. A single `inet` table cannot express both, which
#: is why there are two tables rather than one clever one.
_FAMILY = {
    "ip": ("ipv4_addr", "ipv4_addr", ("ip", "saddr"), ("ip", "daddr"),
           ("ip", "dscp")),
    "ip6": ("ipv6_addr", "ipv6_addr", ("ip6", "saddr"), ("ip6", "daddr"),
            ("ip6", "dscp")),
}

#: The address expressions are TOKEN TUPLES, not strings. nftables parses `ip`
#: and `saddr` as separate keywords, so emitting "ip saddr" as one argv element
#: makes the kernel look for a protocol literally named "ip saddr". That is the
#: same shape of mistake as the "cake bandwidth 95mbit" bug that read as a
#: missing kernel module, which is why `test_tokenisation` exists.
_ADDRESS_TOKEN_EXCEPTIONS: frozenset[str] = frozenset({"{", "}"})


def _set_type(family: str) -> str:
    src_t, dst_t, _, _, _ = _FAMILY[family]
    return f"{src_t} . {dst_t} . inet_proto . inet_service"


# --------------------------------------------------------------------------
# pure command generation
# --------------------------------------------------------------------------

def generate_table(family: str, ns: str | None = None) -> tuple[tuple[str, ...], ...]:
    """Create (idempotently) the table and chain. `add` on an existing table is
    an error in nft, so the caller runs `delete` first -- see `Bridge.setup`."""
    pre = _netns(ns)
    return (
        pre + ("nft", "add", "table", family, NFT_TABLE),
        pre + ("nft", "add", "chain", family, NFT_TABLE, NFT_CHAIN,
               "{ type filter hook prerouting priority "
               f"{NFT_HOOK_PRIORITY}; policy accept; }}"),
    )


def generate_sets(family: str, ns: str | None = None) -> tuple[tuple[str, ...], ...]:
    """One set per class, each with kernel-side timeout support."""
    pre = _netns(ns)
    stype = _set_type(family)
    return tuple(
        pre + ("nft", "add", "set", family, NFT_TABLE, SET_NAMES[c],
               "{ type " + stype + " ; flags timeout ; timeout "
               + NFT_ELEMENT_TIMEOUT + " ; }")
        for c in MARKED_CLASSES
    )


def generate_rules(family: str, in_if: str, ns: str | None = None,
                   set_priority: bool = False) -> tuple[tuple[str, ...], ...]:
    """One rule per class, most authoritative first.

    nftables stops at the first matching rule in a chain, so the order of this
    tuple *is* the precedence. `class_precedence` therefore defines it rather
    than dict iteration order.
    """
    pre = _netns(ns)
    _, _, src_toks, dst_toks, dscp_expr = _FAMILY[family]
    cmds = []
    for c in CLASS_PRECEDENCE:
        mark = encode(c)
        cmds.append(pre + (
            "nft", "add", "rule", family, NFT_TABLE, NFT_CHAIN,
            "iifname", in_if,
            # "." is nftables' concatenation operator and is REQUIRED between the
            # expressions that make up the set key. Emitting
            #   ip saddr ip daddr meta l4proto th dport @set
            # instead of
            #   ip saddr . ip daddr . meta l4proto . th dport @set
            # parses as five separate expressions, and nft binds @set to only
            # the last one. Caught by bridge_probe.sh on a real kernel:
            # "syntax error, unexpected meta".
            *src_toks, ".", *dst_toks, ".",
            "meta", "l4proto", ".", "th", "dport",
            "@" + SET_NAMES[c],
            # The DSCP write is what tc actually reads. `ip dscp set` for IPv4,
            # `ip6 dscp set` for IPv6 -- the two families spell this differently.
            # The mark is set as well, and not only for symmetry: DSCP has 6 bits
            # and can carry the class and nothing else, while the mark also
            # carries confidence, reason and lease id. Keeping both means the
            # richer per-flow facts survive even though no tc classifier on this
            # toolchain can read them yet.
            dscp_expr[0], dscp_expr[1], "set", CS_DSCP_NAMES[c],
            "meta", "mark", "set", str(mark),
            # Optionally mirror the DSCP into skb->priority. OFF by default.
            #
            # The hypothesis was that `tc flower ip_tos` matches skb->priority
            # rather than iph->tos. It does not explain what is happening:
            # enabling this was observed in the kernel's own ruleset
            # ("meta priority set 0:18") and 1:20 still did not grow.
            #
            # It is also not free. HTB uses skb->priority as a 0-7 class
            # priority, and 0x18 is 24 -- outside that range. So mirroring the
            # DSCP there may actively confuse class selection inside HTB. Left
            # available for the isolated test in testbed/bridge_isolate.sh, which
            # can settle whether it helps or hurts, but not enabled blindly.
            *(("meta", "priority", "set", str(CS_DSCP_VALUES[c]))
              if set_priority else ()),
            # Per-rule match counter. Without it, a steering failure has two
            # indistinguishable causes -- the nft rule did not match the packet,
            # or it matched and the tc filter did not route it -- and the only
            # visible symptom was a class counter staying at zero. The counter
            # separates them in one run. nftables counters cost a few bytes per
            # rule and are readable with `nft list ruleset`.
            "counter",
        ))
    return tuple(cmds)


def generate_add_element(family: str, key: FlowKey, class_id: int,
                         confidence: float = 0.0, reason: int = 0,
                         lease_id: int = 0, timeout: str | None = NFT_ELEMENT_TIMEOUT,
                         ns: str | None = None) -> tuple[str, ...]:
    """Mark a flow. The mark is baked into the rule, so the element carries no
    value -- which is why one set per class is required."""
    if class_id not in SET_NAMES:
        raise BridgeError(f"class id {class_id} has no set")
    # encode() validates, and raises rather than silently masking a bad field
    encode(class_id, confidence=confidence, reason=reason, lease_id=lease_id)
    pre = _netns(ns)
    return pre + ("nft", "add", "element", family, NFT_TABLE,
                  SET_NAMES[class_id], key.element(timeout))


def generate_del_element(family: str, key: FlowKey, class_id: int,
                         ns: str | None = None) -> tuple[str, ...]:
    if class_id not in SET_NAMES:
        raise BridgeError(f"class id {class_id} has no set")
    pre = _netns(ns)
    return pre + ("nft", "delete", "element", family, NFT_TABLE,
                  SET_NAMES[class_id], key.element(timeout=None))


def generate_steer_filters(dev: str, ns: str | None = None,
                           protocol_filter: bool = True) -> tuple[tuple[str, ...], ...]:
    """Static `tc flower` filters, one per class per protocol, keyed on the DSCP
    selector code the bridge stamped on the packet.

    ## Why flower and not fw

    The original design had nftables write the packet mark and static `tc fw`
    filters read it, matching the mark's class nibble. **No classifier on
    iproute2 6.1.0 can match a packet mark.** Measured, not assumed:

        fw handle 0xNN/0x0f        rejected: fw has no `handle`
        fw mask 0xf handle 0x1     rejected: fw has no `mask`
        flower meta mark           rejected: flower has no `meta` key at all
        basic match "skb/mark ..." rejected: not the ematch grammar

    `flower ip_tos` is used instead because it is proven to work on this exact
    toolchain: gate check 14 routes IPv6 EF traffic with `flower ip_tos 0xb8/0xfc`,
    and the probe confirms `flower ip_tos 0x28/0xfc` alongside `ip_proto` and
    full 4-tuple matching.

    ## What this costs

    The DSCP on the wire is rewritten to a CSx selector code, so the original
    value is not visible downstream. That is a deliberate policy decision, not
    an accident: many routers remark DSCP to reflect their own scheduling, and
    CSx codes are reserved for exactly that kind of local assignment. If the
    original value must survive, the alternative is per-flow `flower` filters
    matching the flow key directly, which mutates nothing but costs a netlink
    transaction per reclassification and loses kernel-side mark expiry.

    ## Mask

    DSCP is the top 6 bits of the TOS byte; the low 2 are ECN and must not be
    matched, hence /0xfc. Identical to what gate check 14 already proves.
    """
    pre = _netns(ns)
    cmds = []
    for protocol in (("ip", "ipv6") if protocol_filter else ("all",)):
        for c in MARKED_CLASSES:
            cmds.append(pre + (
                "tc", "filter", "add", "dev", dev, "parent", "1:",
                "protocol", protocol,
                "prio", str(steer_prio(protocol, c)),
                "flower", "skip_hw",
                "ip_tos", f"{CS_DSCP_VALUES[c]:#04x}/{DSCP_MASK}",
                "flowid", _flowid(c),
            ))
    return tuple(cmds)


def generate_flow_filter(key: "FlowKey", class_id: int, dev: str,
                         handle: int, ns: str | None = None) -> tuple[str, ...]:
    """One `tc flower` filter matching a flow's key directly.

    ## Why per-flow filters, and not DSCP steering

    The mechanism this module originally used was: nftables stamps a DSCP
    selector code on the packet in prerouting, and static filters read it. It
    does not work, and the reason is now measured rather than guessed.

    On this toolchain, with controls for every other variable:

        both classifiers read the header   flower ignores skb->priority alone
        u32 works                          positive control passes
        the header IS 0x18 at postrouting  the chain counters read 60
        the wire IS 0x18                   the client reads 60
        a SENDER-written DSCP matches      passes
        an NFTABLES-written one does NOT   fails, on two different ports

    So a DSCP written by nftables is invisible to tc egress classifiers even
    though the packet is transmitted carrying it. Five hypotheses died to this
    one -- including a `meta l4proto` width mismatch, a lost skb->priority, and a
    DSCP that did not survive to egress -- each consistent with everything known
    at the time. See testbed/bridge_isolate.sh.

    ## What this costs, stated plainly

    One netlink transaction per reclassification, which is exactly what the
    nftables-set indirection existed to avoid. For the handful of concurrent
    flows a home router carries this is small: at 20 flows a full re-tick is
    about 40 transactions, roughly 4-12 ms against a ~1 s tick.

    In exchange:

    * nothing is mutated on the wire, so the DSCP-rewrite side effect and its
      collision risk disappear entirely;
    * no dependency on `tc fw`, which cannot read a mark on iproute2 6.1.0;
    * no dependency on nftables' DSCP write being visible to tc.

    ## What is lost

    Kernel-side expiry. The nftables sets gave mark expiry for free via
    `flags timeout`, surviving even a crashed process. Per-flow filters do not:
    if ACIQ dies mid-run, its filters remain and keep routing those flows to
    classes that may no longer be configured. `Bridge.teardown()` clears them,
    and callers should use it, but a hard kill leaves residue. That is a real
    regression against the set design and is recorded rather than glossed.
    """
    if not 1 <= handle <= MAX_FLOW_HANDLE:
        raise BridgeError(f"handle {handle} outside 1..{MAX_FLOW_HANDLE:#x}")
    proto = "ipv6" if family_of(key.src) == "ip6" else "ip"
    return _netns(ns) + (
        "tc", "filter", "add", "dev", dev, "parent", "1:",
        "protocol", proto,
        "prio", str(FLOW_FILTER_PRIO[proto]),
        "handle", f"0x{handle:04x}",
        "flower", "skip_hw",
        "src_ip", key.src,
        "dst_ip", key.dst,
        "ip_proto", key.proto,
        "dst_port", str(key.dport),
        "flowid", _flowid(class_id),
    )


def generate_del_flow_filter(dev: str, handle: int, proto: str,
                             ns: str | None = None) -> tuple[str, ...]:
    """Delete one per-flow filter by handle.

    Deleting by handle rather than by re-stating the match: the match is four
    fields and getting one wrong leaves the filter in place silently, and a
    leftover filter routes a flow to a stale class indefinitely.
    """
    return _netns(ns) + (
        "tc", "filter", "del", "dev", dev, "parent", "1:",
        "protocol", proto,
        "prio", str(FLOW_FILTER_PRIO[proto]),
        "handle", f"0x{handle:04x}",
        "flower",
    )


def _flowid(class_id: int) -> str:
    """Map a class id onto its HTB class.

    Read from `tc.CLASS_IDS` rather than restated here: the bridge and the tree
    must agree on every classid, and a duplicated table is a table that will
    eventually disagree after a one-line change to one copy only.
    """
    if class_id == CLASS_UNCLASSIFIED:
        # Deliberately the DEFAULT class, not a class of its own: the point is
        # that this flow stops being eligible for EF priority, and 1:30 is
        # already where all non-EF traffic lands.
        return tc.CLASS_IDS[TrafficClass.BULK]
    return tc.CLASS_IDS[_TRAFFIC_BY_CLASS[class_id]]


def generate_flush(family: str, ns: str | None = None) -> tuple[tuple[str, ...], ...]:
    pre = _netns(ns)
    return tuple(pre + ("nft", "flush", "set", family, NFT_TABLE, SET_NAMES[c])
                 for c in MARKED_CLASSES)


def generate_teardown(family: str, ns: str | None = None) -> tuple[str, ...]:
    """`delete table` removes the chain and all sets in one transaction, which
    is why teardown does not enumerate them."""
    return _netns(ns) + ("nft", "delete", "table", family, NFT_TABLE)


@dataclass(frozen=True)
class InstalledFilter:
    """One per-flow filter found on the device by enumeration."""

    pref: int
    protocol: str
    handle: int


def enumerate_flow_filters(dev: str, ns: str | None = None,
                           executor=None) -> list[InstalledFilter]:
    """Find every per-flow filter currently on `dev`.

    Needed because a fresh process has empty state, so `teardown()` cannot know
    what a previous run left behind. Filters left after a restart keep routing
    their flows to classes that may no longer be configured, and nothing else
    removes them.

    Reads `tc -j` (JSON) rather than the human-readable listing: this gate has
    already been bitten by parsing tool output -- an assertion matching the
    literal "flags timeout" when nft prints "timeout 2m", and awk keyed on a
    chain name without resetting between chains. A structured output format is
    the fix for that class of bug, not a more careful text parser.

    Returns an empty list if the listing cannot be read or parsed. Failing to
    enumerate must not prevent teardown from removing what it *does* know about.
    """
    run = executor or _subprocess_executor
    argv = _netns(ns) + ("tc", "-j", "filter", "show", "dev", dev, "parent", "1:")
    try:
        rc, out, _err = run(argv)
        if rc != 0:
            return []
        entries = json.loads(out)
    except (json.JSONDecodeError, TypeError, ValueError):
        return []
    if not isinstance(entries, list):
        return []

    found: list[InstalledFilter] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        pref = entry.get("pref")
        kind = entry.get("kind")
        proto = entry.get("protocol")
        opts = entry.get("options")
        if pref is None or kind != "flower" or not isinstance(opts, dict):
            continue
        if pref not in FLOW_FILTER_PRIO.values():
            continue
        handle = opts.get("handle")
        if handle is None:
            continue
        if isinstance(handle, str):
            try:
                handle = int(handle, 16) if handle.startswith("0x") else int(handle)
            except ValueError:
                continue
        if not isinstance(handle, int) or handle <= 0:
            continue
        found.append(InstalledFilter(int(pref), proto or "ip", handle))
    return found


def _netns(ns: str | None) -> tuple[str, ...]:
    return ("ip", "netns", "exec", ns) if ns else ()


# --------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------

@dataclass
class FlowSlot:
    """One per-flow tc filter currently installed."""

    handle: int
    protocol: str
    class_id: int


@dataclass
class BridgeState:
    """Which filter each flow currently has.

    Tracked so a reclassification is one delete and one add rather than a
    speculative delete against every filter, and so `teardown()` knows exactly
    what to remove.

    Handles are derived from flow keys (see `handle_for`), so this is a cache of
    what is known to be installed, not the source of truth. Losing it costs a
    redundant delete-then-add, never a wrong filter: `forget()` recomputes the
    handle rather than looking it up.
    """

    slots: dict[tuple[str, str, str, int], "FlowSlot"] = field(default_factory=dict)

    @property
    def membership(self) -> dict:
        """Keyed by flow signature -> class id, for callers that only want the class."""
        return {k: v.class_id for k, v in self.slots.items()}


def _run(executor, argv: tuple[str, ...]) -> tuple[int, str, str]:
    return executor(argv)


class Bridge:
    """Installs and drives the nftables->mark->tc path.

    `executor` is injected so the ordering and error handling can be tested
    without a kernel. Default runs commands for real and requires root.
    """

    def __init__(self, dev: str, in_if: str, ns: str | None = None,
                 families: tuple[str, ...] = ("ip", "ip6"),
                 executor=None, dry_run: bool = False,
                 install_sets: bool = False):
        self.dev = dev
        self.in_if = in_if
        self.ns = ns
        self.families = families
        self.install_sets = install_sets
        self.dry_run = dry_run
        self.executor = executor or _subprocess_executor
        self.state = BridgeState()
        self.commands: list[tuple[str, ...]] = []

    # -- lifecycle ---------------------------------------------------------
    def setup(self) -> list[tuple[str, ...]]:
        """Remove anything left over from a previous run.

        Per-flow filters are installed by `mark()` as flows are classified, so
        there is no static filter block to create. What setup must do is clear
        residue, and it cannot use in-process state for that: after a restart the
        state is empty while the device still carries the previous run's filters,
        which keep routing their flows to classes that may no longer exist. So it
        enumerates the tc tree instead.

        The nftables tables are removed too when `install_sets` was requested.
        They are no longer part of enforcement -- see `generate_flow_filter` for
        why DSCP steering was abandoned -- so they are off by default.
        """
        ran = []
        # Everything on the device at our priorities, not just what this instance
        # installed -- a crashed predecessor's filters are the ones that matter.
        # Skipped under dry_run: a dry run must not read or touch the device.
        for f in ([] if self.dry_run
                  else enumerate_flow_filters(self.dev, self.ns, self.executor)):
            ran += self._do(generate_del_flow_filter(
                self.dev, f.handle, f.protocol, self.ns), missing_ok=True)
        self.state.slots.clear()
        if self.install_sets:
            for family in self.families:
                ran += self._do(generate_teardown(family, self.ns), missing_ok=True)
        return ran

    def teardown(self) -> list[tuple[str, ...]]:
        """Remove every filter this bridge installed.

        Must be called. Per-flow filters are not kernel-timed, so an unclean exit
        leaves them behind routing traffic to stale classes.
        """
        ran = []
        # Known filters first, then anything found on the device. The second
        # pass is what makes a restart clean: this process may be the first to
        # have any idea a previous run left filters behind.
        for slot in list(self.state.slots.values()):
            ran += self._do(generate_del_flow_filter(
                self.dev, slot.handle, slot.protocol, self.ns), missing_ok=True)
        self.state.slots.clear()
        for f in ([] if self.dry_run
                  else enumerate_flow_filters(self.dev, self.ns, self.executor)):
            ran += self._do(generate_del_flow_filter(
                self.dev, f.handle, f.protocol, self.ns), missing_ok=True)
        for family in self.families:
            ran += self._do(generate_teardown(family, self.ns), missing_ok=True)
        return ran

    # -- per-flow ----------------------------------------------------------
    def mark(self, key: FlowKey, class_id: int, confidence: float = 0.0,
             reason: int = 0, lease_id: int = 0) -> list[tuple[str, ...]]:
        """Give a flow a per-flow tc filter pointing at its class.

        Re-marking a flow in the class it is already in is a no-op. That matters
        more here than it did with the nftables sets: an add would be another
        netlink transaction per flow per tick for no behavioural change, and at
        N flows that is the whole budget.

        Re-classification deletes the old filter and installs a new one with a
        fresh handle. Handles are never reused, so a stale delete can never remove
        a filter belonging to some other flow.
        """
        if self._families_for(key) == ():
            return []
        prev = self.state.slots.get(key.signature)
        if prev is not None and prev.class_id == class_id:
            return []

        ran = []
        proto = "ipv6" if family_of(key.src) == "ip6" else "ip"
        handle = handle_for(key)
        # Delete by derived handle, not by the recorded one: on a restart the
        # recorded slot is empty but the filter is still on the device, and
        # adding without deleting would fail with "Filter already exists".
        ran += self._do(generate_del_flow_filter(
            self.dev, handle, proto, self.ns), missing_ok=True)

        handle = handle_for(key)
        ran += self._do(generate_flow_filter(
            key, class_id, self.dev, handle, self.ns))
        proto = "ipv6" if family_of(key.src) == "ip6" else "ip"
        self.state.slots[key.signature] = FlowSlot(handle, proto, class_id)
        return ran

    def forget(self, key: FlowKey) -> list[tuple[str, ...]]:
        """Remove a flow's filter.

        Required for lease release, and the only way a flow that has stopped
        being classified stops being steered. No-op for a flow with no filter.
        """
        self.state.slots.pop(key.signature, None)
        proto = "ipv6" if family_of(key.src) == "ip6" else "ip"
        # Deliberately not gated on the slot: a fresh Bridge must still be able to
        # release a flow, which is exactly the case the gate's bunmark exercises
        # and the reason handles are derived rather than counted.
        return self._do(generate_del_flow_filter(
            self.dev, handle_for(key), proto, self.ns), missing_ok=True)

    def classify_flow(self, key: FlowKey, class_id: int | None,
                      confidence: float = 0.0) -> list[tuple[str, ...]]:
        """Apply a classification verdict, where None means "unclassified".

        An unclassified flow gets its filter removed rather than pointed at a
        default class, so it falls through to the HTB default exactly as an
        unclassified flow should.

        `confidence` is forwarded to `mark` rather than taken and discarded: it
        is the classifier's own statement of how sure it is, and a bridge that
        threw it away could not tell a confident verdict from a marginal one.
        """
        if class_id is None:
            return self.forget(key)
        return self.mark(key, class_id, confidence=confidence)

    def family_of(self, src: str) -> str:
        """Address family from the literal. Delegates to the module-level
        helper; kept as a method so existing callers keep working."""
        return family_of(src)

    def _families_for(self, key: FlowKey) -> tuple[str, ...]:
        f = self.family_of(key.src)
        return (f,) if f in self.families else ()

    # -- plumbing ----------------------------------------------------------
    def _do(self, cmds, missing_ok: bool = False) -> list[tuple[str, ...]]:
        """Run one command, or a sequence of them.

        Normalises the two shapes the generators return naturally: a single
        command is a `tuple[str, ...]`, several are a `tuple[tuple[str, ...], ...]`.
        Without this, passing a single command to a sequence loop iterates its
        *tokens*, so "nft" and "add element" were each executed as if they were
        whole command lines.

        `missing_ok` tolerates a nonzero exit. It is used only for `nft delete`,
        and it is safe there because a delete that fails for a real reason cannot
        hide it: if the object exists and genuinely cannot be removed, the very
        next command (`nft add`) fails and raises. So "it was not there" and
        "something is wrong" both surface -- just at the command where they
        actually matter.

        Two cases make this necessary, and neither is hypothetical:

        * `setup()` deletes before creating, to stay idempotent. On a first run
          there is no table, so `nft delete table` returns
          ENOENT -- "No such file or directory" -- which is the expected state,
          not an error. Raising here made check 15 fail on its first command.
        * `delete element` returns ENOENT whenever a mark has already expired
          through its 120s set timeout and the flow is reclassified afterwards.
          Expiry is designed to happen, so this race is guaranteed in normal
          operation, and it would abort a classification tick.
        """
        if isinstance(cmds, tuple) and cmds and isinstance(cmds[0], str):
            cmds = (cmds,)
        ran = []
        for argv in cmds:
            if self.dry_run:
                self.commands.append(argv)
                ran.append(argv)
                continue
            rc, _out, err = _run(self.executor, argv)
            if rc != 0 and not missing_ok:
                raise BridgeError(f"{' '.join(argv)} -> rc={rc}: {err.strip()}")
            self.commands.append(argv)
            ran.append(argv)
        return ran

    def plan(self) -> list[tuple[str, ...]]:
        """Every static command setup() would run, without running any.

        There are no static filter commands any more: per-flow filters are added
        by mark(). Kept because callers use it to preview work.
        """
        out = []
        if self.install_sets:
            for family in self.families:
                out.append(generate_teardown(family, self.ns))
        return out


def family_of(src: str) -> str:
    """Address family of a literal: "ip" or "ip6".

    Deliberately string inspection rather than `socket.inet_pton`, so a zone id
    (`fe80::1%eth0`) or a hostname does not raise from deep inside a
    classification tick.

    Module level so a caller adding one flow filter does not have to construct
    a Bridge -- which is what the gate's `bmark` helper was doing, and it read as
    though the Bridge instance were needed.
    """
    return "ip6" if ":" in src else "ip"


def _subprocess_executor(argv: tuple[str, ...]) -> tuple[int, str, str]:
    p = subprocess.run(list(argv), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr