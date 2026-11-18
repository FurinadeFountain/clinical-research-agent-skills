#!/usr/bin/env python3
"""Pair cited Markdown passages by DOI for a subsequent human semantic review.

Usage: compare_cited_passages.py OLD_MAIN OLD_SUPP NEW_MAIN NEW_SUPP --output FILE

Supported: one prose paragraph per source line; ATX/HTML section headings; DOI
links/plain DOIs; numeric links, bare numeric citations and numeric reference
definitions; numbered bibliographies headed References/Bibliography/参考文献,
with optional HTML anchors; ordinary HTML and Markdown table rows. Main and
supplement share reference lookup within each version. A local bibliography
takes precedence; conflicting fallback numbers remain unresolved. No network,
author-year resolution, nested-table support, similarity score or scientific
pass/fail is provided. Export soft-wrapped prose as one paragraph per line first.

Exit 0 means the report was written with no detected unresolved citations or
parse issues; it does NOT mean claims were preserved. Exit 1 leaves those issues
in the report. Retained/removed/added describe cited DOI identity only. Text is
stored once per block; inspect all blocks for each DOI, including table context,
for population, model, comparison, timing, outcome and scope of the conclusion.
`citation_label_only_pairs` is a mechanical hint, not approval to reuse a claim:
only simple Markdown doi.org links with visible bracketed single-number citation
labels are canonicalized; all other passage text and formatting remain exact.

Optional: --source-manifest MANIFEST [--source-index FILE]. Manifest format is
{"articles": {"doi": {"file": "relative/to/manifest.xml"}}}. Only the specified
JATS XML files are read; JSON caches and automatic retrieval are unsupported.
Source context is indexed once by DOI (inline, or in FILE), with actual headings,
figure labels and absolute element paths. Paths use local tag names and 1-based
same-tag sibling positions, ignoring namespaces. Missing sources and metadata DOI
mismatches are explicit. Indexed means structurally located, not scientifically
verified; this optional coverage does not change the citation-parsing exit code.
"""

import argparse
from bisect import bisect_right
from collections import Counter, defaultdict
import html
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit
import xml.etree.ElementTree as ET


DOI = re.compile(r"10\.\d{4,9}/[-A-Z0-9._;()/+:=%]+", re.I)
MD_LINK = re.compile(r"(!?)\[((?:\\.|[^\]\\])*)\]\(")
HTML_LINK = re.compile(r"<a\b[^>]*\bhref\s*=\s*([\"'])(.*?)\1[^>]*>(.*?)</a\s*>", re.I | re.S)
ANCHOR = re.compile(r"\b(?:id|name)\s*=\s*([\"'])(.*?)\1", re.I)
NUMERIC = re.compile(r"\d+(?:\s*[,;，、–—-]\s*\d+)*")
REF_ANCHOR = re.compile(r"(?:ref(?:erence)?|bib|cite)[-_: .]?(\d+)$", re.I)


def plain(text):
    return html.unescape(re.sub(r"<[^>]+>", "", text)).replace("\\[", "[").replace("\\]", "]")


def dois(text):
    text = html.unescape(unquote(text))
    found = set()
    for match in DOI.finditer(text):
        value = match.group().rstrip(".,;:")
        while value.endswith(")") and value.count(")") > value.count("("):
            value = value[:-1]
        if re.search(r"(?:biorxiv|medrxiv)\.org/content/$", text[max(0, match.start() - 70):match.start()], re.I):
            value = re.sub(r"v\d+$", "", value)
        if value:
            found.add(value.lower())
    return found


def heading(line):
    match = re.match(r"^\s{0,3}(#{1,6})\s+(.+?)\s*#*\s*$", line)
    if match:
        return len(match[1]), plain(match[2]).strip()
    match = re.match(r"^\s*<h([1-6])\b[^>]*>(.*?)</h\1>\s*$", line, re.I)
    return (int(match[1]), plain(match[2]).strip()) if match else None


