"""WER/CER, occurrence-level alignments and fair corpus aggregation."""
import re
from collections import defaultdict
from importlib.metadata import version, PackageNotFoundError
from .normalizer import (normalize_text, validate_profile, validate_text, text_warnings,
                         NORMALIZER_VERSION, VARIANTS_ID)
from storage import digest
from .rule_based import policy_warnings
from .profiles import describe_profile


def _engine_alignment(reference: str, hypothesis: str, level: str):
    """JiWER is primary. Its RapidFuzz dependency is an explicit offline fallback."""
    try:
        import jiwer
    except ImportError:
        from rapidfuzz.distance import Levenshtein
        r = reference.split() if level == 'words' else list(reference)
        h = hypothesis.split() if level == 'words' else list(hypothesis)
        chunks = [(x.tag, x.src_start, x.src_end, x.dest_start, x.dest_end)
                  for x in Levenshtein.opcodes(r, h)]
        return r, h, chunks, 'RapidFuzz fallback ' + version('rapidfuzz')
    result = (jiwer.process_words if level == 'words' else jiwer.process_characters)(reference, hypothesis)
    chunks = [(c.type, c.ref_start_idx, c.ref_end_idx, c.hyp_start_idx, c.hyp_end_idx)
              for c in result.alignments[0]]
    return result.references[0], result.hypotheses[0], chunks, 'JiWER ' + version('jiwer')


def _tokens(normalized: dict, level: str, spaces: bool) -> list[dict]:
    text, spans = normalized['text'], normalized['spans']
    if level == 'words':
        indices = [(m.start(), m.end()) for m in re.finditer(r'\S+', text)]
    else:
        indices = [(i, i + 1) for i, c in enumerate(text) if spaces or c != ' ']
    return [{'text': text[s:e], 'start': s, 'end': e,
             'source_start': min(p[0] for p in spans[s:e]),
             'source_end': max(p[1] for p in spans[s:e])} for s, e in indices]


def build_error_details(chunks, r_tokens, h_tokens) -> list:
    """Use positions, not word sets. Repeated words can have different outcomes."""
    ops = []
    for tag, rs, re_, hs, he in chunks:
        common = min(re_ - rs, he - hs)
        if tag in ('equal',):
            pairs = [('C', rs + k, hs + k) for k in range(common)]
        elif tag in ('replace', 'substitute'):
            pairs = [('S', rs + k, hs + k) for k in range(common)]
            pairs += [('D', i, None) for i in range(rs + common, re_)]
            pairs += [('I', None, i) for i in range(hs + common, he)]
        elif tag == 'delete':
            pairs = [('D', i, None) for i in range(rs, re_)]
        elif tag == 'insert':
            pairs = [('I', None, i) for i in range(hs, he)]
        else:
            raise ValueError('Unsupported alignment operation.')
        for kind, ri, hi in pairs:
            ops.append({'type': kind, 'ref_index': ri, 'hyp_index': hi,
                        'reference': r_tokens[ri] if ri is not None else None,
                        'prediction': h_tokens[hi] if hi is not None else None})
    return ops


def _score(r: dict, h: dict, level: str, spaces=True) -> dict:
    r_tokens, h_tokens = _tokens(r, level, spaces), _tokens(h, level, spaces)
    rtext = r['text'] if level == 'words' or spaces else r['text'].replace(' ', '')
    htext = h['text'] if level == 'words' or spaces else h['text'].replace(' ', '')
    rseq, hseq, chunks, engine = _engine_alignment(rtext, htext, level)
    if rseq != [t['text'] for t in r_tokens] or hseq != [t['text'] for t in h_tokens]:
        raise RuntimeError('Scoring engine tokenization does not match the declared policy.')
    ops = build_error_details(chunks, r_tokens, h_tokens)
    counts = {k: sum(o['type'] == k for o in ops) for k in 'CSDI'}
    n, m = len(r_tokens), len(h_tokens)
    if n == 0:
        raise ValueError('The reference is empty under this scoring policy.')
    if (counts['C'] + counts['S'] + counts['D'] != n or
            counts['C'] + counts['S'] + counts['I'] != m):
        raise RuntimeError('Invalid alignment counts; refusing to return a score.')
    return {'rate': (counts['S'] + counts['D'] + counts['I']) / n,
            'reference_length': n, 'prediction_length': m, 'counts': counts,
            'operations': ops, 'engine': engine}


