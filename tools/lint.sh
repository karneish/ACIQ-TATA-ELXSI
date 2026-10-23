#!/usr/bin/env bash
# Static analysis. Needs no root, no network namespace, no tc.
#
# Separate from tools/acceptance.py because ruff installed with
# `pip install --user` lives in the invoking user's site-packages, which
# `sudo python3` cannot see. So a sudo'd acceptance run reports the lint gate
# BLOCKED even when ruff is installed and working -- which is exactly what
# happened on the host. Running lint as yourself, where ruff actually is, is
# the honest way to check it.
set -uo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.." || exit 1

run_ruff() {
  if python3 -m ruff --version >/dev/null 2>&1; then
    python3 -m ruff check .
  elif command -v ruff >/dev/null 2>&1; then
    ruff check .
  else
    return 127
  fi
}

# Record the result, revision-stamped, exactly like every other piece of
# evidence in this project.
#
# This exists because the acceptance harness runs under sudo, where ruff
# installed with `pip install --user` is invisible -- /usr/bin/python3 on this
# host has no pip at all. So the harness could never run lint itself and would
# report BLOCKED forever on a machine where lint demonstrably passes.
#
# Every other gate already judges from revision-stamped evidence on disk. Lint
# should not be the one exception, and inventing a mechanism for it would have
# been worse than reusing this one.
REV="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
REC="artifacts/validation/$(git rev-parse --short HEAD 2>/dev/null || echo unknown)/lint.json"

out="$(run_ruff 2>&1)"
rc=$?

if [ "$rc" -eq 127 ]; then
  echo "ruff is not installed. Install it with:" >&2
  echo "    python3 -m pip install --user ruff" >&2
  exit 2
fi

mkdir -p "$(dirname "$REC")" 2>/dev/null || true
printf '{"revision": "%s", "exit": %d, "findings": %d}\n' \
  "$REV" "$rc" "$(printf '%s\n' "$out" | grep -cE '^[a-zA-Z].*:[0-9]+:[0-9]+:')" \
  > "$REC" 2>/dev/null || true

printf '%s\n' "$out"
exit "$rc"