def load_document(path, role):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines(keepends=True)
    offsets = [0]
    for line in lines:
        offsets.append(offsets[-1] + len(line))
    doc = dict(path=str(path.resolve()), role=role, text=text, lines=lines,
               offsets=offsets, skip=set(), sections=[], refs=defaultdict(set))
    section, bib_level, fence, entry = [], None, None, []

    def save_entry():
        if not entry:
            return
        raw = "".join(entry)
        label = re.match(r"\s*(?:\[(\d+)\]|(\d+)[.)])", plain(raw))
        keys = ["n:" + next(g for g in label.groups() if g)] if label else []
        keys += ["a:" + m[2] for m in ANCHOR.finditer(raw)]
        for key in keys:
            doc["refs"][key].update(dois(raw))
        entry.clear()

    for i, line in enumerate(lines):
        marker = re.match(r"^\s*(`{3,}|~{3,})", line)
        if fence:
            doc["skip"].add(i)
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence):
                fence = None
            doc["sections"].append(list(section))
            continue
        if marker:
            fence = marker[1]
            doc["skip"].add(i)
        title = heading(line)
        if title:
            level, name = title
            if bib_level is not None and level <= bib_level:
                save_entry()
                bib_level = None
            section = section[:level - 1]
            section.extend([""] * (level - 1 - len(section)))
            section.append(name)
            if re.match(r"^(?:\d+[.、 ]\s*)?(?:references\b|bibliography\b|参考文献)", name, re.I):
                bib_level = level
            doc["skip"].add(i)
        doc["sections"].append([s for s in section if s])
        definition = re.match(r"^\s{0,3}\[(\d+)\]:\s*(.+)", line)
        if definition:
            doc["refs"]["n:" + definition[1]].update(dois(definition[2]))
            doc["skip"].add(i)
        if bib_level is not None:
            doc["skip"].add(i)
            if title:
                continue
            starts_entry = re.match(r"\s*(?:\[\d+\]|\d+[.)])\s*", plain(line))
            if starts_entry and plain("".join(entry)).strip():
                save_entry()
            entry.append(line)
    save_entry()
    doc["refs"] = dict(doc["refs"])
    return doc


def links(text):
    """Read simple Markdown labels with balanced URL parentheses, plus HTML links."""
    found = []
    for match in MD_LINK.finditer(text):
        depth, end = 1, match.end()
        while end < len(text) and depth:
            if text[end] == "\\":
                end += 2
                continue
            depth += (text[end] == "(") - (text[end] == ")")
            end += 1
        if not depth:
            target = text[match.end():end - 1].strip().split()[0] if text[match.end():end - 1].strip() else ""
            found.append((match.start(), end, match[2], target.strip("<>"), bool(match[1])))
    for match in HTML_LINK.finditer(text):
        found.append((match.start(), match.end(), plain(match[3]), html.unescape(match[2]), False))
    return sorted(found)


def numbers(label):
    label = plain(label).strip(" []^*")
    if not NUMERIC.fullmatch(label):
        return None
    result = []
    for part in re.split(r"[,;，、]", label):
        ends = re.split(r"[–—-]", part.strip())
        first, last = int(ends[0]), int(ends[-1])
        if first < 1 or first > last or last - first > 1000:
            return []
        result.extend(str(n) for n in range(first, last + 1))
    return result


