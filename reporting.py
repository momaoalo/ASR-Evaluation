"""Render a standalone dashboard snapshot. No new inference and no CDN dependency."""
import copy
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from evaluation.evaluator import aggregate_results
from evaluation.profiles import profile_catalog, validate_score_view
from storage import now


def public_case(case: dict) -> dict:
    c = copy.deepcopy(case)
    c.pop('_saved_ns', None)
    if isinstance(c.get('audio'), dict): c['audio'].pop('artifact', None)
    for m in c.get('models', []):
        m.pop('raw_response_path', None)
        if m.get('status') == 'success':
            from evaluation.overview import _checked_metric
            try:
                for view in ('raw', 'normalized'):
                    _checked_metric(m, view)
            except (KeyError, TypeError, ValueError, OverflowError):
                m.update(status='invalid_result', error={'message': 'Saved metrics are inconsistent. Re-score this run.'})
    return c


def export_html_report(results: list, job: dict, root: Path, *, score_view=None) -> str:
    """Single-run export shares the same reporting definitions as the dashboard."""
    view = validate_score_view(score_view or job.get('score_view', 'normalized'))
    run_id=job.get('run_id') or (results[0]['run_id'] if results else 'all')
    return export_overview_report(results, [{**job,'run_id':run_id}], root,
                                  filters={'run':run_id}, score_view=view)


def export_overview_report(results, jobs, root, *, filters=None, score_view='normalized', read_warnings=(), reviews=None, pair_keys=()):
    """One frozen cross-run snapshot; filters never silently revert to one run."""
    from evaluation.overview import validate_filters
    from evaluation.dashboard import build_dashboard as build_overview
    view = validate_score_view(score_view)
    f = validate_filters(filters)
    summaries = {v: build_overview(results, jobs, v, f, reviews, pair_keys) for v in ('normalized', 'raw')}
    for summary in summaries.values():
        summary['read_warnings'] = list(read_warnings)
    selected = summaries[view]
    allowed = {(c['run_id'], c['case_id']): set() for c in selected['audio_cases']}
    for row in selected['rows']:
        allowed.setdefault((row['run_id'], row['case_id']), set()).add(row['provider_key'])
    cases = []
    for case in results:
        key = (case['run_id'], case['case_id'])
        if key in allowed:
            safe = public_case(case)
            safe['report_review'] = (reviews or {}).get(case['run_id']+'/'+case['case_id'], {})
            safe['models'] = [m for m in safe['models'] if m['key'] in allowed[key]]
            cases.append(safe)
    job = {'run_id': f['run'], 'name': 'All runs' if f['run'] == 'all' else f['run'],
           'mode': 'overview', 'status': 'snapshot', 'created_at': now()}
    data = {'offline': True, 'overview': True, 'job': job, 'jobs': jobs,
            'default_view': view, 'filters': f, 'normalization': profile_catalog(),
            'summaries': summaries, 'cases': cases, 'exported_at': now(), 'pair_keys': list(pair_keys), 'csv':{v:csv_results(summaries[v]) for v in summaries}}
    env = Environment(loader=FileSystemLoader(root / 'templates'), autoescape=select_autoescape(['html']))
    return env.get_template('report.html').render(
        data=data, boot={'sample_audio_present': False}, css=(root / 'static/css/app.css').read_text('utf-8'),
        charts=(root / 'static/js/charts.js').read_text('utf-8'),
        script=(root / 'static/js/app.js').read_text('utf-8'))


def csv_results(summary):
    """One row per saved model attempt, plus unscored media cases. UTF-8 BOM."""
    import csv
    import io
    fields = ['run_id','case_id','title','source_type','audio_id','provider','configuration',
              'status','provenance','view','wer_percent','cer_percent','C','S','D','I',
              'reference_words','latest','included','needs_review','excluded','error']
    out = io.StringIO(newline=''); writer = csv.DictWriter(out, fieldnames=fields)
    writer.writeheader()
    def safe(value):
        if isinstance(value,str) and value.lstrip().startswith(('=','+','-','@','\t','\r')):
            return "'" + value
        return value
    for r in summary['rows']:
        row = dict(run_id=r['run_id'],case_id=r['case_id'],title=r['title'],
            source_type=r.get('source_type'),audio_id=r.get('audio_id'),provider=r['provider_key'],
            configuration=r['series_label'],status=r['status'],provenance=r['provenance'],
            view=summary['view'],wer_percent=None if r['wer'] is None else 100*r['wer'],
            cer_percent=None if r['cer'] is None else 100*r['cer'],
            reference_words=r['reference_words'], latest=r.get('latest'),included=r['included'],
            needs_review=r.get('needs_review'),excluded=r.get('excluded'),error=(r.get('error') or {}).get('message',''))
        row.update(r.get('counts') or {})
        writer.writerow({k:safe(v) for k,v in row.items()})
    represented={r['case_uid'] for r in summary['rows']}
    for c in summary['audio_cases']:
        if c['case_uid'] not in represented:
            writer.writerow({k:safe(v) for k,v in dict(run_id=c['run_id'],case_id=c['case_id'],title=c['title'],
                status=c['status'],view=summary['view'],source_type=c.get('source_type'),error=(c.get('error') or {}).get('message','No saved output.')).items()})
    return '\ufeff' + out.getvalue()
