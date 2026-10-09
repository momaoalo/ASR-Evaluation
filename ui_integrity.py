"""Guard a versioned UI against partially copied updates; no provider requests."""
from html import escape
from pathlib import Path
import hashlib
import json

UI_BUILD = 'dashboard-1.6.2'


def verify_ui_files(root: Path) -> list[str]:
    """Return actionable file names instead of serving an incompatible dashboard."""
    try:
        manifest = json.loads((root / 'ui_manifest.json').read_text('utf-8'))
    except (OSError, ValueError):
        return ['ui_manifest.json is missing or unreadable']
    if manifest.get('build') != UI_BUILD:
        return ['ui_manifest.json belongs to another build']
    problems = []
    for name, expected in manifest.get('files', {}).items():
        # The manifest is local trusted build data, but do not read outside the project.
        path = (root / name).resolve()
        if not path.is_relative_to(root.resolve()):
            problems.append('Invalid manifest path'); continue
        try:
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
        except OSError:
            problems.append(name + ' is missing'); continue
        if actual != expected:
            problems.append(name + ' does not match UI 1.6.2')
    if not manifest.get('files'):
        problems.append('UI manifest is empty')
    return problems


def repair_page(problems: list[str], root: Path) -> str:
    """A plain page independent of the broken CSS/JS. Existing results are untouched."""
    items = ''.join('<li>' + escape(x) + '</li>' for x in problems)
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><title>ASR — Repair required</title>
<meta name="viewport" content="width=device-width,initial-scale=1"><body style="font:16px/1.7 Arial;margin:40px auto;padding:20px;max-width:760px;color:#24394a">
<h1>Some application files are from different updates.</h1>
<p>Your saved evaluations have not been deleted. The application stopped loading this page to avoid displaying incorrect or empty results.</p>
<ul>{items}</ul><p>Close the running application, extract ASR_Evaluator_Dashboard_1_6_2.zip outside this project, run UPDATE_EXISTING.bat, and restart.</p>
<p><b>Build:</b> {UI_BUILD}<br><b>Project:</b> {escape(str(root.resolve()))}</p>
<button onclick="location.reload()" hidden>Reload</button>
<p lang="ar" dir="rtl">ملفات الواجهة غير متطابقة. أغلق التطبيق واستخرج الحزمة خارج المشروع ثم شغّل UPDATE_EXISTING.bat وأعد التشغيل. لم تُحذف نتائجك.</p>
</body></html>'''
