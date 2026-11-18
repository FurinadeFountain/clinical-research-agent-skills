#!/usr/bin/env python3
"""Stdlib-only offline regression tests for ncbi_pmc full-text verification."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import ncbi_pmc as pmc


class TestNcbiPmcFullText(unittest.TestCase):
    def _run_fetch(self, outcomes: list[object], records: list[dict[str, object]] | None = None) -> dict[str, object]:
        queue = list(outcomes)

        def fake_fetch(url: str, timeout_sec: int) -> pmc.HttpResponse:
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item  # type: ignore[return-value]

        recs = (
            records
            if records is not None
            else [{"pmcid": "PMC123", "xml_url": "https://pmc-oa-opendata.s3.amazonaws.com/PMC123.xml"}]
        )
        with tempfile.TemporaryDirectory() as tmp:
            out_xml = Path(tmp) / "PMC123.xml"
            res = pmc._fetch_free_jats_xml(fake_fetch, "PMC123", recs, str(out_xml), 3)
            self.assertEqual(out_xml.exists(), res["free_xml_available"] is True)
            return res

    def test_503_across_providers_is_unknown(self) -> None:
        res = self._run_fetch([pmc.HttpResponse(503, b"busy"), pmc.HttpResponse(503, b"busy")])
        self.assertIsNone(res["free_xml_available"])
        self.assertEqual(res["status"], "unknown")
        self.assertEqual(len(res["attempts"]), 2)

    def test_404_and_410_report_not_found(self) -> None:
        res = self._run_fetch([pmc.HttpResponse(404, b""), pmc.HttpResponse(410, b"")])
        self.assertIs(res["free_xml_available"], False)
        self.assertEqual(res["status"], "not_found")

    def test_mixed_404_and_rate_limit_remains_unknown(self) -> None:
        res = self._run_fetch([pmc.HttpResponse(404, b""), pmc.HttpResponse(429, b"rate limit")])
        self.assertIsNone(res["free_xml_available"])
        self.assertEqual(res["status"], "unknown")

    def test_timeout_falls_back_to_valid_europepmc_jats(self) -> None:
        valid_jats = (
            b'<article><front><article-meta><article-id pub-id-type="pmc">123</article-id>'
            b"</article-meta></front><body><sec><title>Methods</title><p>Data.</p></sec></body></article>"
        )
        res = self._run_fetch([pmc.TransportFailure("TimeoutError"), pmc.HttpResponse(200, valid_jats)])
        self.assertTrue(res["free_xml_available"])
        self.assertEqual(res["status"], "available")
        self.assertEqual(res["xml_provider"], "europepmc")
        self.assertEqual(res["section_titles"], ["Methods"])

    def test_xhtml_gateway_page_with_body_is_rejected(self) -> None:
        xhtml_err = b"<html><body><p>Upstream gateway error page</p></body></html>"
        res = self._run_fetch([pmc.HttpResponse(200, xhtml_err), pmc.HttpResponse(200, xhtml_err)])
        self.assertIsNone(res["free_xml_available"])
        self.assertEqual(res["status"], "unknown")
        self.assertTrue(all(a["status"] == "invalid_response" for a in res["attempts"]))

    def test_mismatched_article_pmcid_is_rejected(self) -> None:
        wrong_article = (
            b'<article><front><article-meta><article-id pub-id-type="pmc">PMC999999</article-id>'
            b"</article-meta></front><body><p>Wrong paper.</p></body></article>"
        )
        res = self._run_fetch([pmc.HttpResponse(200, wrong_article), pmc.HttpResponse(404, b"")])
        self.assertIsNone(res["free_xml_available"])
        self.assertEqual(res["status"], "unknown")
        self.assertEqual(res["attempts"][0]["reason"], "pmcid_mismatch")

    def test_namespaced_jats_article_passes(self) -> None:
        ns_jats = (
            b'<article xmlns="https://jats.nlm.nih.gov/ns/archiving/1.3/">'
            b'<front><article-meta><article-id pub-id-type="pmcid">PMC123</article-id></article-meta></front>'
            b"<body><sec><title>Results</title><p>Measured.</p></sec></body></article>"
        )
        res = self._run_fetch([pmc.HttpResponse(200, ns_jats)])
        self.assertEqual(res["status"], "available")
        self.assertEqual(res["section_titles"], ["Results"])


if __name__ == "__main__":
    unittest.main()
