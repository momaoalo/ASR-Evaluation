"""Workspace aggregation. Saved scores are never recomputed or silently blended.

The table contains every attempt. Corpus statistics use the latest observation
per audio/reference/model/settings/policy, so retries and re-scores do not give
one clip extra weight. Incompatible settings and supplied/live results are
separate series. An overall winner requires identical successful case coverage.
"""
from collections import defaultdict
import copy
import math
from storage import digest, valid_id

LANGUAGES = {'ar': 'Arabic', 'en': 'English', 'mixed': 'Arabic + English'}
VIEW_VERSION = 'overview-audio-cases-1.2'


def compact_case(case):
    """Keep only summary data in the index, not full transcript alignments."""
    if not isinstance(case, dict) or not isinstance(case.get('models'), list):
        raise ValueError('Invalid case structure.')
    if not isinstance(case.get('audio', {}), dict) or not isinstance(case.get('profile', {}), dict):
        raise ValueError('Invalid case metadata.')
    if any(not isinstance(m, dict) or not isinstance(m.get('key'), str) for m in case['models']):
        raise ValueError('Invalid model record.')
    fields = ('run_id', 'case_id', 'title', 'created_at', 'source', 'crop', 'profile',
              'reference_hash', 'status', 'audio', 'error', 'rescored_from', 'requested_models',
              'normalizer_version', 'unicode_database')
    out = {k: copy.deepcopy(case[k]) for k in fields if k in case}
    if not out.get('reference_hash'):
        out['reference_hash'] = digest(case.get('reference', ''))
    out['models'] = []
    for model in case.get('models', []):
        m = {k: copy.deepcopy(model[k]) for k in ('key', 'label', 'status', 'provenance',
             'request_settings', 'cache_hit', 'elapsed_ms', 'received_at', 'error') if k in model}
        e = model.get('evaluation')
        if e:
            try:
                if not isinstance(e, dict) or not isinstance(e.get('metrics', {}), dict):
                    raise ValueError('Invalid metric structure.')
                m['evaluation'] = {k: copy.deepcopy(e[k]) for k in ('profile', 'profile_id',
                    'normalizer_version', 'metric_policy', 'policy_label') if k in e}
                m['evaluation']['metrics'] = {}
                for view in ('normalized', 'raw'):
                    if view not in e.get('metrics', {}):
                        continue
                    v = e['metrics'][view]
                    if not isinstance(v, dict):
                        raise ValueError('Invalid metric structure.')
                    m['evaluation']['metrics'][view] = {
                        'wer': v['wer'], 'cer': v['cer'], **{level: {
                            k: copy.deepcopy(v[level][k]) for k in ('counts', 'reference_length', 'prediction_length')
                        } for level in ('words', 'characters')}}
            except (KeyError, TypeError, ValueError):
                # Keep the case and its other models visible. Never fabricate scores.
                m.pop('evaluation', None)
                m.update(status='invalid_result', error={
                    'message': 'Saved metrics are incomplete. Original transcripts are retained; re-score this run.'})
        out['models'].append(m)
    from evaluation.report_metadata import attach_metadata
    return attach_metadata(case, out)


def validate_filters(values=None):
    f = {'run': 'all', 'language': 'all', 'origin': 'all', 'model': 'all', 'q': ''}
    if values:
        f.update({k: str(values[k]) for k in f if k in values})
    if f['run'] != 'all':
        valid_id(f['run'])
    if f['language'] not in ('all', *LANGUAGES) or f['origin'] not in ('all', 'live', 'supplied'):
        raise ValueError('Invalid overview filter.')
    if f['model'] != 'all':
        valid_id(f['model'])
    if len(f['q']) > 200:
        raise ValueError('Search is limited to 200 characters.')
    f['q'] = f['q'].strip()
    return f


def _case_identity(case):
    audio = case.get('audio') or {}
    # Never use case_001 alone: IDs are only unique *inside* one run.
    source = {'sha256': audio['sha256']} if audio.get('sha256') else {
        'source': case.get('source', {}), 'crop': case.get('crop', {}),
        'fallback': None if case.get('source') else [case.get('run_id'), case.get('case_id')]}
    return digest({'audio': source, 'reference': case.get('reference_hash')})[:24]


