from aciq.restart import describe_applied
from aciq.uplink import uplink_rates
from aciq.ipv6 import ipv6_flow
import unittest

class TestRestartReconciliation(unittest.TestCase):
    def test_describe(self):
        d = describe_applied(True, "qdisc htb 1: root rate 100Mbit")
        self.assertTrue(d['reconciled']); self.assertTrue(d['kernel_tree_present'])

    def test_describe_empty(self):
        d = describe_applied(False, None)
        self.assertFalse(d['kernel_tree_present'])

class TestUplinkShaping(unittest.TestCase):
    def test_clamps(self):
        self.assertEqual(uplink_rates(20, {'bulk_download': 80, 'video_call_voice': 5}, 10)['bulk_download'], 20.0)

class TestIPv6Scenario(unittest.TestCase):
    def test_flow(self):
        f = ipv6_flow('fd00:1::2', 'fd00:2::2', 5000, 443)
        self.assertEqual(f['family'], 'ipv6'); self.assertEqual(f['dport'], 443)

if __name__ == '__main__': unittest.main()
