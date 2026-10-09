"""Read-only audit of every tracked source/document file in the public Git clone.

Checks presence, UTF-8, Python syntax, JSON syntax, sensitive local paths, and
the integrity-protected UI. This is NOT a credential scan, provider API check,
full end-to-end test or legal/code security audit.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {'.py', '.md', '.txt', '.json', '.html', '.css', '.js', '.csv',
                 '.ps1', '.bat', '.yml', '.yaml', '.svg', '.example', '.gitignore',
                 '.gitattributes'}
BINARY_SUFFIXES = {'.jpg', '.jpeg', '.png', '.webp', '.gif', '.ico', '.mp3',
                   '.mp4', '.wav', '.ogg', '.zip', '.pdf', '.woff', '.woff2'}


def main() -> int:
    command = subprocess.run(['git', 'ls-files', '-z'], cwd=ROOT, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, check=False)
    if command.returncode:
        print('Could not list tracked Git files. Run this inside a Git checkout.', file=sys.stderr)
        return 2
    tracked = [Path(raw.decode('utf-8', 'strict')) for raw in command.stdout.split(b'\0') if raw]
    errors = []
    counts = {'tracked': len(tracked), 'text': 0, 'json': 0, 'python': 0, 'binary': 0}
    for rel in tracked:
        path = ROOT / rel
        name = rel.as_posix()
        if not path.is_file():
            errors.append(f'{name}: tracked file missing')
            continue
        if any(part in {'.env', '.venv', '.tools', '__pycache__', 'data'} for part in rel.parts):
            errors.append(f'{name}: private runtime path should not be tracked')
            continue
        if path.suffix.lower() in BINARY_SUFFIXES:
            counts['binary'] += 1
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and not name.startswith('.'):
            errors.append(f'{name}: file type has no audit policy')
            continue
        try:
            content = path.read_bytes().decode('utf-8-sig')
        except UnicodeDecodeError:
            errors.append(f'{name}: cannot decode as UTF-8')
            continue
        counts['text'] += 1
        if path.suffix == '.json':
            try:
                json.loads(content)
                counts['json'] += 1
            except json.JSONDecodeError as exc:
                errors.append(f'{name}: invalid JSON ({exc.msg} at line {exc.lineno})')
        elif path.suffix == '.py':
            try:
                ast.parse(content, filename=name)
                counts['python'] += 1
            except SyntaxError as exc:
                errors.append(f'{name}: Python syntax error at line {exc.lineno}: {exc.msg}')
    from ui_integrity import verify_ui_files
    for issue in verify_ui_files(ROOT):
        errors.append('UI integrity: ' + issue)
    print('Tracked file audit:', ', '.join(f'{k}={v}' for k, v in counts.items()))
    for error in errors:
        print('FAIL:', error)
    if errors:
        return 1
    print('PASS: tracked file presence, UTF-8, JSON, Python syntax, and UI file hashes.')
    print('Scope excludes live ASR, ownership/licensing, vulnerabilities and confidential-content review.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