def _identity(case, model):
    e = model.get('evaluation') or next((m['evaluation'] for m in case.get('models', []) if m.get('evaluation')), {})
    profile = e.get('profile') or case.get('profile') or {}
    language = profile.get('language', 'mixed')
    provenance = model.get('provenance', 'live')
    origin = 'supplied' if provenance in ('imported', 'supplied') else 'live'
    req = model.get('request_settings') or {}
    # Only public model settings are used here; no credentials or raw responses.
    req = {k: v for k, v in req.items() if k in ('model_id', 'model', 'model_constant', 'language',
        'language_code', 'sdk', 'api_url', 'api_path', 'diarize', 'tag_audio_events',
        'timestamps_granularity', 'no_verbatim')}
    provider = model.get('key', 'unknown')
    label = model.get('label') or provider
    if origin == 'live' and req.get('model_id'):
        label = ('ElevenLabs' if provider == 'elevenlabs' else 'HUMAIN' if provider == 'humain' else provider) + ' · ' + str(req['model_id'])
    elif origin == 'live' and (req.get('model_constant') or req.get('model')):
        label = ('HUMAIN' if provider == 'humain' else provider) + ' · ' + str(req.get('model_constant') or req['model'])
    # Supplied transcript slots (imported_1) do not identify an actual ASR model.
    provider_id = ' '.join(label.split()).casefold() if origin == 'supplied' else provider
    policy = {'profile': profile, 'version': e.get('normalizer_version') or case.get('normalizer_version', 'unrecorded'),
              'unicode': e.get('metric_policy', {}).get('unicode_database') or case.get('unicode_database', 'unrecorded')}
    policy_id = digest(policy)[:10]
    identity = {'provider': provider_id, 'origin': origin, 'settings': req,
                'language': language, 'policy': policy_id}
    return {'key': 'model_' + digest(identity)[:20], 'label': label,
            'language': language, 'origin': origin, 'policy_id': policy_id,
            'settings_id': digest(req)[:8], 'provider': provider}


def _checked_metric(model, view):
    """Reject corrupt saved numbers instead of inventing a score."""
    v = model['evaluation']['metrics'][view]
    for level, rate in (('words', 'wer'), ('characters', 'cer')):
        m = v[level]; counts = m['counts']; n = m['reference_length']; h = m['prediction_length']
        if any(type(counts[k]) is not int or counts[k] < 0 for k in 'CSDI'):
            raise ValueError('Invalid counts')
        if type(n) is not int or type(h) is not int or n <= 0 or h < 0:
            raise ValueError('Invalid denominator')
        if counts['C'] + counts['S'] + counts['D'] != n or counts['C'] + counts['S'] + counts['I'] != h:
            raise ValueError('Invalid count identity')
        value = v[rate]
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise ValueError('Invalid rate')
        if not math.isclose(value, sum(counts[k] for k in 'SDI') / n, rel_tol=1e-10, abs_tol=1e-12):
            raise ValueError('Counts and rate disagree')
    return v


