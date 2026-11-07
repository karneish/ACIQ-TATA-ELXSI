"""The secret scanner must fail on a real-looking credential.

The pattern set was tuned against this repo's own prose (class names, git
revision hashes, SHA256SUMS, artefact paths all legitimately hit the naive
`[A-Za-z0-9]{40,}` rule), so the DANGER after tuning is a scanner that turns
into a rubber stamp. These tests pin a real-shaped credential as a HIT and
one miss per known-safe shape, so the tuning cannot drift back to noise —
or, worse, to silence.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import tools.secret_scan as ss  # noqa: E402


class ScanVerdicts(unittest.TestCase):
    def test_aws_key_is_a_hit(self):
        hits = ss.scan_text('X = "AKIAB4EVEY736251XW03"\n')
        self.assertTrue(any(r == "aws-key" for r, _, _ in hits), hits)

    def test_named_hex_secret_is_a_hit(self):
        secret = "a6f9c8d74e5263b18f0a9c2d47751be6b8bd"
        hits = ss.scan_text(f'api_key = "{secret}"\n')
        self.assertEqual(hits[0][0], "generic-hex-secret")

    def test_private_key_marker_is_a_hit(self):
        self.assertEqual(
            ss.scan_text("-----BEGIN RSA PRIVATE KEY-----\n")[0][0],
            "private-key")

    def test_git_revision_hash_is_not_a_hit(self):
        hashes = "\n".join(
            f'{("a"*40)} {"a"*23}{"b"*17}' for _ in range(1)) + "\n"
        self.assertEqual([h for h in ss.scan_text(hashes)
                          if h[0] == "b64-lookalike"], [])

    def test_artefact_path_line_is_not_a_hit(self):
        line = ("artifacts/validation/89b87758/"
                "classifier-before.txt, which is in\n")
        self.assertFalse(ss.scan_text(line))

    def test_test_class_names_are_not_hits(self):
        self.assertFalse(ss.scan_text(
            "class TestTheGateNeverLeavesASourceToTheKernel(unittest.Group:\n"))

    def test_sha256sums_lines_are_not_hits(self):
        hexes = "\n".join(f"{'c4c6902fdc325a5f6c428b448a9a813d71e894b49b54cfa8219d9099d61c663d'}  ./REPORT-{i}"
                          for i in range(6)) + "\n"
        self.assertFalse(ss.scan_text(hexes))

    def test_empty_text(self):
        self.assertEqual(ss.scan_text(""), [])

    def test_embedded_prose_slash_list_is_not_a_hit(self):
        self.assertFalse(ss.scan_text(
            "evaluation E1-E11 (latency/jitter/loss/fairness/stability/CPU/reproducibility/dashboard clarity)\n"))

    def test_embedded_prose_slash_list_with_digits_heading_is_not_a_hit(self):
        self.assertFalse(ss.scan_text(
            "`config.json` per run stores the full scenario/system/mode/seed/ports/dscp/floors/lease/inject-fail configuration\n"))

    def test_real_b64_credential_still_is_a_hit(self):
        token = "A9bC8dE7fG6hH5iJ4kL3mM2nN1oO0pPqQrRsStTuUvVwXx"
        hits = ss.scan_text(f'KEY = "{token}"\n')
        self.assertTrue(any(r == "b64-lookalike" for r, _, _ in hits), hits)


if __name__ == "__main__":
    unittest.main()
