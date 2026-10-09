"""Auditable reporting scopes, paired comparisons and extraction. No ASR or rescoring.

History includes ALL attempts. Pair scores use latest observations on common
scored-reference cases. A missing setting/failed retry cannot invent a competitor.
"""
from collections import Counter, defaultdict
import copy
import itertools
import math
import statistics
from storage import digest
from evaluation.overview import build_overview as legacy_overview, compact_case, _checked_metric

REPORT_VERSION = 'dashboard-1.6.2'


def _policy(case, model, view):
    e = model.get('evaluation') or {}
    mp = e.get('metric_policy') or {}
    if view == 'raw':
        data = {'view': view, 'spaces': mp.get('cer_spaces', (case.get('profile') or {}).get('cer_spaces', True)),
                'unit': mp.get('character_unit', 'Unicode code points'), 'version': e.get('normalizer_version') or case.get('normalizer_version', 'unrecorded')}
    else:
        data = {'view': view, 'profile': {k: v for k,v in (e.get('profile') or case.get('profile') or {}).items() if k != 'language'},
                'version': e.get('normalizer_version') or case.get('normalizer_version', 'unrecorded'),
                'unicode': mp.get('unicode_database') or case.get('unicode_database', 'unrecorded')}
    return digest(data)[:12]


def _totals(rows):
    good = [r for r in rows if r['status'] == 'success']
    words = sum(r['reference_words'] for r in good)
    chars = sum(r['reference_characters'] for r in good)
    counts = {k: sum(r['counts'][k] for r in good) for k in 'CSDI'}
    cc = {k: sum(r['char_counts'][k] for r in good) for k in 'CSDI'}
    return {'counts': counts, 'char_counts': cc, 'reference_words': words, 'reference_characters': chars,
            'wer': sum(counts[k] for k in 'SDI')/words if words else None,
            'cer': sum(cc[k] for k in 'SDI')/chars if chars else None,
            'successes': len(good), 'attempted': len(rows),
            'failures': sum(r['status'] not in ('success','pending','running','queued') for r in rows),
            # Macro averages give each shared case equal weight. Corpus rates above
            # weight reference tokens. Keep both, never average the two providers.
            'mean_case_wer': statistics.fmean(r['wer'] for r in good) if good else None,
            'mean_case_cer': statistics.fmean(r['cer'] for r in good) if good else None,
            'mean_case_count': len(good),
            'median_case_wer': statistics.median([r['wer'] for r in good]) if good else None}


def _review(case, reviews):
    value = reviews.get(case['run_id']+'/'+case['case_id'], case.get('report_review') or {})
    # Do not carry an approval to edited data with a different reference.
    if value.get('reference_hash') and value['reference_hash'] != case.get('reference_hash'):
        return {}
    return value