def build_overview(results, jobs=(), view='normalized', filters=None):
    """Pure summary builder shared by the live page and exported snapshot."""
    if view not in ('normalized', 'raw'):
        raise ValueError('Choose Cleaning or No cleaning.')
    f = validate_filters(filters)
    job_map = {j['run_id']: j for j in jobs}
    observations, media, options, case_info = [], [], {}, {}
    q = f['q'].casefold()
    for case in results:
        run = case['run_id']; cid = case['case_id']; uid = f'{run}/{cid}'
        job = job_map.get(run, {})
        lang = (case.get('profile') or job.get('profile') or {}).get('language', 'mixed')
        if f['run'] != 'all' and run != f['run'] or f['language'] != 'all' and lang != f['language']:
            continue
        title = str(case.get('title') or cid)
        matches = not q or q in (title + ' ' + cid + ' ' + run + ' ' + job.get('name', '')).casefold()
        identity = _case_identity(case)
        audio = case.get('audio') or {}
        duration = audio.get('duration') or 0
        if not isinstance(duration, (int, float)) or not math.isfinite(duration) or duration < 0:
            duration = 0
        common = {'run_id': run, 'run_name': job.get('name') or run, 'case_id': cid,
                  'case_uid': uid, 'clip_id': identity, 'title': title, 'language': lang,
                  'duration': duration, 'created_at': case.get('created_at') or job.get('created_at', ''),
                  '_order': (case.get('created_at') or job.get('created_at', ''),
                             case.get('_saved_ns', 0), run, cid)}
        if case.get('error') and matches and f['model'] == 'all':
            origin = 'supplied' if job.get('mode') == 'imported' else 'live'
            if f['origin'] in ('all', origin):
                media.append({**common, 'error': case['error'], 'origin': origin})
                case_info[uid] = common
        for m in case.get('models', []):
            group = _identity(case, m)
            if f['origin'] not in ('all', group['origin']):
                continue
            options[group['key']] = group
            if not matches or f['model'] not in ('all', group['key']):
                continue
            row = {**common, 'model': group['key'], 'provider_key': m['key'],
                   'label': group['label'], 'origin': group['origin'], 'policy_id': group['policy_id'],
                   'status': m.get('status', 'failed'), 'provenance': m.get('provenance', 'live'),
                   'cache_hit': bool(m.get('cache_hit')), 'elapsed_ms': m.get('elapsed_ms'),
                   'error': m.get('error'), 'wer': None, 'cer': None, 'counts': None,
                   'reference_words': 0, 'reference_characters': 0, 'char_counts': None}
            if row['status'] == 'success':
                try:
                    metric = _checked_metric(m, view)
                    row.update(wer=metric['wer'], cer=metric['cer'], counts=metric['words']['counts'],
                               char_counts=metric['characters']['counts'],
                               reference_words=metric['words']['reference_length'],
                               reference_characters=metric['characters']['reference_length'])
                except (KeyError, TypeError, ValueError, OverflowError):
                    row.update(status='invalid_result', error={'message': 'Saved metrics are missing or inconsistent. Re-score this run; no score was fabricated.'})
            observations.append(row)
            case_info[uid] = common
    # Newest observation, not newest *successful* one: failed retries stay visible.
    observations.sort(key=lambda r: r['_order'], reverse=True)
    latest, seen = [], set()
    for row in observations:
        key = (row['clip_id'], row['model'])
        row['included'] = key not in seen
        seen.add(key)
        if row['included']:
            latest.append(row)
    by_model = defaultdict(list)
    for row in latest:
        by_model[row['model']].append(row)
    # Distinguish same display labels with different settings/rules in legends.
    labels = defaultdict(list)
    for key in options:
        g = options[key]
        name = f"{g['label']} · {LANGUAGES.get(g['language'], g['language'])}"
        if g['origin'] == 'supplied':
            name += ' · supplied'
        labels[name].append(key)
    display = {}
    for name, keys in labels.items():
        for key in keys:
            display[key] = name if len(keys) == 1 else f"{name} · config {key[-6:]}"
    models, successful_sets = [], []
    for key, rows in sorted(by_model.items(), key=lambda kv: display[kv[0]].casefold()):
        good = [r for r in rows if r['status'] == 'success']
        counts = {k: sum(r['counts'][k] for r in good) for k in 'CSDI'}
        nc = {k: sum(r['char_counts'][k] for r in good) for k in 'CSDI'}
        n = sum(r['reference_words'] for r in good); ch = sum(r['reference_characters'] for r in good)
        group = options[key]
        models.append({**group, 'label': display[key], 'counts': counts,
            'wer': sum(counts[k] for k in 'SDI') / n if n else None,
            'cer': sum(nc[k] for k in 'SDI') / ch if ch else None,
            'reference_words': n, 'reference_characters': ch, 'successes': len(good),
            'attempted': len(rows), 'failures': sum(r['status'] not in ('success', 'pending', 'running') for r in rows),
            'saved_attempts': sum(r['model'] == key for r in observations), 'matched': 0})
        successful_sets.append({r['clip_id'] for r in good})
    shared = set.intersection(*successful_sets) if successful_sets else set()
    comparable = (len(models) >= 2 and bool(shared) and all(s == shared for s in successful_sets)
                  and len({m['policy_id'] for m in models}) == 1
                  and len({m['origin'] for m in models}) == 1)
    # Do not declare a winner while selected provider calls are still pending.
    scope_runs = {c['run_id'] for c in case_info.values()}
    active = [j for j in jobs if j.get('status') in ('queued', 'running')
              and (f['run'] == 'all' or j['run_id'] == f['run'])]
    if active:
        comparable = False
    for m in models:
        m['matched'] = len(shared)
    best_rate = min(m['wer'] for m in models) if comparable else None
    best = ', '.join(m['label'] for m in models if math.isclose(m['wer'], best_rate, abs_tol=1e-12)) if comparable else None
    unique = {}
    for c in case_info.values():
        unique[c['clip_id']] = c['duration']
    for row in observations:
        row['series_label'] = display[row['model']]
        row.pop('_order', None)
    for row in media:
        row.pop('_order', None)
    # Stable clip order; absent models are gaps, never zero-score points.
    latest.sort(key=lambda r: (r['created_at'], r['run_id'], r['case_id'], r['model']))
    summary = {
        'version': VIEW_VERSION, 'view': view, 'filters': f,
        'run_count': len(scope_runs), 'case_count': len(unique), 'case_evaluations': len(case_info),
        'duration': sum(unique.values()), 'models': models, 'rows': observations,
        'chart_rows': latest, 'case_failures': media, 'media_failures': len(media),
        'successful_transcripts': sum(r['status'] == 'success' for r in observations),
        'failures': sum(r['status'] not in ('success', 'pending', 'running') for r in observations),
        'included_transcripts': sum(r['status'] == 'success' for r in latest),
        'earlier_attempts': len(observations) - len(latest), 'matched_cases': len(shared),
        'best': best, 'best_wer': best_rate, 'comparable': comparable,
        'comparison_blocked': not comparable, 'policy_count': len({m['policy_id'] for m in models}),
        'comparison_note': 'Corpus scores use the latest observation per clip, reference, model/settings and saved scoring policy. Every attempt remains in the table. A winner is shown only for identical successful case coverage and compatible policies.',
        'model_options': [{'key': key, 'label': display.get(key) or
                          f"{v['label']} · {LANGUAGES.get(v['language'], v['language'])}" +
                          (' · supplied' if v['origin'] == 'supplied' else '')}
                         for key, v in sorted(options.items(), key=lambda kv: kv[1]['label'])],
        'active_jobs': active,
    }

    summary['audio_cases'] = build_case_list(results, jobs, summary)
    summary['listed_case_count'] = len(summary['audio_cases'])
    return summary


