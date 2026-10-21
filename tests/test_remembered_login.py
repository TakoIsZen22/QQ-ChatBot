"""Windows integration: real DPAPI, disposable installation and account only."""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
from src.core.config import load,validate
from src.core.desktop_api import DesktopApi
from src.core.local_account import LocalAccount
from src.core.remembered_login import RememberedLogin


@unittest.skipUnless(os.name=='nt','Windows DPAPI integration')
class RememberedLoginTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup)
        # Windows CI TEMP can contain an 8.3 alias; stores resolve their root.
        self.root=Path(temp.name).resolve();self.cfg=load(self.root/'absent.json')
        for name,value in (('ROOT',self.root),('load',Mock(return_value=self.cfg))):
            p=patch('src.core.desktop_api.'+name,value);p.start();self.addCleanup(p.stop)
        self.password='disposable-dpapi-fixture-password'
        self.api=self.new_api()
        self.account=LocalAccount(self.root,self.cfg['account'])
        self.vault=RememberedLogin(self.root,self.cfg['account'])

    def new_api(self):
        backend=Mock();backend.port.return_value=False
        return DesktopApi(backend)

    def setup_account(self,**options):
        return self.api.account('setup',dict(username='fixture-user',password=self.password,**options))

    def test_opt_in_dpapi_and_reopen_auto_login_never_returns_password(self):
        self.setup_account()
        self.assertFalse(self.vault.path.exists())
        status=self.api.account('login',dict(username='fixture-user',password=self.password,remember_password=True,auto_login=True))
        self.assertTrue(status['remember']['auto_login'])
        for path in (self.vault.path,self.account.path,self.account.attempts):
            self.assertNotIn(self.password,path.read_text(encoding='utf-8'))
        self.assertNotIn(self.password,json.dumps(status))
        reopened=self.new_api()
        self.assertFalse(reopened.account()['authenticated'])
        result=reopened.account('resume')
        self.assertTrue(result['authenticated'])
        self.assertNotIn(self.password,json.dumps(result))
        token=reopened._session
        reopened.account('resume');self.assertEqual(token,reopened._session)
        self.assertTrue(reopened._signed_in())

    def test_lock_disables_auto_across_restart_remembered_manual_unlock_and_forget(self):
        self.setup_account(remember_password=True,auto_login=True)
        self.api.account('lock')
        reopened=self.new_api()
        status=reopened.account('resume')
        self.assertFalse(status['authenticated']);self.assertTrue(status['remember']['saved'])
        self.assertFalse(status['remember']['auto_login'])
        status=reopened.account('login',dict(username='fixture-user',password='',use_saved=True,remember_password=True,auto_login=False))
        self.assertTrue(status['authenticated'])
        attempts=self.account.attempts.read_bytes()
        reopened.account('forget')
        self.assertFalse(self.vault.path.exists())
        self.assertEqual(attempts,self.account.attempts.read_bytes())
        self.assertTrue(reopened.account()['authenticated'])
        self.assertTrue((self.root/'.runtime/account-logs/events.jsonl').exists())

    def test_revision_change_browser_lock_expiry_and_corruption_require_manual_login(self):
        self.setup_account(remember_password=True,auto_login=True)
        encrypted=self.vault.path.read_bytes()
        self.account.lock(self.api._session) # another HTTP session locks the installation
        self.assertFalse(self.new_api().account('resume')['authenticated'])
        self.api.account('login',dict(username='fixture-user',password=self.password,remember_password=True,auto_login=True))
        with patch('src.core.remembered_login.time.time',return_value=time.time()+31*86400):
            self.assertFalse(self.vault.status(self.account)['saved'])
        self.vault.path.write_text('{broken',encoding='utf-8')
        self.assertFalse(self.new_api().account('resume')['authenticated'])
        self.assertTrue(self.account.login('fixture-user',self.password))
        self.vault.path.write_bytes(encrypted) # old revision cannot revive saved credentials
        self.assertFalse(self.vault.status(self.account)['saved'])

    def test_copied_installation_and_tampered_dpapi_cannot_auto_login(self):
        import shutil
        self.setup_account(remember_password=True,auto_login=True)
        with tempfile.TemporaryDirectory() as folder:
            other=Path(folder)
            for file in (self.account.path,self.vault.path):
                target=other/file.relative_to(self.root);target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(file,target)
            self.assertIsNone(RememberedLogin(other,self.cfg['account']).read(LocalAccount(other,self.cfg['account'])))
        wrapper=json.loads(self.vault.path.read_text(encoding='utf-8'))
        wrapper['blob']='dGFtcGVyZWQ='
        self.vault.path.write_text(json.dumps(wrapper),encoding='utf-8')
        self.assertFalse(self.new_api().account('resume')['authenticated'])

    def test_password_change_revokes_saved_password_and_throttle_is_not_bypassed(self):
        self.setup_account(remember_password=True,auto_login=True)
        self.api.account('change',dict(username='fixture-new',password=self.password+'-new',current_password=self.password))
        self.assertFalse(self.vault.path.exists())
        self.assertFalse(self.new_api().account('resume')['authenticated'])
        self.api.account('login',dict(username='fixture-new',password=self.password+'-new',remember_password=True,auto_login=True))
        for _ in range(self.cfg['account']['max_failures']):
            with self.assertRaises(PermissionError):self.account.login('fixture-new','incorrect-fixture-password')
        before=self.account.attempts.read_bytes()
        reopened=self.new_api()
        self.assertFalse(reopened.account('resume')['authenticated'])
        self.assertFalse(self.vault.path.exists())
        self.assertEqual(before,self.account.attempts.read_bytes())
        self.assertFalse(reopened.account('resume')['authenticated'])

    def test_encrypt_failure_does_not_fail_successful_login_or_expose_inputs(self):
        self.setup_account()
        with patch('src.core.remembered_login._dpapi',side_effect=ValueError('fixture')):
            result=self.api.account('login',dict(username='fixture-user',password=self.password,remember_password=True,auto_login=True))
        self.assertTrue(result['authenticated']);self.assertTrue(result['warning'])
        self.assertFalse(result['remember']['saved'])
        self.assertNotIn(self.password,json.dumps(result))
        for fields in ({'remember_password':'true'},{'auto_login':True},{'use_saved':True}):
            with self.assertRaises(ValueError):self.api.account('login',dict(username='fixture-user',password=self.password,**fields))


class RememberPolicyTests(unittest.TestCase):
    def test_remember_days_bounds(self):
        for value in (0,91,True,'30'):
            cfg=load(Path(tempfile.gettempdir())/'absent-fixture.json');cfg['account']['remember_days']=value
            with self.subTest(value=value),self.assertRaises(ValueError):validate(cfg)

    def test_non_windows_does_not_create_plaintext_fallback(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);cfg=load(root/'absent.json');account=LocalAccount(root,cfg['account'])
            account.setup('fixture','disposable-policy-fixture-password')
            vault=RememberedLogin(root,cfg['account'])
            with patch('src.core.remembered_login.os.name','posix'):
                self.assertFalse(vault.status(account)['supported'])
                with self.assertRaises(ValueError):vault.save(account,'fixture','disposable-policy-fixture-password')
                self.assertFalse(vault.path.exists())
