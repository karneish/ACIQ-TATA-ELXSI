#!/usr/bin/env bash
# testbed/corpus_live.sh — collect the router-vantage classifier corpus.
# Needs the live testbed (sudo -- make setup first). ~35 min at defaults
# (6 classes x 30 one-flow windows + 3 ambiguous windows x 10 flows; the
# per-flow serial design exists because bulk.py's listener serves
# connections one at a time — concurrent senders would sit in the accept
# backlog and fabricate near-zero "bulk" rows). Fails loudly if any class
# lands under 30 flows.
#   sudo env ACIQ_VENV=/home/mekarz/aciq-venv ./testbed/corpus_live.sh
set -euo pipefail
cd "$(dirname "$0")/.."
VENV="${ACIQ_VENV:-/home/mekarz/aciq-venv}"
PY="$VENV/bin/python"; [ -x "$PY" ] || PY=python3
OUT="data/experiments/classifier_corpus/corpus.jsonl"
mkdir -p data/experiments/classifier_corpus

testbed/cleanup.sh 2>/dev/null || true
# setup is LOGGED, not voided: an unexplained abort at 09:51 on 2026-10-24 died
# between "id -u" and the corpus header and every shard of why was dropped to
# the pipe buffer -- a setup failure silently the same shape as nothing.
testbed/setup.sh 2>&1 | tee testbed/logs/corpus-setup-$(date +%Y%m%d-%H%M%S).log

echo "[corpus] per-flow windows: 6 classes x 30 flows + 3 ambiguous x 10, ~6 s each (~35 min)"
# -u: the collector prints nothing default-swallowed; its early crash must not
# be indistinguishable from no output. (Same 09:51 abort: print buffering kept
# even the header from reaching tee.)
"$PY" -u tools/gen_corpus.py --out "$OUT" \
  2>&1 | tee testbed/logs/corpus-$(date +%Y%m%d-%H%M%S).log
echo "[corpus] offline evaluation (thresholds were fixed before this data existed)"
"$PY" tools/eval_corpus.py
echo "[corpus] done"
