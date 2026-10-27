from __future__ import annotations

import json
import unittest

from aciq.api import IntentService
from aciq.identity import DeviceRegistry
from aciq.intent import LeaseBook


class TestDeviceIdentity(unittest.TestCase):
    def setUp(self):
        self.reg = DeviceRegistry()
        self.reg.upsert("AA:BB:CC:DD:EE:FF", ip="10.0.1.5", hostname="tv")
        self.svc = IntentService(LeaseBook(), devices=self.reg, token="t")

    def _post(self, body):
        return self.svc.handle("POST", "/intent", json.dumps(body).encode(),
                               headers={"authorization": "Bearer t"},
                               client="10.0.0.1")

    def test_resolve_ip_from_mac(self):
        st, body, _ = self._post({"target": "device", "mac": "aa:bb:cc:dd:ee:ff"})
        self.assertEqual(st, 201)
        self.assertEqual(body["ip"], "10.0.1.5")

    def test_a_wrong_ip_for_a_mac_is_rejected(self):
        st, body, _ = self._post({"target": "device", "mac": "aa:bb:cc:dd:ee:ff",
                                  "ip": "10.0.1.9"})
        self.assertEqual(st, 409)
        self.assertIn("does not match", body["error"])

    def test_unknown_mac_is_rejected(self):
        st, body, _ = self._post({"target": "device", "mac": "11:22:33:44:55:66"})
        self.assertEqual(st, 400)

    def test_list_devices(self):
        st, body, _ = self.svc.handle("GET", "/devices",
                                       headers={"authorization": "Bearer t"})
        self.assertEqual(st, 200)
        self.assertEqual(body["devices"][0]["mac"], "aa:bb:cc:dd:ee:ff")
        self.assertEqual(body["devices"][0]["hostname"], "tv")

    def test_mac_only_on_device_target(self):
        st, body, _ = self._post({"target": "flow", "mac": "aa:bb:cc:dd:ee:ff",
                                  "flow": "10.0.1.2:1->10.0.1.3:80"})
        self.assertEqual(st, 400)


if __name__ == "__main__":
    unittest.main()
