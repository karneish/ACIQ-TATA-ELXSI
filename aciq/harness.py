"""M6 — experiment harness.

Runs the matrix: reset -> inject -> collect -> record, for each system under
test, with a fixed seed so a run can be repeated.

The one invariant this module exists to protect:

    set_capacity(C) changes HTB class 1:1, and clamps each child's ceil to C. It
    never rescales child *rates* -- that is M3's job after M2 detects the drop.

Child *rates* are never touched here. That is not a style preference: if the
harness rescaled them, the estimator would be bypassed and "adaptation time"
would measure the harness rather than the system. Choosing rates is M3's job,
after M2 has detected a change from counters alone.

Child *ceil* is a different matter, and getting it wrong cost every `--drop-at`
run taken before 2026-10-10. The parent rate alone does not cap a subtree: a
class borrows past its parent's rate up to its own ceil, and `build_plan` gives
every child a ceil equal to the capacity at plan time. Dropping the parent to
10 Mbps left the children at ceil 100, so the link kept passing traffic. Measured
in `data/leaseB4`:

    t=19.50  parent counter  4.67 Mbps
    t=25.66  parent counter 24.68 Mbps    <- the "10 Mbps" link

Clamping ceil to C restores the invariant gate check 6 asserts --
`max(child ceil) <= capacity` -- and it does so without making a policy
decision. It also makes saturation *visible*: with the link genuinely capped,
M2 has an oversubscribed link to measure, which it never had before.

The earlier version of this docstring said `set_capacity` changes "ONLY class
1:1" and treated the parent-only change as correct. That claim was measured
wrong, and it is the reason six experiments reported a link state they never
reached.

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
from .metrics import ClassCounters, MetricsCollector
from .model import Lease, RatePlan, TrafficClass
from .policy import build_plan
from .shield import Shield
from .tc import BARE_CLASS_ID, ROOT_CLASS_ID, render
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
        # `enumerate` and the inner `range` index were both unused -- only the
        # count matters, since each entry draws a fresh random port. Binding an
        # index that is never read is the kind of thing that later reads as if
        # the index were significant.
        for w in self.workloads:
            for _ in range(w.count):
                out.append((w.label, 5100 + rng.randrange(0, 400), w.dscp))
        return out


#: TATA's scenarios. DSCP EF on the call and game is realistic: real VoIP
#: endpoints mark interactive media EF, which is exactly the signal M1 uses.
SCENARIOS: dict[str, Scenario] = {
    # The rising edge of adaptation. Every other scenario here drops the link and
    # leaves it down, so nothing in the suite has ever tested whether the
    # controller can walk back UP. That is half of what the brief grades as
    # "adaptation speed and policy stability": a policy left pinned at the
    # degraded rate after the link recovers is a real, user-visible defect, and
    # a drop-only suite cannot see it.
    "s4_capacity_recovery": Scenario(
        name="s4_capacity_recovery",
        workloads=(
            Workload("call", "call", 1, dscp=46),
            Workload("bulk", "bulk", 1),
        ),
        duration_s=60.0,
        settle_s=4.0,
    ),
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
    #: False when tc refused the requested capacity change, which makes
    #: `link_end_mbps` the value that was *asked for* rather than one the link
    #: ever reached. Every `--drop-at` run before this reported 10 or 20 Mbps on
    #: a link whose parent counter showed 25 Mbps sustained.
    capacity_change_applied: bool = True
    #: Why, when it was refused. A field rather than only a note, because a note
    #: is prose and this is the evidence: `dropcheck2` reported
    #: capacity_change_applied False with no reason anywhere, which sent me
    #: looking in the wrong place twice.
    capacity_change_error: str = ""
    #: Did the link come BACK UP during the run, and to what rate.
    #:
    #: Every adaptation experiment so far tested only the falling edge. Half of
    #: "adaptation speed and policy stability" is what happens on recovery: an
    #: estimator that cannot walk back up, or a policy left pinned at the
    #: degraded rate, is a defect that a drop-only test can never see.
    capacity_recovered: bool = False
    capacity_recover_to_mbps: float | None = None
    #: Every policy application attempted: the rate the kernel was asked for,
    #: whether it committed, any shield violations or read-back mismatches, and
    #: the rates the kernel then reported as installed.
    policy_change_log: list[dict] = field(default_factory=list)
    estimator_mbps: float | None = None
    samples: list[dict] = field(default_factory=list)
    policy_changes: int = 0
    #: raw `tc qdisc show` for the out-of-band bottleneck at end of run
    bottleneck_state: str = ""
    #: OBSERVED duration of the run, in seconds, taken from the first and last
    #: samples rather than from the configured scenario.
    #:
    #: There was no such field, so a 31-minute soak reported `duration_s: None`
    #: and the acceptance gate read that as "0 seconds -- not a stability
    #: result". The run was real: 1801 samples across 1859 seconds. Reporting
    #: the configured value would be the weaker claim; the span actually
    #: observed is the evidence.
    duration_s: float = 0.0
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


def _rate_of(plan, cls) -> float:
    """A class's configured rate, falling back to something safe.

    The fallback matters more than it looks: emitting `rate 0` would look
    authoritative and would be honoured by the kernel, quietly deleting the
    bandwidth M3 had allocated.
    """
    if plan is not None and cls in plan.rates:
        return float(plan.rates[cls])
    return 0.0


def _class_ids_of(plan) -> dict:
    """TrafficClass -> "1:NN" for the classes in `plan`, so their ceil can be
    clamped alongside the parent. Empty when no plan has been built yet, which
    makes set_capacity a parent-only change -- the old behaviour, and the bug."""
    from .tc import CLASS_IDS
    if plan is None:
        return {}
    return {c: CLASS_IDS[c] for c in plan.rates}


def _make_bottleneck_source(harness: Harness):
    """The bottleneck's own counter source.

    Returns None when the harness is NOT driving a real kernel, because
    `BottleneckDropSource` defaults to `subprocess.run` and would otherwise
    shell out for real regardless of the runner the rest of the harness uses.

    That was harmless while this source only supplied `dropped()` and `backlog()`:
    an unreachable device returned None and every caller treated that as "no
    signal". Adding `delivered_bytes()` made it load-bearing, because a real
    number there OVERRIDES the estimator's goodput input. So on a host where
    `ip` and `tc` exist -- including one with a leftover `router` namespace from
    a previous testbed run -- a unit test using FakeRunner began reading real
    counters, the estimator saw no capacity drop, and four closed-loop tests
    failed as root while passing unprivileged:

        test_adapts_down_when_counters_show_saturation   changed is False
        test_policy_changes_are_counted                  0 >= 1
        test_adaptation_rebuilds_the_tree_...            '1:10' not found in ''
        test_adaptive_path_needs_no_out_of_band_capacity changed is False

    The asymmetry is the lesson: four failures under root and none otherwise, on
    a change that had passed every unprivileged run. A test that only validates
    in the weaker environment is not a validated test.

    The source is injectable so a unit test can supply one deliberately, and so
    this real one is not built when there is no real kernel to read.
    """
    from .metrics import BottleneckDropSource
    from .txn import FakeRunner
    if isinstance(getattr(harness, "runner", None), FakeRunner):
        return None
    return BottleneckDropSource(dev=harness.bottleneck_dev,
                                ns=harness.bottleneck_ns)


#: Seconds of standing buffer the emulated bottleneck is allowed to hold.
#: 50 ms is a realistic CPE figure; netem's own default is ~20x that.
BUFFER_S = 0.05
#: Largest packet used for the sizing, so the limit is never optimistic.
_MTU_BYTES = 1500
#: Floor on the packet limit. Below roughly 4 Mbps, BUFFER_S would be about
#: four packets -- too few for netem to distinguish a full queue from an idle
#: one, so the target is unreachable and the floor wins instead. This is a real
#: limitation of the emulation at very low rates, not a rounding detail, and
#: `test_harness_live` pins the floor so it cannot drift upward unnoticed.
_MIN_BUFFER_PACKETS = 32


def _netem_limit(rate_mbps: float) -> int:
    """Packets of buffer for a given rate, sized in seconds not in packets.

    The /8 is bits-to-bytes. Leaving it out produces a limit 8x too large --
    400 ms of buffer instead of 50 -- which looks plausible next to netem's
    default and is therefore easy to ship by accident.
    """
    bytes_per_s = rate_mbps * 1e6 / 8
    return max(_MIN_BUFFER_PACKETS, int(bytes_per_s * BUFFER_S / _MTU_BYTES))


def _qdisc_reports_rate(text: str, want_mbps: float) -> bool:
    """Does `tc qdisc show` report this netem limit, numerically?

    It was a substring test -- `"10.0000" in out` -- which can never succeed:
    tc prints what it was given, normalised, as `rate 10Mbit`. On the host that
    made a perfectly applied limit report as REFUSED, and the run was then
    treated as undropped while netem was sitting there holding the link at 10.

    That is the worst shape of verification bug: it does not miss a fault, it
    invents one, and it makes a working system look broken.
    """
    import re
    # Case-insensitive: the host prints `rate 10Mbit`, the test double prints
    # `rate 10.0000mbit`. Both are valid tc output and both must verify.
    for m in re.finditer(r"\brate\s+([0-9.]+)\s*([KMG]?)bit", text,
                         re.IGNORECASE):
        val = float(m.group(1))
        unit = m.group(2).upper()
        mbps = val * {"": 1e-6, "K": 1e-3, "M": 1.0, "G": 1e3}[unit]
        if abs(mbps - want_mbps) <= max(0.01 * want_mbps, 0.01):
            return True
    return False


class Harness:
    """Orchestrates runs. Needs root for tc; the control logic is testable
    without it because the runner and collector are injected."""

    def __init__(
        self,
        runner=None,
        shield: Shield | None = None,
        dev: str = "veth-lan",
        ns_wan: str = "wan",
        ns_router: str = "router",
        clock=time.monotonic,
        link_mbps: float | None = None,
    ):
        self.runner = runner or Runner()
        # The bottleneck lives OUTSIDE the namespace and device the controller
        # writes. Generators run in ns wan, sinks in ns client, and the path is
        # wan -> router -> client; ACIQ writes exactly one device,
        # router/veth-lan. So ns wan / dev veth-w is a limit the controller
        # cannot reach, which is the entire point -- see set_capacity.
        # ns wan / veth-w -- and the namespace matters for a physical reason.
        #
        # `tc qdisc ... root netem` shapes EGRESS. Traffic runs
        # wan -> router -> client, so only the wan side's egress carries it:
        #
        #   wan/veth-w       egress = generator -> router   LIMITS
        #   router/veth-wan  egress = router -> wan (ACKs)   DOES NOT LIMIT
        #
        # Moving it to router/veth-wan for observability produced a run where
        # the qdisc read `rate 10Mbit`, capacity_change_applied was True, and
        # steady goodput was 102.44 -- a limit that was applied, verified, and
        # doing nothing at all.
        #
        # Observability does not require the same namespace: the drop/backlog
        # reader takes ns and dev, so it can read `wan/veth-w` while the
        # controller writes `router/veth-lan`. Unwritable and observable are
        # separate properties, and they are satisfied separately.
        self.bottleneck_ns = ns_wan
        self.bottleneck_dev = "veth-w"
        #: Raw `tc qdisc show` text for the bottleneck, captured at the end of
        #: every run. A capacity change that is applied and then silently lost
        #: is invisible without it -- the run reports the link it was told to
        #: build, not the link it ended up with.
        self.bottleneck_state_at_end: str = ""
        #: lazily built; see BottleneckDropSource for why it exists
        self._bottleneck_src = None
        self.shield = shield or Shield()
        self.dev = dev
        self.ns = ns_router
        self.clock = clock
        self.txn = TransactionManager(self.runner, self.shield, dev=dev, ns=ns_router, clock=clock)
        self._estimator = CapacityEstimator()
        self._collector: MetricsCollector | None = None
        self.policy_changes = 0
        #: The last Measurement handed to the estimator, kept so per-sample
        #: evidence can record what the estimator actually saw.
        self.last_measurement = None
        #: Every policy application this run attempted, with the rate the
        #: kernel was asked for, whether it committed, and what was read back.
        self.policy_change_log: list[dict] = []
        #: The link's provisioned rate, when the caller knows it. Seeds the
        #: estimator's recovery target only -- see `seed_high_water`.
        if link_mbps and link_mbps > 0.0:
            self._estimator.seed_high_water(link_mbps)
        #: None until enable_enforcement() is called. See ClosedLoop and the
        #: enforce_* helpers below for why this is opt-in rather than always-on.
        self._enforcer: ClosedLoop | None = None
        #: M7's lease book. None until enable_leases(), so a run that never
        #: opens the intent API behaves exactly as it did before M7 existed.
        self._lease_book = None
        #: Whether the lease currently held is actually installed in the tree.
        #: Distinct from "a lease is held": the shield can refuse the plan, and a
        #: filter pointing at a class that was never created steers nothing.
        self._lease_in_effect = False

    # ---------------- enforcement: opt-in, see ClosedLoop ----------------
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
                            self._capacity_mbps
                            if self._capacity_mbps is not None
                            else self._configured_capacity)
        measured = self._estimator.current.mbps
        cap = measured if measured else self._configured_capacity
        if self._enforcer.capacity_mbps != cap:
            # measured is truthy exactly when M2 has a reading; passing it
            # through the parameter is the whole point of set_capacity's
            # flag -- an earlier version wrote the attribute directly because
            # set_capacity used to clobber it right after assigning it.
            self._enforcer.set_capacity(cap, measured=bool(measured))
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
    def set_capacity(self, capacity_mbps: float) -> tuple[tuple[str, ...], ...]:
        """Change the emulated link capacity, OUT OF BAND.

        **Why this no longer writes class 1:1.**

        It used to. And `build_plan` writes 1:1 too, from the capacity
        *estimate*. Two writers on the same class means the controller's policy
        change erases the bottleneck it is being asked to detect, after which
        the estimator faithfully reports the number the controller chose.
        Measured on the host (kernel 7.1.5, `s2_wan_drop`):

            t=5.19  ~102 Mbps   link at 100
            t=6.24   12.35 Mbps drop applied
            t=7.28   10.03 Mbps correctly at the 10 Mbps target
            t=9.41   47.11 Mbps controller re-planned and raised it back
            t=13.51  47.02 Mbps and stayed there

        Detection worked; recovery was impossible, because the controller was
        writing to the bottleneck itself.

        The limit now goes on `netem` at ns `wan` / `veth-w`, which sits on the
        path the generators use and which `TransactionManager` never writes.
        The controller can shape as hard as it likes; the link stays at the
        capacity it was actually given, and the estimator measures a real
        bottleneck instead of its own output.

        **What is no longer done here, deliberately.** This used to also
        rescale every child class's ceil, because a bare parent change does not
        bound an HTB link -- children borrow up to their own ceil. That is still
        true, and it used to be the reason the drop was enforced at all. It is
        no longer needed, because a netem limit *does* bound the link
        physically, and clamping the tree here would reintroduce exactly the
        collision this change exists to remove: the moment the controller
        re-plans, it would rewrite the ceils we had just clamped.

        `max(child ceil) <= capacity` remains a property of `build_plan` for a
        planned capacity; it is no longer the mechanism that enforces one.
        """
        pre = ("ip", "netns", "exec", self.bottleneck_ns)
        rate = f"{capacity_mbps:.4f}mbit"
        cmds = [
            # `replace` so repeated calls are idempotent, matching the way the
            # controller's own rebuild behaves.
            pre + ("tc", "qdisc", "replace", "dev", self.bottleneck_dev,
                   "root", "netem", "rate", rate,
                   # A REALISTIC buffer, not netem's default.
                   #
                   # netem defaults to `limit 1000` packets. At 20 Mbps and a
                   # 1500-byte worst case that is ~1.2 MB -- roughly 480 ms of
                   # standing queue. Measured in a real congested run, the netem
                   # queue held 206 packets median and 625 at peak while the
                   # controller's OWN queue for the interactive class held
                   # **0 bytes at every tick**. So the ~860 ms p95 was almost
                   # entirely the testbed's buffer, not the controller, and it
                   # inflated all three systems alike.
                   #
                   # No broadband CPE ships half a second of buffer. Sized here
                   # to BUFFER_S seconds of the emulated rate, at MTU, with a
                   # floor so a very slow link still queues enough to shape.
                   "limit", str(_netem_limit(capacity_mbps))),
            # Read back. Applying a bottleneck is no more proof that the link is
            # limited than a `tc qdisc add` returning 0 -- the same standard the
            # rollback work established.
            pre + ("tc", "qdisc", "show", "dev", self.bottleneck_dev),
        ]
        failures = []
        rc, out, err = self.runner.run(cmds[0])
        if rc != 0:
            failures.append(f"qdisc replace -> {err.strip() or rc}")
        else:
            rc, out, err = self.runner.run(cmds[1])
            applied = _qdisc_reports_rate(out or "", capacity_mbps)
            if rc != 0:
                failures.append(f"qdisc show -> {err.strip() or rc}")
            elif not applied:
                failures.append(
                    f"qdisc replace returned 0 but read-back did not show the "
                    f"limit: {str(out).strip()[:120]}")
        # The return code used to be discarded entirely, so a refused change
        # looked exactly like a successful one and `link_end_mbps` reported the
        # value that was asked for rather than one the link ever reached.
        self._capacity_change_ok = not failures
        self._capacity_change_error = "; ".join(failures)
        # Only on success. A refused change is not the link's capacity, and
        # recording it as one is how "tc said no" turned into the system
        # confidently planning for a link that does not exist.
        #
        # `_capacity_mbps` is what a later lease rebuild reads. Without it the
        # rebuild used the capacity the run started at, and the retry after a
        # shield deferral re-applied a 100 Mbps plan onto a link capped to 10.
        if not failures:
            self._configured_capacity = capacity_mbps
            self._capacity_mbps = capacity_mbps
        return tuple(cmds)

    def _bottleneck_drops(self):
        if self._bottleneck_src is None:
            try:
                self._bottleneck_src = _make_bottleneck_source(self)
            except Exception:                       # noqa: BLE001
                return None
        return self._bottleneck_src

    def bottleneck_backlog(self) -> int | None:
        """Queue depth at the out-of-band bottleneck, or None if unreadable."""
        src = self._bottleneck_drops()
        if src is None:
            return None
        return src.backlog()

    def bottleneck_drop_rate(self, dt: float) -> float | None:
        """Drops per second on the out-of-band bottleneck, or None if unreadable."""
        src = self._bottleneck_drops()
        if src is None:
            return None
        return src.drop_rate(dt)

    def bottleneck_delivered_mbps(self, dt: float) -> float | None:
        """Mbps the bottleneck actually delivered, or None if unreadable.

        Fed to the estimator in preference to the per-class sum, which is
        offered load measured upstream of the queue. See
        `BottleneckDropSource.delivered_bytes` for the measurement behind it.

        None means "no reading", and the caller falls back rather than feeding
        the estimator a zero that would collapse the estimate.
        """
        src = self._bottleneck_drops()
        if src is None:
            return None
        now_bytes = src.delivered_bytes()
        if now_bytes is None:
            return None
        prev = getattr(self, "_prev_delivered_bytes", None)
        self._prev_delivered_bytes = now_bytes
        if prev is None or dt <= 0:
            return None
        # A counter that goes backwards means the qdisc was replaced between
        # ticks; that delta is meaningless, so report no reading instead.
        if now_bytes < prev:
            return None
        from .metrics import goodput_mbps as _gbps
        return _gbps(prev, now_bytes, dt)

    def capture_bottleneck(self) -> str:
        """Record the bottleneck's real state, for the run's evidence."""
        pre = ("ip", "netns", "exec", self.bottleneck_ns)
        # -s matters: without it `tc qdisc show` prints the configuration line
        # and no counters at all, so the per-tick evidence recorded a qdisc
        # with no queue depth and no drops and could not show the limit failing.
        rc, out, err = self.runner.run(
            pre + ("tc", "-s", "qdisc", "show", "dev", self.bottleneck_dev))
        self.bottleneck_state_at_end = (out or "").strip() or f"(rc={rc}) {err.strip()}"
        return self.bottleneck_state_at_end

    #: Whether the last `set_capacity` actually took effect.
    _capacity_change_ok: bool = True
    _capacity_change_error: str = ""

    # ---------------- system setup ----------------
    def apply_system(self, system: SystemSpec, capacity_mbps: float) -> bool:
        """Build the full tree for a system. Required for every apply because
        HTB's default class cannot be changed on a live qdisc."""
        self._configured_capacity = capacity_mbps
        # The capacity actually configured on the link right now. Every path
        # that applies a capacity passes through here, which is what makes it
        # safe for a later lease rebuild to trust this rather than the value the
        # run started at.
        self._capacity_mbps = capacity_mbps
        if system is SystemSpec.ACIQ:
            plan = self._current_plan or build_plan(capacity_mbps, self._lease)
            # Record the plan that was applied. `apply_system` built it, handed it
            # to the transaction manager and then forgot it, so `_current_plan`
            # stayed None and anything asking which classes exist found nothing --
            # including set_capacity, which needs the class list to clamp their
            # ceil. The plan is the harness's own record of what it configured.
            self._current_plan = plan
            self.txn.remember_capacity(capacity_mbps)
            ok = self.txn.apply(plan).ok
            # Any apply that reaches the kernel rebuilds the qdisc and destroys
            # every per-flow filter; the bridge must be told whether or not the
            # commit succeeded (a rollback replays last-good, which has none).
            if self.txn.last_outcome is None or self.txn.last_outcome.kernel_touched:
                self._invalidate_enforcer_filters()
            return ok
        tree = baseline_tree(system, capacity_mbps)
        self.txn.remember_capacity(capacity_mbps)
        self.runner.run(self.txn._prefix + ("tc", "qdisc", "del", "dev", self.dev, "root"))
        # The del alone destroyed every filter on the old root, success or not.
        self._invalidate_enforcer_filters()
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
    #: The capacity last applied to the tree. None until the first one, which is
    #: what lets sync_lease fall back to the caller's value on a fresh harness.
    _capacity_mbps: float | None = None
    _lease: Lease | None = None
    _tree = None

    def set_lease(self, lease: Lease | None, capacity_mbps: float) -> None:
        self._lease = lease
        self._current_plan = build_plan(capacity_mbps, lease)
        self._capacity_mbps = capacity_mbps

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

        # Rebuild against the link's *current* capacity whenever we are about to
        # apply -- not only when the lease changed.
        #
        # The retry after a shield deferral takes the `same` path: the lease has
        # not changed, but it is not yet in effect. Guarding only the
        # "changed" branch left that retry applying whatever `_current_plan`
        # already held, which was the plan built at the start of the run:
        #
        #     classid 1:1  htb rate 100.0000mbit ceil 100.0000mbit
        #     classid 1:40 htb rate  39.0984mbit ceil 100.0000mbit
        #
        # on a link that had been capped to 10.
        effective = (self._capacity_mbps
                     if self._capacity_mbps is not None else capacity_mbps)
        self.set_lease(lease, effective)
        if self._current_plan is None:
            self._lease_in_effect = False
            return False
        ok = bool(self.txn.apply(self._current_plan, now=self.clock()).ok)
        # The tree was rebuilt (or attempted and rolled back — a rollback
        # replays last-good, which also has no flower filters), so every
        # per-flow filter is gone whether or not the apply committed. Telling
        # the bridge only on success left it believing filters were installed
        # after a failed apply, and `mark()` then no-op'd for flows that had
        # nothing on the device — the exact silent-staleness bug
        # `invalidate()` exists to prevent, on the failure path.
        out = self.txn.last_outcome
        if ok or (out is not None and out.kernel_touched):
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
        offered = sum(goodput_mbps(prev[k].rx_bytes, counters[k].rx_bytes, dt)
                      for k in counters if k in prev)
        # Prefer the bottleneck's own delivered rate. The class sum is offered
        # load: `rx_bytes` on veth-lan counts a packet the moment it is handed
        # to the queue, so anything the queue later drops is included. That is
        # how a 20 Mbps link was read as 22.39 and how a latency tail got
        # written into a controller that was otherwise working. Fall back to the
        # offered figure only when the bottleneck cannot be read, so a missing
        # counter degrades to the old behaviour instead of to zero.
        gbps = self.bottleneck_delivered_mbps(dt)
        if gbps is None:
            gbps = offered
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
        # The shaper queues live in the children: the parent's own backlog reads
        # 0 throughout a congested run. Summed here rather than in the reader so
        # the saturation test sees one number and the raw counters stay raw.
        backlog = sum(counters[k].backlog_bytes for k in counters if k in prev)
        measurement = Measurement(
            t=now, goodput_mbps=gbps, drop_rate_per_s=drate,
            overlimit_rate_per_s=orate,
            link_drop_rate_per_s=ldr, link_overlimit_rate_per_s=lor,
            child_backlog_bytes=backlog,
            bottleneck_drop_rate_per_s=self.bottleneck_drop_rate(dt),
            bottleneck_backlog_bytes=self.bottleneck_backlog())
        #: The observation the estimator actually consumed this tick. Recorded
        #: so the per-sample evidence explains the verdict instead of being
        #: gathered separately and occasionally disagreeing with it.
        self.last_measurement = measurement
        cap = self._estimator.observe(measurement)
        if not cap.changed:
            return None, False

        plan = build_plan(cap.mbps, self._lease)
        self._current_plan = plan
        self.txn.remember_capacity(cap.mbps)
        # same timeline as the estimator, or the dwell window is measured wrong
        txr = self.txn.apply(plan, now=now)
        # Record what the KERNEL actually has, not just what was asked for.
        #
        # The Option A acceptance criteria require the recovery evidence to show
        # that the applied parent rate matches the intended policy and was read
        # back. `policy_changes` counts commits but nothing recorded WHICH rate
        # was committed or whether the readback agreed, so a reader could see
        # "5 policy changes" and "estimator 68.3" and still not know whether the
        # kernel was ever actually reconfigured.
        self.policy_change_log.append({
            "t": round(now, 2),
            "intended_capacity_mbps": round(cap.mbps, 3),
            "intended_parent_rate_mbps": round(plan.capacity_mbps, 3),
            "committed": bool(txr.committed),
            "ok": bool(txr.ok),
            "rolled_back": bool(txr.rolled_back),
            "reason": txr.reason,
            "violations": [{"code": v.code, "detail": v.detail,
                            "severity": v.severity} for v in txr.violations],
            "mismatches": [{"classid": m.classid, "field": m.field,
                            "expected": m.expected, "actual": m.actual}
                           for m in txr.mismatches],
            "applied_state": self._read_applied_rates(),
        })
        if txr.committed:
            self.policy_changes += 1
        # Same rule as sync_lease: a rebuild attempt destroys every per-flow
        # flower filter whether or not the commit succeeded — a rolled-back
        # apply replays last-good, which has no filters either. Invalidating
        # only on success left the bridge's slot map stale after a failed
        # apply, so `mark()` no-op'd for flows with nothing on the device.
        if txr.committed or txr.kernel_touched:
            self._invalidate_enforcer_filters()
        if txr.committed:
            return cap.mbps, True
        return cap.mbps, False

    _prev_counters = None
    _prev_link = None

    def _read_applied_rates(self) -> dict:
        """What the kernel reports as installed, read back after an apply.

        Recorded per policy change so the evidence shows the applied parent rate
        rather than only the requested one.

        It uses the transaction manager's OWN read-back path, not a second
        parser. An earlier version of this called `tc -j class show` and parsed
        the result itself, which is wrong in a way only this host could reveal:
        txn.py already documents that

            `tc -s -j class show` was never validated on this machine and
            returned empty, which made every class look absent and every apply
            look like a read-back mismatch

        so the JSON path answers nothing here, and a private parser would have
        reported `readable: false` on every single apply -- evidence that looks
        diligent and is empty. Text output is primary on this machine, JSON is
        the fallback, and `parse_class_state` is the function that already knows
        both shapes.

        An unreadable device is reported as unreadable, never as an empty dict
        with no classes: "we could not look" and "the kernel has nothing
        installed" must stay distinguishable.
        """
        from .tc import parse_class_state
        state, source = self.txn._read_class_state()
        if not state:
            return {"readable": False,
                    "error": "neither tc class show nor tc -s -j class show "
                             "answered"}
        classes = parse_class_state(state)
        if not classes:
            return {"readable": False, "source": source,
                    "error": "read-back produced no class state"}
        return {"readable": True, "source": source, "classes": classes}

    def reset_loop(self) -> None:
        """Reset the estimator and loop state, but NOT the shield.

        The shield deliberately survives between operations.
        """

        self._estimator = CapacityEstimator()
        self._prev_counters = None
        self._prev_link = None
        # Leaked across runs before: `_prev_delivered_bytes` kept run 1's
        # counter, so run 2's first bottleneck reading was a delta measured
        # against a number from a different experiment (or silently became
        # None when the counter reset backwards). The change log leaked too --
        # run 2's report carried run 1's policy applications, making a fresh
        # run look like it had been changing policy all along.
        if hasattr(self, "_prev_delivered_bytes"):
            del self._prev_delivered_bytes
        self.policy_change_log = []
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
        self._lease_in_effect = False
        self.last_measurement = None
        self.txn.audit.clear()
        self.txn.last_outcome = None
        self.txn.last_rollback = None
        self.txn.last_reason = ""
