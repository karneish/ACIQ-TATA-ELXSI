"""M7 -- the intent API's domain logic, with no HTTP in it.

A *lease* is a time-boxed, weighted request for extra bandwidth, made by a
person rather than inferred from behaviour. It is the only way this system gives
a flow more than its class guarantees.

## Why a lease is not a priority boost

A boost is permanent until someone remembers to undo it. A lease borrows a
bounded share and expires on its own, so a forgotten request cannot permanently
harm the household. That property is the whole design, and it is why `POST
/intent` takes a `ttl_s` rather than offering an indefinite grant: there is no
code path that creates a lease which does not expire.

## Scope: device or flow

`target: "device"` matches on IP and ignores the port, because a device's
reconnects change its source port and a port-sensitive request would silently
stop applying. `target: "flow"` matches the 5-tuple including the port.

## Why most-recent-wins

Re-requesting the same target replaces the previous lease rather than stacking
with it. Two overlapping leases on one device would each add a bounded share,
and `build_plan` caps the *total* with LAMBDA, so stacking silently halves what
the second one is worth instead of saying so. Replacing keeps the visible effect
of "I asked for this" independent of how many times you asked.

No kernel access and no I/O, so the whole lifecycle is testable without root.
The HTTP layer in `aciq/api.py` is a thin shell over this.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

#: Where `aciqctl lease` and `aciqctl leases` share state.
#:
#: A file, because two CLI invocations that cannot see each other is a trap: the
#: first version printed "lease-1  device 10.0.1.2 ... 60s" and then the next
#: command said "no active leases", which reads as the lease having been refused
#: rather than as two processes never having met.
DEFAULT_PATH = Path("data/leases.json")

from .model import Flow, Lease, TrafficClass

#: Default time-to-live. Long enough to cover a meeting or a film, short enough
#: that an abandoned request is not a permanent change to the household.
DEFAULT_TTL_S = 90.0

#: Bounds on the requested weight. A weight is a share of the leased allowance,
#: not a share of the link, so >1 is meaningless rather than merely greedy.
MIN_WEIGHT = 0.05
MAX_WEIGHT = 1.0

#: Longest TTL accepted. Not a policy preference: it bounds how long a lease can
#: sit in the plan if the expiry sweep is never run (a long-idle process).
MAX_TTL_S = 3600.0


class IntentError(ValueError):
    """A malformed or unsatisfiable request. Carries an HTTP status."""


def _validate(target: str, ip: str | None, flow: str | None,
              weight: float, ttl_s: float) -> None:
    if target not in ("device", "flow"):
        raise IntentError(f"target must be 'device' or 'flow', not {target!r}")
    if target == "device":
        if not ip:
            raise IntentError("a device lease needs an ip")
        if flow:
            raise IntentError("a device lease must not also name a flow")
    else:
        if not flow:
            raise IntentError("a flow lease needs a flow")
    if not (MIN_WEIGHT <= weight <= MAX_WEIGHT):
        raise IntentError(
            f"weight must be between {MIN_WEIGHT} and {MAX_WEIGHT}, got {weight}")
    if not (0 < ttl_s <= MAX_TTL_S):
        raise IntentError(f"ttl_s must be in (0, {MAX_TTL_S}], got {ttl_s}")


def _scope_key(target: str, ip: str | None, flow: str | None) -> tuple[str, str]:
    """Identity of what a lease applies to. Two leases on one scope collide."""
    return (target, ip if target == "device" else (flow or ""))


@dataclass(frozen=True)
class LeaseStore:
    """Every live lease, plus the clock. Immutable: methods return new stores.

    Frozen so the API's request thread and the experiment's sampling thread
    cannot interleave a read-modify-write. The lock in `LeaseBook` handles the
    swap between them; inside a store there is nothing to race on.
    """

    leases: tuple[Lease, ...] = ()
    _seq: int = 0
    _now: Callable[[], float] = time.time

    # ---- writes ----------------------------------------------------------
    def request(self, target: str, *, ip: str | None = None, flow: str | None = None,
                weight: float = 0.4, ttl_s: float = DEFAULT_TTL_S,
                lease_id: str | None = None) -> tuple["LeaseStore", Lease]:
        """Create a lease, replacing any existing one on the same scope."""
        _validate(target, ip, flow, weight, ttl_s)
        key = _scope_key(target, ip, flow)
        kept = tuple(l for l in self.leases if _scope_key(l.target, l.ip, l.flow) != key)
        created = self._now()
        lid = lease_id or f"lease-{self._seq + 1}"
        lease = Lease(id=lid, target=target, ip=ip, flow=flow, weight=weight,
                      ttl_s=ttl_s, created_at=created)
        return replace(self, leases=kept + (lease,), _seq=self._seq + 1), lease

    def release(self, lease_id: str) -> tuple["LeaseStore", Lease | None]:
        """Remove by id. Returns the removed lease, or None if already gone."""
        for l in self.leases:
            if l.id == lease_id:
                kept = tuple(x for x in self.leases if x.id != lease_id)
                return replace(self, leases=kept), l
        return self, None

    def sweep(self, now: float | None = None) -> "LeaseStore":
        """Drop expired leases. Called before every read.

        Expiry is enforced here *and* by `Lease.expired`, so an unswept store
        still reports the right active set -- the sweep only keeps the stored
        list from growing without bound.
        """
        t = self._now() if now is None else now
        kept = tuple(l for l in self.leases if not l.expired(t))
        return self if kept == self.leases else replace(self, leases=kept)

    # ---- reads -----------------------------------------------------------
    def active(self, now: float | None = None) -> tuple[Lease, ...]:
        """Unexpired leases, oldest first."""
        t = self._now() if now is None else now
        return tuple(sorted((l for l in self.leases if not l.expired(t)),
                            key=lambda l: l.created_at))

    def get(self, lease_id: str, now: float | None = None) -> Lease | None:
        t = self._now() if now is None else now
        for l in self.leases:
            if l.id == lease_id and not l.expired(t):
                return l
        return None

    def for_flow(self, flow: Flow, now: float | None = None) -> Lease | None:
        """The lease covering this flow, if any.

        Device scope wins over flow scope, as in `corrections`: the narrower
        statement is the more deliberate one. Two leases can both match, and
        picking wrongly would hand a specific request to a general one.

        **A device matches on either endpoint, not just the source.** This was
        src-only, and it is wrong for the dominant direction of a home broadband
        link: traffic runs internet -> device, so the device's own address is
        the *destination*. In the testbed, video flows as
        `src=203.0.113.2 dst=10.0.1.2`, so a lease for 10.0.1.2 -- the client's
        address, the thing a user would naturally name -- matched nothing at all.
        The first leased run reported the lease as active and steered nothing,
        which is exactly the failure this endpoint test exists to catch.
        """
        best: Lease | None = None
        for l in self.active(now):
            if l.target == "device" and l.ip in (flow.src, flow.dst):
                cand, prec = l, 1
            elif l.target == "flow" and l.flow == flow.key:
                cand, prec = l, 2
            else:
                continue
            if (best is None
                    or prec > _scope_prec(best)
                    or (prec == _scope_prec(best)
                        and cand.created_at > best.created_at)):
                best = cand
        return best

    def expiring_in(self, now: float | None = None) -> float | None:
        """Seconds until the earliest active lease expires, or None if none."""
        live = self.active(now)
        if not live:
            return None
        t = self._now() if now is None else now
        return max(0.0, min(l.created_at + l.ttl_s for l in live) - t)

    def now(self) -> float:
        """The store's own clock.

        Exposed so callers that render a lease -- `lease_to_dict` -- measure
        against the same time the store does. Without it a lease's `expires_in`
        is computed against wall-clock `time.time()` while its `created_at` came
        from an injected clock, and every lease reads as already expired.
        """
        return self._now()

    def __len__(self) -> int:
        return len(self.active())


def _scope_prec(lease: Lease) -> int:
    return 1 if lease.target == "device" else 2


def load(path: Path | str = DEFAULT_PATH, clock: Callable[[], float] = time.time
         ) -> "LeaseBook":
    """Read the shared lease file, dropping anything already expired.

    A corrupt or absent file yields an empty book rather than an exception: the
    lease store is a convenience, and refusing to start the dashboard because a
    lease file has a stray byte in it would be a worse outcome than forgetting
    the leases.
    """
    p = Path(path)
    try:
        raw = json.loads(p.read_text())
    except (OSError, json.JSONDecodeError):
        # path=p here too. This is the *first ever* use -- the file does not
        # exist yet -- so dropping the path here meant the very first lease was
        # held only in memory and vanished when the command exited. The non-empty
        # branch below had it right, which is why it only showed up on a clean
        # slate and looked intermittent.
        return LeaseBook(clock=clock, path=p)
    leases = []
    for d in raw.get("leases", []) if isinstance(raw, dict) else []:
        try:
            leases.append(Lease(id=str(d["id"]), target=str(d["target"]),
                                ip=d.get("ip"), flow=d.get("flow"),
                                weight=float(d.get("weight", 0.4)),
                                ttl_s=float(d.get("ttl_s", DEFAULT_TTL_S)),
                                created_at=float(d.get("created_at", 0.0))))
        except (KeyError, TypeError, ValueError):
            continue
    seq = max((int(l.id.rsplit("-", 1)[-1]) for l in leases
               if l.id.rsplit("-", 1)[-1].isdigit()), default=0)
    # path=p, not None: a book loaded from a file must still write back to it,
    # or `aciqctl` would read leases it could never release. Symptom was a
    # release that silently did nothing and a reload that still listed the lease.
    return LeaseBook(LeaseStore(leases=tuple(leases), _seq=seq, _now=clock),
                     clock=clock, path=p)


def save(book: "LeaseBook", path: Path | str = DEFAULT_PATH) -> None:
    """Write the shared lease file, expired entries removed.

    Atomic via a temp file and rename, so a crash mid-write cannot leave a
    truncated file that reads as zero leases -- which would silently drop every
    live lease.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    now = book.now()
    payload = {"leases": [lease_to_dict(l, now) for l in book.active(now)]}
    tmp = p.with_suffix(p.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, indent=2))
    tmp.replace(p)


