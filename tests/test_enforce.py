"""M4 enforcement and M9 transaction/shield tests. No root, no tc, no network."""

from __future__ import annotations

import json
import unittest

from aciq.model import RatePlan, TrafficClass
from aciq.policy import build_plan
from aciq.shield import (
    BACKOFF_S,
    BREACHES_TO_FAULT,
    MAX_RETRIES,
    MIN_CHANGE_WINDOW_S,
    Mode,
    Shield,
)
from aciq.qdisc import ClassState, parse_class_json, parse_class_text
from aciq.tc import (
    ROOT_CLASS_ID,
    ROOT_HANDLE,
    build_tree,
    parse_class_state,
    render,
    unverified_fields,
    verify,
)
from aciq.txn import FakeRunner, TransactionManager

CAP = 100.0


def plan(cap=CAP, lease=None):
    return build_plan(cap, lease)


def readback_json(tree):
    """Explicit JSON read-back, for tests exercising the fallback reader."""
    out = []
    for c in tree.classes:
        out.append({"kind": "htb", "handle": c.classid,
                    "rate": int(round(c.rate_mbps * 1e6)),
                    "ceil": int(round(c.ceil_mbps * 1e6))})
    return json.dumps(out)


def readback_state(tree):
    """Read-back state a correct kernel would report, in Mbps."""
    return {c.classid: ClassState(classid=c.classid, rate_mbps=c.rate_mbps,
                                  ceil_mbps=c.ceil_mbps)
            for c in tree.classes}


def readback_text(tree) -> str:
    """Render a tree the way `tc class show` prints it, so the text parser is
    exercised against a realistic shape rather than a hand-written fixture."""
    out = []
    for c in tree.classes:
        out.append(f"class htb {c.classid} root prio 0 "
                   f"rate {c.rate_mbps:g}Mbit ceil {c.ceil_mbps:g}Mbit burst 15Kb")
        out.append("  Sent 123456 bytes 100 pkt (dropped 0, overlimits 3 requeues 0)")
    return "\n".join(out)


class TestTreeRendering(unittest.TestCase):
    def test_root_first_then_classes(self):
        cmds = render(build_tree(plan()))
        self.assertIn("root", cmds[0])
        self.assertEqual(cmds[0][cmds[0].index("handle") + 1], ROOT_HANDLE)

    def test_bare_class_comes_before_children(self):
        cmds = render(build_tree(plan()))
        # argv may carry an `ip netns exec <ns>` prefix, so locate "tc" first
        class_cmds = [c for c in cmds if c[c.index("tc") + 1] == "class"]
        self.assertEqual(class_cmds[0][class_cmds[0].index("classid") + 1], ROOT_CLASS_ID)

    def test_ceil_never_exceeds_capacity(self):
        """Measured: a 20 Mbit parent with ceil 99/97 delivered 28.5 Mbps."""
        for cap in (100.0, 20.0, 6.0):
            tree = build_tree(plan(cap))
            for c in tree.classes:
                self.assertLessEqual(c.ceil_mbps, cap + 1e-9)

    def test_leaf_handles_are_unique(self):
        cmds = render(build_tree(plan()))
        handles = [c[c.index("handle") + 1] for c in cmds if c[1] == "qdisc"]
        self.assertEqual(len(handles), len(set(handles)), handles)

    def test_filters_are_per_protocol(self):
        tree = build_tree(plan())
        protos = {f.protocol for f in tree.filters}
        self.assertEqual(protos, {"ip", "ipv6"})
        ip_f = next(f for f in tree.filters if f.protocol == "ip")
        v6_f = next(f for f in tree.filters if f.protocol == "ipv6")
        self.assertIn("u32", ip_f.command_tail)
        self.assertIn("flower", v6_f.command_tail)

    def test_filter_priorities_differ(self):
        tree = build_tree(plan())
        prios = [f.priority for f in tree.filters]
        self.assertEqual(len(prios), len(set(prios)))

    def test_no_filters_without_interactive(self):
        tree = build_tree(RatePlan(capacity_mbps=CAP,
                                   rates={TrafficClass.BULK: 10.0}))
        self.assertEqual(tree.filters, ())

    def test_leaf_args_accepts_string_or_tuple(self):
        from aciq.tc import leaf_args
        self.assertEqual(leaf_args("cake bandwidth 95mbit"),
                         ("cake", "bandwidth", "95mbit"))
        self.assertEqual(leaf_args(("fq_codel",)), ("fq_codel",))
        self.assertEqual(leaf_args(None), ())

    def test_tree_total_respects_capacity(self):
        self.assertLessEqual(build_tree(plan()).total_rate(), CAP + 1e-9)


