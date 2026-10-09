"""Local readiness check. Never sends audio, API keys or network requests."""
import importlib.metadata as metadata
import importlib.util
import shutil
import sys
from pathlib import Path

if __name__ == '__main__':
    print('Python:', sys.version.split()[0])
    print('Executable:', sys.executable)
    for dist, module in [('Flask','flask'), ('requests','requests'), ('python-dotenv','dotenv'),
                         ('jiwer','jiwer'), ('rapidfuzz','rapidfuzz'),
                         ('waitress','waitress'), ('humain-voice','humain_voice')]:
        ready = importlib.util.find_spec(module) is not None
        print(f'{dist:16} {metadata.version(dist) if ready else "MISSING"}')
    for name in ('ffmpeg', 'ffprobe', 'yt-dlp', 'deno'):
        print(f'{name:16} {"ready" if shutil.which(name) else "MISSING / not on PATH"}')
    sample = Path(__file__).resolve().parent / 'examples/doctor_clip.mp3'
    print('Bundled audio:  ', 'present' if sample.is_file() else 'MISSING')
    print('Credentials: use Connections in the dashboard. This check does not authenticate.')
