"""Flask integration tests. Run locally after installing requirements.txt."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
import shutil
import unittest
from config import Settings, BASE_DIR

@unittest.skipUnless(importlib.util.find_spec('flask'),'Flask is not installed in this test environment')
class WebTests(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.tmp=TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ['examples','templates','static','docs']:shutil.copytree(BASE_DIR/name,self.root/name)
        shutil.copy2(BASE_DIR/'ui_manifest.json',self.root/'ui_manifest.json')
        self.app=create_app(Settings(root=self.root),start_worker=False);self.client=self.app.test_client()
        self.token={'X-CSRF-Token':self.app.extensions['csrf']}
    def tearDown(self):self.app.extensions['jobs'].close();self.tmp.cleanup()
    def test_page(self):self.assertEqual(self.client.get('/').status_code,200)
    def test_csrf(self):self.assertEqual(self.client.post('/api/sample/score',json={}).status_code,403)
    def test_origin(self):
        r=self.client.post('/api/sample/score',json={},headers={**self.token,'Origin':'https://evil.test'})
        self.assertEqual(r.status_code,403)
    def test_sample_inspect_export(self):
        r=self.client.post('/api/sample/score',json={},headers=self.token);self.assertEqual(r.status_code,200)
        run=r.json['run_id'];summary=self.client.get('/api/results/'+run).json['summary']
        self.assertEqual(summary['successful_transcripts'],2)
        self.assertEqual(self.client.get('/api/results/'+run+'/doctor_001').status_code,200)
        report=self.client.get('/api/export/'+run);self.assertEqual(report.status_code,200)
        self.assertIn(b'Offline report',report.data);self.assertNotIn(b'xi-api-key=',report.data)
    def test_no_secret_echo(self):
        self.client.post('/api/settings',headers=self.token,json={'elevenlabs_api_key':'never-display-this'})
        response=self.client.get('/api/settings');self.assertNotIn(b'never-display-this',response.data)
    def test_unknown_path(self):self.assertEqual(self.client.get('/api/results/missing/missing').status_code,404)
    def test_missing_provider_key(self):
        sample=self.client.get('/api/sample').json
        r=self.client.post('/api/evaluate',json={'cases':[sample['case']],'models':['elevenlabs'],'consent':True},headers=self.token)
        self.assertEqual(r.status_code,400)