def resolve(doc, documents, number, target=""):
    url = urlsplit(target)
    candidates = documents
    if url.path and not url.scheme and not url.netloc:
        dest = str((Path(doc["path"]).parent / unquote(url.path)).resolve())
        candidates = [d for d in documents if d["path"] == dest]
        if not candidates:
            return set(), "citation points outside the supplied documents"
    fragment = unquote(url.fragment)
    keys = ["n:" + number] if number else []
    if fragment:
        match = REF_ANCHOR.fullmatch(fragment)
        if any("a:" + fragment in d["refs"] for d in candidates):
            keys = ["a:" + fragment]
        elif match:
            keys = ["n:" + match[1]]
    for key in keys:
        local = doc if doc in candidates else None
        pool = [local] if local and key in local["refs"] else candidates
        present = [d["refs"][key] for d in pool if key in d["refs"]]
        found = set().union(*present) if present else set()
        if len(found) == 1:
            return found, None
        if found:
            return found, "ambiguous reference maps to multiple DOIs"
        if present:
            return set(), "reference entry has no recognized DOI"
    return set(), "no matching DOI-bearing reference entry"


def citations(text, doc, documents):
    original = text
    # Equations and code can contain numeric intervals that are not citations.
    text = re.sub(r"(`+).*?\1|\$\$.*?\$\$|(?<!\\)\$[^$\n]*?(?<!\\)\$|\\\(.*?\\\)",
                  lambda m: " " * len(m[0]), text, flags=re.S)
    found, unresolved, masked, citation_spans = set(), [], list(text), []
    for start, end, label, target, image in links(text):
        masked[start:end] = " " * (end - start)
        if image:
            continue
        direct = dois(target)
        labels = numbers(label)
        fragment = unquote(urlsplit(target).fragment)
        is_reference = labels is not None or bool(REF_ANCHOR.fullmatch(fragment)) or any("a:" + fragment in d["refs"] for d in documents)
        if direct:
            found.update(direct)
            if labels:
                for number in labels:
                    expected, reason = resolve(doc, documents, number)
                    if expected and (reason or not direct.issubset(expected)):
                        unresolved.append(dict(reference=label, target=target, reason="DOI link conflicts with its reference number", candidate_dois=sorted(expected)))
            source_link = MD_LINK.match(original, start)
            url = urlsplit(target)
            if (source_link and len(direct) == 1 and labels and len(labels) == 1
                    and re.fullmatch(r"\[\s*\d+\s*\]", plain(label).strip())
                    and url.scheme in ["http", "https"] and url.netloc.lower() in ["doi.org", "dx.doi.org"]
                    and original[source_link.end():end - 1].strip() in [target, "<" + target + ">"]):
                citation_spans.append((start, end, tuple(sorted(direct))))
        elif is_reference:
            if labels == []:
                unresolved.append(dict(reference=label, target=target, reason="invalid or excessive numeric range"))
            else:
                for number in labels or [None]:
                    expected, reason = resolve(doc, documents, number, target)
                    if reason:
                        unresolved.append(dict(reference=number or label, target=target, reason=reason, candidate_dois=sorted(expected)))
                    else:
                        found.update(expected)
        elif re.search(r"(?:doi\.org/|\bdoi:)", target, re.I):
            unresolved.append(dict(reference=label, target=target, reason="unrecognized DOI link"))
    remainder = "".join(masked)
    found.update(dois(remainder))
    for match in re.finditer(r"\\?\[\s*(\d+(?:\s*[,;，、–—-]\s*\d+)*)\s*\\?\]", remainder):
        labels = numbers(match[1])
        if labels == []:
            unresolved.append(dict(reference=match[0], reason="invalid or excessive numeric range"))
        for number in labels or []:
            expected, reason = resolve(doc, documents, number)
            if reason:
                unresolved.append(dict(reference=number, reason=reason, candidate_dois=sorted(expected)))
            else:
                found.update(expected)
    key, previous = [], 0
    for start, end, identity in citation_spans:
        key.extend([original[previous:start], identity])
        previous = end
    key.append(original[previous:])
    return sorted(found), unresolved, tuple(key) if citation_spans and not unresolved else None


