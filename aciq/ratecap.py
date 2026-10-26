"""M2.5 — the rate governor: decouples the applied rate from the estimator.

THE DEFECT THIS MODULE EXISTS FOR (fix 17, docs/evidence/fix/diagnosis.md)

`Harness._adapt_step_inner` used to apply the estimator's belief verbatim:
`applied = bound.rate` at harness.py:996, with nothing between the estimator
and the tree but the law's dwell/step bounds. Two measured consequences on
the s1/s2/s4 matrix:

* the netem token bucket's startup bursts (Sent/dt readings of 111-114 Mbps
  against a true 100 Mbps link) walked the EWMA estimate up to 101.7-105.2,
  the tree was configured at that whole number, stayed ABOVE the link, and
  the out-of-band bottleneck queue grew to 1.9-3.0 MB of GRO super-packets.
  Call p95 was 238.89 ms against B0's 250.71 ms -- the shaper did not bind.
* after a true capacity drop, the first transition-tick reading was adopted
  whole (FAST_DROP_RATIO, alpha=1.0), the step-clamped tree then sat at 78.4
  Mbps against a 20 Mbps link for the rest of the run, and the hysteresis
  band (0.10 x estimate vs the EWMA-mixed delta) pinned the estimate at 23.8
  forever: any gap under ~16.7% (0.10 / 0.6) could never escape, and the
  delivered counter's honest readings of 19.5-20.9 Mbps could not move it.

WHAT IS FIXED HERE, IN ORDER

1. A HARD CEILING. The applied rate may never exceed
   `cap_fraction x belief`, default 0.90 (configurable 0.90-0.95). On the
   matrix this puts the tree at 0.90 x 102.45 = 92.2 Mbps in s1 -- below the
   true 100 Mbps link, so the bottleneck queue never fills from our side and
   interactive latency stops depending on a FIFO we do not control. The
   residual estimate error in s2/s4 measured +9% (est-stall fix, see the
   hysteresis change in aciq.capacity); 0.90 x 1.09 = 0.98 keeps even that
   safely under the link. This coupling is why the default is 0.90 and not
   0.95: the ceiling only holds while
   `cap_fraction x (1 + estimate_error) < 1`.
2. LATENCY-INFLATION FEEDBACK. While the measured queueing delay -- the
   bottleneck's backlog divided by its delivered rate, our existing probe
   (bottleneck_backlog_bytes / bottleneck_delivered_mbps) -- exceeds
   `inflation_threshold_ms`, the applied rate is ratcheted DOWN by
   down_step_frac (10%) per decision, whatever the estimator currently
   believes. When the delay has been at or below `clear_threshold_ms` for
   `hold_clear_s` (10 s) AND offered demand exceeds the applied rate by more
   than probe_ratio (5%), the applied rate is ratcheted UP by up_step_frac
   (2%) per decision. Up is deliberately slower than down and is always
   bounded by the same ceiling: an over-eager probe can only ever cost one
   ratchet-width of latency, never an outage.
3. A CHANGE BUDGET. At most `max_changes_per_min` rate decisions per rolling
   minute. Above it the governor holds and says so. The tree should never
   flap faster than a human could follow.

WHAT IS NOT HERE, DELIBERATELY

* The law stays untouched (dwell, step, floor, emergency, rollback/stand-
  down). The governor proposes; `bound_rate_change` disposes. Everything
  the verifier rejects still means "no rate moves".
* The bottleneck's delay probe being unreadable (netem absent, e.g. offline
  tests) means NO ratchet, not a guess: the ceiling alone still applies, and
  no delay is ever invented.
* No rate floor of its own: the plan's floors (aciq.policy.floor_total_mbps)
  decide what the tree can legally carry. The governor receives the floor
  from the harness and never proposes below it.
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass

#: The estimator's belief is treated as a ceiling, not an application.
#: 0.90-0.95 configurable; 0.90 because the s2/s4 estimate stall measures
#: +9% after the hysteresis fix and 0.90 x 1.09 = 0.98 x link.
CAP_FRACTION = 0.90

#: The rate the ACIQ tree is BUILT at, before any measurement exists
#: (docs/evidence/task2-params.md #4). The post-fix S1 artefacts show the
#: launch ramp burst queueing in the netem's own buffer while the tree sat at
#: 1.00 x link for the first tick, producing call p95 82-84 ms against
#: CAKE-static's 1.45. Shaping from the first packet costs nothing when the
#: number is exactly the ceiling the first governor commit reaches anyway.
INITIAL_PARENT_FRACTION = CAP_FRACTION

#: Bottleneck queueing delay above which the tree must shrink. The same
#: netem at steady, sub-link traffic shows 0.9-1.7 ms (14.4 kB residue at
#: 100 Mbps, measured in the fix 17 diagnosis); a burst fills 1.2-1.9 MB in
#: the first two seconds. 20 ms is above anything a working shaper produces
#: and far below the 238 ms the unshaped tree produced.
INFLATION_THRESHOLD_MS = 20.0

#: Delay at or below which the link counts as CLEAR for the probe-up gate.
#: Half the inflation threshold: a queue that only just stopped hurting is
#: not a queue that has drained, and the proofs stay conservative.
CLEAR_THRESHOLD_MS = 10.0

#: Sustained-clear seconds required before the rate may be allowed to rise.
HOLD_CLEAR_S = 10.0

#: Fraction of the applied rate removed per ratchet step while delay is
#: inflated. The law's 5 s dwell makes this the effective pace floor-bound;
#: the law's own 25% step (50% under emergency drops) still caps every
#: commit, so nothing here bypasses it.
DOWN_STEP_FRAC = 0.10

#: Fraction of the applied rate added per probe-up step. Slow: a wrong up
#: costs one ratchet-width of delay, and the down path is one step behind.
UP_STEP_FRAC = 0.02

#: Offered demand must exceed the applied rate by this factor before a
#: probe-up may run. Probing into idle demand is pointless; probing into
#: standing demand is how the ceiling is ever reached.
PROBE_RATIO = 1.05

#: Per rolling minute, how many rate RISES the governor generates. Falls do
#: not consume the budget at all: post-fix run evidence (docs/evidence/
#: task2-params.md) shows a drop-tick descent starved by its own refused
#: attempts - six stamps, three of them dwell-refused, filled the 6/min
#: ledger and the kernel root then sat at 3.23x the deliverable for the rest
#: of every S2/S4 run. Descent is bounded by the law's dwell instead; the
#: flap risk this budget exists for is a risk only when the rate is rising.
MAX_CHANGES_PER_MIN = 6

#: Delay EMA at which the law is handed a delay emergency: a single DOWN move
#: may land at the want in one commit, skipping the dwell, subject to a
#: cooldown (next constant). Declared in docs/evidence/task2-params.md from
#: the artefacts: capacity drops at rate do NOT produce packet drops, so the
#: existing >=500 drop/s emergency never fired; and the measured transient
#: delay reaches 99-149 ms while a healthy link subtracts 0.9-1.7 ms.
DELAY_EMERGENCY_MS = 100.0

#: One delay emergency per this many seconds; between clearances descent
#: proceeds at the normal dwell-bounded pace. ~= 4 dwell windows.
DELAY_EMERGENCY_COOLDOWN_S = 20.0

#: EMA weight for the delay series. 0.5 keeps direction readable; anything
#: closer to 1 follows the netem's burst artifacts tick by tick.
DELAY_ALPHA = 0.5

_EPS = 1e-9


@dataclass(frozen=True)
class GovernorConfig:
    """All tunables in one dataclass; see the module docstring for provenance."""

    cap_fraction: float = CAP_FRACTION
    inflation_threshold_ms: float = INFLATION_THRESHOLD_MS
    clear_threshold_ms: float = CLEAR_THRESHOLD_MS
    hold_clear_s: float = HOLD_CLEAR_S
    down_step_frac: float = DOWN_STEP_FRAC
    up_step_frac: float = UP_STEP_FRAC
    probe_ratio: float = PROBE_RATIO
    max_changes_per_min: int = MAX_CHANGES_PER_MIN
    delay_alpha: float = DELAY_ALPHA
    delay_emergency_ms: float = DELAY_EMERGENCY_MS
    delay_emergency_cooldown_s: float = DELAY_EMERGENCY_COOLDOWN_S

    def __post_init__(self):
        if not (0.5 < self.cap_fraction < 0.999):
            raise ValueError(f"cap_fraction {self.cap_fraction} outside (0.5, 1)")
        if not (0.0 < self.clear_threshold_ms < self.inflation_threshold_ms):
            raise ValueError("clear_threshold must be below inflation threshold")
        if not (self.inflation_threshold_ms < self.delay_emergency_ms):
            raise ValueError(
                f"delay_emergency_ms {self.delay_emergency_ms} must exceed "
                f"inflation threshold {self.inflation_threshold_ms}")
        if not (0.0 < self.down_step_frac < 1.0
                and 0.0 < self.up_step_frac < self.down_step_frac):
            raise ValueError(
                f"steps must satisfy 0 < up({self.up_step_frac}) "
                f"< down({self.down_step_frac}) < 1")
        if self.max_changes_per_min < 1:
            raise ValueError("max_changes_per_min must be >= 1")
        for _n, _v in (("hold_clear_s", self.hold_clear_s),
                       ("delay_alpha", self.delay_alpha)):
            if _v <= 0.0:
                raise ValueError(f"{_n} must be positive")


@dataclass(frozen=True)
class GovernorDecision:
    """One tick's outcome. Recorded wholesale into the run evidence."""

    rate: float                  # what the controller should want this tick
    reason: str                  # always filled, even when nothing moved
    belief_mbps: float | None    # the estimator's number this tick
    ceiling_mbps: float | None   # cap_fraction x belief, after the checks
    delay_ms: float | None       # backlog / delivered, this tick
    delay_ema_ms: float | None   # the smoothed value the ratchet reads
    changed: bool                # True when rate moved this tick
    delivered_mbps: float | None = None   # post-queue goodput this tick
    delay_emergency: bool = False         # clearance fired this tick
    t: float = 0.0               # monotonic stamp the caller handed us


