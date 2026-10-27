"""tools/secret_scan.py — no credential-shaped strings in sources.

Scans tracked source files for token/key/password patterns and exits 1 on a
hit. Pairs with the citation audit (make lint): a fix round's final check
lets a leak you can SEE fail the build, not merely be acknowledged.

Deliberately pattern-shaped rather than list-based: a new provider's secret
will not be on an allowlist, and a variable named e.g. aws_secret cannot be
scanned for by list either.
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: Each pattern must match the shape of a secret, not the WORD appearing in
#: prose, and not a git revision sha (pure hex 40/64 = commit or SHA256SUMS
#: content, which every evidence file in this repo legitimately contains).
PATTERNS = [
    ("aws-key", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("generic-hex-secret",
     re.compile(r"(?i)\b(secret|token|passwd|password|api['_\-]?key)"
                r"['\"]?\s*[:=]\s*['\"][0-9a-f]{32,}['\"]")),
    ("b64-lookalike", re.compile(
        r"(?<![-/])(?!\w*Test\w*\b)[A-Za-z0-9+/]{40,}={0,2}\b")),
    ("private-key", re.compile("-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("netrc", re.compile(r"(^|\n)\s*machine\s+\S+\s*\n\s*login\s")),
]

#: Shapes that are NOT secrets but look like one: git revisions (hex 40) and
#: file sums (hex 64) appear in every evidence file in this repo, and paths
#: under artifacts/validation/ are quoted by commit id by design.
SAFE_SHAPES = (re.compile(r"^[0-9a-f]{40}$"), re.compile(r"^[0-9a-f]{64}$"))

SKIP_SUFFIX = {".pyc", ".log"}
SKIP_DIRS = {".git", "__pycache__", "data/runs", "data/experiments"}
#: Its OWN regression test necessarily contains the needles; skipping it
#: follows the same rule as citation audit's self-referential list.
SKIP_FILES = {"tests/test_secret_scan.py"}


def tracked_files() -> list[str]:
    ls = subprocess.run(["git", "ls-files"], capture_output=True, text=True,
                        cwd=ROOT)
    files = [l for line in ls.stdout.splitlines() if (l := line)]
    out = []
    for f in files:
        p = f.lower()
        if p.endswith(tuple(SKIP_SUFFIX)):
            continue
        if any(d in f for d in SKIP_DIRS):
            continue
        out.append(f)
    return out


def _scan_lines(lines: list[str]) -> list[tuple[str, str, str]]:
    """(rule, line_no, snippet) for anything credential-shaped in text.
    The core verdict; file-level scan_files() wraps it."""
    hits: list[tuple[str, str, str]] = []
    for line_no, line in enumerate(lines, 1):
        # Prose and code identifiers: class/def names legitimately run long,
        # URLs are not machine credentials.
        ok_meta = bool(re.match(r"^\s*(class |def |#|\*|[-a-z0-9]+:)", line)
                       or "http" in line
                       or line.lstrip().startswith("<"))
        for rule, rx in PATTERNS:
            hit = rx.search(line)
            if hit is None or ok_meta:
                continue
            token = hit.group(0)
            if any(s.fullmatch(token) for s in SAFE_SHAPES):
                continue
            # A run quoted inside a path is preceded by "/" or ":" (the
            # line's directory part); a standalone credential is flanked
            # by a boundary. Only standalone strings are candidates.
            before = line[:hit.start()]
            if hit.start() > 0 and before[-1] in "/:=,.-":
                continue
            # A line that OPENS with a repo path is quoting a location;
            # a run from a credential would not open a tracked source line
            # as a directory name.
            stripped = line.lstrip()
            if re.match(r"^[a-z0-9./_-]+\.[a-z]{2,4}\b", stripped) or \
                    stripped.startswith(("artifacts/", "data/", "docs/",
                                         "testbed/")):
                continue
            hits.append((rule, line_no, line.strip()[:120]))
    return hits


def scan_files(files: list[str] | None = None) -> list[tuple[str, str, str]]:
    """(file, rule, snippet) triples for anything credential-shaped."""
    hits: list[tuple[str, str, str]] = []
    for f in (files if files is not None else tracked_files()):
        if f in SKIP_FILES:
            continue
        if f.lower().endswith(".pdf"):     # binary: strings-scan, not file.read
            continue
        try:
            text = (ROOT / f).read_text(encoding="utf-8", errors="strict")
        except UnicodeDecodeError:
            continue    # another binary asset; UTF-8 sources are the mandate
        except OSError:
            continue
        for rule, line_no, snippet in _scan_lines(text.splitlines()):
            hits.append((f"{f}:{line_no}", rule, snippet))
    return hits


def scan_text(text: str) -> list[tuple[str, int, str]]:
    """Public hook for tests: the verdict on arbitrary text."""
    return _scan_lines(text.splitlines())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--files", nargs="*", default=None)
    hits = scan_files(ap.parse_args().files)
    for f, rule, snippet in hits:
        print(f"HIT {rule}  {f}: {snippet}")
    if hits:
        print(f"{len(hits)} secret-shaped hit(s); fix before shipping")
        return 1
    print("secret-scan: clean")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
