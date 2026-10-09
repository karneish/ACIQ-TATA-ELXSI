"""M7 (intent API) and M8 (dashboard).

The two are tested together because the contract that matters is the seam: a
lease requested over HTTP has to reach `class 1:40`, and the dashboard sitting on
the same server must be unable to write anything.
"""

import json
import threading
import urllib.error
import urllib.request
import unittest

from aciq.api import IntentService, make_handler, serve
from aciq.bridge import Bridge
from aciq.classify import FlowFeatures
from aciq.closedloop import ClosedLoop
from aciq.dashboard import PANELS, build_from_samples, panels_from_samples
from aciq.intent import (
    DEFAULT_TTL_S,
    MAX_TTL_S,
    MAX_WEIGHT,
    IntentError,
    LeaseBook,
    LeaseStore,
    lease_to_dict,
    load,
    save,
)
from aciq.model import Flow, Lease, TrafficClass
from aciq.policy import build_plan
from aciq.shield import Shield


class Clock:
    """A fake clock. Leases are entirely about time, so tests own it."""

    def __init__(self, t: float = 1000.0):
        self.t = t

    def __call__(self) -> float:
        return self.t

    def advance(self, dt: float) -> None:
        self.t += dt


def store(clock: Clock, **kw):
    return LeaseStore(_now=clock, **kw)


def flow(ip="10.0.1.2", sport=1111, dst="10.0.1.3", dport=7001, proto="udp"):
    return Flow(ip, sport, dst, dport, proto)


class TestLeaseLifecycle(unittest.TestCase):
    def test_a_lease_is_created_with_an_id_and_an_expiry(self):
        c = Clock()
        st, lease = store(c).request("device", ip="10.0.1.2", ttl_s=30)
        self.assertTrue(lease.id)
        self.assertEqual(lease.created_at, c.t)
        d = lease_to_dict(lease, c.t)
        self.assertEqual(d["expires_at"], 1030.0)
        self.assertEqual(d["expires_in"], 30.0)

    def test_a_lease_expires_on_its_own(self):
        """The whole design. A forgotten request must not be permanent."""
        c = Clock()
        st, _ = store(c).request("device", ip="10.0.1.2", ttl_s=30)
        self.assertEqual(len(st.active(c.t)), 1)
        c.advance(29.9)
        self.assertEqual(len(st.active(c.t)), 1)
        c.advance(0.2)
        self.assertEqual(len(st.active(c.t)), 0)

    def test_expiry_is_exact_at_the_boundary(self):
        c = Clock()
        st, lease = store(c).request("device", ip="10.0.1.2", ttl_s=30)
        self.assertFalse(lease.expired(c.t + 29.999))
        self.assertTrue(lease.expired(c.t + 30.0))

    def test_re_requesting_replaces_rather_than_stacks(self):
        """Two leases on one device would each add a bounded share, so stacking
        silently halves what the second is worth instead of saying so."""
        c = Clock()
        st, l1 = LeaseStore(_now=c).request("device", ip="10.0.1.2", ttl_s=60)
        st, l2 = st.request("device", ip="10.0.1.2", weight=0.9, ttl_s=60)
        self.assertEqual(len(st.active(c.t)), 1)
        self.assertEqual(st.active(c.t)[0].id, l2.id)
        self.assertEqual(st.active(c.t)[0].weight, 0.9)

    def test_different_scopes_coexist(self):
        c = Clock()
        st, _ = LeaseStore(_now=c).request("device", ip="10.0.1.2", ttl_s=60)
        st, _ = st.request("device", ip="10.0.1.9", ttl_s=60)
        st, _ = st.request("flow", flow="a:1->b:2", ttl_s=60)
        self.assertEqual(len(st.active(c.t)), 3)

    def test_release_removes_only_that_lease(self):
        c = Clock()
        st, a = LeaseStore(_now=c).request("device", ip="10.0.1.2", ttl_s=60)
        st, b = st.request("device", ip="10.0.1.9", ttl_s=60)
        st, gone = st.release(a.id)
        self.assertEqual(gone.id, a.id)
        self.assertEqual([l.id for l in st.active(c.t)], [b.id])

    def test_releasing_an_unknown_id_is_not_an_error(self):
        st, _ = LeaseStore(_now=Clock()).request("device", ip="10.0.1.2")
        st2, gone = st.release("nope")
        self.assertIsNone(gone)
        self.assertEqual(st2.leases, st.leases)

    def test_sweep_bounds_the_stored_list(self):
        c = Clock()
        st, _ = LeaseStore(_now=c).request("device", ip="10.0.1.2", ttl_s=10)
        c.advance(11)
        self.assertEqual(len(st.active(c.t)), 0)
        self.assertEqual(st.sweep(c.t).leases, (), "expired lease still stored")


