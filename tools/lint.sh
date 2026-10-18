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

if python3 -m ruff --version >/dev/null 2>&1; then
  exec python3 -m ruff check .
elif command -v ruff >/dev/null 2>&1; then
  exec ruff check .
fi

echo "ruff is not installed. Install it with:" >&2
echo "    python3 -m pip install --user ruff" >&2
echo "or, to make it visible to a sudo'd acceptance run:" >&2
echo "    sudo python3 -m pip install ruff" >&2
exit 2
