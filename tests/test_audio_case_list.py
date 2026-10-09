"""Regression contract: Overview is always a case list; History opens one run.
External ASR calls are not used in these tests.
"""
import copy
import importlib.util
import json
import re
import shutil
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from config import Settings, BASE_DIR
from storage import ResultIndex, save_result, write_json, read_json
from evaluation.overview import build_overview, compact_case
from reporting import export_overview_report
from tests.test_overview import case, jobs_for

class AudioCaseListTests(unittest.TestCase):
    def test_one_item_per_audio_with_two_models(self):
        cs=[case('run_'+str(i)) for i in range(11)]
        s=build_overview(cs,jobs_for(cs))
        self.assertEqual(len(s['audio_cases']),11)
        self.assertEqual(len(s['rows']),22)
        self.assertTrue(all(len(c['models'])==2 for c in s['audio_cases']))
    def test_repeated_clip_not_removed_from_list(self):
        a=case('run_a',audio='same');b=case('run_b',audio='same')
        s=build_overview([a,b],jobs_for([a,b]))
        self.assertEqual(s['case_count'],1)
        self.assertEqual(len(s['audio_cases']),2)
        self.assertEqual(s['earlier_attempts'],2)
    def test_identical_titles_and_ids_have_distinct_rows(self):
        cs=[case('run_a'),case('run_b')]
        for c in cs:c['title']='At the doctor'
        s=build_overview(cs,jobs_for(cs))
        self.assertEqual({c['case_uid'] for c in s['audio_cases']},{'run_a/case_001','run_b/case_001'})
    def test_audio_case_visible_without_models(self):
        c=case();c['models']=[];c['status']='running'
        s=build_overview([c],jobs_for([c]));self.assertEqual(len(s['audio_cases']),1)
        self.assertEqual(s['audio_cases'][0]['status'],'running');self.assertEqual(s['successful_transcripts'],0)
    def test_media_failure_in_list_without_score(self):
        c=case();c['models']=[];c['error']={'message':'decode failed'}
        item=build_overview([c])['audio_cases'][0]
        self.assertEqual(item['status'],'failed');self.assertEqual(item['models'],[])
    def test_provider_failure_keeps_other_model(self):
        c=case(b=None);item=build_overview([c])['audio_cases'][0]
        self.assertEqual(item['status'],'partial');self.assertEqual(len(item['models']),2)
        self.assertIsNone(item['models'][1]['wer'])
    def test_pending_model_kept(self):
        c=case();c['models'][1]={'key':'elevenlabs','label':'ElevenLabs','status':'pending'}
        item=build_overview([c])['audio_cases'][0];self.assertEqual(item['status'],'running')
        self.assertIsNone(item['models'][1]['wer'])
    def test_bad_model_isolated_not_case(self):
        c=case();c['models'][0]['evaluation']['metrics']['normalized']=[]
        compact=compact_case(c);item=build_overview([compact])['audio_cases'][0]
        self.assertEqual(item['models'][0]['status'],'invalid_result')
        self.assertEqual(item['models'][1]['status'],'success')
    def test_both_failures_still_two_model_tiles(self):
        c=case(b=None);c['models'][0].update(status='failed');c['models'][0].pop('evaluation')
        item=build_overview([c])['audio_cases'][0]
        self.assertEqual(item['status'],'failed');self.assertEqual(len(item['models']),2)
    def test_search_limits_cases_not_individual_providers(self):
        cs=[case('run_a'),case('run_b')];s=build_overview(cs,filters={'q':'run_b'})
        self.assertEqual(len(s['audio_cases']),1);self.assertEqual(len(s['audio_cases'][0]['models']),2)
    def test_both_views_same_case_list(self):
        cs=[case('run_a'),case('run_b',b=None)]
        self.assertEqual([x['case_uid'] for x in build_overview(cs,view='raw')['audio_cases']],
                         [x['case_uid'] for x in build_overview(cs)['audio_cases']])
    def test_list_does_not_mutate_records(self):
        cs=[case('run_a'),case('run_b')];old=copy.deepcopy(cs);build_overview(cs);self.assertEqual(cs,old)
    def test_bom_json_from_windows_is_readable(self):
        with TemporaryDirectory() as d:
            p=Path(d)/'data.json';p.write_text(json.dumps({'x':1}),encoding='utf-8-sig')
            self.assertEqual(read_json(p),{'x':1})
    def test_index_retains_case_with_bad_model_and_warning(self):
        with TemporaryDirectory() as d:
            s=Settings(root=Path(d));c=case();c['models'][0]['evaluation']=['invalid'];save_result(s,c)
            cs,w=ResultIndex(s).load();self.assertEqual(len(cs),1);self.assertEqual(len(w),1)
            self.assertEqual(len(build_overview(cs)['audio_cases']),1)
    def test_export_keeps_case_with_no_models(self):
        cs=[case()];cs[0]['models']=[];cs[0]['status']='running'
        html=export_overview_report(cs,jobs_for(cs),BASE_DIR)
        boot=json.loads(re.search(r'<script type="application/json" id="bootstrap">(.*?)</script>',html,re.S).group(1))
        self.assertEqual(len(boot['cases']),1);self.assertEqual(len(boot['summaries']['raw']['audio_cases']),1)
    def test_no_run_selector_in_html(self):
        html=(BASE_DIR/'templates/_workspace.html').read_text(encoding='utf-8')
        self.assertNotIn('id="runSelect"',html);self.assertNotIn('ACTIVE RUN',html)
        self.assertNotIn('id="modelFilter"',html);self.assertIn('id="page-run"',html)
    def test_overview_query_is_always_all(self):
        js=(BASE_DIR/'static/js/app.js').read_text(encoding='utf-8')
        self.assertIn("return {run: 'all', q:",js)
        self.assertIn('await openRun(open.dataset.openRun)',js)
    def test_job_headers_include_no_sensitive_input(self):
        from jobs import JobManager
        job={'run_id':'run_q','cases':[{'case_id':'case_001','title':'Audio','ground_truth':'secret','source':{'path':'private'}}]}
        public=JobManager.public(None,job)
        self.assertEqual(public['case_headers'],[{'case_id':'case_001','title':'Audio'}])
        self.assertNotIn('secret',json.dumps(public));self.assertNotIn('private',json.dumps(public))
    def test_queued_input_cases_visible_before_checkpoint(self):
        j={'run_id':'run_q','name':'Queued','status':'queued','case_headers':[{'case_id':'c1','title':'Waiting audio'}]}
        s=build_overview([], [j]);self.assertEqual(len(s['audio_cases']),1)
        self.assertFalse(s['audio_cases'][0]['has_result']);self.assertEqual(s['successful_transcripts'],0)
    def test_checkpoint_replaces_placeholder_not_duplicate(self):
        c=case('run_q');j=jobs_for([c])[0];j['case_headers']=[{'case_id':'case_001','title':'Input'}]
        s=build_overview([c],[j]);self.assertEqual(len(s['audio_cases']),1)
        self.assertEqual(len(s['audio_cases'][0]['models']),2)
    def test_asset_cache_busting_in_template(self):
        html=(BASE_DIR/'templates/index.html').read_text(encoding='utf-8');self.assertEqual(html.count('v=asset_version'),3)