class TestVerification(unittest.TestCase):
    def test_matching_state_verifies(self):
        tree = build_tree(plan())
        self.assertEqual(verify(tree, parse_class_state(readback_state(tree))), [])

    def test_text_output_round_trips(self):
        """The primary reader is text, verified by gate check 10."""
        tree = build_tree(plan())
        parsed = parse_class_text(readback_text(tree))
        self.assertEqual(verify(tree, parse_class_state(parsed)), [])

    def test_text_parser_reads_rates_and_units(self):
        parsed = parse_class_text(
            "class htb 1:10 root prio 0 rate 40Mbit ceil 100Mbit burst 15Kb")
        self.assertAlmostEqual(parsed["1:10"].rate_mbps, 40.0)
        self.assertAlmostEqual(parsed["1:10"].ceil_mbps, 100.0)

    def test_text_parser_reads_kbit_and_gbit(self):
        p = parse_class_text("class htb 1:1 root rate 500Kbit ceil 1Gbit")
        self.assertAlmostEqual(p["1:1"].rate_mbps, 0.5)
        self.assertAlmostEqual(p["1:1"].ceil_mbps, 1000.0)

    def test_text_parser_reads_counters(self):
        parsed = parse_class_text(
            "class htb 1:30 root rate 30Mbit ceil 100Mbit\n"
            "  Sent 9999 bytes 10 pkt (dropped 7, overlimits 42 requeues 1)")
        self.assertEqual(parsed["1:30"].rx_bytes, 9999)
        self.assertEqual(parsed["1:30"].drops, 7)
        self.assertEqual(parsed["1:30"].overlimits, 42)

    def test_json_parser_decodes_numeric_handles(self):
        parsed = parse_class_json(json.dumps(
            [{"handle": 65552, "rate": 40000000, "ceil": 100000000}]))
        self.assertIn("1:10", parsed)
        self.assertAlmostEqual(parsed["1:10"].rate_mbps, 40.0)

    def test_malformed_json_reads_as_empty(self):
        self.assertEqual(parse_class_json("{not json"), {})

    def test_missing_class_is_a_mismatch(self):
        tree = build_tree(plan())
        state = parse_class_state(readback_state(tree))
        del state["1:10"]
        self.assertTrue(any(m.field == "present" for m in verify(tree, state)))

    def test_wrong_rate_is_a_mismatch(self):
        tree = build_tree(plan())
        state = parse_class_state(readback_state(tree))
        state["1:30"]["rate"] = 1.0
        self.assertTrue(any(m.field == "rate" for m in verify(tree, state)))

    def test_unreadable_rate_is_unverifiable_not_a_mismatch(self):
        """A reader that cannot see rates is a weaker guarantee, not a wrong
        rate. It must not veto, and it must not read as a clean pass."""
        tree = build_tree(plan())
        state = {c: ClassState(classid=c) for c in ("1:1", "1:10", "1:20", "1:30")}
        parsed = parse_class_state(state)
        unverifiable = unverified_fields(tree, parsed)
        self.assertEqual(verify(tree, parsed, unverifiable), [])
        self.assertTrue(unverified_fields(tree, parsed))

    def test_verify_empty_state_fails_loudly(self):
        tree = build_tree(plan())
        self.assertTrue(verify(tree, {}))


