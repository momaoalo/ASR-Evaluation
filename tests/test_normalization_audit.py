"""Regression cases from the 1.1 audit. No credentials and no external ASR calls."""
import importlib.util
import math
import random
import string
import unittest
from unittest.mock import patch
from evaluation.normalizer import (validate_profile, normalize_text, extract_spoken_text,
                                   NORMALIZER_VERSION)
from evaluation.evaluator import evaluate_transcription, aggregate_results

P = validate_profile()

# These are semantic distinctions that the default policy must NOT erase.
DISTINCT = [
    ('negative_number','-5','5'), ('leading_decimal','.5 mg','5 mg'),
    ('negative_leading_decimal','-.5','5'), ('minus_decimal','−0.5','0.5'),
    ('positive_sign','+5','5'), ('range','5-10','510'),
    ('ratio','5/10','510'), ('unit_slash','mg/dL','mg dL'),
    ('unit_difference','5 mg','5 g'), ('dose_tenfold','5 mg','50 mg'),
    ('decimal_zero','0.5','05'), ('decimal_leading_zero','.5','0.5'),
    ('arabic_decimal','٫٥','٥'), ('arabic_minus','-٥','٥'),
    ('thousands_not_guessed','1,000','1000'), ('comma_decimal_not_guessed','0,5','0.5'),
    ('exponent_sign','1e-5','1e5'), ('squared','m²','m2'),
    ('fraction_not_expanded','½','1/2'), ('micro_not_milli','µg','mg'),
    ('percent','5%','5'), ('comparison_lt','<5','5'), ('comparison_gt','>5','5'),
    ('plusminus','±5','5'), ('negation_ar','لا ألم','ألم'),
    ('negation_en','no chest pain','chest pain'), ('side_ar','يمين','يسار'),
    ('side_en','left','right'), ('positive_negative','positive','negative'),
    ('unit_case_default','5 mL','5 ml'), ('temperature','37°C','37°F'),
    ('ta_marbuta','ساعة','ساعه'), ('alif_maqsura','مستشفى','مستشفي'),
    ('hamza_seat','سؤال','سوال'), ('not_translation','ألم','pain'),
    ('not_synonyms','سعيد','مسرور'), ('numbers_not_expanded','خمسة','5'),
    ('english_numbers_not_expanded','five','5'), ('abbreviation_not_expanded','BP','blood pressure'),
    ('contraction_not_expanded',"don't",'do not'), ('dialect_not_rewritten','ما عندي','ليس لدي'),
    ('technical_parentheses','(5)','5'), ('technical_square','[5]','5'),
    ('emoji_kept','pain 😢','pain'), ('joiner_kept','می\u200cروم','میروم'),
]
EQUIVALENT = [
    ('spaces','  hello\tworld\r\n','hello world'),
    ('bidi_marks','\u200fألم\u200e','ألم'), ('bom','\ufeffhello','hello'),
    ('zero_width_boundary','hello\u200bworld','hello world'),
    ('soft_hyphen','anti\u00adbody','antibody'),
    ('alif_forms','أ إ آ ٱ','ا ا ا ا'), ('vowel_marks','أَلَمٌ شَدِيدٌ','الم شديد'),
    ('tatweel','ســلام','سلام'), ('digits_ar','٠١٢٣٤٥٦٧٨٩','0123456789'),
    ('digits_farsi','۰۱۲۳۴۵۶۷۸۹','0123456789'),
    ('decimal_ar','٥٫٠ mg','5.0 mg'), ('thousands_glyph','١٬٠٠٠','1,000'),
    ('percent_ar','٥٪','5%'), ('unicode_minus','−5','-5'),
    ('hyphen_glyph','well‐known','well-known'), ('arabic_ligature','سﻼم','سلام'),
    ('curly_apostrophe','don’t',"don't"), ('nfc_latin','cafe\u0301','café'),
    ('nfc_hamza','ا\u0654لم','ألم'), ('hangul_nfc','\u1100\u1161\u11a8','각'),
    ('mixed','أشعر pain ٥ mg','اشعر pain 5 mg'),
    ('sentence_punctuation','hello, world!','hello world'),
]

class NormalizationRegressionTests(unittest.TestCase):
    pass

def distinct_test(a,b):
    def test(self):
        e=evaluate_transcription(a,b)['metrics']['normalized']
        self.assertGreater(e['wer'],0)
        self.assertGreater(e['cer'],0)
    return test

def equivalent_test(a,b):
    def test(self):
        e=evaluate_transcription(a,b)['metrics']['normalized']
        self.assertEqual((e['wer'],e['cer']),(0,0))
    return test
for name,a,b in DISTINCT:
    setattr(NormalizationRegressionTests,'test_preserve_'+name,distinct_test(a,b))
for name,a,b in EQUIVALENT:
    setattr(NormalizationRegressionTests,'test_equivalent_'+name,equivalent_test(a,b))