def passages(doc, side):
    units, issues, skip = [], [], set(doc["skip"])
    lines, offsets = doc["lines"], doc["offsets"]

    def add(raw, start, end, kind="prose", context=()):
        first = bisect_right(offsets, start) - 1
        last = bisect_right(offsets, max(start, end - 1)) - 1
        unit = dict(id=f"{side}-{doc['role']}-{len(units) + 1}", file=doc["path"],
                    line_start=first + 1, line_end=last + 1, section=doc["sections"][first],
                    kind=kind, text=raw.rstrip("\r\n"), dois=[], context_ids=list(context))
        units.append(unit)
        return unit["id"]

    i = 0
    while i < len(lines):
        if i in skip or not lines[i].strip():
            i += 1
            continue
        if re.search(r"<table\b", lines[i], re.I):
            end = i
            while end < len(lines) and not re.search(r"</table\s*>", lines[end], re.I):
                end += 1
            if end == len(lines):
                issues.append(dict(file=doc["path"], line=i + 1, reason="unclosed HTML table; retained as one fallback passage"))
                end -= 1
            raw = "".join(lines[i:end + 1])
            rows = list(re.finditer(r"<tr\b[^>]*>.*?</tr\s*>", raw, re.I | re.S))
            if not rows or len(rows) != len(re.findall(r"<tr\b", raw, re.I)):
                issues.append(dict(file=doc["path"], line=i + 1, reason="HTML table rows could not be fully parsed; retained as one fallback passage"))
                add(raw, offsets[i], offsets[end + 1], "table_fallback")
            else:
                header = None
                for n, row in enumerate(rows):
                    is_header = bool(re.search(r"<th\b", row[0], re.I)) or (n == 0 and bool(re.search(r'header-row\s*=\s*[\"\']true', raw[:rows[0].start()], re.I)))
                    key = add(row[0], offsets[i] + row.start(), offsets[i] + row.end(), "table_header" if is_header else "table_row", [header] if header and not is_header else [])
                    if is_header:
                        header = key
            i = end + 1
            continue
        if i + 1 < len(lines) and "|" in lines[i] and re.fullmatch(r"\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*", lines[i + 1]):
            header = add(lines[i], offsets[i], offsets[i + 1], "table_header")
            i += 2
            while i < len(lines) and i not in skip and lines[i].strip() and "|" in lines[i]:
                add(lines[i], offsets[i], offsets[i + 1], "table_row", [header])
                i += 1
            continue
        if re.search(r"</?(?:table|tr|td|th)\b", lines[i], re.I):
            issues.append(dict(file=doc["path"], line=i + 1, reason="table markup outside a parsed table"))
        add(lines[i], offsets[i], offsets[i + 1])
        i += 1
    return units, issues


