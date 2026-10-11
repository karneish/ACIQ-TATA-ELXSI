# Baseline comparison

Covers §7. **The conclusion is that no superiority over CAKE is established, and
that this document exists to make that unambiguous.**

## Configurations, as actually run

| arm | qdisc | configuration |
|---|---|---|
| `b0_fifo` | `pfifo` | default; no rate limit |
| `b1_cake95` | `cake` at 95% of link capacity | root qdisc |
| `aciq` | `htb` root, `fq_codel` leaves | three classes + optional lease |

`b1_cake95` at 95% is the correct comparison for a link-shaping controller: it
reserves 5% rather than taking the whole link, and it is the configuration most
likely to *win* against ACIQ. Comparing against a deliberately hobbled CAKE
would produce a favourable number that means nothing.

## Results as they stand

`data/matrix6`, six paired seeds:

- vs `b0_fifo`: **p = 0.0312** on p50/p95/p99 and loss
- vs `b1_cake95`: **no significant difference**

**No claim of superiority over CAKE appears anywhere in this repository, and
none is supported by this data.**

## Why the comparison is currently inconclusive rather than negative

Two reasons, both stated rather than smoothed:

1. **The latency pipeline was broken.** `rtt_p95`, `jitter_ms` and `loss_ratio`
   were identically zero in every stored run — four independent causes, fixed in
   this work (P0-001 to P0-004). **Every stored comparison used a metric that
   does not work.** The p50/p95/p99 figures in `matrix6` come from the generator
   reports via a path that worked; the per-sample `loss_ratio` did not.
2. **The runs were not contended.** `s3` offered ~14.3 Mbps on a 20 Mbps link —
   71% utilisation, not congestion. A shaping controller's advantage appears
   under contention, and there was none.

## What a fair comparison would require

| requirement | status |
|---|---|
| matched topology, capacity, duration, seed | yes — the driver shares the scenario |
| same measurement method across arms | **now yes**; was not |
| a pre-declared primary metric | **not declared** |
| adequate sample size | 6 seeds; `MIN_PAIRS_FOR_PVALUE = 6` is the floor, not a comfortable n |
| effect size and confidence interval | **not reported** |
| non-inferiority margin, if that is the claim | **not defined** |

§7.3 forbids choosing the metric after seeing results. This project has not done
that, but it also has not *pre-declared* one — which is the same discipline
failing in the other direction.

## Where ACIQ adds capability CAKE does not have

These are architectural and are **not** performance claims:

- **Intent leases.** A time-boxed, device-specific guarantee through an API.
  CAKE has no equivalent. This is the clearest demonstration:

  | | tv1 (leased) | tv2 | tv3 | 3-device total |
  |---|---|---|---|---|
  | no lease | 17.99 MB | 17.92 MB | 17.92 MB | 53.83 |
  | lease 0.6 | **23.05 MB** | 15.54 MB | 15.34 MB | 53.93 |

  +28.1% for the leased device, at the expense of the other two, with the link
  saturated. Exact paired Wilcoxon **p = 0.015625**, n = 7, across seven paired
  seeds. Sent-side measurement, independent of the controller's own accounting.

- **Auditability.** Every policy change records the tree it applied.
- **Explicit safety.** A shield vetoes before the kernel is touched.
- **Per-flow enforcement with operator correction**, rather than per-flow
  classification without a way to override it.

## Not verified

An end-to-end three-arm comparison under the corrected measurement pipeline is
**blocked-environment**. Until it runs, the honest statement is: *ACIQ is not
shown to outperform CAKE on raw queueing, and is shown to provide capabilities
CAKE does not.*
