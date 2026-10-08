"""Mark encoding: the contract between the nftables bridge and tc enforcement.

Pure arithmetic. No netlink, no root, no subprocess -- so every field layout,
shift and mask below is unit-testable without privileges, and the testbed only
has to prove that the kernel honours what this module already specifies.

## Why a mark at all

Classification is **per flow** and enforcement is **per class**. Something has to
carry a per-flow verdict to the point where classes are chosen. That is the
packet mark.

Two alternatives were rejected:

- **`tc u32`/per-flow `tc` filters.** Every reclassification is a netlink
  transaction adding and deleting filters. For hundreds of flows that is
  hundreds of transactions per tick. The tc tree becomes the bottleneck and a
  slow tick degrades everyone's QoS.
- **`cake dual-dsthost` as the leaf.** Verified as a genuine device-fairness
  improvement, but it groups by *destination address*, not by QoS class, so it
  cannot express "interactive gets 8x". Kept as a separate improvement; not a
  substitute.

So: **nftables writes the mark, `tc fw` filters read it.** The filters are
static -- one per class, written once at setup. Reclassification changes a set
element and nothing else, and nftables handles element expiry in the kernel via
`flags timeout`, which is what gives mark expiry without a userspace sweeper.

## Mark layout (32 bits)

Fields are packed from the least significant bit. The layout is deliberately
byte-tolerant: the class id occupies the low nibble so a `tc fw` filter can mask
on it alone.

    bits  0-3   class id      0=unclassified 1=interactive 2=adaptive
                               3=bulk 4=leased 5-15 reserved for sub-classes
    bit   4     seen          1 = the bridge examined this flow
    bits  5-6   confidence    0=none 1=low 2=medium 3=high
    bits  7-8   reason        0=none 1=dscp 2=behaviour 3=correction
    bits  9-16  lease id      0 = not leased; 1-255 identify a lease
    bits 17-31  reserved      must be 0

### Why the `seen` bit exists

Without it, "the bridge decided this flow is unclassified" and "the bridge never
looked at this flow" are the same value: zero. They must differ, because they
lead to opposite enforcement decisions:

- **untouched** -- falls through to the DSCP-EF filter, which may still promote
  the flow. Correct: the bridge has no opinion yet.
- **seen, class 0** -- the bridge *examined* the flow and found it unclassified,
  possibly because a claimed EF mark contradicted its measured rate. Falling
  through would hand it EF priority, which is exactly what the trust logic in
  `classify.py` exists to prevent.

Collapsing these two cases silently reintroduces the evasion hole. The bit costs
one and removes an entire class of wrong answers.

### Reserved class ids 5-15

The plan allows 4-8 differentiated sub-classes, fixed at configuration time.
Class ids 5-15 are therefore left undefined rather than assigned: a sub-class
feature can be added without renumbering, and an id that is set but undefined
is rejected loudly by `encode()` rather than silently mapped somewhere.
"""

from __future__ import annotations

from dataclasses import dataclass

from .model import TrafficClass

#: Class ids, as stored in mark bits 0-3.
CLASS_UNCLASSIFIED = 0
CLASS_INTERACTIVE = 1
CLASS_ADAPTIVE = 2
CLASS_BULK = 3
CLASS_LEASED = 4

CLASS_BY_TRAFFIC = {
    TrafficClass.INTERACTIVE: CLASS_INTERACTIVE,
    TrafficClass.ADAPTIVE: CLASS_ADAPTIVE,
    TrafficClass.BULK: CLASS_BULK,
    # LEASED exists in the model but had no mapping, so encode_for_traffic()
    # raised KeyError on the one class the lease feature needs to produce.
    TrafficClass.LEASED: CLASS_LEASED,
}

#: Defined only up to LEASED; 5-15 are reserved for sub-classes.
DEFINED_CLASS_IDS = frozenset({CLASS_UNCLASSIFIED, CLASS_INTERACTIVE,
                               CLASS_ADAPTIVE, CLASS_BULK, CLASS_LEASED})

# ---- bit positions -------------------------------------------------------
CLASS_SHIFT = 0
CLASS_BITS = 4
CLASS_MASK = (1 << CLASS_BITS) - 1  # 0xF

SEEN_BIT = 1 << 4  # 0x10

CONF_SHIFT = 5
CONF_BITS = 2
CONF_MASK = ((1 << CONF_BITS) - 1) << CONF_SHIFT  # 0x60

REASON_SHIFT = 7
REASON_BITS = 2
REASON_MASK = ((1 << REASON_BITS) - 1) << REASON_SHIFT  # 0x180

LEASE_SHIFT = 9
LEASE_BITS = 8
#: bits 9-16 inclusive. Must be 0xFF << 9 = 0x1FE00. An earlier value of 0xFE00
#: covered only bits 9-15, leaving bit 16 belonging to neither the lease field
#: nor MARK_RESERVED_MASK -- an undefined hole in the layout that no test using
#: lease_id <= 127 would have caught.
LEASE_MASK = ((1 << LEASE_BITS) - 1) << LEASE_SHIFT

MARK_RESERVED_MASK = 0xFFFE0000  # bits 17-31, must always be zero

#: Proves the defined fields tile the low 17 bits exactly, with no gap and no
#: overlap. Checked at import: a layout error should fail immediately, not
#: surface later as traffic in the wrong class.
_LAYOUT_BITS = (CLASS_MASK | SEEN_BIT | CONF_MASK | REASON_MASK | LEASE_MASK)
if _LAYOUT_BITS != (LEASE_MASK | 0x1FFFF):
    raise AssertionError(
        f"mark layout does not tile bits 0-16: covered 0x{_LAYOUT_BITS:05x}")

