"""HUMAIN official SDK adapter, isolated in a child process for a hard deadline.

Account-specific API URL/path is configured locally; it is NOT the marketing URL.
Docs: https://pypi.org/project/humain-voice/0.18.0/
"""
import dataclasses
import enum
import json
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from .asr_common import ProviderError, build_model_result

LANGUAGE_MODES = {
    'ar': ('Ar', 'BayanAr'),
    'en': ('En', 'FastEn'),
    'mixed': ('ArEn', 'BayanArEn'),
}


def validate_connection(c: dict) -> None:
    if not c.get('humain_api_key', '').strip():
        raise ProviderError('HUMAIN API key is not configured in the backend.', 'configuration')
    u = urlparse(c.get('humain_api_url', '').strip())
    if u.scheme != 'https' or not u.hostname or u.username or u.password or u.query or u.fragment:
        raise ProviderError('Enter the HUMAIN HTTPS API base URL supplied with your account (not the website/login page).', 'configuration')
    if u.hostname in ('localhost', '127.0.0.1', '::1'):
        raise ProviderError('A public HUMAIN API URL is required.', 'configuration')


def request_settings(c: dict, language: str = 'mixed') -> dict:
    language_name, model_name = LANGUAGE_MODES.get(language, LANGUAGE_MODES['mixed'])
    return {'sdk': 'humain-voice==0.18.0', 'model_constant': model_name,
            'language': language_name, 'api_url': c.get('humain_api_url', ''),
            'api_path': c.get('humain_api_path', '/socket.io')}


def transcribe_humain(audio: Path, credentials: dict, language: str, timeout=300) -> tuple[dict, dict]:
    validate_connection(credentials)
    language_name, model_name = LANGUAGE_MODES.get(language, LANGUAGE_MODES['mixed'])
    payload = {'path': str(audio.resolve()), 'language': language_name, 'model': model_name,
               'credentials': {k: v for k, v in credentials.items() if k.startswith('humain_')}}
    start = time.perf_counter()
    try:
        proc = subprocess.run([sys.executable, '-m', 'services.humain_asr', '--worker'],
              cwd=Path(__file__).resolve().parents[1], input=json.dumps(payload),
              capture_output=True, text=True, encoding='utf-8', errors='replace',
              timeout=timeout, shell=False)
    except subprocess.TimeoutExpired:
        raise ProviderError('HUMAIN timed out. The SDK process was stopped; check your account before retrying a possibly accepted request.', 'timeout') from None
    marked = [x[len('ASR_RESULT='):] for x in proc.stdout.splitlines() if x.startswith('ASR_RESULT=')]
    if not marked:
        raise ProviderError('HUMAIN SDK did not return a result. Install requirements and verify API URL/path.', 'sdk_error')
    output = json.loads(marked[-1])
    if 'error' in output:
        raise ProviderError(output['error'], output.get('code', 'sdk_error'))
    raw = output['raw']
    result = build_model_result('humain', 'HUMAIN · ' + model_name,
              output['text'], settings={**request_settings(credentials, language), 'resolved_model': output['resolved_model']},
              elapsed_ms=round((time.perf_counter() - start) * 1000),
              metadata={'response_kind': 'serialized_sdk_response', 'language_mode': language_name})
    return result, raw


def _plain(value):
    if isinstance(value, enum.Enum):
        return value.value
    if hasattr(value, 'model_dump'):
        return value.model_dump(mode='json')
    if dataclasses.is_dataclass(value):
        return _plain(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, '__dict__'):
        return {k: _plain(v) for k, v in vars(value).items() if not k.startswith('_')}
    return str(value)


def _worker():
    try:
        from humain_voice import stt
        payload = json.loads(sys.stdin.read())
        c = payload['credentials']
        model_enum = getattr(stt, 'FastTranscriptionModel', stt.ASRModel)
        model = getattr(model_enum, payload.get('model', 'BayanArEn'))
        language_value = getattr(stt.Language, payload.get('language', 'ArEn'))
        with stt.FastTranscriptionClient(api_url=c['humain_api_url'], api_key=c['humain_api_key'],
                                        api_path=c.get('humain_api_path', '/socket.io')) as client:
            with open(payload['path'], 'rb') as f:
                result = client.transcribe_sync(f, language_value, model)
        answer = {'text': result.transcription, 'raw': _plain(result), 'resolved_model': _plain(model)}
    except ImportError:
        answer = {'error': 'Install the official humain-voice SDK with requirements.txt.', 'code': 'dependency'}
    except Exception as exc:
        # Do not return arbitrary exception messages: SDK errors may include credentials.
        name = type(exc).__name__
        answer = {'error': f'HUMAIN SDK request failed ({name}). Verify API base URL, socket path, key permissions and credits.', 'code': 'sdk_error'}
    print('ASR_RESULT=' + json.dumps(answer, ensure_ascii=True))


if __name__ == '__main__':
    _worker()
