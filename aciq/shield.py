"""M9 — the shield: veto rules and the fault/recovery state machine.

Split out from the transaction manager so the rules are pure and testable with
no kernel and no runner.

Veto conditions, and one deliberate non-veto:

* A class below its floor — checked against the **scaled** floor, respecting the
  plan's `degraded` flag. Checking the ideal floor would veto every legitimately
  degraded plan forever.
* Child rates summing above capacity.
* More than one policy change per MIN_CHANGE_WINDOW_S.
* Read-back mismatch.
* Drop / overlimit rate over limit.

**Not a veto: interactive delay.** It rises precisely when capacity has dropped
and the policy is stale — vetoing on it would block the one change that fixes
the problem. Delay is a reported diagnostic.

**Not a veto: backlog.** Gate check 12 measured backlog at 0 throughout a
saturated link, because fq_codel keeps queues short. A backlog veto would
almost never fire, which reads as protection that isn't there.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .model import RatePlan
from .policy import floor_mbps
from .tc import BARE_CLASS_ID, Mismatch, TcTree

#: Minimum seconds between policy changes.
MIN_CHANGE_WINDOW_S = 5.0
#: Sustained breach count inside the window that trips FAULT_PENDING.
BREACHES_TO_FAULT = 3
BREACH_WINDOW_S = 60.0
#: drop/overlimit per second above which a plan is vetoed. Measured saturation
#: ran 24803-65101 overlimits over 25 s, i.e. thousands per second.
DROP_RATE_LIMIT = 5000.0
OVERLIMIT_RATE_LIMIT = 5000.0
#: Recovery backoff, capped. Never unbounded and never never-retried.
BACKOFF_S = (1.0, 2.0, 4.0, 8.0, 16.0, 60.0)
MAX_RETRIES = 5
#: Clean, breach-free seconds required before the retry budget resets.
SUSTAINED_OK_S = 300.0


class Mode(str, Enum):
    MONITOR = "monitor"
    FAULT_PENDING = "fault_pending"
    SAFE_HELD = "safe_held"


@dataclass(frozen=True)
class Violation:
    """A veto reason.

    `severity` matters. Two kinds:

    * ``defer`` — the veto is the mechanism working. Being inside the change
      window means "not yet", not "something is broken". Escalating these to a
      fault put the shield into FAULT_PENDING during perfectly normal
      operation, which then refused legitimate work.
    * ``fault`` — a genuine safety violation or a kernel failure. Only these
      trip the shield.
    """

    code: str
    detail: str
    severity: str = "fault"

    def __str__(self) -> str:
        return f"{self.code}: {self.detail}"


@dataclass
class ShieldState:
    mode: Mode = Mode.MONITOR
    breaches: list[float] = field(default_factory=list)
    last_change_t: float | None = None
    retries: int = 0
    last_fault_t: float | None = None
    last_ok_t: float | None = None
    alarm: str | None = None

    @property
    def in_fault(self) -> bool:
        return self.mode in (Mode.FAULT_PENDING, Mode.SAFE_HELD)


class Shield:
    def __init__(self, state: ShieldState | None = None):
        self.state = state or ShieldState()

    # ---------------- pre-apply vetoes ----------------
    def veto_plan(self, plan: RatePlan) -> list[Violation]:
        out: list[Violation] = []

        if plan.total() > plan.capacity_mbps + 1e-6:
            out.append(Violation(
                "child_sum_exceeds_capacity",
                f"sum(rates)={plan.total():.3f} > capacity={plan.capacity_mbps:.3f}"))

        # Scaled floor when degraded: on a very small link the floors cannot all
        # fit, and M3 scales them rather than silently breaking the invariant.
        base_floor = floor_mbps(plan.capacity_mbps)
        scaled = base_floor
        if plan.degraded and plan.rates:
            scaled = plan.capacity_mbps / len(plan.rates)
        for cls, rate in plan.rates.items():
            if rate + 1e-6 < scaled:
                out.append(Violation(
                    "below_floor",
                    f"{cls.value} rate={rate:.3f} below "
                    f"{'scaled' if plan.degraded else 'required'} floor={scaled:.3f}"))
        return out

    def veto_rate(self, now: float) -> list[Violation]:
        if self.state.last_change_t is None:
            return []
        if (now - self.state.last_change_t) < MIN_CHANGE_WINDOW_S:
            return [Violation(
                "rate_limited",
                f"{(now - self.state.last_change_t):.2f}s since last change, "
                f"minimum {MIN_CHANGE_WINDOW_S}s",
                severity="defer")]
        return []

    def veto_load(self, drop_rate: float, overlimit_rate: float) -> list[Violation]:
        out: list[Violation] = []
        if drop_rate > DROP_RATE_LIMIT:
            out.append(Violation("drop_rate_limit", f"{drop_rate:.0f}/s > {DROP_RATE_LIMIT:.0f}"))
        if overlimit_rate > OVERLIMIT_RATE_LIMIT:
            out.append(Violation("overlimit_rate_limit",
                                 f"{overlimit_rate:.0f}/s > {OVERLIMIT_RATE_LIMIT:.0f}"))
        return out

    def veto_readback(self, mismatches: list[Mismatch]) -> list[Violation]:
        return [Violation("readback_mismatch",
                          f"{m.classid} {m.field}: wanted {m.expected:.3f}, got {m.actual:.3f}")
                for m in mismatches]

    # ---------------- state machine ----------------
    def note_change(self, now: float) -> None:
        self.state.last_change_t = now

    def breach(self, now: float, reasons: list[Violation]) -> None:
        """Apply safe state immediately, then decide fault vs recovery."""
        self.state.breaches.append(now)
        cutoff = now - BREACH_WINDOW_S
        self.state.breaches = [b for b in self.state.breaches if b >= cutoff]

        # Recovery backoff advances on each consecutive fault.
        if self.state.mode is Mode.SAFE_HELD:
            return
        self.state.mode = Mode.FAULT_PENDING
        self.state.last_fault_t = now
        self.state.retries += 1
        if self.state.retries > MAX_RETRIES:
            # SAFE_HELD is a SAFE STATE, not a lock: the safe plan stays applied,
            # the alarm is latched and visible, and manual reset is the only way
            # out. It cannot self-clear because sustained health can only accrue
            # in MONITOR.
            self.state.mode = Mode.SAFE_HELD
            self.state.alarm = (
                f"recovery budget exhausted after {MAX_RETRIES} attempts; "
                f"safe state held, manual reset required "
                f"({'; '.join(str(r) for r in reasons[:3])})")
        else:
            self.state.alarm = f"fault: {'; '.join(str(r) for r in reasons[:3])}"

    def backoff_s(self) -> float:
        i = min(max(self.state.retries - 1, 0), len(BACKOFF_S) - 1)
        return BACKOFF_S[i]

    def may_retry(self, now: float) -> bool:
        """True when a recovery attempt is due. Retry budget wins over a rolling
        window: once backoff reaches 60 s, each attempt lands in its own window,
        so a window-based counter would never reach MAX_RETRIES and would loop
        forever."""
        if self.state.mode is not Mode.FAULT_PENDING:
            return False
        if self.state.last_fault_t is None:
            return True
        return (now - self.state.last_fault_t) >= self.backoff_s()

    def observe_ok(self, now: float) -> None:
        """A clean observation in MONITOR resets the budget after enough time."""
        if self.state.mode is not Mode.MONITOR:
            return
        self.state.breaches = [b for b in self.state.breaches if b >= now - BREACH_WINDOW_S]
        if not self.state.breaches:
            self.state.last_ok_t = self.state.last_ok_t or now
            if self.state.retries and (now - (self.state.last_ok_t or now)) >= SUSTAINED_OK_S:
                self.state.retries = 0
        else:
            self.state.last_ok_t = None

    def reset(self) -> None:
        """Manual reset. The only way out of SAFE_HELD.

        Also clears the change window. Leaving `last_change_t` latched would
        suppress the first policy change after a reset, which in the experiment
        matrix made a later run fail its opening apply as "rate limited" for a
        change that had happened in an entirely different run.
        """
        self.state.mode = Mode.MONITOR
        self.state.retries = 0
        self.state.breaches = []
        self.state.alarm = None
        self.state.last_fault_t = None
        self.state.last_ok_t = None
        self.state.last_change_t = None
