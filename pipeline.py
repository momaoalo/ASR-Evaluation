"""Orchestration only. Provider, scoring, media and persistence code live elsewhere."""
import copy
import math
import re
import unicodedata
from pathlib import Path
from storage import (new_id, now, digest, write_json, read_json, valid_id,
                     save_result, save_raw_response, load_result)
from evaluation.normalizer import validate_profile, extract_spoken_text, normalize_text, NORMALIZER_VERSION
from evaluation.evaluator import evaluate_transcription
from evaluation.profiles import get_cleaning_profile, validate_score_view
from services.audio_processor import prepare_audio
from services.downloader import canonical_youtube_url, download_audio
from services.asr_common import ProviderError, build_model_result
from services.elevenlabs_asr import transcribe_elevenlabs, request_settings as eleven_settings
from services.humain_asr import transcribe_humain, request_settings as humain_settings


def build_case(item: dict, index: int, profile: dict) -> dict:
    if not isinstance(item, dict):
        raise ValueError('Each case must be a JSON object.')
    reference = item.get('ground_truth', '')
    if not isinstance(reference, str) or not reference.strip() or len(reference) > 50000:
        raise ValueError(f'Case {index+1}: provide a reference of 1–50,000 characters.')
    if not normalize_text(reference, profile)['text'].strip():
        raise ValueError(f'Case {index+1}: the reference is empty after normalization.')
    source = item.get('source', {})
    if not isinstance(source, dict) or source.get('type') not in ('sample', 'youtube', 'upload'):
        raise ValueError('Source must be sample, youtube or upload.')
    source = dict(source)
    if source['type'] == 'youtube':
        source['url'] = canonical_youtube_url(source.get('url', ''))
    if source['type'] == 'upload':
        valid_id(source.get('upload_id', ''))
    crop = item.get('crop', {})
    if not isinstance(crop, dict):
        raise ValueError('Crop must be a JSON object with start and end.')
    start = float(crop.get('start', 0))
    end = crop.get('end')
    end = None if end in (None, '') else float(end)
    if not math.isfinite(start) or start < 0 or (end is not None and (not math.isfinite(end) or end <= start)):
        raise ValueError('Invalid crop interval.')
    return {'case_id': valid_id(item.get('case_id') or f'case_{index+1:03d}'),
            'title': str(item.get('title') or f'Audio {index+1}')[:160],
            'source': source, 'crop': {'start': start, 'end': end}, 'profile': profile,
            'ground_truth': reference, 'reference_hash': digest(reference)}


def validate_request(payload: dict, settings) -> dict:
    if not isinstance(payload, dict):
        raise ValueError('Submit a JSON object or an uploaded manifest.')
    cases = payload.get('cases', [])
    if not isinstance(cases, list) or not 1 <= len(cases) <= settings.max_cases:
        raise ValueError(f'Submit 1–{settings.max_cases} cases.')
    models = payload.get('models', ['humain', 'elevenlabs'])
    if not isinstance(models, list) or not models or len(set(models)) != len(models) or any(m not in ('humain', 'elevenlabs') for m in models):
        raise ValueError('Choose HUMAIN and/or ElevenLabs; no duplicate providers.')
    if payload.get('consent') is not True:
        raise ValueError('Confirm that audio may be sent to the selected providers and use credits.')
    p = validate_profile(payload['profile']) if payload.get('profile') is not None else get_cleaning_profile()
    score_view = validate_score_view(payload.get('score_view', 'normalized'))
    clean = [build_case(c, i, p) for i, c in enumerate(cases)]
    if len(set(c['case_id'] for c in clean)) != len(clean):
        raise ValueError('Case IDs must be unique inside a run.')
    return {'cases': clean, 'profile': p, 'models': models, 'score_view': score_view,
            'name': str(payload.get('name') or 'New evaluation')[:120],
            'reuse_cache': payload.get('reuse_cache', True) is True, 'mode': 'live'}


def save_uploaded_audio(file, settings) -> dict:
    suffix = Path(file.filename or '').suffix.lower()
    if suffix not in ('.wav', '.mp3', '.m4a', '.mp4', '.ogg', '.flac', '.webm', '.aac'):
        raise ValueError('Unsupported file extension.')
    upload_id = new_id('upload')
    path = settings.data / 'audio' / (upload_id + suffix)
    path.parent.mkdir(parents=True, exist_ok=True)
    file.save(path)
    if path.stat().st_size > settings.max_upload_mb * 1024**2:
        path.unlink(); raise ValueError('File exceeds the upload size limit.')
    if not path.stat().st_size:
        path.unlink(); raise ValueError('The uploaded file is empty.')
    metadata = {'upload_id': upload_id, 'filename': path.name,
                'display_name': Path(file.filename).name, 'bytes': path.stat().st_size}
    write_json(settings.data / 'audio' / (upload_id + '.json'), metadata)
    return {k: v for k, v in metadata.items() if k != 'filename'}


def resolve_uploaded_audio(source: dict, settings) -> tuple[Path, dict]:
    key = valid_id(source['upload_id'])
    meta = read_json(settings.data / 'audio' / (key + '.json'))
    path = settings.data / 'audio' / meta['filename']
    if path.resolve().parent != (settings.data / 'audio').resolve() or not path.is_file():
        raise ValueError('Uploaded audio artifact is unavailable.')
    return path, {'display_name': meta['display_name']}


