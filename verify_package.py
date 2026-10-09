"""Verify one extracted full build without network access or API requests."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent


def verify(root: Path = ROOT) -> list[str]:
    try:
        manifest = json.loads((root / 'package_manifest.json').read_text('utf-8'))
    except (OSError, ValueError):
        return ['package_manifest.json is missing or unreadable. Extract the whole ZIP.']
    issues = []
    for name, expected in manifest['files'].items():
        path = root / name
        if not path.is_file():
            issues.append(name + ' is missing')
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            issues.append(name + ' differs from this full release')
    for name in manifest.get('required_editable_files', []):
        if not (root / name).is_file():
            issues.append(name + ' is missing')
    return issues


if __name__ == '__main__':
    problems = verify()
    print('Project folder:', ROOT)
    if problems:
        print('FILES DO NOT MATCH. Do not apply old updates over this build.')
        print('\n'.join('- ' + x for x in problems))
        raise SystemExit(1)
    print('FULL 1.6.2 — ALL PACKAGE FILES MATCH')
    print('Local keys and data are intentionally excluded from hash checks.')
    print('This verifies installed files, not provider authorization.')
