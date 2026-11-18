#!/usr/bin/env python3
"""Deterministic linter for scientific manuscripts and grant proposals (.md / .tex).

Catches structural slop and mechanical violations without spending LLM tokens:
1. Heading hygiene: middle-dot ('·' / '・') keyword chains and conclusion-prompt colons.
2. Leaked internal/audit labels: '模式 M0-M3', 'Step 2A', '路线 A', 'VERDICT:', 'FAIL:', 'WARN:'.
3. Markdown numeric citation first-appearance order & bibliography parity.
   TeX citation resolution requires the project's compiler/bibliography checks.
4. Structural defensive-patch bloat: oversized inline parentheticals in spine sections,
   parenthetical-stuffed paragraphs, and duplicate caveats brushed across >=3 sections.
5. English staccato fragmentation: excessive <=12-word short-sentence ratios (>30%, or
   >=24% paired with <16% logical connectors) or >=3 consecutive short fragments at paragraph ends.
6. Chinese code-like overloaded defensive sentences: single sentences packing >=120 CJK chars
   in spine sections (Abstract/Intro/Objectives) or >=140 CJK chars (>=115 with >=2 '；') elsewhere.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

MIDDLE_DOT_RE = re.compile(r"[·・]")
PROMPT_COLON_RE = re.compile(
    r"(一句话总结|核心在于|关键在于|核心结论|先说结论)\s*[：:]"
)
INTERNAL_TAG_PATTERNS = [
    ("internal mode code", re.compile(r"模式\s*M\d(?:\s*[-–~—]\s*M?\d)?")),
    ("internal step code", re.compile(r"\bStep\s*\d+[A-Z](?:\s*[-–~—]\s*\d*[A-Z])?\b")),
    ("internal route label", re.compile(r"路线\s*[A-D]\b")),
    ("raw audit verdict token", re.compile(r"\bVERDICT\s*:\s*(?:FAIL|WARN|PASS|INCOMPLETE)\b")),
    ("raw audit finding prefix", re.compile(r"(?:^|\s)(?:FAIL|WARN)\s*\d*\s*:")),
]
SPINE_HEADING_RE = re.compile(
    r"(摘要|abstract|研究目标|objectives?|关键科学问题|立项依据|引言|introduction)",
    re.IGNORECASE,
)
BIB_HEADING_RE = re.compile(
    r"^(?:references|bibliography|参考文献|引用文献)\s*$", re.IGNORECASE
)
NON_PROSE_SECTION_RE = re.compile(
    r"(?:acknowledg|author\s+contributions?|competing\s+interests?|declarations?|致谢|作者贡献|利益冲突)",
    re.IGNORECASE,
)
ABBREV_DOT_RE = re.compile(
    r"\b(?:et\s+al|figs?|eqs?|drs?|prof|vs|e\.g|i\.e|ca|approx|no|vol|pp|spp?|cf|refs?)\.",
    re.IGNORECASE,
)
EN_LOGICAL_CONN_RE = re.compile(
    r"\b(?:although|though|whereas|while|because|since|however|therefore|thus|consequently|"
    r"nevertheless|nonetheless|instead|by\s+contrast|in\s+contrast|unlike|despite|thereby)\b",
    re.IGNORECASE,
)
MD_HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*#*$")
TEX_HEADING_RE = re.compile(
    r"\\(?:part|chapter|(?:sub){0,2}section)\*?\{([^{}]+)\}"
)
BRACKET_CITE_RE = re.compile(
    r"(?<![!\[a-zA-Z0-9_])\[(\d+(?:\s*[,，\-–—]\s*\d+)*)\](?!\s*\()"
)
CJK_COUNT_RE = re.compile(r"[\u4e00-\u9fff]")
PAREN_PAIR_RE = re.compile(r"（([^（）\n]{8,})）|\(([^()\n]{20,})\)")


def strip_code_and_comments(text: str, is_tex: bool) -> list[str]:
    if is_tex:
        lines = []
        in_verbatim = False
        for raw in text.splitlines():
            if re.search(r"\\begin\{(?:lstlisting|verbatim|minted)\}", raw):
                in_verbatim = True
            if in_verbatim:
                lines.append("")
                if re.search(r"\\end\{(?:lstlisting|verbatim|minted)\}", raw):
                    in_verbatim = False
                continue
            cleaned = re.sub(r"(?<!\\)%.*$", "", raw)
            lines.append(cleaned)
        return lines

    cleaned_full = re.sub(
        r"(?ms)^\s*```[^\n]*\n.*?^\s*```[^\n]*$",
        lambda m: "\n" * m.group(0).count("\n"),
        text,
    )
    cleaned_full = re.sub(
        r"(?ms)<!--.*?-->",
        lambda m: "\n" * m.group(0).count("\n"),
        cleaned_full,
    )
    cleaned_full = re.sub(
        r"(?ims)<(?:table|image)\b.*?</(?:table|image)>",
        lambda m: "\n" * m.group(0).count("\n"),
        cleaned_full,
    )
    cleaned_full = re.sub(
        r"(?ms)\$\$.*?\$\$",
        lambda m: "\n" * m.group(0).count("\n"),
        cleaned_full,
    )
    return cleaned_full.splitlines()


def expand_cite_numbers(spec: str) -> list[int]:
    nums: list[int] = []
    for part in re.split(r"[,，]", spec):
        part = part.strip()
        if not part:
            continue
        rng = re.split(r"[-–—]", part)
        if len(rng) == 2 and rng[0].strip().isdigit() and rng[1].strip().isdigit():
            a, b = int(rng[0].strip()), int(rng[1].strip())
            if 0 < a <= b and (b - a) <= 100:
                nums.extend(range(a, b + 1))
        elif part.isdigit():
            val = int(part)
            if val > 0:
                nums.append(val)
    return nums


def normalize_caveat(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip().lower())
    s = re.sub(r"\[\d+(?:\s*[,，\-–—]\s*\d+)*\]", "", s)
    return s.strip(" ，,。.;；:：")


def is_benign_scientific_paren(content: str) -> bool:
    s = content.strip()
    if s.startswith(("http://", "https://", "file://", "mailto:", "doi:")):
        return True
    if re.match(
        r"^(?:n\s*=|p\s*[<=>]|95%\s*ci|iqr|mean|sd|sem|or\s*=|hr\s*=|rr\s*=|"
        r"fig\.?|figure|table|图\s*\d|表\s*\d|式\s*\d|eq\.?)",
        s,
        re.IGNORECASE,
    ):
        return True
    if len(CJK_COUNT_RE.findall(s)) <= 8 and len(s) <= 35:
        return True
    return False


def lint_file(path: Path, *, fragment: bool = False) -> tuple[list[str], list[str], dict[str, object]]:
    is_tex = path.suffix.lower() == ".tex"
    raw_text = path.read_text(encoding="utf-8", errors="replace")
    lines = strip_code_and_comments(raw_text, is_tex)

    errors: list[str] = []
    warnings: list[str] = []

    current_section = "Preamble"
    in_bibliography = False
    bib_numbers: set[int] = set()
    seen_cites: set[int] = set()
    max_cite = 0
    citation_jump_reported = 0

    caveat_sections: dict[str, set[str]] = defaultdict(set)
    para_lines: list[tuple[int, str]] = []
    en_sentences: list[tuple[int, bool]] = []
    cjk_overload_reported = 0

    def split_english_sentences(text: str) -> list[tuple[int, bool]]:
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
        cleaned = re.sub(r"(?:\[\d+(?:\s*[,，\-–—]\s*\d+)*\]|\(\d+(?:\s*[,，\-–—]\s*\d+)*\))", "", cleaned)
        cleaned = ABBREV_DOT_RE.sub(lambda m: m.group(0)[:-1], cleaned)
        parts = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])", cleaned.strip())
        return [
            (len(s.split()), bool(EN_LOGICAL_CONN_RE.search(s)))
            for s in parts
            if len(s.split()) >= 3
        ]

    def flush_paragraph(section_name: str) -> None:
        nonlocal para_lines, cjk_overload_reported
        if not para_lines:
            return
        start_ln = para_lines[0][0]
        joined = " ".join(x[1].strip() for x in para_lines if x[1].strip())
        para_lines = []
        if not joined or joined.startswith(("|", "\\begin", "\\item")):
            return
        is_list_para = joined.startswith(("- ", "* ")) or bool(re.match(r"^\d+\.\s", joined))
        # Strip Markdown link targets [label](url) so URLs are never mistaken for prose parentheticals
        joined_for_parens = re.sub(r"\]\(\s*<?[^)\s]+>?(?:\s+\"[^\"]*\")?\s*\)", "]", joined)

        substantive_parens: list[str] = []
        for pm in PAREN_PAIR_RE.finditer(joined_for_parens):
            inner = pm.group(1) or pm.group(2) or ""
            if is_benign_scientific_paren(inner):
                continue
            cjk_n = len(CJK_COUNT_RE.findall(inner))
            substantive_parens.append(inner)
            if SPINE_HEADING_RE.search(section_name) and (
                cjk_n >= 42 or len(inner) >= 200
            ):
                warnings.append(
                    f"L{start_ln} [{section_name}]: oversized parenthetical patch ({cjk_n} CJK / {len(inner)} chars) in spine section: '（{inner[:36]}…）'"
                )
            if cjk_n >= 10 or len(inner) >= 40:
                norm_full = normalize_caveat(inner)
                if len(norm_full) >= 10:
                    caveat_sections[norm_full].add(section_name)
                for sub in re.split(r"[，,;；]", inner):
                    norm_sub = normalize_caveat(sub)
                    if len(CJK_COUNT_RE.findall(norm_sub)) >= 12 or len(norm_sub) >= 45:
                        caveat_sections[norm_sub].add(section_name)

        if len(substantive_parens) >= 4:
            warnings.append(
                f"L{start_ln} [{section_name}]: paragraph contains {len(substantive_parens)} substantive parenthetical clauses (defensive patch overload risk)"
            )

        if len(CJK_COUNT_RE.findall(joined)) >= 80 and not NON_PROSE_SECTION_RE.search(section_name):
            cjk_clean = re.sub(r"\$[^$\n]+\$", "", joined_for_parens)
            cjk_clean = re.sub(r"<[^>]+>", "", cjk_clean)
            in_spine = bool(SPINE_HEADING_RE.search(section_name))
            for sent in re.split(r"[。！？!?]", cjk_clean):
                cjk_len = len(CJK_COUNT_RE.findall(sent))
                semi_n = sent.count("；") + sent.count(";")
                overloaded = (
                    (in_spine and cjk_len >= 120)
                    or cjk_len >= 140
                    or (cjk_len >= 115 and semi_n >= 2)
                )
                if overloaded and cjk_overload_reported < 8:
                    preview = re.sub(r"\s+", " ", sent.strip())[:38]
                    warnings.append(
                        f"L{start_ln} [{section_name}]: overloaded Chinese sentence ({cjk_len} CJK chars, {semi_n} semicolons) — split code-like defensive clauses into concise sentences: '{preview}…'"
                    )
                    cjk_overload_reported += 1

        if (
            not is_tex
            and not is_list_para
            and len(CJK_COUNT_RE.findall(joined)) == 0
            and not NON_PROSE_SECTION_RE.search(section_name)
            and len(joined.split()) >= 35
        ):
            sent_info = split_english_sentences(joined)
            en_sentences.extend(sent_info)
            sent_lens = [n for n, _ in sent_info]
            if (
                len(sent_lens) >= 5
                and all(n <= 12 for n in sent_lens[-3:])
                and sum(sent_lens[-3:]) <= 30
            ):
                warnings.append(
                    f"L{start_ln} [{section_name}]: paragraph ends with 3 consecutive short fragments ({sent_lens[-3:]} words) — integrate caveats/links via subordination rather than staccato disclaimers"
                )

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        heading_title: str | None = None
        if not is_tex:
            hm = MD_HEADING_RE.match(stripped)
            if hm:
                heading_title = hm.group(2).strip()
        else:
            tm = TEX_HEADING_RE.search(stripped)
            if tm:
                heading_title = tm.group(1).strip()

        if heading_title is not None:
            flush_paragraph(current_section)
            current_section = heading_title
            clean_h = re.sub(r"^[\d.、一二三四五六七八九十()\s]+", "", heading_title)
            if BIB_HEADING_RE.match(clean_h):
                in_bibliography = True
            else:
                in_bibliography = False

            if MIDDLE_DOT_RE.search(heading_title):
                errors.append(
                    f"L{idx}: heading uses middle-dot keyword chain: '{heading_title}'"
                )
            if PROMPT_COLON_RE.search(heading_title):
                errors.append(
                    f"L{idx}: heading uses conclusion-prompt colon: '{heading_title}'"
                )
            continue

        if in_bibliography:
            bm = re.match(r"^\s*(?:\[(\d+)\]|(\d+)\.)\s+\S", stripped)
            if bm:
                bib_numbers.add(int(bm.group(1) or bm.group(2)))
            continue

        if not stripped:
            flush_paragraph(current_section)
            continue

        para_lines.append((idx, line))

        pcm = PROMPT_COLON_RE.search(line)
        if pcm:
            errors.append(
                f"L{idx} [{current_section}]: prose uses conclusion-prompt colon '{pcm.group(0)}'"
            )

        for label, pat in INTERNAL_TAG_PATTERNS:
            m = pat.search(line)
            if m:
                errors.append(
                    f"L{idx} [{current_section}]: leaked {label} '{m.group(0).strip()}'"
                )

        if not is_tex:
            # Reference-style Markdown link definitions are not body citations.
            if re.match(r"^\s*\[[^\]]+\]:\s*\S", line):
                continue
            citation_line = re.sub(r"`[^`]*`", "", line)
            for cm in BRACKET_CITE_RE.finditer(citation_line):
                for num in expand_cite_numbers(cm.group(1)):
                    if num not in seen_cites:
                        if not fragment and num > max_cite + 1 and citation_jump_reported < 5:
                            errors.append(
                                f"L{idx}: Vancouver citation [{num}] appears before [{max_cite + 1}] (out-of-order first appearance)"
                            )
                            citation_jump_reported += 1
                        seen_cites.add(num)
                        if num > max_cite:
                            max_cite = num

    flush_paragraph(current_section)

    for norm_caveat, secs in caveat_sections.items():
        if len(secs) >= 3:
            warnings.append(
                f"duplicate caveat brushed across {len(secs)} sections ({sorted(secs)}): '{norm_caveat[:40]}…' — use single-point placement"
            )

    if not fragment and len(en_sentences) >= 30:
        total_en = len(en_sentences)
        short_n = sum(1 for n, _ in en_sentences if n <= 12)
        conn_n = sum(1 for _, has_c in en_sentences if has_c)
        short_ratio = short_n / total_en
        conn_ratio = conn_n / total_en
        if short_ratio > 0.30 or (short_ratio >= 0.24 and conn_ratio < 0.16):
            warnings.append(
                f"English prose shows staccato/unlinked sentence rhythm: {short_n}/{total_en} ({100.0 * short_ratio:.0f}%) short sentences (<=12 words) and {conn_n}/{total_en} ({100.0 * conn_ratio:.0f}%) sentences with logical subordinators/connectors — merge choppy clauses and caveats via subordination"
            )

    if not is_tex and not fragment:
        missing_in_bib = sorted(seen_cites - bib_numbers)
        uncited_in_bib = sorted(bib_numbers - seen_cites)
        if missing_in_bib:
            errors.append(
                f"in-text citations missing from bibliography: {missing_in_bib[:10]}"
            )
        if uncited_in_bib:
            warnings.append(
                f"bibliography entries never cited in body text: {uncited_in_bib[:10]}"
            )

    meta = {
        "lines": len(lines),
        "unique_numeric_citations": len(seen_cites),
        "bibliography_entries": len(bib_numbers),
        "citation_check": "not_checked_tex" if is_tex else ("fragment_counts_only" if fragment else "numeric_markdown"),
    }
    if is_tex:
        warnings.append("TeX citation order and bibliography parity not checked; verify compiler/bibliography output and rendered references")
    return errors, warnings, meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="Markdown or TeX files")
    parser.add_argument(
        "--strict", action="store_true", help="treat patch-bloat warnings as exit-1 errors"
    )
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument("--fragment", action="store_true", help="check a partial excerpt without enforcing complete-document citation order/parity")
    args = parser.parse_args()

    results = []
    exit_code = 0
    for fpath in args.files:
        if not fpath.is_file():
            results.append(
                {"file": str(fpath), "errors": ["file does not exist"], "warnings": []}
            )
            exit_code = max(exit_code, 2)
            continue
        errs, warns, meta = lint_file(fpath, fragment=args.fragment)
        if errs or (args.strict and warns):
            exit_code = max(exit_code, 1)
        results.append(
            {"file": str(fpath), "meta": meta, "errors": errs, "warnings": warns}
        )

    if args.json:
        print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    else:
        for item in results:
            status = (
                "FAIL"
                if item["errors"] or (args.strict and item["warnings"])
                else ("WARN" if item["warnings"] else "PASS")
            )
            print(
                f"[{status}] {item['file']} "
                f"(errors={len(item['errors'])}, warnings={len(item['warnings'])})"
            )
            for e in item["errors"]:
                print(f"  ERROR: {e}")
            for w in item["warnings"]:
                print(f"  WARN : {w}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
