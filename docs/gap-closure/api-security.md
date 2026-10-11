# API security

Covers §14.

## Deployment model, stated and enforced

**Loopback by default. A bearer token is required for anything else.** This was
previously only true because the default bind happened to be loopback — a
property of a default, not a control.

```bash
$ ./aciqctl serve --host 0.0.0.0 --port 8091
ValueError: refusing to bind 0.0.0.0: a non-loopback bind exposes POST /intent
to the network, so a token is required. Set ACIQ_API_TOKEN, or bind 127.0.0.1
for a local-only service.
```

The process stops. A warning in a log nobody reads is not a control.

## Controls

| §14 requirement | status |
|---|---|
| explicit bind-address policy | **enforced at startup**, raises |
| authentication for remote access | bearer token, constant-time compare |
| authorization per action | single management principal; no per-role model — see limits |
| request-body size limit | 64 kB, refused with 413 |
| strict JSON and schema validation | object required; unknown fields tolerated and ignored |
| numeric bounds | bool, NaN, inf, non-numeric strings and out-of-range values rejected |
| safe error responses | no stack traces, no internal paths |
| request rate limiting | 30 writes / 60 s per client; reads never limited |
| concurrency | `ThreadingHTTPServer`; the lease book holds an `RLock` |
| duplicate / replayed actions | a lease for the same scope replaces the previous one |
| audit logging | `--audit-log`, line-delimited JSON, flushed per record |
| malformed HTTP | body read is capped; bad JSON is 400, not 500 |
| no credential leakage in logs | the token is never written to the audit record |
| startup failure on missing config | raises, does not warn |

Read routes (`GET /`, `/status`, `/intent`) are **not** authenticated: a
loopback dashboard polling every two seconds should not need a credential.
Mutating routes are.

## Why `NaN` is rejected explicitly

`float("nan")` survives a bare `float()` and fails every comparison against it,
so a NaN rate produces a plan that nothing can be checked against — a safety
failure that looks like success. It is rejected at the boundary rather than
discovered three modules later.

## One real defect found in my own limiter

The rate-limit table was pruned by age alone. Under a fixed or coarse clock
nothing ever expired, so the table grew without bound — a memory leak reachable
by varying the source address alone. The test drove 1400 distinct clients and
caught it at 1200 entries. Now capped at `MAX_RATE_CLIENTS`, with oldest-half
eviction when time-based pruning is insufficient.

## Tests

27 in `tests/test_api_security.py`, including over-the-wire on port 0:

- unauthorised `POST` creates nothing; a token *prefix* does not pass
- unauthorised `DELETE` leaves the lease in place
- the write limit is per client, reads are never throttled, and throttled
  requests create nothing
- the client table stays bounded under 1400 distinct clients
- the token never appears in the audit log
- oversized bodies and NaN weights are refused; a traversal path 404s

## Limits, stated rather than implied

- **No per-role authorization.** There is one management principal. "A caller
  cannot create a lease for a device they are not authorized to manage" (§9.2) is
  **not implemented** — there is no device ownership model to authorize against,
  because leases are addressed by IP with no identity binding (P1-002).
- **No TLS.** The token travels in clear. Acceptable on loopback; **not**
  acceptable on a management network. If the bind policy is relaxed, TLS or a
  reverse proxy terminating it becomes required, and that is not implemented.
- **No timing-safe body parsing**, only the token compare is constant-time.
- **No replay protection beyond scope replacement.** A captured `POST` replayed
  within its TTL recreates the same lease; it does not compound.
- **No audit of reads.** Only policy-changing requests are recorded.
- **Not penetration tested.** These are unit and integration tests against the
  real handler. No claim is made about resistance to an attacker with network
  access.