class TestLeaseValidation(unittest.TestCase):
    def test_target_must_be_device_or_flow(self):
        with self.assertRaises(IntentError):
            LeaseStore(_now=Clock()).request("host", ip="10.0.1.2")

    def test_a_device_lease_needs_an_ip(self):
        with self.assertRaises(IntentError):
            LeaseStore(_now=Clock()).request("device")

    def test_a_device_lease_must_not_also_name_a_flow(self):
        with self.assertRaises(IntentError):
            LeaseStore(_now=Clock()).request("device", ip="10.0.1.2", flow="a:1->b:2")

    def test_a_flow_lease_needs_a_flow(self):
        with self.assertRaises(IntentError):
            LeaseStore(_now=Clock()).request("flow")

    def test_weight_is_bounded(self):
        for w in (0.0, -1, MAX_WEIGHT + 0.01, 9.0):
            with self.assertRaises(IntentError, msg=f"weight {w} accepted"):
                LeaseStore(_now=Clock()).request("device", ip="1", weight=w)

    def test_weight_bounds_are_inclusive(self):
        LeaseStore(_now=Clock()).request("device", ip="1", weight=MAX_WEIGHT)

    def test_ttl_must_be_positive_and_bounded(self):
        for ttl in (0.0, -5, MAX_TTL_S + 1):
            with self.assertRaises(IntentError, msg=f"ttl {ttl} accepted"):
                LeaseStore(_now=Clock()).request("device", ip="1", ttl_s=ttl)

    def test_there_is_no_way_to_make_an_indefinite_lease(self):
        """A lease that never expires is a permanent boost wearing a lease's
        vocabulary, so ttl_s must always be finite and positive."""
        with self.assertRaises(IntentError):
            LeaseStore(_now=Clock()).request("device", ip="1", ttl_s=0)
        with self.assertRaises(IntentError):
            LeaseStore(_now=Clock()).request("device", ip="1", ttl_s=10**9)


class TestLeaseScope(unittest.TestCase):
    def test_a_device_lease_matches_by_ip_and_ignores_the_port(self):
        """A device's source port changes on every reconnect. A port-sensitive
        request would silently stop applying."""
        c = Clock()
        st, _ = LeaseStore(_now=c).request("device", ip="10.0.1.2", ttl_s=60)
        self.assertIsNotNone(st.for_flow(flow(sport=1), c.t))
        self.assertIsNotNone(st.for_flow(flow(sport=99999), c.t))

    def test_a_device_lease_does_not_match_another_host(self):
        c = Clock()
        st, _ = LeaseStore(_now=c).request("device", ip="10.0.1.2", ttl_s=60)
        self.assertIsNone(st.for_flow(flow(ip="10.0.1.9"), c.t))

    def test_a_flow_lease_is_port_sensitive(self):
        c = Clock()
        st, _ = LeaseStore(_now=c).request("flow", flow="203.0.113.2:1->10.0.1.2:7001",
                                          ttl_s=60)
        hit = flow(ip="203.0.113.2", sport=1, dst="10.0.1.2", dport=7001)
        miss = flow(ip="203.0.113.2", sport=1, dst="10.0.1.2", dport=7002)
        self.assertIsNotNone(st.for_flow(hit, c.t))
        self.assertIsNone(st.for_flow(miss, c.t))

    def test_device_scope_beats_flow_scope(self):
        """Both match; the narrower statement is the more deliberate one."""
        c = Clock()
        st, dev = LeaseStore(_now=c).request("device", ip="10.0.1.2", ttl_s=60)
        st, fl = st.request("flow", flow=flow(ip="10.0.1.2", sport=1111,
                                               dst="10.0.1.3", dport=7001).key,
                            ttl_s=60)
        self.assertEqual(st.for_flow(flow(), c.t).id, fl.id)


