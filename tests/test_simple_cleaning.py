"""Two UI modes, one fixed cleaning ruleset; no ASR/network calls."""
import json
import unittest
from pathlib import Path
from evaluation.evaluator import evaluate_transcription
from evaluation.profiles import get_cleaning_profile, profile_catalog, validate_score_view
from evaluation.normalizer import normalize_text
from config import BASE_DIR, Settings
from pipeline import validate_request
from reporting import export_html_report

class SimpleCleaningTests(unittest.TestCase):
    def test_exactly_two_public_choices(self):
        self.assertEqual(profile_catalog()['modes'], {'normalized': 'Cleaning', 'raw': 'No cleaning'})
        self.assertNotIn('presets', profile_catalog())

    def test_fixed_agreed_rule_flags(self):
        p=get_cleaning_profile()
        for key in ['diacritics','alif','tatweel','digits','punctuation','lowercase',
                    'hamza_seats','standalone_hamza','ta_marbuta','final_ta','alif_maqsura',
                    'feminine_ti','final_ya','arabic_keyboard','arabic_joiners','fullwidth',
                    'arabic_question_forms']:
            self.assertTrue(p[key],key)
        self.assertFalse(p['arabic_spelling'])  # General rules, not a word dictionary.

    def test_only_two_scores_and_source_is_unchanged(self):
        a,b='أَلَم PATIENT','الم patient'
        e=evaluate_transcription(a,b,get_cleaning_profile())
        self.assertEqual(set(e['metrics']), {'raw','normalized'})
        self.assertGreater(e['metrics']['raw']['wer'],0)
        self.assertEqual(e['metrics']['normalized']['wer'],0)
        self.assertEqual(e['metrics']['raw']['reference_text'],a)
        self.assertEqual(e['metrics']['raw']['prediction_text'],b)

    def test_agreed_spelling_examples(self):
        for a,b in [('مدرسة','مدرسه'),('مدرسة','مدرست'),('انكسرتِ','انكسرتي'),
                    ('سمحت','سمحتي'),('استلقِ','استلقي'),('مم تشكو','مما تشكو'),
                    ('نتيجة','نتيجه'),('PATIENT','patient')]:
            with self.subTest(reference=a,prediction=b):
                e=evaluate_transcription(a,b,get_cleaning_profile())
                self.assertEqual(e['metrics']['normalized']['wer'],0)
                self.assertGreater(e['metrics']['raw']['wer'],0)

    def test_genuine_edits_still_count(self):
        for a,b in [('وصورة','صورة'),('لا ألم','ألم'),('5 mg','50 mg'),('-5','5'),('.5','5')]:
            with self.subTest(reference=a,prediction=b):
                self.assertGreater(evaluate_transcription(a,b,get_cleaning_profile())['metrics']['normalized']['wer'],0)

    def test_counts_agree_in_both_modes(self):
        e=evaluate_transcription('أهلًا وسهلًا بك','اهلا وسهلا',get_cleaning_profile())
        for v in e['metrics'].values():
            for level in ['words','characters']:
                s=v[level];c=s['counts']
                self.assertEqual(s['reference_length'],c['C']+c['S']+c['D'])
                self.assertEqual(s['prediction_length'],c['C']+c['S']+c['I'])
                self.assertEqual(s['rate'],(c['S']+c['D']+c['I'])/s['reference_length'])

    def test_no_cleaning_preserves_case_marks_and_punctuation(self):
        text='PATIENT أَلَم، 5.0!'
        self.assertEqual(normalize_text(text,get_cleaning_profile(),baseline=True)['text'],text)

    def test_modes_are_validated(self):
        for v in ['raw','normalized']:
            self.assertEqual(validate_score_view(v),v)
        for v in ['custom','general','conservative',None,True]:
            with self.assertRaises(ValueError):validate_score_view(v)

    def test_request_keeps_display_mode(self):
        item=json.loads((BASE_DIR/'examples/sample.json').read_text())['case']
        for mode in ['raw','normalized']:
            r=validate_request({'cases':[item],'models':['elevenlabs'],'consent':True,'score_view':mode},Settings())
            self.assertEqual(r['score_view'],mode)
            self.assertTrue(r['profile']['final_ya'])

    def test_export_honors_display_mode(self):
        for mode in ['raw','normalized']:
            html=export_html_report([],{'run_id':'test','score_view':mode},BASE_DIR)
            self.assertIn('"default_view": "'+mode+'"',html)
            self.assertNotIn('id="policyPreset"',html)
            self.assertIn('>No cleaning</span>',html)

    def test_catalog_does_not_mutate_fixed_rules(self):
        a=profile_catalog();a['cleaning_profile']['final_ya']=False
        self.assertTrue(get_cleaning_profile()['final_ya'])
