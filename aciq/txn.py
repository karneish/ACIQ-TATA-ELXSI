"""M4 enforcement + M9 transaction manager.

M4 is the only place in the project that touches the kernel. M9 wraps it so a
policy change is all-or-nothing: snapshot, apply, read back, and on any problem
roll back to something known good.

The runner is injected, so the entire transaction path — including rollback and
fault recovery — is testable without root and without touching a real interface.
"""

from __future__ import annotations

import json
import subprocess
import time
from dataclasses import dataclass, field

from .model import RatePlan
from .qdisc import read_class_state
from .shield import Mode, Shield, Violation
from .tc import TcTree, Mismatch, build_tree, parse_class_state, render, verify, unverified_fields


class Runner:
    """Real command execution. Needs root.

    A missing binary is reported as a failed command rather than an exception:
    a driver that dies because `ip` is absent produces no artefacts at all,
    which is the worst possible outcome when something has gone wrong.
    """

    def run(self, argv: tuple[str, ...]) -> tuple[int, str, str]:
        try:
            r = subprocess.run(list(argv), capture_output=True, text=True, timeout=10)
        except FileNotFoundError as e:
            return 127, "", f"{e.strerror}: {argv[0]}"
        except (OSError, subprocess.SubprocessError) as e:
            return 126, "", str(e)
        return r.returncode, r.stdout or "", r.stderr or ""


class FakeRunner:
    """Test double.

    `fail_once` models a transient fault so a rollback can still succeed.
    `auto_readback` synthesises `tc -j class show` output from the class-add
    commands it has already seen, so verification can genuinely pass — without
    it every transaction rolls back and nothing downstream can be exercised.
    """

    def __init__(self, fail_on: str | None = None, readback: str = "",
                 fail_once: bool = False, auto_readback: bool = False):
        self.fail_on = fail_on
        self.readback = readback
        #: fail only the first matching command, modelling a transient fault so
        #: a rollback can actually succeed
        self.fail_once = fail_once
        self._fired = False
        self.auto_readback = auto_readback
        self._applied: dict[str, dict[str, float]] = {}
        self._bytes: dict[str, int] = {}
        self._packets: dict[str, int] = {}
        self._drops: dict[str, int] = {}
        self._over: dict[str, int] = {}
        self.commands: list[tuple[str, ...]] = []

    @staticmethod
    def _mbps(token: str) -> float:
        return float(token.rstrip("mbit"))

    def run(self, argv: tuple[str, ...]) -> tuple[int, str, str]:
        self.commands.append(argv)
        if self.fail_on and self.fail_on in " ".join(argv):
            if not (self.fail_once and self._fired):
                self._fired = True
                return 1, "", f"injected failure on {self.fail_on}"
        # `tc class show` (text) is the primary reader; `-s -j` is the fallback.
        # auto_readback serves both so the primary path is the one under test.
        if "class" in argv and "show" in argv:
            if "-j" in argv:
                if self.auto_readback:
                    return 0, json.dumps(
                        [{"kind": "htb", "handle": k,
                          "rate": int(v["rate"] * 1e6), "ceil": int(v["ceil"] * 1e6)}
                         for k, v in self._applied.items()]), ""
                return 0, self.readback, ""
            if self.auto_readback:
                lines = [
                    f"class htb {k} root prio 0 rate {v['rate']:g}Mbit "
                    f"ceil {v['ceil']:g}Mbit burst 15Kb\n"
                    f"  Sent {self._bytes.get(k, 0)} bytes {self._packets.get(k, 0)} "
                    f"pkt (dropped {self._drops.get(k, 0)}, "
                    f"overlimits {self._over.get(k, 0)} requeues 0)"
                    for k, v in self._applied.items()
                ]
                return 0, "\n".join(lines), ""
            return 0, self.readback, ""
        if "class" in argv and "add" in argv:
            cid = argv[argv.index("classid") + 1]
            rate = self._mbps(argv[argv.index("rate") + 1])
            ceil = self._mbps(argv[argv.index("ceil") + 1])
            self._applied[cid] = {"rate": rate, "ceil": ceil}
        if "stats" in argv or "statistics" in argv:
            pass
        return 0, "", ""


@dataclass
class Outcome:
    ok: bool
    committed: bool
    rolled_back: bool
    violations: list[Violation] = field(default_factory=list)
    mismatches: list[Mismatch] = field(default_factory=list)
    reason: str = ""


