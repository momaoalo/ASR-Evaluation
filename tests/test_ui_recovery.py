"""Regression guards for the old-template/new-script failure. No live ASR calls."""
import hashlib
import json
from pathlib import Path
import re
import shutil
from tempfile import TemporaryDirectory
import unittest
from jinja2 import Environment, FileSystemLoader, select_autoescape
from config import BASE_DIR
from evaluation.profiles import profile_catalog
from ui_integrity import UI_BUILD, verify_ui_files, repair_page


class UIRecoveryTests(unittest.TestCase):
    def test_release_files_match_manifest(self):
        self.assertEqual(verify_ui_files(BASE_DIR), [])

    def test_old_template_is_rejected(self):
        with TemporaryDirectory() as d:
            root=Path(d)
            for name in ('templates','static'):
                shutil.copytree(BASE_DIR/name,root/name)
            shutil.copy2(BASE_DIR/'ui_manifest.json',root/'ui_manifest.json')
            page=root/'templates/_workspace.html'
            page.write_text(page.read_text(encoding='utf-8').replace('id="savedRunTitle"','id="oldRunTitle"'))
            self.assertTrue(any('_workspace.html' in x for x in verify_ui_files(root)))

    def test_missing_manifest_explains_repair(self):
        with TemporaryDirectory() as d:
            problems=verify_ui_files(Path(d))
            self.assertTrue(problems)
            page=repair_page(problems,Path(d))
            self.assertIn('git pull --ff-only',page)
            self.assertIn('have not been deleted',page)

    def test_actual_template_supplies_all_required_ids(self):
        env=Environment(loader=FileSystemLoader(BASE_DIR/'templates'),autoescape=select_autoescape(['html']))
        env.globals['url_for']=lambda _,filename,**kw:'/static/'+filename
        sample=json.loads((BASE_DIR/'examples/sample.json').read_text(encoding='utf-8'))
        html=env.get_template('index.html').render(boot={'offline':False,'ui_version':UI_BUILD,'sample':sample,'normalization':profile_catalog()})
        js=(BASE_DIR/'static/js/app.js').read_text(encoding='utf-8')
        ids=json.loads(re.search(r'const expectedIds = (\[.*?\]);',js).group(1))
        found=re.findall(r'id="([\w-]+)"',html)
        self.assertEqual(len(found),len(set(found)),'No duplicate IDs allowed')
        self.assertFalse(set(ids)-set(found))
        self.assertNotIn('ACTIVE RUN',html)
        self.assertNotIn('id="runSelect"',html)
        self.assertIn(sample['case']['ground_truth'],html)
        self.assertIn('id="savedRunTitle"',html)

    @unittest.skipUnless((BASE_DIR/'examples/doctor_clip.mp3').is_file(), 'Original sample audio is not redistributable in public Git checkout')
    def test_sample_audio_is_real_and_matches_reference_metadata(self):
        sample=json.loads((BASE_DIR/'examples/sample.json').read_text(encoding='utf-8'))
        audio=BASE_DIR/'examples/doctor_clip.mp3'
        self.assertEqual(hashlib.sha256(audio.read_bytes()).hexdigest(),sample['audio']['sha256'])
        self.assertTrue(sample['case']['ground_truth'].strip().endswith('شفاك الله.'))
        self.assertAlmostEqual(sample['audio']['duration'],104.352,places=2)

    def test_supplied_inputs_do_not_claim_verified_models_by_default(self):
        template=(BASE_DIR/'templates/_workspace.html').read_text(encoding='utf-8')
        self.assertIn('value="Model 1 · supplied (unverified)"',template)
        self.assertIn('value="Model 2 · supplied (unverified)"',template)

    def test_key_material_is_not_in_ui(self):
        js=(BASE_DIR/'static/js/app.js').read_text(encoding='utf-8')
        self.assertNotRegex(js,r'sk[-_][A-Za-z0-9]{20,}')
        template=(BASE_DIR/'templates/_workspace.html').read_text(encoding='utf-8')
        self.assertNotIn('data-page="connections"',template)
        self.assertNotIn('data-page="map"',template)

    def test_init_errors_are_reported_and_chart_failure_does_not_hide_list(self):
        js=(BASE_DIR/'static/js/app.js').read_text(encoding='utf-8')
        self.assertIn('init().catch',js)
        self.assertLess(js.index('renderTable(); renderSummary(); renderProgress();'),js.index('try { renderCharts(); }'))
