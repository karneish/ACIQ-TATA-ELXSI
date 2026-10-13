# Real-kernel acceptance

**Verdict on this document: the live rollback gate HAS been executed and passed
on real hardware. The remaining kernel gates have not.**

| | |
|---|---|
| host | Pop!_OS, kernel `7.1.5-76070105-generic` |
| iproute2 | `6.1.0`, libbpf `1.3.0` |
| revision | `7250aa58` |
| command | `sudo python3 -m unittest tests.test_rollback_live -v` |
| result | **`Ran 6 tests ... OK`** |

Everything below records what was attempted, what is now proven, and what
remains blocked.

## The environment, established rather than assumed

The brief warns against inferring host capability from a shell prompt. That
warning matters here, because this environment **looks** like the user's host:

| probe | result | what it means |
|---|---|---|
| `hostname` | `pop-os` | the sandbox **shares the host kernel** — a name proves nothing |
| `uname -a` | `Linux pop-os 7.1.5-76070105-generic ...` | same, still proves nothing |
| `id` | `uid=1000(mekarz) gid=1000(mekarz)` | same uid as the user |
| **`/proc/1/comm`** | **`bwrap`** | bubblewrap sandbox — this is the decisive signal |
| **`CapEff`** | **`0000000000000000`** | zero capabilities, including `CAP_NET_ADMIN` |
| `CapBnd` | `0000000000000000` | nothing can be regained |
| `unshare --net true` | `Operation not permitted` | namespaces refused at the syscall level |
| `ip`, `tc`, `iperf3`, `nc`, `ping`, `sudo` | **absent** | |
| `find / -xdev -name ip -o -name tc` | **no results** | not a `PATH` artefact — genuinely absent from the filesystem |

**Conclusion: this is a restricted sandbox, not the user's Pop!_OS shell.** The
hostname and kernel are shared with the host, which is exactly why the obvious
checks are not sufficient; the process tree and the capability set are what
distinguish them.

Per the brief's rule against repeating privileged attempts once the environment
has conclusively demonstrated they are unavailable, no further privileged
operations were attempted after the above.

## Commands not executed here

```bash
sudo python3 tools/acceptance.py                  # NOT RUN
sudo python3 -m unittest tests.test_rollback_live -v   # NOT RUN
```

These were **not** run on the user's machine. No output from them appears
anywhere in this repository, and no result in any document is attributed to
them. The one time a real run was attempted, it was by the user, and its output
is recorded in `rollback-readback-verification.md` — including the five defects
it exposed.

## What the sandbox *can* support

| evidence class | status | basis |
|---|---|---|
| unit / integration / socket | **supported** | 832 tests, 0 failures |
| classifier evaluation | **supported** | 16 constructed cases, two capacities |
| API security | **supported** | 27 tests, over the wire on loopback |
| metric integrity | **supported** | arithmetic + live socket recomputation |
| claim audit | **supported** | constants, evidence, citations, phrases |
| **simulated rollback** | **supported** | 33 mocked tests |
| **live-test-vs-double** | **supported** | 6 tests |
| kernel traffic control | **BLOCKED** (sandbox) / **PASS** (host) | host ran it; see above |
| network namespaces | **BLOCKED** (sandbox) / **PASS** (host) | namespace created and removed |
| **real rollback read-back** | **PASS on host** | 6/6, `tc` read-back in a real namespace |
| live enforcement (21-check gate) | **NOT YET RUN** | next step |
| live adaptation | **BLOCKED** / not yet run |
| CAKE / FIFO comparison | **BLOCKED** | |
| sustained stability | **BLOCKED** | |

## Real-kernel enforcement: 21/21 checks PASS at `8aecc3a8`

The traffic gate ran on the user's host and every check passed:

```
docs/evidence/gate-20261013-135720.log
PASS 1..11, 13..20   MEASURED 12 (a measurement, not a pass/fail check)
FAIL none
```

Checks that matter most for this work:

| check | result | what it establishes |
|---|---|---|
| 6 | **PASS** — `ping avg 20.059 ms` under 20 ms netem | shaping and impairment are both live on the shaped link |
| 11, 13 | PASS | per-flow counters via conntrack, **v4 and v6** |
| 14 | PASS | an IPv6 EF-marked flow is routed to `1:10` |
| 15 | PASS | per-flow flower filters install |
| 16 | PASS | a steered **IPv4** flow reaches `1:20` and ADAPTIVE receives traffic |
| **17** | **PASS** | **a rejected EF-claiming flow does not reach `1:10`** |
| 18 | PASS | a steered **IPv6** flow reaches `1:20` |
| 19 | PASS | removing the filter returns the flow to the default class |
| 20 | PASS | teardown removes the bridge's filters |

