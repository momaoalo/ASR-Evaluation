"""Single-process job queue for a local workstation, not a distributed broker."""
import copy
import queue
import threading
from storage import now, new_id, write_json, read_json, load_results, save_result, valid_id
from pipeline import run_batch
from evaluation.evaluator import evaluate_transcription
from evaluation.normalizer import extract_spoken_text

TERMINAL = ('complete', 'partial', 'failed', 'cancelled', 'interrupted')

class JobManager:
    def __init__(self, settings, start_worker=True):
        self.settings = settings
        self.queue = queue.Queue(maxsize=10)
        self.lock = threading.RLock()
        self.cancelled = set()
        self._runtime_credentials = {}
        self.stop_event = threading.Event()
        (settings.data / 'jobs').mkdir(parents=True, exist_ok=True)
        # No auto-replay: a terminated process may have submitted billable requests.
        self.read_errors = []
        for job in self.list():
            if job.get('status') not in TERMINAL:
                full = self.get(job['job_id'])
                full.update(status='interrupted', stage='Interrupted by a server restart; not resubmitted.')
                write_json(self.path(job['job_id']), full)
        self.worker = None
        if start_worker:
            self.worker = threading.Thread(target=self._work, daemon=True, name='asr-single-worker')
            self.worker.start()

    def path(self, job_id):
        return self.settings.data / 'jobs' / (valid_id(job_id) + '.json')

    def get(self, job_id):
        return read_json(self.path(job_id))

    def public(self, job):
        result = {k: v for k, v in job.items() if k not in ('cases', 'source_results')}
        # Lightweight case headers let Overview show work before a score exists.
        # Do not return references, transcripts, paths or provider credentials here.
        source = job.get('cases') or job.get('source_results') or []
        result['case_headers'] = [
            {'case_id': c['case_id'], 'title': c.get('title') or c['case_id']}
            for c in source if isinstance(c, dict) and isinstance(c.get('case_id'), str)]
        return result

    def list(self):
        records, errors = [], []
        for path in (self.settings.data / 'jobs').glob('*.json'):
            try:
                job = read_json(path)
                if job.get('run_id') != path.stem or job.get('job_id') != path.stem:
                    raise ValueError('Invalid job record')
                records.append(self.public(job))
            except (OSError, ValueError, KeyError, TypeError, AttributeError):
                errors.append({'run_id': path.stem, 'message': 'Job metadata is unreadable; saved case outcomes are preserved.'})
        self.read_errors = errors
        return sorted(records, key=lambda j: (j.get('created_at', ''), j['run_id']), reverse=True)

    def patch(self, job_id, **fields):
        with self.lock:
            job = self.get(job_id); job.update(fields, updated_at=now())
            write_json(self.path(job_id), job)
            return job

    def create_job(self, request, credentials=None):
        with self.lock:
            if self.queue.full():
                raise ValueError('The local job queue is full. Wait for a job to finish.')
            key = new_id('run')
            job = {**request, 'job_id': key, 'run_id': key, 'created_at': now(), 'updated_at': now(),
                   'status': 'queued', 'completed': 0, 'total': len(request.get('cases', request.get('source_results', []))),
                   'stage': 'Queued', 'current_case': ''}
            write_json(self.path(key), job)
            if credentials:
                self._runtime_credentials[key] = credentials.copy()
            self.queue.put_nowait(key)
            return self.public(job)

    def cancel(self, job_id):
        job = self.get(job_id)
        if job['status'] in TERMINAL:
            return self.public(job)
        self.cancelled.add(job_id)
        return self.public(self.patch(job_id, stage='Stop requested — finish the current case first.'))

    def _work(self):
        while not self.stop_event.is_set():
            try:
                job_id = self.queue.get(timeout=.3)
            except queue.Empty:
                continue
            try:
                self.execute(job_id)
            except Exception:
                # A damaged job record must not kill the queue worker.
                try:
                    self.patch(job_id, status='failed', stage='Unable to process the job record.')
                except Exception:
                    pass
            finally:
                self.queue.task_done()

    def execute(self, job_id):
        job = self.patch(job_id, status='running', stage='Starting')
        def update(index, title, stage):
            self.patch(job_id, completed=index, current_case=title, stage=stage)
        try:
            if job.get('mode') == 'rescore':
                outcomes = []
                for index, original in enumerate(job['source_results']):
                    if job_id in self.cancelled:
                        break
                    c = copy.deepcopy(original)
                    c.update(run_id=job_id, created_at=now(), profile=job['profile'], rescored_from=original['run_id'])
                    update(index, c['title'], 'Re-scoring saved transcripts')
                    for m in c.get('models', []):
                        if m['status'] == 'success':
                            try:
                                # Re-parse explicit imported metadata from its untouched raw
                                # source; this also repairs legacy subtitle numeric-line loss.
                                fmt = m.get('metadata', {}).get('format')
                                if m.get('provenance') == 'imported' and fmt in ('plain', 'subtitles') and isinstance(m.get('raw_text'), str):
                                    m['speech_text'], m['metadata'] = extract_spoken_text(m['raw_text'], fmt)
                                m['evaluation'] = evaluate_transcription(c['reference'], m['speech_text'], job['profile'])
                            except ValueError as exc:
                                m['status'] = 'failed'; m['error'] = {'message': str(exc), 'stage': 'rescore'}
                    successes = sum(m['status'] == 'success' for m in c.get('models', []))
                    c['status'] = 'complete' if successes and successes == len(c['models']) else ('partial' if successes else 'failed')
                    save_result(self.settings, c); outcomes.append(c)
                    update(index+1, c['title'], 'Saved')
            else:
                creds = self._runtime_credentials.get(job_id, {})
                # Credentials live only in memory while the queued job runs.
                class PerJobSettings:
                    def __getattr__(_, name):
                        return getattr(self.settings, name)
                    def credentials(_):
                        return {**self.settings.credentials(), **creds}
                outcomes = run_batch(job, PerJobSettings(), update, lambda: job_id in self.cancelled)
            n = sum(c['status'] == 'complete' for c in outcomes)
            any_success = any(m['status'] == 'success' for c in outcomes for m in c.get('models', []))
            status = 'complete' if n == job['total'] else ('partial' if any_success else 'failed')
            if job_id in self.cancelled:
                status = 'cancelled'
            self.patch(job_id, status=status, completed=len(outcomes), stage='Finished', finished_at=now())
        except Exception:
            self.patch(job_id, status='failed', stage='Job failed. Completed case checkpoints are retained.')
        finally:
            self._runtime_credentials.pop(job_id, None)

    def close(self):
        self.stop_event.set()
