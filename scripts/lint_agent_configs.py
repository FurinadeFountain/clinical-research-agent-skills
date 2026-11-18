#!/usr/bin/env python3
"""Self-linter for repository AGENTS.md budgets, Markdown links, and skill integrity.

Enforces deterministic invariants across the open-source research skill suite:
1. Global AGENTS.md and combined host-supplement character budget ceilings
   (prevents prompt-bloat creep against frontier model context).
2. Presence of <!-- SHARED_CORE_START / END --> markers in AGENTS.md.
3. Valid YAML frontmatter (name + description) in every skills/*/SKILL.md and
   valid interface block in optional agents/openai.yaml files.
4. Zero broken relative Markdown links across README.md, AGENTS.md, hosts/*.md,
   and all active SKILL.md / references/**/*.md files.
5. Portable shebangs (no hardcoded user home paths) and valid Python syntax
   (py_compile) across all skill helper scripts.
"""

from __future__ import annotations

import argparse
import ast
import glob
import json
import os
import re
import shutil
import sys
from pathlib import Path

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover - stdlib fallback for clean environments
    yaml = None

REPO_ROOT = Path(__file__).resolve().parents[1]

SHARED_CORE_BUDGET = 3200
COMBINED_HOST_BUDGET = 4600

SHARED_CORE_RE = re.compile(
    r"(<!-- SHARED_CORE_START -->\n)(.*?)(\n<!-- SHARED_CORE_END -->)",
    flags=re.DOTALL,
)
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)#\s]+)(?:#[^)]+)?\)")
HOME_SHEBANG_RE = re.compile(r"^#!\s*(?:/Users/|/home/|[A-Za-z]:\\)")


def strip_fenced_code(text: str) -> str:
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def _check_balanced_yaml_scalar(raw_val: str) -> None:
    v = raw_val.strip()
    if not v or v in (">", "|", ">-", "|-"):
        return
    if v[0] in ("'", '"') and (len(v) < 2 or v[-1] != v[0]):
        raise ValueError(f"Unclosed quote in YAML value: {raw_val!r}")
    if v[0] == "[" and not v.endswith("]"):
        raise ValueError(f"Unclosed '[' in YAML value: {raw_val!r}")
    if v[0] == "{" and not v.endswith("}"):
        raise ValueError(f"Unclosed '{{' in YAML value: {raw_val!r}")


def parse_frontmatter(block: str) -> dict[str, object]:
    result: dict[str, object] = {}
    current_key: str | None = None
    for raw_line in block.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if not raw_line.startswith((" ", "\t")) and ":" in raw_line:
            k, v = raw_line.split(":", 1)
            current_key = k.strip()
            _check_balanced_yaml_scalar(v)
            val = v.strip().strip("'\"")
            result[current_key] = val if val not in (">", "|", ">-", "|-") else ""
        elif current_key and isinstance(result.get(current_key), str):
            result[current_key] = (str(result[current_key]) + " " + raw_line.strip()).strip()
    if yaml is not None:
        loaded = yaml.safe_load(block)
        if not isinstance(loaded, dict):
            raise ValueError("YAML frontmatter root must be a mapping")
        return loaded
    return result


