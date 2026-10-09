"""Media, jobs and API adapters; external calls are replaced with deterministic mocks."""
from pathlib import Path
from tempfile import TemporaryDirectory
from dataclasses import replace
from unittest.mock import patch, Mock
import io
import json
import shutil
import subprocess
import unittest
import requests
from config import Settings, BASE_DIR
from storage import read_json, write_json, file_hash, load_results, valid_id
from pipeline import validate_request, build_case, run_case, save_uploaded_audio
from jobs import JobManager
from evaluation.normalizer import validate_profile
from services.downloader import canonical_youtube_url
from services.audio_processor import probe_audio, prepare_audio
from services.asr_common import build_model_result, ProviderError
from services.elevenlabs_asr import transcribe_elevenlabs
from services.humain_asr import transcribe_humain

HAS_ORIGINAL_MP3 = (BASE_DIR / 'examples' / 'doctor_clip.mp3').is_file()

class Base(unittest.TestCase):
    def setUp(self):
        self.temp=TemporaryDirectory();self.root=Path(self.temp.name);self.s=Settings(root=self.root)
        (self.root/'examples').mkdir()
        shutil.copy(BASE_DIR/'examples'/'sample.json',self.root/'examples'/'sample.json')
        if HAS_ORIGINAL_MP3:
            shutil.copy(BASE_DIR/'examples'/'doctor_clip.mp3',self.root/'examples'/'doctor_clip.mp3')
        else:
            # Provider HTTP/SDK mock tests only need an existing file handle.
            # Do not claim this placeholder is the original audio fixture.
            (self.root/'examples'/'doctor_clip.mp3').write_bytes(b'NO_PUBLIC_AUDIO_FIXTURE')
        self.sample=read_json(self.root/'examples/sample.json')
    def tearDown(self):self.temp.cleanup()
    def case(self):return build_case(self.sample['case'],0,validate_profile())

class MediaTests(Base):
    @unittest.skipUnless(HAS_ORIGINAL_MP3 and shutil.which('ffmpeg') and shutil.which('ffprobe'),'Original audio fixture and FFmpeg required')
    def test_real_clip_crop(self):
        src=self.root/'examples/doctor_clip.mp3';before=file_hash(src)
        p,meta=prepare_audio(src,{'start':1,'end':3},self.s)
        self.assertAlmostEqual(meta['duration'],2,places=2);self.assertEqual(meta['sample_rate'],16000)
        self.assertEqual(meta['channels'],1);self.assertEqual(meta['codec'],'pcm_s16le')
        self.assertEqual(before,file_hash(src))
        p2,_=prepare_audio(src,{'start':1,'end':3},self.s);self.assertEqual(p,p2)

    @unittest.skipUnless(shutil.which('ffprobe'),'FFprobe required')
    def test_invalid_audio(self):
        p=self.root/'bad.mp3';p.write_bytes(b'not sound')
        with self.assertRaises(ValueError):probe_audio(p)

    @unittest.skipUnless(HAS_ORIGINAL_MP3 and shutil.which('ffprobe'),'Original audio fixture and FFprobe required')
    def test_bad_crop(self):
        with self.assertRaises(ValueError):prepare_audio(self.root/'examples/doctor_clip.mp3',{'start':20,'end':2},self.s)

class ValidationTests(Base):
    def test_good_youtube(self):
        self.assertEqual(canonical_youtube_url('https://youtu.be/IV3uF59g7rs'),'https://www.youtube.com/watch?v=IV3uF59g7rs')
    def test_bad_hosts(self):
        for url in ['http://youtube.com/watch?v=IV3uF59g7rs','https://youtube.com.evil.test/watch?v=IV3uF59g7rs','https://127.0.0.1/','https://youtube.com@evil.test/watch?v=IV3uF59g7rs','file:///etc/passwd','https://www.youtube.com/playlist?list=a']:
            with self.subTest(url=url),self.assertRaises(ValueError):canonical_youtube_url(url)
    def test_consent_required(self):
        with self.assertRaises(ValueError):validate_request({'cases':[self.sample['case']]},self.s)
    def test_duplicate_cases(self):
        with self.assertRaises(ValueError):validate_request({'cases':[self.sample['case']]*2,'consent':True},self.s)
    def test_batch_limit(self):
        with self.assertRaises(ValueError):validate_request({'cases':[self.sample['case']]*101,'consent':True},self.s)
    def test_id_path_traversal(self):
        for s in ['../x','/etc/passwd','x/y','..','']:
            with self.assertRaises(ValueError):valid_id(s)
    def test_atomic_json_unicode(self):
        p=self.root/'a.json';write_json(p,{'text':'أهلًا'});self.assertEqual(read_json(p)['text'],'أهلًا');self.assertFalse(list(self.root.glob('*.tmp')))

