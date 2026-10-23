"""Router-vantage classifier corpus — collected LIVE, evaluated OFFLINE.

Why this exists: `tools/eval_classifier.py` scores hand-CONSTRUCTED cases, in
which the clauses were reasoned against the features they exhibit. A corpus
collected at the router vantage (conntrack only, no generator self-reports)
is the honest report on what the shipped rules do to real observed tuples.
Thresholds are NOT tuned here; nothing is fit on this data. The shipped
constants of aciq/classify.py were fixed before any of it was collected —
that is the claim, and the file the constants live in is recorded in the
evaluator's `paths_fixed` field.

Collection (needs root + the live testbed): for each of the five source
classes, run ONE generator pair (sink in client ns, sender in wan ns) on its
dedicated port, poll `conntrack -L` at the ROUTER ns, rebuild FlowFeatures
through aciq.flowtrack.FlowTracker, and write one JSON line per flow with the
label it was generated under. Flow tuples are recorded so the evaluator can
split fixed/held-out without class leakage (same tuple in both is the leak).

Records are flat and loadable without the repo (everything needed to rebuild
FlowFeatures is in the line).
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from aciq.flowtrack import ConntrackSource, FlowTracker  # noqa: E402
from aciq.features import FlowFeatures  # noqa: E402

#: label -> (client workload script, sender script, dport).
#: Ports match the shipped generators so a mis-tagged port is obvious: the
#: port IS the label in this design, and a collision would poison every
#: record downstream. S5 f-note: update/backup reuse bulk.py; they are
#: distinct classes to the classifier (rate/shape), same port is fine because
#: each window observes exactly one class.
CORPUS_PLAN = {
    "video_call_voice": ("call.py", "call.py", 5001),
    "interactive_gaming": ("game.py", "game.py", 5002),
    "adaptive_video_streaming": ("video.py", "video.py", 5003),
    "bulk_download": ("bulk.py", "bulk.py", 5004),
    "software_update": ("bulk.py", "bulk.py", 5004),
    "cloud_backup": ("bulk.py", "bulk.py", 5004),
}

#: 7 classes is the statement; the 7th (UNKNOWN) is never generated: it is the
#: class for flows no window generated, and it appears as prediction-only.


def features_record(label: str, feats: FlowFeatures,
                    capacity_mbps: float) -> dict:
    f = feats.flow
    return {
        "label": label,
        "flow": {"src": f.src, "dst": f.dst, "sport": f.sport,
                 "dport": f.dport, "proto": f.proto},
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


def collect_window(label: str, plan: tuple, env: NSEnv,
                   duration_s: float, poll_s: float,
                   workloads_dir: Path, capacity_mbps: float,
                   extra_flags: list[str] | None = None,
                   tracker: FlowTracker | None = None,
                   source: ConntrackSource | None = None) -> list[dict]:
    _, script, dport = plan
    wl = str(workloads_dir)
    tracker = tracker or FlowTracker(window=max(2, int(duration_s / poll_s)))
    source = source or ConntrackSource(ns=env.router)
    sink = Generator(script,
                     env.nsexec(env.client, ["python3", f"{wl}/{script}",
                                             "--listen", "--port", str(dport)]),
                     env.nsexec(env.wan, ["python3", f"{wl}/{script}",
                                          "--dst", env.client_ip,
                                          "--port", str(dport),
                                          "--duration", str(duration_s)]
                                   + (extra_flags or [])))
    with sink:
        time.sleep(1.5)
        sink.start_sender()
        deadline = time.monotonic() + duration_s + 2.0
        while time.monotonic() < deadline:
            tracker.observe(source.read(), time.monotonic())
            time.sleep(poll_s)
    ps = []
    for k in tracker.keys():
        f = tracker.features(k)
        if f is None:
            continue
        flw = f.flow
        if flw.dport == dport and flw.proto == "tcp":
            ps.append(features_record(label, f, capacity_mbps))
    return ps


def collect_all(out: Path, duration_s: float = 20.0, poll_s: float = 1.0,
                env: NSEnv | None = None, capacity_mbps: float = 100.0,
                workloads_dir: Path | None = None) -> int:
    env = env or NSEnv()
    wl = workloads_dir or ROOT / "testbed/workloads"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []
    for label, plan in CORPUS_PLAN.items():
        rows.extend(collect_window(label, plan, env, duration_s, poll_s,
                                   wl, capacity_mbps))
    with out.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    print(f"corpus: {len(rows)} flows -> {out}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path,
                    default=ROOT / "data/experiments/classifier_corpus/corpus.jsonl")
    ap.add_argument("--duration", type=float, default=20.0)
    ap.add_argument("--poll-s", type=float, default=1.0)
    a = ap.parse_args()
    if subprocess.run(["id", "-u"]).returncode != 0:
        print("must run as root (ip netns exec conntrack -L)")
        return 1
    return collect_all(a.out, a.duration, a.poll_s)


if __name__ == "__main__":
    raise SystemExit(main())
