"""General rule coverage + deliberately documented collisions. No ASR/network."""
import json
import random
import string
import unittest
from pathlib import Path
from unittest.mock import patch
from evaluation.normalizer import normalize_text, validate_profile, DEFAULT_PROFILE
from evaluation.profiles import get_preset, profile_catalog
from evaluation.evaluator import evaluate_transcription
from evaluation.rule_based import RULE_DEFAULTS

G = get_preset('general')
C = get_preset('custom')
R = {**C, 'final_ya': True}


def canonical(s, p=G):
    return normalize_text(s, p)['text']


class RuleEngineTests(unittest.TestCase):
    def test_no_word_dictionary_is_used(self):
        with patch('evaluation.normalizer.apply_reviewed_variants', side_effect=lambda items, *_: items):
            self.assertEqual(canonical('مدرسة ومكتبة وجامعة ومزرعة'), canonical('مدرسه ومكتبه وجامعه ومزرعه'))
        self.assertFalse(G['arabic_spelling'])
        self.assertFalse(G['arabic_question_forms'])

    def test_all_alif_forms_any_position(self):
        for form in 'أإآٱٲٳٵ':
            for a, b in [('', 'مل'), ('ر', 'س'), ('بد', '')]:
                with self.subTest(form=form,a=a):
                    self.assertEqual(canonical(a+form+b), canonical(a+'ا'+b))

    def test_hamza_carriers_any_position(self):
        for form, base in [('ؤ','و'),('ئ','ي'),('ٶ','و'),('ٸ','ي')]:
            for left,right in [('','مل'),('ش','ون'),('بد','')]:
                with self.subTest(form=form,left=left):
                    self.assertEqual(canonical(left+form+right),canonical(left+base+right))

    def test_standalone_hamza_any_position(self):
        for a,b in [('','شي'),('شي',''),('سو','ال')]:
            self.assertEqual(canonical(a+'ء'+b),canonical(a+b))
        self.assertNotEqual(canonical('شيء',{**G,'standalone_hamza':False}),canonical('شي',{**G,'standalone_hamza':False}))

    def test_hamza_removal_does_not_delete_carrier_letter(self):
        self.assertEqual(canonical('سأل سؤال شاطئ'), 'سال سوال شاطي')
        self.assertNotEqual(canonical('سأل'), canonical('سل'))

    def test_precomposed_decomposed_hamza(self):
        for a,b in [('أ','ا\u0654'),('إ','ا\u0655'),('آ','ا\u0653'),('ؤ','و\u0654'),('ئ','ي\u0654')]:
            self.assertEqual(canonical('ب'+a+'ت'), canonical('ب'+b+'ت'))
        p={**G,'alif':False,'hamza_seats':False,'standalone_hamza':False}
        self.assertNotEqual(canonical('سؤل',p),canonical('سول',p))

    def test_no_combining_hamza_accidentally_removed_as_vowel(self):
        p={**G,'hamza_seats':False,'alif':False,'standalone_hamza':False}
        self.assertEqual(canonical('ب\u0654',p),'ب\u0654')
        self.assertEqual(canonical('ب\u0654',G),'ب')

    def test_tashkeel_tanwin_shadda_and_extended_marks(self):
        for mark in ['َ','ُ','ِ','ً','ٌ','ٍ','ْ','ّ','\u0670','\u08e4','\u08f0']:
            self.assertEqual(canonical('علم'+mark),canonical('علم'))
        self.assertEqual(canonical('شكرًا'),canonical('شكراً'))

    def test_diacritics_are_optional(self):
        self.assertNotEqual(canonical('عَلَم',{**G,'diacritics':False}),canonical('عِلْم',{**G,'diacritics':False}))

    def test_latin_accents_are_not_arabic_diacritics(self):
        self.assertNotEqual(canonical('résumé'),canonical('resume'))
        self.assertEqual(canonical('cafe\u0301'),canonical('café'))

    def test_ta_marbuta_rule_is_terminal(self):
        self.assertEqual(canonical('مكتبة، جامعة!'),canonical('مكتبه جامعه'))
        self.assertNotEqual(canonical('ةب'),canonical('هب'))
        p={**G,'punctuation':False,'diacritics':False}
        self.assertEqual(canonical('مدرسةٌ،',p),canonical('مدرسهٌ،',p))

    def test_suffix_not_on_alphanumeric_identifier(self):
        for a,b in [('xمدرسة','xمدرسه'),('مدرسة2','مدرسه2'),('_مدرسة','_مدرسه')]:
            self.assertNotEqual(canonical(a),canonical(b))

    def test_final_open_ta_requires_custom(self):
        self.assertNotEqual(canonical('قوة'),canonical('قوت'))
        self.assertEqual(canonical('قوة',C),canonical('قوت',C))
        self.assertNotEqual(canonical('تبدأ',C),canonical('هبدأ',C))

    def test_feminine_ti_rule_no_lexicon(self):
        for a,b in [('انكسرتِ','انكسرتي'),('كتبْتِ','كتبتي'),('سمحتِ','سمحتي'),('ذهبْتِ','ذهبتي')]:
            with self.subTest(a=a):
                self.assertEqual(canonical(a,C),canonical(b,C))
                self.assertNotEqual(canonical(a,G),canonical(b,G))

    def test_kasra_and_unvowelled_already_match(self):
        self.assertEqual(canonical('انكسرتِ'),canonical('انكسرت'))

    def test_not_every_yeh_is_kasra(self):
        self.assertNotEqual(canonical('كتابي',G),canonical('كتاب',G))
        self.assertNotEqual(canonical('كتابي',C),canonical('كتاب',C))
        self.assertEqual(canonical('كتابي',R),canonical('كتاب',R))
        self.assertEqual(canonical('استلقي',R),canonical('استلق',R))
        self.assertNotEqual(canonical('في',R),canonical('ف',R))
        self.assertNotEqual(canonical('علي',R),canonical('عل',R))

    def test_repeated_final_yeh_stable(self):
        self.assertEqual(canonical('انكسرتيي',C),canonical('انكسرت',C))
        self.assertEqual(canonical('كتابيى',R),canonical('كتاب',R))
        self.assertEqual(canonical(canonical('كتابيى',R),R),canonical('كتابيى',R))

    def test_all_final_letters_are_reached_after_deleted_hamza(self):
        self.assertEqual(canonical('مدرسةء',G),canonical('مدرسه',G))

    def test_keyboard_variants_and_maksura(self):
        for a,b in [('کبير','كبير'),('یوم','يوم'),('مستشفى','مستشفي'),('هنا','ہنا')]:
            self.assertEqual(canonical(a),canonical(b))
        self.assertNotEqual(canonical('پ',G),canonical('ب',G))
        self.assertNotEqual(canonical('ڤ',G),canonical('ف',G))

    def test_arabic_presentation_forms(self):
        for a,b in [('سﻼم','سلام'),('ﻷن','لان'),('ﻤﺩﺭﺴﺔ','مدرسة')]:
            self.assertEqual(canonical(a),canonical(b))

    def test_fullwidth_ascii_only(self):
        self.assertEqual(canonical('ＰＡＴＩＥＮＴ ５．０'),canonical('patient 5.0'))
        self.assertNotEqual(canonical('m²'),canonical('m2'))
        self.assertNotEqual(canonical('½'),canonical('1/2'))

    def test_arabic_joiners_only(self):
        self.assertEqual(canonical('ال\u200d\u200cطبيب'),canonical('الطبيب'))
        self.assertNotEqual(canonical('ab\u200dcd'),canonical('abcd'))
        self.assertEqual(canonical('👩\u200d⚕️'), '👩\u200d⚕️')
        self.assertEqual(canonical('hello\u200bworld'),'hello world')

    def test_english_profile_does_not_rewrite_arabic(self):
        p=get_preset('custom','en')
        self.assertEqual(canonical('مدرسة انكسرتي كَلام',p),'مدرسة انكسرتي كَلام')
        self.assertEqual(canonical('PATIENT',p),'patient')

    def test_english_case_all_positions(self):
        self.assertEqual(canonical('PATIENT PaTiEnT patient'), 'patient patient patient')
        self.assertEqual(canonical('I AM IN THE HOSPITAL'), 'i am in the hospital')

    def test_units_are_explicit_choice(self):
        self.assertEqual(canonical('5 mL'), canonical('5 ml'))
        p={**G,'preserve_units':True}
        self.assertNotEqual(canonical('5 mL',p),canonical('5 ml',p))
        self.assertEqual(canonical('HELLO',p),'hello')

    def test_typographic_apostrophe_not_negation_removal(self):
        self.assertEqual(canonical('DON’T'),canonical("don't"))
        self.assertNotEqual(canonical("don't"),canonical('do'))
        self.assertNotEqual(canonical("don't"),canonical('do not'))

    def test_arbitrary_typos_are_not_guessed(self):
        for a,b in [('patient','paitent'),('مدرسة','مرسة'),('color','colour'),('مسؤول','مسئول')]:
            self.assertNotEqual(canonical(a),canonical(b))

    def test_semantic_differences_still_present_except_declared_collisions(self):
        for a,b in [('لا ألم','ألم'),('وصورة','صورة'),('5 mg','50 mg'),('-5','5'),('.5','5'),('5 mg','5 g'),('mg/dL','mg dL'),('يمين','يسار'),('pain','no pain'),('سأل','سل')]:
            for p in (G,C,R):
                with self.subTest(a=a,p=p):
                    self.assertNotEqual(canonical(a,p),canonical(b,p))

    def test_known_collisions_are_visible_not_claimed_correct(self):
        for a,b,p in [('كرة','كره',G),('على','علي',G),('سأل','سال',G),('قوة','قوت',C),('بيتي','بيت',C),('كتابي','كتاب',R)]:
            e=evaluate_transcription(a,b,p)
            self.assertEqual(e['metrics']['normalized']['wer'],0)
            self.assertGreater(e['metrics']['raw']['wer'],0)
            self.assertTrue(e['warnings'])
            self.assertEqual(set(e['metrics']), {'raw', 'normalized'})

    def test_pair_independent_normalization(self):
        fixed='مدرسة وانكسرتي'
        normal=canonical(fixed,C)
        for h in ['مدرسه وانكسرت','كلمة مختلفة','النص']:
            e=evaluate_transcription(fixed,h,C)
            self.assertEqual(e['metrics']['normalized']['reference_text'],normal)

    def test_metrics_and_suffix_source_offsets(self):
        original='قالت انكسرتي اليوم'
        e=evaluate_transcription('قالت انكسرتِ اليوم',original,C)
        self.assertEqual(e['metrics']['normalized']['wer'],0)
        op=e['metrics']['normalized']['words']['operations'][1]['prediction']
        self.assertEqual(original[op['source_start']:op['source_end']],'انكسرتي')

    def test_api_profile_validation_and_catalog(self):
        for bad in [{'final_ta':'true'},{'x':True},{'language':'fr'}]:
            with self.assertRaises(ValueError): validate_profile(bad)
        cat=profile_catalog()
        self.assertEqual(cat['default'],'cleaning')
        self.assertEqual(set(cat['modes']), {'raw', 'normalized'})
        cat['cleaning_profile']['final_ya']=False
        self.assertTrue(profile_catalog()['cleaning_profile']['final_ya'])

    def test_policy_identity_changes(self):
        ids={evaluate_transcription('مدرسة','مدرسه',p)['profile_id'] for p in (G,C,R)}
        self.assertEqual(len(ids),3)

    def test_generated_unseen_words_2000(self):
        rng=random.Random(1337)
        alphabet='بجدحخرزسشصضطظعغفقكلمنو'
        for _ in range(2000):
            stem=''.join(rng.choices(alphabet,k=rng.randint(3,12)))
            self.assertEqual(canonical(stem+'ة'),canonical(stem+'ه'))
            self.assertEqual(canonical(stem+'ة',C),canonical(stem+'ت',C))
            self.assertEqual(canonical(stem+'تِ',C),canonical(stem+'تي',C))

    def test_random_idempotence_and_source_spans_2500(self):
        rng=random.Random(8310)
        vocab=['مدرسة','قوة','قوت','انكسرتي','بيتي','استلقي','شيء','شَأن','سؤال','رأس','شاطئ','ﻼ','مستشفى','کبير','یوم','مكتبه','رأ\u0654س','س\u200d\u200cلام','Ⓐ','ＰＡＴＩＥＮＴ','İ','m²','٠٫٥','5mL','mg/dL','👩\u200d⚕️','é','a\u030a','-5','مما','تشكو']
        flags=[k for k in DEFAULT_PROFILE if k!='language']
        for _ in range(2500):
            p={**DEFAULT_PROFILE,**{k:bool(rng.getrandbits(1)) for k in flags}}
            p['language']=rng.choice(['ar','en','mixed'])
            text=rng.choice([' ', '\n', ', ', '،']).join(rng.choices(vocab,k=rng.randint(1,12)))
            n=normalize_text(text,p)
            self.assertEqual(normalize_text(n['text'],p)['text'],n['text'],(text,p,n['text']))
            self.assertEqual(len(n['spans']),len(n['text']))
            self.assertTrue(all(0<=a<b<=len(text) for a,b in n['spans']))

    def test_long_joiner_sequence(self):
        self.assertEqual(canonical('مدر'+'\u200d'*10000+'سة'),canonical('مدرسة'))


if __name__ == '__main__':
    unittest.main()