def build_case_list(results, jobs, summary):
    """One list item per saved run/case; never deduplicate this browsing list.

    Model rows remain separate for corpus arithmetic. Browsing a case does not
    depend on successful scoring, and no global run selection is required.
    """
    f = summary['filters']
    job_map = {j['run_id']: j for j in jobs}
    by_case = defaultdict(list)
    for row in summary['rows']:
        by_case[(row['run_id'], row['case_id'])].append(row)
    listed = []
    for case in results:
        run, cid = case['run_id'], case['case_id']
        job = job_map.get(run, {})
        title = str(case.get('title') or cid)
        lang = (case.get('profile') or job.get('profile') or {}).get('language', 'mixed')
        if f['run'] not in ('all', run) or f['language'] not in ('all', lang):
            continue
        haystack = ' '.join([title, cid, run, str(job.get('name') or '')]).casefold()
        if f['q'] and f['q'].casefold() not in haystack:
            continue
        rows = by_case.get((run, cid), [])
        origin = 'supplied' if job.get('mode') == 'imported' else 'live'
        if not rows and (f['model'] != 'all' or f['origin'] not in ('all', origin)):
            continue
        if not rows and case.get('models') and f['origin'] != 'all':
            continue  # A real source/model filter excluded the model rows.
        # Retain provider order from the stored record (not a ranking).
        order = {m['key']: i for i, m in enumerate(case.get('models', []))}
        rows = sorted(rows, key=lambda r: order.get(r['provider_key'], 999))
        statuses = [r['status'] for r in rows]
        status = case.get('status') or job.get('status', 'pending')
        if statuses:
            if all(x == 'success' for x in statuses): status = 'complete'
            elif any(x in ('pending', 'running', 'queued') for x in statuses): status = 'running'
            elif 'success' in statuses: status = 'partial'
            else: status = 'failed'
        if case.get('error'): status = 'failed'
        seconds = (case.get('audio') or {}).get('duration')
        if not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
            seconds = None
        listed.append({
            'run_id': run, 'case_id': cid, 'case_uid': run + '/' + cid,
            'run_name': str(job.get('name') or run), 'title': title,
            'created_at': case.get('created_at') or job.get('created_at', ''),
            'duration': seconds, 'language': lang, 'status': status,
            'error': case.get('error'), 'models': rows,
            'scored_models': statuses.count('success'), 'model_count': len(rows),
        })
    # Retain known input cases even before the worker writes its first result.
    present = {(c['run_id'], c['case_id']) for c in results}
    if f['model'] == 'all':
        for job in jobs:
            run = job['run_id']
            lang = (job.get('profile') or {}).get('language', 'mixed')
            origin = 'supplied' if job.get('mode') == 'imported' else 'live'
            if f['run'] not in ('all', run) or f['language'] not in ('all', lang) or f['origin'] not in ('all', origin):
                continue
            for header in job.get('case_headers', []):
                cid = header['case_id']
                if (run, cid) in present:
                    continue
                title = str(header.get('title') or cid)
                if f['q'] and f['q'].casefold() not in (title+' '+cid+' '+run+' '+str(job.get('name') or '')).casefold():
                    continue
                status = job.get('status', 'pending')
                listed.append({'run_id': run, 'case_id': cid, 'case_uid': run+'/'+cid,
                    'run_name': str(job.get('name') or run), 'title': title, 'language': lang,
                    'created_at': job.get('created_at',''), 'duration': None, 'status': status,
                    'models': [], 'model_count': 0, 'scored_models': 0, 'has_result': False,
                    'error': {'message': ('Waiting for the first saved result.' if status in ('queued','running')
                              else 'Run input exists, but no case result was saved. Open the run for its status.')}})
    # Same-title repeats are distinct through (run_id, case_id).
    return sorted(listed, key=lambda c: (c['created_at'], c['run_id'], c['case_id']), reverse=True)
