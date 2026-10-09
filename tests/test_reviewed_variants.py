"""Optional policy regressions requested from the supplied Arabic example."""
import json
import random
import unittest
from pathlib import Path
from evaluation.normalizer import normalize_text, validate_profile, extract_spoken_text, VARIANTS_ID
from evaluation.evaluator import evaluate_transcription

P = validate_profile()
SPELL = {**P, 'arabic_spelling': True}
CUSTOM = {**SPELL, 'arabic_question_forms': True}
ROOT = Path(__file__).resolve().parents[1]

class ReviewedVariantTests(unittest.TestCase):
    def test_late_whitespace_change_is_logged(self):
        text='a'*120+'  b'
        n=normalize_text(text,P)
        self.assertIn('Whitespace',n['changes'])
        self.assertEqual(n['text'],'a'*120+' b')
    def test_user_three_spelling_pairs(self):
        for r,h in [('ساعة','ساعه'),('نتيجة','نتيجه'),('والاشعة','والاشعه')]:
            with self.subTest(r=r,h=h):
                e=evaluate_transcription(r,h,SPELL)
                self.assertEqual(e['metrics']['normalized']['wer'],0)
                self.assertGreater(e['metrics']['raw']['wer'],0)
                self.assertIn('Reviewed Arabic spelling',e['changes']['prediction'])
    def test_basic_profile_does_not_silently_spell_correct(self):
        self.assertGreater(evaluate_transcription('ساعة','ساعه')['metrics']['normalized']['wer'],0)
        self.assertFalse(P['arabic_spelling'])
        self.assertFalse(P['arabic_question_forms'])
    def test_conjunction_is_never_removed(self):
        e=evaluate_transcription('وصورة','صورة',CUSTOM)['metrics']['normalized']
        self.assertEqual(e['words']['counts'],{'C':0,'S':1,'D':0,'I':0})
        self.assertEqual(e['characters']['counts'],{'C':4,'S':0,'D':1,'I':0})
    def test_prefixes_remain_distinct(self):
        for r,h in [('وساعة','ساعه'),('والنتيجة','النتيجه'),('بجرعة','جرعه')]:
            with self.subTest(r=r,h=h):
                self.assertGreater(evaluate_transcription(r,h,CUSTOM)['metrics']['normalized']['wer'],0)
    def test_question_rule_requires_explicit_opt_in(self):
        self.assertGreater(evaluate_transcription('مم تشكو','مما تشكو',SPELL)['metrics']['normalized']['wer'],0)
        e=evaluate_transcription('مم تشكو','مما تشكو',CUSTOM)
        self.assertEqual(e['metrics']['normalized']['wer'],0)
        self.assertGreater(e['metrics']['raw']['wer'],0)
    def test_question_rule_is_phrase_local_not_global(self):
        for text in ['مما قال الطبيب','هذه مما قال','مما تشكون','ومما تشكو']:
            with self.subTest(text=text):
                self.assertEqual(normalize_text(text,CUSTOM)['text'],normalize_text(text,P)['text'])
    def test_unknown_final_heh_not_folded(self):
        for r,h in [('كتابة','كتابه'),('وجه','وجة'),('علية','عليه')]:
            with self.subTest(r=r,h=h):
                self.assertGreater(evaluate_transcription(r,h,CUSTOM)['metrics']['normalized']['wer'],0)
    def test_medical_and_meaning_differences_preserved(self):
        for r,h in [('5 mg','50 mg'),('لا ألم','ألم'),('يمين','يسار'),('-5','5'),('.5','5'),('سمحت','سمحتي'),('استلق','استلقي'),('BP','blood pressure')]:
            with self.subTest(r=r,h=h):
                self.assertGreater(evaluate_transcription(r,h,CUSTOM)['metrics']['normalized']['wer'],0)
    def test_spelling_does_not_override_alif_toggle(self):
        p={**SPELL,'alif':False}
        self.assertEqual(normalize_text('والأشعه',p)['text'],'والأشعة')
        self.assertEqual(normalize_text('والاشعه',p)['text'],'والاشعة')
        self.assertGreater(evaluate_transcription('والأشعة','والاشعه',p)['metrics']['normalized']['wer'],0)
    def test_english_profile_keeps_arabic_spelling(self):
        self.assertEqual(normalize_text('ساعه مما تشكو',{**CUSTOM,'language':'en'})['text'],'ساعه مما تشكو')
    def test_alias_applied_independently_and_symmetrically(self):
        for r,h in [('نتيجه','نتيجة'),('نتيجة','نتيجه'),('نتيجه','نتيجه')]:
            e=evaluate_transcription(r,h,SPELL)
            self.assertEqual(e['metrics']['normalized']['reference_text'],'نتيجة')
            self.assertEqual(e['metrics']['normalized']['prediction_text'],'نتيجة')
    def test_policy_identity_changes(self):
        ids={evaluate_transcription('ساعة','ساعه',p)['profile_id'] for p in [P,SPELL,CUSTOM]}
        self.assertEqual(len(ids),3)
        self.assertEqual(evaluate_transcription('a','a',CUSTOM)['variants_id'],VARIANTS_ID)
        self.assertIsNone(evaluate_transcription('a','a',P)['variants_id'])
    def test_source_spans_capture_canonicalized_occurrence(self):
        h='قبل مما تشكو ثم ساعه'
        e=evaluate_transcription('قبل مم تشكو ثم ساعة',h,CUSTOM)['metrics']['normalized']
        for o in e['words']['operations']:
            t=o['prediction']
            if t['text']=='مم':self.assertEqual(h[t['source_start']:t['source_end']],'مما')
            if t['text']=='ساعة':self.assertEqual(h[t['source_start']:t['source_end']],'ساعه')
    def test_example_exact_expected_scores(self):
        s=json.loads((ROOT/'examples/sample.json').read_text('utf-8'))
        r=s['case']['ground_truth'];h=s['predictions'][0]['text']
        for p,n in [(P,5),(SPELL,2),(CUSTOM,1)]:
            with self.subTest(profile=p):
                v=evaluate_transcription(r,h,p)['metrics']['normalized']
                self.assertEqual(v['words']['reference_length'],86)
                self.assertEqual(v['words']['counts']['S'],n)
                self.assertEqual(v['wer'],n/86)
        v=evaluate_transcription(r,h,CUSTOM)['metrics']['normalized']
        self.assertEqual(v['characters']['reference_length'],437)
        self.assertEqual(v['cer'],1/437)
    def test_example_second_model_not_forced_to_perfect(self):
        s=json.loads((ROOT/'examples/sample.json').read_text('utf-8'))
        h,_=extract_spoken_text(s['predictions'][1]['text'],'subtitles')
        v=evaluate_transcription(s['case']['ground_truth'],h,CUSTOM)['metrics']['normalized']
        errors=[(o['reference']['text'],o['prediction']['text']) for o in v['words']['operations'] if o['type']!='C']
        self.assertEqual(errors,[('سمحت','سمحتي'),('استلق','استلقي')])
    def test_idempotence_random_profiles_1000(self):
        rng=random.Random(7783)
        vocab=['مما','تشكو','ساعه','والأشعه','جرعه','HELLO','mg','5mL','-.٥','وصفه','نتيجه','أَلَمٌ','ﻼ','أ','1','🙂','İ','é','A\u030a']
        flags=[k for k in P if k!='language']
        for i in range(1000):
            p={**P,**{k:bool(rng.getrandbits(1)) for k in flags}}
            t=' '.join(rng.choices(vocab,k=rng.randint(0,16)))
            n=normalize_text(t,p)
            self.assertEqual(normalize_text(n['text'],p)['text'],n['text'],(repr(t),p))
            self.assertEqual(len(n['spans']),len(n['text']))
            self.assertTrue(all(0<=a<b<=len(t) for a,b in n['spans']))


