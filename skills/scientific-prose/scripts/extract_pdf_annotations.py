#!/usr/bin/env python3
"""Extract PDF annotation comments and approximate highlighted text."""

from __future__ import annotations

import argparse
import json
import signal
import sys
import unicodedata
from pathlib import Path
from typing import Any


def load_pdf_libraries() -> tuple[Any, Any]:
    """Load PDF libraries from the isolated bundled runtime."""
    try:
        from pypdf import PdfReader as reader_class
        import pdfplumber as plumber_module
        return reader_class, plumber_module
    except ImportError as exc:
        raise RuntimeError(
            "pypdf and pdfplumber are required in the bundled Python runtime"
        ) from exc


def pdf_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [pdf_value(item) for item in value]
    return str(value)


def rect_to_bbox(rect: list[float], page_height: float) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = (float(value) for value in rect)
    return min(x0, x1), page_height - max(y0, y1), max(x0, x1), page_height - min(y0, y1)


def markup_rectangles(annotation: Any, fallback_rect: list[float]) -> list[list[float]]:
    quad_points = [float(value) for value in annotation.get("/QuadPoints", [])]
    rectangles: list[list[float]] = []
    for offset in range(0, len(quad_points) - 7, 8):
        quad = quad_points[offset : offset + 8]
        xs = quad[0::2]
        ys = quad[1::2]
        rectangles.append([min(xs), min(ys), max(xs), max(ys)])
    if rectangles:
        return rectangles
    return [fallback_rect] if len(fallback_rect) == 4 else []


def extract_region_text(plumber_page: Any, rectangles: list[list[float]]) -> str | None:
    if plumber_page is None or not rectangles:
        return None
    fragments: list[str] = []
    for rect in rectangles:
        bbox = rect_to_bbox(rect, float(plumber_page.height))
        text = plumber_page.crop(bbox).extract_text(x_tolerance=2, y_tolerance=2)
        normalized = " ".join(text.split()) if text else ""
        if normalized and normalized not in fragments:
            fragments.append(normalized)
    return " ".join(fragments) if fragments else None


def annotation_identity(value: Any) -> str | None:
    if value is None:
        return None
    try:
        obj = value.get_object()
        named = obj.get("/NM")
        if named:
            return str(named)
        if hasattr(value, "idnum"):
            return f"object:{value.idnum}:{getattr(value, 'generation', 0)}"
    except Exception:
        return str(value)
    return str(value)


def extract_annotations(
    path: Path, max_pages: int, max_annotations: int
) -> tuple[list[dict[str, Any]], list[str]]:
    reader_class, plumber_module = load_pdf_libraries()
    reader = reader_class(str(path))
    plumber_pdf = plumber_module.open(path) if plumber_module is not None else None
    records: list[dict[str, Any]] = []
    warnings: list[str] = []

    if len(reader.pages) > max_pages:
        raise RuntimeError(f"PDF has {len(reader.pages)} pages; limit is {max_pages}")

    try:
        for page_number, page in enumerate(reader.pages, start=1):
            plumber_page = plumber_pdf.pages[page_number - 1] if plumber_pdf is not None else None
            for annotation_index, annotation_ref in enumerate(page.get("/Annots") or [], start=1):
                annotation = annotation_ref.get_object()
                subtype = str(annotation.get("/Subtype", ""))
                if subtype in {"/Link", "/Popup"}:
                    continue
                rect = [float(value) for value in annotation.get("/Rect", [])]
                quad_points = [float(value) for value in annotation.get("/QuadPoints", [])]
                content = pdf_value(annotation.get("/Contents"))
                object_id = annotation_identity(annotation_ref)
                unique_id = str(
                    annotation.get("/NM")
                    or object_id
                    or f"page:{page_number}:annotation:{annotation_index}"
                )
                highlighted_text = None
                if subtype in {"/Highlight", "/Underline", "/StrikeOut", "/Squiggly"}:
                    highlighted_text = extract_region_text(
                        plumber_page, markup_rectangles(annotation, rect)
                    )
                    if not highlighted_text:
                        warnings.append(
                            f"page {page_number} annotation {unique_id}: no highlighted text extracted"
                        )
                record = {
                    "id": unique_id,
                    "object_id": object_id,
                    "page": page_number,
                    "annotation_index": annotation_index,
                    "subtype": subtype.removeprefix("/"),
                    "author": pdf_value(annotation.get("/T")),
                    "subject": pdf_value(annotation.get("/Subj")),
                    "modified": pdf_value(annotation.get("/M")),
                    "rectangle": rect,
                    "quad_points": quad_points,
                    "reply_to": annotation_identity(annotation.get("/IRT")),
                    "parent": annotation_identity(annotation.get("/Parent")),
                    "comment": content,
                    "highlighted_text": highlighted_text,
                }
                if content is not None or subtype not in {"/Widget"}:
                    records.append(record)
                    if len(records) > max_annotations:
                        raise RuntimeError(
                            f"annotation count exceeds the limit of {max_annotations}"
                        )
    finally:
        if plumber_pdf is not None:
            plumber_pdf.close()

    return records, warnings


def safe_terminal(value: Any) -> str:
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


def timeout_handler(_signum: int, _frame: Any) -> None:
    raise TimeoutError("PDF parsing exceeded the configured timeout")


def print_text(records: list[dict[str, Any]]) -> None:
    for index, record in enumerate(records, start=1):
        print(
            f"[{index}] id={safe_terminal(record['id'])} page={record['page']} "
            f"type={safe_terminal(record['subtype'])} "
            f"author={safe_terminal(record['author'] or '-')}"
        )
        if record["highlighted_text"]:
            print(f"highlight: {safe_terminal(record['highlighted_text'])}")
        print(f"comment: {safe_terminal(record['comment'] or '-')}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="annotated PDF to inspect")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of readable text")
    parser.add_argument(
        "--allow-missing-highlight-text",
        action="store_true",
        help="return success even when a markup annotation has no extractable text",
    )
    parser.add_argument("--timeout", type=int, default=60, help="total parsing time limit in seconds")
    parser.add_argument("--max-pages", type=int, default=2000, help="maximum PDF page count")
    parser.add_argument(
        "--max-annotations", type=int, default=10000, help="maximum actionable annotation count"
    )
    parser.add_argument(
        "--max-size-mb", type=float, default=512.0, help="maximum input PDF size"
    )
    args = parser.parse_args()

    if not args.pdf.is_file():
        parser.error(f"PDF does not exist: {args.pdf}")
    if min(args.timeout, args.max_pages, args.max_annotations, args.max_size_mb) <= 0:
        parser.error("all safety limits must be positive")
    if args.pdf.stat().st_size > args.max_size_mb * 1024 * 1024:
        parser.error(f"PDF exceeds the {args.max_size_mb:g} MB safety limit")

    try:
        if hasattr(signal, "SIGALRM"):
            signal.signal(signal.SIGALRM, timeout_handler)
            signal.alarm(args.timeout)
        records, warnings = extract_annotations(
            args.pdf.resolve(), args.max_pages, args.max_annotations
        )
    except Exception as exc:
        print(f"error: {safe_terminal(exc)}", file=sys.stderr)
        return 2
    finally:
        if hasattr(signal, "alarm"):
            signal.alarm(0)

    if args.json:
        print(json.dumps(records, ensure_ascii=False, indent=2))
    else:
        print_text(records)
        print(f"annotations={len(records)}")
    for warning in warnings:
        print(f"warning: {safe_terminal(warning)}", file=sys.stderr)
    if warnings and not args.allow_missing_highlight_text:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