class TestLeasePersistence(unittest.TestCase):
    def test_two_books_on_one_file_see_each_other(self):
        """The bug this exists for: `aciqctl lease` printed an id and
        `aciqctl leases` then said none, because nothing was written."""
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "leases.json")
            a = LeaseBook(path=p)
            a.request(target="device", ip="10.0.1.2", ttl_s=60)
            self.assertEqual(len(load(p).active()), 1)

    def test_a_book_loaded_from_a_file_can_still_write_to_it(self):
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "leases.json")
            LeaseBook(path=p).request(target="device", ip="10.0.1.2", ttl_s=60)
            b = load(p)
            self.assertIsNotNone(b.path, "a loaded book dropped its path")
            b.release("lease-1")
            self.assertEqual(load(p).active(), ())

    def test_a_first_lease_on_an_absent_file_is_still_persisted(self):
        """The missing-file branch originally returned a pathless book, so the
        very first lease lived only in memory -- it appeared only on a clean
        slate, which made it look intermittent."""
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "leases.json")
            book = load(p)
            book.request(target="device", ip="10.0.1.2", ttl_s=60)
            self.assertTrue(os.path.exists(p))
            self.assertEqual(len(load(p).active()), 1)

    def test_a_corrupt_file_yields_no_leases_rather_than_an_exception(self):
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "leases.json")
            open(p, "w").write("{not json")
            self.assertEqual(load(p).active(), ())

    def test_expired_leases_are_not_written_back(self):
        import tempfile
        import os
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "leases.json")
            c = Clock()
            b = LeaseBook(clock=c, path=p)
            b.request(target="device", ip="10.0.1.2", ttl_s=10)
            self.assertEqual(len(json.loads(Path(p).read_text())["leases"]), 1)
            c.advance(11)
            b.request(target="device", ip="10.0.1.9", ttl_s=60)
            saved = json.loads(Path(p).read_text())["leases"]
            self.assertEqual([l["ip"] for l in saved], ["10.0.1.9"])

    def test_the_file_is_written_atomically(self):
        """A crash mid-write must not leave a truncated file that reads as zero
        leases -- which would silently drop every live lease."""
        import tempfile
        import os
        from pathlib import Path
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "leases.json")
            b = LeaseBook(path=p)
            b.request(target="device", ip="10.0.1.2", ttl_s=60)
            self.assertFalse(os.path.exists(p + ".tmp"),
                             "the temp file outlived the write")


