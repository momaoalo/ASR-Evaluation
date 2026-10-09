"""Media inspection and deterministic conversion. Never alter the source file."""
from pathlib import Path
import json
import math
import shutil
import subprocess
import wave
from storage import digest, file_hash


def run_media(command: list[str], timeout: int) -> str:
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                                errors='replace', timeout=timeout, shell=False)
    except FileNotFoundError:
        raise ValueError(f'{command[0]} is not installed or is not on PATH.') from None
    except subprocess.TimeoutExpired:
        raise ValueError('Audio processing timed out. Check the file and crop interval.') from None
    if result.returncode:
        raise ValueError('The media tool could not decode or prepare this file. Check that it contains valid audio.')
    return result.stdout


def probe_audio(path: Path) -> dict:
    if not path.is_file():
        raise ValueError('Audio file not found.')
    if shutil.which('ffprobe'):
        data = json.loads(run_media(['ffprobe', '-v', 'error', '-protocol_whitelist', 'file,pipe',
            '-select_streams', 'a:0', '-show_streams', '-show_format', '-of', 'json', str(path)], 30))
        streams = data.get('streams', [])
        if not streams:
            raise ValueError('No audio stream was found.')
        s = streams[0]
        duration = float(s.get('duration', data.get('format', {}).get('duration', 0)))
        meta = {'duration': duration, 'sample_rate': int(s.get('sample_rate', 0)),
                'channels': int(s.get('channels', 0)), 'codec': s.get('codec_name', 'unknown')}
    else:
        try:
            with wave.open(str(path), 'rb') as w:
                meta = {'duration': w.getnframes() / w.getframerate(), 'sample_rate': w.getframerate(),
                        'channels': w.getnchannels(), 'codec': f'pcm_{w.getsampwidth()*8}bit'}
        except (wave.Error, EOFError):
            raise ValueError('FFprobe is required for this audio format.') from None
    if not math.isfinite(meta['duration']) or meta['duration'] <= 0:
        raise ValueError('Audio duration could not be determined.')
    return {**meta, 'sha256': file_hash(path), 'bytes': path.stat().st_size}


def prepare_audio(path: Path, crop: dict, settings) -> tuple[Path, dict]:
    source = probe_audio(path)
    start, end = float(crop.get('start', 0)), crop.get('end')
    end = source['duration'] if end is None else float(end)
    if not (math.isfinite(start) and math.isfinite(end)) or start < 0 or end <= start or end > source['duration'] + 0.05:
        raise ValueError('Crop must be inside the file: 0 <= start < end <= duration.')
    if end - start > settings.max_audio_seconds:
        raise ValueError(f'Each prepared clip must be at most {settings.max_audio_seconds} seconds.')
    policy = {'version': 'pcm16-v1', 'start': start, 'end': end,
              'rate': settings.sample_rate, 'channels': 1, 'codec': 'pcm_s16le'}
    identity = digest({'hash': source['sha256'], 'policy': policy})
    target = settings.data / 'audio' / ('prepared_' + identity[:24] + '.wav')
    target.parent.mkdir(parents=True, exist_ok=True)
    if not target.exists():
        temp = target.with_suffix('.pending.wav')
        try:
            run_media(['ffmpeg', '-nostdin', '-v', 'error', '-y', '-protocol_whitelist', 'file,pipe',
                       '-i', str(path), '-ss', str(start), '-t', str(end - start), '-map', '0:a:0',
                       '-vn', '-map_metadata', '-1', '-ac', '1', '-ar', str(settings.sample_rate),
                       '-c:a', 'pcm_s16le', str(temp)], settings.media_timeout)
            temp.replace(target)
        finally:
            temp.unlink(missing_ok=True)
    meta = probe_audio(target)
    if abs(meta['duration'] - (end - start)) > 0.12:
        raise ValueError('Prepared duration does not match the requested crop.')
    return target, {**meta, 'source_metadata': source, 'processing': policy,
                    'artifact': target.name, 'preprocessing_note': 'PCM16 / mono / 16 kHz is the chosen shared test configuration, not a universal provider requirement.'}
