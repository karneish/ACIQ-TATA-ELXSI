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
* No rate floor of its own: the plan's floors (aciq.policy.floor_total_mbps)
  decide what the tree can legally carry. The governor receives the floor
  from the harness and never proposes below it.

ROUND-3 ADDITIONS (docs/evidence/round3-params.md, declared before any
run; per-tick diagnosis in docs/evidence/round3-diagnosis.md). Two failures
were measured on the S2b band's committed artefacts:

* up-steps NEVER climb. The probe gate `offered > probe_ratio x applied`
  is unsatisfiable when the bulk source is window-limited by the tree
  itself: offered rides exactly at the applied rate. And the ceiling can
  never rise, because a saturated observation cannot exist while the tree
  is the limiting pipe. Result: the tree pins at `0.9 x last saturate`
  forever (measured seed 800: applied 16.52 for the remaining 37 s of the
  run against a true 100 Mbps link).
  The DEMAND PROBE replaces the demand gate with the pipe-limited
  signature -- delay clear, offered >= DEMAND_FRAC x applied, sustained
  -- and then resolves the ambiguity (real demand vs a finished source)
  by a bounded probe-and-see: step up, watch the delay response, land at
  the last known-good rate on any inflation (probe-and-see overshoot is
  one ratchet-width of latency by construction).
* severe drops WALK instead of landing. When the ceiling is saturated and
  confident far below the applied rate, the descent was an emergency --
  but the emergency was VETOED whenever the plan floor exceeded the
  ceiling (`min_rate <= ceiling` gate): on seed 800 (100 -> 10) the
  ceiling 9.95 lost to the 14.0 floor, so the law's 25%/5 s envelope
  walked 7 commits over ~31 s and bind failed 8/10 seeds. The veto is
  replaced by an honest landing at `max(ceiling, min_rate)`: the floor is
  still respected, and one law-emergency commit replaces the walk.
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

#: Capacity-collapse emergency threshold. The dev band (seeds 400-409, gate
#: FAIL 2026-10-26) measured the gap the delay emergency alone leaves open:
#: after s2's post-drop tick the ceiling is 0.21x the applied root while the
#: delay EMA hovers at 37-72 ms -- below DELAY_EMERGENCY_MS -- so no declared
#: bypass may fire, the law's DOWN envelope (0.25x per commit, one per 5 s
#: dwell) needs ~25 s to walk a 91.8-root down to 19.4, and s2's post-drop
#: window (~10-14 s) runs out with the kernel at 51.5 Mbps = 2.57x the link.
#: A ceiling at or below COLLAPSE_FRAC x applied is therefore declared an
#: emergency in its own right: it shares the emergency cooldown and bypasses
#: dwell + step envelope for that one DOWN commit. HALF of the link is a
#: collapse no controller reasoning can justify without explicit emergency
#: powers; 0.5 keeps it far from ordinary estimation noise (per-seed
#: residual error ~7.9%).
CAPACITY_EMERGENCY_COLLAPSE_FRAC = 0.5

#: EMA weight for the delay series. 0.5 keeps direction readable; anything
#: closer to 1 follows the netem's burst artifacts tick by tick.
DELAY_ALPHA = 0.5

#: Round 3 (docs/evidence/round3-params.md). Sustained seconds of the
#: pipe-limited demand signature -- delay EMA clear AND
#: offered >= PROBE_DEMAND_FRAC x applied -- before a ceiling-piercing
#: probe may fire. A step in the dark needs a sustained window; this is
#: seeded from HOLD_CLEAR_S and tuned ONLY on the s7_* DEV band.
#:
#: Round 4: lowered from 7.0 to the law's minimum dwell (MIN_DWELL_S = 5).
#: The same number is the SURVIVAL window that promotes a pierce to
#: `_probe_verified` (and the guard that keeps the bind from wiping it). A
#: survival window LONGER than the minimum spacing between the pierces it
#: observes can never elapse: the ladder pace is one lawful change per
#: 5 s, so every new pierce re-stamped `_last_rise` before 7 s, promotion
#: never fired, `_probe_verified` stayed None, and the terminal bind fell
#: back to the stale ceiling (dev smoke seed1000 s2b_step_up_20to100:
#: pierces 7.4/12.7/18.1/23.4/28.7/34.0, zero promotions, publishable
#: 0.57). 5 s is the largest window that is still reachable at lawful
#: cadence; the demand window it also governs is one law slot, which is
#: exactly the sustained evidence a piercing step needs.
PROBE_HOLD_S = 5.0

