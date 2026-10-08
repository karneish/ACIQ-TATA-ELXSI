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
- **Static `tc fw` filters**, one per class per protocol, matching the mark's
  class nibble via `handle 0xNN/0x0f`. Reclassification touches one set element
  and nothing in the tc tree.

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

import subprocess
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

#: Mark-driven filter priorities, per class. Distinct per class so evaluation
#: order is explicit rather than relying on same-prio chaining rules.
MARK_FILTER_PRIO = {
    CLASS_UNCLASSIFIED: 10,
    CLASS_INTERACTIVE: 11,
    CLASS_ADAPTIVE: 12,
    CLASS_BULK: 13,
    CLASS_LEASED: 14,
}

#: DSCP-EF fallback lives here so it can never pre-empt the bridge. Imported
#: from `tc` rather than redeclared: the bridge installs mark filters and `tc`
#: installs the EF filters into the same parent, so two copies of these numbers
#: would be two chances to get the ordering wrong in exactly the way that fails
#: silently.
DSCP_FILTER_PRIO = tc.DSCP_FILTER_PRIO

#: Classes that get a mark-driven filter, in priority order.
MARKED_CLASSES = tuple(sorted(MARK_FILTER_PRIO, key=MARK_FILTER_PRIO.get))

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
    "ip": ("ipv4_addr", "ipv4_addr", ("ip", "saddr"), ("ip", "daddr")),
    "ip6": ("ipv6_addr", "ipv6_addr", ("ip6", "saddr"), ("ip6", "daddr")),
}

#: The address expressions are TOKEN TUPLES, not strings. nftables parses `ip`
#: and `saddr` as separate keywords, so emitting "ip saddr" as one argv element
#: makes the kernel look for a protocol literally named "ip saddr". That is the
#: same shape of mistake as the "cake bandwidth 95mbit" bug that read as a
#: missing kernel module, which is why `test_tokenisation` exists.
_ADDRESS_TOKEN_EXCEPTIONS: frozenset[str] = frozenset({"{", "}"})


def _set_type(family: str) -> str:
    src_t, dst_t, _, _ = _FAMILY[family]
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


