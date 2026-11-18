#!/usr/bin/env python3
"""Stdlib-only offline regression tests for ncbi_entrez."""

from __future__ import annotations

import json
import unittest

import ncbi_entrez as entrez


class TestNcbiEntrez(unittest.TestCase):
    def test_rejects_unknown_endpoint(self) -> None:
        out = entrez.execute({"endpoint": "eblast", "params": {"db": "pubmed"}})
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "invalid_endpoint")

    def test_compacts_esearch_json(self) -> None:
        fake_json = json.dumps(
            {
                "esearchresult": {
                    "count": "42",
                    "idlist": ["101", "102", "103"],
                    "querytranslation": "myocardial infarction[All Fields]",
                }
            }
        ).encode("utf-8")
        out = entrez.execute(
            {"endpoint": "esearch", "params": {"db": "pubmed", "term": "myocardial infarction", "retmode": "json"}, "max_items": 2},
            fetch=lambda url, timeout: entrez.HttpResponse(200, fake_json, "application/json"),
        )
        self.assertTrue(out["ok"])
        self.assertEqual(out["count"], 42)
        self.assertEqual(out["ids"], ["101", "102"])
        self.assertTrue(out["truncated"])

    def test_reports_http_failure_cleanly(self) -> None:
        out = entrez.execute(
            {"endpoint": "esummary", "params": {"db": "gene", "id": "7157", "retmode": "json"}},
            fetch=lambda url, timeout: entrez.HttpResponse(503, b"Service Unavailable"),
        )
        self.assertFalse(out["ok"])
        self.assertEqual(out["error"]["code"], "http_503")


if __name__ == "__main__":
    unittest.main()
