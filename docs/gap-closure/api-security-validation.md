# API security validation

Status: **PASS** — revalidated this run, not carried forward from the report.

## Environment

Loopback only, which *is* the documented deployment model. 38 tests, over the
wire on port 0.

## The reported defects, re-checked against the current code

| reported | current code | verdict |
|---|---|---|
| bind refusal without token | `check_bind()` raises before `serve()` | **holds** |
| token auth | constant-time compare, mutating routes only | **holds** |
| rate limiting | 30 writes / 60 s per client | **holds** |
| audit logging | one line per policy-changing request | **holds** |
| limiter unbounded under a fixed clock | capped + oldest-half eviction | **holds**, proven below |

Demonstrated live, not asserted:

```
$ ./aciqctl serve --host 0.0.0.0 --port 8091
ValueError: refusing to bind 0.0.0.0: a non-loopback bind exposes POST /intent
to the network, so a token is required. Set ACIQ_API_TOKEN, or bind 127.0.0.1.
```

## Rate-limiter boundedness — proven on every condition the prompt names

| condition | result |
|---|---|
| fixed clock, 5000 unique clients | table **904** entries (cap 1024) |
| advancing clock, 5000 clients over 10 windows | table **500** |
| one client hammering | exactly **30 × 201**, remainder **429** |
| spoofed `X-Forwarded-For` headers | **0** entries — client key ignores them |
| 20 concurrent threads × 50 requests | **0** exceptions, table 20 |
| `x-forwarded` referenced in `api.py` | **False** |

The client identity comes from `client_address` — the socket peer — and never
from a request header. `x-forwarded` does not appear in the module at all, so a
caller cannot rotate its rate-limit bucket by claiming a different address.

## Token handling

Missing, empty, wrong, and **prefix** tokens are all rejected; a valid one is
accepted. The comparison is constant-time. **The token is never written to the
audit record** — a verified assertion, because a log line containing a bearer
token turns the log into a credential store.

## Local development cannot silently disable authentication

Reads (`/`, `/status`, `/intent`) stay unauthenticated so a loopback dashboard
needs no credential. **Writes never do.** There is no flag that turns off write
authentication; the only way to expose writes is to bind a non-loopback address,
which the process refuses without a token.

## Audit logging

Records outcome, client, and lease identity for every policy-changing request —
including failures (`unauthorised`, `rate_limited`) and not only successes.

## Limits, unchanged and stated

- **No per-role authorization.** One management principal. §9.2's "a caller
  cannot lease a device they are not authorized to manage" is **not
  implemented** — there is no ownership model to authorize against, because
  leases address an IP with no identity binding.
- **No TLS.** The token travels in clear. Acceptable on loopback, **not**
  acceptable on a management network. Relaxing the bind policy requires TLS or a
  terminating proxy, neither of which is implemented.
- **No replay protection** beyond scope replacement.
- **Not penetration tested.** Unit and integration tests against the real
  handler, over the wire on loopback. No claim about an attacker with network
  access.
