"""Validate a public Git checkout, or optionally an archived full-release ZIP.

The original package_manifest.json captures a different full-release snapshot.
It is NOT expected to match subsequent GitHub source edits or the omitted media.
"""
from pathlib import Path
import hashlib
import json
import sys

from ui_integrity import verify_ui_files

ROOT = Path(__file__).resolve().parent
REQUIRED = (
    "app.py", "run_local.py", "requirements.txt", "ui_manifest.json",
    "templates/index.html", "templates/_workspace.html",
    "static/js/app.js", "static/js/charts.js", "static/css/app.css",
)


def verify(root: Path = ROOT, *, full_release: bool = False) -> list[str]:
    """Check current runtime files by default, never old ZIP hashes on a Git checkout."""
    if not full_release:
        return verify_ui_files(root) + [name + " is missing" for name in REQUIRED
                                        if not (root / name).is_file()]
    try:
        manifest = json.loads((root / "package_manifest.json").read_text("utf-8"))
    except (OSError, ValueError):
        return ["package_manifest.json is missing or unreadable."]
    issues = []
    for name, expected in manifest.get("files", {}).items():
        path = root / name
        if not path.is_file():
            issues.append(name + " is missing")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            issues.append(name + " differs from the historical full release")
    for name in manifest.get("required_editable_files", []):
        if not (root / name).is_file():
            issues.append(name + " is missing")
    return issues


if __name__ == "__main__":
    full = "--full-release" in sys.argv[1:]
    problems = verify(full_release=full)
    print("Project:", ROOT)
    print("Mode:", "archived full-release ZIP" if full else "current Git source / UI integrity")
    if problems:
        print("Verification issues:")
        for issue in problems:
            print("-", issue)
        raise SystemExit(1)
    print("PASS: checked files are present and UI hashes match.")
    if not full:
        sample = ROOT / "examples/doctor_clip.mp3"
        if not sample.is_file():
            print("Note: original sample audio is omitted from the public repository.")
        print("This check does NOT verify provider credentials, FFmpeg, or live ASR requests.")