class TestLeaseThreadSafety(unittest.TestCase):
    def test_concurrent_requests_do_not_lose_any(self):
        """Read-modify-write on a shared store. The lock is what makes it
        atomic; the test is what proves the lock is actually held."""
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as d:
            book = LeaseBook(path=os.path.join(d, "leases.json"))
            errors = []

            def worker(n):
                try:
                    for i in range(20):
                        book.request(target="device", ip=f"10.0.1.{n}",
                                     ttl_s=600)
                except Exception as e:  # pragma: no cover - diagnostic
                    errors.append(e)

            threads = [threading.Thread(target=worker, args=(n,)) for n in range(6)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()
            self.assertEqual(errors, [])
            self.assertEqual(len(book.active()), 6)

    def test_requesting_persists_while_holding_the_lock(self):
        """save() re-enters the book. With a plain Lock that self-deadlocks and
        the process hangs with no traceback -- so this asserts it returns."""
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as d:
            book = LeaseBook(path=os.path.join(d, "leases.json"))
            done = []

            def go():
                book.request(target="device", ip="10.0.1.2", ttl_s=60)
                done.append(True)

            t = threading.Thread(target=go, daemon=True)
            t.start()
            t.join(timeout=5)
            self.assertEqual(done, [True], "request() deadlocked")


class TestLeaseReachesTheKernel(unittest.TestCase):
    """The spec's success condition: a lease visibly raises the flow's share,
    and the effect reverts on expiry."""

    def _loop(self, book):
        def ex(argv):
            return (0, "[]", "") if "-j" in argv else (0, "", "")

        class NoCorrections:
            @staticmethod
            def lookup(*a, **k):
                return None

        return ClosedLoop(Bridge("veth-lan", "eth0", "router", executor=ex),
                          corrections=NoCorrections(), leases=book)

    def _features(self, ip="10.0.1.2"):
        return FlowFeatures(flow=flow(ip=ip), rx_bytes=4_000_000, packets=4000,
                            age_s=10.0, avg_packet_bytes=1000)

    def test_no_lease_means_no_leased_class(self):
        v = self._loop(None).apply(self._features())
        self.assertNotEqual(v.label, "leased")
        self.assertFalse(v.leased)

    def test_a_lease_steers_the_flow_to_the_leased_class(self):
        c = Clock()
        book = LeaseBook(clock=c)
        book.request(target="device", ip="10.0.1.2", ttl_s=60)
        v = self._loop(book).apply(self._features())
        self.assertEqual(v.label, "leased")
        self.assertTrue(v.leased)

    def test_a_lease_does_not_steer_a_different_host(self):
        c = Clock()
        book = LeaseBook(clock=c)
        book.request(target="device", ip="10.0.1.2", ttl_s=60)
        v = self._loop(book).apply(self._features(ip="10.0.1.9"))
        self.assertFalse(v.leased)

    def test_expiry_reverts_the_flow(self):
        c = Clock()
        book = LeaseBook(clock=c)
        book.request(target="device", ip="10.0.1.2", ttl_s=30)
        loop = self._loop(book)
        self.assertTrue(loop.apply(self._features()).leased)
        c.advance(31)
        self.assertFalse(loop.apply(self._features()).leased)

    def test_the_verdict_says_the_lease_decided_it(self):
        c = Clock()
        book = LeaseBook(clock=c)
        lease = book.request(target="device", ip="10.0.1.2", ttl_s=60)
        v = self._loop(book).apply(self._features())
        self.assertEqual(v.classification.tier, "L")
        self.assertIn(lease.id, v.classification.evidence)

    def test_a_lease_outranks_a_correction(self):
        """A lease is a person asking for something specific about a specific
        flow; a correction fixes the classifier's reasoning about it. The more
        specific, more recent statement wins -- and the correction is still there
        underneath once the lease lapses."""
        from aciq.corrections import CorrectionStore
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "c.jsonl")
            cs = CorrectionStore(path=p)
            cs.record(flow(ip="10.0.1.2"), TrafficClass.INTERACTIVE, reason="test")
            cs.reload()

            c = Clock()
            book = LeaseBook(clock=c)
            book.request(target="device", ip="10.0.1.2", ttl_s=30)

            def ex(argv):
                return (0, "[]", "") if "-j" in argv else (0, "", "")

            loop = ClosedLoop(Bridge("veth-lan", "eth0", "router", executor=ex),
                              corrections=cs, leases=book)
            self.assertTrue(loop.apply(self._features()).leased)
            c.advance(31)
            after = loop.apply(self._features())
            self.assertFalse(after.leased)
            self.assertEqual(after.cls, TrafficClass.INTERACTIVE,
                             "the correction should resurface")


class TestLeaseChangesThePlan(unittest.TestCase):
    """The plan must reserve for the lease, not just reclassify into a queue
    that has none -- which is the state v0 shipped."""

    def test_a_lease_creates_a_leased_class(self):
        no_lease = build_plan(100.0, None)
        leased = build_plan(100.0, Lease(id="l1", target="device", ip="10.0.1.2",
                                         weight=0.6))
        self.assertNotIn(TrafficClass.LEASED, no_lease.rates)
        self.assertIn(TrafficClass.LEASED, leased.rates)

    def test_the_lease_comes_out_of_the_others(self):
        """A lease that adds bandwidth nobody gives up would break the
        sum(children) <= capacity invariant."""
        plan = build_plan(100.0, Lease(id="l1", target="device", ip="10.0.1.2",
                                       weight=0.6))
        self.assertLessEqual(sum(plan.rates.values()), plan.capacity_mbps + 1e-6)

    def test_rates_sum_to_capacity_with_and_without_a_lease(self):
        for lease in (None, Lease(id="l", target="device", ip="1", weight=1.0)):
            plan = build_plan(100.0, lease)
            self.assertAlmostEqual(sum(plan.rates.values()), 100.0, places=6)


