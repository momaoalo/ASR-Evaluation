"""Flask boundary: validate HTTP, call services, return safe JSON or HTML.
Run locally with: python app.py. This is a single-user workstation application.
"""
import copy
import hmac
import hashlib
import importlib.util
import json
import secrets
import shutil
from pathlib import Path
from urllib.parse import urlparse
from flask import Flask, request, jsonify, render_template, send_file, abort, make_response
from werkzeug.exceptions import HTTPException
from config import Settings
VERSION = "1.6.2"
from storage import read_json, write_json, load_results, load_result, now, valid_id, new_id, ResultIndex
from pipeline import validate_request, save_uploaded_audio, build_case, score_imported_case
from evaluation.normalizer import validate_profile
from evaluation.profiles import profile_catalog, get_cleaning_profile, validate_score_view
from evaluation.evaluator import aggregate_results
from jobs import JobManager
from reporting import export_html_report, export_overview_report, public_case
from evaluation.overview import validate_filters
from evaluation.dashboard import build_dashboard as build_overview
from reporting_review import load_reviews, save_review, rescore_reference
from ui_integrity import UI_BUILD, verify_ui_files, repair_page
from services.downloader import yt_dlp_available


def create_app(settings=None, start_worker=True):
    s = settings or Settings()
    app = Flask(__name__, template_folder=str(s.root / 'templates'), static_folder=str(s.root / 'static'))
    app.config.update(MAX_CONTENT_LENGTH=s.max_upload_mb*1024**2, TRUSTED_HOSTS=['localhost', '127.0.0.1', '[::1]'])
    app.json.ensure_ascii = False
    app.config['TEMPLATES_AUTO_RELOAD'] = True
    csrf = secrets.token_urlsafe(32)
    jobs = JobManager(s, start_worker)
    app.extensions['jobs'] = jobs
    app.extensions['settings'] = s
    app.extensions['csrf'] = csrf
    result_index = ResultIndex(s)
    app.extensions['result_index'] = result_index

    @app.before_request
    def local_boundary():
        if request.remote_addr not in ('127.0.0.1', '::1', None):
            abort(403, 'This application is local-only.')
        if request.method in ('POST', 'PUT', 'PATCH', 'DELETE'):
            if not hmac.compare_digest(request.headers.get('X-CSRF-Token', ''), csrf):
                abort(403, 'Reload the application and retry the request.')
            origin = request.headers.get('Origin')
            if origin and urlparse(origin).netloc != request.host:
                abort(403, 'Cross-origin requests are not accepted.')

    @app.after_request
    def headers(response):
        response.headers.update({'X-Content-Type-Options': 'nosniff', 'X-Frame-Options': 'DENY',
            'Referrer-Policy': 'no-referrer', 'Cache-Control': 'no-store'})
        if request.path == '/':
            response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'"
        return response

    @app.errorhandler(Exception)
    def safe_error(exc):
        if isinstance(exc, HTTPException):
            return jsonify(error=exc.description), exc.code
        if isinstance(exc, FileNotFoundError):
            return jsonify(error='The requested artifact was not found.'), 404
        if isinstance(exc, (ValueError, KeyError, TypeError)):
            return jsonify(error=str(exc) if not isinstance(exc, KeyError) else 'Required field missing.'), 400
        return jsonify(error='The operation failed. Saved results have not been removed.'), 500

    @app.get('/')
    def index():
        problems = verify_ui_files(s.root)
        if problems:
            return repair_page(problems, s.root), 503
        assets = b''.join((s.root / name).read_bytes() for name in
            ('templates/index.html', 'templates/_workspace.html',
             'static/js/app.js', 'static/js/charts.js', 'static/css/app.css'))
        version = hashlib.sha256(assets).hexdigest()[:16]
        try:
            included_sample = read_json(s.root / 'examples/sample.json')
        except (OSError, ValueError):
            included_sample = None
        return render_template('index.html', asset_version=version,
            boot={'csrf': csrf, 'version': VERSION, 'ui_version': UI_BUILD,
                  'sample': included_sample, 'sample_audio_present': (s.root / 'examples/doctor_clip.mp3').is_file(), 'offline': False,
                  'normalization': profile_catalog()})

    @app.get('/api/build')
    def build_route():
        # Local-only diagnostics: no provider credentials and no inference.
        problems = verify_ui_files(s.root)
        return jsonify(ui_build=UI_BUILD, application_version=VERSION,
            files_consistent=not problems, issues=problems,
            project_directory=str(s.root.resolve()),
            sample_audio_present=(s.root / 'examples/doctor_clip.mp3').is_file(),
            sample_reference_present=(s.root / 'examples/sample.json').is_file())

    @app.get('/api/health')
    def health():
        c = s.credentials()
        return jsonify(version=VERSION, local_only=True,
            tools={**{name: bool(shutil.which(name)) for name in ('ffmpeg', 'ffprobe', 'deno')}, 'yt-dlp': yt_dlp_available()},
            packages={name: bool(importlib.util.find_spec(module)) for name, module in [('jiwer','jiwer'), ('humain-voice','humain_voice')]},
            providers={'elevenlabs': bool(c.get('elevenlabs_api_key')),
                       'humain': bool(c.get('humain_api_key') and c.get('humain_api_url'))})

    @app.get('/api/sample')
    def sample():
        return jsonify(read_json(s.root / 'examples/sample.json'))

    @app.get('/api/sample/audio')
    def sample_audio():
        return send_file(s.root / 'examples/doctor_clip.mp3', conditional=True)

    @app.post('/api/sample/score')
    def sample_score():
        sample = read_json(s.root / 'examples/sample.json')
        run_id = new_id('sample')
        payload = request.get_json() or {}
        score_view = validate_score_view(payload.get('score_view', 'normalized'))
        p = get_cleaning_profile(sample['profile'].get('language', 'mixed'))
        case = build_case(sample['case'], 0, p)
        meta = sample['audio']
        score_imported_case(case, sample['predictions'], run_id, s, meta)
        job = {'job_id': run_id, 'run_id': run_id, 'name': 'At the doctor · supplied transcripts',
               'created_at': now(), 'updated_at': now(), 'status': 'complete', 'mode': 'imported',
               'completed': 1, 'total': 1, 'profile': p, 'score_view': score_view, 'models': ['ai_transcriber', 'elevenlabs'],
               'stage': 'Saved user-supplied transcripts scored locally. No ASR calls.'}
        write_json(jobs.path(run_id), job)
        return jsonify(job)

    @app.post('/api/imported/evaluate')
    def imported_evaluate():
        payload = request.get_json() or {}
        profile = validate_profile(payload['profile']) if payload.get('profile') is not None else get_cleaning_profile()
        score_view = validate_score_view(payload.get('score_view', 'normalized'))
        case = build_case(payload.get('case') or {}, 0, profile)
        predictions = payload.get('predictions')
        if not isinstance(predictions, list) or not 1 <= len(predictions) <= 8:
            raise ValueError('Provide at least one supplied transcript.')
        clean_predictions = []
        for i, item in enumerate(predictions):
            if not isinstance(item, dict):
                raise ValueError('Each supplied transcript must be an object.')
            text = item.get('text', '')
            if not isinstance(text, str) or not text.strip() or len(text) > s.max_text_chars:
                raise ValueError(f'Supplied transcript {i + 1} is empty or too long.')
            label = str(item.get('label') or f'Model {i + 1}')[:120]
            clean_predictions.append({'key': f'imported_{i+1}', 'label': label, 'text': text, 'format': item.get('format', 'plain')})
        run_id = new_id('imported')
        score_imported_case(case, clean_predictions, run_id, s)
        job = {'job_id': run_id, 'run_id': run_id, 'name': case['title'],
               'created_at': now(), 'updated_at': now(), 'status': 'complete', 'mode': 'imported',
               'completed': 1, 'total': 1, 'profile': profile, 'score_view': score_view,
               'models': [x['key'] for x in clean_predictions],
               'stage': 'Supplied transcripts scored locally. No ASR API calls.'}
        write_json(jobs.path(run_id), job)
        return jsonify(job), 201

    @app.post('/api/uploads')
    def upload():
        files = request.files.getlist('files')
        if not 1 <= len(files) <= s.max_cases:
            raise ValueError('Select one or more audio files.')
        return jsonify(uploads=[save_uploaded_audio(f, s) for f in files])

    @app.post('/api/evaluate')
    def evaluate_route():
        raw_payload = request.get_json()
        payload = validate_request(raw_payload, s)
        # Block the specific old UI failure: a bundled reference silently carried
        # into a different source. Legitimate reuse requires explicit acknowledgement.
        sample_reference = read_json(s.root / 'examples/sample.json')['case']['ground_truth']
        from evaluation.report_metadata import text_id
        for original in raw_payload.get('cases', []):
            if original.get('source', {}).get('type') != 'sample' and text_id(original.get('ground_truth')) == text_id(sample_reference) and original.get('reference_confirmed') is not True:
                raise ValueError('The bundled reference is attached to another audio source. Check the match and explicitly confirm it (reference_confirmed=true).')
        # Missing credentials are a preflight error, never a falsely scored model.
        supplied = (raw_payload or {}).get('provider_credentials') or {}
        if not isinstance(supplied, dict):
            raise ValueError('Invalid provider credentials.')
        allowed = ('humain_api_key', 'elevenlabs_api_key', 'humain_api_url')
        if any(k not in allowed for k in supplied):
            raise ValueError('Unsupported provider setting.')
        if any(not isinstance(v, str) or len(v) > 2048 for v in supplied.values()):
            raise ValueError('Invalid provider setting value.')
        supplied = {k: v.strip() for k, v in supplied.items() if v.strip()}
        credentials = {**s.credentials(), **supplied}
        if 'elevenlabs' in payload['models'] and not credentials.get('elevenlabs_api_key'):
            raise ValueError('ElevenLabs API key is not configured in the backend.')
        if 'humain' in payload['models']:
            from services.humain_asr import validate_connection
            try:
                validate_connection(credentials)
            except Exception as exc:
                raise ValueError(str(exc)) from None
        job = jobs.create_job(payload, credentials=supplied)
        return jsonify(job), 202

    @app.get('/api/jobs')
    def job_list():
        return jsonify(jobs=jobs.list())

    @app.get('/api/jobs/<job_id>')
    def job_status_route(job_id):
        return jsonify(jobs.public(jobs.get(job_id)))

    @app.post('/api/jobs/<job_id>/cancel')
    def cancel_job(job_id):
        return jsonify(jobs.cancel(job_id))

    def snapshot(run_id=None):
        filters = validate_filters(request.args)
        if run_id is not None:
            filters['run'] = valid_id(run_id)
        view = validate_score_view(request.args.get('view', 'normalized'))
        saved_jobs = jobs.list()
        cases, warnings = result_index.load(filters['run'])
        if filters['run'] != 'all' and not cases and not warnings and not any(
                j['run_id'] == filters['run'] for j in saved_jobs):
            abort(404, 'The saved run was not found. Refresh Saved runs.')
        summary = build_overview(cases, saved_jobs, view, filters, load_reviews(s),
            [request.args.get('pair_a', ''), request.args.get('pair_b', '')])
        summary['read_warnings'] = summary.get('read_warnings', []) + warnings + jobs.read_errors
        # Job metadata alone is not a scored case, but explain it rather than showing an unexplained zero.
        with_cases = {c['run_id'] for c in cases}
        summary['runs_without_results'] = [j for j in saved_jobs
            if j['run_id'] not in with_cases and filters['run'] in ('all', j['run_id'])]
        return cases, saved_jobs, summary

    def overview_snapshot():
        return snapshot()

    @app.get('/api/overview')
    def overview_route():
        _, saved_jobs, summary = overview_snapshot()
        return jsonify(summary=summary, jobs=saved_jobs)

    @app.get('/api/export/overview')
    def export_overview_route():
        compact, saved_jobs, summary = overview_snapshot()
        stamps = {(c['run_id'], c['case_id']): c.get('_saved_ns', 0) for c in compact}
        wanted = {(r['run_id'], r['case_id']) for r in summary['audio_cases'] if r.get('has_result', True)}
        cases = [{**load_result(s, run, case_id), '_saved_ns': stamps[(run, case_id)]} for run, case_id in sorted(wanted)]
        # Freeze exactly the visible filters and backend-computed summaries.
        html = export_overview_report(cases, saved_jobs, s.root,
            filters=summary['filters'], score_view=summary['view'], read_warnings=summary['read_warnings'],
            reviews=load_reviews(s), pair_keys=summary['comparison']['keys'])
        response = make_response(html)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Content-Disposition'] = 'attachment; filename="asr_overview_report.html"'
        return response

    @app.post('/api/reviews/<run_id>/<case_id>')
    def review_route(run_id, case_id):
        payload = request.get_json() or {}
        return jsonify(save_review(s, run_id, case_id, payload))

    @app.post('/api/reference/<run_id>/<case_id>')
    def reference_route(run_id, case_id):
        payload = request.get_json() or {}
        job = rescore_reference(s, run_id, case_id, payload)
        return jsonify(job), 201

    @app.get('/api/export/overview.json')
    def overview_json():
        _, saved_jobs, summary = overview_snapshot()
        cases = [public_case(load_result(s, c['run_id'], c['case_id']))
                 for c in summary['audio_cases'] if c.get('has_result', True)]
        response = jsonify(report_version='dashboard-1.6.2', exported_at=now(), summary=summary,
                           reviews=load_reviews(s), cases=cases, jobs=saved_jobs)
        response.headers['Content-Disposition'] = 'attachment; filename="asr_results.json"'
        return response

    @app.get('/api/export/overview.csv')
    def overview_csv():
        from reporting import csv_results
        _, _, summary = overview_snapshot()
        response = make_response(csv_results(summary))
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        response.headers['Content-Disposition'] = 'attachment; filename="asr_results.csv"'
        return response

    @app.get('/api/results/<run_id>')
    def results_route(run_id):
        cases, saved_jobs, summary = snapshot(run_id)
        job = next((j for j in saved_jobs if j['run_id'] == run_id), None)
        if job is None:
            # Still open saved outcomes if job metadata was lost. Do not delete/re-score them.
            job = {'run_id': run_id, 'job_id': run_id, 'name': run_id,
                   'status': 'recovered', 'completed': len(cases), 'total': len(cases),
                   'profile': cases[0].get('profile', {}) if cases else {},
                   'created_at': '', 'mode': 'saved', 'metadata_missing': True}
        return jsonify(job=job, summary=summary)

    @app.get('/api/results/<run_id>/<case_id>')
    def result_detail_route(run_id, case_id):
        case = public_case(load_result(s, run_id, case_id))
        case['report_review'] = load_reviews(s).get(run_id+'/'+case_id, {})
        from evaluation.overview import compact_case
        case['quality_flags'] = compact_case(case).get('quality_flags', [])
        return jsonify(case)

    @app.get('/api/audio/<run_id>/<case_id>')
    def case_audio(run_id, case_id):
        case = load_result(s, run_id, case_id)
        if case.get('source', {}).get('type') == 'sample' and case.get('audio', {}).get('artifact') is None:
            return send_file(s.root / 'examples/doctor_clip.mp3', conditional=True)
        name = case.get('audio', {}).get('artifact', '')
        if not name or Path(name).name != name:
            abort(404)
        return send_file(s.data / 'audio' / name, conditional=True)

    @app.post('/api/rescore/<run_id>')
    def rescore_route(run_id):
        originals = load_results(s, run_id)
        if not originals:
            raise ValueError('No saved case outcomes to re-score.')
        payload = request.get_json() or {}
        profile = validate_profile(payload['profile']) if payload.get('profile') is not None else get_cleaning_profile()
        score_view = validate_score_view(payload.get('score_view', 'normalized'))
        old = jobs.get(run_id)
        job = jobs.create_job({'source_results': originals, 'name': old['name'] + ' · re-score',
            'profile': profile, 'score_view': score_view, 'models': old.get('models', []), 'mode': 'rescore', 'from_run': run_id})
        return jsonify(job), 202

    @app.get('/api/export/<run_id>')
    def export_report_route(run_id):
        job = jobs.public(jobs.get(run_id))
        score_view = validate_score_view(request.args.get('view', job.get('score_view', 'normalized')))
        html = export_overview_report(load_results(s, run_id), [job], s.root,
            filters={'run':run_id}, score_view=score_view, reviews=load_reviews(s))
        response = make_response(html)
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        response.headers['Content-Disposition'] = f'attachment; filename="asr_report_{valid_id(run_id)}.html"'
        return response

    @app.get('/api/results/<run_id>/download/json')
    def export_json(run_id):
        response = jsonify(job=jobs.public(jobs.get(run_id)), cases=[public_case(c) for c in load_results(s, run_id)])
        response.headers['Content-Disposition'] = f'attachment; filename="{valid_id(run_id)}.json"'
        return response

    return app


if __name__ == '__main__':
    from run_local import main
    main()
