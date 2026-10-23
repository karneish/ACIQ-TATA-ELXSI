# Device identity and lease lifecycle

Covers §9.

## Identity model, and its limits

**A device is an IP address.** There is no MAC binding, no DHCP lease tracking,
no identity store. Consequences, stated rather than implied:

| scenario | behaviour |
|---|---|
| DHCP address change | the lease no longer matches the device; it silently stops applying |
| IPv4 address reuse | **a new device inherits the old device's lease** |
| IPv6 privacy addresses | the lease breaks on every rotation |
| multiple devices behind one NAT | they share one address and cannot be told apart |
| spoofed lease request | accepted — any caller can lease any address |
| namespace/interface recreation | leases are in-memory plus a JSON file; both survive |

MAC-based identity is **not** introduced here, and that is deliberate rather than
an omission. In this topology every device reaches the router through the same
WAN interface, so a MAC would be a stable local identifier — but it is
forgeable by anyone on the segment, and it does not survive a bridge or a routed
hop. Swapping IP for MAC would look like an improvement while moving the
trust boundary without moving the risk. §9.1 asks for the strongest model
*supported by the architecture*; IP is currently that.

## The testbed's improvement is real but is not identity

Per-workload source addresses (203.0.113.3–6) are stable for the life of a run
and make a lease match **one** device. That is what made per-device leases
measurable at all — before it, every workload shared one address and a lease
matched everything. It is stable addressing, not identity: nothing prevents the
address being reused.

## Lifecycle, and what is tested

| behaviour | implemented | tested |
|---|---|---|
| grant with TTL | yes | yes |
| expiry removes the lease | yes | yes |
| renewal | yes (re-request) | yes |
| cancellation | yes, `DELETE /intent/<id>` | yes |
| persistence across restart | yes, atomic JSON write | yes |
| duplicate request for one scope | replaces, last wins | yes |
| malformed request rejected | yes | yes |
| unauthorised request rejected | **yes**, bearer token | yes |
| controller restart reconciles | **no** — see below |

**Expiry stops granting special treatment**, verified: the run reports
`in effect for 38.0s` and the audit shows the class reverting to the unleased
plan. An expired lease cannot influence the tree.

## Conflicting leases

Two devices may both hold a lease. What happens:

- each lease's weight is applied to its own class;
- the shield still vetoes if the resulting `sum(rates) > capacity`, so
  **overcommitment is impossible**;
- when floors cannot all be met, they scale down proportionally and the plan is
  marked `degraded` — recorded rather than silently violated.

There is no priority between competing leases. Neither is refused; both are
scaled. That is a documented policy, not an accident, and §9.3's "define what
happens when all requested guarantees cannot be met" is answered by it.

**Not verified:** a two-lease contention experiment on a real kernel is
**blocked-environment**.

## Restart behaviour — a real gap

After a restart the lease book reloads from its JSON file, but the harness has
**no record of what the kernel is actually running**. If the controller died
mid-apply, the reloaded book and the live qdisc can disagree, and the controller
does not reconcile them.

That is §13's "the controller must not blindly trust in-memory state after a
crash", and it is **not implemented**. The safe behaviour — rebuild the tree from
the reloaded book before serving — is specified and small; it is not shipped
because it cannot be tested here.

## Address changes do not transfer privilege

A lease is matched per tick against live flow endpoints, so a device that
acquires a leased address *does* receive the lease. That is the "address reuse
transfers privilege" case above, and it is **not mitigated**.