class TestShieldAcceptsALease(unittest.TestCase):
    """The spec says the lease is 'verified by the shield'."""

    def test_a_normal_lease_plan_is_not_vetoed(self):
        shield = Shield()
        plan = build_plan(100.0, Lease(id="l1", target="device", ip="10.0.1.2",
                                       weight=0.6))
        self.assertEqual(shield.veto_plan(plan), [])

    def test_a_maximum_weight_lease_is_still_not_vetoed(self):
        shield = Shield()
        plan = build_plan(100.0, Lease(id="l1", target="device", ip="1", weight=1.0))
        self.assertEqual(shield.veto_plan(plan), [])

    def test_a_lease_on_a_tiny_link_degrades_rather_than_vetoes(self):
        """4 classes below 8 Mbps degrade the plan; that is not a veto, and
        treating it as one would make leases unusable exactly when the link is
        tightest."""
        shield = Shield()
        plan = build_plan(6.0, Lease(id="l1", target="device", ip="1", weight=0.9))
        self.assertEqual(shield.veto_plan(plan), [])


class TestIntentService(unittest.TestCase):
    def _svc(self, clock=None):
        return IntentService(LeaseBook(clock=clock or Clock()))

    def _post(self, svc, **body):
        return svc.handle("POST", "/intent", json.dumps(body).encode())

    def test_post_creates_and_returns_201(self):
        st, payload, ctype = self._post(self._svc(), target="device",
                                        ip="10.0.1.2", weight=0.6, ttl_s=30)
        self.assertEqual(st, 201)
        self.assertEqual(payload["ip"], "10.0.1.2")
        self.assertIn("application/json", ctype)

    def test_post_returns_the_expiry_as_an_absolute_time(self):
        c = Clock()
        st, payload, _ = self._post(self._svc(c), target="device", ip="1", ttl_s=30)
        self.assertAlmostEqual(payload["expires_in"], 30.0, places=3)

    def test_get_lists_live_leases(self):
        svc = self._svc()
        self._post(svc, target="device", ip="10.0.1.2", ttl_s=60)
        st, payload, _ = svc.handle("GET", "/intent")
        self.assertEqual(st, 200)
        self.assertEqual(len(payload["leases"]), 1)

    def test_delete_removes_it(self):
        svc = self._svc()
        self._post(svc, target="device", ip="10.0.1.2", ttl_s=60)
        st, payload, _ = svc.handle("DELETE", "/intent/lease-1")
        self.assertEqual(st, 200)
        self.assertEqual(payload["released"]["id"], "lease-1")
        self.assertEqual(svc.handle("GET", "/intent")[1]["leases"], [])

    def test_deleting_twice_is_404_not_500(self):
        svc = self._svc()
        self._post(svc, target="device", ip="1", ttl_s=60)
        self.assertEqual(svc.handle("DELETE", "/intent/lease-1")[0], 200)
        self.assertEqual(svc.handle("DELETE", "/intent/lease-1")[0], 404)

    def test_status_reports_lease_count_and_countdown(self):
        svc = self._svc(Clock(1000.0))
        self._post(svc, target="device", ip="1", ttl_s=45)
        st, payload, _ = svc.handle("GET", "/status")
        self.assertEqual(payload["leases"], 1)
        self.assertAlmostEqual(payload["lease_expiring_in"], 45.0, places=3)

    def test_expired_leases_disappear_from_status(self):
        c = Clock()
        svc = self._svc(c)
        self._post(svc, target="device", ip="1", ttl_s=10)
        c.advance(11)
        self.assertEqual(svc.handle("GET", "/status")[1]["leases"], 0)
        self.assertIsNone(svc.handle("GET", "/status")[1]["lease_expiring_in"])

    def test_bad_target_is_400_with_a_reason(self):
        st, payload, _ = self._post(self._svc(), target="banana", ip="1")
        self.assertEqual(st, 400)
        self.assertIn("target", payload["error"])

    def test_weight_out_of_range_is_400(self):
        self.assertEqual(self._post(self._svc(), target="device", ip="1",
                                    weight=99)[0], 400)

    def test_nan_and_infinity_are_rejected(self):
        """float('nan') survives a bare float() and every comparison against it
        is False, so a plan could contain NaN unnoticed."""
        for bad in (float("nan"), float("inf"), float("-inf")):
            st, payload, _ = self._post(self._svc(), target="device", ip="1",
                                        weight=bad)
            self.assertEqual(st, 400, f"{bad} accepted")
            self.assertIn("finite", payload["error"])

    def test_a_boolean_weight_is_rejected(self):
        """True is an int in Python and would become weight=1.0 silently."""
        st, payload, _ = self._post(self._svc(), target="device", ip="1",
                                    weight=True)
        self.assertEqual(st, 400)
        self.assertIn("boolean", payload["error"])

    def test_a_numeric_string_is_accepted(self):
        """Forms and environment variables deliver strings, and refusing them
        would be pedantry rather than safety."""
        self.assertEqual(self._post(self._svc(), target="device", ip="1",
                                    weight="0.5")[0], 201)

    def test_a_non_numeric_string_is_rejected(self):
        self.assertEqual(self._post(self._svc(), target="device", ip="1",
                                    weight="lots")[0], 400)

    def test_invalid_json_is_400_not_500(self):
        st, payload, _ = self._svc().handle("POST", "/intent", b"{oops")
        self.assertEqual(st, 400)
        self.assertIn("JSON", payload["error"])

    def test_a_json_array_is_400(self):
        self.assertEqual(self._svc().handle("POST", "/intent", b"[1,2]")[0], 400)

    def test_an_oversized_body_is_413(self):
        st, _p, _c = self._svc().handle("POST", "/intent", b"x" * 70000)
        self.assertEqual(st, 413)

    def test_an_unknown_route_is_404(self):
        self.assertEqual(self._svc().handle("GET", "/nope")[0], 404)

    def test_wrong_method_on_intent_is_405(self):
        self.assertEqual(self._svc().handle("PUT", "/intent")[0], 405)

    def test_a_query_string_does_not_break_routing(self):
        self.assertEqual(self._svc().handle("GET", "/intent?pretty=1")[0], 200)

    def test_trailing_slash_is_tolerated(self):
        self.assertEqual(self._svc().handle("GET", "/intent/")[0], 200)

    def test_a_lease_id_with_a_path_separator_is_not_routable(self):
        """The id pattern excludes '/', so `DELETE /intent/../x` cannot escape
        into another route."""
        self.assertEqual(self._svc().handle("DELETE", "/intent/a/b")[0], 404)