def generate_rules(family: str, in_if: str,
                   ns: str | None = None) -> tuple[tuple[str, ...], ...]:
    """One rule per class, most authoritative first.

    nftables stops at the first matching rule in a chain, so the order of this
    tuple *is* the precedence. `class_precedence` therefore defines it rather
    than dict iteration order.
    """
    pre = _netns(ns)
    _, _, src_toks, dst_toks = _FAMILY[family]
    cmds = []
    for c in CLASS_PRECEDENCE:
        mark = encode(c)
        cmds.append(pre + (
            "nft", "add", "rule", family, NFT_TABLE, NFT_CHAIN,
            "iifname", in_if,
            *src_toks, *dst_toks,
            "meta", "l4proto", "th", "dport",
            "@" + SET_NAMES[c],
            "meta", "mark", "set", str(mark),
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


def generate_mark_filters(dev: str, ns: str | None = None,
                          protocol_filter: bool = True) -> tuple[tuple[str, ...], ...]:
    """Static `tc fw` filters, one per class per protocol, matching the class
    nibble of the mark.

    `handle 0xNN/0x0f` masks to the class field so confidence, reason and lease
    id do not each need their own filter. With 5 classes x 4 confidence x 4
    reasons that would otherwise be 80 filters, and one new bucket would
    invalidate every one of them.
    """
    pre = _netns(ns)
    cmds = []
    for protocol in (("ip", "ipv6") if protocol_filter else ("all",)):
        for c in MARKED_CLASSES:
            cmds.append(pre + (
                "tc", "filter", "add", "dev", dev, "parent", "1:",
                "protocol", protocol,
                "prio", str(MARK_FILTER_PRIO[c]),
                "fw", "handle", class_handle(c),
                "flowid", _flowid(c),
            ))
    return tuple(cmds)


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


def _netns(ns: str | None) -> tuple[str, ...]:
    return ("ip", "netns", "exec", ns) if ns else ()


# --------------------------------------------------------------------------
# orchestration
# --------------------------------------------------------------------------

@dataclass
class BridgeState:
    """Which class each flow is currently in, per family.

    Tracked so a reclassification is one delete and one add, rather than a
    speculative delete against every set (5 netlink calls per change, most of
    which must tolerate ENOENT).
    """

    membership: dict[tuple[str, tuple[str, str, str, int]], int] = field(
        default_factory=dict)


def _run(executor, argv: tuple[str, ...]) -> tuple[int, str, str]:
    return executor(argv)


class Bridge:
    """Installs and drives the nftables->mark->tc path.

    `executor` is injected so the ordering and error handling can be tested
    without a kernel. Default runs commands for real and requires root.
    """

    def __init__(self, dev: str, in_if: str, ns: str | None = None,
                 families: tuple[str, ...] = ("ip", "ip6"),
                 executor=None, dry_run: bool = False):
        self.dev = dev
        self.in_if = in_if
        self.ns = ns
        self.families = families
        self.dry_run = dry_run
        self.executor = executor or _subprocess_executor
        self.state = BridgeState()
        self.commands: list[tuple[str, ...]] = []

    # -- lifecycle ---------------------------------------------------------
    def setup(self) -> list[tuple[str, ...]]:
        """Idempotent install.

        nft's `add` fails on an existing table, so teardown runs first. That is
        deliberate: a half-installed bridge whose rules disagree with the code
        is worse than a brief window with no bridge, and it keeps setup to one
        code path instead of `add` with fallback to `create`.
        """
        ran = []
        # Two passes, not one interleaved per family: delete both tables before
        # creating either. Interleaving means a failure while building the IPv6
        # table leaves a stale IPv4 table behind, and the next run then deletes
        # it -- so the window where rules and code disagree is wider than
        # necessary.
        for family in self.families:
            ran += self._do(generate_teardown(family, self.ns), missing_ok=True)
        for family in self.families:
            ran += self._do(generate_table(family, self.ns))
            ran += self._do(generate_sets(family, self.ns))
            ran += self._do(generate_rules(family, self.in_if, self.ns))
        ran += self._do(generate_mark_filters(self.dev, self.ns))
        return ran

    def teardown(self) -> list[tuple[str, ...]]:
        ran = []
        for family in self.families:
            ran += self._do(generate_teardown(family, self.ns), missing_ok=True)
        self.state.membership.clear()
        return ran

    # -- per-flow ----------------------------------------------------------
    def mark(self, key: FlowKey, class_id: int, confidence: float = 0.0,
             reason: int = 0, lease_id: int = 0) -> list[tuple[str, ...]]:
        """Place a flow in a class, moving it if it was somewhere else.

        Re-marking a flow in the class it is already in is a no-op: re-adding an
        existing element resets its timeout, and doing that on every tick would
        keep a dead flow's mark alive forever. That is how a stale mark becomes
        permanent, so it is avoided rather than tolerated.
        """
        families = self._families_for(key)
        prev = self.state.membership.get((families[0], key.signature))
        if prev == class_id:
            return []

        ran = []
        for family in families:
            if prev is not None:
                # missing_ok: a 120s kernel timeout may already have removed it
                ran += self._do(generate_del_element(family, key, prev, self.ns),
                                missing_ok=True)
            ran += self._do(generate_add_element(
                family, key, class_id, confidence=confidence, reason=reason,
                lease_id=lease_id, ns=self.ns))
        self.state.membership[(families[0], key.signature)] = class_id
        return ran

    def forget(self, key: FlowKey) -> list[tuple[str, ...]]:
        """Drop a flow's mark explicitly. Not normally needed -- the kernel's
        element timeout expires it -- but required for lease release."""
        families = self._families_for(key)
        prev = self.state.membership.get((families[0], key.signature))
        if prev is None:
            return []
        ran = []
        for family in families:
            ran += self._do(generate_del_element(family, key, prev, self.ns),
                            missing_ok=True)
        self.state.membership.pop((families[0], key.signature), None)
        return ran

    def family_of(self, src: str) -> str:
        """Address family from the literal. Deliberately literal rather than
        `socket.inet_pton`, so a zone id (`fe80::1%eth0`) or a hostname does not
        raise from deep inside a classification tick."""
        return "ip6" if ":" in src else "ip"

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
        """Every command setup() would run, without running any."""
        out = []
        for family in self.families:
            # appended as one element, not splatted: generate_teardown returns a
            # single argv, and `list()` on it yields its tokens
            out.append(generate_teardown(family, self.ns))
        for family in self.families:
            out += list(generate_table(family, self.ns))
            out += list(generate_sets(family, self.ns))
            out += list(generate_rules(family, self.in_if, self.ns))
        out += list(generate_mark_filters(self.dev, self.ns))
        return out


def _subprocess_executor(argv: tuple[str, ...]) -> tuple[int, str, str]:
    p = subprocess.run(list(argv), capture_output=True, text=True)
    return p.returncode, p.stdout, p.stderr