class RateGovernor:
    """Turns (estimator belief, delivered rate, bottleneck delay) into a rate
    the tree may enforce, bounded hard by `cap_fraction x belief`.

    Stateless about the TREE: the caller passes the rate currently applied
    each tick, so `reset_loop` needs no governor re-seeding and there is no
    state that can silently disagree with the kernel's readback.
    """

    def __init__(self, config: GovernorConfig | None = None,
                 clock=time.monotonic):
        self.cfg = config or GovernorConfig()
        self._clock = clock
        self._delay_ema: float | None = None
        self._clear_since: float | None = None
        # (now, rose) pairs: the ledger of real changes, so refund can pop
        # exactly the stamp it is refunding and the rise budget reads only
        # the rises.
        self._change_ts: deque = deque(maxlen=64)
        # Last tick a delay emergency clearance was spent; the cooldown keeps
        # a shrinking episode from becoming a rapid-fire series of full jumps.
        self._delay_emergency_last: float | None = None
        #: Full decision log for the run artefact. One small dict per tick.
        self.log: list[dict] = []

    # ------------------------------------------------------------------
    def refund_last_change(self) -> bool:
        """Give the budget back for a change that never touched the kernel.

        The budget's currency is REAL change: the stamp is taken when a
        decision differs from the applied rate. But an apply that fails (or a
        transaction whose rollback replays last-good) leaves the kernel ex-
        actly as it was -- an S5(c)-style injected failure would otherwise
        spend the budget on nothing and leave the post-drop plan forever
        un-ratcheted (seen live: seed s2/555 applied the drop plan once,
        the injected `class add` failed, the rollback replayed last-good,
        and the budget was gone -- no committed apply ever followed, so the
        "run continued" witness had nothing to point at). Pops the most
        recent stamp; returns True when one was removed.
        """
        if self._change_ts:
            self._change_ts.pop()
            return True
        return False

    def observe(self, belief: float | None, applied: float | None,
                delivered: float | None, backlog_bytes: int | None,
                offered: float | None, now: float,
                min_rate: float | None = None) -> GovernorDecision:
        """One decision. Pure with respect to the tree; see the class doc.

        `belief`  -- the estimator's current number (None possible offline).
        `applied` -- the rate the tree currently carries.
        `delivered` / `backlog_bytes` -- the bottleneck probe; either being
        None disables the delay ratchet for this tick (no invention).
        `offered` -- pre-queue demand; feeds the probe-up gate only.
        `min_rate` -- the plan's total floor; never proposed below it.
        """
        cfg = self.cfg
        changed = False
        # ------------------------------------------------ ceiling
        ceiling = None
        if belief is not None and belief > 0.0:
            ceiling = cfg.cap_fraction * belief

        # ------------------------------------------------ delay probe
        delay_ms = None
        if delivered is not None and delivered > 0.0 and backlog_bytes is not None:
            delay_ms = backlog_bytes / (delivered * 125.0)
        if delay_ms is not None:
            if self._delay_ema is None:
                self._delay_ema = delay_ms
            else:
                a = min(1.0, max(cfg.delay_alpha, _EPS))
                self._delay_ema = a * delay_ms + (1.0 - a) * self._delay_ema

        inflating = (self._delay_ema is not None
                     and self._delay_ema > cfg.inflation_threshold_ms)
        clear = (self._delay_ema is not None
                 and self._delay_ema <= cfg.clear_threshold_ms)

        # ------------------------------------------------ clear tracking
        if clear:
            if self._clear_since is None:
                self._clear_since = now
        elif not inflating or self._delay_ema is None:
            # Unknown delay: never claim a recovery we cannot measure.
            self._clear_since = None
        held_clear = (self._clear_since is not None
                      and (now - self._clear_since) >= cfg.hold_clear_s)

        # ------------------------------------------------ budget
        # The ledger's currency is now RISES only: descent is bounded by the
        # law's dwell instead, so it can never starve behind the budget that
        # the S2/S4 evidence measured, and the flap risk stays covered where
        # it is real (upward probing).
        recent = [t for t, _rose in self._change_ts if now - t <= 60.0]
        ups_recent = [t for t, rose in self._change_ts
                      if now - t <= 60.0 and rose]
        budget_left = cfg.max_changes_per_min - len(ups_recent)

        # delay-emergency availability: one full-descent clearance per cooldown
        emerg_free = (self._delay_emergency_last is None
                      or (now - self._delay_emergency_last)
                      >= cfg.delay_emergency_cooldown_s)

        # ------------------------------------------------ decision
        # base = what we already have; the ceiling is a hard bound in every
        # branch, so "hold" can still fall when the belief dropped, but never
        # rises on a passive tick.
        rate, reason, emerg = self._decide(
            cfg, applied=applied, ceiling=ceiling,
            inflating=inflating, held_clear=held_clear,
            offered=offered, min_rate=min_rate, budget_left=budget_left,
            delay_ema=self._delay_ema, emerg_free=emerg_free)

        if emerg:
            self._delay_emergency_last = now

        if applied is not None and rate is not None and rate > applied:
            changed = True
            self._change_ts.append((now, True))
        elif applied is not None and rate is not None and rate < applied:
            # A descent is real change for the log; it never spends the
            # budget (see the ledger comment above).
            changed = True
        elif applied is None and rate is not None:
            # Room states the first proposal as the ceiling it was; it does
            # not spend the budget, which guards sustained behaviour.
            changed = True

        dec = GovernorDecision(
            rate=rate, reason=reason,
            belief_mbps=belief, ceiling_mbps=ceiling,
            delay_ms=delay_ms, delay_ema_ms=self._delay_ema,
            changed=changed, delivered_mbps=delivered,
            delay_emergency=bool(emerg), t=now)
        self.log.append(vars(dec).copy())
        return dec

    def _decide(self, cfg: GovernorConfig, *, applied, ceiling,
                inflating, held_clear, offered, min_rate, budget_left,
                delay_ema, emerg_free: bool):
        """The rule table, in one place so the reasons stay readable."""
        if ceiling is None and applied is None:
            return None, "no estimate and nothing applied yet", False

        if applied is None:
            # First tick the governor is consulted with a real applied rate
            # above never happened: start at the ceiling, not above it.
            if ceiling is None:
                return None, "no estimate and no ceiling yet", False
            return ceiling, f"first rate: ceiling ({cfg.cap_fraction} x belief)", False

        if inflating:
            if ceiling is None:
                # No belief yet (estimate not established): no ceiling to
                # obey, so nothing may ratchet either — hold.
                return applied, (f"delay inflated {delay_ema:.1f} ms but no "
                                 f"ceiling to obey without an estimate: hold"), False
            # Ratchet DOWN, but never below the ceiling and never above the
            # ceiling either: the ceiling can have moved under the applied
            # rate because the belief fell, so clamp both ways.
            rate = min(ceiling, applied * (1.0 - cfg.down_step_frac))
            if min_rate is not None:
                rate = max(rate, min_rate)
            if rate >= applied:
                return ceiling, (f"delay inflated {delay_ema:.1f} ms > "
                                 f"{cfg.inflation_threshold_ms:.0f} ms: held "
                                 f"at ceiling"), False
            # Delay emergency (declared in docs/evidence/task2-params.md #1-2):
            # a capacity drop backs the queue up rather than dropping it, so
            # the law's drop-rate emergency never fires; this is the delay-
            # driven twin of that path. One full-descent clearance per
            # cooldown; between clearances the dwell-bounded steps proceed.
            if (delay_ema is not None
                    and delay_ema >= cfg.delay_emergency_ms and emerg_free
                    and ceiling < applied
                    and (min_rate is None or min_rate <= ceiling)):
                return ceiling, (f"delay emergency {delay_ema:.1f} ms >= "
                                 f"{cfg.delay_emergency_ms:.0f} ms: descent "
                                 f"to ceiling in one commit"), True
            return rate, (f"delay inflated {delay_ema:.1f} ms > "
                          f"{cfg.inflation_threshold_ms:.0f} ms: "
                          f"ratchet down one step"), False

        if held_clear and offered is not None and offered > 0.0:
            if ceiling is None:
                return applied, "clear but no ceiling to probe toward", False
            if offered <= applied * cfg.probe_ratio:
                return applied, (f"clear for {cfg.hold_clear_s:.0f} s but "
                                 f"offered {offered:.1f} does not demand it"), False
            if applied >= ceiling * (1.0 - _EPS):
                return applied, "clear and demanded, already at ceiling", False
            if min_rate is not None and min_rate >= ceiling:
                return applied, "floor already at ceiling", False
            if budget_left <= 0:
                return applied, (f"rise budget exhausted "
                                 f"({cfg.max_changes_per_min}/min)"), False
            rate = min(ceiling, applied * (1.0 + cfg.up_step_frac))
            return rate, (f"clear for {cfg.hold_clear_s:.0f} s and demanded "
                          f"{offered:.1f} Mbps: probe up, bounded by ceiling"), False

        hold = min(applied, ceiling) if ceiling is not None else applied
        if hold < applied:
            # The belief fell underneath the applied rate; the ceiling binds.
            return ceiling, "belief fell below applied: ceiling binds", False
        if delay_ema is not None:
            return hold, (f"delay {delay_ema:.1f} ms between clear and "
                          f"inflation thresholds: hold"), False
        return hold, "no delay telemetry: ceiling only", False