#: Round 3. Multiplicative probe step above the (stale) ceiling.
#: 0.25 matches the law's up envelope exactly, so a probe commit need
#: never be step-clamped by the verifier; tuned ONLY on the DEV band.
PROBE_UP_FRAC = 0.25

#: Round 3. The pipe-limited signature: offered >= DEMAND_FRAC x applied.
#: The old gate demanded offered > 1.05 x applied, which can never hold
#: for a source window-limited by the tree (measured: offered 15.1-16.1
#: against applied 16.52 for the rest of an s2b_step_up run).
PROBE_DEMAND_FRAC = 0.85

#: Round 3. Grace for the demand window: the signature may flicker for
#: this many seconds (TCP senders catch up to an opened tree within a
#: couple of ticks) before the window resets and a fresh full hold is
#: required. Without the grace, one light tick restarts a 12 s hold.
PROBE_DEMAND_GAP_S = 3.0

#: Round 3. After a probe overshoot lands its backoff, new probes are
#: blocked this long: back-offs are prioritized, rises are cheap.
PROBE_BACKOFF_S = 18.0

#: Round 4. Below this offered/delivered rate the wire is IDLE: nothing is
#: riding the queue (a lone voice call offers ~1.5 Mbps; the bulk flow that
#: any round-3 shape saturates with is tens of Mbps). The bind branch
#: ("belief fell below applied") may only follow a decaying belief down
#: while the wire still carries the load -- on an idle wire the belief has
#: simply run out of samples, and shrinking the cap there is (a) protecting
#: nothing and (b) exactly the policy instability the brief asks to avoid.
#: Dev smoke seed1000 s2b_step_up_20to100: the bulk stopped at ~39 s, the
#: belief decayed, and the final commit fell to 48.5 (a 25% law-clamped
#: descent from 64.7) inside the measured final third, dragging the
#: publishable utilization from 0.65 to 0.57 for no benefit.
IDLE_WIRE_MBPS = 5.0

#: Round 3 (DEV-band retune, declared in round3-params.md). The pierce
#: witness. The ceiling-freshness gate could not tell a tree pin (a
#: saturated sample refreshes the ceiling AT the applied rate forever,
#: seed 1004 s2b_step_up: sat refreshes at rel 22.1-32.6 all at applied
#: 15.25, pierce never fired) from a real pin. The tree's own overlimit
#: counter does: overlimiting is the TREE dropping offered demand (dev
#: plateau: >= 940 overlimits/s on the pinned classes), and the rate
#: settles near zero when the LINK is the binder. A probe may fire only
#: while the tree is seen overlimiting at this rate for one decision
#: tick, alongside the demand window.
PROBE_OVERLIMIT_MIN = 50.0

#: Round 3. Overshoot signature: the wire still carries at least this
#: fraction of the applied rate while delay inflates. That is what the
#: tree sitting above the TRUE link looks like (delivered ~= link). A
#: genuine capacity collapse leaves delivered far below -- delivered
#: 10.9-13.2 Mbps against applied 45-72 on seed 800 -- so a real drop
#: still goes through the ordinary ratchet and its law bounds.
PROBE_RUNNING_FRAC = 0.6

