"""Developer-only: regenerate UI hashes after intentional, tested edits."""
from pathlib import Path
import hashlib,json,sys
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from ui_integrity import UI_BUILD
files=['templates/index.html','templates/_workspace.html','static/js/app.js','static/js/charts.js','static/css/app.css']
(root/'ui_manifest.json').write_text(json.dumps({'build':UI_BUILD,'files':{n:hashlib.sha256((root/n).read_bytes()).hexdigest() for n in files}},indent=2),encoding='utf-8')
print('UI hashes updated. Run tests and verify the browser before distributing.')
