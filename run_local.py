"""One-click local launcher. Uses this exact Python, opens only the matching app."""
import json
from pathlib import Path
import threading
import time
import urllib.request
import webbrowser

from ui_integrity import UI_BUILD, verify_ui_files

URL = 'http://127.0.0.1:5000'
ROOT = Path(__file__).resolve().parent


def existing_server():
    try:
        with urllib.request.urlopen(URL + '/api/build', timeout=1) as response:
            return json.load(response)
    except Exception:
        return None


def main():
    problems = verify_ui_files(ROOT)
    if problems:
        raise RuntimeError('Incomplete application files:\n' + '\n'.join(problems))
    current = existing_server()
    if current:
        if current.get('ui_build') == UI_BUILD and current.get('files_consistent') and Path(current.get('project_directory', '')).resolve() == ROOT:
            webbrowser.open(URL)
            print('This application is already running. Keep its existing window open.'); return
        raise RuntimeError('A different ASR application is running on port 5000. Close it first.')
    try:
        from waitress import serve
    except ImportError as exc:
        raise RuntimeError('Python dependencies are missing. In PowerShell run: .\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt') from exc
    from app import create_app
    application = create_app()
    def open_when_ready():
        for _ in range(60):
            status = existing_server()
            if status and status.get('ui_build') == UI_BUILD and status.get('files_consistent'):
                webbrowser.open(URL); return
            time.sleep(0.25)
    threading.Thread(target=open_when_ready, daemon=True).start()
    print(f'ASR Evaluator — {UI_BUILD}\nProject: {ROOT}\nOpen: {URL}\nKeep this window open. Ctrl+C stops the app.',flush=True)
    serve(application, host='127.0.0.1', port=5000, threads=6)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Stopped.')
    except Exception as exc:
        print('Could not start:', exc)
        raise SystemExit(1)
