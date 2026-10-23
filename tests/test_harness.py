"""M6 harness tests. No root, no tc, no traffic — the runner is injected."""

from __future__ import annotations

import json
import unittest

from aciq.harness import (
    ROOT_CLASS_ID,
    SCENARIOS,
    SINGLE_CLASS_ID,
    CapacityMode,
    Harness,
    RunResult,
    SystemSpec,
    baseline_tree,
)
from aciq.intent import Lease
from aciq.metrics import ClassCounters
from aciq.model import TrafficClass
from aciq.tc import render
from aciq.txn import FakeRunner


def harness(runner=None):
    """Default to auto_readback so verification genuinely passes and the
    transaction can actually commit."""
    return Harness(runner=runner or FakeRunner(auto_readback=True), clock=lambda: 0.0)


def saturating(now, rx, over_before, over_after):
    return counters(rx=rx, overlimits=over_after)


class TestCapacityInvariant(unittest.TestCase):
    """The reason this module exists."""

    def test_set_capacity_does_not_touch_the_parents_class(self):
        """Inverted deliberately, and this is the whole defect.

        It used to assert `set_capacity` wrote class 1:1 first. It does not
        anymore, because `build_plan` writes 1:1 too -- so the controller's
        policy change erased the capacity drop it was being asked to detect,
        and the estimator then reported the number the controller chose.
        Measured: 100 -> 10 -> 47 Mbps on one run.

        The bottleneck is now netem on ns wan / veth-w, which
        `TransactionManager` never writes.
        """
        h = harness()
        for argv in h.set_capacity(20.0):
            text = " ".join(argv)
            self.assertNotIn(f"classid {ROOT_CLASS_ID}", text,
                             f"set_capacity must not write {ROOT_CLASS_ID}")

    def test_CAPACITY_IS_ENFORCED_OUT_OF_BAND_NOT_BY_CLAMPING(self):
        """Superseded by a real bottleneck; the clamp is the collision.

        A class borrows past its parent rate up to its own ceil, so the old
        implementation clamped every child's ceil to force the link down. That
        is exactly the write the controller then overwrote on its next policy
        change. The link is now limited physically by netem, so there is nothing
        to clamp and nothing for the controller to undo.
        """
        h = harness()
        h.apply_system(SystemSpec.ACIQ, 100.0)
        before = len(h.runner.commands)
        h.set_capacity(10.0)
        added = [" ".join(c) for c in h.runner.commands[before:]]
        self.assertTrue(any("netem" in c and "10.0000mbit" in c for c in added),
                        f"expected a netem rate limit: {added}")
        for c in added:
            self.assertNotIn("parent 1:1 classid", c,
                             "no class on the controller's tree may be written")

    def test_OLD_clamp_mechanism_is_gone(self):
        """The previous test, kept as its own assertion so the clamp cannot
        creep back.
        The parent rate alone does not cap a subtree: a class borrows
        past its parent's rate up to its own ceil, and build_plan sets every child
        ceil to the capacity at plan time. Six `--drop-at` experiments reported a
        link state they never reached because this clamp was missing -- measured
        24.68 Mbps through a "10 Mbps" parent in data/leaseB4.

        Gate check 6 is the evidence both are needed: it drops the parent *and*
        rescales child ceil, then asserts max(child ceil) <= capacity.
        """
        h = harness()
        h.apply_system(SystemSpec.ACIQ, 100.0)
        before = len(h.runner.commands)
        h.set_capacity(10.0)
        added = [" ".join(c) for c in h.runner.commands[before:]]
        classes = [c for c in added if "parent 1:1 classid" in c]
        self.assertEqual(classes, [],
                         "the clamp is the collision; it must not come back")

    def test_every_child_command_carries_a_rate(self):
        """tc refuses `class change ... htb ceil X` with `"rate" is required`.

        Measured: dropcheck3 reported capacity_change_applied False with

            classid 1:10 htb ceil 10.0000mbit -> "rate" is required.

        The clamp cannot be expressed on its own, which is why this looked like a
        mysterious refusal until the error text was finally surfaced into the
        artefact.
        """
        h = harness()
        h.apply_system(SystemSpec.ACIQ, 100.0)
        for cmd in h.set_capacity(10.0):
            if "parent 1:1 classid" in " ".join(cmd):
                self.assertIn(" rate ", f" {' '.join(cmd)} ")


    def test_no_child_rate_ever_exceeds_its_own_ceil(self):
        """`rate <= ceil` is an HTB requirement, not a clamp artefact.

        The clamp that used to be applied here is gone, but the validity rule
        the kernel enforces is not: a class whose rate exceeds its own ceil is
        refused. netem carries a rate and no ceil, so it is skipped rather than
        mistaken for a class.
        """
        h = harness()
        h.apply_system(SystemSpec.ACIQ, 100.0)
        seen = 0
        for c in h.runner.commands:
            text = " ".join(c)
            if " rate " not in f" {text} " or " ceil " not in f" {text} ":
                continue
            rate = float(text.split(" rate ")[1].split("mbit")[0])
            ceil = float(text.split(" ceil ")[1].split("mbit")[0])
            self.assertLessEqual(rate, ceil, f"invalid HTB class: {text}")
            seen += 1
        self.assertTrue(seen, "no classes were checked")
    def test_a_clamp_never_raises_a_child_rate(self):
        """min() only. Raising one would hand M3's bandwidth to someone."""
        h = harness()
        h.apply_system(SystemSpec.ACIQ, 100.0)
        before = {}
        for c in h.runner.commands:
            t = " ".join(c)
            if "classid" in t and " rate " in f" {t} ":
                before[t.split("classid ")[1].split(" ")[0]] = float(
                    t.split(" rate ")[1].split("mbit")[0])
        for cmd in h.set_capacity(10.0):
            text = " ".join(cmd)
            if "parent 1:1 classid" not in text:
                continue
            cid = text.split("classid ")[1].split(" ")[0]
            rate = float(text.split(" rate ")[1].split("mbit")[0])
            self.assertLessEqual(rate, before.get(cid, rate) + 1e-9)


    def test_child_rates_still_sum_to_the_new_capacity(self):
        """The invariant is unchanged; only the enforcer moved.

        The limit is now physical -- netem on `wan/veth-w`, a link the
        controller never writes -- rather than a rescale that the controller
        overwrote on its very next policy change. So the sum invariant is a
        property of build_plan, and is asserted as one.
        """
        for cap in (100.0, 20.0, 10.0, 3.0):
            h = harness()
            h.apply_system(SystemSpec.ACIQ, cap)
            h.set_capacity(cap)
            plan = h._current_plan
            self.assertLessEqual(sum(plan.rates.values()), cap + 1e-6,
                                 f"children promised more than {cap}")
            for cid, rate in plan.rates.items():
                self.assertLessEqual(rate, cap + 1e-6, f"{cid} at {cap}")

    def test_the_proportions_m3_chose_survive_a_capacity_change(self):
        """M3 owns the proportions and a drop must not flatten them.

        The rescale that used to live in set_capacity is what preserved them,
        and it is gone because it was the collision. build_plan computes the
        same proportions for a capacity, so the property survives -- asserted
        against build_plan now rather than against commands that are no longer
        emitted.
        """
        h = harness()
        h.apply_system(SystemSpec.ACIQ, 100.0)
        before = dict(h._current_plan.rates)
        self.assertTrue(before, "no plan rates to preserve")

        h.set_capacity(10.0)
        h.apply_system(SystemSpec.ACIQ, 10.0)
        after = dict(h._current_plan.rates)
        self.assertTrue(after, "no plan rates after the drop")
        self.assertEqual(sorted(map(str, before)), sorted(map(str, after)))

        tb, ta = sum(before.values()), sum(after.values())
        for b4, a4 in zip(sorted(before.values(), reverse=True),
                          sorted(after.values(), reverse=True)):
            self.assertAlmostEqual(b4 / tb, a4 / ta, places=6,
                                   msg="proportions flattened across the drop")
    def test_a_grown_capacity_does_not_rescale_upwards(self):
        """A capacity that grows is M3's to replan. The harness only shrinks."""
        h = harness()
        h.apply_system(SystemSpec.ACIQ, 100.0)
        before = len(h.runner.commands)
        h.set_capacity(200.0)
        for cmd in h.runner.commands[before:]:
            text = " ".join(cmd)
            if "parent 1:1 classid" in text:
                rate = float(text.split(" rate ")[1].split("mbit")[0])
                self.assertLessEqual(rate, 100.0,
                                     f"a capacity change handed out bandwidth: {text}")

    def test_set_capacity_emits_no_qdisc_command_on_the_controller_device(self):
        """The intent survives the mechanism change.

        It originally forbade any qdisc command, because replacing a qdisc on
        `veth-lan` destroys the tree the controller owns. That is still the
        rule -- it is now scoped to the controller's device, because the
        bottleneck has to be a qdisc somewhere and it is deliberately NOT
        there.
        """
        h = harness()
        h.set_capacity(20.0)
        for cmd in h.runner.commands:
            text = " ".join(cmd)
            if "qdisc" not in text:
                continue
            self.assertNotIn(h.dev, text,
                             f"qdisc command on the controller's device: {text}")
            self.assertIn(h.bottleneck_dev, text,
                          f"qdisc command must be on the bottleneck: {text}")

    def test_capacity_value_reaches_the_command(self):
        h = harness()
        cmds = h.set_capacity(19.5)
        self.assertIn("19.5000mbit", " ".join(cmds[0]))


