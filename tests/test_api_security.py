"""Security tests for the M7 intent API.

§14. Everything here is a real assertion about the real handler -- no mocks of
the policy layer, because the point is that a rejected request never reaches the
lease book.

The deployment model this enforces: **loopback by default, and a token is
required for anything else.** That restriction is enforced at startup, not
documented and hoped for.
"""

from __future__ import annotations

import json
import unittest
import urllib.error
import urllib.request

from aciq.api import (
    LOOPBACK_HOSTS,
    RATE_LIMIT_WRITES,
    IntentService,
    check_bind,
    serve,
)
from aciq.intent import LeaseBook


def _service(**kw):
    return IntentService(LeaseBook(), **kw)


class TestBindPolicy(unittest.TestCase):
    """§14: enforce the restriction rather than merely documenting it."""

    def test_loopback_is_allowed_without_a_token(self):
        for h in LOOPBACK_HOSTS:
            check_bind(h, None)          # must not raise

    def test_a_non_loopback_bind_without_a_token_is_refused(self):
        for h in ("0.0.0.0", "192.168.1.10", "::"):
            with self.assertRaises(ValueError, msg=h):
                check_bind(h, None)

    def test_a_non_loopback_bind_with_a_token_is_allowed(self):
        check_bind("0.0.0.0", "s3cret")

    def test_the_error_explains_the_fix(self):
        with self.assertRaises(ValueError) as e:
            check_bind("0.0.0.0", None)
        msg = str(e.exception)
        self.assertIn("ACIQ_API_TOKEN", msg)
        self.assertIn("127.0.0.1", msg)

    def test_serve_refuses_rather_than_warns(self):
        """A warning in a log nobody reads is not a control."""
        with self.assertRaises(ValueError):
            serve(LeaseBook(), host="0.0.0.0", port=0, token=None)


class TestAuthentication(unittest.TestCase):
    def test_a_write_without_a_token_is_rejected(self):
        s = _service(token="s3cret")
        st, _b, _c = s.handle("POST", "/intent",
                              body=json.dumps({"target": "device",
                                               "ip": "10.0.1.2"}).encode())
        self.assertEqual(st, 401)

    def test_a_rejected_request_does_not_create_a_lease(self):
        s = _service(token="s3cret")
        s.handle("POST", "/intent",
                 body=json.dumps({"target": "device", "ip": "10.0.1.2"}).encode())
        self.assertEqual(len(s.book.active()), 0)

    def test_the_correct_token_is_accepted(self):
        s = _service(token="s3cret")
        st, _b, _c = s.handle("POST", "/intent",
                              body=json.dumps({"target": "device",
                                               "ip": "10.0.1.2"}).encode(),
                              headers={"authorization": "Bearer s3cret"})
        self.assertEqual(st, 201)

    def test_a_wrong_token_is_rejected(self):
        s = _service(token="s3cret")
        st, _b, _c = s.handle("POST", "/intent", body=b"{}",
                              headers={"authorization": "Bearer wrong"})
        self.assertEqual(st, 401)

    def test_a_prefix_of_the_token_is_rejected(self):
        """Not a constant-time shortcut, but a correct prefix check: a shorter
        token must not pass."""
        s = _service(token="s3cret")
        st, _b, _c = s.handle("POST", "/intent", body=b"{}",
                              headers={"authorization": "Bearer s3cre"})
        self.assertEqual(st, 401)

    def test_reads_are_not_authenticated(self):
        """A dashboard on loopback must work without a token, or it is useless."""
        s = _service(token="s3cret")
        self.assertEqual(s.handle("GET", "/")[0], 200)
        self.assertEqual(s.handle("GET", "/status")[0], 200)
        self.assertEqual(s.handle("GET", "/intent")[0], 200)

    def test_delete_also_requires_the_token(self):
        s = _service(token="s3cret")
        s.handle("POST", "/intent",
                 body=json.dumps({"target": "device", "ip": "10.0.1.2"}).encode(),
                 headers={"authorization": "Bearer s3cret"})
        lease_id = s.book.active()[0].id
        self.assertEqual(s.handle("DELETE", f"/intent/{lease_id}")[0], 401)
        self.assertEqual(len(s.book.active()), 1, "an unauthorised DELETE worked")
        self.assertEqual(s.handle("DELETE", f"/intent/{lease_id}",
                                  headers={"authorization": "Bearer s3cret"})[0], 200)


