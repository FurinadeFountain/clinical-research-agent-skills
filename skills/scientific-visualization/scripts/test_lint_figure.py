"""Physical-size and policy regression cases, using synthetic SVG fixtures only."""
import base64
import json
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch

import lint_figure as lint


def png(width, height):
    def chunk(kind, data):
        return struct.pack("!I", len(data)) + kind + data + struct.pack("!I", zlib.crc32(kind + data) & 0xffffffff)
    raw = (b"\0" + b"\xff\xff\xff" * width) * height
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack("!2I5B", width, height, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


class FigureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "figure.svg"

    def make(self, *, width=100, height=100, viewbox="0 0 100 100", image_width=100,
             image_height=100, transform="", pixels=(600, 600), aspect="", extra=""):
        image = '<image width="%s" height="%s" href="data:image/png;base64,%s"/>' % (
            image_width, image_height, base64.b64encode(png(*pixels)).decode())
        self.path.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}mm" height="{height}mm" viewBox="{viewbox}" {aspect}><g transform="{transform}">{image}</g><text font-family="Arial">A</text>{extra}</svg>')
        return lint.check_svg(self.path, "manuscript", 300, False)

    def test_viewbox_low_dpi_is_rejected(self):
        errors, warnings, meta = self.make()
        self.assertAlmostEqual(meta["raster_dpi"][0], 152.4)
        self.assertTrue(any("low effective DPI" in e for e in errors))
        self.assertEqual(warnings, [])

    def test_group_scale_high_dpi_is_accepted(self):
        errors, warnings, meta = self.make(transform="translate(10,20) rotate(30) scale(0.5)")
        self.assertAlmostEqual(meta["raster_dpi"][0], 304.8)
        self.assertEqual((errors, warnings), ([], []))

    def test_nested_transforms(self):
        self.make()
        text = self.path.read_text().replace('<g transform="">', '<g transform="scale(0.5)"><g transform="scale(0.5)">').replace('</g>', '</g></g>')
        self.path.write_text(text)
        errors, _, meta = lint.check_svg(self.path, "manuscript", 300, False)
        self.assertAlmostEqual(meta["raster_dpi"][0], 609.6)
        self.assertEqual(errors, [])

    def test_root_aspect_ratio(self):
        _, _, meet = self.make(width=150, height=50)
        _, _, none = self.make(width=150, height=50, aspect='preserveAspectRatio="none"')
        self.assertAlmostEqual(meet["raster_dpi"][0], 304.8)
        self.assertAlmostEqual(none["raster_dpi"][0], 101.6)

    def test_image_letterbox(self):
        errors, _, meta = self.make(pixels=(1200, 600), width=100, height=100)
        self.assertAlmostEqual(meta["raster_dpi"][0], 304.8)
        self.assertEqual(errors, [])

    def test_shear_worst_stretch(self):
        _, _, meta = self.make(transform="matrix(1 0 1 1 0 0)")
        self.assertLess(meta["raster_dpi"][0], 152.4)

    def test_css_is_unverified_not_passed(self):
        _, warnings, meta = self.make(extra='<style>image { transform:scale(2); }</style>')
        self.assertEqual(meta["raster_dpi"], [])
        self.assertTrue(any("DPI unverified" in w for w in warnings))

    def test_overrides_do_not_disable_dpi(self):
        self.make(width=210, extra='<text font-family="Source Han Sans SC">对照组</text>')
        errors, _, _ = lint.check_svg(self.path, "manuscript", 300, False,
                                     allow_cjk=True, allowed_fonts=["Source Han Sans SC"], max_width_mm=220)
        self.assertTrue(any("low effective DPI" in e for e in errors))
        self.assertFalse(any("CJK text" in e or "font-family" in e or "bounds" in e for e in errors))

    def test_cli_policy_overrides(self):
        self.make(width=210, pixels=(2400, 2400), extra='<text font-family="Source Han Sans SC">对照组</text>')
        result = subprocess.run([sys.executable, "-B", lint.__file__, str(self.path), "--allow-cjk", "--allow-font", "Source Han Sans SC", "--max-width-mm", "220", "--json"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["results"][0]["errors"], [])

    def test_missing_pdf_tools_is_unverified(self):
        with patch.object(lint, "find_bin", return_value=None):
            _, warnings, _ = lint.check_pdf(Path("unused.pdf"), "manuscript", 300, False)
        self.assertEqual(len(warnings), 4)


if __name__ == "__main__":
    unittest.main()
