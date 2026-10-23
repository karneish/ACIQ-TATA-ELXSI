#!/usr/bin/env python3
"""Audit every claim in the documentation against the code and the evidence.

§20. The point is that this is *mechanical*: a claim is supported if the symbol
it names exists, the constant it quotes matches, or the artefact it cites exists
and says what is claimed. A claim whose evidence is missing is reported, not
quietly left.

This does not decide whether a claim is *true* -- it decides whether the
repository contains the thing the claim rests on. Claims about measurements are
checked against the stored artefacts; claims about behaviour are checked for the
code path that implements them.
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").glob("*.md"))

#: Phrases §20 names explicitly. Each must be either justified by evidence or
#: absent.
RED_FLAG_PHRASES = [
    "fully adaptive", "real-time", "production-ready", "production ready",
    "zero packet loss", "zero-loss", "guaranteed fairness", "outperforms cake",
    "all tests passing", "fully automated", "never fails", "always correct",
    "zero risk", "fully validated", "production grade",
]

#: Claims that are legitimate *if* the evidence exists. Checked structurally.
EVIDENCE_CLAIMS = [
    ("p = 0.0312", "b0_fifo comparison", "data/matrix6"),
    ("0.015625", "lease Wilcoxon", "data/ab_lease_42"),
    ("92.6", "gate check 6 (stale value)", "docs/evidence"),
    ("92.7", "gate check 6", "docs/evidence"),
    ("12.92", "withdrawn lease figure", "docs/limitations.md"),
    ("20 PASS", "gate summary", "docs/evidence"),
]


def scan_flags() -> list[dict]:
    hits = []
    for d in DOCS:
        text = d.read_text(errors="replace").lower()
        for phrase in RED_FLAG_PHRASES:
            for m in re.finditer(re.escape(phrase), text):
                line = text[:m.start()].count("\n") + 1
                ctx = d.read_text(errors="replace").split("\n")[line - 1]
                hits.append({"doc": d.name, "line": line, "phrase": phrase,
                             "context": ctx.strip()[:140]})
    return hits


def scan_evidence() -> list[dict]:
    out = []
    for phrase, what, where in EVIDENCE_CLAIMS:
        found_in = [d.name for d in DOCS
                    if phrase.lower() in d.read_text(errors="replace").lower()]
        # Is the cited evidence actually present?
        target = ROOT / where
        if where.startswith("data/"):
            # A run tree is evidence if it contains results, not merely a
            # directory of the right name.
            present = bool(glob.glob(f"{where}/**/result.json", recursive=True))
        elif target.is_dir():
            present = bool(list(target.glob("*.log"))) or bool(
                list(target.glob("*.json")))
        else:
            present = target.exists()
        # Present on disk is not enough. docs/evidence/*.log was covered by the
        # blanket `*.log` ignore rule, so every gate log the documentation
        # cites was absent from the repository -- a fresh clone got citations
        # pointing at files that were not there. Presence must mean *tracked*.
        tracked = _is_tracked(where)
        out.append({"claim": phrase, "what": what, "evidence": where,
                    "evidence_present": present,
                    "evidence_tracked": tracked,
                    "cited_in": found_in})
    return out


def _is_tracked(where: str) -> bool:
    """Is the cited evidence actually committed?

    Uses `git ls-files` on the *tracked* view rather than the filesystem: a
    file that exists locally but is ignored will not be in a clone, and a
    citation into it does not survive publication.
    """
    import subprocess
    path = ROOT / where
    try:
        if path.is_dir():
            r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--",
                                where], capture_output=True, text=True,
                               timeout=30)
            return any(l.strip() for l in r.stdout.splitlines())
        r = subprocess.run(["git", "-C", str(ROOT), "ls-files", "--error-unmatch",
                            str(path.relative_to(ROOT))],
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError, ValueError):
        return False


def check_code_claims() -> list[dict]:
    """Constants quoted in the docs must match the code."""
    sys.path.insert(0, str(ROOT))
    from aciq import api, capacity, classify, report, shield   # noqa: E402

    checks = [
        ("SAT_OVERLIMIT_MIN", capacity.SAT_OVERLIMIT_MIN, 3000.0),
        ("BACKLOG_MIN_BYTES", capacity.BACKLOG_MIN_BYTES, 1024),
        ("MIN_SAMPLES_FOR_PERCENTILES",
         __import__("aciq.measure", fromlist=["x"]).MIN_SAMPLES_FOR_PERCENTILES, 10),
        ("BULK_MIN_CAPACITY_FRAC", classify.BULK_MIN_CAPACITY_FRAC, 0.5),
        ("EF_FAST_CONFLICT_CAPACITY_FRAC",
         classify.EF_FAST_CONFLICT_CAPACITY_FRAC, 0.5),
        ("MIN_PKT_CONF", classify.MIN_CONFIDENCE, 0.5),
        ("DROP_RATE_LIMIT", shield.DROP_RATE_LIMIT, 5000.0),
        ("OVERLIMIT_RATE_LIMIT", shield.OVERLIMIT_RATE_LIMIT, 5000.0),
        ("MIN_PAIRS_FOR_PVALUE", report.MIN_PAIRS_FOR_PVALUE, 6),
        ("MAX_BODY_BYTES", api.MAX_BODY_BYTES, 64 * 1024),
        ("RATE_LIMIT_WRITES", api.RATE_LIMIT_WRITES, 30),
    ]
    return [{"constant": n, "code": c, "documented": d, "agrees": c == d}
            for n, c, d in checks]


def check_cited_tests() -> list[dict]:
    """Every `test_*` name cited in docs/gap-closure/ must exist.

    Citing a test that does not exist is the documentation equivalent of a
    number that does not reconcile: it reads as evidence and checks nothing.
    This caught four invented test names in classifier-final-validation.md.
    """
    import re as _re
    tests = ROOT / "tests"
    defined: set[str] = set()
    for f in sorted(tests.glob("test_*.py")):
        defined |= set(_re.findall(r"def (test_\w+)", f.read_text()))
    # A correction note has to be able to name the bad name it is correcting.
    # Lines that say so are exempt -- otherwise documenting a fix trips the very
    # check the fix introduced, which is how this file ended up failing its own
    # audit after being written to pass it.
    exempt = _re.compile(r"never existed|does not exist|do not exist|"
                         r"not a real test|invented|was wrong", _re.I)
    cited: dict[str, list[str]] = {}
    for doc in sorted((ROOT / "docs" / "gap-closure").glob("*.md")):
        for line in doc.read_text().splitlines():
            if exempt.search(line):
                continue
            for name in _re.findall(r"`(test_[A-Za-z0-9_]+)`", line):
                cited.setdefault(name, []).append(doc.name)
    out = []
    for name, where in sorted(cited.items()):
        # a trailing `*` is a deliberate wildcard, e.g. `test_missing_*`
        if name.endswith("*"):
            prefix = name[:-1]
            found = any(d.startswith(prefix) for d in defined)
        else:
            found = name in defined
        out.append({"test": name, "defined": found,
                    "cited_in": sorted(set(where))})
    return out


def parse_suite_status(text: str) -> dict:
    """Read unittest's summary. Pure, so it can be unit-tested.

    `endswith("OK")` was the previous implementation and it broke as soon as
    unittest started reporting skips: `OK (skipped=6)` does not end in `OK`, so
    a fully passing suite was reported as failed. Skips are expected here -- the
    live kernel tests skip in any sandbox -- so a parser that cannot read them
    makes the audit wrong in exactly the environment it is most needed.
    """
    lines = text.strip().splitlines()
    status = lines[-1].strip() if lines else ""
    m = re.search(r"Ran (\d+) tests?", text)
    skipped = re.search(r"skipped=(\d+)", text)
    failed = re.search(r"(?:failures|errors)=(\d+)", text)
    return {"ran": int(m.group(1)) if m else None,
            "ok": bool(re.fullmatch(r"OK(?: \(.*\))?", status)),
            "skipped": int(skipped.group(1)) if skipped else 0,
            "failures": int(failed.group(1)) if failed else 0,
            "status": status}


def check_test_count() -> dict:
    import subprocess
    r = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."],
        cwd=ROOT, capture_output=True, text=True, timeout=900)
    d = parse_suite_status(r.stderr)
    d["exit"] = r.returncode
    return d


def scan_path_citations() -> list[dict]:
    """Every path-shaped string in the tracked tree must resolve.

    The fixed EVIDENCE_CLAIMS list above can only check the citations somebody
    remembered to add to it. This checks the other kind: a path written into a
    document or a comment, which a reader is expected to be able to open.

    Three defects of this shape were found and fixed by hand, and each of them
    was in a document that claimed to be checkable:

      * docs/gap-closure/classifier-before-after.md named the before-matrix as
        artifacts/validation/89b87758/classifier-before.txt, which is in
        artifacts/validation/6a22208c/.
      * docs/limitations.md pointed at data/leaseA/README.md, which has never
        existed in this repository.
      * every published artifacts/validation/<rev>/acceptance.json names the log
        each phase wrote, in its "log" field, and none of those logs was
        committed -- 289 pointers to nothing.

    The last one is why the scan looks at JSON as well as prose: a gate result
    that names a log it does not ship is a claim a reader cannot check.

    A path that is a PREFIX or a PATTERN is not a broken citation -- `docs/evidence/gate-`
    and `data/host_gate_congested_` name a family, not a file. Neither is a path
    that is a runtime output rather than a committed artefact: `data/leases.json`
    and `data/corrections.jsonl` are written by the controller as it runs.
    Those are listed in RUNTIME_OUTPUTS.
    """
    import subprocess
    import re

    tracked = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files"],
        capture_output=True, text=True, timeout=60).stdout.split("\n")
    tracked = [t for t in tracked if t]

    # Runtime-written paths: the controller creates these, they are not evidence.
    runtime_outputs = {
        "data/leases.json", "data/corrections.jsonl", "data/REPORT.md",
        "data/COMPARISON.md", "aciq/scratch",
    }
    # Paths that exist only inside a test's own fixture or a doctest-style
    # example, where the whole point is that the file is absent.
    deliberate_absent = {"data/does_not_exist_at_all"}

    # A path-shaped token: a directory of the project, then a path.
    pat = re.compile(
        r"\b((?:docs|artifacts|data|testbed|aciq|tools|tests)/"
        r"[A-Za-z0-9_][A-Za-z0-9_./-]*)")

    seen: dict[str, set[str]] = {}
    # Files that QUOTE broken paths on purpose: this tool's own source (it
    # names them in the docstring of this function as the examples it is
    # written for) and the test that documents the defect. A finding reported
    # by this tool is not itself a finding.
    SELF_REFERENTIAL = {"tools/audit_claims.py", "tests/test_acceptance.py"}
    for f in tracked:
        if not f.endswith((".md", ".py", ".sh", ".json", ".toml")):
            continue
        # This tool's own output records the paths it is complaining about, so
        # scanning it would report every finding back as a new one.
        if f == "docs/gap-closure/claim-audit.json":
            continue
        try:
            lines = (ROOT / f).read_text(errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            # A path that appears only in a command line is an example of where
            # to PUT an output, not a pointer at something that is published.
            # `--results-dir data/e2e` writes a directory that is not in the
            # repository, and its absence is not a broken citation.
            if re.search(r"--[a-z-]+\s+\S*$", line) and re.search(
                    r"--results-dir|--out|--report|--samples|--dir\b", line):
                continue
            for m in pat.finditer(line):
                p = m.group(1).rstrip(".,;:)`\"'")
                if p.endswith("/"):
                    continue
                seen.setdefault(p, set()).add(f)

    # A path that ends in a separator is a PREFIX, not a file: `docs/evidence/gate-`
    # and `testbed/logs/gate-` name a family of logs, and `tests/test_` names a
    # family of test modules. A reader following one of those is looking for a
    # member of the family, and a missing family is a different defect.
    PREFIX_FAMILIES = ("docs/evidence/gate-", "docs/evidence/rollback-live-",
                        "testbed/logs/gate-", "testbed/logs/rollback-live-",
                        "tests/test_")

    # A path that a document says is NOT YET WRITTEN is a documented gap, not
    # a broken citation: the whole point of the sentence is that the file does
    # not exist. `testbed/fault_inject.sh` is named that way in the
    # enforcement-failure-testing report -- once as "not yet written" and once
    # in a defect row whose action is to WRITE it.
    NOT_YET_WRITTEN = re.compile(
        r"not\s+yet\s+written|does\s+not\s+exist|not\s+written\s+yet|"
        r"to\s+be\s+written|never\s+written|not\s+exist|TODO|"
        r"\bwrite\b", re.I)

    out = []
    for p, where in sorted(seen.items()):
        if p in runtime_outputs or p in deliberate_absent:
            continue
        if "*" in p or "<" in p:            # a family, not a file
            continue
        if p in PREFIX_FAMILIES:
            continue
        # This tool's own source quotes the broken paths it is describing, in
        # the docstring of scan_path_citations and in the comments above. Those
        # are the EXAMPLES of the defect, not instances of it, so a finding
        # reported by this tool is not itself a finding. The same applies to
        # the test that documents the defect: it has to name the broken paths
        # to be a regression test for them.
        if where and all(w in SELF_REFERENTIAL for w in where):
            continue
        # A path quoted inside a captured error message is evidence OF a
        # failure, not a pointer at a published file. host_gate.sh records the
        # tee error it hit; that text names a log that was never written, which
        # is the bug the comment is explaining.
        #
        # A path a document says is NOT YET WRITTEN is a documented gap, not a
        # broken citation: the whole point of the sentence is that the file
        # does not exist. `testbed/fault_inject.sh` is named that way.
        #
        # Either way the citation is excused when EVERY line that mentions the
        # path says so -- a document that points at a missing file as if it
        # existed is still broken, and that is the case this must not excuse.
        def _excused(w: str, path: str = p) -> bool:
            fp = ROOT / w
            if not fp.is_file():
                return False
            lines = [ln for ln in fp.read_text(errors="replace").splitlines()
                     if path in ln]
            if not lines:
                return False
            return all(
                NOT_YET_WRITTEN.search(ln)
                or re.search(r"(tee|error|Error|ERROR|no such file|failed|"
                             r"never|not\s+been)\b", ln)
                for ln in lines)

        if where and all(_excused(w) for w in where):
            continue
        if p.startswith("data/host_gate"):
            # `data/host_gate_congested_` and friends are PREFIXES: the
            # documents write them as `data/host_gate_{congested_,}{aciq,...}`
            # to name a family of directories. The families themselves exist.
            if not list((ROOT / "data").glob("host_gate*")):
                out.append({"path": p, "cited_in": sorted(where),
                            "reason": "no such directory family"})
            continue
        # A directory citation resolves if the directory exists.
        if (ROOT / p).is_dir():
            continue
        if not (ROOT / p).exists():
            out.append({"path": p, "cited_in": sorted(where),
                        "reason": "not in the tree"})
            continue
        if not _is_tracked(p):
            out.append({"path": p, "cited_in": sorted(where),
                        "reason": "exists but is NOT committed"})
    return out


def main() -> int:
    print("=== claim audit ===\n")

    print("-- constants quoted in the docs vs the code --")
    cc = check_code_claims()
    bad = [c for c in cc if not c["agrees"]]
    for c in cc:
        print(f"  [{'ok ' if c['agrees'] else 'DRIFT'}] {c['constant']:<32} "
              f"code={c['code']} documented={c['documented']}")

    print("\n-- test names cited in docs/gap-closure/ --")
    tc = check_cited_tests()
    for t in tc:
        if t["test"].endswith("*"):
            continue
        mark = "ok " if t["defined"] else "DRIFT"
        print(f"  [{mark}] {t['test']:<56} {', '.join(t['cited_in'])}")
    missing = [t for t in tc if not t["defined"]]

    print("\n-- evidence cited by claims --")
    ec = scan_evidence()
    for e in ec:
        if not e["evidence_present"]:
            st = "MISSING"
        elif not e.get("evidence_tracked", True):
            st = "UNTRACKED"
        else:
            st = "present"
        print(f"  [{st:<9}] {e['claim']:<12} ({e['what']}) -> {e['evidence']}")
    untracked_ev = [e for e in ec
                    if e["evidence_present"] and not e.get("evidence_tracked", True)]
    ev_missing = [e for e in ec if not e["evidence_present"]]
    if untracked_ev:
        print("  ^ cited evidence exists locally but is NOT committed; a "
              "clone would have a broken citation")

    print("\n-- path citations that do not resolve --")
    pc = scan_path_citations()
    if not pc:
        print("  every path-shaped citation resolves to a committed file")
    for c in pc:
        print(f"  [BROKEN  ] {c['path']}  ({c['reason']})")
        print(f"             cited in: {', '.join(c['cited_in'][:4])}")

    print("\n-- red-flag phrases --")
    flags = scan_flags()
    if not flags:
        print("  none found")
    for f in flags:
        print(f"  {f['doc']}:{f['line']}  '{f['phrase']}'")
        print(f"      {f['context']}")

    print("\n-- test suite --")
    t = check_test_count()
    print(f"  ran {t['ran']} tests, ok={t['ok']}, exit={t['exit']}"
          + (f", {t['skipped']} skipped" if t["skipped"] else ""))

    summary = {"constants_disagree": bad, "evidence": ec,
               "evidence_untracked": untracked_ev,
               "broken_path_citations": pc,
               "red_flags": flags, "tests": t,
               "cited_tests_missing": missing}
    (ROOT / "docs" / "gap-closure" / "claim-audit.json").write_text(
        json.dumps(summary, indent=2, default=str) + "\n")
    print("\n  wrote docs/gap-closure/claim-audit.json")
    if missing:
        print(f"  {len(missing)} cited test name(s) do not exist")
    # A test-name citation that resolves to nothing is exactly as much a
    # documentation defect as a constant that disagrees with the code, so it
    # has to reach the exit code. Reporting DRIFT and exiting 0 would make the
    # check decorative -- the same "recorded, printed, never consulted" shape
    # already found in this file and in tools/acceptance.py.
    #
    # The same applies to a path citation that resolves to nothing. A document
    # that points at a file the reader cannot open is a claim that cannot be
    # checked, and the three that were found by hand (see scan_path_citations)
    # were all in documents that describe themselves as checkable.
    return 1 if (bad or flags or missing or ev_missing or untracked_ev
                 or pc) else 0


if __name__ == "__main__":
    raise SystemExit(main())