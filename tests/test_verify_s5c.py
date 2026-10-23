"""S5(c) verifier lines up with the injection contract.

Three witnesses, from artefacts ONLY (config.json, result.json's notes,
samples.jsonl's policy_outcome fields): armed, rolled back, run continued.
The verifier must NOT pass a run whose samples show a rollback but no
afterwards-committed apply — 'rolled back' alone does not prove the tx path
survived the failure, which is the point of the S5 case.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tools.verify_s5c import verify  # noqa: E402


def _run(d: Path, *, inject=True, armed=True, rolled=True, resumed=True):
    d.mkdir(parents=True, exist_ok=True)
    (d / "config.json").write_text(
        json.dumps({"inject_fail_apply": bool(inject)}))
    lines = [{"t": 5.0, "policy_outcome":
              {"ok": True, "committed": True, "rolled_back": False}},
             {"t": 19.0, "policy_outcome":
              {"ok": False, "committed": False, "rolled_back": bool(rolled)}},
             {"t": 21.0, "policy_outcome":
              {"ok": True, "committed": True, "rolled_back": False}}]
    if not resumed:
        del lines[2]
    (d / "samples.jsonl").write_text(
        "".join(json.dumps(x) + "\n" for x in lines))
    (d / "result.json").write_text(json.dumps(
        {"notes": ["S5(c) injected failed apply ARMED at t=19.0s"]
         if armed else ["no injection in this run"]}))


class TestVerifyS5c(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.mkdtemp(prefix="s5c-")
        self.root = Path(self._tmp)

    def _verify(self, names):
        return verify([str(self.root / n) for n in names])

    def test_full_witness_passes(self):
        _run(self.root / "run_ok")
        ok, missing = self._verify(["run_ok"])
        self.assertTrue(ok, missing)

    def test_no_rollback_witness_fails(self):
        _run(self.root / "run_flat", rolled=False)
        ok, missing = self._verify(["run_flat"])
        self.assertFalse(ok)
        self.assertIn("rolled_back", str(missing))

    def test_no_afterwards_commit_fails(self):
        _run(self.root / "run_noresume", resumed=False)
        ok, missing = self._verify(["run_noresume"])
        self.assertFalse(ok)
        self.assertIn("resumed", str(missing))

    def test_unarmed_note_fails(self):
        _run(self.root / "run_unarmed", armed=False)
        ok, missing = self._verify(["run_unarmed"])
        self.assertFalse(ok)
        self.assertIn("armed", str(missing))

    def test_non_injected_dirs_are_ignored_not_failures(self):
        _run(self.root / "plain", inject=False, armed=False)
        ok, missing = self._verify(["plain"])   # no inject-> verifier skips
        self.assertFalse(ok)                    # nothing to witness -> fail
        self.assertTrue(all("plain" in m for m in missing), missing)


if __name__ == "__main__":
    unittest.main()
