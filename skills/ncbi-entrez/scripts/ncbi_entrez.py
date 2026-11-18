#!/usr/bin/env python3
"""Zero-dependency NCBI Entrez E-Utilities helper (Python stdlib only)."""

from __future__ import annotations

import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Callable

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ALLOWED_ENDPOINTS = {"esearch", "esummary", "efetch", "elink", "einfo"}
USER_AGENT = "clinical-research-agent-skills/1.0 (stdlib-urllib)"


class HttpResponse:
    def __init__(self, status_code: int, content: bytes, content_type: str = "") -> None:
        self.status_code = status_code
        self.content = content
        self.content_type = content_type


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
            ctype = resp.headers.get("Content-Type", "") if resp.headers else ""
            return HttpResponse(int(status), resp.read(), ctype)
    except urllib.error.HTTPError as exc:
        body = exc.read() if exc.fp is not None else b""
        return HttpResponse(int(exc.code), body, "")
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError) as exc:
        raise TransportFailure(type(exc).__name__) from exc


def _ncbi_common_params() -> dict[str, str]:
    params: dict[str, str] = {"tool": "clinical_research_agent_skills"}
    email = os.environ.get("NCBI_EMAIL", "").strip()
    api_key = os.environ.get("NCBI_API_KEY", "").strip()
    if email:
        params["email"] = email
    if api_key:
        params["api_key"] = api_key
    return params


def _compact_json_payload(endpoint: str, parsed: dict[str, Any], max_items: int) -> dict[str, Any]:
    if endpoint == "esearch" and isinstance(parsed.get("esearchresult"), dict):
        er = parsed["esearchresult"]
        ids = list(er.get("idlist") or [])
        return {
            "count": int(er.get("count", len(ids)) or 0),
            "ids": ids[:max_items],
            "truncated": len(ids) > max_items,
            "querytranslation": er.get("querytranslation"),
        }
    if endpoint == "esummary" and isinstance(parsed.get("result"), dict):
        res = parsed["result"]
        uids = [str(u) for u in (res.get("uids") or [])]
        items = [res[uid] for uid in uids[:max_items] if uid in res]
        return {
            "uids": uids[:max_items],
            "records": items,
            "truncated": len(uids) > max_items,
        }
    if endpoint == "elink" and isinstance(parsed.get("linksets"), list):
        lsets = parsed["linksets"]
        return {
            "linksets": lsets[:max_items],
            "truncated": len(lsets) > max_items,
        }
    return {"summary": parsed}


def execute(payload: dict[str, Any], fetch: FetchFn = _default_fetch) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return {"ok": False, "error": {"code": "invalid_input", "message": "Input must be a JSON object."}}
    endpoint = str(payload.get("endpoint") or "").strip().lower()
    if endpoint not in ALLOWED_ENDPOINTS:
        return {
            "ok": False,
            "error": {
                "code": "invalid_endpoint",
                "message": f"`endpoint` must be one of {sorted(ALLOWED_ENDPOINTS)}.",
            },
        }

    raw_params = payload.get("params") or {}
    if not isinstance(raw_params, dict):
        return {"ok": False, "error": {"code": "invalid_params", "message": "`params` must be an object."}}

    max_items = max(1, min(int(payload.get("max_items", 10)), 100))
    timeout_sec = max(1, min(int(payload.get("timeout_sec", 15)), 120))
    save_raw = bool(payload.get("save_raw", False))
    raw_output_path = payload.get("raw_output_path")

    merged_params: dict[str, str] = {**_ncbi_common_params()}
    for k, v in raw_params.items():
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            merged_params[str(k)] = ",".join(str(x) for x in v)
        else:
            merged_params[str(k)] = str(v)

    url = f"{EUTILS_BASE}/{endpoint}.fcgi?{urllib.parse.urlencode(merged_params)}"
    try:
        resp = fetch(url, timeout_sec)
    except TransportFailure as exc:
        return {"ok": False, "error": {"code": "request_failed", "message": exc.reason}}

    if resp.status_code != 200:
        return {
            "ok": False,
            "error": {"code": f"http_{resp.status_code}", "message": f"NCBI returned HTTP {resp.status_code}."},
        }

    saved_path: str | None = None
    if save_raw:
        ext = ".json" if merged_params.get("retmode", "").lower() == "json" else ".xml"
        out_file = Path(raw_output_path) if raw_output_path else Path(f"/tmp/ncbi_{endpoint}{ext}")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_bytes(resp.content)
        saved_path = str(out_file)

    retmode = merged_params.get("retmode", "").lower()
    want_xml = payload.get("response_format", "").lower() == "xml" or retmode == "xml"
    text_body = resp.content.decode("utf-8", errors="replace")

    if not want_xml and (retmode == "json" or "json" in resp.content_type.lower()):
        try:
            parsed_json = json.loads(text_body)
            compact = _compact_json_payload(endpoint, parsed_json, max_items)
            return {
                "ok": True,
                "source": "ncbi-entrez",
                "endpoint": endpoint,
                "db": merged_params.get("db"),
                **compact,
                "raw_output_path": saved_path,
            }
        except json.JSONDecodeError as exc:
            return {"ok": False, "error": {"code": "invalid_json_response", "message": str(exc)}}

    try:
        root = ET.fromstring(resp.content)
        child_tags = [child.tag for child in list(root)[:max_items]]
        return {
            "ok": True,
            "source": "ncbi-entrez",
            "endpoint": endpoint,
            "db": merged_params.get("db"),
            "xml_root": root.tag,
            "top_elements": child_tags,
            "text_head": text_body[:4000],
            "truncated": len(text_body) > 4000,
            "raw_output_path": saved_path,
        }
    except ET.ParseError:
        return {
            "ok": True,
            "source": "ncbi-entrez",
            "endpoint": endpoint,
            "db": merged_params.get("db"),
            "text_head": text_body[:4000],
            "truncated": len(text_body) > 4000,
            "raw_output_path": saved_path,
        }


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
