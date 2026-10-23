"""The emulated link is limited to the scenario's capacity before the run.

Three properties, and they are separate properties:

  * a dry run touches no kernel, so it must not even *ask* for the link to be
    shaped -- `run_experiments.py --dry-run` promises it touches nothing;
  * a real run limits the out-of-band bottleneck to the capacity the scenario
    asked for, BEFORE it reads a single counter, because the estimator's input
    is the bottleneck's own delivered bytes and an unshaped link gives it none;
  * a link limit the kernel refuses is a FAILED run, reported as such, and not
    a run that quietly reports a capacity it never had.

The third is the one that was missing. `capacity_change_applied` defaulted to
True, so a refused limit produced a run that claimed a link capacity the link
never had -- and the estimator, which cannot measure an unlimited link, would
have gone on to report a number for it.

These tests use a `FakeRunner`, so they prove the *wiring*: which command is
issued, in what order, and what the artefact says when it is refused. They do
NOT prove that a real `tc` applies a real limit; that is what the host gate
and the acceptance harness are for, and this environment cannot run either.
"""

import json
import tempfile
import unittest
from pathlib import Path

from aciq.experiment import DryLauncher, ExperimentRunner
from aciq.harness import Harness, SystemSpec
from aciq.metrics import CounterSnapshot
from aciq.txn import FakeRunner

import time as _time


class _NullSource:
    """Empty counter snapshots, so a run never shells out to `tc` to read."""

    def snapshot(self):
        return CounterSnapshot(t=_time.monotonic(), by_class={})


class _LiveishLauncher:
    """Not a DryLauncher, but launches nothing real.

    The shaping call is guarded on the launcher being a DryLauncher, so the
    branch that shapes the link needs a launcher that is not one. This stands
    in for NetnsLauncher: it is not dry, and it spawns nothing.
    """

    def __init__(self):
        self.stopped = False
        self.sources = []
        self.sinks = []

    def spawn_sink(self, kind, port, log_path):
        self.sinks.append((kind, port))

    def spawn_source(self, kind, dst, port, duration, dscp, json_out, log_path,
                     src=None):
        self.sources.append((kind, port))

    def collect(self):
        return []

    def stop(self):
        self.stopped = True


def _shaping_commands(runner: FakeRunner) -> list[tuple[str, ...]]:
    """The commands that LIMIT the link.

    `tc qdisc replace` on the bottleneck device is the only command in the
    tree that replaces a qdisc: the controller's own tree is deleted and
    re-added (`qdisc del` / `qdisc add`), never replaced. So this filter
    selects the shaping operation and nothing else.
    """
    return [c for c in runner.commands if "replace" in c and "qdisc" in c]


