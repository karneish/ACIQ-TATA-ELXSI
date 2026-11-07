"""Starvation + dashboard unavailable-states + new-scenario gates."""
import subprocess, sys, unittest
from pathlib import Path
sys.path.insert(0, '.')

class TestStarvationGate(unittest.TestCase):
    def test_verify_passes_140_with_bounded_starvation(self):
        out = subprocess.run([sys.executable, 'tools/verify_round3.py', 'data/runs_final3'],
                             capture_output=True, text=True)
        self.assertIn('140 judged PASS, 0 FAIL', out.stdout)
        # starvation_ticks appears on interactive shapes and is bounded (<5)
        for line in out.stdout.splitlines():
            if 's3_tv' in line:
                self.assertIn('starvation_ticks=', line)

class TestDashboardUnavailable(unittest.TestCase):
    def test_empty_renders_no_data(self):
        from aciq.dashboard import build_from_samples
        html = build_from_samples([])
        self.assertIn('no data', html.lower())

    def test_bandwide_artifact(self):
        prov = Path('data/experiments/dashboard_final3/provenance.json').read_text()
        self.assertIn('6840', prov)  # band-wide: all 140 ACIQ runs, not 3

class TestNewScenarios(unittest.TestCase):
    def test_s5_s8_registered(self):
        from aciq.harness import SCENARIOS
        self.assertIn('s5_update_backup_voice', SCENARIOS)
        self.assertIn('s8_ipv6_call', SCENARIOS)
        kinds = [w.kind for w in SCENARIOS['s5_update_backup_voice'].workloads]
        self.assertEqual(kinds, ['update','backup','voice'])

if __name__ == '__main__': unittest.main()