class LeaseBook:
    """Mutable holder with a lock, so threads cannot interleave a request.

    The API accepts requests on a request thread while the experiment samples on
    another. Copy-on-write means a reader always sees a consistent snapshot;
    this lock only makes the read-modify-write atomic.
    """

    def __init__(self, store: LeaseStore | None = None,
                 clock: Callable[[], float] = time.time,
                 path: Path | str | None = None):
        # RLock, not Lock. `request` persists while holding the lock, and
        # `save` reads `book.active()`, which acquires it again -- with a plain
        # Lock that self-deadlocks and the process hangs with no traceback.
        # Reentrancy is exactly the case here: the same thread re-entering its
        # own guard is legitimate, two threads racing is not.
        self._lock = threading.RLock()
        self._store = (store or LeaseStore(_now=clock)).sweep()
        self._clock = clock
        #: Where to persist, if anywhere. None keeps leases in memory only, which
        #: is what a live server wants: the file is for CLI-to-CLI continuity.
        self.path = path

    def _now(self) -> float:
        return self._clock()

    @property
    def store(self) -> LeaseStore:
        with self._lock:
            return self._store

    def request(self, **kw) -> Lease:
        with self._lock:
            # Re-base onto a store whose clock agrees with this book.
            base = replace(self._store, _now=self._clock).sweep(self._now())
            new, lease = base.request(**kw)
            self._store = new
            if self.path is not None:
                save(self, self.path)
            return lease

    def release(self, lease_id: str) -> Lease | None:
        with self._lock:
            new, gone = self._store.release(lease_id)
            self._store = new
            if self.path is not None and gone is not None:
                save(self, self.path)
            return gone

    def now(self) -> float:
        """This book's clock. So renderers and the store agree on "now"."""
        return self._now()

    def active(self, now: float | None = None) -> tuple[Lease, ...]:
        """Live leases. `now` is accepted for symmetry with the store and for
        tests that drive a fake clock; omitting it uses the book's own."""
        return self.store.active(self._now() if now is None else now)

    def for_flow(self, flow: Flow) -> Lease | None:
        return self.store.for_flow(flow, self._now())

    def expiring_in(self) -> float | None:
        return self.store.expiring_in(self._now())

    def to_policy_lease(self) -> Lease | None:
        """The lease `build_plan` understands, or None if nothing is live.

        `build_plan` takes a single lease. With several live it takes the
        earliest-expiring one -- a bounded, explainable choice, rather than an
        arbitrary one that would change as the clock moves.
        """
        live = self.active()
        if not live:
            return None
        return min(live, key=lambda l: l.created_at + l.ttl_s)


def lease_to_dict(lease: Lease, now: float | None = None) -> dict:
    """Wire shape. `expires_at` is absolute so a client can show a countdown."""
    t = time.time() if now is None else now
    return {
        "id": lease.id,
        "target": lease.target,
        "ip": lease.ip,
        "flow": lease.flow,
        "weight": lease.weight,
        "ttl_s": lease.ttl_s,
        "created_at": lease.created_at,
        "expires_at": lease.created_at + lease.ttl_s,
        "expires_in": max(0.0, lease.created_at + lease.ttl_s - t),
    }