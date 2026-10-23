#!/usr/bin/env python3
from aciq.scale_harness import ScaleHarness
import sys

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "artifacts/scale_simulated.json"
    print(ScaleHarness().write_report(out))