class BoundaryAndSubtitleTests(unittest.TestCase):
    def test_srt_numeric_speech_not_removed(self):
        text='1\n00:00:01,000 --> 00:00:02,000\n500\n\n2\n00:00:02,000 --> 00:00:03,000\nmg'
        self.assertEqual(extract_spoken_text(text,'subtitles')[0],'500\nmg')
    def test_vtt_short_timestamps_and_tags(self):
        text='WEBVTT\n\nNOTE source\nignore me\n\ncue-1\n00:01.000 --> 00:02.000 align:start\n<v Doctor><b>500</b> mg &amp; water</v>\n'
        self.assertEqual(extract_spoken_text(text,'subtitles')[0],'500 mg & water')
    def test_plain_numeric_text_never_removed(self):
        t='500\nmg';self.assertEqual(extract_spoken_text(t,'plain')[0],t)
    def test_subtitle_mode_without_timing_conservative(self):
        t='500\nmg';self.assertEqual(extract_spoken_text(t,'subtitles')[0],t)
    def test_numeric_line_and_unknown_bracket_kept(self):
        t='00:00:01,000 --> 00:00:02,000 [Speaker 0]\n[يسعل] 5\n[allergic to nuts]'
        self.assertEqual(extract_spoken_text(t,'subtitles')[0],'5\n[allergic to nuts]')
    def test_plain_srt_warns_not_silently_stripped(self):
        t='00:00:01,000 --> 00:00:02,000\nhi'
        e=evaluate_transcription('hi',t);self.assertTrue(e['warnings']);self.assertGreater(e['metrics']['normalized']['wer'],0)
    def test_replacement_character_warns(self):
        self.assertTrue(evaluate_transcription('hello','hel\ufffdlo')['warnings'])
    def test_unsegmented_script_warns(self):
        e=evaluate_transcription('你好','您好');self.assertTrue(e['warnings']);self.assertEqual(e['metrics']['normalized']['cer'],.5)
    def test_plain_markup_not_deleted(self):
        e=evaluate_transcription('hi','<b>hi</b>');self.assertTrue(e['warnings']);self.assertGreater(e['metrics']['normalized']['wer'],0)
    def test_invalid_types(self):
        for r,h in [(None,'a'),('a',None),(1,'a'),('a',{}),([],[])]:
            with self.subTest(r=r,h=h),self.assertRaises(ValueError):evaluate_transcription(r,h)
    def test_invalid_unicode_rejected(self):
        for s in ['a\x00b','a\ud800b','a\x08b']:
            with self.subTest(s=repr(s)),self.assertRaises(ValueError):evaluate_transcription(s,'ab')
    def test_length_limit_no_truncation(self):
        with self.assertRaises(ValueError):evaluate_transcription('a'*50001,'a')
    def test_empty_reference_no_fabricated_zero(self):
        for r in ['', ' \t\r\n', '!!!', 'َُِ']:
            with self.subTest(r=r),self.assertRaises(ValueError):evaluate_transcription(r,'a')
    def test_units_casefold_protected(self):
        p={**P,'lowercase':True}
        for a,b in [('5mL','5ml'),('5 mL','5 ml'),('5 MG','5 mg'),('µg','µG'),('mg/dL','mg/dl')]:
            with self.subTest(a=a,b=b):
                self.assertGreater(evaluate_transcription(a,b,p)['metrics']['normalized']['wer'],0)
    def test_casefold_switch(self):
        self.assertEqual(normalize_text('HELLO', {**P,'lowercase':True})['text'],'hello')
        self.assertNotEqual(normalize_text('HELLO',P)['text'],'hello')
    def test_normalization_switches(self):
        for setting,a,b in [('alif','ألم','الم'),('diacritics','سَلَم','سلم'),('digits','٥','5'),('punctuation','hello!','hello'),('tatweel','سـلام','سلام')]:
            with self.subTest(setting=setting):
                e=evaluate_transcription(a,b,{**P,setting:False})['metrics']['normalized'];self.assertGreater(e['wer'],0)
    def test_arabic_rules_not_forced_in_english_profile(self):
        self.assertEqual(normalize_text('أَلَمٌ', {**P,'language':'en'})['text'],'أَلَمٌ')
    def test_raw_text_never_mutated(self):
        r='أَلَمٌ  ٥٫٠';before=r;e=evaluate_transcription(r,'ألم 5.0')
        self.assertEqual(r,before);self.assertGreater(e['metrics']['raw']['wer'],0)
    def test_mapping_every_character_including_ligatures(self):
        for text in ['سﻼم', 'أَلَمٌ  شديد', 'A\u200e\u030A', 'don’t', '٥٫٠', 'hello\u200bworld', '🙂 مرحبا']:
            n=normalize_text(text,P)
            self.assertEqual(len(n['text']),len(n['spans']))
            self.assertTrue(all(0<=s<e<=len(text) for s,e in n['spans']))
    def test_fuzz_idempotence_2000(self):
        rng=random.Random(60916)
        alphabet=list('abc ABC123٠٥-+.,:/[]أإآاةىؤئﻼَُِّـ\n\t')+['\u200e','\u200b','\u0301','\u200d','🙂']
        for i in range(2000):
            t=''.join(rng.choices(alphabet,k=rng.randint(0,70)))
            p={**P,'lowercase':bool(i%2)}
            n=normalize_text(t,p)
            self.assertEqual(normalize_text(n['text'],p)['text'],n['text'],repr(t))
            self.assertEqual(len(n['text']),len(n['spans']))
            self.assertTrue(all(0<=s<e<=len(t) for s,e in n['spans']))
    def test_cer_counts_codepoints_not_bytes(self):
        e=evaluate_transcription('😀 أ','😀 ب')['metrics']['normalized']
        self.assertEqual(e['characters']['reference_length'],3);self.assertAlmostEqual(e['cer'],1/3)


