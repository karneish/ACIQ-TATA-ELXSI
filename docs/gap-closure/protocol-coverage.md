# Protocol coverage

Covers §12.

## What is genuinely covered

| protocol | classify | filter | enforced | evidence |
|---|---|---|---|---|
| IPv4 / TCP | yes | flower `ip_proto tcp` | yes | gate 16 |
| IPv4 / UDP | yes | flower `ip_proto udp` | yes | gate 16, 17 |
| IPv6 / TCP | yes | flower `ipv6` | yes | gate 18 |
| IPv6 / UDP | yes | flower `ipv6` | yes | gate 18 |
| IPv6 / DSCP-EF fallback | n/a | `ip_tos 184/0xfc` | yes | gate 14 |
| unmarked traffic | no | DSCP-EF fallback only | yes | by design |

Filter priorities, asserted rather than assumed:

```
10-19   bridge, mark-driven, one priority per class per protocol
20-29   reserved
30-31   DSCP-EF fallback (v4 at 30, v6 at 31)
```

Gate check 17 exists to prove the ordering: a flow the bridge *rejected* must
not reach `1:10` via the EF fallback.

## What is not covered, and what happens instead

| protocol | behaviour | is it safe? |
|---|---|---|
| ICMP / ICMPv6 | not classified; default class | yes — no interactive priority |
| SCTP, GRE | not classified; default class | yes |
| IPv6 extension headers | flower key may not match | yes — falls through to default |
| fragments | not reassembled before matching | yes — falls through |
| malformed packets | not classified | yes |

`th dport` exists only for TCP and UDP. That is a property of the key shape, and
the honest consequence is that anything else takes the DSCP-EF path or the
default class.

**That is a safe fallback, not a bypass.** An unmarked ICMP flow cannot reach
`1:10` unless it sets DSCP EF, and even then it reaches the *fallback*, whose
job is exactly to serve traffic the bridge could not classify. §12 asks that an
unclassifiable protocol not create an unsafe bypass — it does not.

## Not verified

No test drives ICMP, SCTP or fragmented traffic through the namespace path.
The behaviour above is read from the code, not observed. **Blocked-environment.**
