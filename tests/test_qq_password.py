"""QQ login fixtures. No real QQ login, credential discovery or outbound API."""
import hashlib
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
from src.core.qq_password import QQPassword
from src.core.qq_verification import official_url,open_verification
from src.core.native_host import NativeHost,atomic
from src.core.onboarding import Onboarding


class QQPasswordTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    @unittest.skipUnless(os.name=='nt','Windows DPAPI')
    def test_real_dpapi_binding_auto_disable_and_forget(self):
        cache=QQPassword(self.root,'12345');hashed=hashlib.md5(b'fixture-only').hexdigest()
        cache.save(hashed,True)
        self.assertNotIn(hashed,cache.path.read_text())
        self.assertEqual(cache.read()['hash'],hashed);self.assertTrue(cache.status()['auto'])
        self.assertIsNone(QQPassword(self.root,'99999').read())
        cache.disable_auto();self.assertFalse(cache.status()['auto'])
        cache.forget();self.assertFalse(cache.status()['saved'])

    def test_native_ipc_old_host_is_actionable_and_does_not_write_secret(self):
        host=NativeHost(self.root);host.directory.mkdir(parents=True)
        record={'run_id':'a'*32}
        atomic(host.directory/'host-config.json',record)
        with patch.object(host,'owned',return_value=record):
            with self.assertRaisesRegex(RuntimeError,'停止后重新启动'):host.login({'action':'password','password_md5':'secret'})
        self.assertFalse((host.directory/'control.json').exists())
        self.assertNotIn('secret',(host.directory/'host-config.json').read_text())

    def test_onboarding_converts_qq_password_without_model_request_or_mode_change(self):
        api=SimpleNamespace(_command_lock=threading.Lock(),_backend=Mock())
        setup=Onboarding(api);host=Mock();host.owned.return_value=True;host.login.return_value={'phase':'password_accepted'}
        cache=Mock();cfg={'qq':{'bot_id':'12345'}}
        with patch.object(setup,'_password',return_value=cache),patch('src.core.onboarding.load',return_value=cfg),patch('src.core.native_host.NativeHost',return_value=host):
            setup.password_login({'password':'fixture-secret','remember':False,'auto':False})
            sent=host.login.call_args.args[0]
            self.assertEqual(sent['password_md5'],hashlib.md5(b'fixture-secret').hexdigest())
            self.assertNotIn('fixture-secret',json.dumps(sent));api._backend.assert_not_called()
            cache.forget.assert_called_once()
            with self.assertRaises(ValueError):setup.password_login({'password':'x','remember':False,'auto':True})

    def test_no_automatic_retry_after_first_attempt_or_existing_host(self):
        setup=Onboarding(SimpleNamespace());cache=Mock();cache.read.return_value={'auto':True}
        with patch('src.core.onboarding.ROOT',self.root),patch.object(setup,'_password',return_value=cache),patch('src.core.native_host.NativeHost') as host:
            host.return_value.owned.return_value=True
            self.assertFalse(setup.password_auto()['attempted'])
            self.assertFalse(setup.password_auto()['attempted'])
            self.assertEqual(cache.read.call_count,1)

    def test_manual_service_stop_prevents_password_auto_start(self):
        from src.core.service_intent import ServiceIntent
        ServiceIntent(self.root).write(False,'manual_stop')
        setup=Onboarding(SimpleNamespace());cache=Mock()
        with patch('src.core.onboarding.ROOT',self.root),patch.object(setup,'_password',return_value=cache),patch('src.core.native_host.NativeHost') as host:
            self.assertFalse(setup.password_auto()['attempted'])
            cache.read.assert_not_called();host.assert_not_called()

    def test_manual_desktop_stop_disables_qq_auto_login(self):
        from src.core.desktop_backend import DesktopBackend
        cache=Mock();host=Mock();host.control.return_value={'message':'fixture stopped'}
        with patch('src.core.qq_password.QQPassword',return_value=cache),patch('src.core.native_host.NativeHost',return_value=host):
            self.assertEqual(DesktopBackend().stop_qq(),'fixture stopped')
            cache.disable_auto.assert_called_once();host.control.assert_called_once_with('stop')

    def test_official_verification_url_and_isolated_api(self):
        for url in ['http://qq.com/a','https://qq.com.evil.test/a','https://evil.test','https://qq.com:8443/a','https://a@qq.com/a']:
            with self.subTest(url=url),self.assertRaises(ValueError):official_url(url)
        self.assertEqual(official_url('https://accounts.qq.com/verify'),'https://accounts.qq.com/verify')
        import sys
        fake=Mock();fake.create_window.return_value=Mock()
        complete=Mock()
        with patch.dict(sys.modules,{'webview':fake}):
            open_verification({'kind':'captcha','url':'https://ssl.captcha.qq.com/test?aid=123&sid=abc'},complete)
        args=fake.create_window.call_args.kwargs
        bridge=args['js_api']
        self.assertEqual([k for k in dir(bridge) if callable(getattr(bridge,k)) and not k.startswith('_')],['submit'])
        bridge.submit('fixture-ticket','rand')
        complete.assert_called_once_with({'action':'continue','ticket':'fixture-ticket','randstr':'rand'})
        self.assertNotIn('fixture-ticket',args['html'])
        with self.assertRaises(ValueError):bridge.submit('again','rand')


if __name__=='__main__':unittest.main()
