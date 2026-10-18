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
from .qdisc import parse_qdisc_text
from .shield import Mode, Shield, Violation
from .tc import (TcTree, Mismatch, build_tree, canon_classid, compare_states,
                 parse_class_state, render, verify, unverified_fields)


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
        #: root qdisc model, handle -> kind. Added because the safe state is
        #: class-free and is therefore verified by reading the root qdisc back;
        #: without this a correct safe state is indistinguishable from no qdisc.
        self._qdiscs: dict[str, str] = {}

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
        if "qdisc" in argv and "del" in argv:
            self._qdiscs.clear()
        if "qdisc" in argv and ("add" in argv or "replace" in argv):
            verb = "add" if "add" in argv else "replace"
            rest = argv[argv.index(verb) + 1:]
            # drop dev/<name>, root and handle, then whatever kind comes first
            kind = "unknown"
            rate = None
            for i, tok in enumerate(rest):
                if tok in ("dev", "root", "handle"):
                    continue
                if tok.startswith("veth") or tok.startswith("eth"):
                    continue
                kind = tok
                if "rate" in rest and rest[i + 1:i + 2]:
                    rate = rest[rest.index("rate") + 1]
                break
            handle = (argv[argv.index("handle") + 1]
                      if "handle" in argv else "root")
            self._qdiscs[handle] = (kind, rate)
            if verb == "replace":
                self._qdiscs = {handle: (kind, rate)}
        if "qdisc" in argv and "show" in argv:
            if not self._qdiscs:
                return 0, "", ""
            # tc prints the netem rate limit, which is what the read-back
            # verification looks for. Without it a correctly applied limit
            # reads as unconfirmed.
            return 0, "\n".join(
                (f"qdisc {k} {h}: root refcnt 2 rate {r}" if r
                 else f"qdisc {k} {h}: root refcnt 2")
                for h, (k, r) in self._qdiscs.items()), ""
        if "class" in argv and "add" in argv:
            cid = argv[argv.index("classid") + 1]
            rate = self._mbps(argv[argv.index("rate") + 1])
            ceil = self._mbps(argv[argv.index("ceil") + 1])
            self._applied[cid] = {"rate": rate, "ceil": ceil}
        if "stats" in argv or "statistics" in argv:
            pass
        return 0, "", ""


def _comparable_pairs(target: dict, actual: dict) -> int:
    """How many (class, field) pairs BOTH sides actually report.

    Presence of a class is not comparability: `tc` can print a class without
    its rates, and a baseline captured under one kernel's output format can
    therefore be structurally incapable of failing a comparison.
    """
    # Canonicalise both sides. Without this, a baseline keyed `1:10` and a
    # read-back keyed `1:0010` -- the same class, printed the other way --
    # compare as zero shared fields and a genuinely verified restore would be
    # reported unverifiable. The padding test caught exactly that.
    tgt = {canon_classid(k): v for k, v in target.items()}
    act = {canon_classid(k): v for k, v in actual.items()}
    n = 0
    for cid, want in tgt.items():
        got = act.get(cid) or {}
        for key in ("rate", "ceil"):
            if want.get(key) is not None and got.get(key) is not None:
                n += 1
    return n


#: Rollback outcome vocabulary. Each is a distinct condition with a different
#: meaning for whoever is holding a broken link, so collapsing them into a bool
#: is what made the original defect possible: every path returned True.
VERIFIED = "verified"                        # cmds ok AND read-back matched
COMMANDS_FAILED = "commands_failed"          # a restore command was refused
VERIFICATION_FAILED = "verification_failed"  # cmds ok, state still wrong
UNVERIFIABLE = "unverifiable"                # state could not be inspected
NO_TARGET = "no_target"                      # nothing known-good to restore to
PARTIAL = "partial"                          # some cmds failed, state matched


@dataclass
class RollbackResult:
    """Evidence about what a rollback actually did.

    ``ok`` is True **only** for `verified`. Running the commands is not the
    same as restoring the kernel, and this type exists so that difference
    cannot be quietly lost in a bool.
    """

    ok: bool
    outcome: str
    reason: str = ""
    mismatches: list[Mismatch] = field(default_factory=list)
    unverified: list[tuple[str, str]] = field(default_factory=list)
    failed_commands: list[str] = field(default_factory=list)
    source: str = "none"
    target: str = ""

    def __bool__(self) -> bool:
        return self.ok