Check 17 is the classifier fix of `89b87758` being enforced by the **kernel**:
an EF claim is refused, and the refused flow does not land in the interactive
class. Until this run, that behaviour had only ever been asserted in-process.

## What the first real run exposed

3 of 6 failed initially. **Every one was a defect in the test**, and one revealed
that the in-memory double was certifying behaviour the kernel does not have.

Two facts were measured, not assumed:

| probe | result |
|---|---|
| `tc -j` on iproute2 6.1.0 | **accepted, but prints TEXT** |
| after `tc qdisc del dev X root` | veth reverts to **`qdisc noqueue 0: root`** |

The controller was correct throughout — it reads text first, and the diagnostic
confirmed it verified all four classes (`1:1 1:10 1:20 1:30`) with
`read-back source: tc-text`. The failures were:

1. the test's reader called `json.loads()` on text, returned `{}`, and every
   downstream assertion failed against a tree the kernel had actually installed;
2. "clean" was defined as *no qdisc at all*, when a veth correctly shows
   `noqueue`;
3. the double modelled `-j` as JSON, so it passed while reality failed three
   times over.

Correcting the double then exposed two more real bugs in the test — `rstrip("bit")`
strips a character *set*, so `"100000Kbit"` became `"100000K"` and `float()` raised;
and the unit table scaled Mbit by 1e-3, parsing `"100Mbit"` as 0.1 Mbps.

**This is the argument for having the double at all** — once it was made
faithful it caught bugs that would otherwise have waited for the next host run.

## Phase 7.1 — is the rollback baseline trustworthy?

The brief asks whether the expected rollback state is derived from a trustworthy
baseline rather than reconstructed from the same possibly-faulty state being
checked. Traced:

```
apply()   tree = build_tree(plan)          <- intent
          _rebuild(tree)                   <- render + execute
          state = self._read_classes()     <- observation
          verify(tree, state)              <- intent vs observation
          ...commit only if no mismatch...
          _last_good_state = state         <- the OBSERVATION, cross-checked
```

**The target is an observation that was cross-checked against intent at commit
time.** It is not the post-rollback state being tested, and it is not derived
solely from the path under test. That part is sound.

### But the trace exposed a real defect: vacuous verification

`verify()` deliberately tolerates fields the reader cannot see — a weaker
guarantee, not a wrong rate. It records those in `unverified_fields` and
**commits anyway**.

So if the reader reports classes but no rates — a plausible output under a
different kernel or `tc` format — then:

```
_last_good_state = {'1:1': {}, '1:10': {}, '1:20': {}, '1:30': {}}
```

and `compare_states` returns an **empty mismatch list**, which means "nothing
was wrong", not "everything was checked and matched".

Reproduced before the fix:

```
commit ok       : True
baseline stored : {'1:1': {}, '1:10': {}, '1:20': {}, '1:30': {}}
>>> ROLLBACK VERDICT: verified
>>> fields compared : 0
>>> rolled_back     : True
```

**The rollback reported success having compared nothing.** That is the same
defect family as the original `return True`, one level deeper, and it survived
because every existing test used a reader that reports rates.

**Fixed** in `_comparable_pairs()`: count the (class, field) pairs both sides
actually expose, and report `unverifiable` when that count is zero. Now:

```
>>> VERDICT: unverifiable | ok: False
>>> reason : the read-back exposed no comparable rate/ceil fields (target 4
             classes, actual 4 classes), so the restored state cannot be
             confirmed -- an empty comparison is not a match
```

### And the fix introduced a false negative, caught immediately

The first version compared raw keys, so a baseline keyed `1:10` and a read-back
keyed `1:0010` — the same class, printed differently — compared as zero shared
fields, and a **genuinely verified** restore would have been reported
unverifiable. The existing `test_zero_padded_handles_do_not_trigger_a_false_mismatch`
caught it. `_comparable_pairs` now canonicalises both sides.

## Skipped tests (Phase 10) — all six evaluated

Exactly six tests are skipped, all in `tests/test_rollback_live.py`:

