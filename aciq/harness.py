"""M6 — experiment harness.

Runs the matrix: reset -> inject -> collect -> record, for each system under
test, with a fixed seed so a run can be repeated.

The one invariant this module exists to protect:

    set_capacity(C) changes ONLY HTB class 1:1. It never rescales children.

That is not a style preference. Gate runs 1 and 2 measured that changing the
parent rate alone does not cap throughput (28.5 Mbps through a 20 Mbps parent),
because a class borrows past its parent's rate up to its own `ceil`. Rescaling
children is M3's job, and only after M2 has detected the drop. If the harness
rescaled them, the whole estimator would be bypassed and "adaptation time"
would measure the harness rather than the system.

Capacity is therefore delivered three ways, all from this module:

  static    baselines are never told. Realistic: a static router does not learn.
  informed  baselines are handed the new capacity. An oracle no real device is,
            included to separate "queueing well" from "adapting".
  adaptive  nobody is told. M2 must observe it from counters alone.
"""

from __future__ import annotations

import json
import random
import time
from dataclasses import asdict, dataclass, field
from enum import Enum

from .bridge import Bridge
from .capacity import CapacityEstimator
from .closedloop import ClosedLoop, Verdict
from .classify import FlowFeatures
from .corrections import CorrectionStore
from .metrics import ClassCounters, CounterSnapshot, MetricsCollector
from .model import Lease, RatePlan, TrafficClass
from .policy import build_plan
from .shield import Shield
from .tc import BARE_CLASS_ID, ROOT_CLASS_ID, ROOT_HANDLE, build_tree, render
from .txn import Runner, TransactionManager


class SystemSpec(str, Enum):
    """The three systems compared. Identical bottleneck, different queueing."""

    B0 = "b0_fifo"          # one class, pfifo limit 1000
    B1 = "b1_cake95"        # one class, cake at 95% of link
    ACIQ = "aciq"           # four classes, fq_codel each, rate + ceil


class CapacityMode(str, Enum):
    STATIC = "static"
    INFORMED = "informed"
    ADAPTIVE = "adaptive"


#: HTB handles used by the baseline single-class trees. 1:50 is deliberate: it
#: matches the leaf used in gate checks 10a/10b so the baselines run the exact
#: configuration that was measured to work.
SINGLE_CLASS_ID = "1:50"


@dataclass(frozen=True)
class Workload:
    kind: str          # call | game | video | bulk
    label: str
    count: int = 1
    dscp: int | None = None


@dataclass(frozen=True)
class Scenario:
    name: str
    workloads: tuple[Workload, ...]
    duration_s: float = 30.0
    settle_s: float = 4.0

    def seed_workloads(self, seed: int) -> list[tuple[str, int, int | None]]:
        """Deterministic (label, port, dscp) triples so a run can be repeated.

        Ports are assigned from a fixed base plus the label's index, NOT from the
        generator defaults, so that no workload is identified by its port. M1
        must classify on behaviour and DSCP, never on 'it is the generator'.
        """
        rng = random.Random(seed)
        out = []
        for i, w in enumerate(self.workloads):
            for n in range(w.count):
                out.append((w.label, 5100 + rng.randrange(0, 400), w.dscp))
        return out


#: TATA's scenarios. DSCP EF on the call and game is realistic: real VoIP
#: endpoints mark interactive media EF, which is exactly the signal M1 uses.
SCENARIOS: dict[str, Scenario] = {
    "s1_iso_during_call": Scenario(
        name="s1_iso_during_call",
        workloads=(
            Workload("call", "call", 1, dscp=46),
            Workload("bulk", "bulk", 1),
        ),
        duration_s=30.0,
    ),
    "s2_wan_drop": Scenario(
        name="s2_wan_drop",
        workloads=(
            Workload("call", "call", 1, dscp=46),
            Workload("bulk", "bulk", 1),
        ),
        duration_s=40.0,
    ),
    "s3_tv_and_gaming": Scenario(
        name="s3_tv_and_gaming",
        workloads=(
            Workload("game", "game", 1, dscp=46),
            Workload("video", "tv1", 1),
            Workload("video", "tv2", 1),
            Workload("video", "tv3", 1),
        ),
        duration_s=40.0,
    ),
}


@dataclass
class RunResult:
    scenario: str
    system: str
    capacity_mode: str
    seed: int
    link_start_mbps: float
    link_end_mbps: float
    estimator_mbps: float | None = None
    samples: list[dict] = field(default_factory=list)
    policy_changes: int = 0
    notes: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        return json.dumps(asdict(self), indent=2)