def compare(old_main, old_supp, new_main, new_supp):
    report = dict(scope="DOI identity and exact/citation-label-only passage comparison are mechanical hints, not semantic passes. Review every cited old/new block and its new context.",
                  review_axes=["population", "model", "comparison", "timing", "outcome", "conclusion_scope"],
                  blocks={}, studies=[], unresolved=[], parse_issues=[])
    citation_keys = {}
    for side, paths in [("old", [old_main, old_supp]), ("new", [new_main, new_supp])]:
        documents = [load_document(path, role) for path, role in zip(paths, ["main", "supplement"])]
        all_units = []
        for doc in documents:
            units, issues = passages(doc, side)
            report["parse_issues"].extend(dict(side=side, **issue) for issue in issues)
            for unit in units:
                unit["dois"], unresolved, key = citations(unit["text"], doc, documents)
                if key is not None and unit["kind"] != "table_fallback":
                    citation_keys[unit["id"]] = key
                report["unresolved"].extend(dict(side=side, block_id=unit["id"], **issue) for issue in unresolved)
            all_units.extend(units)
        keep = {u["id"] for u in all_units if u["dois"]} | {u["block_id"] for u in report["unresolved"] if u["side"] == side}
        keep.update(c for u in all_units if u["id"] in keep for c in u["context_ids"])
        report["blocks"][side] = [u for u in all_units if u["id"] in keep]
    indexes = {side: defaultdict(list) for side in ["old", "new"]}
    for side, blocks in report["blocks"].items():
        for block in blocks:
            for doi in block["dois"]:
                indexes[side][doi].append(block)
    for doi in sorted(set(indexes["old"]) | set(indexes["new"])):
        old, new = indexes["old"][doi], indexes["new"][doi]
        pairs, available = [], list(new)
        for block in old:
            match = next((b for b in available if b["text"] == block["text"]), None)
            if match:
                pairs.append([block["id"], match["id"]])
                available.remove(match)
        label_pairs, exact_old = [], {pair[0] for pair in pairs}
        for block in old:
            key = citation_keys.get(block["id"])
            match = next((b for b in available if key is not None and citation_keys.get(b["id"]) == key), None)
            if block["id"] not in exact_old and match:
                label_pairs.append([block["id"], match["id"]])
                available.remove(match)
        report["studies"].append(dict(doi=doi, status="retained" if old and new else "removed" if old else "added",
                                      old=[b["id"] for b in old], new=[b["id"] for b in new], exact_text_pairs=pairs,
                                      citation_label_only_pairs=label_pairs))
    report["summary"] = dict(studies=dict(Counter(s["status"] for s in report["studies"])),
                             cited_blocks={side: sum(bool(b["dois"]) for b in blocks) for side, blocks in report["blocks"].items()},
                             unresolved=len(report["unresolved"]), parse_issues=len(report["parse_issues"]))
    for name in ["exact_text_pairs", "citation_label_only_pairs"]:
        report["summary"][name] = len({tuple(pair) for study in report["studies"] for pair in study[name]})
    return report


def xml_tag(node):
    return node.tag.rsplit("}", 1)[-1]


def xml_child(node, name):
    return next((c for c in node if xml_tag(c) == name), None) if node is not None else None


def xml_text(node):
    return "".join(node.itertext()).strip() if node is not None else ""


def xml_paths(node, path=None):
    path = path or f"/{xml_tag(node)}[1]"
    yield node, path
    counts = Counter()
    for child in node:
        name = xml_tag(child)
        counts[name] += 1
        yield from xml_paths(child, f"{path}/{name}[{counts[name]}]")


def index_source_xml(path, doi):
    """Index structure, never infer which population or outcome a passage supports."""
    record = dict(file=str(path), locations=[])
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError) as exc:
        return dict(record, status="xml_error", reason=str(exc))
    articles = []
    for node, element_path in xml_paths(root):
        if xml_tag(node) == "article":
            meta = xml_child(xml_child(node, "front"), "article-meta")
            identifiers = set().union(*(dois(xml_text(c)) for c in (meta if meta is not None else [])
                                        if xml_tag(c) == "article-id" and c.get("pub-id-type") == "doi"))
            articles.append((node, element_path, meta, identifiers))
    matching = [a for a in articles if doi in a[3]]
    record["document_dois"] = sorted(set().union(*(a[3] for a in articles)))
    if len(matching) == 1:
        selected, identity = matching[0], "matched"
    elif len(articles) == 1 and not articles[0][3]:
        selected, identity = articles[0], "not_present"
    else:
        status = "ambiguous_article" if len(matching) > 1 else "doi_mismatch" if record["document_dois"] else "unsupported_xml"
        return dict(record, status=status)
    article, article_path, meta, _ = selected
    record.update(status="indexed" if identity == "matched" else "indexed_doi_unconfirmed",
                  doi_identity=identity, article_title=xml_text(xml_child(meta, "title-group")))

    def visit(node, element_path, headings=(), region=None):
        name = xml_tag(node)
        if name in ["abstract", "trans-abstract", "body", "back"]:
            region = "abstract" if name.endswith("abstract") else name
        title = xml_text(xml_child(node, "title"))
        current = headings + (title,) if name in ["sec", "abstract", "trans-abstract"] and title else headings
        if name in ["abstract", "trans-abstract"] or (name == "sec" and region in ["abstract", "body"]):
            location = dict(kind="abstract" if name.endswith("abstract") else "section",
                            element_path=element_path, xml_id=node.get("id"), region=region,
                            heading=title, heading_path=list(current))
            for attr in ["sec-type", "abstract-type"]:
                if node.get(attr):
                    location[attr] = node.get(attr)
            record["locations"].append(location)
        if name == "fig":
            caption = xml_child(node, "caption")
            if caption is not None:
                record["locations"].append(dict(kind="figure-caption", element_path=element_path + "/caption[1]",
                                                xml_id=caption.get("id"), figure_id=node.get("id"),
                                                figure_label=xml_text(xml_child(node, "label")),
                                                heading=xml_text(xml_child(caption, "title")), heading_path=list(headings), region=region))
        counts = Counter()
        for child in node:
            child_name = xml_tag(child)
            counts[child_name] += 1
            if child_name not in ["sub-article", "response"]:
                visit(child, f"{element_path}/{child_name}[{counts[child_name]}]", current, region)

    visit(article, article_path)
    return record