class TestBaselineTrees(unittest.TestCase):
    def test_leaf_spec_is_split_into_separate_argv_tokens(self):
        """Regression guard for a real failure.

        A leaf spec reaching subprocess as ONE argument made tc search for a
        qdisc kind named "cake bandwidth 95.0000mbit" and fail with
        "Specified qdisc kind is unknown" — indistinguishable, from the error
        text alone, from a missing kernel module.
        """
        for system, expected in ((SystemSpec.B0, ["pfifo", "limit", "1000"]),
                                 (SystemSpec.B1, ["cake", "bandwidth"])):
            for argv in render(baseline_tree(system, 100.0)):
                if "parent" in argv and "qdisc" in argv and "add" in argv:
                    self.assertNotIn(" ", argv[-1],
                                     f"{system.value}: {argv[-1]!r} is one token")
                    for token in expected:
                        self.assertIn(token, argv)
                    break

    """All three systems face the same bottleneck and differ only in queueing."""

    def test_b0_uses_pfifo_with_a_realistic_limit(self):
        tree = baseline_tree(SystemSpec.B0, 100.0)
        leaf = next(c for c in tree.classes if c.classid == SINGLE_CLASS_ID)
        self.assertEqual(tuple(leaf.leaf), ("pfifo", "limit", "1000"))

    def test_b1_uses_cake_at_95_percent(self):
        tree = baseline_tree(SystemSpec.B1, 100.0)
        leaf = next(c for c in tree.classes if c.classid == SINGLE_CLASS_ID)
        spec = tuple(leaf.leaf)
        self.assertEqual(spec[:2], ("cake", "bandwidth"))
        self.assertTrue(spec[2].startswith("95"))

    def test_b1_is_below_capacity_to_avoid_double_shaping(self):
        """Two shapers at the same rate fight for the same bytes."""
        tree = baseline_tree(SystemSpec.B1, 100.0)
        leaf = next(c for c in tree.classes if c.classid == SINGLE_CLASS_ID)
        mbps = float(tuple(leaf.leaf)[2].rstrip("mbit"))
        self.assertLess(mbps, 100.0)

    def test_baselines_share_the_same_parent_class(self):
        b0 = baseline_tree(SystemSpec.B0, 100.0)
        b1 = baseline_tree(SystemSpec.B1, 100.0)
        p0 = next(c for c in b0.classes if c.classid == ROOT_CLASS_ID)
        p1 = next(c for c in b1.classes if c.classid == ROOT_CLASS_ID)
        self.assertEqual(p0.rate_mbps, p1.rate_mbps)
        self.assertEqual(p0.ceil_mbps, p1.ceil_mbps)

    def test_baseline_ceil_never_exceeds_capacity(self):
        for cap in (100.0, 20.0):
            for sys_ in (SystemSpec.B0, SystemSpec.B1):
                tree = baseline_tree(sys_, cap)
                for c in tree.classes:
                    self.assertLessEqual(c.ceil_mbps, cap + 1e-9)

    def test_baselines_have_no_filters(self):
        self.assertEqual(baseline_tree(SystemSpec.B0, 100.0).filters, ())

    def test_baselines_default_to_their_single_class(self):
        tree = baseline_tree(SystemSpec.B0, 100.0)
        self.assertEqual(tree.default_class, "50")


