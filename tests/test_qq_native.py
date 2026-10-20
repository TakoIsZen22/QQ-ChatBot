import copy
import hashlib
import http.server
import json
import tempfile
import threading
import unittest
from pathlib import Path
from src.core.config import load
from src.core.qq_native import prepare, restore, diagnose


class NativeSetupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.package = self.root/'.runtime/qq-client/Files/versions/fixture/resources/app/package.json'
        self.package.parent.mkdir(parents=True)
        self.original = b'{"main":"./application.asar/app_launcher/index.js","version":"fixture"}'
        self.package.write_bytes(self.original)
        self.cfg = load(self.root/'absent.json')
        self.cfg['owner']['qq_id']='11111';self.cfg['qq']['bot_id']='22222'

    def test_prepare_restore_exact_original_and_prepare_again(self):
        self.assertTrue(prepare(self.root,self.cfg)['prepared'])
        entry=self.package.parent/'qq-chatbot-entry.js'
        self.assertTrue(entry.is_file())
        self.assertIn('bootstrap.js',entry.read_text())
        self.assertIn('qq_native',entry.read_text())
        self.assertTrue(prepare(self.root,self.cfg)['prepared'])
        self.assertTrue(restore(self.root)['restored'])
        self.assertEqual(self.package.read_bytes(),self.original)
        self.assertTrue(restore(self.root)['restored'])
        self.assertTrue(prepare(self.root,self.cfg)['prepared'])

    def test_update_is_never_overwritten_by_restore_or_prepare(self):
        prepare(self.root,self.cfg)
        self.package.write_text('{"main":"./new-version.js"}')
        with self.assertRaises(ValueError):prepare(self.root,self.cfg)
        with self.assertRaises(ValueError):restore(self.root)
        self.assertEqual(json.loads(self.package.read_text())['main'],'./new-version.js')

    def test_no_system_install_or_same_account(self):
        with tempfile.TemporaryDirectory() as elsewhere:
            with self.assertRaises(ValueError):prepare(Path(elsewhere),self.cfg)
        self.cfg['qq']['bot_id']='11111'
        with self.assertRaises(ValueError):prepare(self.root,self.cfg)

    def test_original_backup_tamper_is_refused(self):
        prepare(self.root,self.cfg)
        (self.root/'.runtime/qq-native/package.original.json').write_text('{}')
        with self.assertRaises(ValueError):restore(self.root)

    def test_installer_flat_layout_prepares_and_restores(self):
        # Onboarding renames QQ.exe.parent into qq-client, removing NSIS Files/.
        for pattern in ('versions/fixture/resources/app', 'resources/app'):
            with self.subTest(pattern=pattern), tempfile.TemporaryDirectory() as temp:
                root=Path(temp); package=root/'.runtime/qq-client'/pattern/'package.json'
                package.parent.mkdir(parents=True);package.write_bytes(self.original)
                self.assertTrue(prepare(root,self.cfg)['prepared'])
                self.assertTrue(restore(root)['restored'])
                self.assertEqual(package.read_bytes(),self.original)

    def test_ambiguous_client_layout_is_not_patched(self):
        other=self.root/'.runtime/qq-client/versions/fixture/resources/app/package.json'
        other.parent.mkdir(parents=True);other.write_bytes(self.original)
        with self.assertRaises(ValueError):prepare(self.root,self.cfg)
        self.assertEqual(self.package.read_bytes(),self.original)
        self.assertEqual(other.read_bytes(),self.original)

    def test_readonly_diagnosis_cannot_make_experimental_client_launchable(self):
        before=self.package.read_bytes()
        report=diagnose(self.root,self.cfg,probe=False)
        self.assertEqual(report['stage'],'client_missing')
        self.assertFalse(report['launch_available'])
        self.assertIn('real_login_and_message_acceptance_on_this_installation',report['pending'])
        self.assertFalse(report['gateway']['checked'])
        self.assertEqual(self.package.read_bytes(),before)
        self.assertFalse((self.root/'.runtime/qq-native').exists())
        (self.root/'.runtime/qq-client/Files/QQ.exe').touch()
        self.assertEqual(diagnose(self.root,self.cfg,probe=False)['stage'],'host_missing')
        prepare(self.root,self.cfg)
        report=diagnose(self.root,self.cfg,probe=False)
        self.assertTrue(report['entry']['prepared'])
        self.assertEqual(report['stage'],'host_missing')
        self.assertFalse(report['launch_available'])
        for account in ('11111','22222'):self.assertNotIn(account,json.dumps(report))

    def test_diagnosis_only_probes_status_and_filters_native_response(self):
        (self.root/'.runtime/qq-client/Files/QQ.exe').touch();prepare(self.root,self.cfg)
        requests=[]
        class Handler(http.server.BaseHTTPRequestHandler):
            payload={'status':'ok','retcode':0,'data':{'online':True,'good':True,'private':'PRIVATE_BODY'}}
            def log_message(self,*args):pass
            def do_POST(self):
                requests.append((self.path,self.headers.get('X-QQ-ChatBot'),self.rfile.read(int(self.headers['Content-Length']))))
                raw=json.dumps(self.payload).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(raw)
        with http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler) as server:
            thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
            self.addCleanup(server.shutdown)
            self.cfg['qq']['native_port']=server.server_port
            report=diagnose(self.root,self.cfg)
            self.assertEqual(report['stage'],'host_missing')
            self.assertFalse(report['launch_available'])
            self.assertNotIn('PRIVATE_BODY',json.dumps(report))
            Handler.payload={'status':'failed','retcode':1,'message':'PRIVATE_ERROR'}
            report=diagnose(self.root,self.cfg)
            self.assertEqual(report['stage'],'host_missing')
            self.assertNotIn('PRIVATE_ERROR',json.dumps(report))
            self.assertEqual(requests,[('/get_status','1',b'{}')]*2)
            server.shutdown();thread.join(timeout=2)
