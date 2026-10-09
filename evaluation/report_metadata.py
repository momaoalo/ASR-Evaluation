"""Small, non-destructive reporting metadata. Never correct a reference by guessing."""
import math
import re
from urllib.parse import urlparse, parse_qs
from storage import digest


def text_id(text):
    # Whitespace only: do not merge spelling/meaning differences for raw scoring.
    return digest(' '.join(str(text or '').split()))[:24]


def video_id(source, metadata):
    value = metadata.get('video_id')
    if value:
        return str(value)
    url = source.get('url') or metadata.get('url') or ''
    parsed = urlparse(url)
    if parsed.hostname in ('youtu.be', 'www.youtu.be'):
        return parsed.path.strip('/').split('/')[0]
    if parsed.hostname in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
        return (parse_qs(parsed.query).get('v') or [''])[0]
    return ''


def audio_identity(case):
    """Count evidenced inputs, not semantic/acoustic uniqueness.

    Known source+interval ties an original to its prepared representation. Hashes
    tie repeated uploads. Different encodings with no lineage are NOT guessed equal.
    Reference text never participates in this audio identity.
    """
    audio = case.get('audio') or {}
    seconds = audio.get('duration')
    if not isinstance(seconds, (int, float)) or isinstance(seconds, bool) or not math.isfinite(seconds) or seconds <= 0:
        return None
    if not audio.get('sha256'):
        return None
    source = case.get('source') or {}
    metadata = case.get('source_metadata') or {}
    crop = case.get('crop')
    processing = audio.get('processing') or {}
    # Whole-source evaluations use their recorded source identity. Legacy records
    # lacking crop infer a full interval only from source-duration evidence.
    start = (crop or {}).get('start', processing.get('start', 0))
    end = (crop or {}).get('end')
    source_seconds = (audio.get('source_metadata') or {}).get('duration', seconds)
    full = (float(start or 0) == 0 and (end is None or abs(float(end)-float(source_seconds)) < .001))
    if crop is None and processing:
        full = float(start or 0) == 0 and abs(float(processing.get('end', seconds))-float(source_seconds)) < .001
    interval = 'full' if full else [float(start or 0), end if end is not None else processing.get('end')]
    vid = video_id(source, metadata)
    if source.get('type') == 'sample':
        token = {'sample': vid or 'bundled-doctor', 'interval': interval,
                 'original_interval': [metadata.get('clip_start', 0), metadata.get('clip_end')]}
        method = 'bundled source + interval'
    elif vid:
        token = {'youtube': vid, 'interval': interval}
        method = 'YouTube source + interval'
    else:
        token = {'sha256': audio['sha256']}
        method = 'exact prepared-file hash'
    return {'id': 'audio_' + digest(token)[:20], 'method': method, 'duration': float(seconds)}


def attach_metadata(original, compact):
    """Called once when a saved file changes, not on every dashboard redraw."""
    compact['source_metadata'] = original.get('source_metadata') or {}
    compact['reference_canonical_id'] = text_id(original.get('reference'))
    compact['reference_preview'] = str(original.get('reference') or '')[:180]
    try:
        compact['report_media'] = audio_identity(original)
    except (ValueError, TypeError, AttributeError, OverflowError):
        compact['report_media'] = None
    compact['quality_flags'] = []
    texts = []
    for src, dst in zip(original.get('models', []), compact.get('models', [])):
        for view in ('normalized', 'raw'):
            e = src.get('evaluation') if isinstance(src.get('evaluation'), dict) else {}
            metrics = e.get('metrics') if isinstance(e.get('metrics'), dict) else {}
            metric = metrics.get(view) if isinstance(metrics.get(view), dict) else {}
            if view in (dst.get('evaluation') or {}).get('metrics', {}):
                dst['evaluation']['metrics'][view]['scored_reference_id'] = text_id(metric.get('reference_text') or original.get('reference'))
        metric = metrics.get('normalized') if isinstance(metrics.get('normalized'), dict) else {}
        if dst.get('status') == 'success' and isinstance(metric.get('prediction_text'), str) and isinstance(metric.get('wer'), (int,float)):
            texts.append((src.get('key'), metric['prediction_text'], metric.get('wer', 0)))
    # A review hint, never an automatic exclusion or a declaration that ASR is right.
    for i, (ka, a, wa) in enumerate(texts):
        for kb, b, wb in texts[i+1:]:
            if ka != kb and min(wa, wb) >= .7:
                aa, bb = set(a.split()), set(b.split())
                overlap = len(aa & bb) / max(1, len(aa | bb))
                if overlap >= .9 and min(len(a.split()), len(b.split())) >= 8:
                    compact['quality_flags'].append({'code': 'reference_review',
                        'message': 'Two outputs agree closely but both differ strongly from the reference. Check that this transcript belongs to this exact audio. This is a heuristic, not proof.'})
                    break
        if compact['quality_flags']:
            break
    reference = str(original.get('reference') or '')
    if re.search(r'(?m)^\s*\d{1,2}:\d{2}(?::\d{2})?', reference):
        compact['quality_flags'].append({'code': 'reference_timestamps',
            'message': 'The reference appears to contain timestamps. Review the spoken-text reference; no text was removed automatically.'})
    compact['_report_metadata'] = 1
    return compact
