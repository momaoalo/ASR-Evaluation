"""Copy only local state from a backup. Never execute or import the old code.

Run IMPORT_OLD_DATA.bat after extracting the full application to a clean folder.
The source remains untouched. Existing different destination files stop the copy.
"""
from pathlib import Path
from contextlib import contextmanager
import ast
import hashlib
import errno
import json
import os
import shutil
import socket
import tempfile
import time

IMPORTER_VERSION = '1.5.2-import-fix.1'
RETRY_DELAYS = (0.2, 0.5, 1.0, 2.0, 3.0)
ROOT = Path(__file__).resolve().parent
SECRET_CONSTANTS = {'HUMAIN_API_KEY': 'humain_api_key',
                    'ELEVENLABS_API_KEY': 'elevenlabs_api_key'}


def _retry_file_operation(operation, label):
    """Retry transient sharing/lock errors only. Never alter file permissions."""
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            return operation()
        except OSError as exc:
            winerror = getattr(exc, 'winerror', None)
            retryable = (winerror in {32, 33} or
                         (winerror is None and
                          exc.errno in {errno.EACCES, errno.EPERM, errno.EBUSY}))
            if not retryable or attempt == len(RETRY_DELAYS):
                exc.import_operation = label
                raise
            time.sleep(RETRY_DELAYS[attempt])


def file_hash(path: Path) -> str:
    """Stream and explicitly close every file, including large audio files."""
    def calculate():
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                digest.update(block)
        return digest.hexdigest()
    return _retry_file_operation(calculate, 'Verifying ' + path.name)


def _read_text(path: Path) -> str:
    return _retry_file_operation(
        lambda: path.read_text('utf-8-sig'), 'Reading ' + path.name)


@contextmanager
def _staging_directory(parent: Path, warnings: list):
    """Cleanup is housekeeping, not proof of whether an import succeeded.

    A Windows sharing violation can prevent deletion AFTER the verified copy.
    Do not turn that into IMPORT STOPPED or hide an earlier real copy error.
    The backup is never moved or deleted.
    """
    stage = Path(tempfile.mkdtemp(prefix='.asr-import-', dir=parent))
    try:
        yield stage
    finally:
        try:
            if stage.exists():
                _retry_file_operation(
                    lambda: shutil.rmtree(stage), 'Removing temporary workspace')
        except OSError as exc:
            # Keep the remaining temporary files. Never touch source/destination
            # to "fix" a cleanup lock; the caller verifies those separately.
            warnings.append({
                'code': 'temporary_cleanup_deferred',
                'path': str(stage),
                'os_code': getattr(exc, 'winerror', None) or exc.errno,
                'message': 'Temporary files could not be removed. '
                           'The backup and verified destination files are unaffected.'
            })


def _copy_new_file(staged: Path, target: Path, created: list):
    """Never overwrite an existing file, even if it appeared after preflight."""
    # Retrying exclusive open is safe: an unsuccessful open creates no file.
    output = _retry_file_operation(
        lambda: target.open('xb'), 'Creating ' + target.name)
    created.append(target)
    with output:
        def transfer():
            # If a read/lock failure interrupted the copy, restart only OUR
            # newly created file through the still-owned handle.
            output.seek(0)
            output.truncate(0)
            with staged.open('rb') as incoming:
                shutil.copyfileobj(incoming, output, length=1024 * 1024)
            output.flush()
            os.fsync(output.fileno())
        _retry_file_operation(transfer, 'Copying ' + target.name)


def _linked(path: Path) -> bool:
    return path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction())


def _hardcoded_keys(source: Path) -> dict:
    """Read literal key assignments only; ast.parse does not run config.py."""
    path = source / 'config.py'
    if not path.is_file():
        return {}
    tree = ast.parse(_read_text(path))
    keys = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id in SECRET_CONSTANTS:
                value = node.value
                if isinstance(value, ast.Constant) and isinstance(value.value, str) and value.value.strip():
                    keys[SECRET_CONSTANTS[target.id]] = value.value.strip()
    return keys