class TestScenarios(unittest.TestCase):
    def test_scenario_one_is_iso_during_a_call(self):
        kinds = {w.kind for w in SCENARIOS["s1_iso_during_call"].workloads}
        self.assertEqual(kinds, {"call", "bulk"})

    def test_scenario_three_is_three_tvs_and_a_game(self):
        s = SCENARIOS["s3_tv_and_gaming"]
        videos = [w for w in s.workloads if w.kind == "video"]
        games = [w for w in s.workloads if w.kind == "game"]
        self.assertEqual(len(videos), 3)
        self.assertEqual(len(games), 1)

    def test_interactive_workloads_are_dscp_marked(self):
        """Real VoIP endpoints mark EF; M1 keys on that, not on generator ports."""
        for name, s in SCENARIOS.items():
            for w in s.workloads:
                if w.kind in ("call", "game"):
                    self.assertEqual(w.dscp, 46, f"{name}/{w.label}")

    def test_seed_is_reproducible(self):
        s = SCENARIOS["s3_tv_and_gaming"]
        self.assertEqual(s.seed_workloads(42), s.seed_workloads(42))

    def test_different_seeds_give_different_ports(self):
        s = SCENARIOS["s3_tv_and_gaming"]
        self.assertNotEqual(s.seed_workloads(1), s.seed_workloads(2))

    def test_ports_are_not_the_generator_defaults(self):
        """M1 must not be able to identify a flow by 'it is call.py on 5001'."""
        s = SCENARIOS["s1_iso_during_call"]
        for _, port, _ in s.seed_workloads(7):
            self.assertNotIn(port, (5001, 5002, 5003, 5004))

    def test_workload_ports_are_unique(self):
        for s in SCENARIOS.values():
            ports = [p for _, p, _ in s.seed_workloads(3)]
            self.assertEqual(len(ports), len(set(ports)), f"{s.name} has duplicate ports")


