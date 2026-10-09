"""Cross-run aggregation regressions. Synthetic fixtures, no provider calls."""
import copy
import json
import math
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from config import Settings, BASE_DIR
from storage import save_result, write_json, digest, ResultIndex
from evaluation.overview import build_overview, compact_case, validate_filters
from evaluation.evaluator import evaluate_transcription
from evaluation.profiles import get_cleaning_profile
from reporting import export_overview_report


def case(run='run_a', cid='case_001', ref='one two three', a='one two three', b='one three',
         audio=None, language='ar', origin='live', when='2026-09-16T10:00:00+00:00'):
    p=get_cleaning_profile(language)
    ev=evaluate_transcription(ref,a,p)
    c={'run_id':run,'case_id':cid,'title':run+' '+language, 'reference':ref,'reference_hash':digest(ref),
       'created_at':when,'source':{'type':'sample'},'profile':p,'status':'complete',
       'normalizer_version':ev['normalizer_version'], 'unicode_database':ev['metric_policy']['unicode_database'],
       'audio':{'sha256':audio or run,'duration':60},'models':[]}
    for key,pred in [('humain',a),('elevenlabs',b)]:
        m={'key':key,'label':key.title(),'provenance':origin,'request_settings':{'model_id':key+'_v1','language':language}}
        if pred is None: m.update(status='failed',error={'message':'Test provider failure','code':'http_401'})
        else: m.update(status='success',raw_text=pred,speech_text=pred,evaluation=evaluate_transcription(ref,pred,p))
        c['models'].append(m)
    return c


def jobs_for(cases):
    return [{'run_id':r,'job_id':r,'name':r,'created_at':'2026-09-16T10:00:00+00:00','status':'complete',
             'completed':1,'total':1,'mode':'live'} for r in sorted({c['run_id'] for c in cases})]