class TestRateLimiting(unittest.TestCase):
    def test_writes_are_capped_per_client(self):
        s = _service()
        body = json.dumps({"target": "device", "ip": "10.0.1.2"}).encode()
        codes = [s.handle("POST", "/intent", body, client="1.2.3.4")[0]
                 for _ in range(RATE_LIMIT_WRITES + 5)]
        self.assertEqual(codes.count(201), RATE_LIMIT_WRITES)
        self.assertEqual(codes.count(429), 5)

    def test_the_limit_is_per_client(self):
        s = _service()
        body = json.dumps({"target": "device", "ip": "10.0.1.2"}).encode()
        for _ in range(RATE_LIMIT_WRITES + 2):
            s.handle("POST", "/intent", body, client="1.1.1.1")
        self.assertEqual(s.handle("POST", "/intent", body, client="2.2.2.2")[0], 201)

    def test_reads_are_never_throttled(self):
        """The dashboard polls every two seconds; throttling reads would break it."""
        s = _service()
        for _ in range(RATE_LIMIT_WRITES * 3):
            self.assertEqual(s.handle("GET", "/status", client="1.2.3.4")[0], 200)

    def test_a_throttled_request_creates_nothing(self):
        s = _service()
        # Distinct addresses: the book replaces the previous lease for the same
        # scope, so reusing one IP would leave a single active lease and the
        # assertion would pass for the wrong reason.
        for i in range(RATE_LIMIT_WRITES + 3):
            body = json.dumps({"target": "device",
                               "ip": f"10.0.1.{i}"}).encode()
            s.handle("POST", "/intent", body, client="9.9.9.9")
        self.assertEqual(len(s.book.active()), RATE_LIMIT_WRITES)

    def test_the_client_table_cannot_grow_without_bound(self):
        """An unbounded dict keyed by client address is itself a memory leak.

        Time-based pruning does not catch this on its own: under a fixed clock
        nothing ever expires, so the table grows regardless. The first version
        of the limiter pruned only by age and failed this test at 1200 entries.
        """
        from aciq.api import MAX_RATE_CLIENTS
        s = _service()
        for i in range(1400):
            body = json.dumps({"target": "device",
                               "ip": f"10.0.{i // 256}.{i % 256}"}).encode()
            s.handle("POST", "/intent", body, client=f"10.9.{i // 256}.{i % 256}")
        self.assertLessEqual(len(s._rate), MAX_RATE_CLIENTS)


class TestAudit(unittest.TestCase):
    def test_a_created_lease_is_audited(self):
        recs = []
        s = _service(audit=recs.append)
        s.handle("POST", "/intent",
                 body=json.dumps({"target": "device", "ip": "10.0.1.2"}).encode(),
                 client="5.5.5.5")
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]["outcome"], "created")
        self.assertEqual(recs[0]["client"], "5.5.5.5")
        self.assertEqual(recs[0]["ip"], "10.0.1.2")

    def test_a_rejected_request_is_audited(self):
        recs = []
        s = _service(audit=recs.append, token="t")
        s.handle("POST", "/intent", b"{}", client="6.6.6.6")
        self.assertEqual(recs[0]["outcome"], "unauthorised")

    def test_a_throttled_request_is_audited(self):
        recs = []
        s = _service(audit=recs.append)
        body = json.dumps({"target": "device", "ip": "10.0.1.2"}).encode()
        for _ in range(RATE_LIMIT_WRITES + 1):
            s.handle("POST", "/intent", body, client="7.7.7.7")
        self.assertIn("rate_limited", [r["outcome"] for r in recs])

    def test_the_token_is_never_audited(self):
        """A log line containing the bearer token turns the log into a credential
        store."""
        recs = []
        s = _service(audit=recs.append, token="TOPSECRET")
        s.handle("POST", "/intent", b"{}",
                 headers={"authorization": "Bearer TOPSECRET"}, client="8.8.8.8")
        self.assertNotIn("TOPSECRET", json.dumps(recs))


class TestOverTheWire(unittest.TestCase):
    """The socket path, on port 0, loopback only."""

    @classmethod
    def setUpClass(cls):
        cls.srv = serve(LeaseBook(), host="127.0.0.1", port=0, token=None,
                        verbose=False)
        cls.port = cls.srv.server_address[1]
        import threading
        cls.t = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.t.start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def _post(self, payload, headers=None):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/intent",
            data=json.dumps(payload).encode(), method="POST",
            headers=headers or {})
        try:
            with urllib.request.urlopen(req, timeout=5) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_a_local_write_succeeds_without_a_token(self):
        st, body = self._post({"target": "device", "ip": "10.0.1.2"})
        self.assertEqual(st, 201)
        self.assertIn("id", body)

    def test_an_oversized_body_is_refused(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/intent",
            data=json.dumps({"target": "device", "ip": "10.0.1.2",
                             "pad": "x" * 200_000}).encode(), method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
            self.fail("a 200 kB body was accepted")
        except urllib.error.HTTPError as e:
            self.assertIn(e.code, (413, 400))

    def test_malformed_json_is_a_400_not_a_500(self):
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/intent",
            data=b"{not json", method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
            self.fail("malformed JSON was accepted")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)

    def test_nan_weight_is_refused(self):
        """float('nan') survives `float()` and fails every comparison against
        it, producing a plan nothing can be compared to."""
        req = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/intent",
            data=b'{"target":"device","ip":"10.0.1.2","weight":NaN}',
            method="POST")
        try:
            urllib.request.urlopen(req, timeout=5)
            self.fail("a NaN weight was accepted")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 400)

    def test_an_unknown_route_is_a_404(self):
        try:
            urllib.request.urlopen(
                f"http://127.0.0.1:{self.port}/../../etc/passwd", timeout=5)
            self.fail("a traversal path was served")
        except urllib.error.HTTPError as e:
            self.assertEqual(e.code, 404)

    def test_get_cannot_reach_a_write_route(self):
        st, _b, _c = _service().handle("GET", "/intent/l-1")
        self.assertEqual(st, 404)


if __name__ == "__main__":
    unittest.main()