class TestApplySystem(unittest.TestCase):
    def test_baseline_apply_rebuilds_the_tree(self):
        r = FakeRunner()
        h = Harness(runner=r, clock=lambda: 0.0)
        self.assertTrue(h.apply_system(SystemSpec.B0, 100.0))
        self.assertTrue(any("del" in c and "root" in c for c in r.commands))

    def test_aciq_apply_goes_through_the_transaction(self):
        r = FakeRunner()
        h = Harness(runner=r, clock=lambda: 0.0)
        h.apply_system(SystemSpec.ACIQ, 100.0)
        # classes come from the plan, so 1:10 must be present
        self.assertTrue(any("1:10" in " ".join(c) for c in r.commands))

    def test_apply_failure_is_reported(self):
        r = FakeRunner(fail_on="class")
        h = Harness(runner=r, clock=lambda: 0.0)
        self.assertFalse(h.apply_system(SystemSpec.B0, 100.0))


def counters(rx=0, drops=0, overlimits=0, backlog=0):
    return {
        TrafficClass.INTERACTIVE: ClassCounters(
            cls=TrafficClass.INTERACTIVE, rx_bytes=rx, drops=drops,
            overlimits=overlimits, backlog_bytes=backlog),
        TrafficClass.BULK: ClassCounters(
            cls=TrafficClass.BULK, rx_bytes=rx, drops=drops,
            overlimits=overlimits, backlog_bytes=backlog),
    }


def link(rx=0, drops=0, overlimits=0):
    """Parent-class counters. Only these decide saturation."""
    return ClassCounters(cls=TrafficClass.INTERACTIVE, rx_bytes=rx,
                         drops=drops, overlimits=overlimits)


class TestClosedLoop(unittest.TestCase):
    """M2 -> M3 -> M4, driven only by counters."""

    def test_child_pressure_alone_does_not_adapt(self):
        """Measured death spiral: children over their guarantees on an idle
        link shrank a 100 Mbps estimate to 7.2 Mbps."""
        h = harness()
        for t in range(20):
            h.adapt_step(counters(rx=1_000_000, overlimits=1300),
                         dt=1.0, now=float(t), link=link())
        self.assertEqual(h.policy_changes, 0)

    def test_first_iteration_only_establishes_a_baseline(self):
        h = harness()
        cap, changed = h.adapt_step(counters(rx=0), dt=1.0, now=0.0, link=link())
        self.assertIsNone(cap)
        self.assertFalse(changed)

    def test_no_adaptation_while_idle(self):
        """An idle link carries no capacity information."""
        h = harness()
        h.adapt_step(counters(rx=0), dt=1.0, now=0.0, link=link())
        cap, changed = h.adapt_step(counters(rx=1000), dt=1.0, now=1.0, link=link())
        self.assertIsNone(cap)
        self.assertFalse(changed)

    def test_adapts_down_when_counters_show_saturation(self):
        h = harness()
        h.adapt_step(counters(rx=0), dt=1.0, now=0.0, link=link())
        h.adapt_step(counters(rx=0, overlimits=9000), dt=1.0, now=1.0, link=link(overlimits=9000))
        # Saturated again, and throughput has collapsed to ~20 Mbps.
        # overlimits must keep RISING each saturated sample: M2 treats a flat
        # overlimit count as "not saturated right now", which is correct.
        cap, changed = h.adapt_step(counters(rx=2_500_000, overlimits=18000),
                                    dt=1.0, now=10.0, link=link(overlimits=18000))
        self.assertTrue(changed)
        self.assertIsNotNone(cap)
        self.assertLess(cap, 100.0)

    def test_flat_overlimits_is_not_treated_as_saturation(self):
        """M2 reads rate, not level. A static overlimit count carries no news."""
        h = harness()
        h.adapt_step(counters(rx=0), dt=1.0, now=0.0, link=link())
        h.adapt_step(counters(rx=0, overlimits=9000), dt=1.0, now=1.0, link=link(overlimits=9000))
        cap, changed = h.adapt_step(counters(rx=2_500_000, overlimits=9000),
                                    dt=1.0, now=10.0, link=link(overlimits=9000))
        self.assertFalse(changed)

    def test_adaptation_never_reads_the_configured_rate(self):
        """The step function's only inputs are counters. `link` is the parent's
        observed counters, not its configured rate."""
        import inspect
        params = list(inspect.signature(Harness.adapt_step).parameters)
        self.assertEqual(params, ["self", "counters", "dt", "now", "link"])
        self.assertNotIn("capacity", params)
        self.assertNotIn("configured", params)

    def test_policy_changes_are_counted(self):
        h = harness()
        h.adapt_step(counters(rx=0), dt=1.0, now=0.0, link=link())
        h.adapt_step(counters(rx=0, overlimits=9000), dt=1.0, now=1.0, link=link(overlimits=9000))
        h.adapt_step(counters(rx=2_500_000, overlimits=18000), dt=1.0, now=10.0,
                     link=link(overlimits=18000))
        self.assertGreaterEqual(h.policy_changes, 1)

    def test_adaptation_rebuilds_the_tree_with_rescaled_children(self):
        """After detecting the drop, M3 rescales children and M4 rebuilds.
        This is what set_capacity must NOT have done."""
        h = harness()
        h.apply_system(SystemSpec.ACIQ, 100.0)
        h.reset_loop()
        h.adapt_step(counters(rx=0), dt=1.0, now=0.0, link=link())
        h.adapt_step(counters(rx=0, overlimits=9000), dt=1.0, now=1.0, link=link(overlimits=9000))
        before = len(h.runner.commands)
        h.adapt_step(counters(rx=2_500_000, overlimits=18000), dt=1.0, now=10.0,
                     link=link(overlimits=18000))
        added = " ".join(" ".join(c) for c in h.runner.commands[before:])
        self.assertIn("1:10", added)   # children were rescaled
        self.assertIn("1:30", added)

    def test_reset_clears_loop_state(self):
        h = harness()
        h.adapt_step(counters(rx=100), dt=1.0, now=0.0, link=link())
        h.reset_loop()
        self.assertEqual(h.policy_changes, 0)
        cap, changed = h.adapt_step(counters(rx=999_999), dt=1.0, now=5.0, link=link())
        self.assertFalse(changed)


