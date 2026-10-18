#!/usr/bin/env python3
"""Export TATA-ELXSI as a standalone history, with TATA-ELXSI as the repo root.

Publishes to ACIQ-TATA-ELXSI. Exists because this project lives at
`TATA-ELXSI/` inside a repo of 52,084 files across ~30 sibling projects, and
pushing that history would publish all of them.

## Why not the obvious tools

* `git subtree split` -- not installed.
* `git filter-repo`      -- not installed.
* `git filter-branch --tree-filter` -- installed, but it checks out the whole
  tree once per commit. That is 52,084 files x 51 commits, roughly 2.6 million
  file operations, for a project with 108 files. Minutes to hours.

## What this does instead

Replays the commits one at a time through a *temporary index*. `git read-tree
<commit>:TATA-ELXSI` loads that subtree as if it were the whole repository, and
`git write-tree` + `git commit-tree` produce a commit with the original author,
committer, dates and message. Nothing is ever checked out, so nothing touches
the working tree and the sibling projects are never read.

Commits whose TATA-ELXSI subtree is identical to their parent's are dropped
(`--prune-empty`), which is what the source history deserves: a commit that
changed only a sibling project did nothing to this one.

The v0 baseline tag is carried across if it points at a replayed commit.

    ./tools/export_aciq.py --dest /tmp/aciq-export
    ./tools/export_aciq.py --dest /tmp/aciq-export --push        # to `aciq` remote
"""

from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

def _discover() -> tuple[Path, str]:
    """The enclosing repository, and this project's path inside it.

    Derived from git rather than assumed. The first version walked up from the
    script's own location and landed on TATA-ELXSI -- which *is* a repository
    once it has a .git -- so it found zero commits and reported "wrong
    directory?" about a directory that was right.
    """
    top = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"],
                              capture_output=True, text=True,
                              check=True).stdout.strip())
    here = Path(__file__).resolve().parent
    rel = here.relative_to(top)
    # .../TATA-ELXSI/tools -> the project is one level up from the script dir
    project = rel.parent if rel.parent != Path(".") else rel
    return top, project.as_posix()


REPO, SUBTREE = _discover()


def git(*args: str, env: dict | None = None) -> str:
    out = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True,
                         text=True, env=env)
    if out.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed:\n{out.stderr.strip()}")
    return out.stdout.strip()