def import_state(source: Path, destination: Path = ROOT, *, progress=None) -> dict:
    """Stage, verify, and copy data/.env/config.local.json; never copy old code."""
    warnings = []
    report_progress = progress or (lambda message: None)
    report_progress('[1/4] Checking backup and destination folders...')
    source = source.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if source == destination or source in destination.parents or destination in source.parents:
        raise ValueError('Choose a separate old project folder, not this folder or its parent.')
    if not (source / 'app.py').is_file():
        raise ValueError('The old folder must contain app.py directly, not another project subfolder.')
    if not (destination / 'app.py').is_file():
        raise ValueError('The destination is not a complete ASR application.')
    if _linked(source / 'config.py'):
        raise ValueError('Linked configuration files are not imported.')

    # Build a complete copy plan before changing the destination.
    source_files = []
    if (source / 'data').exists():
        if _linked(source / 'data') or not (source / 'data').is_dir():
            raise ValueError('The old data path must be a regular folder.')
        for path in (source / 'data').rglob('*'):
            if _linked(path):
                raise ValueError('Linked files/folders in data are not imported.')
            if path.is_file():
                source_files.append((path, path.relative_to(source)))
    for name in ('.env', 'config.local.json'):
        path = source / name
        if path.exists():
            if _linked(path) or not path.is_file():
                raise ValueError('Configuration must be a regular file: ' + name)
            source_files.append((path, Path(name)))
    if (source / 'config.local.json').is_file():
        saved = json.loads(_read_text(source / 'config.local.json'))
        if not isinstance(saved, dict):
            raise ValueError('Old config.local.json must contain a JSON object.')
    else:
        saved = {}
    hardcoded = _hardcoded_keys(source)

    report_progress('[2/4] Staging and verifying backup files...')
    with _staging_directory(destination.parent, warnings) as stage:
        expected = {}
        for path, relative in source_files:
            staged = stage / relative
            staged.parent.mkdir(parents=True, exist_ok=True)
            before = file_hash(path)
            _retry_file_operation(lambda: shutil.copy2(path, staged),
                                  'Staging ' + str(relative))
            if file_hash(staged) != before or file_hash(path) != before:
                raise RuntimeError('A source file changed during copying. Stop the old app and retry.')
            expected[relative] = before
        if hardcoded:
            saved.update(hardcoded)
            staged = stage / 'config.local.json'
            _retry_file_operation(
                lambda: staged.write_text(json.dumps(saved, ensure_ascii=False, indent=2), encoding='utf-8'),
                'Preparing local settings')
            expected[Path('config.local.json')] = file_hash(staged)

        report_progress('[3/4] Checking for existing or conflicting files...')
        # Do not overwrite existing results or credentials with different contents.
        to_copy = []
        unchanged = 0
        for relative, digest in expected.items():
            target = destination / relative
            if not target.resolve().is_relative_to(destination):
                raise ValueError('Destination contains an unsafe linked path.')
            for parent in (target, *target.parents):
                if parent == destination:
                    break
                if _linked(parent):
                    raise ValueError('Destination contains a linked path.')
            if target.exists():
                if not target.is_file() or file_hash(target) != digest:
                    raise ValueError('Destination already contains a different file: ' + str(relative) +
                                     '. Import into a clean extraction; nothing was overwritten.')
                unchanged += 1
            else:
                to_copy.append(relative)
        created = []
        report_progress('[4/4] Importing verified files...')
        try:
            for relative in to_copy:
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                _copy_new_file(stage / relative, target, created)
                if file_hash(target) != expected[relative]:
                    raise RuntimeError('Copy verification failed: ' + str(relative))
        except BaseException as exc:
            # Remove only files created by this attempt. Never remove an older
            # result or a pre-existing credential. Preserve the real failure.
            not_removed = []
            for path in reversed(created):
                try:
                    _retry_file_operation(lambda: path.unlink(missing_ok=True),
                                          'Rolling back ' + path.name)
                except OSError:
                    not_removed.append(str(path.relative_to(destination)))
            if not_removed:
                raise RuntimeError(
                    'Import did not complete. Some newly created files are still locked: ' +
                    ', '.join(not_removed) + '. The old backup is unchanged. '
                    'Do not delete it. Close the app/media players and retry after '
                    'reviewing these destination files.') from exc
            raise
    return {'copied_files': len(to_copy), 'unchanged_files': unchanged,
            'saved_run_files': len(list((destination / 'data/jobs').glob('*.json'))),
            'saved_case_files': len(list((destination / 'data/results').glob('*/*.json'))),
            'configuration_present': (destination / 'config.local.json').is_file()
                                     or (destination / '.env').is_file(),
            'hardcoded_keys_migrated': bool(hardcoded),
            'importer_version': IMPORTER_VERSION, 'warnings': warnings}


def main():
    print('ASR Evaluator - import previous results and local settings')
    print('Importer:', IMPORTER_VERSION)
    print('Old code, templates and scripts will NOT be copied. The source is never deleted.')
    try:
        with socket.create_connection(('127.0.0.1', 5000), timeout=0.5):
            raise RuntimeError('An application is using port 5000. Close it before importing.')
    except (ConnectionRefusedError, socket.timeout, OSError):
        pass
    default = ROOT.with_name('asr-evaluator-backup')
    text = input(f'Old project folder [{default}]: ').strip().strip('"')
    source = Path(text) if text else default
    print('Source:', source)
    print('Destination:', ROOT)
    result = import_state(source, progress=lambda message: print(message, flush=True))
    print('\nIMPORT COMPLETE — old source kept unchanged.')
    print('Files copied:', result['copied_files'])
    print('Already identical:', result['unchanged_files'])
    print('Saved runs:', result['saved_run_files'], '| Saved cases:', result['saved_case_files'])
    print('Local settings found:', 'yes' if result['configuration_present'] else 'no')
    for warning in result['warnings']:
        print('NOTE: Import completed, but temporary cleanup was deferred.')
        print('Temporary folder:', warning['path'])
        print('You may remove that temporary folder after closing programs or restarting Windows.')
        print('Do not delete your asr-evaluator-backup folder.')
    print('Next: START_WINDOWS.bat in this folder.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # No key values or configuration contents appear in console output.
        print('IMPORT STOPPED:', str(exc))
        if getattr(exc, 'import_operation', None):
            print('Operation:', exc.import_operation)
        if getattr(exc, 'winerror', None) in {32, 33}:
            print('A file is still in use. Close the old/new app and audio players,')
            print('then retry. Do not delete the old backup or disable security tools.')
        raise SystemExit(1)