class TestCapacityModes(unittest.TestCase):
    def test_three_modes_exist(self):
        self.assertEqual({m.value for m in CapacityMode},
                         {"static", "informed", "adaptive"})

    def test_static_baseline_is_not_told_about_a_drop(self):
        h = harness()
        h.apply_system(SystemSpec.B1, 100.0)
        before = len(h.runner.commands)
        h.set_capacity(20.0)
        added = [" ".join(c) for c in h.runner.commands[before:]]
        # Two commands now: apply the out-of-band limit, then read it back.
        # Still no rebuild of the baseline's tree, which is what this test is
        # actually about -- a static baseline must not be told the new rate.
        self.assertEqual(len(added), 2, added)
        self.assertTrue(any("qdisc replace" in c for c in added))
        self.assertTrue(any("qdisc show" in c for c in added))
        for c in added:
            self.assertNotIn("class add", c)
            self.assertNotIn("class change", c)

    def test_adaptive_path_needs_no_out_of_band_capacity(self):
        """ACIQ reaches its new rate purely by observing counters."""
        h = harness()
        h.apply_system(SystemSpec.ACIQ, 100.0)
        h.reset_loop()
        h.adapt_step(counters(rx=0), dt=1.0, now=0.0, link=link())
        h.adapt_step(counters(rx=0, overlimits=9000), dt=1.0, now=1.0, link=link(overlimits=9000))
        cap, changed = h.adapt_step(counters(rx=2_500_000, overlimits=18000),
                                    dt=1.0, now=10.0, link=link(overlimits=18000))
        self.assertTrue(changed)


class TestRunResult(unittest.TestCase):
    def test_serialises_to_json(self):
        r = RunResult(
            scenario="s1_iso_during_call", system="aciq",
            capacity_mode=CapacityMode.ADAPTIVE.value, seed=42,
            link_start_mbps=100.0, link_end_mbps=20.0,
            estimator_mbps=19.1, samples=[{"t": 1.0}], policy_changes=2,
        )
        data = json.loads(r.to_json())
        self.assertEqual(data["system"], "aciq")
        self.assertEqual(data["policy_changes"], 2)
        self.assertEqual(data["estimator_mbps"], 19.1)

    def test_estimator_value_may_be_absent(self):
        r = RunResult("s1", "b0", "static", 1, 100.0, 100.0)
        self.assertIsNone(json.loads(r.to_json())["estimator_mbps"])


if __name__ == "__main__":
    unittest.main()