def record_failure(stage, exc) -> dict:
    if isinstance(exc, (ValueError, ProviderError)):
        message = str(exc)
    else:
        message = f'{stage} failed ({type(exc).__name__}). Inspect input and configuration.'
    return {'stage': stage, 'code': getattr(exc, 'code', 'processing_error'), 'message': message}


def run_case(case: dict, job: dict, settings, progress) -> dict:
    """One shared clip; sequential independent provider calls; partial outcomes survive."""
    result = {'normalizer_version': NORMALIZER_VERSION, 'unicode_database': unicodedata.unidata_version, 'schema_version': 1, 'run_id': job['run_id'], 'case_id': case['case_id'],
              'title': case['title'], 'created_at': now(), 'source': case['source'],
              'reference': case['ground_truth'], 'reference_hash': case['reference_hash'],
              'profile': case['profile'], 'crop': case['crop'], 'requested_models': job['models'],
              'models': [], 'status': 'running', 'trace': []}
    def step(stage):
        result['trace'].append({'stage': stage, 'at': now()}); progress(stage)
    try:
        step('Acquiring audio')
        source = case['source']
        if source['type'] == 'sample':
            path = settings.root / 'examples' / 'doctor_clip.mp3'
            source_meta = read_json(settings.root / 'examples' / 'sample.json')['source']
        elif source['type'] == 'youtube':
            path, source_meta = download_audio(source['url'], settings)
        else:
            path, source_meta = resolve_uploaded_audio(source, settings)
        step('Preparing audio')
        audio, meta = prepare_audio(path, case['crop'], settings)
        result['audio'] = meta
        result['source_metadata'] = source_meta
    except Exception as exc:
        result.update(status='failed', error=record_failure('audio', exc))
        save_result(settings, result)
        return result
    credentials = settings.credentials()
    clients = {'humain': transcribe_humain, 'elevenlabs': transcribe_elevenlabs}
    for provider in job['models']:
        step('Transcribing · ' + provider)
        req = humain_settings(credentials, case['profile']['language']) if provider == 'humain' else eleven_settings(case['profile']['language'])
        cache_id = digest({'audio': meta['sha256'], 'provider': provider, 'settings': req, 'adapter': '1.0.0'})
        cache_path = settings.data / 'cache' / (cache_id + '.json')
        try:
            if job.get('reuse_cache') and cache_path.exists():
                cached = read_json(cache_path); m, raw = cached['model'], cached['raw']
                m['cache_hit'] = True; m['provenance'] = 'cached'
            else:
                m, raw = clients[provider](audio, credentials, case['profile']['language'], settings.api_timeout)
                write_json(cache_path, {'model': m, 'raw': raw})
            m['raw_response_path'] = save_raw_response(settings, job['run_id'], case['case_id'], provider, raw)
            step('Scoring · ' + provider)
            m['evaluation'] = evaluate_transcription(case['ground_truth'], m['speech_text'], case['profile'])
            result['models'].append(m)
        except Exception as exc:
            result['models'].append({'key': provider, 'label': 'HUMAIN' if provider == 'humain' else 'ElevenLabs · Scribe v2',
                                    'status': 'failed', 'provenance': 'live', 'request_settings': req,
                                    'error': record_failure(provider, exc)})
        # Checkpoint after each provider. Do not lose A because B or a later case fails.
        save_result(settings, result)
    successes = sum(m['status'] == 'success' for m in result['models'])
    result['status'] = 'complete' if successes == len(job['models']) else ('partial' if successes else 'failed')
    step('Saved')
    save_result(settings, result)
    return result


def score_imported_case(case: dict, models: list, run_id: str, settings, audio=None) -> dict:
    result = {'normalizer_version': NORMALIZER_VERSION, 'unicode_database': unicodedata.unidata_version, 'schema_version': 1, 'run_id': run_id, 'case_id': case['case_id'], 'title': case['title'],
              'created_at': now(), 'source': case['source'], 'reference': case['ground_truth'],
              'reference_hash': case['reference_hash'], 'profile': case['profile'], 'crop': case['crop'],
              'audio': audio or {}, 'models': [], 'status': 'complete',
              'trace': [{'stage': 'Scored saved user-supplied transcripts; no ASR API call', 'at': now()}]}
    if case['source']['type'] == 'sample':
        result['source_metadata'] = read_json(settings.root / 'examples/sample.json')['source']
    for item in models:
        speech, extraction = extract_spoken_text(item['text'], item.get('format', 'plain'))
        m = build_model_result(valid_id(item['key']), item['label'], speech,
                raw_text=item['text'], settings={}, provenance='imported', metadata=extraction)
        m['evaluation'] = evaluate_transcription(case['ground_truth'], speech, case['profile'])
        result['models'].append(m)
    save_result(settings, result)
    return result


def run_batch(job: dict, settings, update, should_stop=lambda: False) -> list:
    """Sequential bounded batch. Cancellation finishes the current case safely."""
    outcomes = []
    for index, case in enumerate(job['cases']):
        if should_stop():
            break
        update(index, case['title'], 'Starting case')
        result = run_case(case, job, settings, lambda stage: update(index, case['title'], stage))
        outcomes.append(result)
        update(index + 1, case['title'], 'Case saved')
    return outcomes
