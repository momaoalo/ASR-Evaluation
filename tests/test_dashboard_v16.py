"""Dashboard regressions. Fixtures are synthetic; no live ASR requests."""
import copy, csv, io, json, unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from config import Settings, BASE_DIR
from tests.test_overview import case, jobs_for
from storage import save_result, load_result, digest, ResultIndex, write_json
from evaluation.dashboard import build_dashboard
from evaluation.overview import compact_case
from evaluation.report_metadata import audio_identity
from reporting import csv_results, export_overview_report, public_case
from reporting_review import save_review, load_reviews, rescore_reference


def fixture(run='run_a', **kwargs):
    c=case(run=run, **kwargs)
    c['source']={'type':'upload','upload_id':'upload_'+run}
    return c

class DashboardTests(unittest.TestCase):
    def summary(self,cs,**kw):return build_dashboard(cs,jobs_for(cs),**kw)
    def test_all_attempts_are_visible(self):
        cs=[fixture('run_a'),fixture('run_b',audio='run_a')]
        s=self.summary(cs)
        self.assertEqual(len(s['audio_cases']),2);self.assertEqual(s['successful_transcripts'],4)
    def test_audio_count_independent_of_reference(self):
        cs=[fixture('run_a',audio='same'),fixture('run_b',audio='same',ref='different reference')]
        s=self.summary(cs);self.assertEqual(s['audio_input_count'],1);self.assertEqual(s['duration'],60)
    def test_whitespace_reference_does_not_create_new_pair_case(self):
        cs=[fixture('run_a',audio='same'),fixture('run_b',audio='same',ref='one two three\n')]
        self.assertEqual(self.summary(cs)['matched_cases'],1)
    def test_different_raw_reference_stays_different(self):
        cs=[fixture('run_a',audio='same'),fixture('run_b',audio='same',ref='one two three.')]
        self.assertEqual(self.summary(cs,view='raw')['matched_cases'],2)
    def test_shared_scored_reference_with_cleaning(self):
        cs=[fixture('run_a',audio='same'),fixture('run_b',audio='same',ref='one two three.')]
        self.assertEqual(self.summary(cs)['matched_cases'],1)
    def test_no_audio_is_not_unique_recording(self):
        c=fixture();c.pop('audio');c['models']=[];c['error']={'message':'media failed'}
        s=self.summary([c]);self.assertEqual(s['audio_input_count'],0);self.assertEqual(s['media_unavailable_cases'],1)
    def test_same_title_is_not_same_audio(self):
        cs=[fixture('run_a'),fixture('run_b')]
        cs[1]['title']=cs[0]['title'];self.assertEqual(self.summary(cs)['audio_input_count'],2)
    def test_sample_lineage_groups_original_and_prepared(self):
        a=fixture('run_a');b=fixture('run_b');a['source']=b['source']={'type':'sample'}
        a['source_metadata']=b['source_metadata']={'video_id':'abcdefghijk','clip_start':0,'clip_end':60}
        self.assertEqual(self.summary([a,b])['audio_input_count'],1)
    def test_crop_interval_matters(self):
        a=fixture('run_a');b=fixture('run_b');a['source']=b['source']={'type':'sample'}
        b['crop']={'start':5,'end':20};self.assertEqual(self.summary([a,b])['audio_input_count'],2)
    def test_failed_old_config_does_not_zero_live_pair(self):
        a=fixture();old=fixture('run_old',b=None)
        old['models'][1].pop('request_settings');s=self.summary([a,old])
        self.assertEqual(s['matched_cases'],1);self.assertEqual(len(s['comparison']['keys']),2)
    def test_imported_does_not_block_live_pair(self):
        cs=[fixture(),fixture('run_imported',origin='imported')]
        s=self.summary(cs);self.assertEqual(s['matched_cases'],1)
        self.assertTrue(all(m['origin']=='live' for m in s['comparison']['models']))
    def test_same_subset_for_unequal_coverage(self):
        cs=[fixture('run_a'),fixture('run_b',b=None)]
        s=self.summary(cs);self.assertEqual(s['matched_cases'],1)
        self.assertTrue(all(m['reference_words']==3 for m in s['comparison']['models']))
    def test_latest_failure_never_uses_old_success(self):
        cs=[fixture('run_a',audio='same'),fixture('run_b',audio='same',b=None,when='2026-09-16T12:00:00+00:00')]
        s=self.summary(cs);self.assertEqual(s['matched_cases'],0)
    def test_new_unknown_failure_blocks_old_success(self):
        cs=[fixture('run_a',audio='same'),fixture('run_b',audio='same',b=None,when='2026-09-16T12:00:00+00:00')]
        cs[1]['models'][1].pop('request_settings');s=self.summary(cs)
        self.assertEqual(s['matched_cases'],0)
    def test_one_model_no_paired_winner(self):
        c=fixture();c['models']=c['models'][:1];s=self.summary([c]);self.assertEqual(s['matched_cases'],0);self.assertIsNone(s['best'])
    def test_wer_over_100_retained(self):
        s=self.summary([fixture(ref='a',a='a b c d',b='a')]);self.assertEqual(s['comparison']['models'][0]['wer'],3)
    def test_weighted_not_mean(self):
        cs=[fixture('run_a',ref='a '*10,a='b '+'a '*9,b='a '*10),fixture('run_b',ref='a '*100,a='b '*50+'a '*50,b='a '*100)]
        self.assertAlmostEqual(self.summary(cs)['comparison']['models'][0]['wer'],51/110)
    def test_flag_is_not_automatic_exclusion(self):
        c=fixture(ref='one two three four five six seven eight nine ten',a='a b c d e f g h i j',b='a b c d e f g h i j')
        s=self.summary([c]);self.assertEqual(s['comparison']['flagged'],1);self.assertEqual(s['matched_cases'],1);self.assertIsNone(s['best'])
    def test_confirmed_reference_releases_warning(self):
        c=fixture(ref='one two three four five six seven eight nine ten',a='a b c d e f g h i j',b='a b c d e f g h i j')
        s=self.summary([c],reviews={'run_a/case_001':{'status':'confirmed','reference_hash':c['reference_hash']}})
        self.assertEqual(s['comparison']['flagged'],0);self.assertIsNotNone(s['best'])
    def test_excluded_latest_does_not_fall_back(self):
        cs=[fixture('run_a',audio='same'),fixture('run_b',audio='same',when='2026-09-16T12:00:00+00:00')]
        s=self.summary(cs,reviews={'run_b/case_001':{'status':'excluded'}})
        self.assertEqual(s['matched_cases'],0);self.assertEqual(s['listed_case_count'],2)
    def test_changed_reference_invalidates_old_review(self):
        c=fixture();s=self.summary([c],reviews={'run_a/case_001':{'status':'excluded','reference_hash':'different'}})
        self.assertEqual(s['matched_cases'],1)
    def test_raw_and_cleaning_only(self):
        for view in ['raw','normalized']:self.assertEqual(self.summary([fixture()],view=view)['view'],view)
        with self.assertRaises(ValueError):self.summary([fixture()],view='custom')
    def test_corrupt_model_does_not_hide_other(self):
        c=fixture();c['models'][0]['evaluation']['metrics']['normalized']=[]
        s=self.summary([c]);self.assertEqual(len(s['audio_cases']),1);self.assertEqual(s['successful_transcripts'],1)
    def test_negative_or_nan_audio_is_unknown(self):
        for d in [-1,float('nan'),None]:
            c=fixture();c['audio']['duration']=d;self.assertIsNone(audio_identity(c))
    def test_no_input_mutation(self):
        cs=[fixture()];before=copy.deepcopy(cs);self.summary(cs);self.assertEqual(cs,before)
    def test_compact_retains_no_transcript_arrays(self):
        c=compact_case(fixture());self.assertNotIn('reference',c)
        self.assertNotIn('operations',c['models'][0]['evaluation']['metrics']['raw']['words'])
    def test_json_finite(self):json.dumps(self.summary([fixture()]),allow_nan=False)
    def test_csv_includes_unscored_media(self):
        c=fixture('run_bad');c['audio']={};c['models']=[];c['error']={'message':'bad file'}
        rows=list(csv.DictReader(io.StringIO(csv_results(self.summary([fixture(),c])).lstrip('\ufeff'))))
        self.assertEqual(len(rows),3);self.assertEqual(rows[-1]['wer_percent'],'')
    def test_csv_formula_neutralized(self):
        c=fixture();c['title']='=1+2';text=csv_results(self.summary([c]));self.assertIn("'=1+2",text)
    def test_search_scope_affects_all_counts(self):
        cs=[fixture('run_a'),fixture('run_b')];s=self.summary(cs,filters={'q':'run_a'})
        self.assertEqual(s['listed_case_count'],1);self.assertEqual(s['successful_transcripts'],2)
    def test_failed_only_history_still_visible(self):
        c=fixture(b=None);c['models']=c['models'][1:];s=self.summary([c])
        self.assertEqual(len(s['audio_cases']),1);self.assertEqual(s['comparison']['keys'],[])
    def test_selected_pair_preserved(self):
        cs=[fixture(),fixture('run_supplied',origin='imported')];s=self.summary(cs)
        keys=[m['key'] for m in s['models'] if m['origin']=='supplied'];p=self.summary(cs,pair_keys=keys)
        self.assertEqual(set(keys),set(p['comparison']['keys']))
    def test_export_same_scopes_two_views(self):
        cs=[fixture()];html=export_overview_report(cs,jobs_for(cs),BASE_DIR)
        self.assertIn('"comparison":',html);self.assertIn('"csv":',html);self.assertIn('dashboard-1.6.2',html)

    def test_overview_is_simplified(self):
        template=(BASE_DIR/'templates/_workspace.html').read_text('utf-8')
        overview=template.split('<div class="page hidden" id="page-new">',1)[0]
        self.assertNotIn('PINNED SAMPLE', overview)
        self.assertNotIn('Data quality &amp; failed attempts', overview)
        self.assertNotIn('All configurations &amp; historical coverage', overview)
        self.assertIn('PINNED SAMPLE', template.split('<div class="page hidden" id="page-new">',1)[1])

    def test_case_cards_own_problem_messages(self):
        js=(BASE_DIR/'static/js/app.js').read_text('utf-8')
        self.assertIn('function caseIssues(c)', js)
        self.assertIn('caseIssueMarkup(c)', js)
        self.assertIn("model.error?.message", js)
        self.assertIn("c.error?.message", js)

class ReferenceReviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();self.settings=Settings(root=Path(self.tmp.name));self.c=fixture();save_result(self.settings,self.c)
    def tearDown(self):self.tmp.cleanup()
    def test_decision_separate_from_original(self):
        before=load_result(self.settings,'run_a','case_001');save_review(self.settings,'run_a','case_001',{'status':'excluded'})
        self.assertEqual(before,load_result(self.settings,'run_a','case_001'));self.assertEqual(load_reviews(self.settings)['run_a/case_001']['status'],'excluded')
    def test_decision_validation(self):
        with self.assertRaises(ValueError):save_review(self.settings,'run_a','case_001',{'status':'pass'})
    def test_reference_correction_new_id_original_unchanged(self):
        before=load_result(self.settings,'run_a','case_001')
        j=rescore_reference(self.settings,'run_a','case_001',{'reference':'one three','confirmed':True})
        self.assertNotEqual(j['run_id'],'run_a');self.assertEqual(before,load_result(self.settings,'run_a','case_001'))
        new=load_result(self.settings,j['run_id'],'case_001');self.assertEqual(new['models'][1]['evaluation']['metrics']['raw']['wer'],0)
        self.assertEqual(load_reviews(self.settings)['run_a/case_001']['status'],'excluded')
    def test_confirmation_required(self):
        with self.assertRaises(ValueError):rescore_reference(self.settings,'run_a','case_001',{'reference':'one three'})
    def test_empty_reference_rejected(self):
        with self.assertRaises(ValueError):rescore_reference(self.settings,'run_a','case_001',{'reference':'','confirmed':True})
    def test_new_review_binds_hash(self):
        review=save_review(self.settings,'run_a','case_001',{'status':'confirmed'})
        self.assertEqual(review['reference_hash'],self.c['reference_hash'])
    def test_corrupt_review_surfaces_warning(self):
        write_json(self.settings.data/'reviews/run_a/case_001.json',{'status':'excluded'})
        (self.settings.data/'reviews/run_a/case_001.json').write_text('{broken')
        self.assertTrue(load_reviews(self.settings)['_warnings'])
