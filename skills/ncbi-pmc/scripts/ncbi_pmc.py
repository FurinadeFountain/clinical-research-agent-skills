#!/usr/bin/env python3
"""Zero-dependency NCBI PMC metadata & JATS XML helper (Python stdlib only)."""

from __future__ import annotations

import json
import os
import re
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

PMC_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PMC_S3_BASE_URL = "https://pmc-oa-opendata.s3.amazonaws.com"
EUROPE_PMC_XML_TMPL = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"

PMCID_RE = re.compile(r"^PMC(?P<num>[0-9]+)(?:\.(?P<ver>[0-9]+))?$", re.IGNORECASE)
PMID_RE = re.compile(r"^[0-9]+$")
DOI_RE = re.compile(r"^10\.[0-9]{4,9}/[-._;()/:A-Za-z0-9]+$")

USER_AGENT = "clinical-research-agent-skills/1.0 (stdlib-urllib)"


class HttpResponse:
    def __init__(self, status_code: int, content: bytes) -> None:
        self.status_code = status_code
        self.content = content


class TransportFailure(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


FetchFn = Callable[[str, int], HttpResponse]


def _default_fetch(url: str, timeout_sec: int) -> HttpResponse:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            status = getattr(resp, "status", None) or resp.getcode() or 200
            return HttpResponse(int(status), resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp is not None else b""
        return HttpResponse(int(exc.code), body)
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise TransportFailure(type(exc).__name__) from exc


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def _normalize_pmc_num(text: str) -> str | None:
    cleaned = text.strip()
    m = PMCID_RE.match(cleaned)
    if m:
        return m.group("num")
    if cleaned.isdigit():
        return cleaned
    return None


def _parse_direct_pmcid(identifier: str) -> tuple[str, int | None] | None:
    m = PMCID_RE.match(identifier.strip())
    if not m:
        return None
    ver = int(m.group("ver")) if m.group("ver") is not None else None
    return f"PMC{m.group('num')}", ver


def _ncbi_common_params() -> dict[str, str]:
    params: dict[str, str] = {"tool": "clinical_research_agent_skills"}
    email = os.environ.get("NCBI_EMAIL", "").strip()
    api_key = os.environ.get("NCBI_API_KEY", "").strip()
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key
    return params


def _resolve_pmcids(fetch: FetchFn, identifier: str, retmax: int, timeout_sec: int) -> tuple[list[str], int]:
    ident = identifier.strip()
    if PMID_RE.match(ident):
        term = f"{ident}[PMID]"
    elif DOI_RE.match(ident):
        term = f'"{ident}"[DOI]'
    else:
        term = ident

    query = {
        **_ncbi_common_params(),
        "db": "pmc",
        "term": term,
        "retmode": "json",
        "retmax": str(retmax),
    }
    url = f"{PMC_ESEARCH_URL}?{urllib.parse.urlencode(query)}"
    resp = fetch(url, timeout_sec)
    if resp.status_code != 200:
        raise TransportFailure(f"HTTP_{resp.status_code}")
    payload = json.loads(resp.content.decode("utf-8"))
    esearch = payload.get("esearchresult", {})
    id_list = [f"PMC{str(x).removeprefix('PMC')}" for x in esearch.get("idlist", []) if str(x).strip()]
    total = int(esearch.get("count", len(id_list)) or 0)
    return id_list, total


def _list_s3_versions(fetch: FetchFn, pmcid: str, timeout_sec: int) -> list[str]:
    prefix = f"metadata/{pmcid}."
    query = urllib.parse.urlencode({"list-type": "2", "prefix": prefix})
    resp = fetch(f"{PMC_S3_BASE_URL}/?{query}", timeout_sec)
    if resp.status_code in (404, 410):
        return []
    if resp.status_code != 200:
        raise TransportFailure(f"HTTP_{resp.status_code}")
    root = ET.fromstring(resp.content)
    versions: list[tuple[int, str]] = []
    key_re = re.compile(rf"^metadata/({re.escape(pmcid)}\.(\d+))\.json$", re.IGNORECASE)
    for elem in root.iter():
        if _local_name(elem.tag) == "Key" and elem.text:
            m = key_re.match(elem.text.strip())
            if m:
                versions.append((int(m.group(2)), m.group(1)))
    versions.sort(key=lambda item: item[0], reverse=True)
    return [v[1] for v in versions]


def _fetch_s3_metadata(fetch: FetchFn, version_key: str, timeout_sec: int) -> tuple[dict[str, Any], bytes] | None:
    url = f"{PMC_S3_BASE_URL}/metadata/{urllib.parse.quote(version_key)}.json"
    resp = fetch(url, timeout_sec)
    if resp.status_code in (404, 410):
        return None
    if resp.status_code != 200:
        raise TransportFailure(f"HTTP_{resp.status_code}")
    parsed = json.loads(resp.content.decode("utf-8"))
    if not isinstance(parsed, dict):
        raise TransportFailure("InvalidMetadataJSON")
    return parsed, resp.content


def _compact_record(raw: dict[str, Any], expected_pmcid: str) -> dict[str, Any]:
    raw_pmcid = str(raw.get("pmcid") or expected_pmcid).strip()
    return {
        "pmcid": raw_pmcid,
        "version": raw.get("version"),
        "pmid": raw.get("pmid"),
        "doi": raw.get("doi"),
        "license": raw.get("license"),
        "is_open_access": raw.get("is_open_access", raw.get("open_access")),
        "is_retracted": raw.get("is_retracted", raw.get("retracted", False)),
        "xml_url": raw.get("xml_url") or raw.get("jats_xml_url"),
        "pdf_url": raw.get("pdf_url"),
    }


def _extract_xml_pmc_nums(root: ET.Element) -> set[str]:
    found: set[str] = set()
    for elem in root.iter():
        if _local_name(elem.tag) == "article-id":
            id_type = (elem.attrib.get("pub-id-type") or "").strip().lower()
            if id_type in ("pmc", "pmcid", "pmc-uid") and elem.text:
                norm = _normalize_pmc_num(elem.text)
                if norm:
                    found.add(norm)
    return found


def _fetch_free_jats_xml(
    fetch: FetchFn,
    pmcid: str,
    records: list[dict[str, Any]],
    xml_output_path: str | None,
    timeout_sec: int,
) -> dict[str, Any]:
    expected_num = _normalize_pmc_num(pmcid)
    candidates: list[tuple[str, str]] = []
    for rec in records:
        rec_num = _normalize_pmc_num(str(rec.get("pmcid") or ""))
        xurl = rec.get("xml_url")
        if rec_num == expected_num and isinstance(xurl, str) and xurl.startswith("https://"):
            candidates.append(("pmc-oa-s3", xurl))
            break
    candidates.append(("europepmc", EUROPE_PMC_XML_TMPL.format(pmcid=urllib.parse.quote(pmcid))))

    attempts: list[dict[str, Any]] = []
    for provider, url in candidates:
        try:
            resp = fetch(url, timeout_sec)
        except TransportFailure as exc:
            attempts.append({"provider": provider, "status": "request_failed", "error": exc.reason})
            continue
        except Exception as exc:  # pragma: no cover - defensive guard for custom test doubles
            attempts.append({"provider": provider, "status": "request_failed", "error": type(exc).__name__})
            continue

        if resp.status_code in (404, 410):
            attempts.append({"provider": provider, "status": "not_found", "http_status": resp.status_code})
            continue
        if resp.status_code != 200:
            attempts.append({"provider": provider, "status": "request_failed", "http_status": resp.status_code})
            continue
        if not resp.content:
            attempts.append({"provider": provider, "status": "invalid_response", "reason": "empty_body"})
            continue

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError:
            attempts.append({"provider": provider, "status": "invalid_response", "reason": "xml_parse_error"})
            continue

        if _local_name(root.tag) != "article":
            attempts.append(
                {
                    "provider": provider,
                    "status": "invalid_response",
                    "reason": f"unexpected_root_{_local_name(root.tag)}",
                }
            )
            continue

        xml_pmc_nums = _extract_xml_pmc_nums(root)
        if expected_num and xml_pmc_nums and expected_num not in xml_pmc_nums:
            attempts.append(
                {
                    "provider": provider,
                    "status": "invalid_response",
                    "reason": "pmcid_mismatch",
                }
            )
            continue

        body = next((el for el in root.iter() if _local_name(el.tag) == "body"), None)
        if body is None or not "".join(body.itertext()).strip():
            attempts.append({"provider": provider, "status": "invalid_response", "reason": "missing_or_empty_body"})
            continue

        sec_titles = [
            "".join(el.itertext()).strip()
            for sec in body
            if _local_name(sec.tag) == "sec"
            for el in sec
            if _local_name(el.tag) == "title" and "".join(el.itertext()).strip()
        ]
        out_path = Path(xml_output_path) if xml_output_path else Path(f"/tmp/{pmcid}.xml")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(resp.content)
        return {
            "free_xml_available": True,
            "status": "available",
            "attempts": attempts + [{"provider": provider, "status": "available"}],
            "xml_provider": provider,
            "xml_saved_path": str(out_path),
            "xml_bytes": len(resp.content),
            "section_titles": sec_titles,
        }

    not_found = bool(attempts) and all(a["status"] == "not_found" for a in attempts)
    return {
        "free_xml_available": False if not_found else None,
        "status": "not_found" if not_found else "unknown",
        "attempts": attempts,
        "xml_provider": None,
        "xml_saved_path": None,
        "xml_bytes": 0,
        "section_titles": [],
    }


def execute(payload: dict[str, Any], fetch: FetchFn = _default_fetch) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "error": {"code": "invalid_input", "message": "Input must be a JSON object."}}
    params = payload.get("params") or {}
    identifier = str(params.get("id") or "").strip()
    if not identifier:
        return {"ok": False, "error": {"code": "missing_id", "message": "`params.id` is required."}}

    retmax = max(1, min(int(params.get("retmax", 5)), 50))
    max_items = max(1, min(int(payload.get("max_items", 5)), 50))
    timeout_sec = max(1, min(int(payload.get("timeout_sec", 15)), 120))
    fetch_xml = bool(payload.get("fetch_xml", False))
    xml_output_path = payload.get("xml_output_path")
    save_raw = bool(payload.get("save_raw", False))
    raw_output_path = payload.get("raw_output_path")

    try:
        direct = _parse_direct_pmcid(identifier)
        requested_ver: int | None = None
        if direct is not None:
            pmcids = [direct[0]]
            requested_ver = direct[1]
            total_pmcids = 1
        else:
            pmcids, total_pmcids = _resolve_pmcids(fetch, identifier, retmax, timeout_sec)

        target_pmcid = pmcids[0] if pmcids else None
        version_keys: list[str] = []
        if target_pmcid is not None:
            if requested_ver is not None:
                version_keys = [f"{target_pmcid}.{requested_ver}"]
            else:
                version_keys = _list_s3_versions(fetch, target_pmcid, timeout_sec)

        records: list[dict[str, Any]] = []
        raw_blobs: list[bytes] = []
        warnings: list[str] = []
        if target_pmcid is not None:
            expected_num = _normalize_pmc_num(target_pmcid)
            for vkey in version_keys[:max_items]:
                fetched = _fetch_s3_metadata(fetch, vkey, timeout_sec)
                if fetched is None:
                    warnings.append(f"No PMC Open Access metadata found for {vkey}.")
                    continue
                meta_obj, raw_bytes = fetched
                rec = _compact_record(meta_obj, target_pmcid)
                if _normalize_pmc_num(str(rec.get("pmcid") or "")) != expected_num:
                    warnings.append(f"Ignored mismatched metadata record for {vkey}.")
                    continue
                records.append(rec)
                raw_blobs.append(raw_bytes)

        saved_raw_path: str | None = None
        if save_raw and raw_blobs:
            out_raw = Path(raw_output_path) if raw_output_path else Path(f"/tmp/{target_pmcid or 'pmc'}.json")
            out_raw.parent.mkdir(parents=True, exist_ok=True)
            out_raw.write_bytes(raw_blobs[0])
            saved_raw_path = str(out_raw)

        result: dict[str, Any] = {
            "ok": True,
            "source": "ncbi-pmc",
            "identifier": identifier,
            "pmcids": pmcids,
            "pmcid_count_returned": len(pmcids),
            "pmcid_count_available": total_pmcids,
            "records": records,
            "raw_output_path": saved_raw_path,
            "warnings": warnings,
        }
        if fetch_xml:
            if target_pmcid is None:
                result["fulltext_xml"] = {
                    "free_xml_available": None,
                    "status": "unresolved_identifier",
                    "attempts": [],
                    "xml_provider": None,
                    "xml_saved_path": None,
                    "xml_bytes": 0,
                    "section_titles": [],
                }
            else:
                result["fulltext_xml"] = _fetch_free_jats_xml(
                    fetch, target_pmcid, records, xml_output_path, timeout_sec
                )
            if result["fulltext_xml"]["free_xml_available"] is None:
                warnings.append(
                    "Free full-text XML availability is unknown; inspect fulltext_xml.status and attempts rather than assuming a paywall."
                )
        return result
    except (TransportFailure, ET.ParseError, ValueError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": {"code": "upstream_failure", "message": str(exc)}}


def main() -> int:
    raw = sys.stdin.read().strip()
    if not raw:
        print(json.dumps({"ok": False, "error": {"code": "empty_stdin", "message": "Expected JSON on stdin."}}))
        return 1
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(json.dumps({"ok": False, "error": {"code": "invalid_json", "message": str(exc)}}))
        return 1
    out = execute(payload)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0 if out.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
