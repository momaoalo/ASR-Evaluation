"""Genuine Flask test-client checks; explicitly skipped if Flask is unavailable."""
import importlib.util, json, shutil, unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from config import BASE_DIR, Settings
from storage import save_result, write_json, load_result
from tests.test_dashboard_v16 import fixture
from tests.test_overview import jobs_for

@unittest.skipUnless(importlib.util.find_spec('flask'), 'Flask unavailable; these route tests were not executed')
class DashboardRoutesTests(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.tmp=TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ['examples','templates','static','docs']:shutil.copytree(BASE_DIR/name,self.root/name)
        shutil.copy2(BASE_DIR/'ui_manifest.json',self.root/'ui_manifest.json')
        self.settings=Settings(root=self.root);self.c=fixture()
        save_result(self.settings,self.c)
        for j in jobs_for([self.c]):write_json(self.settings.data/'jobs'/(j['run_id']+'.json'),j)
        self.app=create_app(self.settings,start_worker=False);self.client=self.app.test_client()
        self.headers={'X-CSRF-Token':self.app.extensions['csrf']}
    def tearDown(self):self.app.extensions['jobs'].close();self.tmp.cleanup()
    def test_overview_paired_scope(self):
        r=self.client.get('/api/overview');self.assertEqual(r.status_code,200)
        self.assertEqual(r.json['summary']['matched_cases'],1)
    def test_review_requires_csrf(self):
        self.assertEqual(self.client.post('/api/reviews/run_a/case_001',json={'status':'excluded'}).status_code,403)
    def test_review_updates_without_mutating_results(self):
        before=load_result(self.settings,'run_a','case_001')
        r=self.client.post('/api/reviews/run_a/case_001',json={'status':'excluded'},headers=self.headers)
        self.assertEqual(r.status_code,200);self.assertEqual(before,load_result(self.settings,'run_a','case_001'))
        self.assertEqual(self.client.get('/api/overview').json['summary']['matched_cases'],0)
    def test_reference_corrects_new_run(self):
        r=self.client.post('/api/reference/run_a/case_001',json={'reference':'one three','confirmed':True},headers=self.headers)
        self.assertEqual(r.status_code,201);self.assertNotEqual(r.json['run_id'],'run_a')
    def test_reference_requires_confirmation(self):
        self.assertEqual(self.client.post('/api/reference/run_a/case_001',json={'reference':'one three'},headers=self.headers).status_code,400)
    def test_reference_unknown_case(self):
        self.assertEqual(self.client.post('/api/reference/unknown/case_001',json={'reference':'a','confirmed':True},headers=self.headers).status_code,404)
    def test_csv_and_json_endpoints(self):
        a=self.client.get('/api/export/overview.csv');self.assertEqual(a.status_code,200);self.assertIn(b'wer_percent',a.data)
        b=self.client.get('/api/export/overview.json');self.assertEqual(b.status_code,200);self.assertEqual(len(b.json['cases']),1)
    def test_export_html_contains_both_views(self):
        r=self.client.get('/api/export/overview');self.assertEqual(r.status_code,200)
        self.assertIn(b'Paired test cases',r.data);self.assertIn(b'"csv":',r.data)
    def test_inherited_sample_reference_rejected(self):
        sample=self.client.get('/api/sample').json['case']
        sample['source']={'type':'youtube','url':'https://www.youtube.com/watch?v=abcdefghijk'}
        r=self.client.post('/api/evaluate',json={'cases':[sample],'models':['elevenlabs'],'consent':True},headers=self.headers)
        self.assertEqual(r.status_code,400);self.assertIn(b'explicitly confirm',r.data)
    def test_no_secret_in_export(self):
        write_json(self.root/'config.local.json',{'elevenlabs_api_key':'PRIVATE-TEST-DO-NOT-EXPORT'})
        for url in ['/api/overview','/api/export/overview','/api/export/overview.json','/api/export/overview.csv']:
            self.assertNotIn(b'PRIVATE-TEST-DO-NOT-EXPORT',self.client.get(url).data)