class TestALeaseCannotUndoACapacityDrop(unittest.TestCase):
    """A lease applied after a drop rebuilt its plan from the capacity the run
    *started* at, because set_capacity never recorded the capacity it had
    applied. The lease plan carries the parent rate, so applying it restored the
    link: measured 15.1-15.4 Mbps against a 10 Mbps cap for the six seconds
    after the lease committed.
    """

    def _dropped(self):
        h = harness()
        h.apply_system(SystemSpec.ACIQ, 100.0)
        h.set_capacity(10.0)
        return h

    def test_the_applied_capacity_is_remembered(self):
        self.assertEqual(self._dropped()._capacity_mbps, 10.0)

    def test_a_stale_capacity_argument_cannot_restore_the_link(self):
        h = self._dropped()
        lease = Lease(id="l1", target="device", ip="203.0.113.4", weight=0.6)
        h.sync_lease(lease, 100.0)          # the value the run started at
        self.assertEqual(h._current_plan.capacity_mbps, 10.0,
                         "the lease plan was built for the pre-drop capacity")

    def test_no_class_is_promised_more_than_the_link_has(self):
        h = self._dropped()
        lease = Lease(id="l1", target="device", ip="203.0.113.4", weight=0.6)
        h.sync_lease(lease, 100.0)
        # rates are keyed by TrafficClass, not by classid string.
        children = sum(h._current_plan.rates.values())
        self.assertLessEqual(children, 10.0,
                             f"children promised {children} of a 10 Mbps link")

    def test_the_lease_still_gets_its_share_of_the_smaller_link(self):
        """The point of the fix is to *shrink* the lease, not to lose it."""
        h = self._dropped()
        lease = Lease(id="l1", target="device", ip="203.0.113.4", weight=0.6)
        h.sync_lease(lease, 100.0)
        self.assertIn(TrafficClass.LEASED, h._current_plan.rates,
                      "the lease class disappeared from the plan")
        self.assertGreater(h._current_plan.rates[TrafficClass.LEASED], 0.0)

    def test_a_fresh_harness_still_accepts_the_caller_capacity(self):
        """_capacity_mbps is None until something is applied; falling back to
        the argument keeps a fresh harness working."""
        h = harness()
        self.assertIsNone(h._capacity_mbps)
        h.apply_system(SystemSpec.ACIQ, 50.0)
        self.assertEqual(h._capacity_mbps, 50.0)


class TestTheShieldRetryCannotReapplyAStalePlan(unittest.TestCase):
    """A lease applied at t=0 is deferred by the shield's change window and
    retried each tick. The retry takes the "lease unchanged" path, which skipped
    the plan rebuild -- so it applied the plan built at the start of the run:

        classid 1:1  htb rate 100.0000mbit ceil 100.0000mbit
        classid 1:40 htb rate  39.0984mbit ceil 100.0000mbit

    on a link that had been capped to 10 Mbps. Measured 12.27 Mbps against a
    10 Mbit parent, 23% over.
    """

    def _deferred_lease_then_drop(self):
        clock = [0.0]
        h = Harness(runner=FakeRunner(auto_readback=True), clock=lambda: clock[0])
        h.reset_for_run()
        h.set_lease(None, 100.0)
        h.apply_system(SystemSpec.ACIQ, 100.0)
        lease = Lease(id="l", target="device", ip="203.0.113.4", weight=0.6)
        first = h.sync_lease(lease, 100.0)
        self.assertFalse(first, "the first apply should be deferred by the shield")
        return h, lease, clock

    def test_a_drop_updates_the_configured_capacity(self):
        """Both the enforcer and the per-tick lease sync read this. Left at the
        run's starting value, a dropped link kept being treated as 100 Mbps."""
        h, _lease, _c = self._deferred_lease_then_drop()
        self.assertEqual(h._configured_capacity, 100.0)
        h.set_capacity(10.0)
        self.assertEqual(h._configured_capacity, 10.0)
        self.assertEqual(h._capacity_mbps, 10.0)

    def test_the_retry_rebuilds_the_plan_for_the_dropped_link(self):
        h, lease, clock = self._deferred_lease_then_drop()
        clock[0] = 5.0
        h.set_capacity(10.0)
        clock[0] = 6.13
        h.runner.commands.clear()
        self.assertTrue(h.sync_lease(lease, 100.0), "the retry should now succeed")
        self.assertEqual(h._current_plan.capacity_mbps, 10.0,
                         "the retry re-applied the start-of-run plan")

    def test_no_class_is_promised_more_than_the_link_has(self):
        h, lease, clock = self._deferred_lease_then_drop()
        clock[0] = 5.0
        h.set_capacity(10.0)
        clock[0] = 6.13
        h.sync_lease(lease, 100.0)
        self.assertLessEqual(sum(h._current_plan.rates.values()), 10.0)

    def test_no_ceiling_is_promised_past_the_link(self):
        h, lease, clock = self._deferred_lease_then_drop()
        clock[0] = 5.0
        h.set_capacity(10.0)
        clock[0] = 6.13
        h.sync_lease(lease, 100.0)
        for v in h._current_plan.rates.values():
            self.assertLessEqual(v, 10.0)

    def test_an_unchanged_lease_still_reapplies_rather_than_going_quiet(self):
        """The fix must not turn the retry into a no-op: that was the original
        bug where class 1:40 was never created at all."""
        h, lease, clock = self._deferred_lease_then_drop()
        clock[0] = 6.13
        self.assertTrue(h.sync_lease(lease, 100.0))
        self.assertIn(TrafficClass.LEASED, h._current_plan.rates)

    def test_an_already_effective_lease_is_still_a_cheap_no_op(self):
        """The fast path matters: enforce() calls this every tick, and rebuilding
        every tick is the loop that destroyed the filters repeatedly."""
        h, lease, clock = self._deferred_lease_then_drop()
        clock[0] = 6.13
        self.assertTrue(h.sync_lease(lease, 100.0))
        h.runner.commands.clear()
        self.assertTrue(h.sync_lease(lease, 100.0))
        self.assertEqual(h.runner.commands, [],
                         "an unchanged, already-applied lease rebuilt the qdisc")


