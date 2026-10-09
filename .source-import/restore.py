from __future__ import annotations

import base64
import hashlib
import shutil
import tarfile
from pathlib import Path

EXPECTED_SHA256 = "d3d9a2839a9da7ef508af428ff05bc6b72083d1f25092e4b3f6f1059e3d97900"
EXPECTED_PARTS = [f"part-{i:03d}.b64" for i in range(14)]

repo = Path.cwd().resolve()
source_dir = repo / ".source-import"

parts = sorted(source_dir.glob("part-*.b64"))
if [p.name for p in parts] != EXPECTED_PARTS:
    raise SystemExit(
        "Source package is incomplete. Expected: "
        + ", ".join(EXPECTED_PARTS)
        + " | Found: "
        + ", ".join(p.name for p in parts)
    )

encoded = "".join(p.read_text(encoding="utf-8").strip() for p in parts)
archive_bytes = base64.b64decode(encoded, validate=True)
actual_sha256 = hashlib.sha256(archive_bytes).hexdigest()

if actual_sha256 != EXPECTED_SHA256:
    raise SystemExit(
        f"SHA-256 mismatch. Expected {EXPECTED_SHA256}, got {actual_sha256}. "
        "Nothing was extracted."
    )

archive_path = source_dir / "verified-source.tar.xz"
archive_path.write_bytes(archive_bytes)

with tarfile.open(archive_path, mode="r:xz") as tar:
    members = tar.getmembers()
    for member in members:
        if member.issym() or member.islnk():
            raise SystemExit(f"Refusing archive link: {member.name}")
        target = (repo / member.name).resolve()
        if target != repo and repo not in target.parents:
            raise SystemExit(f"Unsafe archive path: {member.name}")
    tar.extractall(path=repo, members=members, filter="data")

workflow = repo / ".github" / "workflows" / "source-import.yml"
if workflow.exists():
    workflow.unlink()

shutil.rmtree(source_dir)

print(f"Verified source package SHA-256: {actual_sha256}")
print(f"Restored {len(members)} archive entries.")
