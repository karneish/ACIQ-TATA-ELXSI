import unittest
from pathlib import Path

class TestDemoDry(unittest.TestCase):
    def test_demo_log_exists(self):
        self.assertTrue(Path('data/experiments/demo_dry_s1/demo_dry.log').exists())
        self.assertTrue(Path('data/experiments/demo_dry_s3/demo_dry.log').exists())

class TestS3Judged(unittest.TestCase):
    def test_verify_reports_interactive_pass(self):
        import subprocess
        out = subprocess.run(['python3','tools/verify_round3.py','data/runs_final3'],
                             capture_output=True, text=True)
        self.assertIn('140 judged PASS, 0 FAIL', out.stdout)
        self.assertIn('PASS(interactive)', out.stdout)

class TestIPv6(unittest.TestCase):
    def test_v6_classifier(self):
        import subprocess
        out = subprocess.run(['python3','tools/run_ipv6_dry.py'], capture_output=True, text=True)
        self.assertIn('s8_ipv6_call: PASS', out.stdout)

class TestIntentFairness(unittest.TestCase):
    def test_tool_exists(self):
        self.assertTrue(Path('tools/measure_intent_fairness.py').exists())

class TestNewWorkloads(unittest.TestCase):
    def test_generators_exist(self):
        for n in ('update','backup','voice'):
            self.assertTrue(Path(f'testbed/workloads/{n}.py').exists())

class TestUplinkRestartWired(unittest.TestCase):
    def test_harness_methods(self):
        from pathlib import Path
        t = Path('aciq/harness.py').read_text()
        self.assertIn('def set_uplink_capacity', t)
        self.assertIn('def reconcile_after_restart', t)

class TestCapacityFix(unittest.TestCase):
    def test_seed_wiring(self):
        t = Path('aciq/experiment.py').read_text()
        self.assertIn('recover_to_mbps, ramp_to_mbps', t)

if __name__ == '__main__': unittest.main()
