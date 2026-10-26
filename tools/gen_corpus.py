"""Router-vantage classifier corpus — collected LIVE, evaluated OFFLINE.

Why this exists: `tools/eval_classifier.py` scores hand-CONSTRUCTED cases, in
which the clauses were reasoned against the features they exhibit. A corpus
collected at the router vantage (conntrack only, no generator self-reports)
is the honest report on what the shipped rules do to real observed tuples.
Thresholds are NOT tuned here; nothing is fit on this data. The shipped
constants of aciq/classify.py were fixed before any of it was collected —
that is the claim, and the file the constants live in is recorded in the
evaluator's `paths_fixed` field.

Collection (needs root + the live testbed): for each of the six source
classes, run its generator pair (sink in client ns, sender in wan ns) ONCE
PER FLOW, one flow at a time, each on its own dport, poll `conntrack -L` at
the ROUTER ns, rebuild FlowFeatures through aciq.flowtrack.FlowTracker, and
write one JSON line per flow with the label it was generated under (+ a
`case` field: canonical or deliberately ambiguous). Flow tuples are recorded
so the evaluator can split fixed/held-out without class leakage (same tuple
in both is the leak). Per-class counts are FLOORED at --min-per-class: if
any class lands short the collector exits non-zero so the live step fails
loudly instead of quietly shipping a 9-flow corpus (that failure shipped
once).

Records are flat and loadable without the repo (everything needed to rebuild
FlowFeatures is in the line).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import dataclasses
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aciq.flowtrack import (ConntrackSource, FlowTracker,
                            parse_conntrack_dirs)  # noqa: E402
from aciq.features import FlowFeatures  # noqa: E402

#: label -> (client workload script, sender script, dport, extra_args, reverse).
#: Ports match the shipped generators so a mis-tagged port is obvious: the
#: port IS the label in this design, and a collision would poison every
#: record downstream. S5 f-note: update/backup reuse bulk.py; they are
#: distinct classes to the classifier (rate/shape), same port is fine because
#: each window observes exactly one class.
#:
#: software_update is a smooth constant MID-RATE shape (rate-capped, so the
#: `frac >= 0.5` bulk rule must not swallow it); cloud_backup is an UPLOAD
#: (sink elsewhere, sender home) — exactly the shape the shipped
#: cloud_backup rule looks for (tx share >= 0.8).
CORPUS_PLAN = {
    "video_call_voice": ("call.py", "call.py", 5001, [], False),
    "interactive_gaming": ("game.py", "game.py", 5002, [], False),
    "adaptive_video_streaming": ("video.py", "video.py", 5003, [], False),
    "bulk_download": ("bulk.py", "bulk.py", 5004, [], False),
    "software_update": ("bulk.py", "bulk.py", 5004,
                        ["--rate-cap", "8"], False),
    "cloud_backup": ("bulk.py", "bulk.py", 5004,
                     ["--rate-cap", "8"], True),
}

#: Deliberately AMBIGUOUS windows, T6's "unknown/ambiguous cases". Ground
#: truth is still the class the generator produced (the record says so);
#: what differs is that difficulty is real by construction, not tuned:
#:   * bulk Download at 40% of nominal capacity sits BELOW the shipped bulk
#:     frac floor at that vantage — some rows must abstain, and the strict
#:     table counts them as errors (honesty requirement, not a bug to fix);
#:   * a very low-rate update window (3 Mbps) leaves the class at the
#:     edge of the rate evidence;
#:   * streaming stays full shape but on an uncommon port so no window
#:     of the canonical plan can be confused with it.
#: Nothing in aciq/classify.py is touched by this plan — evaluation only.
AMBIGUOUS_FLOWS = 10
AMBIGUOUS_PLAN: dict[str, tuple[tuple, int]] = {
    "bulk_download": (("bulk.py", "bulk.py", 5104,
                       ["--rate-cap", "40"], False), AMBIGUOUS_FLOWS),
    "adaptive_video_streaming": (("video.py", "video.py", 5103,
                                  [], False), AMBIGUOUS_FLOWS),
    "software_update": (("bulk.py", "bulk.py", 5102,
                         ["--rate-cap", "3"], False), AMBIGUOUS_FLOWS),
}

#: 7 classes is the statement; the 7th (UNKNOWN) is never generated: it is the
#: class for flows no window generated, and it appears as prediction-only.


def features_record(label: str, feats: FlowFeatures,
                    capacity_mbps: float, case: str = "canonical") -> dict:
    f = feats.flow
    return {
        "label": label,
        "flow": {"src": f.src, "dst": f.dst, "sport": f.sport,
                 "dport": f.dport, "proto": f.proto},
        "case": case,
        "dscp": feats.dscp,
        "rx_bytes": feats.rx_bytes, "tx_bytes": feats.tx_bytes,
        "packets": feats.packets, "age_s": feats.age_s,
        "avg_packet_bytes": feats.avg_packet_bytes,
        "burstiness": feats.burstiness, "duty_cycle": feats.duty_cycle,
        "rate_mbps": feats.rate_mbps,
        "correction": None,
        "capacity_mbps": capacity_mbps,
        "t": round(time.time(), 3),
    }


class Generator:
    """One sink/sender pair, started, waited out, killed. Deterministic
    lifetime, no shell state."""

    def __init__(self, sink_script: str, listener_cmd: list[str],
                 sender_cmd: list[str]):
        self.sink_script = sink_script
        self.listener_cmd = listener_cmd
        self.sender_cmd = sender_cmd
        self.procs: list[subprocess.Popen] = []

    def __enter__(self):
        self.procs.append(subprocess.Popen(self.listener_cmd,
                                           stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL))
        return self

    def start_sender(self):
        self.procs.append(subprocess.Popen(self.sender_cmd,
                                           stdout=subprocess.DEVNULL,
                                           stderr=subprocess.DEVNULL))

    def __exit__(self, *exc):
        for p in self.procs:
            try:
                p.terminate()
                p.wait(timeout=3)
            except (subprocess.TimeoutExpired, ProcessLookupError):
                try:
                    p.kill()
                except ProcessLookupError:
                    pass
        self.procs.clear()
        return False


class NSEnv:
    """The namespace commands this tool needs. Kept as a tiny env object so
    offline tests can run the collector against fakes."""

    def __init__(self, router="router", client="client", wan="wan",
                 client_ip="10.0.1.2"):
        self.router, self.client, self.wan = router, client, wan
        self.client_ip = client_ip

    def nsexec(self, ns: str, cmd: list[str]) -> list[str]:
        return ["ip", "netns", "exec", ns] + cmd


def ns_pre(ns: str) -> list[str]:
    return ["ip", "netns", "exec", ns]


class DirectionTracker(FlowTracker):
    """FlowTracker that knows WHERE bytes sat, at corpus-vantage terms.

    The shipped tracker sums both directions (volume is what the controller
    reasons about). The corpus needs direction: the conntrack ORIGIN is
    whoever spoke first, and `orig.src == 10.0.1.2` says the home side
    initiated — reply bytes are then downstream (server payload), orig bytes
    upstream. For a backup window (home side pushes payload) this is what
    lets the tx-share rule fire at all.
    """

    def __init__(self, window: int = 10, home_src: str = "10.0.1.2"):
        super().__init__(window=window)
        self._orig: dict[str, int] = {}
        self.home_src = home_src

    def observe(self, text: str, now: float) -> None:
        seen = parse_conntrack_dirs(text)
        for key, (flow, _p, _b, orig_bytes, reply_bytes) in seen.items():
            self._orig[key] = orig_bytes if flow.src == self.home_src \
                else reply_bytes
        # Base class observes its own summed parse; the direction map is our
        # parallel state, indexed by the same identity key.
        super().observe(text, now)

    def features(self, key: str, dscp: int | None = None
                 ) -> FlowFeatures | None:
        f = super().features(key, dscp)
        if f is None:
            return None
        k = f.flow.identity
        if k in self._orig:
            orig = self._orig[k]
            total = f.rx_bytes
            return dataclasses.replace(f, tx_bytes=orig,
                                       rx_bytes=total - orig)
        return f


def collect_window(label: str, plan: tuple, env: NSEnv,
                   duration_s: float, poll_s: float,
                   workloads_dir: Path, capacity_mbps: float,
                   tracker: FlowTracker | None = None,
                   source: ConntrackSource | None = None,
                   flows: int = 1, case: str = "canonical",
                   port_offset: int = 0) -> list[dict]:
    """Run the generator `flows` times, one flow at a time, each on its OWN
    port (base dport + index [+ port_offset]).

    `port_offset` (task4-params.md) exists so a FRESH corpus can be
    generated with disjoint flow tuples: without it, a second collection
    over the same plan reproduces the same dports, and the tuple-parity
    split would place every new row in exactly the same half as the old
    corpus -- a "fresh held-out" that was not fresh. The offset shifts
    listener and sender together, so the rows stay genuine transfers on
    their own ports.

    Why one CONCURRENT sender was rejected: bulk.py's listener serves
    connections sequentially (accept -> recv until EOF), so a second
    concurrent sender sits in the accept backlog and transfers almost
    nothing — its feature row would fabricate a tiny "bulk" flow. Serial
    flows take longer wall-clock but every row is a genuine transfer.

    Why a fresh port per flow: conntrack entries OUTLIVE their flow
    (`udp`/`tcp established` timeouts exceed the next flow's window). On a
    shared port the next window's tracker would read the previous flow's
    stale entry and either duplicate it or mix two flows' byte counters.
    Distinct dports make every row self-contained; the plan's port-per-label
    property is preserved per flow (dport = base + i [+ port_offset]).
    """
    _listener, script, dport, extra_flags, reverse = plan
    wl = str(workloads_dir)
    sender_side, sink_side = (env.client, env.wan) if reverse \
        else (env.wan, env.client)
    # Dst for the sender: the SINK side's in-bridge address. Download (default):
    # sink home is 10.0.1.2; upload: sink elsewhere is 203.0.113.2.
    sink_ip = "203.0.113.2" if reverse else env.client_ip
    ps: list[dict] = []
    for i in range(flows):
        port = dport + i + port_offset
        # One tracker per FLOW: a shared ring would let earlier flows'
        # increment history be evicted while later ones still poll, and the
        # last window's stale conntrack lines would be re-read as new.
        tr = tracker or DirectionTracker(window=max(2, int(duration_s / poll_s)))
        src = source or ConntrackSource(ns=env.router)
        sink = Generator(script,
                         env.nsexec(sink_side, ["python3", f"{wl}/{script}",
                                                "--listen", "--port",
                                                str(port)]),
                         env.nsexec(sender_side,
                                    ["python3", f"{wl}/{script}",
                                     "--dst", sink_ip,
                                     "--port", str(port),
                                     "--duration", str(duration_s)]
                                    + list(extra_flags)))
        with sink:
            time.sleep(1.2)
            sink.start_sender()
            deadline = time.monotonic() + duration_s + 2.0
            while time.monotonic() < deadline:
                tr.observe(src.read(), time.monotonic())
                time.sleep(poll_s)
        for k in tr.keys():
            f = tr.features(k)
            if f is None:
                continue
            flw = f.flow
            # TCP AND UDP: a corpus with no video-call or gaming rows was a
            # tcp-only filter, not a missing generator.
            if flw.dport == port:
                ps.append(features_record(label, f, capacity_mbps, case))
    return ps


def enforce_min_counts(counts: dict[str, int], min_per_class: int,
                       classes: list[str]) -> str | None:
    """Return a failure message when a generated class is under count, else
    None. Pure so the live step's per-class floor is testable offline."""
    short = {c: counts.get(c, 0) for c in classes
             if counts.get(c, 0) < min_per_class}
    if short:
        return ("corpus under per-class minimum: "
                + ", ".join(f"{c}={n}<{min_per_class}"
                            for c, n in short.items()))
    return None


def collect_all(out: Path, duration_s: float = 6.0, poll_s: float = 1.0,
                env: NSEnv | None = None, capacity_mbps: float = 100.0,
                workloads_dir: Path | None = None,
                flows_per_class: int = 30,
                min_per_class: int = 30,
                port_offset: int = 0) -> int:
    env = env or NSEnv()
    wl = workloads_dir or ROOT / "testbed/workloads"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    print(f"corpus: {len(CORPUS_PLAN)} canonical classes x {flows_per_class} "
          f"flows + {len(AMBIGUOUS_PLAN)} ambiguous windows "
          f"x {AMBIGUOUS_FLOWS} flows, {duration_s:g} s each"
          + (f", port_offset {port_offset}" if port_offset else ""))
    for label, plan in CORPUS_PLAN.items():
        rows.extend(collect_window(label, plan, env, duration_s, poll_s,
                                   wl, capacity_mbps,
                                   flows=flows_per_class,
                                   port_offset=port_offset))
    for label, (plan, n) in AMBIGUOUS_PLAN.items():
        rows.extend(collect_window(label, plan, env, duration_s, poll_s,
                                   wl, capacity_mbps, flows=n,
                                   case="ambiguous",
                                   port_offset=port_offset))
    with out.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    counts: dict[str, int] = {}
    for r in rows:
        counts[r["label"]] = counts.get(r["label"], 0) + 1
    counts_path = out.with_name("counts.json")
    counts_path.write_text(json.dumps(
        {"per_label": counts, "n_total": len(rows)}, indent=1) + "\n")
    print(f"corpus: {len(rows)} flows -> {out}")
    print("corpus per-label counts:", json.dumps(counts, sort_keys=True))
    fatal = enforce_min_counts(counts, min_per_class,
                               sorted({**CORPUS_PLAN, **AMBIGUOUS_PLAN}))
    if fatal:
        print(f"corpus FAILED the per-class floor ({fatal})")
        return 1
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "data/experiments/classifier_corpus/corpus.jsonl")
    ap.add_argument("--duration", type=float, default=6.0)
    ap.add_argument("--poll-s", type=float, default=1.0)
    ap.add_argument("--flows-per-class", type=int, default=30)
    ap.add_argument("--min-per-class", type=int, default=30)
    ap.add_argument("--port-offset", type=int, default=0,
                    help="shift every plan's dport base by this (task4-params.md: "
                         "a nonzero offset makes a fresh corpus's flow tuples "
                         "disjoint from the previous one, so the tuple-parity "
                         "split genuinely re-splits)")
    a = ap.parse_args()
    if subprocess.run(["id", "-u"],
                      stdout=subprocess.PIPE, text=True).stdout.strip() != "0":
        print("must run as root (ip netns exec conntrack -L)")
        return 1
    return collect_all(a.out, a.duration, a.poll_s,
                       flows_per_class=a.flows_per_class,
                       min_per_class=a.min_per_class,
                       port_offset=a.port_offset)


if __name__ == "__main__":
    raise SystemExit(main())
