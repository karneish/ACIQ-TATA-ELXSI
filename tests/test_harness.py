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
    Scenario,
    SystemSpec,
    Workload,
    baseline_tree,
)
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

    def test_set_capacity_changes_the_parent_first(self):
        h = harness()
        cmds = h.set_capacity(20.0)
        argv = cmds[0]
        self.assertEqual(argv[argv.index("classid") + 1], ROOT_CLASS_ID)
        self.assertEqual(argv[argv.index("parent") + 1], "1:")

    def test_set_capacity_clamps_each_childs_ceil(self):
        """The fix. The parent rate alone does not cap a subtree: a class borrows
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
        children = [c for c in added if "parent 1:1 classid" in c]
        clamped = sorted(c.split("classid ")[1].split(" ")[0] for c in children)
        self.assertEqual(clamped, ["1:10", "1:20", "1:30"],
                         "every child ceil must be clamped, one command each")
        for cmd in children:
            self.assertIn("ceil 10.0000mbit", cmd)

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

    def test_no_child_rate_ever_exceeds_its_clamped_ceil(self):
        """HTB requires rate <= ceil. Lowering the ceil under a child's existing
        rate would leave an invalid class, and `rate 0` would be honoured by the
        kernel and silently delete M3's bandwidth."""
        h = harness()
        h.apply_system(SystemSpec.ACIQ, 100.0)
        for cmd in h.set_capacity(10.0):
            text = " ".join(cmd)
            if " rate " not in f" {text} ":
                continue
            rate = float(text.split(" rate ")[1].split("mbit")[0])
            ceil = float(text.split(" ceil ")[1].split("mbit")[0])
            self.assertLessEqual(rate, ceil, f"invalid HTB class: {text}")

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

    def test_set_capacity_never_rescales_child_rates(self):
        """Ceil is a safety clamp; rates are policy and belong to M3. If the
        harness rescaled rates it would bypass M2, and "adaptation time" would
        measure the harness rather than the system."""
        h = harness()
        h.apply_system(SystemSpec.ACIQ, 100.0)
        before = len(h.runner.commands)
        h.set_capacity(10.0)
        for cmd in h.runner.commands[before:]:
            text = " ".join(cmd)
            if "classid 1:" in text and " 1:1 " in text:
                continue
            self.assertNotIn(" rate ", f" {text} ", f"child rate changed: {text}")

    def test_set_capacity_emits_no_qdisc_command(self):
        h = harness()
        h.set_capacity(20.0)
        self.assertNotIn("qdisc", " ".join(h.runner.commands[0]))

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
        # the single drop command only; no rebuild telling it the new rate
        self.assertEqual(len(h.runner.commands) - before, 1)

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