def evaluate_transcription(reference: str, prediction: str, profile=None) -> dict:
    """An API failure is never passed here as an empty successful prediction."""
    p = validate_profile(profile)
    reference, prediction = validate_text(reference), validate_text(prediction)
    if not reference.strip():
        raise ValueError('A nonempty verified reference is required.')
    if max(len(reference), len(prediction)) > 50000:
        raise ValueError('Transcript exceeds the 50,000-character scoring limit.')
    raw_r, raw_h = normalize_text(reference, p, baseline=True), normalize_text(prediction, p, baseline=True)
    norm_r, norm_h = normalize_text(reference, p), normalize_text(prediction, p)
    if not norm_r['text'].strip():
        raise ValueError('The reference is empty under this scoring policy.')
    metrics = {}
    for name, r, h in [('raw', raw_r, raw_h), ('normalized', norm_r, norm_h)]:
        words = _score(r, h, 'words')
        chars = _score(r, h, 'characters', p['cer_spaces'])
        metrics[name] = {'wer': words['rate'], 'cer': chars['rate'], 'words': words, 'characters': chars,
                         'reference_text': r['text'], 'prediction_text': h['text']}
    return {'profile': p, 'profile_id': digest({'rules': p, 'version': NORMALIZER_VERSION, 'variants': VARIANTS_ID if (p['arabic_spelling'] or p['arabic_question_forms']) else None})[:16],
            'policy_label': describe_profile(p),
            'normalizer_version': NORMALIZER_VERSION, 'variants_id': VARIANTS_ID if (p['arabic_spelling'] or p['arabic_question_forms']) else None, 'metrics': metrics,
            'changes': {'reference': norm_r['changes'], 'prediction': norm_h['changes']},
            'metric_policy': {'word_tokens': 'whitespace', 'character_unit': 'Unicode code points',
                              'cer_spaces': p['cer_spaces'], 'ratios': 'unrounded',
                              'unicode_database': __import__('unicodedata').unidata_version,
                              'spelling_policy': describe_profile(p),
                              'word_dictionary_enabled': p['arabic_spelling'],
                              'question_equivalence': p['arabic_question_forms']},
            'warnings': list(dict.fromkeys(text_warnings(reference) + text_warnings(prediction) + policy_warnings(p) +
                        (['Custom spelling equivalences are enabled. These scores are policy-specific, not standard literal-spelling WER; inspect the change log.'] if p['arabic_spelling'] or p['arabic_question_forms'] else []))),
            'note': 'Raw baseline canonicalizes whitespace, zero-width word separators and display-only controls. Cleaning applies the saved spelling rules to both texts. Numeric signs, leading decimal points and unit separators are retained; letter case follows the selected unit-protection policy. No cleaning skips spelling changes; spacing/display preparation remains. CER counts Unicode code points, not bytes or visual graphemes; spaces follow the selected policy. Scores measure textual edits, not meaning or clinical safety.'}


def aggregate_results(results: list, view='normalized', model_filter='all', expected_models=None) -> dict:
    """Primary comparison uses the same successful case set for all chosen models."""
    if view not in ('raw', 'normalized'):
        raise ValueError('Invalid score view.')
    by_model = defaultdict(dict)
    labels = {}
    all_rows = []
    profile_ids = set()
    # Pending/missing selected models must not disappear from the comparison set.
    for key in expected_models or []:
        if model_filter in ('all', key):
            by_model[key]
            labels[key] = {'humain': 'HUMAIN', 'elevenlabs': 'ElevenLabs'}.get(key, key)
    for case in results:
        for m in case.get('models', []):
            key = m['key']; labels[key] = m['label']
            if model_filter != 'all' and key != model_filter:
                continue
            row = {'case_id': case['case_id'], 'title': case['title'], 'model': key, 'label': m['label'],
                   'status': m['status'], 'provenance': m.get('provenance', 'live'),
                   'duration': case.get('audio', {}).get('duration', 0),
                   'cache_hit': m.get('cache_hit', False), 'elapsed_ms': m.get('elapsed_ms'),
                   'error': m.get('error'), 'wer': None, 'cer': None, 'counts': None}
            if m['status'] == 'success':
                e = m['evaluation']; profile_ids.add(e['profile_id'])
                v = e['metrics'][view]
                row.update(wer=v['wer'], cer=v['cer'], counts=v['words']['counts'])
                identity = (case['case_id'], case['reference_hash'], e['profile_id'], case.get('audio', {}).get('sha256'))
                if identity in by_model[key]:
                    raise ValueError('Duplicate case/model identity. Aggregate one run at a time.')
                by_model[key][identity] = (case, m)
            else:
                by_model[key]  # include unsuccessful models in matched-set accounting
            all_rows.append(row)
    keys = sorted(by_model)
    common = set.intersection(*(set(by_model[k]) for k in keys)) if keys else set()
    policy_conflict = len(profile_ids) > 1
    if policy_conflict:
        common = set()  # Never blend incompatible normalization policies.
    models = []
    for key in keys:
        c = {x: 0 for x in 'CSDI'}; nc = {x: 0 for x in 'CSDI'}
        nw = nh = 0
        for identity in common:
            v = by_model[key][identity][1]['evaluation']['metrics'][view]
            for k in c:
                c[k] += v['words']['counts'][k]; nc[k] += v['characters']['counts'][k]
            nw += v['words']['reference_length']; nh += v['characters']['reference_length']
        attempted = sum(r['model'] == key for r in all_rows)
        models.append({'key': key, 'label': labels[key], 'matched': len(common),
                       'successes': len(by_model[key]), 'attempted': attempted,
                       'failures': attempted - len(by_model[key]), 'counts': c,
                       'wer': (c['S'] + c['D'] + c['I']) / nw if nw else None,
                       'cer': (nc['S'] + nc['D'] + nc['I']) / nh if nh else None,
                       'reference_words': nw, 'reference_characters': nh})
    valid = [m for m in models if m['wer'] is not None]
    best = min(valid, key=lambda m: m['wer']) if valid else None
    winners = [m['label'] for m in valid if abs(m['wer'] - best['wer']) < 1e-12] if best else []
    return {'case_count': len(results), 'duration': sum(c.get('audio', {}).get('duration', 0) for c in results),
            'models': models, 'rows': all_rows, 'matched_cases': len(common),
            'case_failures': [{'case_id': c['case_id'], 'title': c['title'], 'error': c['error']} for c in results if c.get('error')],
            'successful_transcripts': sum(r['status'] == 'success' for r in all_rows),
            'failures': sum(r['status'] != 'success' for r in all_rows), 'media_failures': sum(bool(c.get('error')) for c in results), 'best': ', '.join(winners) or None,
            'view': view, 'policy_count': len(profile_ids),
            'comparison_blocked': policy_conflict,
            'comparison_note': ('Mixed scoring policies: re-score with one profile before corpus comparison.' if policy_conflict else
                                'Corpus scores use the shared successful case set. Per-case charts show variation, not improvement over time.')}