class TestShieldVetoes(unittest.TestCase):
    def test_oversubscribed_plan_vetoed(self):
        bad = RatePlan(capacity_mbps=10.0,
                       rates={TrafficClass.INTERACTIVE: 8.0, TrafficClass.BULK: 8.0})
        codes = [v.code for v in Shield().veto_plan(bad)]
        self.assertIn("child_sum_exceeds_capacity", codes)

    def test_valid_plan_not_vetoed(self):
        self.assertEqual(Shield().veto_plan(plan()), [])

    def test_below_floor_vetoed(self):
        bad = RatePlan(capacity_mbps=100.0, rates={TrafficClass.BULK: 0.1})
        self.assertIn("below_floor", [v.code for v in Shield().veto_plan(bad)])

    def test_degraded_plan_is_not_vetoed_forever(self):
        """A tiny link scales its floors; the veto must accept that rather than
        vetoing every legitimately degraded plan."""
        p = build_plan(1.0)
        self.assertTrue(p.degraded)
        self.assertEqual(Shield().veto_plan(p), [])

    def test_rate_limit_blocks_rapid_changes(self):
        s = Shield()
        s.note_change(100.0)
        self.assertTrue(s.veto_rate(100.0 + MIN_CHANGE_WINDOW_S - 0.1))
        self.assertEqual(s.veto_rate(100.0 + MIN_CHANGE_WINDOW_S + 0.1), [])

    def test_drop_rate_limit(self):
        codes = [v.code for v in Shield().veto_load(drop_rate=99999, overlimit_rate=0)]
        self.assertIn("drop_rate_limit", codes)

    def test_normal_saturation_is_not_vetoed(self):
        """Gate check 12 measured 24803-65101 overlimits over 25s, i.e. ~1000-2600/s.
        A link that is merely busy must not be vetoed."""
        self.assertEqual(Shield().veto_load(drop_rate=10, overlimit_rate=2600), [])

    def test_delay_is_never_a_veto_input(self):
        """Delay rises exactly when the policy is stale; vetoing on it would
        block the fix. There is deliberately no such parameter."""
        import inspect
        self.assertNotIn("delay", inspect.signature(Shield.veto_load).parameters)
        self.assertNotIn("rtt", inspect.signature(Shield.veto_load).parameters)


class TestShieldStateMachine(unittest.TestCase):
    def test_breach_enters_fault_pending(self):
        s = Shield()
        s.breach(0.0, [])
        self.assertEqual(s.state.mode, Mode.FAULT_PENDING)

    def test_backoff_increases_and_caps(self):
        s = Shield()
        seen = []
        for i in range(10):
            s.breach(float(i * 100), [])
            seen.append(s.backoff_s())
        self.assertEqual(seen[:6], list(BACKOFF_S))
        self.assertTrue(all(b == BACKOFF_S[-1] for b in seen[6:]))

    def test_budget_exhausted_gives_safe_held_with_alarm(self):
        s = Shield()
        for i in range(MAX_RETRIES + 2):
            s.breach(float(i * 100), [])
        self.assertEqual(s.state.mode, Mode.SAFE_HELD)
        self.assertIsNotNone(s.state.alarm)

    def test_reset_clears_the_change_window(self):
        """A reset that leaves the dwell window latched suppresses the next
        legitimate policy change. In the matrix this made a later run fail its
        opening apply for a change made in a different run entirely."""
        s = Shield()
        s.note_change(1000.0)
        s.reset()
        self.assertIsNone(s.state.last_change_t)
        self.assertEqual(s.veto_rate(1000.1), [])

    def test_safe_held_is_recoverable_only_by_manual_reset(self):
        s = Shield()
        for i in range(MAX_RETRIES + 2):
            s.breach(float(i * 100), [])
        s.observe_ok(10_000.0)
        self.assertEqual(s.state.mode, Mode.SAFE_HELD)
        s.reset()
        self.assertEqual(s.state.mode, Mode.MONITOR)
        self.assertIsNone(s.state.alarm)

    def test_retry_budget_beats_rolling_window(self):
        """Once backoff hits 60s each attempt lands in its own 60s window, so a
        window-based counter would never exhaust and would loop forever."""
        s = Shield()
        s.breach(0.0, [])
        for i in range(1, MAX_RETRIES + 3):
            s.breach(float(i * 1000.0), [])  # 1000s apart: always a new window
        self.assertEqual(s.state.mode, Mode.SAFE_HELD)

    def test_may_retry_respects_backoff(self):
        s = Shield()
        s.breach(0.0, [])
        self.assertFalse(s.may_retry(0.1))
        self.assertTrue(s.may_retry(100.0))

    def test_monitor_mode_never_retries(self):
        self.assertFalse(Shield().may_retry(10_000.0))

    def test_three_breaches_in_window_trip_fault(self):
        s = Shield()
        for i in range(BREACHES_TO_FAULT):
            s.breach(float(i), [])
        self.assertTrue(s.state.in_fault)