class OverviewTests(unittest.TestCase):
    def summary(self, cs, **kwargs): return build_overview(cs,jobs_for(cs),**kwargs)
    def test_all_runs_not_latest_only(self):
        cs=[case('run_a'),case('run_b',cid='case_002')];s=self.summary(cs)
        self.assertEqual((s['run_count'],s['case_evaluations'],s['successful_transcripts']),(2,2,4))
    def test_identical_case_ids_do_not_collide(self):
        cs=[case('run_a'),case('run_b')];s=self.summary(cs)
        self.assertEqual(s['case_count'],2);self.assertEqual(len({r['case_uid'] for r in s['rows']}),2)
    def test_latest_clip_observation_only_for_corpus(self):
        cs=[case('run_a',audio='same',a='wrong wrong wrong'),case('run_b',audio='same',when='2026-09-16T11:00:00+00:00')]
        s=self.summary(cs)
        self.assertEqual(s['case_count'],1);self.assertEqual(s['earlier_attempts'],2)
        self.assertEqual(s['successful_transcripts'],4);self.assertEqual(s['included_transcripts'],2)
        self.assertEqual(next(m['wer'] for m in s['models'] if m['provider']=='humain'),0)
    def test_latest_failure_not_replaced_with_old_success(self):
        old=case('run_a',audio='same');new=case('run_b',audio='same',b=None,when='2026-09-16T11:00:00+00:00')
        s=self.summary([old,new]);m=next(m for m in s['models'] if m['provider']=='elevenlabs')
        self.assertEqual(m['successes'],0);self.assertEqual(m['failures'],1);self.assertIsNone(m['wer'])
        self.assertFalse(s['comparable'])
    def test_empty_success_is_not_provider_failure(self):
        s=self.summary([case(a='',b=None)])
        m=next(m for m in s['models'] if m['provider']=='humain')
        self.assertEqual(m['wer'],1);self.assertEqual(m['failures'],0)
    def test_failed_only_case_retains_provider(self):
        c=case();
        for m in c['models']:m.update(status='failed');m.pop('evaluation')
        s=self.summary([c]);self.assertEqual(s['failures'],2);self.assertTrue(all(m['wer'] is None for m in s['models']))
    def test_true_weighted_corpus(self):
        cs=[case('run_a',ref='a '*10,a='b '+'a '*9,b='a '*10),case('run_b',ref='a '*100,a='b '*50+'a '*50,b='a '*100)]
        s=self.summary(cs);m=next(m for m in s['models'] if m['provider']=='humain')
        self.assertAlmostEqual(m['wer'],51/110);self.assertEqual(m['reference_words'],110)
    def test_rates_over_one_not_clamped(self):
        s=self.summary([case(ref='a',a='a b c d',b='a')]);self.assertEqual(max(m['wer'] for m in s['models']),3)
    def test_same_sets_can_have_winner(self):
        s=self.summary([case()]);self.assertTrue(s['comparable']);self.assertEqual(s['best_wer'],0)
    def test_unequal_coverage_no_false_winner(self):
        s=self.summary([case('run_a'),case('run_b',b=None)]);self.assertFalse(s['comparable']);self.assertIsNone(s['best_wer'])
        self.assertTrue(any(m['wer'] is not None for m in s['models']))
    def test_running_job_blocks_winner(self):
        cs=[case()];jobs=jobs_for(cs);jobs[0]['status']='running'
        self.assertFalse(build_overview(cs,jobs)['comparable'])
    def test_model_settings_are_not_blended(self):
        a=case('run_a');b=case('run_b');b['models'][0]['request_settings']['model_id']='new_model'
        s=self.summary([a,b]);self.assertEqual(len(s['models']),3)
    def test_resolved_model_metadata_does_not_split_failure_identity(self):
        a=case('run_a',audio='x');b=case('run_b',audio='x',b=None,when='2026-09-16T11:00:00+00:00')
        a['models'][1]['request_settings']['resolved_model']='some-result-only-enum'
        s=self.summary([a,b]);self.assertEqual(len(s['models']),2)
    def test_supplied_and_live_are_separate(self):
        s=self.summary([case('run_a'),case('run_b',origin='imported')]);self.assertEqual(len(s['models']),4)
        self.assertFalse(s['comparable'])
    def test_import_slot_label_identifies_supplied_model(self):
        a=case('run_a',origin='imported');b=case('run_b',origin='imported')
        a['models'][0]['key']=b['models'][0]['key']='imported_1';b['models'][0]['label']='Different ASR'
        s=self.summary([a,b]);self.assertEqual(len(s['models']),3)
    def test_different_rules_are_not_blended(self):
        a=case('run_a');b=case('run_b')
        for m in b['models']:m['evaluation']['profile']['final_ya']=False
        s=self.summary([a,b]);self.assertEqual(s['policy_count'],2);self.assertEqual(len(s['models']),4)
    def test_different_normalizer_versions_are_separate(self):
        a=case('run_a');b=case('run_b')
        for m in b['models']:m['evaluation']['normalizer_version']='old'
        s=self.summary([a,b]);self.assertEqual(len(s['models']),4)
    def test_run_filter(self):
        s=self.summary([case('run_a'),case('run_b')],filters={'run':'run_b'})
        self.assertEqual(s['run_count'],1);self.assertTrue(all(r['run_id']=='run_b' for r in s['rows']))
    def test_language_filter(self):
        s=self.summary([case('run_ar'),case('run_en',language='en')],filters={'language':'en'})
        self.assertEqual(s['case_count'],1);self.assertEqual(len(s['models']),2)
    def test_origin_filter(self):
        s=self.summary([case('run_a'),case('run_b',origin='imported')],filters={'origin':'live'})
        self.assertEqual(s['successful_transcripts'],2)
    def test_query_changes_all_totals(self):
        s=self.summary([case('run_a'),case('run_b')],filters={'q':'run_b'})
        self.assertEqual(s['case_count'],1);self.assertEqual(len(s['chart_rows']),2)
        self.assertTrue(all(m['reference_words']==3 for m in s['models']))
    def test_model_filter_changes_cards_charts_rows(self):
        cs=[case('run_a'),case('run_b')];key=self.summary(cs)['models'][0]['key']
        s=self.summary(cs,filters={'model':key});self.assertEqual(len(s['models']),1)
        self.assertEqual(s['successful_transcripts'],2);self.assertEqual(len(s['chart_rows']),2)
    def test_no_matches_returns_real_empty_scope(self):
        s=self.summary([case()],filters={'q':'no-match'})
        self.assertEqual(s['case_count'],0);self.assertEqual(s['models'],[]);self.assertIsNone(s['best'])
    def test_model_ids_stable_between_cleaning_modes(self):
        cs=[case()];a=self.summary(cs,view='raw');b=self.summary(cs)
        self.assertEqual([m['key'] for m in a['models']],[m['key'] for m in b['models']])
    def test_invalid_saved_metrics_are_not_displayed_as_zero(self):
        c=case();c['models'][0]['evaluation']['metrics']['normalized']['wer']=float('nan')
        s=self.summary([c]);r=next(r for r in s['rows'] if r['provider_key']=='humain')
        self.assertEqual(r['status'],'invalid_result');self.assertIsNone(r['wer'])
    def test_count_mismatch_rejected(self):
        c=case();c['models'][0]['evaluation']['metrics']['normalized']['words']['counts']['C']=900
        self.assertEqual(self.summary([c])['failures'],1)
    def test_invalid_view_and_filters_rejected(self):
        for kwargs in [{'view':'other'},{'filters':{'run':'../secret'}},{'filters':{'language':'invalid'}},{'filters':{'q':'x'*201}}]:
            with self.subTest(kwargs=kwargs),self.assertRaises(ValueError):self.summary([],**kwargs)
    def test_different_reference_prevents_dedup(self):
        a=case('run_a',audio='same');b=case('run_b',audio='same',ref='changed reference')
        self.assertEqual(self.summary([a,b])['case_count'],2)
    def test_no_hash_does_not_merge_different_uploads(self):
        a=case('run_a');b=case('run_b')
        for i,c in enumerate([a,b]):c['audio']={};c['source']={'type':'upload','upload_id':str(i)}
        self.assertEqual(self.summary([a,b])['case_count'],2)
    def test_media_failure_survives(self):
        c=case();c['models']=[];c['error']={'message':'Cannot decode'};c['audio']={}
        s=self.summary([c]);self.assertEqual(s['media_failures'],1);self.assertEqual(s['failures'],0)
    def test_100_runs_same_case_id(self):
        cs=[case('run_'+str(i)) for i in range(100)];s=self.summary(cs)
        self.assertEqual(s['case_count'],100);self.assertEqual(s['successful_transcripts'],200)
    def test_inputs_are_not_mutated(self):
        cs=[case()];before=copy.deepcopy(cs);self.summary(cs);self.assertEqual(cs,before)
    def test_compact_has_no_alignment_payload(self):
        c=compact_case(case());text=json.dumps(c)
        self.assertNotIn('operations',text);self.assertNotIn('raw_text',text)
    def test_policy_and_identity_do_not_expose_keys(self):
        c=case();c['models'][0]['request_settings']['api_key']='secret-test-value'
        self.assertNotIn('secret-test-value',json.dumps(self.summary([c])))


