import copy
import json
import stat
import tempfile
import threading
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock,patch
from src.core.config import load,merge
from src.core.onboarding import Onboarding
from src.core.runtime_downloads import checked_url,safe_zip,download
from src.core.runtime_paths import python_command
from src.core.desktop_platform import WindowsIntegration


class SetupTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.cfg=load(self.root/'absent.json');self.api=Mock();self.api._command_lock=threading.Lock()
        self.api._backend.port.return_value=False;self.setup=Onboarding(self.api)
        self.patchers=[patch('src.core.onboarding.ROOT',self.root),patch('src.core.onboarding.load',lambda:copy.deepcopy(self.cfg))]
        for p in self.patchers:p.start();self.addCleanup(p.stop)
        self.body={'owner_name':'你','owner_id':'10001','bot_id':'10002','model':{'provider':'openai_compatible','base_url':'https://example.com/v1','key_env':'FIXTURE_API_KEY','main':'fixture','auxiliary':''}}

    def test_swapped_same_account_or_secret_fields_do_not_stop_services(self):
        for change in ({'bot_id':'10001'},{'owner_id':''},{'owner_id':'１２３'},{'token':'not-an-input'}):
            with self.subTest(change=change),self.assertRaises(ValueError):self.setup.save(dict(self.body,**change))
        self.api._backend.stop_core.assert_not_called()
        bad=copy.deepcopy(self.body);bad['model']['api_key']='not-an-input'
        with self.assertRaises(ValueError):self.setup.save(bad)

    def test_save_uses_local_config_stops_old_account_and_does_not_resume(self):
        with patch('src.core.onboarding.save_local') as save:
            self.setup.save(self.body)
        self.assertEqual(save.call_args.args[0]['owner']['qq_id'],'10001')
        self.assertNotIn('safety',save.call_args.args[0]);self.api._backend.stop_qq.assert_called_once()
        self.api._backend.start_core.assert_called_once();self.assertFalse(self.api._command_lock.locked())
        self.api._backend.request.assert_not_called()

    def test_busy_configuration_or_download_keeps_config_and_pause(self):
        self.api._backend.port.return_value=True;self.api._backend.request.return_value={'busy':True}
        with patch('src.core.onboarding.save_local') as save,self.assertRaisesRegex(RuntimeError,'正在聊天'):self.setup.save(self.body)
        save.assert_not_called();self.api._backend.stop_core.assert_not_called();self.assertFalse(self.api._command_lock.locked())
        self.api._command_lock.acquire()
        with self.assertRaises(RuntimeError):self.setup.install()
        self.api._command_lock.release()

    def test_start_uses_only_native_backend_without_external_setup(self):
        merge(self.cfg,{'owner':{'qq_id':'10001'},'qq':{'bot_id':'10002','enabled':True},'model':{'main':'fixture'}})
        self.api._backend.start_qq.side_effect=RuntimeError('自写桥接尚在研发')
        with patch.object(self.setup,'status',return_value={'components':{'qq':True,'bridge':True}}),patch('src.core.onboarding.subprocess.run') as run:
            with self.assertRaisesRegex(RuntimeError,'研发'):self.setup.start()
            run.assert_not_called()
        self.assertFalse(self.api._command_lock.locked());self.api._backend.request.assert_not_called()

    def test_portable_commands_use_private_runtime(self):
        (self.root/'_runtime').mkdir();(self.root/'_runtime/python.exe').touch()
        self.assertEqual(python_command(self.root),str(self.root/'_runtime/python.exe'))
        self.assertIn('QQ ChatBot.exe',WindowsIntegration(self.root,registry=Mock()).command('--startup'))
        self.assertNotIn('.venv',WindowsIntegration(self.root,registry=Mock()).command('--startup'))

    def test_fresh_install_stays_paused_until_user_authorizes_reply(self):
        self.assertEqual(self.cfg['safety']['mode'],'paused')
        self.assertTrue(self.cfg['safety']['groups_muted']);self.assertFalse(self.cfg['qq']['enabled'])


class DownloadSafetyTests(unittest.TestCase):
    def test_private_redirect_and_untrusted_source_rejected(self):
        for url in ('http://github.com/a','https://127.0.0.1/a','https://evil.example/a','https://github.com:8000/a','https://user:password@github.com/a'):
            with self.subTest(url=url),self.assertRaises(ValueError):checked_url(url)

    def test_zip_traversal_windows_collisions_symlink_and_size_rejected_before_extract(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);archive=root/'test.zip';limits={'max_files':10,'max_unpacked_bytes':1024}
            for i,items in enumerate(([('../escape','x')],[('C:/escape','x')],[('good','x'),('GOOD','x')],[('CON.txt','x')],[('good','x'*1025)])):
                with zipfile.ZipFile(archive,'w') as z:
                    for name,data in items:z.writestr(name,data)
                with self.subTest(items=i),self.assertRaises(ValueError):safe_zip(archive,root/f'out{i}',limits)
                self.assertFalse((root/'escape').exists())
            link=zipfile.ZipInfo('link');link.external_attr=(stat.S_IFLNK|0o777)<<16
            with zipfile.ZipFile(archive,'w') as z:z.writestr(link,'../escape')
            with self.assertRaises(ValueError):safe_zip(archive,root/'links',limits)

    def test_hash_failure_removes_partial_and_never_installs(self):
        with tempfile.TemporaryDirectory() as temp:
            response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
            response.headers={};response.geturl.return_value='https://www.python.org/f.zip';response.read.side_effect=[b'wrong',b'']
            opener=Mock();opener.open.return_value=response
            with patch('src.core.runtime_downloads.urllib.request.build_opener',return_value=opener),self.assertRaisesRegex(ValueError,'SHA256'):
                download({'url':'https://www.python.org/f.zip','sha256':'0'*64,'max_bytes':10},temp)
            self.assertEqual(list(Path(temp).iterdir()),[])
