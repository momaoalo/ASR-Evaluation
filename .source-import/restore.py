from __future__ import annotations

import base64
import hashlib
import io
import shutil
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STAGING = ROOT / ".source-import"
EXPECTED_SHA256 = "a9c8965d252c033c5363e76bc18593946657da460f9247f3ac277bf96f454f5f"

parts = sorted(STAGING.glob("part-*.txt"))
if not parts:
    raise SystemExit("No source package parts found.")

payload = "".join(p.read_text(encoding="utf-8").strip() for p in parts)
archive = base64.b64decode(payload)
actual = hashlib.sha256(archive).hexdigest()
if actual != EXPECTED_SHA256:
    raise SystemExit(f"Package checksum mismatch: {actual}")

with zipfile.ZipFile(io.BytesIO(archive)) as zf:
    bad = zf.testzip()
    if bad:
        raise SystemExit(f"Corrupt archive member: {bad}")
    for info in zf.infolist():
        target = (ROOT / info.filename).resolve()
        if ROOT not in target.parents and target != ROOT:
            raise SystemExit(f"Unsafe archive path: {info.filename}")
    zf.extractall(ROOT)

# Remove temporary importer files and workflow after successful restoration.
shutil.rmtree(STAGING)
workflow = ROOT / ".github" / "workflows" / "source-import.yml"
if workflow.exists():
    workflow.unlink()