def build_source_index(study_dois, manifest_path):
    index = dict(manifest=str(manifest_path.resolve()),
                 scope="Structural source locations only; indexing and metadata DOI matching do not verify scientific claims. Inspect methods, results and captions at the indicated paths.",
                 articles={})
    try:
        entries = json.loads(manifest_path.read_text(encoding="utf-8"))["articles"]
        if not isinstance(entries, dict):
            raise ValueError("manifest articles must be an object keyed by DOI")
        entries = {key.lower(): value for key, value in entries.items()}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        entries = {}
        index["manifest_error"] = str(exc)
    for doi in sorted(set(study_dois)):
        entry = entries.get(doi)
        if "manifest_error" in index:
            record = dict(status="manifest_error")
        elif entry is None:
            record = dict(status="not_covered")
        elif not isinstance(entry, dict) or not isinstance(entry.get("file"), str):
            record = dict(status="invalid_manifest_entry")
        else:
            path = (manifest_path.parent / entry["file"]).resolve()
            if not path.is_file():
                record = dict(status="missing_file", file=str(path))
            elif path.suffix.lower() not in [".xml", ".nxml"]:
                record = dict(status="unsupported_format", file=str(path))
            else:
                record = index_source_xml(path, doi)
            if entry.get("original_cache"):
                record["original_cache"] = entry["original_cache"]
        index["articles"][doi] = record
    index["summary"] = dict(statuses=dict(Counter(a["status"] for a in index["articles"].values())),
                            locations=dict(Counter(loc["kind"] for a in index["articles"].values() for loc in a.get("locations", []))))
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    for name in ["old_main", "old_supp", "new_main", "new_supp"]:
        parser.add_argument(name, type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-manifest", type=Path)
    parser.add_argument("--source-index", type=Path)
    args = parser.parse_args()
    if args.source_index and not args.source_manifest:
        parser.error("--source-index requires --source-manifest")
    report = compare(args.old_main, args.old_supp, args.new_main, args.new_supp)
    if args.source_manifest:
        index = build_source_index([s["doi"] for s in report["studies"]], args.source_manifest)
        for study in report["studies"]:
            study["source_context"] = study["doi"]
        if args.source_index:
            if args.source_index.resolve() == args.output.resolve():
                parser.error("--source-index and --output must be different files")
            args.source_index.parent.mkdir(parents=True, exist_ok=True)
            args.source_index.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            report["source_context"] = dict(index_file=str(args.source_index.resolve()), summary=index["summary"], scope=index["scope"])
        else:
            report["source_context"] = index
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False))
    return int(bool(report["unresolved"] or report["parse_issues"]))


if __name__ == "__main__":
    raise SystemExit(main())