class TransactionManager:
    """Snapshot -> apply -> verify -> (roll back) -> safe state."""

    def __init__(
        self,
        runner,
        shield: Shield | None = None,
        dev: str = "veth-lan",
        ns: str | None = "router",
        clock=time.monotonic,
    ):
        self.runner = runner
        self.shield = shield or Shield()
        self.dev = dev
        self.ns = ns
        self.clock = clock
        self.audit: list[dict] = []
        #: last known-good rendered command list, so a rebuild can be undone
        self._last_good: list[tuple[str, ...]] | None = None
        #: which rung of the safe-state ladder is currently applied
        self.safe_state_in_force: str | None = None
        #: human-readable explanation of the most recent refusal, so a driver
        #: can print *why* rather than only *that* it failed
        self.last_reason: str = ""

    # ---------------- kernel access (M4) ----------------
    def _read_classes(self) -> dict[str, dict[str, float]]:
        """Read-back via the verified paths, recording which one answered.

        `tc -s -j class show` was never validated on this machine and returned
        empty, which made every class look absent and every apply look like a
        read-back mismatch. Text output (gate check 10) is primary; JSON is a
        fallback, and the source name goes into the audit log.
        """
        state, source = self._read_class_state()
        self.last_readback_source = source
        return parse_class_state(state)

    def _read_class_state(self):
        """Text first, JSON second. Both use the injected runner."""
        for argv in (
            ("tc", "class", "show", "dev", self.dev),
            ("tc", "-s", "-j", "class", "show", "dev", self.dev),
        ):
            rc, out, _ = self.runner.run(self._prefix + argv)
            if rc != 0 or not out:
                continue
            if "-j" in argv:
                from .qdisc import parse_class_json
                state = parse_class_json(out)
                if state:
                    return state, "tc-json"
            else:
                from .qdisc import parse_class_text
                state = parse_class_text(out)
                if state:
                    return state, "tc-text"
        return {}, "none"

    @property
    def _prefix(self) -> tuple[str, ...]:
        return ("ip", "netns", "exec", self.ns) if self.ns else ()

    last_readback_source: str = "none"

    def _rebuild(self, tree: TcTree) -> tuple[bool, str]:
        """Delete the root and build the whole tree.

        Necessary, not stylistic: gate check 10a measured that
        `tc qdisc change ... htb default 50` fails with "Change operation not
        supported", so a changed default class means a full rebuild. Deleting the
        root qdisc is what makes that possible.
        """
        pre = ("ip", "netns", "exec", self.ns) if self.ns else ()
        self.runner.run(pre + ("tc", "qdisc", "del", "dev", self.dev, "root"))
        for argv in render(tree, dev=self.dev, ns=self.ns):
            rc, _, err = self.runner.run(argv)
            if rc != 0:
                return False, f"{' '.join(argv)} -> {err.strip()}"
        return True, ""

    # ---------------- transaction ----------------
    def apply(
        self,
        plan: RatePlan,
        drop_rate: float = 0.0,
        overlimit_rate: float = 0.0,
        leaf: tuple[str, ...] | str = "fq_codel",
        now: float | None = None,
    ) -> Outcome:
        """`now` must come from the caller's timeline, not this object's clock.

        The harness drives the estimator and the transaction from one clock. If
        the transaction consulted its own clock instead, the dwell window would
        be measured against a different timeline from the estimator's and a
        legitimate change would be vetoed as rate-limited.
        """
        now = self.clock() if now is None else now

        if self.shield.state.in_fault and not self.shield.may_retry(now):
            self.last_reason = (f"shield {self.shield.state.mode.value}: "
                                f"{self.shield.state.alarm or 'recovery not due'}")
            return Outcome(False, False, False, reason=self.last_reason)

        v = list(self.shield.veto_plan(plan))
        v += self.shield.veto_rate(now)
        v += self.shield.veto_load(drop_rate, overlimit_rate)
        if v:
            deferred = [x for x in v if x.severity == "defer"]
            faults = [x for x in v if x.severity != "defer"]
            self.last_reason = "; ".join(str(x) for x in v)
            if deferred and not faults:
                # "not yet", not "broken": no shield breach, kernel untouched
                self._log(now, "deferred", violations=[str(x) for x in v])
                return Outcome(False, False, False, violations=v,
                               reason="deferred by change window")
            if faults:
                self.shield.breach(now, faults)
                self.last_reason = "; ".join(str(x) for x in faults)
            self._log(now, "vetoed", violations=[str(x) for x in v])
            return Outcome(False, False, False, violations=v, reason="vetoed")

        tree = build_tree(plan, leaf=leaf)
        ok, err = self._rebuild(tree)
        self.last_reason = err
        if not ok:
            self.shield.breach(now, [Violation("apply_failed", err)])
            rb = self._rollback()
            self._log(now, "apply_failed", detail=err, rolled_back=rb)
            return Outcome(False, False, rb,
                           violations=[Violation("apply_failed", err)],
                           reason=err)

        state = self._read_classes()
        unverifiable = unverified_fields(tree, state)
        mism = verify(tree, state, unverifiable)
        if unverifiable:
            self._log(now, "readback_partial",
                      unverified=[f"{c}.{f}" for c, f in unverifiable[:6]],
                      source=self.last_readback_source)
        if mism:
            self.last_reason = ("read-back mismatch: "
                                + "; ".join(f"{m.classid}.{m.field} wanted "
                                            f"{m.expected:.3f} got {m.actual:.3f}"
                                            for m in mism[:4]))
            self.shield.breach(now, self.shield.veto_readback(mism))
            rb = self._rollback()
            self._log(now, "readback_mismatch", mismatches=[str(m) for m in mism],
                      rolled_back=rb, source=self.last_readback_source)
            return Outcome(False, False, rb, mismatches=mism,
                           reason="read-back mismatch")

        # committed
        self.last_reason = ""
        self._last_good = render(tree, dev=self.dev, ns=self.ns)
        self.shield.note_change(now)
        self.shield.observe_ok(now)
        self.shield.state.alarm = None
        # Record *what* was applied, not just how many classes. "classes=5" is
        # what made every hypothesis about a lease overshoot checkable-looking
        # and unfalsifiable: the rate on parent 1:1 is the whole question, and
        # it was absent from the artefact. Several runs were spent inferring it
        # from a separately-timestamped `tc` dump.
        self._log(now, "committed", classes=len(tree.classes),
                  applied={c.classid: [round(c.rate_mbps, 4),
                                       round(c.ceil_mbps, 4)]
                           for c in tree.classes})
        return Outcome(True, True, False)

    def _rollback(self) -> bool:
        """Restore the last known-good tree. Without one, fall back to the safe
        state, which is a plain unleased plan: interactive keeps the largest
        share and every class keeps its floor."""
        if self._last_good is not None:
            pre = ("ip", "netns", "exec", self.ns) if self.ns else ()
            self.runner.run(pre + ("tc", "qdisc", "del", "dev", self.dev, "root"))
            for argv in self._last_good:
                self.runner.run(argv)
            return True
        return self.force_safe()

    def force_safe(self) -> bool:
        """Apply the emergency safe state, escalating to simpler forms.

        The safe state deliberately has **no per-class breakdown**. It exists to
        keep the household protected when something is already wrong, so it must
        be the thing most likely to succeed — a tree containing class 1:30
        cannot be applied if 1:30 is precisely what the kernel is refusing.

        Escalation order, each one measured to work on this machine:
          1. `cake` at 95% of capacity — gate check 9 delivered 90.8 Mbps
          2. `fq_codel` — plain fair queueing, no rate limit
          3. `pfifo limit 1000` — the weakest thing that still shapes something

        Losing the class breakdown is an accepted cost: during a fault,
        protection beats classification.
        """
        pre = ("ip", "netns", "exec", self.ns) if self.ns else ()
        cap = self._last_capacity or 20.0
        ladder = (
            ("cake", ("cake", "bandwidth", f"{0.95 * cap:.4f}mbit")),
            ("fq_codel", ("fq_codel",)),
            ("pfifo", ("pfifo", "limit", "1000")),
        )
        for name, spec in ladder:
            self.runner.run(pre + ("tc", "qdisc", "del", "dev", self.dev, "root"))
            rc, _, err = self.runner.run(
                pre + ("tc", "qdisc", "add", "dev", self.dev, "root", "handle",
                       "1:", *spec))
            if rc == 0:
                self.safe_state_in_force = name
                return True
        self.safe_state_in_force = None
        return False

    _last_capacity: float | None = None

    def remember_capacity(self, mbps: float) -> None:
        self._last_capacity = mbps

    def _log(self, t: float, event: str, **kw) -> None:
        self.audit.append({"t": round(t, 3), "event": event, **kw})

    @property
    def mode(self) -> Mode:
        return self.shield.state.mode