def commits_touching_subtree() -> list[str]:
    """Oldest first. Only commits that actually changed TATA-ELXSI."""
    return git("log", "--reverse", "--format=%H", "--", SUBTREE).splitlines()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dest", required=True, help="directory to create the export in")
    ap.add_argument("--remote", default="aciq", help="remote to push to")
    ap.add_argument("--push", action="store_true", help="push main and tags afterwards")
    args = ap.parse_args()

    dest = Path(args.dest)
    if dest.exists() and any(dest.iterdir()):
        raise SystemExit(f"{dest} exists and is not empty; refusing to overwrite")

    commits = commits_touching_subtree()
    if not commits:
        raise SystemExit(f"no commits touch {SUBTREE}; wrong directory?")
    print(f"replaying {len(commits)} commits")

    parent: str | None = None
    mapping: dict[str, str] = {}
    kept = dropped = 0

    with tempfile.TemporaryDirectory() as idx:
        env = dict(os.environ)
        env["GIT_INDEX_FILE"] = str(Path(idx) / "index")

        for c in commits:
            # Load the subtree as the repository root. --empty first, or the
            # previous commit's tree lingers and a deleted file survives.
            # env=env on every git call that touches an index, without
            # exception. One line here was missing it: `read-tree --empty` ran
            # against the REAL index of the user's repository and wiped all
            # 52,084 entries, making every tracked file read as deleted. The
            # working tree and HEAD were untouched, so `git read-tree HEAD`
            # restored it -- but a script that empties your index as a side
            # effect of exporting is not a script anyone should run.
            subprocess.run(["git", "-C", str(REPO), "read-tree", "--empty"],
                           env=env, check=True, capture_output=True)
            tree_in = subprocess.run(
                ["git", "-C", str(REPO), "read-tree", f"{c}:{SUBTREE}"],
                env=env, capture_output=True, text=True)
            if tree_in.returncode != 0:
                # The commit touched TATA-ELXSI without leaving it present, e.g.
                # a deletion of the whole subtree. Nothing to export from it.
                dropped += 1
                continue
            tree = subprocess.run(["git", "-C", str(REPO), "write-tree"], env=env,
                                  capture_output=True, text=True,
                                  check=True).stdout.strip()

            msg = subprocess.run(["git", "-C", str(REPO), "log", "-1",
                                  "--format=%B", c], capture_output=True,
                                 text=True).stdout
            meta = subprocess.run(["git", "-C", str(REPO), "log", "-1",
                                   "--format=%an%n%ae%n%aI%n%cn%n%ce%n%cI", c],
                                  capture_output=True, text=True).stdout.split("\n")
            an, ae, ad, cn, ce, cd = (x.strip() for x in meta[:6])

            cenv = dict(os.environ)
            cenv.update(GIT_AUTHOR_NAME=an, GIT_AUTHOR_EMAIL=ae, GIT_AUTHOR_DATE=ad,
                        GIT_COMMITTER_NAME=cn, GIT_COMMITTER_EMAIL=ce,
                        GIT_COMMITTER_DATE=cd)

            args_new = ["commit-tree", tree]
            if parent:
                args_new += ["-p", parent]
            new = subprocess.run(["git", "-C", str(REPO), *args_new], env=cenv,
                                 input=msg, capture_output=True, text=True,
                                 check=True).stdout.strip()

            if tree == _tree_of(parent):
                # Same tree as the parent: the commit only touched siblings.
                dropped += 1
                continue
            parent = new
            mapping[c] = new
            kept += 1

    print(f"kept {kept}, dropped {dropped} as empty for {SUBTREE}")

    # ---- materialise as a standalone repository
    dest.mkdir(parents=True, exist_ok=True)
    run = lambda *a: subprocess.run(a, cwd=dest, check=True, capture_output=True,
                                    text=True)
    run("git", "init", "-q", "-b", "main")
    run("git", "remote", "add", "origin",
        subprocess.run(["git", "-C", str(REPO), "remote", "get-url", args.remote],
                       capture_output=True, text=True).stdout.strip())

    # A temporary ref in the source, because `git fetch <path> <sha>` needs
    # allowTipSHA1InWant and a local path does not always grant it. Removed in a
    # finally: it is a scratch pointer into the user's real repository and must
    # not survive a crash.
    tmp_ref = "refs/export-aciq/scratch"
    try:
        subprocess.run(["git", "-C", str(REPO), "update-ref", tmp_ref, parent],
                       check=True, capture_output=True)
        run("git", "fetch", "-q", str(REPO), tmp_ref)
    finally:
        subprocess.run(["git", "-C", str(REPO), "update-ref", "-d", tmp_ref],
                       capture_output=True)

    # `git branch -f main FETCH_HEAD` fails here: after `init -b main`, main is
    # unborn and FETCH_HEAD is not a branch. Point the ref directly, then check
    # the tree out.
    run("git", "update-ref", "refs/heads/main", "FETCH_HEAD")
    run("git", "reset", "-q", "--hard", "FETCH_HEAD")

    # tags that pointed at a replayed commit
    for tag, target in (l.split() for l in git("tag", "-l", "--format=%(refname:short) %(objectname)")
                        .splitlines() if l.strip()):
        deref = git("rev-parse", f"{tag}^{{commit}}")
        if deref in mapping:
            run("git", "tag", "-f", tag, mapping[deref])
            print(f"  tag {tag} -> {mapping[deref][:7]}")

    head = subprocess.run(["git", "-C", str(dest), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()
    n = subprocess.run(["git", "-C", str(dest), "rev-list", "--count", "HEAD"],
                       capture_output=True, text=True).stdout.strip()
    print(f"\nexport at {dest}\n  {n} commits, HEAD {head[:7]}")

    if args.push:
        print(f"\npushing to {args.remote}...")
        run("git", "push", "-u", "origin", "main")
        run("git", "push", "--tags", "origin")
        print("pushed")
    else:
        print(f"\nnot pushed. review it, then:\n  git -C {dest} push -u origin main && git -C {dest} push --tags origin")
    return 0


_TREE_CACHE: dict[str, str] = {}


def _tree_of(commit: str | None) -> str:
    if commit is None:
        return "<none>"
    if commit not in _TREE_CACHE:
        _TREE_CACHE[commit] = git("rev-parse", f"{commit}^{{tree}}")
    return _TREE_CACHE[commit]


if __name__ == "__main__":
    raise SystemExit(main())