class TestTransaction(unittest.TestCase):
    def _tm(self, runner, clock=lambda: 0.0):
        return TransactionManager(runner, Shield(), clock=clock)

    def test_successful_apply_commits(self):
        tree = build_tree(plan())
        r = FakeRunner(readback=readback_json(tree))
        out = self._tm(r).apply(plan())
        self.assertTrue(out.ok)
        self.assertTrue(out.committed)
        self.assertFalse(out.rolled_back)

    def test_rebuild_deletes_root_first(self):
        tree = build_tree(plan())
        r = FakeRunner(readback=readback_json(tree))
        self._tm(r).apply(plan())
        dels = [c for c in r.commands if "del" in c and "root" in c]
        self.assertTrue(dels, "root must be deleted before rebuild")

    def test_apply_failure_rolls_back(self):
        tree = build_tree(plan())
        # transient fault: the rollback that follows can still succeed
        r = FakeRunner(fail_on="1:30", readback=readback_json(tree), fail_once=True)
        out = self._tm(r).apply(plan())
        self.assertFalse(out.ok)
        self.assertFalse(out.committed)
        self.assertTrue(out.rolled_back)

    def test_broken_class_no_longer_prevents_rollback(self):
        """A persistent failure on one class used to make rollback fail too.
        The safe state no longer contains that class, so recovery works."""
        tree = build_tree(plan())
        r = FakeRunner(fail_on="1:30", readback=readback_json(tree))
        tm = self._tm(r)
        tm.remember_capacity(CAP)
        out = tm.apply(plan())
        self.assertFalse(out.ok)
        self.assertTrue(out.rolled_back)

    def test_total_kernel_refusal_reports_rollback_failed_honestly(self):
        """If the kernel refuses every qdisc, nothing can be applied. Reporting
        rolled_back=True there would be a lie."""
        class Dead(FakeRunner):
            def run(self, argv):
                self.commands.append(argv)
                if "qdisc" in argv and "add" in argv:
                    return 1, "", "kernel refuses all qdiscs"
                return 0, "", ""
        tm = TransactionManager(Dead(), Shield())
        tm.remember_capacity(CAP)
        out = tm.apply(plan())
        self.assertFalse(out.ok)
        self.assertFalse(out.rolled_back)

    def test_readback_mismatch_rolls_back(self):
        tree = build_tree(plan())
        wrong = json.dumps([{"kind": "htb", "handle": c.classid, "rate": 1, "ceil": 1}
                            for c in tree.classes])
        out = self._tm(FakeRunner(readback=wrong)).apply(plan())
        self.assertFalse(out.ok)
        self.assertTrue(out.mismatches)
        self.assertTrue(out.rolled_back)

    def test_vetoed_plan_never_touches_the_kernel(self):
        bad = RatePlan(capacity_mbps=10.0,
                       rates={TrafficClass.INTERACTIVE: 8.0, TrafficClass.BULK: 8.0})
        r = FakeRunner()
        out = self._tm(r).apply(bad)
        self.assertFalse(out.ok)
        self.assertEqual(r.commands, [], "a vetoed plan must not run any tc command")

    def test_audit_log_records_outcome(self):
        tree = build_tree(plan())
        tm = self._tm(FakeRunner(readback=readback_json(tree)))
        tm.apply(plan())
        self.assertEqual(tm.audit[-1]["event"], "committed")

    def test_audit_records_veto(self):
        bad = RatePlan(capacity_mbps=10.0,
                       rates={TrafficClass.INTERACTIVE: 8.0, TrafficClass.BULK: 8.0})
        tm = self._tm(FakeRunner())
        tm.apply(bad)
        self.assertEqual(tm.audit[-1]["event"], "vetoed")

    def test_rate_limited_apply_does_not_fault_the_shield(self):
        tree = build_tree(plan())
        tm = self._tm(FakeRunner(readback=readback_json(tree)), clock=lambda: 0.0)
        self.assertTrue(tm.apply(plan()).ok)
        out = tm.apply(plan())
        self.assertFalse(out.ok)
        self.assertEqual(tm.mode, Mode.MONITOR)
        self.assertEqual(tm.audit[-1]["event"], "deferred")

    def test_second_apply_is_rate_limited(self):
        tree = build_tree(plan())
        tm = self._tm(FakeRunner(readback=readback_json(tree)), clock=lambda: 0.0)
        self.assertTrue(tm.apply(plan()).ok)
        out = tm.apply(plan())
        self.assertFalse(out.ok)
        self.assertIn("rate_limited", [v.code for v in out.violations])

    def test_apply_is_refused_while_in_fault(self):
        tree = build_tree(plan())
        tm = self._tm(FakeRunner(fail_on="1:30", readback=readback_json(tree)))
        tm.apply(plan())
        self.assertTrue(tm.shield.state.in_fault)
        r2 = FakeRunner(readback=readback_json(tree))
        tm.runner = r2
        out = tm.apply(plan())
        self.assertFalse(out.ok)
        self.assertEqual(r2.commands, [], "must not touch the kernel while in fault")


