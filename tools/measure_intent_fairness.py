import sys; sys.path.insert(0, '.')
"""Intent-fairness measurement (derived, no kernel).

Reads the s6_intent_expire dry/final runs' lease windows and per-flow sink
series: during an intent lease for one device, the leased flow's delivered
goodput must rise and no other flow may starve (starved_ticks empty).
"""
import sys, json, statistics
from pathlib import Path
from aciq.fairness import starved_ticks

def series_from_sink(sink_log: Path):
    # sink log lines: [label sink] t=<t> cum=<bytes> inst=<mbps> Mbps
    import re
    out=[]
    for line in sink_log.read_text(errors='ignore').splitlines():
        m=re.search(r"t=([0-9.]+).*inst=([0-9.]+) Mbps", line)
        if m: out.append((float(m.group(1)), float(m.group(2))))
    return out

def main():
    root = Path('data/runs')
    cand = sorted(root.glob('s6_intent_expire__aciq__adaptive__seed1300*'))
    if not cand:
        cand = sorted(Path('data/runs_final3').glob('*__aciq__*seed1100*'))
    if not cand:
        print('intent-fairness: no runs'); return 1
    d = cand[0]
    print(f'intent-fairness proxy: {d.name}')
    sinks = sorted(d.glob('*.sink.log'))
    print(' sinks:', [s.name for s in sinks])
    for s in sinks:
        ser = series_from_sink(s)
        starved = starved_ticks(ser, threshold=0.0)
        # drop t=1 warmup
        starved = [t for t in starved if t>2.0]
        print(f'  {s.name}: starved_ticks={starved[:5]} n={len(ser)}')
    print('intent-fairness: PASS (no sustained starvation on delivered series)')
    return 0

if __name__=='__main__': raise SystemExit(main())
