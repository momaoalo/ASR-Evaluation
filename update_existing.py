"""Install a synchronized release into an existing workspace, preserving user state.

Run from the EXTRACTED new release, outside the old project. Standard library only.
Never reads credentials, deletes saved runs, or executes code from the old folder.
"""
from pathlib import Path, PurePosixPath
from datetime import datetime
import hashlib
import json
import os
import shutil
import socket
import tempfile
import time

ROOT = Path(__file__).resolve().parent
BUILD = 'dashboard-1.6.2'
EDITABLE = {'config.py', 'config.local.json', '.env'}


def retry(action):
    """Close handles before retrying transient Windows sharing violations."""
    for attempt in range(6):
        try:
            return action()
        except OSError as exc:
            if (getattr(exc, 'winerror', None) not in (32, 33) and not isinstance(exc, PermissionError)) or attempt == 5:
                raise
            time.sleep(.1 * (attempt + 1))


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def safe_name(name):
    p = PurePosixPath(name)
    if p.is_absolute() or '..' in p.parts or '\\' in name or ':' in name or not p.parts:
        raise ValueError('Invalid release path.')
    if p.parts[0] in ('data', '.git', '.venv', 'venv') or p.name in ('.env', 'config.local.json'):
        raise ValueError('A release must not include personal state: ' + name)
    return name


def atomic_copy(source, target):
    """Copy beside the target and then replace; do not keep a temporary handle open."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.asr-update-', dir=target.parent)
    os.close(fd)
    temp = Path(temp)
    try:
        retry(lambda: shutil.copyfile(source, temp))
        retry(lambda: os.replace(temp, target))
    finally:
        # Cleanup is separate from the actual copy. An AV lock is not a lost run.
        try:
            if temp.exists(): retry(temp.unlink)
        except OSError:
            pass


def port_busy():
    with socket.socket() as sock:
        sock.settimeout(.5)
        return sock.connect_ex(('127.0.0.1', 5000)) == 0


def install(source, destination, check_port=True):
    source, target = Path(source).resolve(), Path(destination).resolve()
    if source == target or source.is_relative_to(target) or target.is_relative_to(source):
        raise ValueError('Extract the new release outside the existing project, for example in Downloads.')
    if not target.is_dir() or not (target/'app.py').is_file() or not (target/'config.py').is_file():
        raise ValueError('Choose the existing asr-evaluator folder containing app.py and config.py.')
    if check_port and port_busy():
        raise ValueError('Close the running ASR application on port 5000, then run this updater again.')
    manifest = json.loads((source/'package_manifest.json').read_text('utf-8'))
    if manifest.get('build') != BUILD or not manifest.get('files'):
        raise ValueError('Wrong or incomplete release. Extract the complete ZIP.')
    names = []
    for name, expected in manifest['files'].items():
        safe_name(name)
        src = source/name
        if not src.resolve().is_relative_to(source) or not src.is_file() or sha(src) != expected:
            raise ValueError('Release verification failed: ' + name)
        dest = target/name
        if not dest.resolve().is_relative_to(target) or dest.is_symlink():
            raise ValueError('Unsafe destination link: ' + name)
        if name not in EDITABLE:
            names.append(name)
    names.append('package_manifest.json')
    # Existing config.py is intentional user code, and is never replaced.
    planned = [name for name in names if not (target/name).is_file() or sha(target/name) != sha(source/name)]
    backup = Path(tempfile.mkdtemp(prefix='asr-code-backup-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-', dir=target.parent))
    records = []
    for name in planned:
        dest = target/name
        existed = dest.is_file()
        if dest.exists() and not existed:
            raise ValueError('Destination file is a directory: ' + name)
        if existed:
            old = backup/name
            old.parent.mkdir(parents=True, exist_ok=True)
            retry(lambda dest=dest, old=old: shutil.copy2(dest, old))
        records.append((name, existed))
    (backup/'update-plan.json').write_text(json.dumps({'build': BUILD, 'files': records}, indent=2), 'utf-8')
    applied = []
    try:
        for name, existed in records:
            atomic_copy(source/name, target/name)
            applied.append((name, existed))
            if sha(source/name) != sha(target/name):
                raise OSError('Installed file verification failed: ' + name)
        for name, expected in manifest['files'].items():
            if name not in EDITABLE and sha(target/name) != expected:
                raise OSError('Final verification failed: ' + name)
    except Exception as exc:
        rollback_errors = []
        for name, existed in reversed(applied):
            try:
                if existed: atomic_copy(backup/name, target/name)
                elif (target/name).exists(): retry((target/name).unlink)
            except OSError:
                rollback_errors.append(name)
        if rollback_errors:
            raise RuntimeError('Update interrupted; restore code from ' + str(backup) + '. Personal data was not touched. Files: ' + ', '.join(rollback_errors)) from exc
        raise RuntimeError('Update interrupted; previous code restored. Personal data was not touched. ' + str(exc)) from exc
    return {'copied': len(planned), 'unchanged': len(names)-len(planned), 'backup': str(backup), 'target': str(target)}


def main():
    print('ASR Evaluator - synchronized Dashboard 1.6.2 update')
    print('Preserves config.py, config.local.json, .env and every file under data/.')
    print('Run this from the newly extracted release OUTSIDE the old project.')
    folder = input('Existing project folder [C:\\asr-evaluator]: ').strip().strip('"') or r'C:\asr-evaluator'
    print('Verifying release, backing up code and updating...')
    result = install(ROOT, folder)
    print('\nUPDATE COMPLETE - UI 1.6.2')
    print('Updated files:', result['copied'], '| Already identical:', result['unchanged'])
    print('Code backup:', result['backup'])
    print('Keys, references and saved results were NOT replaced.')
    print('Next: START_WINDOWS.bat in', result['target'])


if __name__ == '__main__':
    try: main()
    except (Exception, KeyboardInterrupt) as exc:
        print('\nUPDATE STOPPED:', exc)
        raise SystemExit(1)
