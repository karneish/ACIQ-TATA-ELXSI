"""FSM controller: adapts, verifies, rolls back, and stands down.

Division of labour with the rest of the engine, stated once:

- `harness.adapt_step` and the estimator decide WHEN a rate change is
  proposed, through the LAW (`aciq.verifier.bound_rate_change`).
- this controller OWNS the aftermath: feeding the before/after verification
  windows, rendering the verdict, performing the rollback, and standing down
  when rollback doesn't stick.

It is deliberately small and boring. Four states:

  STABLE    windows recording; any change notification arms
  ARMED     change applied, waiting for an after-window
  SLEEPING  standby (consecutive rollbacks consumed), no actuation
  COOLDOWN  a rollback just happened; a short quiet interval before STABLE

Bounded state: per-window deque capped at MIN_VERDICT_SAMPLES (extra samples
simply replace nothing; the window stops growing). `notify_change` must be
called ON THE APPLY PATH by the harness — this module never infers a change
from data it didn't see.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from enum import Enum

from .capacity import Measurement
from .verifier import (BoardGuard, MIN_VERDICT_SAMPLES, STANDBY_S, Verdict,
                       timeline_verdict)


class Phase(str, Enum):
    STABLE = "stable"
    ARMED = "armed"
    COOLDOWN = "cooldown"
    SLEEPING = "sleeping"


@dataclass
class Controller:
    """The verification half of the closed loop, as a deterministic FSM.

    `rollback_fn` receives the Verdict when a rollback must happen; it is
    the context's own responsibility (harness/txn runs its transaction).
    Injected, never constructed here, so tests drive everything offline.
    """

    rollback_fn: object | None = None      # callable(Verdict); injected
    window: int = MIN_VERDICT_SAMPLES
    cooldown_s: float = 2.0
    clock: object | None = None
    state: Phase = Phase.STABLE
    guard: BoardGuard = field(default_factory=BoardGuard)
    last_verdict: Verdict | None = None
    rollbacks: int = 0
    # monotonic timestamp of the last phase transition; the harness hands
    # its own clock's value in, so this module never calls time.*.
    phase_since: float = 0.0

    def __post_init__(self):
        # windows shorter than the verdict's own minimum can never render a
        # verdict, so a caller's "tiny" window silently becomes the minimum:
        # configured honestly rather than multiplied insufficient.
        self.window = max(int(self.window), MIN_VERDICT_SAMPLES)
        self.before: deque = deque(maxlen=self.window)
        self.after: deque = deque(maxlen=self.window)

    # pad helper injected separately once the harness is wired
    # ---- life cycle -------------------------------------------------------
    def notify_change(self, now: float) -> bool:
        """Call once, right after a committed plan apply.

        Arms verification. Returns False (and does nothing) while standby is
        in force — a controller in SLEEPING must not verify-changes into
        rollbacks it has already decided not to perform.
        """
        if self.state is Phase.SLEEPING:
            return False
        if self.guard.blocked(now):
            self.state = Phase.SLEEPING
            self.phase_since = now
            return False
        # The before-window is whatever the STABLE phase collected; we do NOT
        # clear it here — the last `window` samples before the change are
        # exactly the baseline the verdict compares against. maxlen keeps it
        # bounded on long stable stretches.
        self.after.clear()
        self.state = Phase.ARMED
        self.phase_since = now
        return True

    def on_measurement(self, m: Measurement, now: float) -> Verdict | None:
        """Feed ONE tick. Returns a Verdict only when a decision WINDOW is
        ready; every other tick returns None. This is how the caller can
        make decisions exactly once per verified change."""
        if self.state is Phase.COOLDOWN:
            if now - self.phase_since >= self.cooldown_s:
                self.state = Phase.STABLE
                self.phase_since = now
            return None
        if self.state is Phase.SLEEPING:
            if now - self.phase_since >= STANDBY_S:
                # sentence served; stand count zeroed inside the guard
                self.guard.blocked(now)
                self.state = Phase.STABLE
                self.phase_since = now
            return None
        if self.state is Phase.STABLE:
            self.before.append(m)
            return None
        self.after.append(m)
        if len(self.after) < self.window:
            return None
        verdict = timeline_verdict(list(self.before), list(self.after))
        self.last_verdict = verdict
        # today's after-window becomes tomorrow's before-window
        self.before.clear()
        self.before.extend(self.after)
        self.after.clear()
        if verdict.outcome == "rollback":
            # the guard counts BEFORE the callback so standby is decided even
            # if the rollback fn blows up
            self.guard.note_verdict(verdict, now)
            self.rollbacks += 1
            if self.rollback_fn is not None:
                try:
                    self.rollback_fn(verdict)
                except Exception:
                    # the failure mode where a rollback loses is losing ONE
                    # rollback; crashing the measurement loop is worse.
                    pass
        else:
            self.guard.note_verdict(verdict, now)
        self.state = (Phase.SLEEPING
                      if self.guard.standby_until is not None else
                      (Phase.COOLDOWN if verdict.outcome == "rollback"
                       else Phase.STABLE))
        self.phase_since = now
        return verdict

    def teardown(self) -> None:
        """Idempotent: same contract as Bridge/teardown elsewhere — calling
        it twice, or on a fresh controller, must not raise."""
        self.before.clear()
        self.after.clear()