def build_dashboard(results, jobs=(), view='normalized', filters=None, reviews=None, pair_keys=()):
    """Pure function, used by HTTP and standalone export with the same inputs."""
    reviews = reviews or {}
    cases = [c if c.get('_report_metadata') else compact_case(c) for c in results]
    summary = legacy_overview(cases, jobs, view, filters)
    by_uid = {c['run_id']+'/'+c['case_id']: c for c in cases}
    rows = summary['rows']
    configs = {m['key']: m for m in summary['models']}
    # Stable media numbers independent of spelling rules and reference versions.
    media = {}
    for card in summary['audio_cases']:
        c = by_uid.get(card['case_uid'], {})
        info = c.get('report_media')
        if info:
            previous = media.get(info['id'])
            if previous is None or card['created_at'] > previous['created_at']:
                media[info['id']] = {**info, 'title': card['title'], 'created_at': card['created_at'],
                                      'source_type': (c.get('source') or {}).get('type', 'unknown')}
    media_order = {key: i+1 for i,key in enumerate(sorted(media, key=lambda k:(media[k]['created_at'],k)))}
    issues = []
    case_reviews = {}
    for card in summary['audio_cases']:
        c = by_uid.get(card['case_uid'], {})
        rv = _review(c, reviews) if c else {}
        case_reviews[card['case_uid']] = rv
        info = c.get('report_media') or {}
        card.update(audio_id=info.get('id'), audio_number=media_order.get(info.get('id')),
                    source_type=(c.get('source') or {}).get('type', 'unknown'),
                    review=rv, quality_flags=c.get('quality_flags', []),
                    reference_preview=c.get('reference_preview',''))
        if rv.get('status') == 'excluded':
            issues.append({'kind':'excluded','case_uid':card['case_uid'], 'run_id':card['run_id'], 'case_id':card['case_id'],
                           'title':card['title'], 'message':rv.get('note') or 'Manually excluded from aggregate comparisons. Saved scores are unchanged.'})
        elif rv.get('status') != 'confirmed':
            for flag in c.get('quality_flags', []):
                issues.append({**flag,'kind':'review', 'case_uid':card['case_uid'], 'run_id':card['run_id'], 'case_id':card['case_id'], 'title':card['title']})
        if card.get('error'):
            issues.append({'kind':'media','case_uid':card['case_uid'], 'run_id':card['run_id'], 'case_id':card['case_id'],
                           'title':card['title'], 'message':card['error'].get('message', 'Processing failed.')})
    for row in rows:
        c = by_uid[row['case_uid']]
        model = next(m for m in c['models'] if m['key'] == row['provider_key'])
        metric = (model.get('evaluation') or {}).get('metrics', {}).get(view, {})
        info = c.get('report_media') or {}
        media_id = info.get('id') or ('text_' + row['case_uid'])
        row['audio_id'] = info.get('id')
        row['audio_number'] = media_order.get(info.get('id'))
        row['reference_input_id'] = c.get('reference_canonical_id') or c.get('reference_hash')
        row['reference_id'] = metric.get('scored_reference_id') or c.get('reference_canonical_id') or c.get('reference_hash')
        row['comparison_policy'] = _policy(c, model, view)
        row['clip_id'] = digest([media_id, row['reference_id']])[:24]
        row['review'] = case_reviews.get(row['case_uid'], {})
        row['needs_review'] = bool(c.get('quality_flags')) and row['review'].get('status') != 'confirmed'
        row['excluded'] = row['review'].get('status') == 'excluded'
        row['source_type'] = (c.get('source') or {}).get('type', 'unknown')
        # Missing settings remain in history and coverage; they cannot masquerade as
        # a distinct, fully described live model in the main comparison selector.
        row['settings_known'] = bool(model.get('request_settings')) or row['origin'] == 'supplied'
        row['latest'] = False
        row['included'] = False
    seen = set()
    for row in sorted(rows, key=lambda r:(r['created_at'],r['run_id'],r['case_id']), reverse=True):
        key = (row['clip_id'],row['model'],row['comparison_policy'])
        if key not in seen:
            row['latest'] = True
            row['included'] = not row['excluded']
            seen.add(key)
    # Unknown-setting failures still constrain a newer/older request for the same
    # provider, evidenced audio and raw reference; no guessing of settings.
    unknown_failures = {}
    for row in rows:
        if row['origin']=='live' and not row['settings_known'] and row['status']!='success':
            k=(row['audio_id'],row['reference_input_id'],row['provider_key'],row['language'])
            unknown_failures[k]=max(unknown_failures.get(k,('', '')), (row['created_at'],row['run_id']))
    for row in rows:
        k=(row['audio_id'],row['reference_input_id'],row['provider_key'],row['language'])
        if row['included'] and row['status']=='success' and row['origin']=='live' and unknown_failures.get(k,('', ''))>(row['created_at'],row['run_id']):
            row['included']=False
            row['superseded_by_unconfigured_failure']=True
    groups = defaultdict(list)
    for row in rows:
        groups[row['model']].append(row)
    all_models = []
    for key, observations in groups.items():
        cfg = copy.deepcopy(configs[key])
        selected = [r for r in observations if r['included']]
        cfg.update(_totals(selected), saved_attempts=len(observations),
                   historical_successes=sum(r['status']=='success' for r in observations),
                   historical_failures=sum(r['status'] not in ('success','running','pending','queued') for r in observations),
                   settings_known=any(r['settings_known'] for r in observations),
                   last_seen=max(r['created_at'] for r in observations))
        if not cfg['settings_known'] and cfg['origin']=='live':
            cfg['label'] = ('ElevenLabs' if cfg['provider']=='elevenlabs' else cfg['label'])+' · settings not recorded'
        all_models.append(cfg)
    all_models.sort(key=lambda m:(m['origin']!='live',m['provider'],m['label']))
    candidates = [m for m in all_models if m['successes'] and m['settings_known']]
    def pairs_for(a,b):
        # Common reference AND policy AND input: no cross-language or mixed-source ranking.
        if a['origin'] != b['origin'] or a.get('language') != b.get('language'):
            return []
        ar = {(r['clip_id'],r['comparison_policy']):r for r in rows if r['model']==a['key'] and r['included'] and r['status']=='success'}
        br = {(r['clip_id'],r['comparison_policy']):r for r in rows if r['model']==b['key'] and r['included'] and r['status']=='success'}
        # Live comparisons require audio identity; supplied texts may be compared within the same case.
        shared = sorted(set(ar)&set(br))
        return [(ar[k],br[k]) for k in shared if a['origin']=='supplied' or ar[k]['audio_id']]
    combinations = []
    for a,b in itertools.combinations(candidates,2):
        if a['provider']==b['provider'] and a['origin']=='live':
            continue
        ab = pairs_for(a,b)
        priority = (int(a['origin']=='live' and b['origin']=='live'),
                    int({a['provider'],b['provider']}=={'humain','elevenlabs'}),
                    bool(ab), min(a['last_seen'],b['last_seen']), len(ab))
        combinations.append((priority,a,b,ab))
    chosen = None
    if len(pair_keys)==2:
        a = next((m for m in candidates if m['key']==pair_keys[0]),None)
        b = next((m for m in candidates if m['key']==pair_keys[1]),None)
        if a and b and a['key']!=b['key']:
            chosen=((),a,b,pairs_for(a,b))
    if chosen is None and combinations:
        chosen=max(combinations,key=lambda x:x[0])
    paired_models, paired_rows, shared_cases = [], [], []
    chosen_keys=[]
    if chosen:
        _,a,b,ab = chosen
        if a['provider'] == 'elevenlabs' and b['provider']=='humain': a,b=b,a; ab=[(y,x) for x,y in ab]
        chosen_keys=[a['key'],b['key']]
        for side, cfg in enumerate((a,b)):
            selected=[entry[side] for entry in ab]
            paired_models.append({**cfg, **_totals(selected), 'available_successes':cfg['successes']})
        for left,right in ab:
            paired_rows.extend([left,right])
            shared_cases.append({'id':left['clip_id'], 'title':left['title'], 'audio_number':left['audio_number'],
                'source_type':left['source_type'], 'reference_id':left['reference_id'],
                'needs_review':left['needs_review'] or right['needs_review'], 'left':left,'right':right,
                'delta_pp':100*(left['wer']-right['wer'])})
    shared_cases.sort(key=lambda x:(x['audio_number'] or 0,x['reference_id']))
    flagged = sum(c['needs_review'] for c in shared_cases)
    best = None; best_rate = None
    if shared_cases and not flagged and not summary.get('active_jobs'):
        best_rate=min(m['wer'] for m in paired_models)
        best=' / '.join(m['label'] for m in paired_models if math.isclose(m['wer'],best_rate,abs_tol=1e-12))
    notes = []
    if flagged: notes.append(f'{flagged} paired case(s) need reference review. Scores remain visible; no winner is declared.')
    elif not shared_cases: notes.append('No common successful cases for these two configurations. Change the pair or evaluate the same audio and reference with both providers.')
    else: notes.append(f'{len(shared_cases)} common test case(s). This is a descriptive comparison on this subset, not a global benchmark.')
    if shared_cases and len({c['audio_number'] for c in shared_cases}) < len(shared_cases):
        notes.append('This subset includes different reference versions for the same input; it is not a count of independent recordings.')
    if any(c['source_type']=='upload' for c in shared_cases) and any(c['source_type']=='sample' for c in shared_cases):
        notes.append('Different encodings without proven lineage remain separate inputs. The same spoken content may appear more than once.')
    for row in rows:
        if row['status'] not in ('success','pending','running','queued'):
            issues.append({'kind':'provider','case_uid':row['case_uid'],'run_id':row['run_id'],'case_id':row['case_id'],
                           'title':row['title'],'model':row['provider_key'], 'message':(row.get('error') or {}).get('message','No valid score was saved.')})
    rows_by_case=defaultdict(list)
    for row in rows: rows_by_case[row['case_uid']].append(row)
    for card in summary['audio_cases']:
        card['models']=rows_by_case[card['case_uid']]
    provenance = Counter(r['provenance'] for r in rows if r['status']=='success')
    summary.update(version=REPORT_VERSION, models=all_models, chart_rows=paired_rows,
        case_count=len(media), duration=sum(m['duration'] for m in media.values()),
        audio_input_count=len(media), audio_identity_note='Inputs deduplicated by recorded source/interval or exact file hash, not by acoustic similarity. Reference versions do not add audio inputs.',
        media_unavailable_cases=sum(not c.get('audio_id') for c in summary['audio_cases']),
        successful_transcripts=sum(r['status']=='success' for r in rows),
        included_transcripts=sum(r['included'] and r['status']=='success' for r in rows),
        recorded_model_attempts=len(rows), earlier_attempts=sum(not r['latest'] for r in rows),
        excluded_attempts=sum(r['excluded'] for r in rows), provenance_counts=dict(provenance),
        comparison={'keys':chosen_keys,'options':[{'key':m['key'],'label':m['label']} for m in candidates],
            'models':paired_models,'cases':shared_cases,'matched':len(shared_cases),'flagged':flagged,
            'notes':notes,'best':best,'best_wer':best_rate, 'selection_requested':list(pair_keys)},
        matched_cases=len(shared_cases), best=best,best_wer=best_rate,comparable=bool(best),
        issues=issues, unresolved_review_cases=len({i['case_uid'] for i in issues if i['kind']=='review'}),
        comparison_note='Latest per input/scored-reference/configuration; paired metrics use only common successful cases. All saved attempts remain listed.',
        read_warnings=summary.get('read_warnings', []) + reviews.get('_warnings', []))
    return summary