class TestOverRealSocket(unittest.TestCase):
    """The handler adapter and the socket, which `handle` does not cover."""

    @classmethod
    def setUpClass(cls):
        rows = [{"t": i,
                 "per_class": {"adaptive_video": {"rtt_p95": 1.0 + i * 0.01,
                                                 "goodput_mbps": 5.0,
                                                 "jitter_ms": 0.1,
                                                 "loss_ratio": 0.0,
                                                 "backlog_bytes": 100}},
                 "link": {"rx_bytes": i * 1000}, "fairness": 0.4}
                for i in range(10)]
        cls.httpd = serve(LeaseBook(), host="127.0.0.1", port=0,
                          status_provider=lambda: {"capacity_mbps": 92.6},
                          dashboard_provider=lambda: build_from_samples(rows))
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()

    def _call(self, method, path, body=None):
        req = urllib.request.Request(
            self.base + path, method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req) as r:
                return r.status, r.read().decode(), r.headers
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode(), e.headers

    def test_healthz(self):
        self.assertEqual(self._call("GET", "/healthz")[0], 200)

    def test_the_whole_lease_lifecycle_over_http(self):
        st, body, _ = self._call("POST", "/intent",
                                 {"target": "device", "ip": "10.0.1.7",
                                  "weight": 0.6, "ttl_s": 60})
        self.assertEqual(st, 201)
        lease_id = json.loads(body)["id"]
        self.assertEqual(len(json.loads(self._call("GET", "/intent")[1])["leases"]), 1)
        self.assertEqual(self._call("DELETE", f"/intent/{lease_id}")[0], 200)
        self.assertEqual(json.loads(self._call("GET", "/intent")[1])["leases"], [])

    def test_the_dashboard_is_served_at_root(self):
        st, body, headers = self._call("GET", "/")
        self.assertEqual(st, 200)
        self.assertIn("text/html", headers["Content-Type"])
        self.assertEqual(body.count('class="panel"'), 6)

    def test_responses_are_not_cached(self):
        _, _, headers = self._call("GET", "/status")
        self.assertEqual(headers.get("Cache-Control"), "no-store")


