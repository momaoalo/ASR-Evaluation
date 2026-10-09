"""Full-folder delivery and old-data migration regressions. No provider calls."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import hashlib
import json
import unittest
import import_old_data
from import_old_data import import_state, file_hash
from config import BASE_DIR
from ui_integrity import verify_ui_files, UI_BUILD


class ImportOldDataTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.old = self.root/'old'; self.new = self.root/'asr-evaluator'
        for p in (self.old, self.new):
            p.mkdir(); (p/'app.py').write_text('# app')
        (self.old/'data/jobs').mkdir(parents=True)
        (self.old/'data/results/run_1').mkdir(parents=True)
        (self.old/'data/jobs/run_1.json').write_text('{"run_id":"run_1"}')
        (self.old/'data/results/run_1/case_1.json').write_text('{"text":"اختبار"}',encoding='utf-8')
        (self.new/'app.py').write_text('# NEW CODE')
    def tearDown(self): self.temp.cleanup()
    def test_copy_complete_data_without_old_code(self):
        (self.old/'static').mkdir(); (self.old/'static/old.js').write_text('old')
        report=import_state(self.old,self.new)
        self.assertEqual(report['saved_run_files'],1);self.assertEqual(report['saved_case_files'],1)
        self.assertEqual((self.new/'app.py').read_text(),'# NEW CODE')
        self.assertFalse((self.new/'static').exists())
        for p in (self.old/'data').rglob('*.json'):
            self.assertEqual(file_hash(p),file_hash(self.new/p.relative_to(self.old)))
    def test_key_file_and_env_are_copied_without_printing(self):
        original=b'{"elevenlabs_api_key":"TEST_ONLY_CREDENTIAL"}'
        (self.old/'config.local.json').write_bytes(original)
        (self.old/'.env').write_bytes(b'HUMAIN_API_KEY=TEST_ONLY_ENV\n')
        report=import_state(self.old,self.new)
        self.assertEqual((self.new/'config.local.json').read_bytes(),original)
        self.assertEqual((self.old/'.env').read_bytes(),(self.new/'.env').read_bytes())
        self.assertNotIn('TEST_ONLY',json.dumps(report))
    def test_repeat_is_safe(self):
        import_state(self.old,self.new)
        self.assertEqual(import_state(self.old,self.new)['copied_files'],0)
    def test_collision_stops_before_any_copy(self):
        (self.new/'data/jobs').mkdir(parents=True)
        (self.new/'data/jobs/run_1.json').write_text('new-result')
        with self.assertRaises(ValueError):import_state(self.old,self.new)
        self.assertEqual((self.new/'data/jobs/run_1.json').read_text(),'new-result')
        self.assertFalse((self.new/'data/results').exists())
    def test_old_config_is_not_executed(self):
        (self.old/'config.py').write_text('raise RuntimeError("DO NOT EXECUTE")\nELEVENLABS_API_KEY="TEST_LITERAL_KEY"\n')
        import_state(self.old,self.new)
        self.assertEqual(json.loads((self.new/'config.local.json').read_text())['elevenlabs_api_key'],'TEST_LITERAL_KEY')
    def test_literal_keys_keep_original_precedence(self):
        (self.old/'config.local.json').write_text('{"elevenlabs_api_key":"TEST_JSON", "humain_api_url":"https://example.invalid"}')
        (self.old/'config.py').write_text('ELEVENLABS_API_KEY="TEST_CODE"\nHUMAIN_API_KEY=""\n')
        import_state(self.old,self.new)
        saved=json.loads((self.new/'config.local.json').read_text())
        self.assertEqual(saved['elevenlabs_api_key'],'TEST_CODE')
        self.assertEqual(saved['humain_api_url'],'https://example.invalid')
    def test_bom_key_file(self):
        (self.old/'config.local.json').write_text('{"elevenlabs_api_key":"TEST"}',encoding='utf-8-sig')
        import_state(self.old,self.new)
        self.assertEqual((self.old/'config.local.json').read_bytes(),(self.new/'config.local.json').read_bytes())
    def test_bad_json_is_rejected(self):
        (self.old/'config.local.json').write_text('{broken')
        with self.assertRaises(ValueError):import_state(self.old,self.new)
        self.assertFalse((self.new/'data').exists())
    def test_non_object_json_is_rejected(self):
        (self.old/'config.local.json').write_text('[]')
        with self.assertRaises(ValueError):import_state(self.old,self.new)
    def test_same_or_nested_folders_rejected(self):
        for dest in [self.old,self.old/'child',self.root]:
            with self.assertRaises(ValueError):import_state(self.old,dest)
    def test_no_old_project_rejected(self):
        (self.old/'app.py').unlink()
        with self.assertRaises(ValueError):import_state(self.old,self.new)
    def test_links_rejected(self):
        (self.old/'data/link').symlink_to(self.old/'app.py')
        with self.assertRaises(ValueError):import_state(self.old,self.new)
    def test_source_unchanged(self):
        before={str(p.relative_to(self.old)):file_hash(p) for p in self.old.rglob('*') if p.is_file()}
        import_state(self.old,self.new)
        after={str(p.relative_to(self.old)):file_hash(p) for p in self.old.rglob('*') if p.is_file()}
        self.assertEqual(before,after)
    def test_failed_commit_rolls_back_new_files(self):
        original=import_old_data.shutil.copyfileobj
        count=[0]
        def broken(src,dst,*args,**kw):
            count[0]+=1
            if count[0]==2:raise OSError('test interrupted copy')
            return original(src,dst,*args,**kw)
        with patch.object(import_old_data.shutil,'copyfileobj',side_effect=broken):
            with self.assertRaises(OSError):import_state(self.old,self.new)
        self.assertFalse(list((self.new/'data').rglob('*.json')))
        self.assertEqual((self.new/'app.py').read_text(),'# NEW CODE')
    def test_all_essentials_present_in_release(self):
        for name in ['app.py','config.py','run_local.py','requirements.txt','import_old_data.py','verify_package.py','START_WINDOWS.bat','IMPORT_OLD_DATA.bat','examples/ground_truth.txt','templates/_workspace.html','static/js/app.js']:
            self.assertTrue((BASE_DIR/name).is_file(),name)
        # The original MP3 is optional in this public source-only release.
        audio = BASE_DIR/'examples/doctor_clip.mp3'
        if audio.is_file():
            metadata = json.loads((BASE_DIR/'examples/sample.json').read_text(encoding='utf-8'))
            self.assertEqual(hashlib.sha256(audio.read_bytes()).hexdigest(), metadata['audio']['sha256'])
        self.assertEqual(UI_BUILD,'dashboard-1.6.2')
        self.assertEqual(verify_ui_files(BASE_DIR),[])