class ResultIndexTests(unittest.TestCase):
    def setUp(self):self.tmp=TemporaryDirectory();self.s=Settings(root=Path(self.tmp.name));self.idx=ResultIndex(self.s)
    def tearDown(self):self.tmp.cleanup()
    def test_all_and_specific(self):
        save_result(self.s,case('run_a'));save_result(self.s,case('run_b'))
        self.assertEqual(len(self.idx.load()[0]),2);self.assertEqual(len(self.idx.load('run_b')[0]),1)
    def test_cached_records_not_reparsed(self):
        save_result(self.s,case());self.idx.load()
        with patch('storage.read_json',side_effect=AssertionError('Repeated JSON parse')):
            self.assertEqual(len(self.idx.load()[0]),1)
    def test_checkpoint_invalidates_cache(self):
        c=case();save_result(self.s,c);self.idx.load();c['title']='New title';save_result(self.s,c)
        self.assertEqual(self.idx.load()[0][0]['title'],'New title')
    def test_bad_json_is_reported_not_fatal(self):
        save_result(self.s,case());p=self.s.data/'results/run_bad/case_001.json';p.parent.mkdir();p.write_text('{bad')
        rows,warnings=self.idx.load();self.assertEqual(len(rows),1);self.assertEqual(len(warnings),1)
    def test_valid_json_array_is_reported_not_fatal(self):
        save_result(self.s,case());p=self.s.data/'results/run_bad/case_001.json';write_json(p,[])
        rows,warnings=self.idx.load();self.assertEqual(len(rows),1);self.assertEqual(len(warnings),1)
    def test_invalid_metric_structure_is_isolated(self):
        save_result(self.s,case());c=case('run_bad');c['models'][0]['evaluation']=['bad'];save_result(self.s,c)
        rows,warnings=self.idx.load();self.assertEqual(len(rows),2);self.assertEqual(len(warnings),1)
        bad = next(c for c in rows if c['run_id'] == 'run_bad')
        self.assertEqual(bad['models'][0]['status'], 'invalid_result')
        self.assertEqual(bad['models'][1]['status'], 'success')

    def test_invalid_metric_level_is_isolated(self):
        save_result(self.s,case());c=case('run_bad');c['models'][0]['evaluation']['metrics']['raw']=[];save_result(self.s,c)
        rows,warnings=self.idx.load();self.assertEqual(len(rows),2);self.assertEqual(len(warnings),1)
        bad = next(c for c in rows if c['run_id'] == 'run_bad')
        self.assertEqual(bad['models'][0]['status'], 'invalid_result')
        self.assertEqual(bad['models'][1]['status'], 'success')

    def test_mismatched_identity_reported(self):
        p=self.s.data/'results/run_a/case_001.json';write_json(p,case('run_b'))
        rows,warnings=self.idx.load();self.assertEqual(rows,[]);self.assertEqual(len(warnings),1)
    def test_delete_prunes_cache(self):
        save_result(self.s,case());self.idx.load();(self.s.data/'results/run_a/case_001.json').unlink()
        self.assertEqual(self.idx.load()[0],[]);self.assertEqual(self.idx._cache,{})


