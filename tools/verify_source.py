"""Compare the current public source with archived original-file SHA256 values.

This is a HISTORICAL inventory/diff, not verification that later GitHub commits
are byte-identical to the original ZIP. Use verify_package.py for the current build.
"""
from pathlib import Path
import argparse
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]


def compare(strict: bool = False) -> int:
    manifest = json.loads((ROOT / "docs/portfolio/original-files.json").read_text("utf-8"))
    original_exclusions = set(manifest.get("packaging_changes", []))
    optional_media = set(manifest.get("optional_media", []))
    matched, changed, missing_media, missing_source = [], [], [], []
    for name, expected in manifest["files"].items():
        if name in original_exclusions:
            continue
        path = ROOT / name
        if not path.is_file():
            (missing_media if name in optional_media else missing_source).append(name)
        elif hashlib.sha256(path.read_bytes()).hexdigest() == expected:
            matched.append(name)
        else:
            changed.append(name)
    print("Archive comparison only (not today's build verification)")
    print(f"Original files unchanged: {len(matched)}")
    print(f"Modified since archive:  {len(changed)}")
    print(f"Media omitted publicly: {len(missing_media)}")
    print(f"Other original files missing: {len(missing_source)}")
    for item in changed[:20]:
        print("CHANGED: " + item)
    if len(changed) > 20:
        print(f"... and {len(changed) - 20} additional modified files")
    for item in missing_media:
        print("MEDIA OMITTED: " + item)
    for item in missing_source:
        print("MISSING: " + item)
    print("Run python verify_package.py to validate the CURRENT public checkout.")
    if strict and (changed or missing_media or missing_source):
        print("STRICT ARCHIVE MATCH: not met.")
        return 1
    if missing_source:
        print("WARNING: archived original files are absent. The archived inventory may be incomplete.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--strict", action="store_true", help="Fail when the Git checkout differs from the original ZIP")
    args = parser.parse_args()
    raise SystemExit(compare(strict=args.strict))