class TestTheAuditRecordsWhatWasApplied(unittest.TestCase):
    """`classes=5` said how many, never which rates.

    Every hypothesis about the lease overshoot had to be checked against a
    separately-timestamped `tc` dump, taken by hand, with a wall clock that did
    not line up with the run's own timeline -- which is how a correct-looking
    story survived several runs. The rate on parent 1:1 is the entire question
    and it belongs in the artefact.
    """

    def _lease_after_drop(self):
        clock = [0.0]
        h = Harness(runner=FakeRunner(auto_readback=True), clock=lambda: clock[0])
        h.reset_for_run()
        h.set_lease(None, 100.0)
        h.apply_system(SystemSpec.ACIQ, 100.0)
        lease = Lease(id="l", target="device", ip="203.0.113.4", weight=0.6)
        h.sync_lease(lease, 100.0)
        clock[0] = 5.0
        h.set_capacity(10.0)
        clock[0] = 6.26
        h.sync_lease(lease, 100.0)
        return h

    def test_a_commit_records_the_applied_rates(self):
        h = self._lease_after_drop()
        commits = [e for e in h.txn.audit if e["event"] == "committed"]
        self.assertTrue(commits[-1].get("applied"),
                        "the audit records a commit with no applied rates")

    def test_the_recorded_parent_rate_is_the_real_one(self):
        h = self._lease_after_drop()
        commits = [e for e in h.txn.audit if e["event"] == "committed"]
        self.assertEqual(commits[-1]["applied"]["1:1"], [10.0, 10.0])

    def test_every_class_is_recorded_with_its_rate_and_ceiling(self):
        h = self._lease_after_drop()
        applied = [e for e in h.txn.audit if e["event"] == "committed"][-1]["applied"]
        self.assertEqual(set(applied), {"1:1", "1:10", "1:20", "1:30", "1:40"})
        for classid, (rate, ceil_m) in applied.items():
            self.assertLessEqual(ceil_m, 10.0,
                                 f"{classid} ceiling exceeds the link")

    def test_a_refused_change_is_not_recorded_as_applied(self):
        h = Harness(runner=FakeRunner(auto_readback=False), clock=lambda: 0.0)
        h.apply_system(SystemSpec.ACIQ, 100.0)
        h.runner.fail_everything = True
        try:
            h.set_capacity(10.0)
        except Exception:
            pass
        for e in h.txn.audit:
            if e["event"] == "committed":
                self.assertNotIn("1:1", e.get("applied") or {},
                                 "a commit with no applied tree")