class OverviewExportTests(unittest.TestCase):
    def boot(self,cs,**kwargs):
        import re
        html=export_overview_report(cs,jobs_for(cs),BASE_DIR,**kwargs)
        return json.loads(re.search(r'<script type="application/json" id="bootstrap">(.*?)</script>',html,re.S).group(1)),html
    def test_exports_multiple_runs(self):
        boot,html=self.boot([case('run_a'),case('run_b')]);self.assertEqual(len(boot['cases']),2)
        self.assertEqual(boot['summaries']['normalized']['listed_case_count'],2);self.assertEqual(boot['summaries']['normalized']['audio_input_count'],1);self.assertNotIn('<script src=',html)
    def test_duplicate_case_ids_keep_run_ids(self):
        boot,_=self.boot([case('run_a'),case('run_b')]);self.assertEqual({c['run_id'] for c in boot['cases']},{'run_a','run_b'})
    def test_filter_snapshot_exact(self):
        cs=[case('run_a'),case('run_b')];boot,_=self.boot(cs,filters={'q':'run_a'})
        self.assertEqual(len(boot['cases']),1)
        self.assertTrue(all(s['case_count']==1 for s in boot['summaries'].values()))
    def test_excluded_models_not_exported(self):
        cs=[case()];key=build_overview(cs)['models'][0]['key'];boot,_=self.boot(cs,filters={'model':key})
        self.assertEqual(len(boot['cases'][0]['models']),1)
    def test_script_injection_escaped(self):
        c=case();c['reference']='</script><script>alert(1)</script>';boot,html=self.boot([c])
        self.assertNotIn(c['reference'],html)
    def test_read_warnings_retained(self):
        boot,_=self.boot([case()],read_warnings=[{'message':'unreadable'}])
        self.assertEqual(boot['summaries']['raw']['read_warnings'][0]['message'],'unreadable')


# These are genuine Flask route tests when Flask is installed, not a transport mock.
import importlib.util
import shutil
@unittest.skipUnless(importlib.util.find_spec('flask'), 'Flask unavailable in this environment')
class OverviewWebTests(unittest.TestCase):
    def setUp(self):
        from app import create_app
        self.tmp=TemporaryDirectory();self.root=Path(self.tmp.name)
        for name in ('examples','templates','static','docs'):shutil.copytree(BASE_DIR/name,self.root/name)
        self.settings=Settings(root=self.root)
        shutil.copy2(BASE_DIR/'ui_manifest.json',self.root/'ui_manifest.json')
        self.app=create_app(self.settings,start_worker=False);self.client=self.app.test_client()
        self.cs=[case('run_a'),case('run_b')]
        for c in self.cs:save_result(self.settings,c)
        for j in jobs_for(self.cs):write_json(self.settings.data/'jobs'/(j['job_id']+'.json'),j)
    def tearDown(self):self.app.extensions['jobs'].close();self.tmp.cleanup()
    def test_overview_route_all(self):
        r=self.client.get('/api/overview');self.assertEqual(r.status_code,200);self.assertEqual(r.json['summary']['run_count'],2)
    def test_scope_query(self):
        r=self.client.get('/api/overview?run=run_b');self.assertEqual(r.json['summary']['case_count'],1)
    def test_bad_filter_returns_400(self):self.assertEqual(self.client.get('/api/overview?language=bad').status_code,400)
    def test_missing_run_returns_404(self):self.assertEqual(self.client.get('/api/overview?run=missing').status_code,404)
    def test_export_all_static_route(self):
        r=self.client.get('/api/export/overview');self.assertEqual(r.status_code,200);self.assertIn(b'asr_overview_report.html',r.headers['Content-Disposition'].encode())
    def test_export_filtered(self):
        r=self.client.get('/api/export/overview?q=run_b');self.assertEqual(r.status_code,200)
        import re
        b=json.loads(re.search(r'<script type="application/json" id="bootstrap">(.*?)</script>',r.text,re.S).group(1))
        self.assertEqual(len(b['cases']),1);self.assertEqual(b['cases'][0]['run_id'],'run_b')
    def test_inspect_correct_run(self):
        r=self.client.get('/api/results/run_b/case_001');self.assertEqual(r.json['run_id'],'run_b')
    def test_corrupt_job_does_not_blank_overview(self):
        p=self.settings.data/'jobs/broken.json';p.write_text('{bad')
        r=self.client.get('/api/overview');self.assertEqual(r.status_code,200);self.assertEqual(len(r.json['summary']['read_warnings']),1)
    def test_corrupt_result_warning(self):
        p=self.settings.data/'results/run_a/case_001.json';p.write_text('{bad')
        r=self.client.get('/api/overview');self.assertEqual(r.status_code,200);self.assertEqual(r.json['summary']['run_count'],1)
    def test_old_single_run_endpoint_preserved(self):self.assertEqual(self.client.get('/api/results/run_a').status_code,200)
