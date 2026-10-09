"""Verify preserved original files, explicitly reporting separate optional media."""
from pathlib import Path
import hashlib
import json
import sys

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    manifest = json.loads((ROOT / "docs/portfolio/original-files.json").read_text("utf-8"))
    packaging = set(manifest["packaging_changes"])
    media = set(manifest["optional_media"])
    matched, missing_media, failures = [], [], []
    for name, expected in manifest["files"].items():
        if name in packaging:
            continue
        path = ROOT / name
        if not path.is_file():
            (missing_media if name in media else failures).append(name)
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            failures.append(name + " (hash mismatch)")
        else:
            matched.append(name)
    print(f"Original files unchanged: {len(matched)}")
    print("Declared packaging changes: " + ", ".join(sorted(packaging)))
    if missing_media:
        print("Separately distributed media not present: " + ", ".join(missing_media))
        print("Imported-text scoring remains available; sample playback and full original tests require the media.")
    if failures:
        for item in failures:
            print("FAIL: " + item)
        return 1
    print("PASS: all required original files match their recovered source hashes.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
