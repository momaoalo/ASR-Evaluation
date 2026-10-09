"""Ensure Markdown links inside the portfolio repository do not lead to missing files."""
import re
import unittest
from pathlib import Path
from urllib.parse import unquote, urlparse

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r'!?\[[^\]]*\]\(([^)]+)\)')
HEADING_RE = re.compile(r'^#{1,6}\s+(.+?)\s*#*\s*$', re.M)


def heading_anchor(text):
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'[^\w\s-]', '', text.lower(), flags=re.UNICODE)
    return re.sub(r'\s+', '-', text.strip())


class DocumentationLinks(unittest.TestCase):
    def test_local_markdown_links_and_fragments(self):
        failures = []
        for source in ROOT.rglob("*.md"):
            if any(part in {".git", ".venv", ".tools"} for part in source.parts):
                continue
            text = source.read_text(encoding="utf-8")
            for match in LINK_RE.finditer(text):
                raw = match.group(1).strip().split(' "')[0].strip('<>')
                parsed = urlparse(raw)
                if parsed.scheme or parsed.netloc or raw.startswith("//"):
                    continue
                if raw.startswith("mailto:"):
                    continue
                target = unquote(parsed.path)
                dest = (source.parent / target).resolve() if target else source
                if not dest.is_relative_to(ROOT):
                    failures.append(f"{source.relative_to(ROOT)}: link escapes repo: {raw}")
                    continue
                if not dest.exists():
                    failures.append(f"{source.relative_to(ROOT)}: missing: {raw}")
                    continue
                if parsed.fragment and dest.suffix.lower() == ".md":
                    found = {heading_anchor(s) for s in HEADING_RE.findall(dest.read_text(encoding="utf-8"))}
                    if unquote(parsed.fragment).lower() not in found:
                        failures.append(f"{source.relative_to(ROOT)}: missing heading anchor: {raw}")
        self.assertEqual(failures, [], "\n".join(failures))


if __name__ == "__main__":
    unittest.main()
