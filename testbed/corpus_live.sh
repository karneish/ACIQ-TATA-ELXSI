#!/usr/bin/env bash
# testbed/corpus_live.sh — collect the router-vantage classifier corpus.
# Needs the live testbed (sudo -- make setup first). ~150 s at defaults.
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/corpus_live.sh
set -euo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
OUT="data/experiments/classifier_corpus/corpus.jsonl"
mkdir -p data/experiments/classifier_corpus

testbed/cleanup.sh 2>/dev/null || true
testbed/setup.sh >/dev/null

echo "[corpus] windows: 6 classes x 20 s"
"$PY" tools/gen_corpus.py --out "$OUT" \
  2>&1 | tee testbed/logs/corpus-$(date +%Y%m%d-%H%M%S).log
echo "[corpus] offline evaluation (thresholds were fixed before this data existed)"
"$PY" tools/eval_corpus.py
echo "[corpus] done"
