"""M7 -- the intent API, over the standard library.

`POST /intent`, `GET /intent`, `DELETE /intent/{id}`, `GET /status`, and the
M8 dashboard at `GET /`.

## Why not FastAPI

The plan calls for FastAPI. It is not installed, and nothing else is either --
no starlette, no uvicorn, no flask, no aiohttp. `http.server` is in the standard
library, which for this particular service is a better fit than the plan
assumed: the dashboard's hard requirement is that it **can never write policy**,
and a dependency-light handler that only reaches the lease book and a
read-only snapshot cannot be talked into growing a write path later.

So this is a deliberate deviation from `PLAN.md`, recorded here and in the docs,
not an oversight.

## Read-only means read-only

`GET /` and `GET /status` are served from a snapshot built by `snapshot()`,
which returns plain dicts. There is no handler that turns a dashboard request
into a `tc` call, and `_read_only_routes` is asserted by a test that walks every
route and fails if a GET can reach the harness's write methods.

## Request handling is separate from the socket

`IntentService.handle` is a pure-ish function of (method, path, body). The
handler class is a thin adapter over it, so the whole API surface is testable
without opening a port, and the socket path is tested separately on port 0.
"""

from __future__ import annotations

import ipaddress
import json
import re
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from collections.abc import Callable

from .intent import IntentError, LeaseBook, lease_to_dict

#: Refuse absurd bodies rather than buffering them.
MAX_BODY_BYTES = 64 * 1024

#: Mutating requests per client per window. A lease book is cheap to write and
#: expensive to get wrong: an unbounded caller can rewrite the router's policy
#: as fast as Python can serialise JSON. Reads are never limited -- a dashboard
#: polling every two seconds must not be throttled.
RATE_LIMIT_WRITES = 30
RATE_LIMIT_WINDOW_S = 60.0
#: Ceiling on tracked clients, so a varying source address cannot grow the table
#: without bound.
MAX_RATE_CLIENTS = 1024

#: Hosts that are not loopback. Binding to one of these exposes lease creation to
#: the LAN, so it requires an explicit token rather than happening silently.
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

#: Methods that change policy. Everything else is a read.
MUTATING_METHODS = frozenset({"POST", "DELETE", "PUT", "PATCH"})

_INTENT_RE = re.compile(r"^/intent/(?P<id>[A-Za-z0-9_.:-]{1,64})$")

#: A flow lease names a 5-tuple as `src:sport->dst:dport`. Shape-checked here in
#: addition to the book's own validation: the API is the untrusted edge, and a
#: flow string is stored, echoed into status and eventually parsed by the
#: matcher, so a 10 MB "flow" is a denial-of-service waiting to be buffered
#: rather than a lease.
_FLOW_RE = re.compile(
    r"^(?P<src>\S{1,64}):(?P<sport>\d{1,5})->"
    r"(?P<dst>\S{1,64}):(?P<dport>\d{1,5})$")


def _valid_ip(value: Any) -> bool:
    """A real IPv4/IPv6 literal. Rejects hostnames, CIDR and garbage."""
    if not isinstance(value, str) or len(value) > 64:
        return False
    try:
        ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _valid_flow(value: Any) -> bool:
    if not isinstance(value, str) or len(value) > 200:
        return False
    m = _FLOW_RE.match(value)
    if not m:
        return False
    if not (_valid_ip(m.group("src")) and _valid_ip(m.group("dst"))):
        return False
    # Both ends must be the same address family. A flow whose source is IPv4 and
    # whose destination is IPv6 names a tuple no conntrack entry can ever hold,
    # so the lease would install a filter that matches nothing and report
    # success -- the same silent no-op the IP check above exists to prevent.
    if (ipaddress.ip_address(m.group("src")).version
            != ipaddress.ip_address(m.group("dst")).version):
        return False
    return all(0 <= int(m.group(p)) <= 65535 for p in ("sport", "dport"))