def baseline_tree(system: SystemSpec, capacity_mbps: float):
    """Single-class tree for B0 and B1. Both proven by gate checks 10a/10b.

    The parent still caps the link, and the single leaf's ceil is clamped to
    capacity — the measured rule. B1 sits at 95% so it does not fight the
    parent for the same bytes (double shaping at equal rates is unpredictable).
    """
    from .tc import TcClass, TcTree
    # Separate argv elements. A single "cake bandwidth 95mbit" token makes tc
    # fail with "Specified qdisc kind is unknown", which reads like a missing
    # module rather than a malformed argument.
    leaf = (("pfifo", "limit", "1000") if system is SystemSpec.B0
            else ("cake", "bandwidth", f"{0.95 * capacity_mbps:.4f}mbit"))
    return TcTree(
        capacity_mbps=capacity_mbps,
        default_class=SINGLE_CLASS_ID.split(":")[1],
        classes=(
            TcClass(ROOT_CLASS_ID, BARE_CLASS_ID, capacity_mbps, capacity_mbps),
            TcClass(SINGLE_CLASS_ID, ROOT_CLASS_ID, capacity_mbps, capacity_mbps, leaf=leaf),
        ),
        filters=(),
    )


class Harness:
    """Orchestrates runs. Needs root for tc; the control logic is testable
    without it because the runner and collector are injected."""

    def __init__(
        self,
        runner=None,
        shield: Shield | None = None,
        dev: str = "veth-lan",
        ns_router: str = "router",
        clock=time.monotonic,
    ):
        self.runner = runner or Runner()
        self.shield = shield or Shield()
        self.dev = dev
        self.ns = ns_router
        self.clock = clock
        self.txn = TransactionManager(self.runner, self.shield, dev=dev, ns=ns_router, clock=clock)
        self._estimator = CapacityEstimator()
        self._collector: MetricsCollector | None = None
        self.policy_changes = 0
        #: None until enable_enforcement() is called. See aciq/enforce.py for why
        #: this is opt-in rather than always-on.
        self._enforcer: ClosedLoop | None = None
        #: M7's lease book. None until enable_leases(), so a run that never
        #: opens the intent API behaves exactly as it did before M7 existed.
        self._lease_book = None
        #: Whether the lease currently held is actually installed in the tree.
        #: Distinct from "a lease is held": the shield can refuse the plan, and a
        #: filter pointing at a class that was never created steers nothing.
        self._lease_in_effect = False

    # ---------------- enforcement: opt-in, see aciq/enforce.py ----------------
    @property
    def enforcement_enabled(self) -> bool:
        return self._enforcer is not None

    def enable_enforcement(self, corrections=None, capacity_mbps: float = 100.0,
                           dev: str | None = None, in_if: str | None = None,
                           ns: str | None = None, executor=None) -> ClosedLoop:
        """Turn classification into per-flow tc filters.

        Idempotent: calling it twice returns the same enforcer rather than
        building a second Bridge, because two bridges would each enumerate and
        delete the same filters on teardown.
        """
        if self._enforcer is not None:
            return self._enforcer
        # executor is injectable for the same reason `runner` is on __init__:
        # setup() enumerates the tc tree, which needs root, and a control-logic
        # test should not need root to prove a decision reaches the kernel.
        self._enforcer = ClosedLoop(
            Bridge(dev or self.dev, in_if or "eth0", ns or self.ns,
                   executor=executor),
            corrections=corrections if corrections is not None else CorrectionStore(),
            capacity_mbps=capacity_mbps,
        )
        self._enforcer.bridge.setup()
        return self._enforcer

    def enable_leases(self, book) -> None:
        """Let M7 leases influence both classification and the rate plan.

        Order matters and is not obvious. The *plan* reserves capacity for the
        leased class (build_plan creates it and takes the share from the others),
        and the *classifier* routes the leased flow into it. Doing only the first
        reserves an empty queue -- which is the state v0 shipped, where class
        1:40 was given bandwidth and nothing ever arrived. Doing only the second
        steers traffic to a class with no guaranteed rate, which is worse:
        the flow would compete in fq_codel with everything else.
        """
        self._lease_book = book
        if self._enforcer is not None:
            self._enforcer.leases = book

    @property
    def leases(self):
        return self._lease_book

    def disable_enforcement(self) -> None:
        """Remove every filter and go back to reporting-only.

        Teardown rather than just dropping the reference: a filter that outlives
        the enforcer keeps steering a flow to a class nothing is watching, which
        is exactly the residue check 20 was written to catch.
        """
        if self._enforcer is not None:
            self._enforcer.teardown()
            self._enforcer = None

    def enforce(self, features: FlowFeatures, now: float | None = None) -> Verdict | None:
        """Classify one flow and enforce the verdict. None if not enabled.

        Returning None rather than raising when enforcement is off: most callers
        run in reporting-only mode, and a run that silently classified without
        enforcing is a legitimate thing to want.
        """
        if self._enforcer is None:
            return None
        # Capacity comes from M2's *measurement*, never from what was configured
        # on class 1:1. Using the configured rate would classify every flow
        # against a link that does not exist: `tc class change ... rate 20mbit`
        # followed by a run that still measures 92 Mbps is the whole reason M2
        # exists. `apply_system`/`set_capacity` record what was configured, and
        # that is a fallback for the window before the first measurement -- not
        # the input to a decision.
        if self._lease_book is not None:
            # Every tick, and through txn.apply, so the shield gates it. This is
            # what makes a lease *reserve* bandwidth rather than merely
            # reclassify into a queue that has none. Cheap once applied: the
            # call is a no-op while the lease is unchanged and already in effect.
            self.sync_lease(self._lease_book.to_policy_lease(),
                            self._configured_capacity)
        measured = self._estimator.current.mbps
        cap = measured if measured else self._configured_capacity
        if self._enforcer.capacity_mbps != cap:
            self._enforcer.set_capacity(cap)
            self._enforcer.capacity_is_measured = bool(measured)
        return self._enforcer.apply(features, now=now)

    #: What was last written to class 1:1. A fallback for the window before M2
    #: has a reading, never the input to a classification.
    def _invalidate_enforcer_filters(self) -> None:
        """Tell the bridge its filters are gone, after a rebuild.

        Best effort by design: the enforcer may not exist, and a failure here
        must not stop a capacity change from being applied. The alternative --
        leaving stale state -- is a silent no-op on the next mark, which is the
        bug this exists to prevent.
        """
        if self._enforcer is None:
            return
        try:
            self._enforcer.bridge.invalidate()
        except Exception:
            pass

    _configured_capacity: float = 100.0

    # ---------------- the invariant ----------------
    def set_capacity(self, capacity_mbps: float) -> tuple[str, ...]:
        """Change the emulated link capacity. ONLY class 1:1.

        Deliberately a single tc call. Rescaling children here would bypass M2
        and M3 entirely, which is the mistake gate run 1 exposed.
        """
        pre = ("ip", "netns", "exec", self.ns)
        argv = pre + (
            "tc", "class", "change", "dev", self.dev,
            "parent", BARE_CLASS_ID, "classid", ROOT_CLASS_ID, "htb",
            "rate", f"{capacity_mbps:.4f}mbit", "ceil", f"{capacity_mbps:.4f}mbit",
        )
        self.runner.run(argv)
        self._configured_capacity = capacity_mbps
        return argv

    # ---------------- system setup ----------------
    def apply_system(self, system: SystemSpec, capacity_mbps: float) -> bool:
        """Build the full tree for a system. Required for every apply because
        HTB's default class cannot be changed on a live qdisc."""
        self._configured_capacity = capacity_mbps
        if system is SystemSpec.ACIQ:
            plan = self._current_plan or build_plan(capacity_mbps, self._lease)
            self.txn.remember_capacity(capacity_mbps)
            return self.txn.apply(plan).ok
        tree = baseline_tree(system, capacity_mbps)
        self.txn.remember_capacity(capacity_mbps)
        self.runner.run(self.txn._prefix + ("tc", "qdisc", "del", "dev", self.dev, "root"))
        for argv in render(tree, dev=self.dev, ns=self.ns):
            rc, _, err = self.runner.run(argv)
            if rc != 0:
                # Record why. A bare False left the report saying
                # "apply_system failed:" with nothing after it, which is
                # impossible to act on.
                self.txn.last_reason = (
                    f"{' '.join(argv)} -> {err.strip() or f'exit {rc}'}")
                return False
        self._tree = tree
        self.txn.last_reason = ""
        return True

    _current_plan: RatePlan | None = None
    _lease: Lease | None = None
    _tree = None

    def set_lease(self, lease: Lease | None, capacity_mbps: float) -> None:
        self._lease = lease
        self._current_plan = build_plan(capacity_mbps, lease)

    def sync_lease(self, lease: Lease | None, capacity_mbps: float) -> bool:
        """Make the tree match the lease. Returns whether the lease is in effect.

        Applied immediately rather than at the next capacity event: a lease is a
        person asking for something *now*, and waiting for the next M2 reading
        would mean waiting up to a sampling interval for a deliberate action.

        Goes through `txn.apply`, so the shield's vetoes still apply. A lease
        large enough to break an invariant is refused, not forced.

        **Retries while the shield is rate-limiting.** This is the bug the first
        leased run found. `apply_system` has just changed policy, so the shield's
        5-second change window rejects the lease plan at t=0 -- and an early
        return on "the lease has not changed" then meant it was never retried.
        Class 1:40 was never created, the per-flow filter pointed at a class that
        did not exist, and the run reported the lease as held while steering
        nothing. Unchanged-but-not-yet-applied is a third state, distinct from
        both "unchanged and applied" and "changed".
        """
        # No lease and nothing installed: there is nothing to do, and saying so
        # is the whole fix. `enforce()` calls this every tick, so an "unchanged"
        # that still applies rebuilds the entire qdisc once the shield's window
        # opens -- and a rebuild destroys every per-flow flower filter on
        # parent 1:, while the bridge's own state still says they are installed.
        # That loop ran every 5 s for the whole of a leased-B run and silently
        # dumped video into the default class. Ten commits, `policy_changes=0`.
        if lease is None and self._lease is None:
            self._lease_in_effect = False
            return True

        same = ((lease.id if lease else None) == (self._lease.id if self._lease else None)
                and (lease.weight if lease else None)
                == (self._lease.weight if self._lease else None))
        if same and self._lease_in_effect:
            return True

        if not same:
            self.set_lease(lease, capacity_mbps)
        if self._current_plan is None:
            self._lease_in_effect = False
            return False
        ok = bool(self.txn.apply(self._current_plan, now=self.clock()).ok)
        if ok:
            # The tree was rebuilt, so every per-flow filter went with it. Tell
            # the bridge, or it keeps believing filters are installed and
            # `mark()` returns a no-op for a flow that has none.
            self._invalidate_enforcer_filters()
            # Attributed separately from a capacity change. A plan applied here
            # still rebuilds the qdisc, so it is a policy change in every sense
            # that matters to a reader -- and `policy_changes` staying 0 while
            # ten commits sat in the audit is how this went unnoticed.
            self.policy_changes += 1
        # `and lease is not None`, because applying a plan that has no leased class
        # succeeds trivially. Reading `ok` alone reported a lease "in effect" when
        # there was no lease at all -- which is the state after every expiry.
        self._lease_in_effect = ok and lease is not None
        return self._lease_in_effect

    # ---------------- closed loop: M2 -> M3 -> M4 ----------------
    def adapt_step(self, counters: dict[TrafficClass, ClassCounters], dt: float,
                   now: float, link=None) -> tuple[float | None, bool]:
        """One closed-loop iteration, using only what a counter reader sees.

        Returns (capacity_mbps, changed). Never reads class 1:1's *configured*
        rate — only its observed counters, via `link`.
        """
        from .metrics import goodput_mbps, rate_per_s
        prev = getattr(self, "_prev_counters", None)
        prev_link = getattr(self, "_prev_link", None)
        if prev is None or dt <= 0:
            self._prev_counters = counters
            self._prev_link = link
            return None, False
        gbps = sum(goodput_mbps(prev[k].rx_bytes, counters[k].rx_bytes, dt)
                   for k in counters if k in prev)
        # Child rates are still computed, but they no longer drive saturation.
        drate = sum(rate_per_s(prev[k].drops, counters[k].drops, dt)
                    for k in counters if k in prev)
        orate = sum(rate_per_s(prev[k].overlimits, counters[k].overlimits, dt)
                    for k in counters if k in prev)
        ldr = rate_per_s(prev_link.drops, link.drops, dt) if (link and prev_link) else None
        lor = (rate_per_s(prev_link.overlimits, link.overlimits, dt)
               if (link and prev_link) else None)
        self._prev_counters = counters
        self._prev_link = link

        from .capacity import Measurement
        cap = self._estimator.observe(Measurement(
            t=now, goodput_mbps=gbps, drop_rate_per_s=drate,
            overlimit_rate_per_s=orate,
            link_drop_rate_per_s=ldr, link_overlimit_rate_per_s=lor))
        if not cap.changed:
            return None, False

        plan = build_plan(cap.mbps, self._lease)
        self._current_plan = plan
        self.txn.remember_capacity(cap.mbps)
        # same timeline as the estimator, or the dwell window is measured wrong
        if self.txn.apply(plan, now=now).committed:
            self.policy_changes += 1
            # Same as above: a committed apply rebuilt the qdisc, so the
            # bridge's filters are gone even though its state says otherwise.
            self._invalidate_enforcer_filters()
            return cap.mbps, True
        return cap.mbps, False

    _prev_counters = None
    _prev_link = None

    def reset_loop(self) -> None:
        """Reset the estimator and loop state, but NOT the shield.

        The shield deliberately survives between operations.
        """

        self._estimator = CapacityEstimator()
        self._prev_counters = None
        self._prev_link = None
        self.policy_changes = 0

    def reset_for_run(self) -> None:
        """Full per-run reset.

        Without this, runs leak into each other: the shield's dwell timestamp
        from run 1 is still set when run 2 starts, so the first policy change of
        run 2 is vetoed as rate-limited. Each run is an independent experiment
        and must not inherit the previous one's timing.
        """
        self.reset_loop()
        self.shield.reset()
        self._current_plan = None
        self._lease = None
        self.txn.audit.clear()
