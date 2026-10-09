"""Deterministic metrics, normalization and position-mapping tests (no network)."""
import random
import unittest
from evaluation.evaluator import evaluate_transcription, aggregate_results
from evaluation.normalizer import normalize_text, validate_profile, extract_spoken_text

P = validate_profile()

class EvaluationTests(unittest.TestCase):
    def score(self, r, h):
        return evaluate_transcription(r,h)['metrics']['normalized']

    def test_exact(self):
        s=self.score('أنا أحب القهوة','أنا أحب القهوة')
        self.assertEqual((s['wer'],s['cer']),(0,0))
        self.assertEqual(s['words']['counts']['C'],3)

    def test_substitution(self):
        s=self.score('a b c','a x c')
        self.assertAlmostEqual(s['wer'],1/3)
        self.assertEqual(s['words']['counts'],dict(C=2,S=1,D=0,I=0))

    def test_deletion(self):
        self.assertEqual(self.score('a b c','a c')['words']['counts'],dict(C=2,S=0,D=1,I=0))

    def test_insertion(self):
        self.assertEqual(self.score('a b','a x b')['words']['counts'],dict(C=2,S=0,D=0,I=1))

    def test_empty_prediction(self):
        s=self.score('a b','');self.assertEqual(s['wer'],1);self.assertEqual(s['cer'],1)

    def test_empty_reference_rejected(self):
        with self.assertRaises(ValueError): self.score('','hello')

    def test_normalized_empty_rejected(self):
        with self.assertRaises(ValueError): self.score('!!!','a')

    def test_over_100(self):
        self.assertGreater(self.score('a','a b c d')['wer'],1)

    def test_arabic_prefix_word_vs_char(self):
        s=self.score('وصورة','صورة')
        self.assertEqual(s['words']['counts']['S'],1)
        self.assertEqual(s['characters']['counts']['D'],1)

    def test_repeated_words_use_positions(self):
        s=self.score('pain no pain','pain yes pain')
        errors=[o for o in s['words']['operations'] if o['type']!='C']
        self.assertEqual(len(errors),1);self.assertEqual(errors[0]['ref_index'],1)

    def test_raw_baseline_retained(self):
        e=evaluate_transcription('ألمٌ.','الم')
        self.assertGreater(e['metrics']['raw']['wer'],e['metrics']['normalized']['wer'])

    def test_numeric_preservation(self):
        for r,h in [('0.5 mg','5 mg'),('5 mg','50 mg'),('لا ألم','ألم'),('left arm','right arm'),('1/2','12'),('5 mg','5 g')]:
            with self.subTest(r=r):self.assertGreater(self.score(r,h)['wer'],0)

    def test_alif_optional(self):
        self.assertEqual(self.score('ألم','الم')['wer'],0)
        p={**P,'alif':False};self.assertGreater(evaluate_transcription('ألم','الم',p)['metrics']['normalized']['wer'],0)

    def test_ta_marbuta_not_folded(self):
        self.assertGreater(self.score('ساعة','ساعه')['wer'],0)

    def test_alif_maqsura_not_folded(self):
        self.assertGreater(self.score('مستشفى','مستشفي')['wer'],0)

    def test_digits(self):
        self.assertEqual(self.score('٥ mg','5 mg')['wer'],0)

    def test_mixed(self):
        self.assertEqual(self.score('أشعر pain ٥ mg','اشعر pain 5 mg')['wer'],0)

    def test_units_case_protected(self):
        p={**P,'lowercase':True}
        self.assertEqual(normalize_text('HELLO 5 mL IU',p)['text'],'hello 5 mL IU')

    def test_char_spaces_option(self):
        a=evaluate_transcription('ab cd','ab xd',P)['metrics']['normalized']['cer']
        b=evaluate_transcription('ab cd','ab xd',{**P,'cer_spaces':False})['metrics']['normalized']['cer']
        self.assertAlmostEqual(a,1/5);self.assertAlmostEqual(b,1/4)

    def test_no_model_translation(self):
        self.assertGreater(self.score('ألم','pain')['wer'],0)

    def test_mapping_with_combining_marks(self):
        text='أَلَمٌ شديد';n=normalize_text(text,P)
        self.assertEqual(n['text'],'الم شديد')
        self.assertEqual(len(n['spans']),len(n['text']))
        self.assertTrue(all(0<=s<e<=len(text) for s,e in n['spans']))

    def test_normalizer_idempotent(self):
        for t in [' أَلَمٌ  في الصدر. ','HELLO, world!','٠٫٥ mg','لا؛ تغير 50/5','hello\nthere','ســلام']:
            n=normalize_text(t,P)['text'];self.assertEqual(normalize_text(n,P)['text'],n)

    def test_subtitle_metadata_opt_in(self):
        t='00:00:01,000 --> 00:00:02,000 [Speaker 0]\n[يسعل] أهلا\nقيمة [5]'
        plain,_=extract_spoken_text(t,'plain');self.assertEqual(plain,t)
        clean,_=extract_spoken_text(t,'subtitles');self.assertNotIn('Speaker',clean);self.assertNotIn('يسعل',clean);self.assertIn('[5]',clean)

    def test_unknown_options(self):
        with self.assertRaises(ValueError):validate_profile({'surprise':True})
        with self.assertRaises(ValueError):validate_profile({'alif':'true'})

    def test_arabic_phrase_sample(self):
        self.assertEqual(self.score('لو سمحتِ','لو سمحت')['wer'],0)
        self.assertGreater(self.score('لو سمحتِ','لو سمحتي')['wer'],0)

    def test_independent_edit_distance_500_pairs(self):
        rng=random.Random(31)
        def distance(a,b):
            row=list(range(len(b)+1))
            for i,x in enumerate(a,1):
                nxt=[i]
                for j,y in enumerate(b,1):nxt.append(min(nxt[-1]+1,row[j]+1,row[j-1]+(x!=y)))
                row=nxt
            return row[-1]
        for _ in range(500):
            a=[rng.choice('abcd') for _ in range(rng.randint(1,15))]
            b=[rng.choice('abcd') for _ in range(rng.randint(0,15))]
            s=self.score(' '.join(a),' '.join(b))
            self.assertAlmostEqual(s['wer'],distance(a,b)/len(a))
            ca=list(' '.join(a));cb=list(' '.join(b));self.assertAlmostEqual(s['cer'],distance(ca,cb)/len(ca))