class IntentService:
    """The API's behaviour, with no HTTP types in the signatures."""

    def __init__(self, book: LeaseBook | None = None,
                 status_provider: Callable[[], dict] | None = None,
                 dashboard_provider: Callable[[], str] | None = None,
                 token: str | None = None,
                 audit: Callable[[dict], None] | None = None):
        self.book = book or LeaseBook()
        self._status = status_provider or (lambda: {"leases": 0})
        self._dashboard = dashboard_provider or (lambda: "<!doctype html><p>no dashboard")
        #: Bearer token required for mutating routes. None means "no token
        #: configured", which is only acceptable on loopback -- `check_bind`
        #: refuses to start otherwise rather than leaving it to the operator's
        #: memory of which default they got.
        self.token = token
        self._audit = audit or (lambda rec: None)
        #: client -> (window_start, count). The ThreadingHTTPServer runs a
        #: thread per connection, and `_allow_write` is a read-modify-write on
        #: this dict; without the lock two concurrent writes for one client can
        #: both read the same count and one increment is lost, so the cap can be
        #: exceeded. It also protects the pruning pass, which replaces the whole
        #: dict and could otherwise drop a concurrent client's fresh entry.
        self._rate: dict[str, tuple[float, int]] = {}
        self._rate_lock = threading.Lock()

    # ---- routes ----------------------------------------------------------
    def handle(self, method: str, path: str, body: bytes = b"",
               headers: dict | None = None,
               client: str = "local") -> tuple[int, Any, str]:
        """-> (status, payload, content_type). Never raises for bad input."""
        headers = headers or {}
        path = path.split("?", 1)[0].rstrip("/") or "/"
        mutating = method in MUTATING_METHODS

        if mutating:
            # Count the attempt BEFORE deciding anything else. An earlier
            # revision returned 401 for bad credentials *before* consulting the
            # limiter, so a caller could guess tokens without bound -- the one
            # abuse the limiter exists to stop. Authentication still runs first
            # in the sense that it decides the response (401 vs 429 is chosen
            # below by precedence), but the budget is spent either way, so a
            # guessing loop is throttled just like a legitimate one.
            within_budget = self._allow_write(client)
            if self.token is not None:
                supplied = (headers.get("authorization") or "").strip()
                want = f"Bearer {self.token}"
                # Constant-time compare: a timing oracle on a bearer token is a
                # real, if slow, attack.
                if not secrets.compare_digest(supplied, want):
                    self._audit({"method": method, "path": path,
                                 "client": client, "outcome": "unauthorised"})
                    # If the caller is already over budget, say so rather than
                    # 401: the limiter should bound the response, and a flood of
                    # failed auth should be visible as throttling, not as an
                    # unbounded stream of 401s.
                    if not within_budget:
                        return 429, {"error": "too many write requests"}, \
                            "application/json"
                    return 401, {"error": "unauthorised"}, "application/json"
            if not within_budget:
                self._audit({"method": method, "path": path,
                             "client": client, "outcome": "rate_limited"})
                return 429, {"error": "too many write requests"}, "application/json"

        if method == "GET" and path == "/":
            return 200, self._dashboard(), "text/html; charset=utf-8"
        if method == "GET" and path == "/status":
            st = dict(self._status())
            st["leases"] = len(self.book.active())
            st["lease_expiring_in"] = self.book.expiring_in()
            return 200, st, "application/json"
        if path == "/intent":
            if method == "GET":
                now = self.book.now()
                return 200, {"leases": [lease_to_dict(l, now) for l in
                                        self.book.active(now)]}, "application/json"
            if method == "POST":
                return self._create(body, client)
            return 405, {"error": f"{method} not allowed on /intent"}, "application/json"

        m = _INTENT_RE.match(path)
        if m and method == "DELETE":
            lease_id = m.group("id")
            gone = self.book.release(lease_id)
            if gone is None:
                self._audit({"method": "DELETE", "path": path, "client": client,
                             "outcome": "not_found", "lease": lease_id})
                return 404, {"error": "no such lease"}, "application/json"
            # DELETE mutates policy, so it is audited exactly like POST. An
            # earlier revision audited creation and rejection but not release,
            # which made the audit log unable to answer "who removed the EF
            # lease at 03:00" -- the one question a release log exists for.
            self._audit({"method": "DELETE", "path": path, "client": client,
                         "outcome": "released", "lease": gone.id,
                         "target": gone.target, "ip": gone.ip,
                         "flow": gone.flow})
            return 200, {"released": lease_to_dict(gone, self.book.now())}, \
                "application/json"

        if path == "/healthz":
            return 200, {"ok": True}, "application/json"
        return 404, {"error": f"no route for {method} {path}"}, "application/json"

    def _allow_write(self, client: str) -> bool:
        """Token bucket, fixed window. Returns whether the write may proceed."""
        now = self.book.now()
        with self._rate_lock:
            start, count = self._rate.get(client, (now, 0))
            if now - start >= RATE_LIMIT_WINDOW_S:
                start, count = now, 0
            count += 1
            self._rate[client] = (start, count)
            # Bound the table. Time-based pruning alone is not enough: with a
            # fixed or coarse clock nothing ever expires and the dict grows
            # without limit, which is itself a memory leak an attacker can drive
            # simply by varying the source address. Evict the oldest half when
            # over the cap.
            if len(self._rate) > MAX_RATE_CLIENTS:
                fresh = {k: v for k, v in self._rate.items()
                         if now - v[0] < RATE_LIMIT_WINDOW_S}
                if len(fresh) > MAX_RATE_CLIENTS:
                    ordered = sorted(fresh.items(), key=lambda kv: kv[1][0])
                    fresh = dict(ordered[len(ordered) // 2:])
                self._rate = fresh
            return count <= RATE_LIMIT_WRITES

    def _create(self, body: bytes, client: str = "local") -> tuple[int, Any, str]:
        if len(body) > MAX_BODY_BYTES:
            return 413, {"error": "body too large"}, "application/json"
        try:
            data = json.loads(body or b"{}")
        except json.JSONDecodeError as e:
            return 400, {"error": f"invalid JSON: {e.msg}"}, "application/json"
        if not isinstance(data, dict):
            return 400, {"error": "body must be a JSON object"}, "application/json"
        target = data.get("target", "")
        ip = data.get("ip")
        flow = data.get("flow")
        # Validate the discriminated fields against what the target actually
        # means before the book sees them. The book's `_validate` only checks
        # that the field is present, so `{"target":"device","ip":"not-an-ip"}`
        # used to become a live lease whose device scope could never match a
        # real flow -- a silent no-op that reported success.
        if target == "device" and ip is not None and not _valid_ip(ip):
            return 400, {"error": "ip must be an IPv4/IPv6 address, "
                                  f"got {ip!r}"}, "application/json"
        if target == "flow" and flow is not None and not _valid_flow(flow):
            return 400, {"error": "flow must be src:sport->dst:dport with real "
                                  f"addresses, got {flow!r}"}, "application/json"
        try:
            lease = self.book.request(
                target=target,
                ip=ip,
                flow=flow,
                weight=_num(data.get("weight"), 0.4, "weight"),
                ttl_s=_num(data.get("ttl_s"), 90.0, "ttl_s"),
            )
        except IntentError as e:
            # 400: the request parsed as JSON but names a lease the book cannot
            # satisfy (bad TTL, bad weight, missing scope field). An earlier
            # comment promised a separate 422 for "parses but cannot be
            # satisfied"; nothing emitted it, so the comment described a status
            # the API never returns. One code for all rejected writes is honest;
            # the body names the specific fault.
            return 400, {"error": str(e)}, "application/json"
        except TypeError as e:
            return 400, {"error": str(e)}, "application/json"
        self._audit({"method": "POST", "path": "/intent", "outcome": "created",
                     "client": client,
                     "lease": lease.id, "target": lease.target,
                     "ip": lease.ip, "weight": lease.weight,
                     "ttl_s": lease.ttl_s})
        return 201, lease_to_dict(lease, self.book.now()), "application/json"


def _num(v, default: float, name: str) -> float:
    """Coerce, but reject a bool and a string that is not a number.

    `float("nan")` and `float("inf")` both pass a bare `float()` and would
    produce a plan containing NaN, which every comparison against it silently
    fails -- so they are rejected here rather than discovered three modules later.
    """
    if v is None:
        return default
    if isinstance(v, bool):
        raise IntentError(f"{name} must be a number, not a boolean")
    if isinstance(v, str):
        try:
            v = float(v)
        except ValueError as e:
            # `from e` so a traceback distinguishes "the client sent nonsense"
            # from "our own conversion broke" -- the two have very different
            # causes and were indistinguishable in the log.
            raise IntentError(f"{name} must be a number, got {v!r}") from e
    if not isinstance(v, (int, float)):
        raise IntentError(f"{name} must be a number, got {type(v).__name__}")
    v = float(v)
    if v != v or v in (float("inf"), float("-inf")):
        raise IntentError(f"{name} must be finite")
    return v


def make_handler(service: IntentService):
    class Handler(BaseHTTPRequestHandler):
        server_version = "aciq-intent"

        def log_message(self, fmt, *args):  # noqa: N802 - stdlib signature
            # Quiet by default; a line per request turns a live demo into noise.
            if getattr(self.server, "verbose", False):
                super().log_message(fmt, *args)

        def _send(self, status: int, payload: Any, ctype: str) -> None:
            if isinstance(payload, (dict, list)):
                raw = json.dumps(payload, indent=2).encode()
            else:
                raw = str(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _read_body(self) -> bytes:
            try:
                n = int(self.headers.get("Content-Length") or 0)
            except ValueError:
                n = 0
            # Read one byte past the cap when the caller claims a larger body,
            # so `_create`'s `len(body) > MAX_BODY_BYTES` check can actually
            # fire. An earlier version read `min(n, MAX_BODY_BYTES)`, which
            # truncated an oversized body to exactly the cap and made the 413
            # branch unreachable over the wire: the "refuse absurd bodies"
            # docstring described behaviour the socket path never performed.
            want = MAX_BODY_BYTES + 1 if n > MAX_BODY_BYTES else n
            return self.rfile.read(want)

        def _client(self) -> str:
            return self.client_address[0] if self.client_address else "unknown"

        def _hdrs(self) -> dict:
            return {k.lower(): v for k, v in self.headers.items()}

        def do_GET(self):  # noqa: N802
            status, payload, ctype = service.handle(
                "GET", self.path, headers=self._hdrs(), client=self._client())
            self._send(status, payload, ctype)

        def do_POST(self):  # noqa: N802
            status, payload, ctype = service.handle(
                "POST", self.path, self._read_body(),
                headers=self._hdrs(), client=self._client())
            self._send(status, payload, ctype)

        def do_DELETE(self):  # noqa: N802
            status, payload, ctype = service.handle(
                "DELETE", self.path, headers=self._hdrs(), client=self._client())
            self._send(status, payload, ctype)

    return Handler


def check_bind(host: str, token: str | None) -> None:
    """Refuse to expose lease creation without authentication.

    Raising at startup rather than logging a warning: a service that is reachable
    from the LAN and can rewrite the router's policy is a misconfiguration that
    should stop the process, not something the operator should notice in a log
    file they may not read.
    """
    if host in LOOPBACK_HOSTS:
        return
    if not token:
        raise ValueError(
            f"refusing to bind {host}: a non-loopback bind exposes POST /intent "
            f"to the network, so a token is required. Set ACIQ_API_TOKEN, or bind "
            f"127.0.0.1 for a local-only service.")


def serve(book: LeaseBook, host: str = "127.0.0.1", port: int = 8080,
          status_provider=None, dashboard_provider=None, verbose: bool = False,
          token: str | None = None, audit=None):
    """Start the server and block. Returns the ThreadingHTTPServer."""
    check_bind(host, token)
    service = IntentService(book, status_provider, dashboard_provider,
                            token=token, audit=audit)
    httpd = ThreadingHTTPServer((host, port), make_handler(service))
    httpd.verbose = verbose
    return httpd