def distance(a,b):
    """Independent textbook DP, not JiWER and not RapidFuzz."""
    row=list(range(len(b)+1))
    for i,x in enumerate(a,1):
        nxt=[i]
        for j,y in enumerate(b,1):
            nxt.append(min(nxt[-1]+1,row[j]+1,row[j-1]+(x!=y)))
        row=nxt
    return row[-1]

class MathAuditTests(unittest.TestCase):
    def test_independent_multilingual_2000_pairs(self):
        rng=random.Random(61016)
        vocabulary=['a','b','لا','ألم','pain','5','.5','mg','-5','é','🩺','مِمَّ','سﻼم','ا\u0654']
        for i in range(2000):
            r=' '.join(rng.choices(vocabulary,k=rng.randint(1,10)))
            h=' '.join(rng.choices(vocabulary,k=rng.randint(0,10)))
            p={**P,'cer_spaces':bool(i%2)}
            e=evaluate_transcription(r,h,p)
            for mode in ('raw','normalized'):
                m=e['metrics'][mode]
                for level,rate_name in [('words','wer'),('characters','cer')]:
                    a=m['reference_text'];b=m['prediction_text']
                    a=a.split() if level=='words' else list(a if p['cer_spaces'] else a.replace(' ',''))
                    b=b.split() if level=='words' else list(b if p['cer_spaces'] else b.replace(' ',''))
                    counts=m[level]['counts'];expected=distance(a,b)
                    self.assertEqual(sum(counts[t] for t in 'SDI'),expected)
                    self.assertEqual(m[rate_name],expected/len(a))
                    self.assertTrue(math.isfinite(m[rate_name]))
                    ops=m[level]['operations']
                    self.assertEqual([o['ref_index'] for o in ops if o['ref_index'] is not None],list(range(len(a))))
                    self.assertEqual([o['hyp_index'] for o in ops if o['hyp_index'] is not None],list(range(len(b))))
                    for o in ops:
                        if o['type']=='C':self.assertEqual(o['reference']['text'],o['prediction']['text'])
    def test_unrounded_ratio_and_over_100(self):
        e=evaluate_transcription('a b c','a b')['metrics']['normalized']
        self.assertEqual(e['wer'],1/3)
        self.assertEqual(evaluate_transcription('a','a b c d')['metrics']['normalized']['wer'],3)
    def test_engine_token_mismatch_fails_closed(self):
        with patch('evaluation.evaluator._engine_alignment',return_value=(['wrong'],['x'],[], 'test')):
            with self.assertRaises(RuntimeError):evaluate_transcription('a','x')
    @unittest.skipUnless(importlib.util.find_spec('jiwer'), 'JiWER not installed: official-engine parity requires local dependency installation')
    def test_official_jiwer_parity(self):
        import jiwer
        for r,h in [('a b c','a c'),('سﻼم -5','.5 مرحبا'),('hello world',''),('a','a b c d')]:
            e=evaluate_transcription(r,h)
            for view in ('raw','normalized'):
                m=e['metrics'][view]
                self.assertEqual(m['wer'],jiwer.wer(m['reference_text'],m['prediction_text']))
                self.assertEqual(m['cer'],jiwer.cer(m['reference_text'],m['prediction_text']))
    def test_mixed_policy_aggregation_not_ranked(self):
        def case(cid,p):
            return {'case_id':cid,'title':cid,'reference_hash':'a','models':[{'key':'a','label':'A','status':'success','evaluation':evaluate_transcription('a','a',p)}]}
        s=aggregate_results([case('one',P),case('two',{**P,'alif':False})])
        self.assertTrue(s['comparison_blocked']);self.assertIsNone(s['best']);self.assertIsNone(s['models'][0]['wer'])
    def test_duplicate_cases_no_silent_overwrite(self):
        c={'case_id':'x','title':'x','reference_hash':'a','models':[{'key':'a','label':'A','status':'success','evaluation':evaluate_transcription('a','a')}]}
        with self.assertRaises(ValueError):aggregate_results([c,c])
