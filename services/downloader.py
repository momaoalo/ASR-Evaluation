"""YouTube acquisition through the installed yt-dlp CLI, never a web converter."""
from pathlib import Path
from urllib.parse import urlparse, parse_qs
import importlib.util
import json
import re
import shutil
import subprocess
import sys
from storage import digest


def canonical_youtube_url(url: str) -> str:
    if not isinstance(url, str) or len(url) > 2048:
        raise ValueError('Provide a valid YouTube video URL.')
    u = urlparse(url)
    if u.scheme != 'https' or u.username or u.password or u.port not in (None, 443):
        raise ValueError('Only HTTPS YouTube video URLs are accepted.')
    if u.hostname == 'youtu.be':
        video = u.path.strip('/')
    elif u.hostname in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        if u.path == '/watch':
            video = parse_qs(u.query).get('v', [''])[0]
        elif re.fullmatch(r'/(shorts|embed)/[\w-]{11}', u.path):
            video = u.path.rsplit('/', 1)[-1]
        else:
            video = ''
    else:
        video = ''
    if not re.fullmatch(r'[A-Za-z0-9_-]{11}', video):
        raise ValueError('Use a single YouTube video URL, not a playlist or another host.')
    return 'https://www.youtube.com/watch?v=' + video


def yt_dlp_command() -> list[str] | None:
    """Prefer yt-dlp in the running venv, not an unrelated system executable."""
    if importlib.util.find_spec('yt_dlp') is not None:
        return [sys.executable, '-m', 'yt_dlp']
    tool = shutil.which('yt-dlp')
    return [tool] if tool else None


def yt_dlp_available() -> bool:
    return yt_dlp_command() is not None


def download_audio(url: str, settings) -> tuple[Path, dict]:
    url = canonical_youtube_url(url)
    directory = settings.data / 'audio' / ('youtube_' + digest(url)[:16])
    directory.mkdir(parents=True, exist_ok=True)
    cache = directory / 'source.json'
    if cache.exists():
        metadata = json.loads(cache.read_text('utf-8'))
        candidate = directory / metadata['filename']
        if candidate.is_file():
            return candidate, metadata
    tool = yt_dlp_command()
    if not tool:
        raise ValueError('yt-dlp is missing. Run SETUP_WINDOWS.bat or install yt-dlp[default] in the active Python environment. Alternatively, upload an audio file.')
    command = [*tool, '--ignore-config', '--no-playlist', '--no-progress', '--no-warnings',
               '--socket-timeout', '20', '--retries', '1', '--no-overwrites',
               '--max-filesize', str(settings.max_upload_mb) + 'M',
               '--match-filter', 'duration <= 7200', '-f', 'bestaudio/best',
               '-o', str(directory / 'source.%(ext)s'), '--print', 'after_move:%(filepath)s', url]
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=settings.media_timeout, shell=False)
    except subprocess.TimeoutExpired:
        raise ValueError('YouTube download timed out. Use a local audio file or retry explicitly.') from None
    if result.returncode:
        reason = result.stderr.lower()
        if 'sign in' in reason or 'bot' in reason or 'cookies' in reason:
            raise ValueError('YouTube requires browser authentication for this request. No bypass is attempted; upload a local audio file instead.')
        raise ValueError('YouTube acquisition failed. Check that the video is available. Deno 2.3+ is recommended for YouTube support; run diagnostics or upload a local audio file.')
    paths = [Path(s.strip()) for s in result.stdout.splitlines() if s.strip()]
    candidates = [p for p in paths if p.is_file() and p.resolve().parent == directory.resolve()]
    if not candidates:
        raise ValueError('yt-dlp did not return a valid audio artifact.')
    path = candidates[-1]
    if path.stat().st_size > settings.max_upload_mb * 1024**2:
        path.unlink(); raise ValueError('Downloaded file exceeds the size limit.')
    metadata = {'url': url, 'video_id': url.rsplit('=', 1)[-1], 'filename': path.name}
    from storage import write_json
    write_json(cache, metadata)
    return path, metadata