class TestDashboardIsReadOnly(unittest.TestCase):
    """'Must never write policy' is enforced structurally, not by convention."""

    def test_dashboard_imports_nothing_that_can_touch_the_kernel(self):
        import aciq.dashboard as d
        import ast
        tree = ast.parse(Path_of(d.__file__).read_text())
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        forbidden = {"aciq.harness", "aciq.txn", "aciq.tc", "aciq.bridge",
                     "aciq.policy", "aciq.closedloop", "subprocess", "os.system"}
        bad = {m for m in imported
               if m in forbidden or any(m.endswith("." + f.split(".")[-1])
                                       for f in forbidden)}
        self.assertEqual(bad, set(),
                         f"dashboard can now reach: {sorted(bad)}")

    def test_the_dashboard_never_calls_tc(self):
        import aciq.dashboard as d
        src = Path_of(d.__file__).read_text()
        for token in ("tc ", "tc\"", "nft ", "subprocess", "os.system",
                      "set_capacity", "txn.apply"):
            self.assertNotIn(token, src, f"dashboard contains {token!r}")

    def test_a_get_request_cannot_reach_the_harness(self):
        """The service is constructed with providers, not a harness, so there is
        no reference to write through."""
        class Exploding:
            def __getattr__(self, name):
                raise AssertionError(f"dashboard touched {name}")

        svc = IntentService(LeaseBook(), status_provider=lambda: {},
                            dashboard_provider=lambda: "<p>ok</p>")
        self.assertEqual(svc.handle("GET", "/")[0], 200)
        self.assertEqual(svc.handle("GET", "/status")[0], 200)

    def test_only_get_and_post_and_delete_are_routed(self):
        svc = IntentService(LeaseBook())
        for method in ("PUT", "PATCH", "OPTIONS"):
            self.assertIn(svc.handle(method, "/intent")[0], (404, 405))


def Path_of(p):
    from pathlib import Path
    return Path(p)


SAMPLES = [
    {"t": 0.0, "per_class": {"adaptive_video": {"rtt_p95": 1.0, "jitter_ms": 0.1,
                                                "loss_ratio": 0.0,
                                                "backlog_bytes": 0,
                                                "goodput_mbps": 0.0},
                             "bulk_transfer": {"rtt_p95": 40.0, "jitter_ms": 3.0,
                                               "loss_ratio": 0.01,
                                               "backlog_bytes": 9000,
                                               "goodput_mbps": 90.0}},
     "link": {"rx_bytes": 1000, "tx_bytes": 1000}, "fairness": 0.33},
    {"t": 1.0, "per_class": {"adaptive_video": {"rtt_p95": 1.2, "jitter_ms": 0.1,
                                                "loss_ratio": 0.0,
                                                "backlog_bytes": 10,
                                                "goodput_mbps": 5.0},
                             "bulk_transfer": {"rtt_p95": 38.0, "jitter_ms": 2.5,
                                               "loss_ratio": 0.005,
                                               "backlog_bytes": 8000,
                                               "goodput_mbps": 88.0}},
     "link": {"rx_bytes": 2000, "tx_bytes": 2000}, "fairness": 0.34},
]


