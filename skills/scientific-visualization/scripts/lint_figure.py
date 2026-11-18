#!/usr/bin/env python3
"""Deterministic static linter for scientific SVG and PDF figures.

Enforces mechanical invariants that prose instructions often miss:
1. 1:1 physical dimensions (journal manuscript bounds <= 185 x 205 mm by default).
2. Editable vector text (flags Type 3 PDF fonts, unembedded fonts, or outlined-only SVGs).
3. Font-family compliance in manuscript mode (blocks DejaVu Sans, Times, or CJK font fallbacks).
4. Embedded text language in manuscript mode (blocks Chinese/CJK characters inside figure artwork).
5. Embedded raster resolution (>= 300 DPI for image panels >= 32x32 px).
"""

from __future__ import annotations

import argparse
import base64
import io
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

CJK_RE = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff\u3000-\u303f\uff01-\uff5e]")
DISALLOWED_FONT_RE = re.compile(
    r"(dejavu|bitstream\s*vera|times|georgia|calibri|verdana|courier|"
    r"simsun|simhei|pingfang|songti|heiti|kaiti|yahei|source\s*han|noto\s*sans\s*cjk|"
    r"stsong|stheit|adobesong|hiragino)",
    re.IGNORECASE,
)
MATH_OR_SYMBOL_FONT_RE = re.compile(
    r"(lmmath|latin\s*modern\s*math|cmr|cmmi|cmsy|cmex|msam|msbm|stix|zapfdingbats|symbol|kpmath)",
    re.IGNORECASE,
)
UNIT_TO_MM = {
    "mm": 1.0,
    "cm": 10.0,
    "in": 25.4,
    "pt": 25.4 / 72.0,
    "pc": 25.4 / 6.0,
    "px": 25.4 / 96.0,
}
DIM_RE = re.compile(r"^\s*([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z%]*)\s*$")
FONT_FAMILY_STYLE_RE = re.compile(r"font-family\s*:\s*([^;\"'}]+)", re.IGNORECASE)


