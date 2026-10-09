"""Metric-card regressions. No network or provider calls."""
import copy
import json
import math
import re
import unittest
from config import BASE_DIR
from evaluation.dashboard import _totals, build_dashboard
from tests.test_dashboard_v16 import fixture
from tests.test_overview import jobs_for
from reporting import export_overview_report

class ScorecardMetricsTests(unittest.TestCase):
    def summary(self, cases, **kw):
        return build_dashboard(cases,jobs_for(cases),**kw)
    def test_macro_and_corpus_are_distinct(self):
        cs=[fixture('run_short',ref='a '*10,a='b '+'a '*9,b='a '*10),
            fixture('run_long',ref='a '*100,a='b '*50+'a '*50,b='a '*100)]
        m=next(x for x in self.summary(cs)['comparison']['models'] if x['provider']=='humain')
        self.assertAlmostEqual(m['mean_case_wer'],.30)
        self.assertAlmostEqual(m['wer'],51/110)
        self.assertEqual(m['counts']['S'],51)
        self.assertEqual(m['mean_case_count'],2)
    def test_empty_totals_are_not_zero_scores(self):
        m=_totals([])
        for key in ['mean_case_wer','mean_case_cer','wer','cer']:
            self.assertIsNone(m[key])
        self.assertEqual(m['mean_case_count'],0)
    def test_failed_rows_are_not_averaged_as_zero(self):
        s=self.summary([fixture('run_a'),fixture('run_b',b=None)])
        self.assertEqual(s['comparison']['matched'],1)
        for m in s['comparison']['models']:self.assertEqual(m['mean_case_count'],1)
    def test_failed_only_has_no_pair(self):
        c=fixture()
        for m in c['models']:
            m.update(status='failed',error={'message':'test failure'});m.pop('evaluation')
        self.assertFalse(self.summary([c])['comparison']['models'])
    def test_zero_is_preserved(self):
        for m in self.summary([fixture(a='one two three',b='one two three')])['comparison']['models']:
            self.assertEqual(m['mean_case_wer'],0)
            self.assertEqual(m['mean_case_cer'],0)
            self.assertEqual(sum(m['counts'][k] for k in 'SDI'),0)
    def test_over_100_is_not_clipped(self):
        m=next(x for x in self.summary([fixture(ref='a',a='a b c d',b='a')])['comparison']['models'] if x['provider']=='humain')
        self.assertEqual(m['mean_case_wer'],3)
        self.assertEqual(m['counts']['I'],3)
    def test_last_attempt_not_all_repeats(self):
        cs=[fixture('run_old',audio='same',a='wrong wrong wrong'),
            fixture('run_new',audio='same',when='2026-09-17T10:00:00+00:00')]
        m=next(x for x in self.summary(cs)['comparison']['models'] if x['provider']=='humain')
        self.assertEqual(m['mean_case_count'],1);self.assertEqual(m['mean_case_wer'],0)
        self.assertEqual(len(self.summary(cs)['audio_cases']),2)
    def test_models_are_not_merged(self):
        ms=self.summary([fixture()])['comparison']['models']
        self.assertEqual(ms[0]['mean_case_wer'],0)
        self.assertGreater(ms[1]['mean_case_wer'],0)
    def test_cleaning_and_raw_use_their_own_counts(self):
        c=fixture(ref='HELLO WORLD',a='hello world',b='hello world',language='en')
        self.assertEqual(self.summary([c])['comparison']['models'][0]['mean_case_wer'],0)
        self.assertEqual(self.summary([c],view='raw')['comparison']['models'][0]['mean_case_wer'],1)
    def test_review_flag_keeps_scores_not_a_winner(self):
        cs=[fixture('run_bad',ref='one two three four five six seven eight',a='red blue green pink gray black white brown',b='red blue green pink gray black white brown')]
        s=self.summary(cs)
        self.assertTrue(s['comparison']['flagged']);self.assertIsNone(s['best'])
        self.assertEqual(s['comparison']['models'][0]['mean_case_wer'],1)
    def test_exclusions_apply_to_all_new_fields(self):
        cs=[fixture('run_a'),fixture('run_b')]
        rv={'run_b/case_001':{'status':'excluded'}}
        s=self.summary(cs,reviews=rv)
        self.assertEqual(s['comparison']['matched'],1)
        self.assertTrue(all(m['mean_case_count']==1 for m in s['comparison']['models']))
    def test_new_fields_match_exact_chart_rows(self):
        cs=[fixture('run_'+str(i),ref='one two three four',a='one three',b='two four') for i in range(8)]
        s=self.summary(cs)
        for m in s['comparison']['models']:
            rows=[r for r in s['chart_rows'] if r['model']==m['key']]
            self.assertAlmostEqual(m['mean_case_wer'],sum(r['wer'] for r in rows)/len(rows))
            self.assertAlmostEqual(m['mean_case_cer'],sum(r['cer'] for r in rows)/len(rows))
            for k in 'SDI':self.assertEqual(m['counts'][k],sum(r['counts'][k] for r in rows))
    def test_original_data_not_modified(self):
        cs=[fixture()];old=copy.deepcopy(cs);self.summary(cs);self.assertEqual(cs,old)
    def test_empty_reference_is_rejected_by_existing_scorer(self):
        with self.assertRaises(ValueError):fixture(ref='',a='',b='')
    def test_export_contains_computed_macro_fields_in_both_views(self):
        cs=[fixture()];html=export_overview_report(cs,jobs_for(cs),BASE_DIR)
        data=json.loads(re.search(r'id="bootstrap">(.*?)</script>',html,re.S).group(1))
        for view in ['normalized','raw']:
            self.assertIn('mean_case_cer',data['summaries'][view]['comparison']['models'][0])
        self.assertIn('Average WER',html);self.assertIn('Average CER',html)
    def test_section_order_and_native_disclosure(self):
        html=(BASE_DIR/'templates/_workspace.html').read_text('utf-8')
        self.assertLess(html.index('id="modelScorecards"'),html.index('id="chartsSection"'))
        self.assertLess(html.index('id="chartsSection"'),html.index('id="audioCasesSection"'))
        self.assertIn('<details id="chartsSection"',html)
        self.assertNotIn('<details id="chartsSection" open',html)
    def test_navigation_is_job_specific(self):
        s=(BASE_DIR/'static/js/app.js').read_text('utf-8')
        self.assertIn('async function checkFollowCompletion()',s)
        self.assertIn('!terminalStates.has(job.status)',s)
        self.assertIn('state.follow = null; persistFollow()',s)
        self.assertIn('!document.hidden',s)
        self.assertIn('disarmFollow()',s)

if __name__=='__main__':unittest.main()