@unittest.skipUnless(importlib.util.find_spec('flask'),'Requires the installed Flask dependency')
class AudioCaseRoutesTests(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.tmp=TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ('templates','static','examples'):shutil.copytree(BASE_DIR/name,self.root/name)
        shutil.copy2(BASE_DIR/'ui_manifest.json',self.root/'ui_manifest.json')
        self.s=Settings(root=self.root);self.app=create_app(self.s,start_worker=False);self.client=self.app.test_client()
        self.cs=[case('run_a'),case('run_b',b=None)]
        for c in self.cs:save_result(self.s,c)
        for j in jobs_for(self.cs):write_json(self.s.data/'jobs'/(j['run_id']+'.json'),j)
    def tearDown(self):self.app.extensions['jobs'].close();self.tmp.cleanup()
    def test_workspace_audio_cases(self):
        r=self.client.get('/api/overview');self.assertEqual(r.status_code,200)
        self.assertEqual(len(r.json['summary']['audio_cases']),2)
    def test_open_run_lists_all_cases(self):
        r=self.client.get('/api/results/run_b');self.assertEqual(r.status_code,200)
        self.assertEqual(len(r.json['summary']['audio_cases']),1)
        self.assertEqual(r.json['summary']['audio_cases'][0]['status'],'partial')
    def test_open_run_with_missing_job_metadata(self):
        (self.s.data/'jobs/run_a.json').unlink()
        r=self.client.get('/api/results/run_a');self.assertEqual(r.status_code,200)
        self.assertTrue(r.json['job']['metadata_missing'])
    def test_open_run_with_corrupt_metrics_not_500(self):
        c=self.cs[0];c['models'][0]['evaluation']=[];save_result(self.s,c)
        r=self.client.get('/api/results/run_a');self.assertEqual(r.status_code,200)
        self.assertEqual(len(r.json['summary']['audio_cases']),1)
    def test_empty_metadata_only_run_explained(self):
        j={'job_id':'run_empty','run_id':'run_empty','name':'Empty','status':'failed','created_at':'','total':1,'completed':0}
        write_json(self.s.data/'jobs/run_empty.json',j)
        r=self.client.get('/api/results/run_empty');self.assertEqual(r.status_code,200)
        self.assertEqual(len(r.json['summary']['runs_without_results']),1)
    def test_unknown_run_not_empty_success(self):
        self.assertEqual(self.client.get('/api/results/not_here').status_code,404)
    def test_asset_version_rendered(self):
        r=self.client.get('/');self.assertEqual(r.status_code,200);self.assertIn(b'?v=',r.data)
