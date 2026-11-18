import tempfile
import unittest
from pathlib import Path

from lint_agent_configs import REPO_ROOT, lint_repository


class LintAgentConfigsTests(unittest.TestCase):
    def test_live_repository_passes_all_invariants(self) -> None:
        errors, budgets = lint_repository(REPO_ROOT)
        self.assertEqual(errors, [], f"Unexpected repo lint errors: {errors}")
        self.assertIn("AGENTS_shared_core", budgets)

    def test_detects_broken_link_and_home_shebang(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "AGENTS.md").write_text(
                "# Rules\n<!-- SHARED_CORE_START -->\ncore\n<!-- SHARED_CORE_END -->\n",
                encoding="utf-8",
            )
            sdir = root / "skills" / "demo-skill" / "scripts"
            sdir.mkdir(parents=True)
            (sdir.parent / "SKILL.md").write_text(
                "---\nname: demo-skill\ndescription: Demo skill.\n---\n\nSee [missing](nope.md).\n",
                encoding="utf-8",
            )
            (sdir / "helper.py").write_text(
                "#!/Users/alice/venv/bin/python3\nprint('hi')\n",
                encoding="utf-8",
            )
            errors, _ = lint_repository(root)
            self.assertTrue(any("broken relative link -> nope.md" in e for e in errors))
            self.assertTrue(any("non-portable home-directory shebang" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