class TestTheInitialLinkIsLimited(unittest.TestCase):
    def _run(self, tmp, *, launcher, runner, **kw):
        r = ExperimentRunner(
            launcher=launcher,
            harness=Harness(runner=runner, clock=lambda: 0.0),
            results_dir=Path(tmp), real_time=False, source=_NullSource(), **kw)
        res = r.run("s1_iso_during_call", SystemSpec.ACIQ)
        return r, res

    def _result_json(self, tmp, res):
        p = Path(tmp) / "s1_iso_during_call__aciq__adaptive__seed42" / "result.json"
        self.assertTrue(p.exists(), "the run wrote no result.json")
        return json.loads(p.read_text())

    # ---- the dry run ---------------------------------------------------

    def test_a_dry_run_never_asks_the_kernel_to_shape_the_link(self):
        """The guard is on the launcher, because the ExperimentRunner API does
        not guarantee a fake runner: a caller can hand it a real Harness and a
        DryLauncher, and then this call would shell out to `ip netns exec ...
        tc` in a run that promised to touch nothing."""
        with tempfile.TemporaryDirectory() as d:
            runner = FakeRunner(auto_readback=True)
            r, res = self._run(d, launcher=DryLauncher(), runner=runner)
            self.assertEqual(_shaping_commands(runner), [],
                             "a dry run asked for the link to be shaped: "
                             f"{_shaping_commands(runner)}")
            self.assertIn("dry run", " ".join(res.notes),
                          "the run does not say that it shaped nothing")

    def test_a_dry_run_still_completes_and_records_the_link_it_did_not_limit(self):
        """Skipping the shaping must not fail the run: a dry run is a plan, and
        a plan that cannot be executed is still a plan. But the artefact must
        not claim a link that was never limited."""
        with tempfile.TemporaryDirectory() as d:
            runner = FakeRunner(auto_readback=True)
            _r, res = self._run(d, launcher=DryLauncher(), runner=runner)
            self.assertTrue(res.capacity_change_applied,
                            "a dry run failed because it did not shape a link")
            doc = self._result_json(d, res)
            self.assertTrue(doc["capacity_change_applied"])
            self.assertIn("dry run", " ".join(doc["notes"]))

    # ---- the real run --------------------------------------------------

    def test_a_real_run_limits_the_bottleneck_to_the_scenario_capacity(self):
        with tempfile.TemporaryDirectory() as d:
            runner = FakeRunner(auto_readback=True)
            _r, res = self._run(d, launcher=_LiveishLauncher(), runner=runner)
            cmds = _shaping_commands(runner)
            self.assertEqual(len(cmds), 1,
                             f"the link was shaped {len(cmds)} times: {cmds}")
            cmd = cmds[0]
            self.assertIn("netem", cmd)
            self.assertIn("veth-w", cmd,
                          "the limit was not applied to the bottleneck device")
            self.assertIn("wan", cmd,
                          "the limit was not applied in the wan namespace")
            self.assertIn(f"{res.link_start_mbps:.4f}mbit", cmd,
                          f"the link was limited to the wrong rate: {cmd}")

    def test_the_link_is_limited_before_any_counter_is_read(self):
        """The estimator's input is the bottleneck's own delivered bytes. A
        counter read before the limit is installed sees an unshaped link, and
        no reading taken afterwards can undo that."""
        with tempfile.TemporaryDirectory() as d:
            runner = FakeRunner(auto_readback=True)
            self._run(d, launcher=_LiveishLauncher(), runner=runner)
            shape_at = next(i for i, c in enumerate(runner.commands)
                            if "replace" in c and "qdisc" in c)
            reads_at = [i for i, c in enumerate(runner.commands) if "-s" in c]
            self.assertTrue(reads_at, "the run read no counters at all")
            self.assertLess(shape_at, min(reads_at),
                            "a counter was read before the link was limited")

    def test_the_artefact_records_the_limit_that_was_applied(self):
        with tempfile.TemporaryDirectory() as d:
            runner = FakeRunner(auto_readback=True)
            _r, res = self._run(d, launcher=_LiveishLauncher(), runner=runner)
            self.assertIn(f"{res.link_start_mbps:.4f}mbit", res.bottleneck_state,
                          f"the artefact does not record the limit: "
                          f"{res.bottleneck_state!r}")
            doc = self._result_json(d, res)
            self.assertTrue(doc["capacity_change_applied"])
            self.assertEqual(doc["capacity_change_error"], "")

    # ---- the refused limit ---------------------------------------------

    def test_a_refused_limit_is_a_failed_run_and_says_so(self):
        """The kernel refused the limit, so the link is not at the capacity the
        run was asked for. The artefact must say that, in the field a reader
        checks (`capacity_change_applied`), and not only in prose."""
        with tempfile.TemporaryDirectory() as d:
            runner = FakeRunner(fail_on="qdisc replace", auto_readback=True)
            _r, res = self._run(d, launcher=_LiveishLauncher(), runner=runner)
            self.assertFalse(res.capacity_change_applied,
                             "a refused link limit was reported as applied")
            self.assertTrue(res.capacity_change_error,
                            "the refusal was recorded without a reason")
            self.assertIn("could not be limited", " ".join(res.notes))
            doc = self._result_json(d, res)
            self.assertFalse(doc["capacity_change_applied"])
            self.assertEqual(doc["capacity_change_error"],
                             res.capacity_change_error)

    def test_a_refused_limit_ends_the_run_before_any_traffic_is_measured(self):
        """A run that measured traffic on a link it never limited has measured
        a link that did not exist. It must stop, not continue with a note."""
        with tempfile.TemporaryDirectory() as d:
            runner = FakeRunner(fail_on="qdisc replace", auto_readback=True)
            launcher = _LiveishLauncher()
            _r, res = self._run(d, launcher=launcher, runner=runner)
            self.assertEqual(res.samples, [],
                             "the run kept measuring after the link limit was "
                             "refused")
            self.assertTrue(launcher.stopped,
                            "the launcher was not stopped after the refusal")


if __name__ == "__main__":
    unittest.main()