def validate_openai_yaml(text: str) -> None:
    lines = [ln for ln in text.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    if not any(ln.startswith("interface:") for ln in lines):
        raise ValueError("missing top-level 'interface:' mapping")
    for ln in lines:
        if ":" in ln:
            _, v = ln.split(":", 1)
            _check_balanced_yaml_scalar(v)
    if yaml is not None:
        loaded = yaml.safe_load(text)
        if not isinstance(loaded, dict) or not isinstance(loaded.get("interface"), dict):
            raise ValueError("missing 'interface' mapping")


def check_budgets_and_markdown_links(root: Path) -> tuple[list[str], dict[str, dict[str, int]]]:
    errors: list[str] = []
    stats: dict[str, dict[str, int]] = {}

    agents_path = root / "AGENTS.md"
    if not agents_path.is_file():
        errors.append(f"Missing root AGENTS.md at {agents_path}")
        return errors, stats

    agents_txt = agents_path.read_text(encoding="utf-8")
    m = SHARED_CORE_RE.search(agents_txt)
    if not m:
        errors.append("AGENTS.md is missing <!-- SHARED_CORE_START / END --> markers")
        core_chars = len(agents_txt)
    else:
        core_chars = len(m.group(2).strip("\n"))

    stats["AGENTS_shared_core"] = {
        "chars": core_chars,
        "max_chars": SHARED_CORE_BUDGET,
        "lines": len(agents_txt.splitlines()),
    }
    if core_chars > SHARED_CORE_BUDGET:
        errors.append(
            f"AGENTS.md shared core ({core_chars} chars) exceeds ceiling ({SHARED_CORE_BUDGET} chars)"
        )

    hosts_dir = root / "hosts"
    if hosts_dir.is_dir():
        for hp in sorted(hosts_dir.glob("*.md")):
            htxt = hp.read_text(encoding="utf-8")
            combined = len(agents_txt) + 1 + len(htxt)
            label = f"combined_{hp.stem}"
            stats[label] = {
                "chars": combined,
                "max_chars": COMBINED_HOST_BUDGET,
                "lines": len(agents_txt.splitlines()) + len(htxt.splitlines()),
            }
            if combined > COMBINED_HOST_BUDGET:
                errors.append(
                    f"{label} ({combined} chars) exceeds combined ceiling ({COMBINED_HOST_BUDGET} chars)"
                )

    top_docs = [
        p
        for p in [
            root / "README.md",
            root / "README.en.md",
            root / "THIRD_PARTY_NOTICES.md",
            agents_path,
        ]
        if p.is_file()
    ]
    if hosts_dir.is_dir():
        top_docs.extend(sorted(hosts_dir.glob("*.md")))
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        top_docs.extend(sorted(docs_dir.glob("*.md")))
    examples_dir = root / "examples"
    if examples_dir.is_dir():
        top_docs.extend(sorted(examples_dir.rglob("*.md")))
    for doc in top_docs:
        errors.extend(_check_links_in_file(doc, "repo"))

    return errors, stats


def _check_links_in_file(md_path: Path, label: str) -> list[str]:
    errs: list[str] = []
    body = strip_fenced_code(md_path.read_text(encoding="utf-8", errors="replace"))
    for m in LINK_RE.finditer(body):
        target = m.group(1).strip().strip("<>")
        if target.startswith(("http://", "https://", "mailto:", "conversation://")):
            continue
        if target.startswith("file:///"):
            errs.append(f"[{label}] {md_path}: non-portable file:// link in repo doc -> {target}")
            continue
        resolved = (md_path.parent / target).resolve()
        if not resolved.exists():
            errs.append(f"[{label}] {md_path}: broken relative link -> {target}")
    return errs


def check_skills(skills_root: Path) -> list[str]:
    errors: list[str] = []
    if not skills_root.is_dir():
        return [f"Missing skills directory: {skills_root}"]

    skill_dirs = [d for d in sorted(skills_root.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    if not skill_dirs:
        return [f"No skill directories found in {skills_root}"]

    for skill_dir in skill_dirs:
        skill_md = skill_dir / "SKILL.md"
        if not skill_md.is_file():
            errors.append(f"[skills] {skill_dir.name}: missing SKILL.md")
            continue

        txt = skill_md.read_text(encoding="utf-8")
        if not txt.startswith("---\n"):
            errors.append(f"[skills] {skill_md}: missing YAML frontmatter")
        else:
            parts = txt.split("---\n", 2)
            if len(parts) < 3:
                errors.append(f"[skills] {skill_md}: unclosed YAML frontmatter")
            else:
                try:
                    fm = parse_frontmatter(parts[1])
                    if not fm.get("name") or not fm.get("description"):
                        errors.append(f"[skills] {skill_md}: frontmatter requires name and description")
                except Exception as exc:
                    errors.append(f"[skills] {skill_md}: YAML error: {exc}")

        openai_yaml = skill_dir / "agents" / "openai.yaml"
        if openai_yaml.is_file():
            try:
                validate_openai_yaml(openai_yaml.read_text(encoding="utf-8"))
            except Exception as exc:
                errors.append(f"[skills] {openai_yaml}: YAML error: {exc}")

        for md_str in sorted(glob.glob(str(skill_dir / "**" / "*.md"), recursive=True)):
            md_path = Path(md_str)
            rel_parts = md_path.relative_to(skill_dir).parts
            if any(p in ("evals", "examples", "node_modules", "__pycache__") for p in rel_parts):
                continue
            errors.extend(_check_links_in_file(md_path, skill_dir.name))

        for py_str in sorted(glob.glob(str(skill_dir / "**" / "*.py"), recursive=True)):
            sp = Path(py_str)
            if "__pycache__" in sp.parts or sp.name.startswith("."):
                continue
            try:
                ast.parse(sp.read_text(encoding="utf-8"), filename=str(sp))
            except SyntaxError as exc:
                errors.append(f"[skills] {sp}: syntax error: {exc}")
            first = sp.read_text(encoding="utf-8", errors="ignore").splitlines()[:1]
            if first and first[0].startswith("#!"):
                if HOME_SHEBANG_RE.match(first[0]):
                    errors.append(f"[skills] {sp}: non-portable home-directory shebang '{first[0]}'")
                else:
                    toks = first[0][2:].strip().split()
                    interp = toks[0] if toks else ""
                    if interp and not (os.path.exists(interp) or shutil.which(interp)):
                        errors.append(f"[skills] {sp}: missing shebang binary '{interp}'")

    return errors


def lint_repository(root: Path = REPO_ROOT) -> tuple[list[str], dict[str, dict[str, int]]]:
    errors, stats = check_budgets_and_markdown_links(root)
    errors.extend(check_skills(root / "skills"))
    return errors, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=REPO_ROOT, help="repository root to lint")
    parser.add_argument("--json", action="store_true", help="emit JSON output")
    args = parser.parse_args()

    errors, budgets = lint_repository(args.root.resolve())
    if args.json:
        print(json.dumps({"budgets": budgets, "errors": errors}, ensure_ascii=False, indent=2))
    else:
        status = "FAIL" if errors else "PASS"
        print(f"[{status}] Agent Config & Skill Suite Linter (errors={len(errors)})")
        for k, v in budgets.items():
            pct = 100.0 * v["chars"] / v["max_chars"]
            print(f"  BUDGET {k:26s}: {v['chars']:4d} / {v['max_chars']:4d} chars ({pct:5.1f}%)")
        for e in errors:
            print(f"  ERROR: {e}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
