#!/usr/bin/env python3
"""Check local Markdown targets; list prose cross-references needing human review."""
import argparse
import json
import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

LINK = re.compile(r'!?\[[^\n]*?\]\(\s*(?:<([^>]+)>|([^\s)]+))(?:\s+"[^"]*")?\s*\)')
MENTION = re.compile(r'补(?:充)?图\s*S?\d+(?:\.\d+)?|补充(?:方法|表|推导)\s*S?\d+(?:\.\d+)?|supplementary\s+(?:fig(?:ure)?|table|method)s?\.?\s*S?\d+', re.I)

def prose(text):
    return re.sub(r'(?ms)^\s*```[^\n]*\n.*?^\s*```[^\n]*$', lambda m: '\n' * m[0].count('\n'), text)

def anchors(text):
    literal = Counter(re.findall(r'''\bid=["']([^"']+)["']''', text))
    found = set(literal)
    seen = Counter()
    for heading in re.findall(r'(?m)^#{1,6}\s+(.+?)\s*#*$', prose(text)):
        slug = re.sub(r'[^\w\- ]', '', heading.lower()).replace(' ', '-')
        found.add(slug if not seen[slug] else f'{slug}-{seen[slug]}')
        seen[slug] += 1
    return found, {key for key, count in literal.items() if count > 1}

def inspect(paths, cross_refs):
    errors, attention = [], []
    local, external = 0, 0
    for path in paths:
        text = prose(path.read_text())
        masked = list(text)
        for match in LINK.finditer(text):
            for i in range(match.start(), match.end()):
                if masked[i] != '\n':
                    masked[i] = ' '
            url = match[1] or match[2]
            parsed = urlsplit(url)
            if parsed.scheme or parsed.netloc:
                external += 1
                continue
            local += 1
            target = (path.parent / unquote(parsed.path)).resolve() if parsed.path else path.resolve()
            reason = None
            if not target.exists():
                reason = 'missing target'
            elif parsed.fragment and target.is_dir():
                reason = 'anchor on directory target cannot be resolved'
            elif parsed.fragment:
                ids, duplicate = anchors(target.read_text())
                fragment = unquote(parsed.fragment)
                if fragment not in ids:
                    reason = 'missing target anchor'
                elif fragment in duplicate:
                    reason = 'duplicate explicit anchor'
            if reason:
                errors.append({'file': str(path), 'line': text.count('\n', 0, match.start()) + 1, 'url': url, 'issue': reason})
        if path.resolve() in cross_refs:
            for line, value in enumerate(''.join(masked).splitlines(), 1):
                if re.match(r'^\s*#{1,6}\s', value):
                    continue
                for match in MENTION.finditer(value):
                    attention.append({'file': str(path), 'line': line, 'mention': match[0]})
    return {'local_links': local, 'external_links_not_verified': external, 'errors': errors,
            'unlinked_mentions_to_review': attention,
            'scope': 'local existence and anchors only; lead checks correspondence and unlinked mentions'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path)
    parser.add_argument('--cross-refs', nargs='*', type=Path, default=[])
    args = parser.parse_args()
    result = inspect(args.files, {p.resolve() for p in args.cross_refs})
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return bool(result['errors'])

if __name__ == '__main__':
    raise SystemExit(main())
