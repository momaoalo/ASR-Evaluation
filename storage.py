"""UTF-8 JSON persistence with atomic replacement and server-owned identifiers."""
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
import hashlib
import json
import os
import re
import tempfile


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def new_id(prefix: str) -> str:
    return prefix + '_' + uuid4().hex[:20]


def valid_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r'[A-Za-z0-9_-]{1,90}', value):
        raise ValueError('Invalid identifier.')
    return value


def digest(value) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return hashlib.sha256(payload.encode('utf-8')).hexdigest()


def file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def write_json(path: Path, value) -> None:
    """The temp file must be on the same filesystem as its destination."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp = tempfile.mkstemp(prefix='.' + path.name, suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, allow_nan=False, indent=2)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp, path)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)


def save_result(settings, result: dict) -> None:
    path = settings.data / 'results' / valid_id(result['run_id']) / (valid_id(result['case_id']) + '.json')
    write_json(path, result)


def load_results(settings, run_id: str) -> list:
    directory = settings.data / 'results' / valid_id(run_id)
    return [read_json(p) for p in sorted(directory.glob('*.json'))]


def load_result(settings, run_id: str, case_id: str) -> dict:
    return read_json(settings.data / 'results' / valid_id(run_id) / (valid_id(case_id) + '.json'))


def save_raw_response(settings, run_id: str, case_id: str, model: str, response) -> str:
    path = settings.data / 'raw' / valid_id(run_id) / valid_id(case_id) / (valid_id(model) + '.json')
    write_json(path, response)
    return str(path.relative_to(settings.data)).replace('\\', '/')


class ResultIndex:
    """Cache compact summaries by file mtime/size; never cache full alignments.

    Atomic result writes invalidate the matching entry automatically. Missing or
    corrupt records are reported; they do not silently empty the whole dashboard.
    """
    def __init__(self, settings):
        import threading
        self.settings = settings
        self._cache = {}
        self._lock = threading.RLock()

    def load(self, run_id='all'):
        from evaluation.overview import compact_case
        root = self.settings.data / 'results'
        paths = sorted(root.glob('*/*.json')) if run_id == 'all' else sorted((root / valid_id(run_id)).glob('*.json'))
        records, warnings = [], []
        with self._lock:
            if run_id == 'all':
                existing = set(paths)
                self._cache = {p: item for p, item in self._cache.items() if p in existing}
            for path in paths:
                try:
                    st = path.stat(); stamp = (st.st_mtime_ns, st.st_size)
                    cached = self._cache.get(path)
                    if cached is None or cached[0] != stamp:
                        raw = read_json(path)
                        if not isinstance(raw, dict) or raw.get('run_id') != path.parent.name or raw.get('case_id') != path.stem:
                            raise ValueError('Record identity does not match its location.')
                        c = compact_case(raw)
                        c['_saved_ns'] = st.st_mtime_ns
                        self._cache[path] = (stamp, c)
                    record = self._cache[path][1]
                    records.append(record)
                    if any(m.get('status') == 'invalid_result' for m in record.get('models', [])):
                        warnings.append({'run_id': path.parent.name, 'case_id': path.stem,
                            'message': 'One model has incomplete saved metrics; its case and other model results remain visible.'})
                except (OSError, ValueError, TypeError, KeyError, AttributeError):
                    warnings.append({'run_id': path.parent.name, 'case_id': path.stem,
                                     'message': 'Saved record could not be read; excluded from statistics.'})
        return records, warnings
