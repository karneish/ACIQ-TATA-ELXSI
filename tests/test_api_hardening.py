"""Correction API, role separation, replay protection, and TLS."""

from __future__ import annotations

import json
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
import urllib.request
from pathlib import Path

from aciq.api import IntentService, serve
from aciq.corrections import CorrectionStore
from aciq.intent import LeaseBook
from aciq.model import Flow, TrafficClass


class Clock:
    def __init__(self, now: float = 1000.0):
        self.t = now

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


class ServiceCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.path = Path(self._tmp.name) / "corrections.jsonl"
        self.store = CorrectionStore(self.path)
        self.clock = Clock()
        self.svc = IntentService(
            LeaseBook(clock=self.clock),
            corrections=self.store,
            tokens={"op-token": "operator", "view-token": "viewer"},
        )

    def post(self, body, token="op-token", headers=None):
        h = {"authorization": f"Bearer {token}"} if token else {}
        h.update(headers or {})
        return self.svc.handle("POST", "/corrections",
                               json.dumps(body).encode(), headers=h,
                               client="10.0.0.1")

    def correction(self, **kw):
        body = {"src": "10.0.1.2", "dst": "203.0.113.9", "proto": "tcp",
                "dport": 22, "class": "bulk"}
        body.update(kw)
        return body


class TestCorrectionAPI(ServiceCase):
    def test_a_correction_is_recorded_and_listed(self):
        st, body, _ = self.post(self.correction(reason="git clone"))
        self.assertEqual(st, 201)
        self.assertEqual(body["class"], "bulk_transfer")
        self.assertEqual(body["scope"], "port")
        st, listing, _ = self.svc.handle("GET", "/corrections")
        self.assertEqual(st, 200)
        self.assertEqual(len(listing["corrections"]), 1)
        self.assertEqual(listing["corrections"][0]["reason"], "git clone")

    def test_the_correction_changes_the_store_lookup(self):
        self.post(self.correction())
        flow = Flow("10.0.1.2", 40000, "203.0.113.9", 22, "tcp")
        self.assertEqual(self.store.lookup(flow).cls, TrafficClass.BULK)

    def test_a_host_scope_correction_omits_the_port(self):
        st, body, _ = self.post(self.correction(scope="host", dport=None))
        self.assertEqual(st, 201)
        self.assertIsNone(body["dport"])
        self.assertEqual(body["scope"], "host")
        for dport in (22, 443, 8080):
            flow = Flow("10.0.1.2", 40000, "203.0.113.9", dport, "tcp")
            self.assertIsNotNone(self.store.lookup(flow))

    def test_a_port_scope_requires_a_port(self):
        st, _body, _ = self.post(self.correction(dport=None))
        self.assertEqual(st, 400)

    def test_a_bad_class_is_refused(self):
        st, body, _ = self.post(self.correction(**{"class": "banana"}))
        self.assertEqual(st, 400)
        self.assertIn("bulk_transfer", body["error"])

    def test_a_bad_address_is_refused_before_the_store(self):
        for field in ("src", "dst"):
            st, _body, _ = self.post(self.correction(**{field: "not-an-ip"}))
            self.assertEqual(st, 400)

    def test_viewer_cannot_write(self):
        st, _body, _ = self.post(self.correction(), token="view-token")
        self.assertEqual(st, 403)
        self.assertEqual(len(self.store), 0)

    def test_missing_token_cannot_write(self):
        st, _body, _ = self.post(self.correction(), token=None)
        self.assertEqual(st, 401)

    def test_reads_need_no_token(self):
        self.assertEqual(self.svc.handle("GET", "/corrections")[0], 200)

    def test_the_audit_does_not_contain_the_token(self):
        recs = []
        self.svc._audit = recs.append
        self.post(self.correction())
        self.assertNotIn("op-token", json.dumps(recs))
        self.assertEqual(recs[0]["outcome"], "corrected")


class TestReplayProtection(unittest.TestCase):
    def setUp(self):
        self.clock = Clock(1000.0)
        self.svc = IntentService(LeaseBook(clock=self.clock), token="t",
                                 require_replay=True)
        self.body = json.dumps({"target": "device", "ip": "10.0.1.2"}).encode()

    def _post(self, nonce="abcdefgh", ts=1000.0, token="t"):
        return self.svc.handle(
            "POST", "/intent", self.body,
            headers={"authorization": f"Bearer {token}",
                     "x-aciq-timestamp": str(ts),
                     "x-aciq-nonce": nonce},
            client="10.0.0.2")[0]

    def test_a_fresh_request_is_accepted(self):
        self.assertEqual(self._post(), 201)

    def test_the_same_nonce_is_rejected(self):
        self.assertEqual(self._post(), 201)
        self.assertEqual(self._post(), 409)

    def test_a_stale_timestamp_is_rejected(self):
        self.assertEqual(self._post(ts=1.0), 400)

    def test_missing_replay_headers_are_rejected(self):
        st = self.svc.handle(
            "POST", "/intent", self.body,
            headers={"authorization": "Bearer t"}, client="10.0.0.2")[0]
        self.assertEqual(st, 400)

    def test_a_different_nonce_is_accepted(self):
        self.assertEqual(self._post("abcdefgh"), 201)
        self.assertEqual(self._post("ijklmnop"), 201)

    def test_replay_is_not_required_when_disabled(self):
        svc = IntentService(LeaseBook(clock=self.clock), token="t")
        st = svc.handle("POST", "/intent", self.body,
                        headers={"authorization": "Bearer t"})[0]
        self.assertEqual(st, 201)


class TestTLSSocket(unittest.TestCase):
    def setUp(self):
        if shutil.which("openssl") is None:
            self.skipTest("openssl is not installed")
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        d = Path(self._tmp.name)
        self.cert = d / "cert.pem"
        self.key = d / "key.pem"
        subprocess.run(
            ["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes",
             "-keyout", str(self.key), "-out", str(self.cert), "-days", "1",
             "-subj", "/CN=127.0.0.1"],
            check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def test_https_serves_healthz(self):
        httpd = serve(LeaseBook(), host="127.0.0.1", port=0,
                      certfile=str(self.cert), keyfile=str(self.key))
        port = httpd.server_address[1]
        t = threading.Thread(target=httpd.serve_forever, daemon=True)
        t.start()
        try:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            with urllib.request.urlopen(f"https://127.0.0.1:{port}/healthz",
                                        context=ctx, timeout=5) as r:
                self.assertEqual(r.status, 200)
                self.assertTrue(json.loads(r.read())["ok"])
        finally:
            httpd.shutdown()
            httpd.server_close()


if __name__ == "__main__":
    unittest.main()
