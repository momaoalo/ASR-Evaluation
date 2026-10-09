"""Local UI diagnostics: no keys, transcripts or provider requests are printed."""
from pathlib import Path
import json
import sys
import urllib.request
from ui_integrity import UI_BUILD, verify_ui_files
root=Path(__file__).resolve().parent
print('Expected UI:',UI_BUILD)
print('Project:',root)
print('Python:',sys.executable)
print('UI files:',verify_ui_files(root) or 'MATCH')
print('Saved job files:',len(list((root/'data/jobs').glob('*.json'))))
print('Saved case files:',len(list((root/'data/results').glob('*/*.json'))))
print('Sample audio:',(root/'examples/doctor_clip.mp3').is_file())
print('Sample reference:',(root/'examples/sample.json').is_file())
try:
    with urllib.request.urlopen('http://127.0.0.1:5000/api/build',timeout=2) as r:
        status=json.load(r)
    print('Running server:',status)
except Exception:
    print('Running server: unavailable or an older server is still running.')
