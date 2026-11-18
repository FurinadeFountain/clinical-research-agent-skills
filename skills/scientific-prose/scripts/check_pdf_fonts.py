#!/usr/bin/env python3
"""Check font embedding and report PDF font portability warnings."""

from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path


def safe_terminal(value: object) -> str:
    text = str(value)
    output: list[str] = []
    for character in text:
        codepoint = ord(character)
        if codepoint < 32 or 127 <= codepoint <= 159:
            output.append(f"\\x{codepoint:02x}")
        elif unicodedata.category(character) == "Cf":
            output.append(f"\\u{codepoint:04x}")
        else:
            output.append(character)
    return "".join(output)


def trusted_executable(path: Path) -> Path | None:
    try:
        resolved = path.resolve(strict=True)
        mode = resolved.stat()
    except OSError:
        return None
    if not stat.S_ISREG(mode.st_mode) or not os.access(resolved, os.X_OK):
        return None
    if mode.st_uid not in {0, os.getuid()} or mode.st_mode & 0o022:
        return None
    return resolved


def parse_pdffonts(output: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("name") or set(stripped) == {"-"}:
            continue
        columns = stripped.split()
        if len(columns) < 8:
            continue
        middle = columns[1:-5]
        if len(middle) < 2:
            continue
        rows.append(
            {
                "name": columns[0],
                "type": " ".join(middle[:-1]),
                "encoding": middle[-1],
                "embedded": columns[-5],
                "subset": columns[-4],
                "unicode": columns[-3],
                "object": " ".join(columns[-2:]),
            }
        )
    return rows


def trusted_pdffonts() -> Path | None:
    candidates = [
        Path.home()
        / ".cache/codex-runtimes/codex-primary-runtime/dependencies/bin/override/pdffonts",
        Path.home()
        / ".cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/pdffonts",
        Path("/opt/homebrew/bin/pdffonts"),
        Path("/usr/local/bin/pdffonts"),
        Path("/usr/bin/pdffonts"),
    ]
    for candidate in candidates:
        resolved = trusted_executable(candidate)
        if resolved is not None:
            return resolved
    return None


def check_pdf(
    executable: Path, path: Path, timeout: float, allow_no_fonts: bool
) -> tuple[list[str], list[str], int]:
    environment = os.environ.copy()
    for variable in (
        "DYLD_INSERT_LIBRARIES",
        "DYLD_LIBRARY_PATH",
        "LD_PRELOAD",
        "LD_LIBRARY_PATH",
    ):
        environment.pop(variable, None)
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        try:
            result = subprocess.run(
                [str(executable), str(path.resolve())],
                stdout=stdout_file,
                stderr=stderr_file,
                check=False,
                timeout=timeout,
                env=environment,
            )
        except subprocess.TimeoutExpired:
            return [f"pdffonts exceeded the {timeout:g}-second timeout"], [], 0

        stdout_size = stdout_file.tell()
        stderr_size = stderr_file.tell()
        if stdout_size > 5_000_000 or stderr_size > 5_000_000:
            return ["pdffonts diagnostic output exceeded the 5 MB safety limit"], [], 0
        stdout_file.seek(0)
        stderr_file.seek(0)
        stdout = stdout_file.read().decode("utf-8", errors="replace")
        stderr = stderr_file.read().decode("utf-8", errors="replace")

    if result.returncode != 0:
        return [f"pdffonts failed: {stderr.strip()}"], [], 0
    if stderr.strip():
        return [f"pdffonts reported a PDF parse error: {stderr.strip()}"], [], 0

    rows = parse_pdffonts(stdout)
    errors: list[str] = []
    warnings: list[str] = []
    for row in rows:
        label = f"{row['name']} ({row['type']}, {row['encoding']})"
        if row["embedded"].lower() != "yes":
            errors.append(f"font is not embedded: {label}")
        if "type 3" in row["type"].lower():
            warnings.append(f"Type 3 font needs visual/source review: {label}")
        if row["unicode"].lower() != "yes":
            warnings.append(f"font has no Unicode map: {label}")
    if not rows:
        message = "no fonts were reported; the PDF may contain only outlines or raster text"
        if allow_no_fonts:
            warnings.append(message)
        else:
            errors.append(message)
    return errors, warnings, len(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdfs", nargs="+", type=Path, help="manuscript or vector-figure PDFs")
    parser.add_argument("--strict", action="store_true", help="treat warnings as failures")
    parser.add_argument(
        "--allow-no-fonts",
        action="store_true",
        help="permit a deliberately text-free figure PDF that reports no fonts",
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="seconds allowed per PDF")
    parser.add_argument(
        "--max-size-mb", type=float, default=512.0, help="maximum input size per PDF"
    )
    args = parser.parse_args()

    executable = trusted_pdffonts()
    if executable is None:
        print("error: pdffonts is not available", file=sys.stderr)
        return 2
    if args.timeout <= 0 or args.max_size_mb <= 0:
        parser.error("--timeout and --max-size-mb must be positive")

    exit_code = 0
    for path in args.pdfs:
        if not path.is_file():
            print(f"{safe_terminal(path)}: error: file does not exist")
            exit_code = max(exit_code, 2)
            continue
        if path.stat().st_size > args.max_size_mb * 1024 * 1024:
            print(
                f"{safe_terminal(path)}: error: file exceeds the "
                f"{args.max_size_mb:g} MB safety limit"
            )
            exit_code = max(exit_code, 2)
            continue
        errors, warnings, count = check_pdf(
            executable, path, args.timeout, args.allow_no_fonts
        )
        print(
            f"{safe_terminal(path)}: fonts={count} "
            f"errors={len(errors)} warnings={len(warnings)}"
        )
        for message in errors:
            print(f"  ERROR: {safe_terminal(message)}")
        for message in warnings:
            print(f"  WARN: {safe_terminal(message)}")
        if errors or (args.strict and warnings):
            exit_code = max(exit_code, 1)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
