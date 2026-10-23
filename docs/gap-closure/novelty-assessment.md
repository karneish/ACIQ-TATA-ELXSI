# Novelty assessment

This note states, plainly, what in ACIQ+ is a contribution and what is
integration of known techniques. It is written to be falsifiable: each claim
names the prior art it would be checked against and the part of this repository
that carries it.

## What is NOT claimed as novel

- **HTB class hierarchy with guaranteed floors and ceilings.** Standard
  Linux `tc` HTB. The plan uses it; it is not new.
- **`fq_codel` as the leaf qdisc.** The per-flow fairness the project measures
  is `fq_codel`'s property. The project *measures* it rather than claiming it as
  its own — see `docs/gap-closure/fairness-validation.md`.
- **DSCP EF marking and priority.** RFC 3246 / RFC 2474 and DiffServ are
  decades old. ACIQ+ treats a mark as a *claim* to be checked, not as truth,
  but the mechanism itself is not novel.
- **Goodput-based capacity estimation by EWMA.** Textbook. The contribution is
  the specific discipline about *when* the estimator may update (saturation
  evidence only), not the arithmetic.
- **Blind traffic classification by flow statistics.** Well studied (e.g.
  flow-statistical classifiers, `nDPI`-style heuristics). Packet-size, rate and
  duty-cycle features are conventional.

## What this project does that is genuinely distinct

1. **Trust as a checked, decaying input rather than a bootstrap.** The
   classifier accepts a DSCP-EF *claim* and denies it against measured shape
   (`looks_interactive()`), decaying per-source trust on each denied claim
   (`aciq/classify.py`, `TrustStore`). The idea that a mark is a claim is old;
   making the mark's authority something the flow has to *keep earning*, and
   recording the decay in the classification evidence, is the specific design.
   Novelty level: **engineering, modest.**

2. **A capacity estimator gated on external-bottleneck evidence, with the
   vantage-point error corrected.** The measured defect register (P0-006,
   P0-007, §8.3, §8.4) documents that reading `rx_bytes` upstream of the
   bottleneck is *offered* load, not delivered load, and that the resulting
   over-read propagated into bulk's ceiling and produced a 70 ms tail. The
   controller reads the bottleneck's **drop/backlog counters** — an observable
   a physical link also gives — and never its configured rate. Using an
   out-of-band queue's drops as the saturation signal while forbidding the
   controller from reading its configured rate is the design point;
   `aciq/capacity.py`, `BottleneckDropSource` carry it. Novelty level:
   **engineering, and the negative constraint is the interesting half.**

3. **Lease beats correction, and both are audited against what the kernel
   actually holds.** The precedence (an operator lease overrides a stale
   correction), the live reload with mtime throttling, and the readback
   verification that refuses to commit when the kernel's state is opaque
   (`aciq/txn.py` vacuous-verification gate, `readback_unverifiable`) form a
   closed loop where *"the policy applied"* is a claim that must survive a
   read-back. The individual pieces are ordinary systems engineering; the
   refusal-to-commit-on-opaque-readback is the strongest single invariant here.
   Novelty level: **engineering; the honesty invariant is the contribution.**

4. **Honest-unmeasured as a first-class value end to end.** `float | None` plus
   `metric_status`, propagated through collector, dashboard and report, with a
   dashboard that refuses to draw a zero-valued series as a measurement
   (`docs/gap-closure/metric-integrity.md`, P0-001/P0-004). Treating "not
   measured" as distinct from "measured zero" at every layer — including
   refusing an axis that would label a negative latency — is a
   *methodological* contribution more than an algorithmic one. Novelty level:
   **methodology.**

5. **A defect register that survives its own resolution, and claim auditing.**
   Forty-two documented defects, a machine-checked claim audit
   (`tools/audit_claims.py`) that fails if a cited number or test name cannot be
   resolved, and an acceptance harness that reports `NOT RUN` for anything the
   environment cannot exercise. This is reproducibility engineering, not QoS
   research, but it is the part a reviewer can most easily verify. Novelty
   level: **process.**

6. **A bound is only a bound if something evicts, and a measurement that
   measures itself is not a measurement.** A recurring shape across the defects
   found here: a structure described as "bounded" in prose while nothing in the
   code enforced the bound. `TrustStore`'s three maps were keyed by source and
   never evicted; the long-run memory claim was real only after
   `MAX_TRUST_SOURCES` and least-recently-seen eviction were added and a soak
   (`tools/offline_soak.py`) measured RSS over 277 106 ticks. That soak then
   caught the same error one level up: its own first revision retained one float
   per tick and reported that retention as controller drift (~10 MB over 30
   minutes), so the harness was measuring itself. The lesson is methodological —
   a resource invariant is a *test* or it is a hope, and a measurement must be
   sure it is not part of what it measures — and it is the same theme as the
   honesty invariants above, applied to memory rather than to numbers. Novelty
   level: **methodology.**

## What is explicitly left to future work

- **Multi-tenant fairness.** The system is single-operator. `LeaseBook` has one
  namespace of leases. Per-tenant isolation is a documented limitation, not a
  built feature (`docs/limitations.md`, §11.3 of the report).
- **Unclassified-set EF promotion.** An unmarked flow whose behaviour matches
  EF could be promoted; this needs a kernel-integrated run to validate and is
  recorded as blocked rather than shipped unvalidated.
- **DSCP forwarded to the live classifier.** `experiment.py` reads the DSCP the
  generator requested, but the classifier's live path does not yet observe the
  mark on the wire; it is a documented observation-source gap.

## Bottom line

ACIQ+ is an **integration and measurement** contribution, not a new algorithm.
Its defensible claim to novelty is a set of *honesty invariants* — a mark is a
claim, capacity must be inferred from delivered not offered load, "not measured"
is not zero, and a policy is not applied until the kernel says so — each carried
in code and each backed by a defect found by a gate written to fail first. Any
reviewer checking originality should read `docs/gap-closure/defect-register.md`
alongside this note: the defects are the evidence that the invariants are real
rather than asserted.