@dataclass
class Outcome:
    ok: bool
    committed: bool
    rolled_back: bool
    violations: list[Violation] = field(default_factory=list)
    mismatches: list[Mismatch] = field(default_factory=list)
    reason: str = ""
    rollback: RollbackResult | None = None


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
        #: canonical read-back state observed when that tree committed. This is
        #: the rollback *target*, and it is an observation rather than a
        #: re-rendering of intent.
        self._last_good_state: dict[str, dict[str, float]] | None = None
        #: full evidence for the most recent rollback attempt
        self.last_rollback: RollbackResult | None = None
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
            self._log(now, "apply_failed", detail=err, rolled_back=rb.ok,
                      rollback=rb.outcome, rb_reason=rb.reason)
            return Outcome(False, False, rb.ok,
                           violations=[Violation("apply_failed", err)],
                           reason=err, rollback=rb)

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
                      rolled_back=rb.ok, rollback=rb.outcome, rb_reason=rb.reason,
                      source=self.last_readback_source)
            return Outcome(False, False, rb.ok, mismatches=mism,
                           reason="read-back mismatch", rollback=rb)

        # committed
        self.last_reason = ""
        self._last_good = render(tree, dev=self.dev, ns=self.ns)
        # Keep the *observed* state next to the commands. Replaying commands is
        # not the same as knowing what they produced, and a rollback target that
        # cannot be described cannot be checked afterwards -- which is precisely
        # the gap being closed here.
        self._last_good_state = {k: dict(v) for k, v in state.items()}
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

    def _replay(self, argv_list) -> list[str]:
        """Run restore commands, collecting the ones the kernel refused.

        Previously every return value here was discarded, so a rollback that
        restored nothing reported exactly like one that restored everything.
        """
        pre = ("ip", "netns", "exec", self.ns) if self.ns else ()
        rc, _, err = self.runner.run(
            pre + ("tc", "qdisc", "del", "dev", self.dev, "root"))
        failed = [] if rc == 0 else [f"qdisc del: {err.strip() or rc}"]
        for argv in argv_list:
            rc, _, err = self.runner.run(argv)
            if rc != 0:
                failed.append(f"{' '.join(argv)} -> {err.strip() or rc}")
        return failed

    def _read_root_qdisc(self) -> tuple[dict[str, str], str]:
        pre = ("ip", "netns", "exec", self.ns) if self.ns else ()
        for argv in (("tc", "qdisc", "show", "dev", self.dev),
                     ("tc", "-j", "qdisc", "show", "dev", self.dev)):
            rc, out, _ = self.runner.run(pre + argv)
            if rc == 0 and out:
                if "-j" in argv:
                    try:
                        data = json.loads(out)
                    except (ValueError, TypeError):
                        continue
                    state = {}
                    for q in data if isinstance(data, list) else []:
                        if q.get("root") or q.get("parent") in (None, "root"):
                            state[str(q.get("handle") or "root")] =                                 str(q.get("kind", ""))
                    if state:
                        return state, "tc-json"
                else:
                    state = parse_qdisc_text(out)
                    if state:
                        return state, "tc-text"
        return {}, "none"

    def _rollback(self) -> RollbackResult:
        """Restore the last known-good tree and **verify it was restored**.

        Replaying commands proves only that commands ran. The kernel may refuse
        part of the tree, normalise a rate, or leave a filter behind, and the
        old implementation returned True in every one of those cases. The state
        is therefore read back and compared against the canonical snapshot
        captured when the good tree was committed.

        Without a known-good tree, fall back to the safe state, which is a plain
        unleased plan: interactive keeps the largest share and every class keeps
        its floor.
        """
        if self._last_good is None:
            res = self.force_safe(result=True)
            self.last_rollback = res
            return res

        target = self._last_good_state or {}
        failed = self._replay(self._last_good)

        if not target:
            # Commands ran but there is no description of what "restored" means,
            # so the result is unknown -- which is not the same as success.
            res = RollbackResult(
                False, UNVERIFIABLE,
                reason="no canonical state recorded for the known-good tree; "
                       "restored commands ran but the target state is unknown",
                failed_commands=failed, source="none", target="unknown")
            self.last_rollback = res
            self._log(self.clock(), "rollback_unverifiable",
                      reason=res.reason, failed=failed[:6])
            return res

        raw, source = self._read_class_state()
        # _read_class_state returns the reader's own mapping; normalise it the
        # same way apply() does, or the comparison is against dataclasses
        # instead of the {classid: {rate, ceil}} shape it expects.
        actual = parse_class_state(raw)
        if not actual:
            # Commands that were refused outrank an unreadable state: we already
            # know the restore did not happen, so "unverifiable" would understate
            # it and hide the cause behind a missing reader.
            if failed:
                res = RollbackResult(
                    False, COMMANDS_FAILED,
                    reason=f"{len(failed)} restore command(s) refused and the "
                           f"post-rollback state could not be read back "
                           f"(source={source})",
                    failed_commands=failed, source=source, target="known-good")
            else:
                res = RollbackResult(
                    False, UNVERIFIABLE,
                    reason=f"post-rollback read-back returned no class state "
                           f"(source={source}); restoration could not be "
                           f"confirmed",
                    failed_commands=failed, source=source, target="known-good")
            self.last_rollback = res
            self._log(self.clock(), f"rollback_{res.outcome}",
                      reason=res.reason, source=source, failed=failed[:6])
            return res

        # Count what can actually be compared *before* trusting an empty
        # mismatch list. If the reader exposes no rate/ceil on either side,
        # compare_states returns [] -- which means "nothing was wrong", not
        # "everything was checked and matched". Reporting `verified` there
        # would make the check pass precisely when it has no content, and the
        # project's own rule for unverifiable fields says they must never read
        # as a pass.
        comparable = _comparable_pairs(target, actual)
        if not comparable:
            res = RollbackResult(
                False, UNVERIFIABLE,
                reason="the read-back exposed no comparable rate/ceil fields "
                       f"(target {len(target)} classes, actual "
                       f"{len(actual)} classes), so the restored state cannot "
                       "be confirmed -- an empty comparison is not a match",
                source=source, target="known-good")
            self.last_rollback = res
            self._log(self.clock(), "rollback_unverifiable", reason=res.reason,
                      source=source)
            return res

        mism, unver = compare_states(target, actual)
        self.last_readback_source = source

        if failed and not mism:
            # State matches, but a command was refused. Restoring the *observed*
            # state is confirmed; whether anything unobserved (a filter, say)
            # was left behind is not, so this is reported as partial rather
            # than folded into a pass.
            res = RollbackResult(
                False, PARTIAL,
                reason="read-back matched the known-good state, but "
                       f"{len(failed)} restore command(s) were refused",
                failed_commands=failed, source=source, target="known-good")
        elif mism:
            res = RollbackResult(
                False, VERIFICATION_FAILED,
                reason="post-rollback state does not match the known-good tree: "
                       + "; ".join(f"{m.classid}.{m.field} wanted "
                                   f"{m.expected:.3f} got {m.actual:.3f}"
                                   for m in mism[:4]),
                mismatches=mism, unverified=unver, failed_commands=failed,
                source=source, target="known-good")
        elif unver:
            # Everything checkable matched, but not everything was checkable.
            # Called out so it cannot be read as a clean verification.
            res = RollbackResult(
                False, UNVERIFIABLE,
                reason="read-back could not confirm "
                       f"{len(unver)} field(s): "
                       + ", ".join(f"{c}.{f}" for c, f in unver[:4]),
                unverified=unver, source=source, target="known-good")
        else:
            res = RollbackResult(True, VERIFIED,
                                 reason="post-rollback state matches the "
                                        "known-good tree",
                                 source=source, target="known-good")

        self.last_rollback = res
        self._log(self.clock(), f"rollback_{res.outcome}", reason=res.reason,
                  mismatches=[str(m) for m in res.mismatches[:6]],
                  unverified=[f"{c}.{f}" for c, f in res.unverified[:6]],
                  failed=res.failed_commands[:6], source=res.source)
        return res

    def force_safe(self, result: bool = False):
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
        last_err = ""
        for name, spec in ladder:
            self.runner.run(pre + ("tc", "qdisc", "del", "dev", self.dev, "root"))
            rc, _, err = self.runner.run(
                pre + ("tc", "qdisc", "add", "dev", self.dev, "root", "handle",
                       "1:", *spec))
            if rc != 0:
                last_err = f"{name}: {err.strip() or rc}"
                continue
            # A successful `tc qdisc add` is not proof the qdisc is there. Read
            # the root qdisc back before claiming the household is protected --
            # the safe state is class-free, so this is the only read that can
            # distinguish a working safe state from no qdisc at all.
            got, source = self._read_root_qdisc()
            if got and got.get("root"):
                self.safe_state_in_force = name
                res = RollbackResult(True, VERIFIED,
                                     reason=f"safe state '{name}' installed and "
                                            f"confirmed by read-back",
                                     source=source, target=f"safe:{name}")
                self.last_rollback = res
                return res if result else True
            last_err = (f"{name}: accepted by tc but read-back source={source} "
                        f"reported no root qdisc")
        self.safe_state_in_force = None
        res = RollbackResult(
            False, NO_TARGET if result else COMMANDS_FAILED,
            reason="no rung of the safe-state ladder could be installed and "
                   f"confirmed ({last_err})",
            source=self._read_root_qdisc()[1])
        self.last_rollback = res
        return res if result else False

    _last_capacity: float | None = None

    def remember_capacity(self, mbps: float) -> None:
        self._last_capacity = mbps

    def _log(self, t: float, event: str, **kw) -> None:
        self.audit.append({"t": round(t, 3), "event": event, **kw})

    @property
    def mode(self) -> Mode:
        return self.shield.state.mode