#: Round 3. Severe-drop trigger: ceiling < SEVERE_DROP_FRAC x applied
#: with estimator confidence >= SEVERE_DROP_CONF. Initial seed 0.6 was
#: read off the seed-800 step_10 ledger (ceiling 9.95 against applied
#: 60.03 at conf 1.00); DEV band retune to 0.9: a 2x step (s2b_step_50,
#: ceiling 65.03 against applied 73.51 one tick after the drop) never
#: pierced 0.6, so the harness ran the law's 25%-walk and overshot the
#: legal band downward. 0.9 keeps the gate below the ordinary ratchet
#: spacing (a ceiling-binds branch walks INTO the emergency one tick
#: later anyway) while the confidence gate still rules out staleness.
#: Tuned ONLY on the DEV band. Below CAPACITY_EMERGENCY_COLLAPSE_FRAC
#: the old conf-less emergency still rules.
SEVERE_DROP_FRAC = 0.9
#: A severe-drop landing without estimator confidence needs the belief to be
#: FALLING (not merely stale) by at least this fraction over one tick, while
#: the bottleneck is saturated. The up shapes hold a constant low belief
#: (capacity is unobservable below the link), so a stale ceiling must never
#: be read as a drop.
BELIEF_FALL_FRAC = 0.02
#: DEV-band retune #2 (round3-params.md): 0.6 blocked 4/10 s2b_step_50 seeds
#: whose estimator confidence could not clear the gate; 0.45 admits them.
SEVERE_DROP_CONF = 0.45

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
    probe_hold_s: float = PROBE_HOLD_S
    probe_up_frac: float = PROBE_UP_FRAC
    probe_demand_frac: float = PROBE_DEMAND_FRAC
    probe_demand_gap_s: float = PROBE_DEMAND_GAP_S
    probe_backoff_s: float = PROBE_BACKOFF_S
    probe_overlimit_min: float = PROBE_OVERLIMIT_MIN
    probe_running_frac: float = PROBE_RUNNING_FRAC
    severe_drop_frac: float = SEVERE_DROP_FRAC
    severe_drop_conf: float = SEVERE_DROP_CONF

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
                       ("delay_alpha", self.delay_alpha),
                       ("probe_hold_s", self.probe_hold_s),
                       ("probe_demand_gap_s", self.probe_demand_gap_s),
                       ("probe_backoff_s", self.probe_backoff_s),
                       ("probe_overlimit_min", self.probe_overlimit_min)):
            if _v <= 0.0:
                raise ValueError(f"{_n} must be positive")
        if not (0.0 < self.probe_up_frac <= 1.0):
            # Unlike up_step_frac (bounded by down_step_frac so a wrong
            # ceiling-clip climb costs at most one ratchet width), the
            # ROUND-3 piercing step is tuned independent of the descent:
            # the verifier's up envelope (MAX_RATE_STEP_FRAC 0.25) is the
            # hard bound on what reaches the tree regardless.
            raise ValueError(
                f"probe_up_frac {self.probe_up_frac} must be in (0, 1]")
        if not (0.0 < self.probe_demand_frac <= 1.0):
            raise ValueError(
                f"probe_demand_frac {self.probe_demand_frac} outside (0, 1]")
        if not (0.0 < self.probe_running_frac < 1.0):
            raise ValueError(
                f"probe_running_frac {self.probe_running_frac} outside (0, 1)")
        if not (0.0 < self.severe_drop_conf <= 1.0):
            raise ValueError(
                f"severe_drop_conf {self.severe_drop_conf} outside (0, 1]")
        if self.severe_drop_frac <= CAPACITY_EMERGENCY_COLLAPSE_FRAC:
            raise ValueError(
                f"severe_drop_frac {self.severe_drop_frac} must exceed "
                f"CAPACITY_EMERGENCY_COLLAPSE_FRAC "
                f"{CAPACITY_EMERGENCY_COLLAPSE_FRAC}")


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
    probe_known_good: float | None = None  # highest rate that survived its window
    probe_block_remaining_s: float = 0.0   # >0 while new probes are blocked
    demand_window_s: float = 0.0           # seconds the demand signature has held
    overlimit_per_s: float | None = None   # tree overlimits this tick


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
        # The clearance stamp this cooldown replaced. A clearance whose
        # commit never happened is refunded to this (refund_delay_emergency):
        # the round-3 dev band measured the shield's 5 s change window
        # deferring a severe-drop landing (4.25s since last change), which
        # otherwise burnt the 30 s cooldown on a descent that never reached
        # the tree -- the next emergency could then only fire 30 s after
        # the drop, twice past the 8 s gate.
        self._delay_emergency_prev: float | None = None
        # Round 3 demand-probe state. The demand window is the pipe-limited
        # signature (delay clear, offered >= DEMAND_FRAC x applied); the gap
        # tracker lets one light tick through without restarting the hold.
        self._demand_since: float | None = None
        self._demand_gap_since: float | None = None
        # Probe overshoot state: the highest rate known to have survived a
        # full window without inflation, the cap probes may not exceed after
        # a backoff, and the block deadline itself.
        self._known_good: float | None = None
        self._rise_cap: float | None = None
        self._last_rise: tuple[float, float] | None = None
        self._probe_block_until: float | None = None
        # The highest probe rate that survived a full window (promoted).
        # A verified pierce is the engineered exception to applied <=
        # cap_fraction x belief: the belief can only lag a probe, so
        # binding to the pre-probe ceiling after promotion would undo a
        # result the window itself certified. Descents never consult it.
        self._probe_verified: float | None = None
        #: Previous tick's belief; a fall over one tick is the drop signal
        #: that admits a confidence-less severe landing (round 5).
        self._prev_belief: float | None = None
        # Full decision log for the run artefact. One small dict per tick.
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

    # ------------------------------------------------------------------
    def refund_delay_emergency(self) -> bool:
        """Restock a delay-emergency clearance whose commit did not happen.

        The cooldown stamp is taken the tick the clearance FIRES, but the
        round-3 dev band measured the landing itself deferred downstream
        (the shield's 5 s change window, `rate_limited: 4.25s since last
        change`): the decision log then showed the emergency spent, the
        tree unchanged, and the next clearance barred for the full
        cooldown past the drop. If the apply did not commit, the clearance
        buys back its previous value; only a landed emergency may cost
        cooldown. Returns True when a stamp was restored.
        """
        if self._delay_emergency_last is None:
            return False
        self._delay_emergency_last = self._delay_emergency_prev
        self._delay_emergency_prev = None
        return True

    def observe(self, belief: float | None, applied: float | None,
                delivered: float | None, backlog_bytes: int | None,
                offered: float | None, now: float,
                min_rate: float | None = None,
                belief_conf: float | None = None,
                belief_saturated: bool | None = None,
                tree_overlimit_per_s: float | None = None) -> GovernorDecision:
        """One decision. Pure with respect to the tree; see the class doc.

        `belief`  -- the estimator's current number (None possible offline).
        `applied` -- the rate the tree currently carries.
        `delivered` / `backlog_bytes` -- the bottleneck probe; either being
        None disables the delay ratchet for this tick (no invention).
        `offered` -- pre-queue demand; feeds the probe-up gate only.
        `min_rate` -- the plan's total floor; never proposed below it.
        `belief_conf` / `belief_saturated` -- the estimator's confidence and
        saturation flag this tick; the severe-drop trigger gates on
        confidence, and the demand probe pierces only while the tree's own
        overlimit counter (see `tree_overlimit_per_s`) says the TREE, not
        the link, is the limiting pipe.
        `tree_overlimit_per_s` -- sum of per-class overlimits/s this tick;
        None disables the overlimit witness (the probe then cannot fire).
        """
        cfg = self.cfg
        changed = False
        # ------------------------------------------------ ceiling
        ceiling = None
        if belief is not None and belief > 0.0:
            ceiling = cfg.cap_fraction * belief
        # A saturated observation refreshes the ceiling below only via the
        # belief value itself; the demand probe now gates on the overlimit
        # witness instead of ceiling staleness (round3-params.md retune).

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

        # The tree's launch state is the first thing that has survived
        # anything: it seeds known-good, so a launch-time probe overshoot
        # has a real rate to land back at instead of a bare ratchet step.
        if applied is not None and self._known_good is None:
            self._known_good = applied

        # ------------------------------------------------ demand window
        # Round 3: the pipe-limited signature. offered riding at or above
        # DEMAND_FRAC x applied while the delay is CLEAR is what a source
        # window-limited by our own tree looks like; a finished source
        # decays below it. The gap grace keeps a single light tick from
        # restarting the hold.
        demand_ok = (clear and applied is not None and applied > 0.0
                     and offered is not None and offered > 0.0
                     and offered >= cfg.probe_demand_frac * applied)
        if demand_ok:
            if self._demand_since is None:
                self._demand_since = now
            self._demand_gap_since = None
        elif self._demand_since is not None:
            if self._demand_gap_since is None:
                self._demand_gap_since = now
            if inflating or not clear or (
                    (now - self._demand_gap_since)
                    > cfg.probe_demand_gap_s):
                self._demand_since = None
                self._demand_gap_since = None
        held_demand = (self._demand_since is not None
                       and (now - self._demand_since) >= cfg.probe_hold_s)

        # ------------------------------------------------ probe survivors
        # A probe rise that has lived clear for a full window promotes itself
        # to known-good and lifts the overshoot cap: the climb may continue.
        if (self._last_rise is not None and clear
                and applied is not None
                and (now - self._last_rise[0]) >= cfg.probe_hold_s
                and applied >= self._last_rise[1] - 0.5):
            self._known_good = max(self._known_good or 0.0,
                                   self._last_rise[1])
            self._probe_verified = max(self._probe_verified or 0.0,
                                       self._last_rise[1])
            self._rise_cap = None
            self._last_rise = None

        # ------------------------------------------------ budget
        # The ledger's currency is now RISES only: descent is bounded by the
        # law's dwell instead, so it can never starve behind the budget that
        # the S2/S4 evidence measured, and the flap risk stays covered where
        # it is real (upward probing).
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
        # A severe drop is a FALLING belief observed while the bottleneck
        # is saturated, not merely a stale-low one. The up shapes park the
        # belief at a constant low value because a sub-link tree never
        # saturates the external link (estimator doc: capacity is only
        # observable while saturated), so "ceiling < applied" alone is
        # normal there and must never trigger an emergency descent.
        belief_falling = (self._prev_belief is not None
                          and belief is not None
                          and belief < self._prev_belief
                          * (1.0 - BELIEF_FALL_FRAC))
        if belief is not None:
            self._prev_belief = belief
        rate, reason, emerg = self._decide(
            cfg, applied=applied, ceiling=ceiling,
            inflating=inflating, held_clear=held_clear,
            held_demand=held_demand, demand_ok=demand_ok,
            delivered=delivered,
            offered=offered, min_rate=min_rate, budget_left=budget_left,
            delay_ema=self._delay_ema, emerg_free=emerg_free, now=now,
            belief_conf=belief_conf,
            belief_saturated=belief_saturated, belief_falling=belief_falling,
            tree_overlimit_per_s=tree_overlimit_per_s)

        if emerg:
            self._delay_emergency_prev = self._delay_emergency_last
            self._delay_emergency_last = now

        if applied is not None and rate is not None and rate > applied:
            changed = True
            self._change_ts.append((now, True))
            if reason.startswith("demand-probe up"):
                # A piercing probe went out. Hold onto its stamp: the rise
                # survives a full clear window and it becomes known-good.
                # Round 4: only a NEW (higher) target re-stamps. While the
                # kernel apply lags a pierce the governor re-proposes the
                # SAME target for several ticks; each of those used to
                # restart the survival window, so it could never conclude
                # (dev smoke seed1000: four re-proposals 1 s apart after
                # every rung). Re-proposing the pending rate is not a new
                # rise and must not reset the clock that verifies it.
                if (self._last_rise is None
                        or rate > self._last_rise[1] * (1.0 + _EPS)):
                    self._last_rise = (now, rate)
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
            delay_emergency=bool(emerg), t=now,
            probe_known_good=self._known_good,
            probe_block_remaining_s=(max(0.0, self._probe_block_until - now)
                                     if self._probe_block_until is not None
                                     else 0.0),
            demand_window_s=((now - self._demand_since)
                             if self._demand_since is not None else 0.0),
            overlimit_per_s=tree_overlimit_per_s)
        self.log.append(vars(dec).copy())
        return dec

    def _decide(self, cfg: GovernorConfig, *, applied, ceiling,
                inflating, held_clear, held_demand, demand_ok, delivered,
                offered, min_rate, budget_left, delay_ema,
                emerg_free: bool, now: float = 0.0,
                belief_conf: float | None = None,
                belief_saturated: bool | None = None,
                belief_falling: bool = False,
                tree_overlimit_per_s: float | None = None):
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
            # Round 3 probe overshoot: the tree climbed above the TRUE link
            # through a piercing probe. The signature is a pierce in play
            # (a rise stamp or a live cap) with the wire still carrying
            # most of the applied rate (delivered ~= link, far from the
            # collapse regime). A genuine capacity drop has delivered far
            # below this fraction and falls through to the ordinary
            # ratchet and its law bounds.
            overshoot = ((self._rise_cap is not None
                          or self._last_rise is not None)
                         and delivered is not None
                         and delivered >= cfg.probe_running_frac * applied)
            if overshoot:
                land = (self._known_good
                        if self._known_good is not None
                        else applied * (1.0 - cfg.down_step_frac))
                if delivered is not None:
                    # never land above what the wire is actually carrying
                    land = min(land, delivered)
                if min_rate is not None:
                    land = max(land, min_rate)
                if land < applied:
                    self._last_rise = None
                    self._rise_cap = self._known_good
                    self._probe_block_until = now + cfg.probe_backoff_s
                    why = (f"probe overshoot: delay inflated {delay_ema:.1f} "
                           f"ms, wire carries {delivered:.1f} of applied "
                           f"{applied:.1f}: land at known-good "
                           f"{land:.1f} Mbps")
                    return land, why, False

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
            # Declared DOWN emergencies (docs/evidence/task2-params.md, and
            # round 3 in docs/evidence/round3-params.md):
            # 1) delay-driven twin of the law's dead drop-rate emergency --
            #    a capacity drop backs the queue up instead of dropping;
            # 2) capacity collapse -- ceiling <= COLLAPSE_FRAC x applied
            #    (dev-band measured: ceiling 0.21x applied with delay EMA
            #    37-72 ms, and the law's walk-down ran out of window);
            # 3) severe drop -- ceiling < SEVERE_DROP_FRAC x applied while
            #    the estimator is confident (>= SEVERE_DROP_CONF). This one
            #    exists because the seed-800 ledger measured the collapse
            #    veto dying on the plan floor: the old `min_rate <=
            #    ceiling` gate refused every landing whose ceiling was
            #    below the 14.0 floor, so the law's 25%/5 s envelope walked
            #    7 commits and bind failed 8/10 seeds. All three share the
            #    emergency cooldown and bypass dwell + step envelope for
            #    that single DOWN commit, landing at max(ceiling, floor):
            #    the floor stays respected, the walk does not happen.
            delay_shock = (delay_ema is not None
                           and delay_ema >= cfg.delay_emergency_ms)
            collapse = (ceiling is not None
                        and ceiling < applied
                        * CAPACITY_EMERGENCY_COLLAPSE_FRAC)
            # Round 5: a confidence-less severe drop is admitted when the
            # bottleneck is saturated THIS tick and the belief is falling.
            # The 1:1 smoke measured a 50 Mbps drop whose first post-drop
            # belief (83 -> 64.6) had conf < 0.45 (the confidence had
            # decayed on a 100 Mbps link the tree never saturated), so the
            # gate refused and the law walked 105.7 -> 79.3 -> 59.5 -> 52.2
            # = 11.7 s. A collapse bypasses the clearance cooldown too: when
            # the belief later snaps to the true 8 Mbps (ceiling 7.5 vs
            # applied 58.5) the first clearance is already spent, and the
            # 25 % walk then cannot reach the floor band inside 8 s.
            severe = (ceiling is not None
                      and ceiling < applied * cfg.severe_drop_frac
                      and ((belief_conf is not None
                            and belief_conf >= cfg.severe_drop_conf)
                           or (bool(belief_saturated) and belief_falling)))
            if ((delay_shock or collapse or severe)
                    and (emerg_free or collapse) and ceiling < applied):
                land = (max(ceiling, min_rate)
                        if min_rate is not None else ceiling)
                if not emerg_free:
                    why = (f"capacity collapse: ceiling {ceiling:.2f} < "
                           f"{CAPACITY_EMERGENCY_COLLAPSE_FRAC:.2f}x "
                           f"applied {applied:.2f}: land at max(ceiling, "
                           f"floor) in one commit (cooldown bypassed)")
                elif delay_shock:
                    why = (f"delay emergency {delay_ema:.1f} ms >= "
                           f"{cfg.delay_emergency_ms:.0f} ms: descent "
                           f"as max(ceiling, floor) in one commit")
                elif severe:
                    why = (f"severe drop: ceiling {ceiling:.2f} < "
                           f"{cfg.severe_drop_frac:.2f}x applied "
                           f"{applied:.2f} at confidence {belief_conf:.2f}: "
                           f"land at max(ceiling {ceiling:.2f}, floor "
                           f"{min_rate:.1f}) in one commit")
                else:
                    why = (f"capacity emergency: ceiling {ceiling:.2f} < "
                           f"{CAPACITY_EMERGENCY_COLLAPSE_FRAC:.2f}x "
                           f"applied {applied:.2f}: land at "
                           f"max(ceiling, floor) in one commit")
                return land, why, True
            return rate, (f"delay inflated {delay_ema:.1f} ms > "
                          f"{cfg.inflation_threshold_ms:.0f} ms: "
                          f"ratchet down one step"), False

        # Round 3 (DEV-band retune, round3-params.md): the DEMAND PROBE.
        # Pipe-limited demand evidence held for a full window (delay clear,
        # offered >= DEMAND_FRAC x applied), no probe block, budget left,
        # and the tree DROPPING demand on site: the first post-ceiling
        # freshness gate used `_last_saturated_t`, but a saturated sample
        # refreshes the ceiling at exactly the pinned applied rate forever
        # (dev seed 1004 s2b_step_up: saturated ticks at rel 22.1-32.6 all
        # at applied 15.25 against a 100 Mbps link), so the probe never
        # started. The overlimit witness separates the two cases the
        # freshness gate could not: overlimiting means the TREE drops
        # offered demand (the tree is the binder -- pierce); a quiet
        # overlimit counter alongside held demand means the LINK carries
        # what the bulk actually asks for (do not climb).
        block_expired = (self._probe_block_until is None
                         or now >= self._probe_block_until)
        ol = tree_overlimit_per_s
        witness = (ol is not None
                   and ol >= cfg.probe_overlimit_min)
        # The window must be held AND this tick must still carry the
        # signature: the probe's own reason quotes THIS tick's offered
        # figure, so the action cannot rest on evidence that just lapsed.
        pierce_ok = (held_demand and demand_ok and block_expired
                     and budget_left > 0 and witness)
        if pierce_ok:
            if self._probe_block_until is not None:
                # the block expired: a new full demand window has held, so
                # the overshoot cap yields (docs/evidence/round3-params.md)
                self._rise_cap = None
                self._probe_block_until = None
            target = applied * (1.0 + cfg.probe_up_frac)
            if self._rise_cap is not None:
                target = min(target, self._rise_cap)
            if min_rate is not None:
                target = max(target, min_rate)
            if target <= applied * (1.0 + _EPS):
                return applied, (f"demand window held but the probe cap "
                                 f"{self._rise_cap:.1f} leaves no step"), False
            note = (f", capped at known-good {self._rise_cap:.1f}"
                    if self._rise_cap is not None else "")
            return (target,
                    f"demand-probe up: pipe-limited demand evidence "
                    f"(offered {offered:.1f} >= "
                    f"{cfg.probe_demand_frac:.2f}x applied {applied:.1f} "
                    f"for {cfg.probe_hold_s:.0f} s; step "
                    f"{cfg.probe_up_frac:.2f}){note}", False)
        if (held_demand and demand_ok and block_expired and budget_left > 0
                and offered is not None
                and applied is not None and applied > 0.0
                and offered <= applied * cfg.probe_ratio
                and not witness):
            # The signature held but the tree is not overlimiting: either
            # the bulk genuinely rides the link through the tree, or the
            # counters are missing. Both refuse a step in the dark. A
            # DIRECT demand excess (offered > PROBE_RATIO x applied) skips
            # this hold so the ceiling-bounded climb below may still fire.
            return applied, (f"demand window held but the tree does not "
                             f"drop demand (overlimit {ol or 0.0:.0f}/s "
                             f"below witness floor "
                             f"{cfg.probe_overlimit_min:.0f})"), False

        if held_clear and offered is not None and offered > 0.0:
            if offered <= applied * cfg.probe_ratio:
                return applied, (f"clear for {cfg.hold_clear_s:.0f} s but "
                                 f"offered {offered:.1f} does not demand it"), False
            # The climb target is the ceiling OR a probe-verified rate,
            # whichever is higher: after a verified pierce the estimator's
            # belief lags the tree, and binding this branch to the stale
            # ceiling would strand the ladder below its own known-good.
            climb_to = max(ceiling or 0.0, self._probe_verified or 0.0)
            if climb_to <= 0.0:
                return applied, "clear but no ceiling to probe toward", False
            if applied >= climb_to * (1.0 - _EPS):
                return applied, ("clear and demanded, already at climb "
                                 "bound"), False
            if min_rate is not None and min_rate >= climb_to:
                return applied, "floor already at ceiling", False
            if budget_left <= 0:
                return applied, (f"rise budget exhausted "
                                 f"({cfg.max_changes_per_min}/min)"), False
            rate = min(climb_to, applied * (1.0 + cfg.up_step_frac))
            return rate, (f"clear for {cfg.hold_clear_s:.0f} s and demanded "
                          f"{offered:.1f} Mbps: probe up, bounded by "
                          f"ceiling"), False

        # Round 3 (dev band, task: probe climbs wiped by the stale
        # ceiling): a probing commit outruns the estimator by design --
        # the ceiling is 0.9x a belief that can only lag the pierce -- so
        # the bind tick right after a pierce would hold the OLD ceiling
        # and wipes the experiment 3-4 s in, before the probe's own
        # hold window (probe_hold_s) can promote it to known-good.
        # Dev-side trace, seed1000 s2b_step_up_20to100: pierce commit
        # 43.9 at t+5.1s, "ceiling binds" 41.0 at t+8.9s, and the ladder
        # never re-promoted. Two guards, both only on NON-inflating
        # ticks (every descent branch keeps its true-ceiling priority
        # above this block):
        # 1) still inside the pierce's hold window AND the delay is
        #    clear: hold the probe rate (the overshoot landing further
        #    up still consumes the pierce if delay inflates).
        # 2) a probe that SURVIVED its full window promoted itself to
        #    known-good; that verified rate is the lowest stop the
        #    bind may reach while the delay stays clear. Severe/capacity
        #    emergencies and the overshoot landing keep max(ceiling,
        #    floor) semantics and so can drop below it.
        eff_hold = max((ceiling if ceiling is not None else 0.0),
                       self._probe_verified or 0.0)
        if held_clear and self._last_rise is not None \
                and applied is not None \
                and (now - self._last_rise[0]) < cfg.probe_hold_s \
                and applied >= self._last_rise[1] * (1.0 - _EPS):
            return applied, (f"pierce probe verifying: hold at probe "
                             f"rate until the window concludes "
                             f"({cfg.probe_hold_s - (now - self._last_rise[0]):.1f}s left)"), False
        # Round 4: a pierce whose kernel apply has not landed yet (the tree
        # still reads the PRE-pierce rate) is NOT a failed probe. On an idle
        # wire the belief decays once the load stops, and the bind branch
        # would cancel the pending pierce by proposing the stale ceiling --
        # the reported final third then ends in a needless descent. Keep the
        # pending probe alive while the wire is idle; a busy wire keeps its
        # full descent priority below (that is the real capacity-drop path).
        pending_rise = (self._last_rise is not None
                        and (now - self._last_rise[0]) < cfg.probe_hold_s)
        # Idle means MEASURED idle: with no telemetry at all the old descent
        # stays in force (never claim a shrink we cannot see).
        has_wire = offered is not None or delivered is not None
        wire_idle = (has_wire
                     and (offered is None or offered <= IDLE_WIRE_MBPS)
                     and (delivered is None or delivered <= IDLE_WIRE_MBPS))
        if pending_rise and wire_idle and applied is not None:
            keep = max(applied, self._last_rise[1])
            if keep > applied:
                return keep, ("pierce probe pending on an idle wire: keep "
                              "the probe rate instead of following the "
                              "decayed belief"), False
        if wire_idle and applied is not None:
            return applied, ("belief fell below applied on an idle wire: "
                             "hold (no demand to protect, no evidence to "
                             "shrink)"), False
        hold = min(applied, eff_hold) if (self._probe_verified is not None
                                          or ceiling is not None) else applied
        if hold < applied:
            # The belief fell underneath the applied rate; the ceiling binds.
            land = (eff_hold if self._probe_verified is not None
                    and self._probe_verified > (ceiling or 0.0)
                    else ceiling)
            # Round 5: the same falling+saturated severe drop the inflating
            # branch honours must be law-cleared HERE, where a quiet delay
            # (the 1:1 smoke sat at 15.9 ms, below the 20 ms ratchet) sends
            # the bind. Without the clearance the verifier clamps the ceiling
            # target to one 25 % step, which is exactly the 11.7 s walk.
            svd = (ceiling is not None
                   and ceiling < applied * cfg.severe_drop_frac
                   and ((belief_conf is not None
                         and belief_conf >= cfg.severe_drop_conf)
                        or (bool(belief_saturated) and belief_falling)))
            collapse_now = (ceiling is not None
                            and ceiling < applied
                            * CAPACITY_EMERGENCY_COLLAPSE_FRAC)
            if svd and (emerg_free or collapse_now):
                target = max(land, min_rate) if min_rate is not None else land
                how = ("severe drop" if not collapse_now
                       else "capacity collapse")
                return target, (
                    f"belief fell below applied: {how} landing "
                    f"max(ceiling {land:.2f}, floor "
                    f"{min_rate if min_rate is not None else 0.0:.1f}) in "
                    f"one commit"), True
            return land, "belief fell below applied: ceiling binds", False
        if delay_ema is not None:
            return hold, (f"delay {delay_ema:.1f} ms between clear and "
                          f"inflation thresholds: hold"), False
        return hold, "no delay telemetry: ceiling only", False