# ---- confidence buckets --------------------------------------------------
CONF_NONE = 0
CONF_LOW = 1
CONF_MEDIUM = 2
CONF_HIGH = 3

#: Buckets are chosen so the boundaries cannot make a high-confidence decision
#: look merely adequate, or vice versa.
CONF_LOW_BELOW = 0.60
CONF_MEDIUM_BELOW = 0.80


def bucket_confidence(confidence: float) -> int:
    """Map a 0..1 confidence onto a 2-bit bucket."""
    if confidence >= CONF_MEDIUM_BELOW:
        return CONF_HIGH
    if confidence >= CONF_LOW_BELOW:
        return CONF_MEDIUM
    if confidence > 0.0:
        return CONF_LOW
    return CONF_NONE


# ---- reason codes --------------------------------------------------------
REASON_NONE = 0
REASON_DSCP = 1
REASON_BEHAVIOUR = 2
REASON_CORRECTION = 3

REASON_NAMES = {
    REASON_NONE: "none",
    REASON_DSCP: "dscp",
    REASON_BEHAVIOUR: "behaviour",
    REASON_CORRECTION: "correction",
}

#: Tier letters from `classify.py`, mapped to a reason code.
REASON_BY_TIER = {
    "A": REASON_DSCP,
    "B": REASON_BEHAVIOUR,
    "C": REASON_BEHAVIOUR,
    "X": REASON_CORRECTION,
}


class MarkEncodingError(ValueError):
    """Raised rather than silently truncating. A mis-encoded mark does not fail
    loudly at the point of writing; it fails later as traffic in the wrong class."""


@dataclass(frozen=True)
class DecodedMark:
    class_id: int
    seen: bool
    confidence: int
    reason: int
    lease_id: int
    raw: int

    @property
    def reason_name(self) -> str:
        return REASON_NAMES.get(self.reason, f"unknown({self.reason})")

    @property
    def is_untouched(self) -> bool:
        """True when the bridge has no opinion on this packet."""
        return not self.seen


def encode(class_id: int, *, seen: bool = True,
           confidence: float = 0.0, reason: int = REASON_NONE,
           lease_id: int = 0) -> int:
    """Build a packet mark.

    Validates every field. Out-of-range values raise instead of being masked
    off, because a silently truncated class id puts traffic in a class nobody
    configured and no gate check would notice.
    """
    if not 0 <= class_id <= CLASS_MASK:
        raise MarkEncodingError(
            f"class id {class_id} outside 0..{CLASS_MASK}")
    if class_id not in DEFINED_CLASS_IDS:
        raise MarkEncodingError(
            f"class id {class_id} is reserved (only "
            f"{sorted(DEFINED_CLASS_IDS)} are defined)")
    if not 0 <= reason <= ((1 << REASON_BITS) - 1):
        raise MarkEncodingError(f"reason {reason} out of range")
    if not 0 <= lease_id <= 0xFF:
        raise MarkEncodingError(f"lease id {lease_id} outside 0..255")
    if lease_id and class_id != CLASS_LEASED:
        raise MarkEncodingError(
            f"lease id {lease_id} set on class id {class_id}; leases are only "
            f"meaningful on CLASS_LEASED ({CLASS_LEASED})")

    if not seen:
        # Confidence and reason describe a decision that was never made, so an
        # unexamined flow encodes to exactly zero. Enforced rather than assumed:
        # a mark of 0x60 (low confidence, no class) would set the confidence bits
        # on a flow nothing knows about, and is_untouched() would then disagree
        # with the caller about whether the bridge had an opinion.
        return 0

    mark = class_id
    mark |= SEEN_BIT
    mark |= (bucket_confidence(confidence) << CONF_SHIFT)
    mark |= (reason << REASON_SHIFT)
    mark |= (lease_id << LEASE_SHIFT)
    return mark


def encode_for_traffic(tc: TrafficClass, *, confidence: float = 0.0,
                       reason: int = REASON_NONE,
                       lease_id: int = 0) -> int:
    """Encode a TrafficClass, used when the bridge has no class (None) to mean
    "examined and unclassified"."""
    if tc is None:
        return encode(CLASS_UNCLASSIFIED, seen=True, confidence=confidence,
                      reason=reason)
    return encode(CLASS_BY_TRAFFIC[tc], seen=True, confidence=confidence,
                  reason=reason, lease_id=lease_id)


def decode(mark: int) -> DecodedMark:
    """Split a mark back into fields. Used by the gate checks and by tests."""
    if mark < 0 or mark > 0xFFFFFFFF:
        raise MarkEncodingError(f"mark {mark} outside 0..0xFFFFFFFF")
    return DecodedMark(
        class_id=mark & CLASS_MASK,
        seen=bool(mark & SEEN_BIT),
        confidence=(mark & CONF_MASK) >> CONF_SHIFT,
        reason=(mark & REASON_MASK) >> REASON_SHIFT,
        lease_id=(mark & LEASE_MASK) >> LEASE_SHIFT,
        raw=mark,
    )


def class_handle(class_id: int) -> str:
    """The `tc fw` handle string for a class: the mark masked to class bits only.

    Returned as `0xNN/0xF` so a filter matches the class field and ignores
    confidence, reason and lease id. Without the mask, one filter per
    (class x confidence x reason) combination would be needed -- 5 x 4 x 4 = 80
    static filters -- and a single new confidence bucket would invalidate them.
    """
    if class_id not in DEFINED_CLASS_IDS:
        raise MarkEncodingError(f"class id {class_id} is not defined")
    return f"0x{class_id:02x}/0x{CLASS_MASK:02x}"


def is_untouched(mark: int) -> bool:
    """A mark of zero, or any mark without the seen bit, means the bridge did
    not classify this packet."""
    return not (mark & SEEN_BIT)