class TestSafeState(unittest.TestCase):
    def test_safe_state_succeeds_when_a_class_is_broken(self):
        """The safe state must not contain whatever the kernel is refusing.
        A persistent failure on 1:30 used to make rollback fail too, leaving the
        household unshaped in exactly the moment protection mattered most."""
        tree = build_tree(plan())
        r = FakeRunner(fail_on="1:30", readback=readback_json(tree))
        tm = TransactionManager(r, Shield())
        tm.remember_capacity(CAP)
        out = tm.apply(plan())
        self.assertTrue(out.rolled_back)
        self.assertEqual(tm.safe_state_in_force, "cake")

    def test_safe_state_escalates_when_cake_is_refused(self):
        r = FakeRunner(fail_on="cake")
        tm = TransactionManager(r, Shield())
        tm.remember_capacity(CAP)
        self.assertTrue(tm.force_safe())
        self.assertEqual(tm.safe_state_in_force, "fq_codel")

    def test_safe_state_escalates_all_the_way_to_pfifo(self):
        """cake and fq_codel refused, so the last rung must still work."""
        r = FakeRunner(fail_on="cake")
        r2 = FakeRunner(fail_on="fq_codel")
        class Both(FakeRunner):
            # Refuses two qdiscs, then defers to the parent for everything
            # else so the pfifo rung is actually *modelled* in the fake
            # kernel. Returning a bare 0 would claim pfifo was installed
            # without any state to read back, which is precisely the situation
            # the new verification refuses to accept.
            def run(self, argv):
                joined = " ".join(argv)
                if "qdisc" in argv and "add" in argv and ("cake" in joined or "fq_codel" in joined):
                    self.commands.append(argv)
                    return 1, "", "refused"
                return super().run(argv)
        tm = TransactionManager(Both(), Shield())
        tm.remember_capacity(CAP)
        self.assertTrue(tm.force_safe())
        self.assertEqual(tm.safe_state_in_force, "pfifo")

    def test_safe_state_reports_failure_when_nothing_works(self):
        class Dead(FakeRunner):
            def run(self, argv):
                self.commands.append(argv)
                if "qdisc" in argv and "add" in argv:
                    return 1, "", "kernel refuses all qdiscs"
                return 0, "", ""
        tm = TransactionManager(Dead(), Shield())
        tm.remember_capacity(CAP)
        self.assertFalse(tm.force_safe())
        self.assertIsNone(tm.safe_state_in_force)

    def test_safe_state_is_a_valid_protecting_tree(self):
        safe = build_tree(build_plan(CAP))
        for c in safe.classes:
            self.assertLessEqual(c.ceil_mbps, CAP + 1e-9)


if __name__ == "__main__":
    unittest.main()