class ProviderTests(Base):
    @patch('services.elevenlabs_asr.requests.post')
    def test_eleven_request_and_parse(self, post):
        post.return_value=Mock(status_code=200,json=lambda:{'text':'أهلًا','words':[]})
        m,raw=transcribe_elevenlabs(self.root/'examples/doctor_clip.mp3',{'elevenlabs_api_key':'test-key'},'mixed')
        self.assertEqual(m['speech_text'],'أهلًا');kwargs=post.call_args.kwargs
        self.assertNotIn('language_code',kwargs['data']);self.assertNotIn('keyterms',kwargs['data'])
        self.assertEqual(kwargs['headers']['xi-api-key'],'test-key');self.assertNotIn('test-key',json.dumps(m))
        self.assertFalse(kwargs['allow_redirects'])
    @patch('services.elevenlabs_asr.requests.post')
    def test_auth_fail_no_retry(self,post):
        post.return_value=Mock(status_code=401)
        with self.assertRaises(ProviderError):transcribe_elevenlabs(self.root/'examples/doctor_clip.mp3',{'elevenlabs_api_key':'test'},'ar')
        self.assertEqual(post.call_count,1)
    @patch('services.elevenlabs_asr.requests.post',side_effect=requests.Timeout)
    def test_timeout_no_retry(self,post):
        with self.assertRaises(ProviderError):transcribe_elevenlabs(self.root/'examples/doctor_clip.mp3',{'elevenlabs_api_key':'test'},'ar')
        self.assertEqual(post.call_count,1)
    @patch('services.humain_asr.subprocess.run')
    def test_humain_child_contract(self,run):
        run.return_value=Mock(stdout='ASR_RESULT='+json.dumps({'text':'hello','raw':{'transcription':'hello'},'resolved_model':'bayan'}))
        c={'humain_api_key':'test-secret','humain_api_url':'https://api.humain.com','humain_api_path':'/socket.io','humain_model':'BayanArEn'}
        m,_=transcribe_humain(self.root/'examples/doctor_clip.mp3',c,'mixed')
        self.assertEqual(m['speech_text'],'hello');self.assertNotIn('test-secret',str(run.call_args.args));self.assertNotIn('test-secret',str(m))
        self.assertEqual(run.call_args.kwargs['timeout'],300)

class JobTests(Base):
    def test_create_returns_queued(self):
        manager=JobManager(self.s,start_worker=False)
        job=manager.create_job({'cases':[self.case()],'models':['elevenlabs'],'name':'Test','profile':validate_profile()})
        self.assertEqual(job['status'],'queued');self.assertNotIn('cases',job)
    def test_restart_not_replayed(self):
        manager=JobManager(self.s,start_worker=False)
        j=manager.create_job({'cases':[self.case()],'models':['elevenlabs'],'name':'Test'})
        restarted=JobManager(self.s,start_worker=False)
        self.assertEqual(restarted.get(j['job_id'])['status'],'interrupted');self.assertTrue(restarted.queue.empty())

    @unittest.skipUnless(HAS_ORIGINAL_MP3 and shutil.which('ffmpeg'),'Original audio fixture and FFmpeg required')
    @patch('pipeline.transcribe_elevenlabs')
    @patch('pipeline.transcribe_humain',side_effect=ProviderError('Mock provider failure'))
    def test_complete_pipeline_partial_and_cache(self, humain, eleven):
        def response(*args):
            return build_model_result('elevenlabs','ElevenLabs','أهلا',settings={},elapsed_ms=2),{'text':'أهلا'}
        eleven.side_effect=response
        manager=JobManager(self.s,start_worker=False)
        payload={'cases':[self.case()],'models':['humain','elevenlabs'],'name':'API contract test','profile':validate_profile(),'reuse_cache':True}
        j=manager.create_job(payload);manager.execute(j['job_id']);saved=load_results(self.s,j['run_id'])
        self.assertEqual(manager.get(j['job_id'])['status'],'partial')
        self.assertEqual(saved[0]['models'][0]['status'],'failed')
        self.assertEqual(saved[0]['models'][1]['status'],'success')
        j2=manager.create_job(payload);manager.execute(j2['job_id'])
        self.assertEqual(eleven.call_count,1)
        self.assertTrue(load_results(self.s,j2['run_id'])[0]['models'][1]['cache_hit'])
        self.assertTrue((self.s.data/'raw'/j['run_id']/self.case()['case_id']/'elevenlabs.json').exists())