| test | why skipped | conditional? | mandatory? | equivalent evidence? | runs on host? |
|---|---|---|---|---|---|
| `test_a_committed_plan_is_visible_to_independent_tc` | `iproute2 not on PATH` | yes — needs `ip`+`tc` | **yes** | **no** | yes, with sudo |
| `test_rollback_restores_the_known_good_tree` | same | yes | **yes** | **no** | yes |
| `test_rollback_that_cannot_be_verified_is_not_reported_as_success` | same | yes | **yes** | **no** | yes |
| `test_safe_state_is_installed_and_confirmed` | same | yes | **yes** | **no** | yes |
| `test_verification_failed_is_reachable_and_is_not_a_pass` | same | yes | **yes** | **no** | yes |
| `test_teardown_leaves_no_residue` | same | yes | no — hygiene | partially | yes |

The skip is **conditional**, not unconditional: root and `iproute2` are the only
requirements, and the user's host has neither missing nor a blocker.

**No alternative test provides equivalent evidence.** The six tests in
tests/test_rollback_live_sim.py prove the live module is *not broken* — they
execute it against an in-memory kernel double. That catches protocol and logic
errors (it caught five), but a double written by the same author as the code
under test cannot establish how a real kernel behaves.

**All six cover mandatory release requirements.** Until they run, real rollback
is unverified, and no amount of passing simulation changes that.

## Harness defect found this pass (Phase 2)

`complete: true` did not account for skipped tests. The six live tests skip
without root, `suite_verdict` counts a skip as a pass (correctly — a skip is not
a failure), so a run could report `complete: true` with the mandatory rollback
verification never having executed.

```
complete = (no blocked gates) AND (no skipped tests)
```

and the summary now prints `N test(s) skipped -- not counted as passed`.
Regression-tested in `tests/test_acceptance.py::TestCompletionAndSkips`.

## Documentation defect found this pass

Four invented test names in `classifier-final-validation.md` and three in
`fairness-policy-safety.md`. The tests were real; the names were not.

`tools/audit_claims.py` now resolves every backticked `test_*` name cited in
`docs/gap-closure/` against the actual test sources, and **a citation that
resolves to nothing reaches the exit code** — reporting DRIFT and exiting 0
would make the check decorative, which is the third instance of exactly that
shape in this project.

The fairness correction also revealed that **test_two_thousand_flows_still_sum_to_capacity
never existed**, so the "degradation over many flows: yes (2000 flows)" row was
wrong. `build_plan` splits by weight *per class*, not per flow, so flow count is
not an input to the arithmetic. Per-flow fairness is a question the policy does
not answer and no test asks.

## What must run on the host

One command, rather than four hand-typed ones:

```bash
cd ~/Desktop/Full-projects/TATA-ELXSI
sudo ./tools/host_gate.sh            # rollback + full acceptance
sudo ./tools/host_gate.sh --full     # + adaptation, CAKE comparison, 30-min soak
sudo ./tools/host_gate.sh --check    # prerequisites only, changes nothing
```

`tools/host_gate.sh` checks root, `ip`, `tc`, `iperf3` and namespace support
**before** touching anything, refuses with a non-zero exit and the message
"Nothing has been changed" when they are missing, collects everything into
`artifacts/validation/<rev>/host/`, and treats a skipped live gate as SKIPPED
rather than passing.

**Why it exists.** The blocked gates were previously described in prose, and two
of those commands named a scenario (`s4_voip_under_load`) and a system (`cake`)
that do not exist. They would have failed on a real host — after building the
testbed. Every scenario, system and flag the script uses is now regression-tested
against the real driver CLI.

**The 30-minute soak was unreachable.** Every shipped scenario is 30-40 s and
`duration_s` was hardcoded per scenario, so there was no way to run the mandated
duration. `--duration-s` was added to `run_experiments.py`; it replaces the
scenario without mutating it and leaves the defaults untouched. Verified: a
1800 s override preserves every workload and DSCP marking.

The individual commands, if you prefer to run them yourself:

```bash
sudo python3 -m unittest tests.test_rollback_live -v
sudo python3 tools/acceptance.py
sudo python3 run_experiments.py --scenario s2_wan_drop --system aciq \
    --enforce --drop 10 --drop-at 5 --seed 42
sudo python3 run_experiments.py --scenario s3_tv_and_gaming --system aciq \
    --enforce --duration-s 1800
```

**Safety.** tests/test_rollback_live.py creates its own network namespace
(`aciqrb<random>`), a veth pair inside it, and `tc` qdiscs on that pair. The
host's interfaces, routes and qdiscs are never touched; the module tears the
namespace down via `atexit`, including after a failure. If namespace creation
is unavailable it **skips** rather than falling back to a real interface.

`acceptance.py` phase 6 additionally runs testbed/gate.sh, which builds a
larger topology. Review it before running privileged. There is no dry-run mode
and none was invented.