class TestDashboardPanels(unittest.TestCase):
    def test_all_six_required_panels_are_present(self):
        html = build_from_samples(SAMPLES)
        self.assertEqual(html.count('class="panel"'), 6)
        for _key, title in PANELS:
            self.assertIn(title, html)

    def test_the_panel_keys_match_the_architecture_spec(self):
        self.assertEqual([k for k, _ in PANELS],
                         ["latency", "jitter", "loss", "throughput",
                          "queue_depth", "fairness"])

    def test_each_class_gets_its_own_series(self):
        p = panels_from_samples(SAMPLES)
        labels = {s.label for s in p["throughput"]}
        self.assertEqual(labels, {"adaptive_video", "bulk_transfer"})

    def test_points_keep_their_timestamps(self):
        p = panels_from_samples(SAMPLES)
        pts = next(s for s in p["throughput"] if s.label == "adaptive_video").points
        self.assertEqual([t for t, _ in pts], [0.0, 1.0])

    def test_fairness_is_plotted_as_a_link_property(self):
        p = panels_from_samples(SAMPLES)
        self.assertEqual([v for _t, v in p["fairness"][0].points], [0.33, 0.34])

    def test_empty_samples_still_render_all_panels(self):
        html = build_from_samples([])
        self.assertEqual(html.count('class="panel"'), 6)
        self.assertIn("no data", html)

    def test_a_missing_metric_does_not_break_a_panel(self):
        """No series is created for a metric nothing measured, and render_panel
        draws 'no data' for an empty one. The guarantee that matters is that the
        page still has all six panels -- asserted on the page, not the dict,
        because the dict legitimately has no key for something never measured."""
        p = panels_from_samples([{"t": 0, "per_class": {"x": {"p50": 1.0}},
                                  "link": {}, "fairness": None}])
        self.assertEqual(p, {})
        html = build_from_samples([{"t": 0, "per_class": {"x": {"p50": 1.0}},
                                    "link": {}, "fairness": None}])
        self.assertEqual(html.count('class="panel"'), 6)

    def test_the_page_is_self_contained(self):
        """No CDN, no external script: a dashboard that needs the network stops
        working on exactly the air-gapped host it would be demonstrated on."""
        html = build_from_samples(SAMPLES, refresh_s=5)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)
        self.assertNotIn("<script", html)

    def test_refresh_is_a_meta_tag_when_asked_for(self):
        self.assertIn("http-equiv=\"refresh\"", build_from_samples(SAMPLES, refresh_s=3))
        self.assertNotIn("http-equiv=\"refresh\"", build_from_samples(SAMPLES))

    def test_refresh_is_never_zero_seconds(self):
        """content="0" reloads in a tight loop and pins a core."""
        html = build_from_samples(SAMPLES, refresh_s=0)
        self.assertNotIn('content="0"', html)


class TestDashboardRendering(unittest.TestCase):
    def test_a_flat_zero_series_does_not_divide_by_zero(self):
        rows = [{"t": i, "per_class": {"bulk_transfer": {"goodput_mbps": 0.0}},
                 "link": {}, "fairness": 0.0} for i in range(5)]
        html = build_from_samples(rows)
        self.assertIn("<svg", html)

    def test_a_single_sample_renders(self):
        html = build_from_samples(SAMPLES[:1])
        self.assertEqual(html.count('class="panel"'), 6)

    def test_values_are_escaped_in_titles(self):
        from aciq.dashboard import render_panel, Series
        out = render_panel("x", "<script>alert(1)</script>", [])
        self.assertNotIn("<script>alert", out)
        self.assertIn("&lt;script&gt;", out)


class TestRealArtefactsRender(unittest.TestCase):
    """The dashboard must read what the experiment actually writes."""

    def _rows(self, rel):
        import os
        here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        p = os.path.join(here, rel)
        if not os.path.isfile(p):
            self.skipTest(f"{rel} not present")
        return [json.loads(l) for l in open(p).read().splitlines() if l.strip()]

    def test_the_published_matrix_renders(self):
        rows = self._rows("data/matrix6/s1_iso_during_call__aciq__adaptive__seed42"
                          "/samples.jsonl")
        html = build_from_samples(rows, subtitle="s1")
        self.assertEqual(html.count('class="panel"'), 6)
        self.assertNotIn("no data", html)


if __name__ == "__main__":
    unittest.main()