class AggregationTests(unittest.TestCase):
    def case(self, name, r, a, b=None):
        ms=[{'key':'a','label':'A','status':'success','evaluation':evaluate_transcription(r,a)}]
        ms.append({'key':'b','label':'B','status':'success','evaluation':evaluate_transcription(r,b)} if b is not None else {'key':'b','label':'B','status':'failed'})
        return {'case_id':name,'title':name,'reference_hash':r,'audio':{'sha256':name,'duration':1},'models':ms}

    def test_weighted_corpus(self):
        cases=[self.case('a','a '*10,'b '+'a '*9,'a '*10),self.case('b','a '*100,'b '*50+'a '*50,'a '*100)]
        result=aggregate_results(cases)
        self.assertAlmostEqual(result['models'][0]['wer'],51/110)

    def test_paired_coverage(self):
        cases=[self.case('a','x y','x y','x y'),self.case('b','x y','x z',None)]
        s=aggregate_results(cases);self.assertEqual(s['matched_cases'],1)
        self.assertEqual(s['models'][0]['wer'],0);self.assertEqual(s['models'][1]['failures'],1)

    def test_no_shared_cases_no_fake_zero(self):
        s=aggregate_results([self.case('a','x','x',None)])
        self.assertIsNone(s['models'][0]['wer']);self.assertEqual(s['matched_cases'],0)
