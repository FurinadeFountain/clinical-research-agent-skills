#!/usr/bin/env python3
"""Regression tests for the manuscript review & 3-tier triage showcase."""

from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

SHOWCASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = SHOWCASE_DIR.parents[1]
LINTER_PATH = REPO_ROOT / "skills" / "scientific-drafting" / "scripts" / "lint_manuscript.py"


def _load_manuscript_linter():
    spec = importlib.util.spec_from_file_location("lint_manuscript", LINTER_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestManuscriptReviewTriageShowcase(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.linter = _load_manuscript_linter()
        cls.before_path = SHOWCASE_DIR / "draft-before.md"
        cls.after_path = SHOWCASE_DIR / "draft-after.md"
        cls.triage_path = SHOWCASE_DIR / "review-and-triage.md"

    def test_before_draft_triggers_expected_deterministic_gates(self) -> None:
        errors, warnings, _ = self.linter.lint_file(self.before_path)
        joined_errors = "\n".join(errors)
        joined_warnings = "\n".join(warnings)

        self.assertEqual(len(errors), 3, msg=joined_errors)
        self.assertIn("路线 B", joined_errors)
        self.assertIn("citation [3] appears before [2]", joined_errors)
        self.assertIn("middle-dot", joined_errors)
        self.assertEqual(len(warnings), 1, msg=joined_warnings)
        self.assertIn("overloaded Chinese sentence", joined_warnings)

    def test_after_draft_passes_all_gates_and_preserves_scientific_anchors(self) -> None:
        errors, warnings, _ = self.linter.lint_file(self.after_path)
        self.assertEqual(errors, [])
        self.assertEqual(warnings, [])

        after_text = self.after_path.read_text(encoding="utf-8")
        self.assertIn("70 kDa FITC-dextran", after_text)
        self.assertIn("n = 6", after_text)
        self.assertIn("1% DMSO", after_text)
        self.assertIn("## 方法与统计质控", after_text)
        self.assertNotIn("repair response", after_text)
        self.assertNotIn("n = 30", after_text)

    def test_triage_ledger_records_all_three_tiers(self) -> None:
        triage_text = self.triage_path.read_text(encoding="utf-8")
        self.assertIn("VERDICT: FAIL", triage_text)
        self.assertIn("已修正（入正文主干）", triage_text)
        self.assertIn("已分流落位（归入方法专节）", triage_text)
        self.assertIn("凭据不改（透明记录）", triage_text)


if __name__ == "__main__":
    unittest.main()
