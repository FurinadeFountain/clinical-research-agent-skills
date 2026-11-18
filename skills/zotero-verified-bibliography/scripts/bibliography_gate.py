#!/usr/bin/env python3
"""Read-only expected-field verification and numbered Zotero bibliography export."""
import argparse
import csv
import hashlib
import html
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import unicodedata
import urllib.parse
import urllib.request

CORE = {'itemType', 'title', 'creators', 'date'}
JOURNAL = {'publicationTitle', 'volume', 'issue', 'pages'}

def normalized(value, field=''):
    if value is None:
        return ''
    if isinstance(value, list):
        return [normalized(v, field) for v in value]
    if isinstance(value, dict):
        return {k: normalized(v, k) for k, v in value.items() if v not in (None, '')}
    if not isinstance(value, str):
        return value
    value = re.sub(r'\s+', ' ', unicodedata.normalize('NFC', html.unescape(value))).strip()
    if field == 'DOI':
        value = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', value, flags=re.I).lower()
    if field == 'pages':
        value = value.translate(str.maketrans({'–': '-', '—': '-', '−': '-'}))
    return value

def validate_manifest(manifest, exporting=False):
    errors = []
    library = manifest.get('library', {})
    if library.get('type') not in ('user', 'group') or not isinstance(library.get('id'), int) or library.get('id', 0) <= 0:
        errors.append({'error': 'library requires type user/group and actual positive numeric ID'})
    records = manifest.get('records', [])
    if not isinstance(records, list) or not records:
        return errors + [{'error': 'records must be a nonempty array'}]
    refs, keys, dois = [], [], []
    for row in records:
        ref, key = row.get('ref'), row.get('key')
        refs.append(ref); keys.append(key)
        if not isinstance(ref, str) or not ref or not isinstance(key, str) or not re.fullmatch('[A-Z0-9]{8}', key):
            errors.append({'ref': ref, 'error': 'nonempty ref and actual 8-character item key required'})
        expected = row.get('expected', {})
        required = CORE | (JOURNAL if expected.get('itemType') == 'journalArticle' else set())
        for field in sorted(required - expected.keys()):
            errors.append({'ref': ref, 'field': field, 'error': 'missing expectation'})
        covered = {f for e in row.get('evidence', []) if isinstance(e.get('source'), str) and e['source'].strip() for f in e.get('fields', [])}
        allowed = row.get('allowed_missing', {})
        for field, value in expected.items():
            if field not in covered:
                errors.append({'ref': ref, 'field': field, 'error': 'no source coverage recorded'})
            if value in (None, '', []):
                reason = allowed.get(field)
                if field in ('title', 'itemType') or not isinstance(reason, str) or not reason.strip():
                    errors.append({'ref': ref, 'field': field, 'error': 'empty expected value without applicable reason'})
        if not isinstance(expected.get('creators'), list):
            errors.append({'ref': ref, 'field': 'creators', 'error': 'ordered creator array required'})
        doi = normalized(expected.get('DOI', ''), 'DOI')
        if doi:
            dois.append(doi)
    for field, values in [('ref', refs), ('key', keys), ('DOI', dois)]:
        if len(set(values)) != len(values):
            errors.append({'field': field, 'error': 'duplicate identity; resolve before export/import verification'})
    if exporting:
        if manifest.get('numbering') != 'citation-order':
            errors.append({'error': 'this exporter only supports numbered first-citation-order bibliographies'})
        if not manifest.get('style') or not manifest.get('locale'):
            errors.append({'error': 'explicit style and locale required'})
        order = manifest.get('citation_order', [])
        if list(dict.fromkeys(order)) != refs:
            errors.append({'error': 'record order differs from unique first-citation order'})
        if not manifest.get('manuscript', {}).get('path') or not manifest.get('manuscript', {}).get('sha256'):
            errors.append({'error': 'manuscript snapshot path and SHA256 required'})
    return errors

def compare(manifest, actual):
    errors = []
    if not isinstance(actual, list):
        return [{'error': 'readback must be a JSON array'}]
    by_key = {}
    for item in actual:
        key = item.get('key')
        if key in by_key:
            errors.append({'key': key, 'error': 'duplicate key in readback'})
        by_key[key] = item
    expected_keys = {r['key'] for r in manifest['records']}
    for key in sorted(set(by_key) - expected_keys):
        errors.append({'key': key, 'error': 'unexpected item in selected readback'})
    for row in manifest['records']:
        key = row['key']; item = by_key.get(key)
        if item is None:
            errors.append({'ref': row['ref'], 'key': key, 'error': 'missing readback item'}); continue
        library = item.get('library', {})
        if any(library.get(f) != manifest['library'][f] for f in ('id', 'type')):
            errors.append({'key': key, 'error': 'library identity mismatch'})
        data = item.get('data', {})
        for field, expected in row['expected'].items():
            value = data.get(field)
            if normalized(value, field) != normalized(expected, field):
                errors.append({'ref': row['ref'], 'key': key, 'field': field, 'expected': expected, 'actual': value})
        for field, available in [('required_collections', set(data.get('collections', []))), ('required_tags', {t['tag'] for t in data.get('tags', [])})]:
            missing = set(row.get(field, [])) - available
            if missing:
                errors.append({'key': key, 'field': field, 'missing': sorted(missing)})
    return errors

class TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
    def handle_data(self, data):
        self.parts.append(data)
    def handle_starttag(self, tag, attrs):
        if tag == 'br':
            self.parts.append(' ')

def format_reference(bib):
    parser = TextParser(); parser.feed(bib)
    text = re.sub(r'\s+', ' ', ''.join(parser.parts)).strip()
    if not re.match(r'^(?:1[.)]|\[1\])\s*', text):
        raise ValueError('unrecognized single-entry numbering; inspect style output')
    return re.sub(r'^(?:1[.)]|\[1\])\s*', '', text, count=1)

def live_read(manifest, api_base, exporting):
    parsed = urllib.parse.urlparse(api_base)
    if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1', '::1') or parsed.username or parsed.query or parsed.fragment:
        raise ValueError('api-base must be a loopback HTTP URL without credentials/query/fragment')
    library = manifest['library']; route = 'users' if library['type'] == 'user' else 'groups'
    headers = {'Zotero-API-Version': '3'}
    if library.get('server_id'):
        headers['Zotero-Server-ID'] = library['server_id']
    keys = [r['key'] for r in manifest['records']]; actual = []
    for start in range(0, len(keys), 50):
        params = {'itemKey': ','.join(keys[start:start+50]), 'limit': 100, 'include': 'data,bib' if exporting else 'data'}
        if exporting:
            params.update(style=manifest['style'], locale=manifest['locale'])
        url = f"{api_base.rstrip('/')}/{route}/{library['id']}/items/top?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as response:
            actual.extend(json.load(response))
    return actual

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', type=Path); p.add_argument('--out', type=Path, required=True)
    p.add_argument('--actual', type=Path); p.add_argument('--check-only', action='store_true')
    p.add_argument('--api-base', default='http://localhost:23119/api')
    args = p.parse_args()
    if args.out.exists():
        p.error('output directory already exists; use a fresh run directory')
    args.out.mkdir(parents=True)
    manifest = {}; actual = []; errors = []; references = []
    try:
        manifest = json.loads(args.manifest.read_text())
        errors = validate_manifest(manifest, not args.check_only)
        if not errors and not args.check_only:
            snapshot = Path(manifest['manuscript']['path'])
            if not snapshot.is_absolute():
                snapshot = args.manifest.resolve().parent / snapshot
            if hashlib.sha256(snapshot.read_bytes()).hexdigest() != manifest['manuscript']['sha256']:
                errors.append({'error': 'manuscript snapshot hash mismatch'})
        if not errors:
            if args.actual:
                actual = json.loads(args.actual.read_text())
                if not args.check_only and manifest.get('formatted_with') != {'style': manifest['style'], 'locale': manifest['locale']}:
                    errors.append({'error': 'offline formatted-output style/locale provenance missing or different'})
            else:
                actual = live_read(manifest, args.api_base, not args.check_only)
            errors.extend(compare(manifest, actual))
        if not errors and not args.check_only:
            by_key = {x['key']: x for x in actual}
            for row in manifest['records']:
                references.append(format_reference(by_key[row['key']]['bib']))
    except Exception as exc:
        errors.append({'error': f'{type(exc).__name__}: {exc}'})
    report = {'passed': not errors, 'scope': 'expected fields versus stored records; not independent source or claim verification',
              'count': len(manifest.get('records', [])), 'errors': errors,
              'manifest_sha256': hashlib.sha256(args.manifest.read_bytes()).hexdigest() if args.manifest.is_file() else None,
              'style': manifest.get('style'), 'locale': manifest.get('locale')}
    (args.out / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    if actual:
        (args.out / 'readback.json').write_text(json.dumps(actual, ensure_ascii=False, indent=2)+'\n')
    if not errors and not args.check_only:
        (args.out / 'references.txt').write_text('\n\n'.join(f'[{i}] {s}' for i,s in enumerate(references, 1))+'\n')
        with (args.out / 'reference-map.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f); writer.writerow(['number', 'ref', 'library_type', 'library_id', 'item_key', 'DOI', 'reference'])
            for i,(row,ref) in enumerate(zip(manifest['records'], references),1):
                writer.writerow([i,row['ref'],manifest['library']['type'],manifest['library']['id'],row['key'],row['expected'].get('DOI',''),ref])
    print(json.dumps({'passed': not errors, 'count': report['count'], 'error_count': len(errors), 'report': str(args.out/'verification.json')}, ensure_ascii=False))
    return 2 if errors else 0

if __name__ == '__main__':
    sys.exit(main())
