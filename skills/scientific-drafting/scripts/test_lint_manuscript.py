"""Offline regression checks for citation coverage; no manuscript files are changed."""
import tempfile
import unittest
from pathlib import Path

from lint_manuscript import lint_file


class CitationTests(unittest.TestCase):
    def check(self, text, suffix=".md", **kwargs):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / ("sample" + suffix)
            path.write_text(text, encoding="utf-8")
            return lint_file(path, **kwargs)

    def test_missing_bibliography(self):
        errors, _, _ = self.check("# Results\nSupported [1].\n")
        self.assertTrue(any("missing from bibliography" in e for e in errors))

    def test_leading_citation_order(self):
        errors, _, meta = self.check("# Results\n[2] comes before [1].\n# References\n[1] A\n[2] B\n")
        self.assertEqual(meta["unique_numeric_citations"], 2)
        self.assertTrue(any("out-of-order" in e for e in errors))

    def test_valid_range_reuse(self):
        errors, warnings, _ = self.check("# Results\n[1–3] agree. Again [2].\n# References\n[1] A\n[2] B\n[3] C\n")
        self.assertEqual((errors, warnings), ([], []))

    def test_uncited_bibliography(self):
        _, warnings, _ = self.check("# Results\nNo citations.\n# References\n[1] A\n")
        self.assertTrue(any("never cited" in w for w in warnings))

    def test_markdown_links_code_not_citations(self):
        errors, _, meta = self.check("# Results\n[2]: https://example.org\nSee [3](https://example.org) and `[4]`.\n```\n[5]\n```\n")
        self.assertEqual(errors, [])
        self.assertEqual(meta["unique_numeric_citations"], 0)

    def test_explicit_fragment_does_not_require_global_numbers(self):
        errors, _, meta = self.check("A partial excerpt [23].\n", fragment=True)
        self.assertEqual(errors, [])
        self.assertEqual(meta["citation_check"], "fragment_counts_only")

    def test_tex_reports_unchecked_citations(self):
        _, warnings, meta = self.check(r"\section{Results} Result \cite{missing}.", ".tex")
        self.assertEqual(meta["citation_check"], "not_checked_tex")
        self.assertTrue(any("not checked" in w for w in warnings))

    def test_english_staccato_paragraph_tail_and_ratio(self):
        staccato_para = (
            "Single-molecule microscopy counted the ligands engaged between murine cytotoxic T cells and targets. "
            "Target lysis occurred with three engaged complexes while mature synapses needed ten. "
            "These counts apply to mice. "
            "Human cells were not counted. "
            "Total HLA remained unchanged."
        )
        text = "# Mechanism\n\n" + "\n\n".join([staccato_para] * 6) + "\n"
        errors, warnings, _ = self.check(text)
        self.assertEqual(errors, [])
        self.assertTrue(any("3 consecutive short fragments" in w for w in warnings))
        self.assertTrue(any("short sentences (<=12 words)" in w for w in warnings))

    def test_cohesive_english_passes_without_staccato_warning(self):
        cohesive_para = (
            "Although single-molecule imaging in murine cytotoxic T lymphocytes showed that target-cell membrane "
            "permeabilisation required as few as three engaged peptide-MHC complexes, mature synapse formation "
            "and sustained calcium mobilisation required approximately ten complexes on the contact surface. "
            "Because partial Nef-mediated HLA class I downregulation selectively reduces cognate viral epitope "
            "density without abolishing total surface class I expression, scarce viral ligands can fall below "
            "the threshold needed for productive degranulation in primary human T cells."
        )
        text = "# Mechanism\n\n" + "\n\n".join([cohesive_para] * 16) + "\n"
        errors, warnings, _ = self.check(text)
        self.assertEqual((errors, warnings), ([], []))

    def test_chinese_overloaded_defensive_sentence_warning(self):
        overloaded = (
            "## 摘要\n\n"
            "围绕上述假说，本研究尽管仅在单中心回顾性数据库及体外内皮细胞高糖培养二十四小时窗口内开展"
            "且每次血样离心前均需对低温离心机转速温控模块及酶联免疫吸附孔板洗板残留体积执行双人复核，"
            "仍拟通过多变量分位数回归联合倾向性评分匹配模型同时检验基线血浆乳酸清除率对急性肾损伤发生率、"
            "连续性肾脏替代治疗启动时机及九十天全因死亡结局的独立预测效能与亚组交互边界。\n"
        )
        errors, warnings, _ = self.check(overloaded, fragment=True)
        self.assertEqual(errors, [])
        self.assertTrue(any("overloaded Chinese sentence" in w for w in warnings))


if __name__ == "__main__":
    unittest.main()
