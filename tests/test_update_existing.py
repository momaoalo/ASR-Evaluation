"""Installer simulation on temporary directories; no Windows BAT execution."""
import hashlib,json,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import update_existing as up

class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=TemporaryDirectory();root=Path(self.tmp.name)
        self.src=root/'new';self.dst=root/'old';self.src.mkdir();self.dst.mkdir()
        (self.src/'app.py').write_text('new app');(self.src/'templates').mkdir();(self.src/'templates/index.html').write_text('new UI')
        (self.src/'config.py').write_text('empty keys')
        (self.dst/'app.py').write_text('old app');(self.dst/'config.py').write_text('KEEP SECRET')
        (self.dst/'data').mkdir();(self.dst/'data/case.json').write_text('KEEP DATA')
        (self.dst/'config.local.json').write_text('KEEP SETTINGS');(self.dst/'.env').write_text('KEEP ENV')
        self.manifest({'app.py':up.sha(self.src/'app.py'),'templates/index.html':up.sha(self.src/'templates/index.html')})
    def manifest(self,files): (self.src/'package_manifest.json').write_text(json.dumps({'build':up.BUILD,'files':files}))
    def tearDown(self):self.tmp.cleanup()
    def run_install(self):return up.install(self.src,self.dst,check_port=False)
    def test_preserves_all_personal_state(self):
        before={n:(self.dst/n).read_bytes() for n in ['config.py','.env','config.local.json','data/case.json']}
        r=self.run_install()
        for n,v in before.items():self.assertEqual((self.dst/n).read_bytes(),v)
        self.assertEqual((self.dst/'app.py').read_text(),'new app');self.assertEqual((Path(r['backup'])/'app.py').read_text(),'old app')
    def test_repeat_is_idempotent(self):
        self.run_install();self.assertEqual(self.run_install()['copied'],0)
    def test_rejects_running_server(self):
        with patch.object(up,'port_busy',return_value=True):
            with self.assertRaises(ValueError):up.install(self.src,self.dst)
    def test_rejects_invalid_target(self):
        with self.assertRaises(ValueError):up.install(self.src,self.dst/'missing',False)
    def test_rejects_nested_source(self):
        with self.assertRaises(ValueError):up.install(self.dst,self.dst,False)
    def test_rejects_tampered_payload(self):
        (self.src/'app.py').write_text('tampered')
        with self.assertRaises(ValueError):self.run_install()
        self.assertEqual((self.dst/'app.py').read_text(),'old app')
    def test_rejects_data_in_manifest(self):
        self.manifest({'data/case.json':'fake'})
        with self.assertRaises(ValueError):self.run_install()
    def test_rejects_traversal(self):
        self.manifest({'../secret':'fake'})
        with self.assertRaises(ValueError):self.run_install()
    def test_failure_rolls_back_code(self):
        real=up.atomic_copy
        calls=[0]
        def failing(src,dst):
            calls[0]+=1
            if calls[0]==2:raise OSError('simulated disk failure')
            return real(src,dst)
        with patch.object(up,'atomic_copy',side_effect=failing):
            with self.assertRaises(RuntimeError):self.run_install()
        self.assertEqual((self.dst/'app.py').read_text(),'old app');self.assertEqual((self.dst/'data/case.json').read_text(),'KEEP DATA')
    def test_shared_lock_is_retried(self):
        calls=[]
        def f():
            calls.append(1)
            if len(calls)<3:raise PermissionError('lock')
            return True
        with patch.object(up.time,'sleep'):self.assertTrue(up.retry(f))
        self.assertEqual(len(calls),3)
    def test_no_false_success_on_persistent_lock(self):
        with patch.object(up.time,'sleep'):
            with self.assertRaises(PermissionError):up.retry(lambda:(_ for _ in ()).throw(PermissionError('lock')))
