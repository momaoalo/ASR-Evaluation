"""Export and batch summary tests with real local evaluation; no provider calls."""
import copy
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from config import Settings, BASE_DIR
from storage import read_json
from pipeline import build_case, score_imported_case
from reporting import export_html_report, public_case
from evaluation.evaluator import aggregate_results

class ReportingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=TemporaryDirectory()
        cls.sample=read_json(BASE_DIR/'examples/sample.json')
        cls.case=build_case({**cls.sample['case'],'source':{'type':'youtube','url':cls.sample['source']['url']}},0,cls.sample['profile'])
        cls.result=score_imported_case(cls.case,cls.sample['predictions'],'test',Settings(root=Path(cls.tmp.name)),cls.sample['audio'])
    @classmethod
    def tearDownClass(cls):cls.tmp.cleanup()
    def test_export_is_standalone(self):
        report=export_html_report([self.result],{'run_id':'test'},BASE_DIR)
        self.assertIn('<svg',report)
        self.assertIn('ASRCharts',report)
        self.assertNotIn('<script src=',report)
    def test_provider_content_cannot_break_script(self):
        case=copy.deepcopy(self.result)
        case['reference']='</script><script>window.PWNED=true</script>'
        report=export_html_report([case],{'run_id':'test'},BASE_DIR)
        self.assertNotIn(case['reference'],report)
        self.assertIn('\\u003c/script\\u003e',report)
    def test_private_paths_removed(self):
        case=copy.deepcopy(self.result)
        case['audio']['artifact']='internal.wav'
        case['models'][0]['raw_response_path']='internal.json'
        clean=public_case(case)
        self.assertNotIn('artifact',clean['audio'])
        self.assertNotIn('raw_response_path',clean['models'][0])
        self.assertIn('artifact',case['audio'])
    def test_corpus_100_cases_consistent(self):
        cases=[]
        for i in range(100):
            c=copy.copy(self.result);c['case_id']=f'case_{i}';cases.append(c)
        summary=aggregate_results(cases)
        self.assertEqual(summary['matched_cases'],100)
        self.assertEqual(summary['successful_transcripts'],200)
        single=aggregate_results([self.result])
        self.assertEqual(summary['models'][0]['wer'],single['models'][0]['wer'])
    def test_media_failure_has_no_fake_transcript(self):
        summary=aggregate_results([{'case_id':'broken','title':'Broken audio','models':[], 'error':{'message':'Decode failed'}}])
        self.assertEqual(summary['media_failures'],1)
        self.assertEqual(summary['successful_transcripts'],0)
        self.assertFalse(summary['models'])

    def test_pending_selected_model_blocks_premature_ranking(self):
        case=copy.deepcopy(self.result)
        case['models']=case['models'][:1]
        summary=aggregate_results([case],expected_models=['ai_transcriber','elevenlabs'])
        self.assertEqual(len(summary['models']),2)
        self.assertEqual(summary['matched_cases'],0)
        self.assertTrue(all(m['wer'] is None for m in summary['models']))
