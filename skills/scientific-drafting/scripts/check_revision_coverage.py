#!/usr/bin/env python3
"""Verify revision item coverage and quoted locations, without judging meaning."""
import argparse
import json
from collections import Counter
from pathlib import Path

def inspect(requirements, coverage, root):
    required = requirements['items']
    actual = coverage['items']
    errors = []
    for label, items in [('requirements', required), ('coverage', actual)]:
        duplicates = [key for key, n in Counter(i['id'] for i in items).items() if n > 1]
        if duplicates:
            errors.append({'issue': 'duplicate ids', 'document': label, 'ids': duplicates})
    expected = {i['id']: i for i in required}
    provided = {i['id']: i for i in actual}
    for key in sorted(set(expected) - set(provided)):
        errors.append({'id': key, 'issue': 'missing disposition'})
    for key in sorted(set(provided) - set(expected)):
        errors.append({'id': key, 'issue': 'unknown item'})
    locations = 0
    for key in expected.keys() & provided.keys():
        item = provided[key]
        status = item.get('disposition')
        if status == 'unresolved':
            errors.append({'id': key, 'issue': 'unresolved item'})
            continue
        if status in ['removed', 'not_applicable']:
            if not expected[key].get('allow_omission', False):
                errors.append({'id': key, 'issue': 'required content cannot be omitted'})
            if not item.get('reason') or not item.get('dependencies_handled'):
                errors.append({'id': key, 'issue': 'omission lacks reason or dependency disposition'})
            continue
        if status not in ['retained', 'revised', 'moved']:
            errors.append({'id': key, 'issue': 'invalid disposition'})
            continue
        targets = item.get('locations', [])
        if not targets:
            errors.append({'id': key, 'issue': 'no candidate location'})
        for loc in targets:
            path = (root / loc.get('file', '')).resolve()
            if not path.is_relative_to(root.resolve()):
                errors.append({'id': key, 'issue': 'location outside candidate root'})
                continue
            if not path.is_file():
                errors.append({'id': key, 'issue': 'missing candidate file', 'file': str(path)})
                continue
            quote = loc.get('quote', '')
            if not quote.strip() or quote not in path.read_text():
                errors.append({'id': key, 'issue': 'candidate quote not found', 'file': str(path)})
            else:
                locations += 1
    return {'items': len(required), 'located_quotes': locations, 'errors': errors,
            'scope': 'coverage and exact location existence only; assigned owner checks meaning and dependencies'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('requirements', type=Path)
    parser.add_argument('coverage', type=Path)
    parser.add_argument('--root', type=Path)
    args = parser.parse_args()
    result = inspect(json.loads(args.requirements.read_text()), json.loads(args.coverage.read_text()),
                     args.root or args.coverage.parent)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return bool(result['errors'])

if __name__ == '__main__':
    raise SystemExit(main())
