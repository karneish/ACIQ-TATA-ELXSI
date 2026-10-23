#!/usr/bin/env bash
# Renders the documentation diagrams to SVG with graphviz, IF graphviz is
# installed. The script is honest about what it did: missing `dot` is reported
# as "diagrams not rendered", never as success.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v dot >/dev/null 2>&1; then
    echo "graphviz 'dot' not found: diagrams NOT rendered"
    exit 0
fi
mkdir -p docs/diagrams/svg
for src in docs/diagrams/*.dot; do
    dot -Tsvg "$src" -o "docs/diagrams/svg/$(basename "${src%.dot}").svg"
    echo "rendered docs/diagrams/svg/$(basename "${src%.dot}").svg"
done