class TestUnitTestsNeverShellOut(unittest.TestCase):
    """A unit test with a FakeRunner must not read the real kernel.

    Four closed-loop tests failed as root and passed unprivileged after
    `delivered_bytes()` was added, because `BottleneckDropSource` defaults to
    `subprocess.run` and ignored the harness's fake runner. Unprivileged there is
    no `ip` on PATH, so the call raised and returned None; as root it ran for
    real.

    The lesson is not "guard the root path". It is that a test which only
    validates in the weaker environment has not been validated. This test pins
    the property in BOTH environments by making any real subprocess explode --
    so it fails identically whether or not `ip` exists.
    """

    def _explode(self, *a, **kw):
        raise AssertionError(
            "a unit test shelled out to the real system; the FakeRunner was "
            "bypassed. This reproduces the four as-root-only failures.")

    def test_adaptation_never_invokes_a_subprocess(self):
        import subprocess as _sp
        real = _sp.run
        _sp.run = self._explode
        try:
            h = Harness(runner=FakeRunner(auto_readback=True), clock=lambda: 0.0)
            h.adapt_step(counters(rx=0), dt=1.0, now=0.0, link=link())
            h.adapt_step(counters(rx=0, overlimits=9000), dt=1.0, now=1.0,
                         link=link(overlimits=9000))
            cap, changed = h.adapt_step(
                counters(rx=2_500_000, overlimits=18000), dt=1.0, now=10.0,
                link=link(overlimits=18000))
        finally:
            _sp.run = real
        self.assertTrue(changed, "no policy change -- the estimator saw no drop")
        self.assertIsNotNone(cap)

    def test_the_bottleneck_source_is_suppressed_under_a_fake_runner(self):
        h = Harness(runner=FakeRunner(auto_readback=True), clock=lambda: 0.0)
        self.assertIsNone(h._bottleneck_drops(),
                          "a real bottleneck source was built for a fake runner")

    def test_delivered_rate_is_none_without_a_kernel(self):
        """No source means no reading, and no reading means the caller falls
        back to the offered sum rather than to zero."""
        h = Harness(runner=FakeRunner(auto_readback=True), clock=lambda: 0.0)
        self.assertIsNone(h.bottleneck_delivered_mbps(1.0))


class TestCrossRunStateLeaks(unittest.TestCase):
    """Evidence from run 1 must never appear in run 2's report."""

    def test_reset_for_run_clears_the_policy_change_log(self):
        h = harness()
        h.apply_system(SystemSpec.ACIQ, 100.0)
        h.policy_change_log.append({"t": 1.0, "intended_capacity_mbps": 100.0})
        h.policy_changes = 3
        h.reset_for_run()
        self.assertEqual(h.policy_change_log, [],
                         "run 1's policy applications leaked into run 2's "
                         "evidence, making a fresh run look like it had been "
                         "changing policy all along")
        self.assertEqual(h.policy_changes, 0)

    def test_reset_loop_clears_the_bottleneck_byte_counter(self):
        """Run 2's first delta was measured against run 1's counter."""
        h = harness()
        h._prev_delivered_bytes = 123_456_789
        h.reset_loop()
        self.assertFalse(hasattr(h, "_prev_delivered_bytes"),
                         "the bottleneck counter survived the reset; the next "
                         "reading would be a delta against another experiment")

    def test_reset_for_run_clears_lease_and_measurement_state(self):
        h = harness()
        h.last_measurement = object()
        h._lease_in_effect = True
        h.reset_for_run()
        self.assertFalse(h._lease_in_effect)
        self.assertIsNone(h.last_measurement)


class TestBridgeStateAfterFailedApply(unittest.TestCase):
    """A rebuild destroys every filter whether or not the commit succeeded.

    Invalidating only on success left the bridge's slot map claiming filters
    existed after a failed apply had rolled the tree back, so `mark()` no-op'd
    for flows with nothing on the device -- verdicts reported, traffic going
    to the default class.
    """

    def _harness_with_stale_slots(self):
        r = FakeRunner(auto_readback=True)
        h = Harness(runner=r, clock=lambda: 0.0)
        enforcer = h.enable_enforcement(executor=FakeRunner())
        h.apply_system(SystemSpec.ACIQ, 100.0)
        # a flow the bridge believes is installed
        enforcer.bridge.state.slots["flow-sig-1"] = 1
        return h, r

    def test_failed_lease_apply_invalidates_the_bridge(self):
        h, r = self._harness_with_stale_slots()
        h.runner.fail_on = "class add"          # the rebuild will be refused
        h.clock = lambda: 6.0                   # past the shield change window
        lease = Lease(id="l", target="device", ip="203.0.113.4", weight=0.6)
        self.assertFalse(h.sync_lease(lease, 100.0))
        self.assertEqual(h._enforcer.bridge.state.slots, {},
                         "the apply failed after the rebuild, so the old "
                         "filters are gone; the bridge still claimed them")

    def test_deferred_apply_leaves_the_bridge_alone(self):
        """No kernel touch, no churn: a rate-limited apply must not clear
        filters that are still on the device."""
        h, _r = self._harness_with_stale_slots()
        h.clock = lambda: 0.1                   # inside the change window
        lease = Lease(id="l", target="device", ip="203.0.113.4", weight=0.6)
        self.assertFalse(h.sync_lease(lease, 100.0))
        self.assertEqual(h._enforcer.bridge.state.slots, {"flow-sig-1": 1})

    def test_committed_apply_invalidates_the_bridge(self):
        h, _r = self._harness_with_stale_slots()
        h.clock = lambda: 6.0
        lease = Lease(id="l", target="device", ip="203.0.113.4", weight=0.6)
        self.assertTrue(h.sync_lease(lease, 100.0))
        self.assertEqual(h._enforcer.bridge.state.slots, {})