def find_bin(name: str) -> str | None:
    found = shutil.which(name)
    if found:
        return found
    for prefix in ("/opt/homebrew/bin", "/usr/local/bin", "/usr/bin"):
        candidate = os.path.join(prefix, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return None


def parse_svg_length_mm(raw: str | None) -> tuple[float | None, str]:
    if not raw:
        return None, "missing"
    match = DIM_RE.match(raw)
    if not match:
        return None, "unparsed"
    val = float(match.group(1))
    unit = match.group(2).lower()
    if unit == "%":
        return None, "percent"
    if unit == "":
        return val * UNIT_TO_MM["px"], "unitless"
    if unit not in UNIT_TO_MM:
        return None, unit
    return val * UNIT_TO_MM[unit], unit


def raster_pixel_size(data: bytes) -> tuple[int, int] | None:
    try:
        from PIL import Image  # type: ignore

        with Image.open(io.BytesIO(data)) as im:
            return im.size
    except Exception:
        pass
    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        w, h = struct.unpack(">II", data[16:24])
        return int(w), int(h)
    return None


def local_tag(tag: str) -> str:
    return tag.split("}", 1)[-1] if "}" in tag else tag


def linear_product(left, right):
    """Compose the linear parts of SVG affine transforms; translations do not affect DPI."""
    a, b, c, d = left
    e, f, g, h = right
    return (a * e + c * f, b * e + d * f, a * g + c * h, b * g + d * h)


def transform_linear(value: str):
    result = (1.0, 0.0, 0.0, 1.0)
    tokens = list(re.finditer(r"([A-Za-z]+)\s*\(([^)]*)\)", value))
    if re.sub(r"([A-Za-z]+)\s*\(([^)]*)\)", "", value).strip(" ,\t\n"):
        raise ValueError("unsupported transform syntax")
    for token in tokens:
        name = token[1]
        nums = [float(n) for n in re.split(r"[\s,]+", token[2].strip()) if n]
        if not all(math.isfinite(n) for n in nums):
            raise ValueError("non-finite transform")
        if name == "matrix" and len(nums) == 6:
            part = tuple(nums[:4])
        elif name == "scale" and len(nums) in (1, 2):
            part = (nums[0], 0.0, 0.0, nums[-1])
        elif name == "translate" and len(nums) in (1, 2):
            part = (1.0, 0.0, 0.0, 1.0)
        elif name == "rotate" and len(nums) in (1, 3):
            angle = math.radians(nums[0])
            part = (math.cos(angle), math.sin(angle), -math.sin(angle), math.cos(angle))
        elif name in ("skewX", "skewY") and len(nums) == 1:
            shear = math.tan(math.radians(nums[0]))
            part = (1.0, 0.0, shear, 1.0) if name == "skewX" else (1.0, shear, 0.0, 1.0)
        else:
            raise ValueError("unsupported transform")
        result = linear_product(result, part)
    return result


def svg_image_matrices(root, width_mm, height_mm):
    """Map user coordinates to physical mm. Unsupported layout is explicitly unverified."""
    scale = None
    if width_mm and height_mm:
        vb = root.get("viewBox")
        if vb:
            try:
                values = [float(x) for x in re.split(r"[\s,]+", vb.strip())]
                if len(values) != 4 or not all(math.isfinite(x) for x in values) or min(values[2:]) <= 0:
                    raise ValueError("invalid viewBox")
                sx, sy = width_mm / values[2], height_mm / values[3]
                aspect = root.get("preserveAspectRatio", "xMidYMid meet").split()
                if "none" not in aspect:
                    sx = sy = max(sx, sy) if "slice" in aspect else min(sx, sy)
                scale = (sx, 0.0, 0.0, sy)
            except ValueError:
                pass
        else:
            scale = (UNIT_TO_MM["px"], 0.0, 0.0, UNIT_TO_MM["px"])
    # CSS layout needs a renderer. Do not silently treat it as an SVG attribute.
    css_layout = any(local_tag(e.tag) == "style" and re.search(r"\b(?:transform|width|height)\s*:", e.text or "") for e in root.iter())
    matrices = {}
    def walk(elem, current):
        if css_layout or (elem is not root and local_tag(elem.tag) == "svg") or re.search(r"\b(?:transform|width|height)\s*:", elem.get("style", "")):
            current = None
        if current is not None:
            try:
                current = linear_product(current, transform_linear(elem.get("transform", "")))
            except ValueError:
                current = None
        matrices[elem] = current
        for child in elem:
            walk(child, current)
    walk(root, scale)
    return matrices


def image_dpi(elem, pixels, matrix):
    if matrix is None:
        return None
    w, _ = parse_svg_length_mm(elem.get("width"))
    h, _ = parse_svg_length_mm(elem.get("height"))
    if not w or not h or min(pixels) <= 0:
        return None
    # CSS absolute units convert to local user units; viewBox/ancestor transforms
    # then convert those user units to final physical size.
    sx = w / UNIT_TO_MM["px"] / pixels[0]
    sy = h / UNIT_TO_MM["px"] / pixels[1]
    aspect = elem.get("preserveAspectRatio", "xMidYMid meet").split()
    if "none" not in aspect:
        sx = sy = max(sx, sy) if "slice" in aspect else min(sx, sy)
    a, b, c, d = linear_product(matrix, (sx, 0.0, 0.0, sy))
    # Largest singular value is the worst physical pixel stretch, including shear.
    trace = a*a + b*b + c*c + d*d
    disc = max(0.0, trace*trace - 4 * (a*d - b*c)**2)
    stretch = math.sqrt((trace + math.sqrt(disc)) / 2)
    return 25.4 / stretch if stretch > 0 and math.isfinite(stretch) else None


def disallowed_font(name: str, allowed_fonts) -> bool:
    normalize = lambda s: re.sub(r"[\s_-]", "", s).casefold()
    if any(normalize(name).startswith(normalize(f)) for f in allowed_fonts if f.strip()):
        return False
    return bool(DISALLOWED_FONT_RE.search(name))


def check_svg(
    path: Path, mode: str, min_dpi: float, allow_no_text: bool,
    *, allow_cjk=False, allowed_fonts=(), max_width_mm=185.0, max_height_mm=205.0,
) -> tuple[list[str], list[str], dict[str, object]]:
    errors: list[str] = []
    warnings: list[str] = []
    meta: dict[str, object] = {"format": "svg"}
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        return [f"invalid SVG XML: {exc}"], [], meta

    root = tree.getroot()
    w_mm, w_unit = parse_svg_length_mm(root.get("width"))
    h_mm, h_unit = parse_svg_length_mm(root.get("height"))
    meta["width_mm"] = round(w_mm, 2) if w_mm is not None else None
    meta["height_mm"] = round(h_mm, 2) if h_mm is not None else None

    if w_unit in ("unitless", "px", "missing", "percent") or h_unit in (
        "unitless",
        "px",
        "missing",
        "percent",
    ):
        warnings.append(
            f"SVG root width/height uses '{w_unit}/{h_unit}' instead of explicit physical units (mm/in/pt)"
        )
    if mode == "manuscript" and w_mm is not None and h_mm is not None:
        if w_mm > max_width_mm or h_mm > max_height_mm:
            errors.append(
                f"canvas size {w_mm:.1f} x {h_mm:.1f} mm exceeds selected bounds ({max_width_mm:g} x {max_height_mm:g} mm)"
            )

    text_nodes = 0
    path_nodes = 0
    cjk_hits: list[str] = []
    bad_fonts: set[str] = set()
    matrices = svg_image_matrices(root, w_mm, h_mm)
    raster_dpis = []
    if any(local_tag(e.tag) == "use" for e in root.iter()):
        warnings.append("SVG <use> instances not expanded; instance-specific raster DPI/text coverage unverified")

    for elem in root.iter():
        tname = local_tag(elem.tag)
        if tname == "path":
            path_nodes += 1
        elif tname in ("text", "tspan"):
            if tname == "text":
                text_nodes += 1
            for chunk in (elem.text, elem.tail):
                if chunk and CJK_RE.search(chunk):
                    snippet = " ".join(chunk.strip().split())
                    if snippet and snippet not in cjk_hits:
                        cjk_hits.append(snippet[:40])
        elif tname == "style" and elem.text and mode == "manuscript":
            for m in FONT_FAMILY_STYLE_RE.finditer(elem.text):
                primary = m.group(1).split(",")[0].strip().strip("'\"")
                if disallowed_font(primary, allowed_fonts):
                    bad_fonts.add(primary)
        elif tname == "image":
            href = (
                elem.get("{http://www.w3.org/1999/xlink}href")
                or elem.get("href")
                or ""
            )
            raw_bytes: bytes | None = None
            if href.startswith("data:image/") and ";base64," in href:
                try:
                    raw_bytes = base64.b64decode(href.split(";base64,", 1)[1])
                except Exception:
                    raw_bytes = None
            elif href and not href.startswith(("http://", "https://")):
                img_path = (path.parent / href).resolve()
                if img_path.is_file():
                    raw_bytes = img_path.read_bytes()
            if raw_bytes:
                px = raster_pixel_size(raw_bytes)
                if px and px[0] >= 32 and px[1] >= 32:
                    eff = image_dpi(elem, px, matrices[elem])
                    if eff is None:
                        warnings.append("SVG raster DPI unverified: unresolved dimensions, CSS, nested viewport, or transform")
                    else:
                        raster_dpis.append(round(eff, 2))
                    if eff is not None and eff < min_dpi:
                        errors.append(
                            f"embedded SVG raster image ({px[0]}x{px[1]} px) has low effective DPI {eff:.0f} < {min_dpi:.0f}"
                        )
                elif px is None:
                    warnings.append("SVG image pixel dimensions could not be decoded; raster DPI unverified")
            else:
                warnings.append("SVG image unavailable locally or invalid image data; raster DPI unverified")

        if mode == "manuscript":
            ff_attr = elem.get("font-family")
            if ff_attr:
                primary = ff_attr.split(",")[0].strip().strip("'\"")
                if disallowed_font(primary, allowed_fonts):
                    bad_fonts.add(primary)
            style_attr = elem.get("style")
            if style_attr:
                for m in FONT_FAMILY_STYLE_RE.finditer(style_attr):
                    primary = m.group(1).split(",")[0].strip().strip("'\"")
                    if disallowed_font(primary, allowed_fonts):
                        bad_fonts.add(primary)

    meta["text_nodes"] = text_nodes
    meta["path_nodes"] = path_nodes
    meta["raster_dpi"] = raster_dpis

    if text_nodes == 0 and path_nodes >= 20 and not allow_no_text:
        errors.append(
            f"0 editable <text> elements found ({path_nodes} <path> nodes); ensure svg.fonttype='none' rather than outlined text"
        )
    if mode == "manuscript" and cjk_hits and not allow_cjk:
        errors.append(
            f"Chinese/CJK text found inside manuscript figure: {cjk_hits[:5]}"
        )
    if mode == "manuscript" and bad_fonts:
        errors.append(
            f"disallowed primary font-family in manuscript figure (use Arial/Helvetica + Latin Modern Math): {sorted(bad_fonts)}"
        )

    return errors, warnings, meta


def parse_pdffonts(output: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for line in output.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("name") or set(stripped) == {"-"}:
            continue
        cols = stripped.split()
        if len(cols) < 8:
            continue
        middle = cols[1:-5]
        if len(middle) < 2:
            continue
        rows.append(
            {
                "name": cols[0],
                "type": " ".join(middle[:-1]),
                "encoding": middle[-1],
                "embedded": cols[-5],
                "subset": cols[-4],
                "unicode": cols[-3],
            }
        )
    return rows


def check_pdf(
    path: Path, mode: str, min_dpi: float, allow_no_text: bool,
    *, allow_cjk=False, allowed_fonts=(), max_width_mm=185.0, max_height_mm=205.0,
) -> tuple[list[str], list[str], dict[str, object]]:
    errors: list[str] = []
    warnings: list[str] = []
    meta: dict[str, object] = {"format": "pdf"}

    pdfinfo_bin = find_bin("pdfinfo")
    pdffonts_bin = find_bin("pdffonts")
    pdftotext_bin = find_bin("pdftotext")
    pdfimages_bin = find_bin("pdfimages")

    if pdfinfo_bin:
        res = subprocess.run(
            [pdfinfo_bin, str(path)], capture_output=True, text=True, timeout=20
        )
        if res.returncode == 0:
            m = re.search(
                r"Page size:\s*([0-9.]+)\s*x\s*([0-9.]+)\s*pts", res.stdout
            )
            if m:
                w_mm = float(m.group(1)) * UNIT_TO_MM["pt"]
                h_mm = float(m.group(2)) * UNIT_TO_MM["pt"]
                meta["width_mm"] = round(w_mm, 2)
                meta["height_mm"] = round(h_mm, 2)
                if mode == "manuscript" and (w_mm > max_width_mm or h_mm > max_height_mm):
                    errors.append(
                        f"PDF page size {w_mm:.1f} x {h_mm:.1f} mm exceeds selected bounds ({max_width_mm:g} x {max_height_mm:g} mm)"
                    )
            else:
                warnings.append("PDF page size not parsed; physical-size check unverified")
        else:
            errors.append(f"pdfinfo failed: {res.stderr.strip()}")
    else:
        warnings.append("pdfinfo binary not found; physical-size check unverified")

    if pdffonts_bin:
        res = subprocess.run(
            [pdffonts_bin, str(path)], capture_output=True, text=True, timeout=20
        )
        if res.returncode != 0:
            errors.append(f"pdffonts failed: {res.stderr.strip()}")
        else:
            rows = parse_pdffonts(res.stdout)
            meta["fonts_count"] = len(rows)
            if not rows and not allow_no_text:
                errors.append(
                    "no embedded fonts reported in PDF (text may be rasterized or outlined)"
                )
            bad_fonts: set[str] = set()
            for r in rows:
                clean_name = r["name"].split("+", 1)[-1]
                if r["embedded"].lower() != "yes":
                    errors.append(f"unembedded font: {r['name']} ({r['type']})")
                if "type 3" in r["type"].lower():
                    errors.append(
                        f"Type 3 font detected (set pdf.fonttype=42): {r['name']}"
                    )
                if (
                    r["unicode"].lower() != "yes"
                    and not MATH_OR_SYMBOL_FONT_RE.search(clean_name)
                ):
                    warnings.append(f"font lacks ToUnicode map: {r['name']}")
                if mode == "manuscript" and disallowed_font(clean_name, allowed_fonts):
                    bad_fonts.add(clean_name)
            if bad_fonts:
                errors.append(
                    f"disallowed PDF font in manuscript figure (use Arial/Helvetica + Latin Modern Math): {sorted(bad_fonts)}"
                )
    else:
        warnings.append("pdffonts binary not found; skipped font table check")

    if pdftotext_bin and mode == "manuscript" and not allow_cjk:
        res = subprocess.run(
            [pdftotext_bin, str(path), "-"],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if res.returncode != 0:
            warnings.append("pdftotext failed; text-language check unverified")
        elif CJK_RE.search(res.stdout):
            hits = []
            for line in res.stdout.splitlines():
                if CJK_RE.search(line):
                    s = " ".join(line.strip().split())
                    if s and s not in hits:
                        hits.append(s[:40])
            errors.append(
                f"Chinese/CJK text found inside manuscript PDF figure: {hits[:5]}"
            )
    elif mode == "manuscript" and not allow_cjk:
        warnings.append("pdftotext binary not found; text-language check unverified")

    if pdfimages_bin:
        res = subprocess.run(
            [pdfimages_bin, "-list", str(path)],
            capture_output=True,
            text=True,
            timeout=20,
        )
        if res.returncode == 0:
            for line in res.stdout.splitlines():
                cols = line.split()
                if len(cols) >= 14 and cols[0].isdigit() and cols[1].isdigit():
                    img_type = cols[2]
                    if img_type != "image":
                        continue
                    try:
                        w_px = int(cols[3])
                        h_px = int(cols[4])
                        x_ppi = float(cols[12])
                        y_ppi = float(cols[13])
                    except ValueError:
                        continue
                    if w_px >= 32 and h_px >= 32:
                        eff = min(x_ppi, y_ppi)
                        if eff < min_dpi:
                            errors.append(
                                f"embedded PDF raster image #{cols[1]} ({w_px}x{h_px} px) has low PPI {eff:.0f} < {min_dpi:.0f}"
                            )
        else:
            warnings.append("pdfimages failed; raster-resolution check unverified")
    else:
        warnings.append("pdfimages binary not found; raster-resolution check unverified")

    return errors, warnings, meta


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("figures", nargs="+", type=Path, help="SVG or PDF figure files")
    parser.add_argument(
        "--mode",
        choices=("manuscript", "slide"),
        default="manuscript",
        help="target medium ruleset (default: manuscript)",
    )
    parser.add_argument(
        "--min-dpi",
        type=float,
        default=300.0,
        help="minimum effective DPI for embedded raster panels >=32x32 px",
    )
    parser.add_argument(
        "--allow-no-text",
        action="store_true",
        help="permit intentionally text-free figures",
    )
    parser.add_argument(
        "--strict", action="store_true", help="treat warnings as exit-1 failures"
    )
    parser.add_argument("--json", action="store_true", help="emit JSON report")
    parser.add_argument("--allow-cjk", action="store_true", help="permit CJK labels when specified by the user or venue")
    parser.add_argument("--allow-font", action="append", default=[], help="permit a specified font family (repeatable)")
    parser.add_argument("--max-width-mm", type=float, default=185.0, help="selected manuscript width limit, not a universal journal rule")
    parser.add_argument("--max-height-mm", type=float, default=205.0, help="selected manuscript height limit")
    args = parser.parse_args()
    if any(not math.isfinite(v) or v <= 0 for v in (args.min_dpi, args.max_width_mm, args.max_height_mm)):
        parser.error("DPI and size limits must be positive finite numbers")
    overrides = dict(allow_cjk=args.allow_cjk, allowed_fonts=args.allow_font,
                     max_width_mm=args.max_width_mm, max_height_mm=args.max_height_mm)

    results = []
    exit_code = 0
    for fig in args.figures:
        if not fig.is_file():
            results.append(
                {"file": str(fig), "errors": ["file does not exist"], "warnings": []}
            )
            exit_code = max(exit_code, 2)
            continue
        ext = fig.suffix.lower()
        if ext == ".svg":
            errs, warns, meta = check_svg(
                fig, args.mode, args.min_dpi, args.allow_no_text, **overrides
            )
        elif ext == ".pdf":
            errs, warns, meta = check_pdf(
                fig, args.mode, args.min_dpi, args.allow_no_text, **overrides
            )
        else:
            errs, warns, meta = (
                [f"unsupported extension '{ext}' (expected .svg or .pdf)"],
                [],
                {},
            )
        if errs or (args.strict and warns):
            exit_code = max(exit_code, 1)
        results.append(
            {"file": str(fig), "meta": meta, "errors": errs, "warnings": warns}
        )

    if args.json:
        print(json.dumps({"mode": args.mode, "results": results}, ensure_ascii=False, indent=2))
    else:
        for item in results:
            status = (
                "FAIL"
                if item["errors"] or (args.strict and item["warnings"])
                else ("WARN" if item["warnings"] else "PASS")
            )
            dims = ""
            m = item.get("meta", {})
            if m.get("width_mm") and m.get("height_mm"):
                dims = f" [{m['width_mm']}x{m['height_mm']} mm]"
            print(
                f"[{status}] {item['file']}{dims} "
                f"(errors={len(item['errors'])}, warnings={len(item['warnings'])})"
            )
            for e in item["errors"]:
                print(f"  ERROR: {e}")
            for w in item["warnings"]:
                print(f"  WARN : {w}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
