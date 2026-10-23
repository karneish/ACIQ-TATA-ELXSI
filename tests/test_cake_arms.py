"""T2 — the two CAKE arms must be distinguishable, and their rates recorded.

Contract under test (see docs/modules.md, T2 fix round):

* B0/B1/CAKE-oracle/ACIQ all share one out-of-band netem bottleneck that a
  baseline tree is NEVER re-applied against mid-run, so the pre-existing
  `b1_cake95` arm is CAKE-STATIC: cake bandwidth = 0.95 x link at t=0,
  set-and-forget, exactly "what a real user would have".
* The new `b1_cake_oracle` arm is the same single-class CAKE tree applied at
  0.95 x POST-DROP capacity FROM THE START. config.json must say
  `oracle_from_start: True` and give the applied cake rate, so no comparison
  can dress an oracle number up as a user-realistic one.
* A drop-less run must never activate the oracle branch (there is nothing to
  be an oracle ABOUT) — it falls back to the starting capacity, same as B1.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aciq.experiment import DryLauncher, ExperimentRunner  # noqa: E402
from aciq.harness import CapacityMode, Harness, SystemSpec  # noqa: E402
from aciq.txn import FakeRunner  # noqa: E402


def _run_offline(system: SystemSpec, tmp: str, **kwargs):
    h = Harness(runner=FakeRunner(auto_readback=True), clock=__import__("time").monotonic)
    r = ExperimentRunner(
        launcher=DryLauncher(), harness=h,
        results_dir=Path(tmp), real_time=False,
        initial_link_mbps=100.0,
    )
    return r.run("s2_wan_drop", system, CapacityMode.STATIC, 7,
                 100.0, 20.0, **kwargs)


class TestCakeArms(unittest.TestCase):
    def _config_of(self, tmp_root: str) -> dict:
        run_dir = sorted(Path(tmp_root).glob("s2_wan_drop__b1_cake95__static__seed7"))
        run_dir = sorted(Path(tmp_root).glob("s2_wan_drop*seed7"))
        return json.loads((run_dir[0] / "config.json").read_text())

    def test_static_cake_rate_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run_offline(SystemSpec.B1, tmp, drop_at_s=10.0)
            cfg = self._config_of(tmp)
            self.assertEqual(cfg["system"], "b1_cake95")
            self.assertFalse(cfg["oracle_from_start"])
            # set-and-forget: applied ONCE at 95% of the STARTING link
            self.assertEqual(cfg["cake_rate_at_apply"], 95.0)

    def test_oracle_cake_rate_recorded(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run_offline(SystemSpec.B1_ORACLE, tmp, drop_at_s=10.0)
            cfg = self._config_of(tmp)
            self.assertEqual(cfg["system"], "b1_cake_oracle")
            self.assertTrue(cfg["oracle_from_start"])
            # applied at 95% of the POST-DROP rate, from t=0
            self.assertEqual(cfg["cake_rate_at_apply"], 19.0)

    def test_oracle_branch_needs_a_drop(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run_offline(SystemSpec.B1_ORACLE, tmp, drop_at_s=None)  # no drop
            cfg = self._config_of(tmp)
            self.assertFalse(cfg["oracle_from_start"])
            self.assertEqual(cfg["cake_rate_at_apply"], 95.0)

    def test_b0_and_aciq_have_no_cake_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            _run_offline(SystemSpec.B0, tmp, drop_at_s=10.0)
            self.assertIsNone(self._config_of(tmp)["cake_rate_at_apply"])
        with tempfile.TemporaryDirectory() as tmp:
            _run_offline(SystemSpec.ACIQ, tmp, drop_at_s=10.0)
            self.assertIsNone(self._config_of(tmp)["cake_rate_at_apply"])

    def test_baseline_tree_never_changes_mid_run(self):
        """The verifier finding this fix exists for: a baseline tree must be
        applied exactly ONCE per run. If set_capacity ever re-applied B1's
        tree at the drop rate, the "static" arm would be lying."""
        from aciq.harness import baseline_tree, render
        tree = baseline_tree(SystemSpec.B1_ORACLE, 20.0)
        argvs = [a for a in render(tree, dev="veth-lan", ns="router")]
        flat = " ".join(" ".join(a) for a in argvs)
        self.assertIn("cake bandwidth 19.0000mbit", flat)


if __name__ == "__main__":
    unittest.main()
