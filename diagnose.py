"""Local readiness check. Never sends audio, API keys or network requests."""
import importlib.metadata as metadata
import importlib.util
import shutil
from services.downloader import yt_dlp_available
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
    root = Path(__file__).resolve().parent
    for name in ('ffmpeg', 'ffprobe', 'deno'):
        folder = 'deno' if name == 'deno' else 'ffmpeg'
        portable = root / '.tools' / folder / (name + '.exe')
        ready = bool(shutil.which(name)) or portable.is_file()
        print(f'{name:16} {"ready" if ready else "MISSING / run INSTALL_MEDIA_WINDOWS.bat"}')
    print(f'{"yt-dlp":16} {"ready" if yt_dlp_available() else "MISSING (run setup)"}')
    sample = Path(__file__).resolve().parent / 'examples/doctor_clip.mp3'
    print('Bundled audio:  ', 'present' if sample.is_file() else 'MISSING')
    print('Credentials: use Connections in the dashboard. This check does not authenticate.')