class RescoreRecoveryTests(unittest.TestCase):
    def test_legacy_numeric_subtitle_is_recovered_without_asr(self):
        from tempfile import TemporaryDirectory
        from config import Settings
        from jobs import JobManager
        from storage import load_results
        from unittest.mock import patch
        raw='1\n00:00:01,000 --> 00:00:02,000\n500\nmg'
        original={'run_id':'old_run','case_id':'case_1','title':'Legacy numeric subtitle',
                  'reference':'500 mg','reference_hash':'same-reference','models':[
                    {'key':'sample','label':'Sample','status':'success','provenance':'imported',
                     'raw_text':raw,'speech_text':'mg','metadata':{'format':'subtitles'},
                     'evaluation':evaluate_transcription('500 mg','mg',P)}]}
        with TemporaryDirectory() as d:
            settings=Settings(root=Path(d));manager=JobManager(settings,start_worker=False)
            try:
                job=manager.create_job({'mode':'rescore','source_results':[original],
                                        'profile':P,'models':['sample'],'name':'Recovery'})
                with patch('jobs.run_batch') as live:
                    manager.execute(job['job_id'])
                    live.assert_not_called()
                result=load_results(settings,job['run_id'])[0]
                self.assertEqual(result['models'][0]['speech_text'],'500\nmg')
                self.assertEqual(result['models'][0]['evaluation']['metrics']['normalized']['wer'],0)
                self.assertEqual(original['models'][0]['speech_text'],'mg')
                self.assertEqual(result['models'][0]['raw_text'],raw)
            finally:manager.close()
