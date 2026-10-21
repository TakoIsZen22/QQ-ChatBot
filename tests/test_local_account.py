import asyncio
import inspect
import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import aiohttp
from aiohttp.test_utils import TestClient,TestServer
from src.core.config import load,validate
from src.core.desktop_api import DesktopApi
from src.core.local_account import LocalAccount,LoginRequired
from src.core.harness import Harness
from src.channel.local_ui import build


class AccountTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cfg=load(self.root/'absent.json')
        self.account=LocalAccount(self.root,self.cfg['account'])
        # Disposable fixture password, never a configured/default user credential.
        self.password='仅在测试临时目录使用的密码'

    def test_optional_setup_hashing_login_expiry_and_global_lock(self):
        self.assertTrue(self.account.authenticated())
        token=self.account.setup('本机用户',self.password)
        raw=self.account.path.read_text(encoding='utf-8')
        self.assertNotIn(self.password,raw)
        self.assertFalse(self.account.status()['authenticated'])
        self.assertEqual(self.account.status()['username'],'')
        second=LocalAccount(self.root,self.cfg['account'])
        other=second.login('本机用户',self.password)
        self.assertTrue(second.authenticated(token))
        with patch('src.core.local_account.time.time',return_value=time.time()+50000):self.assertFalse(second.authenticated(other))
        self.assertFalse(second.authenticated(token+'tampered'))
        second.lock(other)
        self.assertFalse(self.account.authenticated(token))
        self.assertFalse(self.account.authenticated(other))
        with self.assertRaises(PermissionError):self.account.setup('覆盖',self.password)

    def test_password_change_requires_current_password_revokes_previous_sessions(self):
        token=self.account.setup('旧名',self.password)
        with self.assertRaises(PermissionError):self.account.change(token,'wrong','新名',self.password+'new')
        new=self.account.change(token,self.password,'新名',self.password+'new')
        self.assertFalse(self.account.authenticated(token))
        self.assertEqual(self.account.status(new)['username'],'新名')
        with self.assertRaises(PermissionError):self.account.login('旧名',self.password)
        self.assertTrue(self.account.authenticated(self.account.login('新名',self.password+'new')))

    def test_rate_limit_survives_new_instance_and_does_not_extend_on_rejected_retry(self):
        self.account.setup('用户',self.password)
        wrong='disposable-incorrect-password-fixture'
        for _ in range(self.cfg['account']['max_failures']):
            with self.assertRaises(PermissionError):self.account.login('用户',wrong)
        before=self.account.attempts.read_bytes()
        second=LocalAccount(self.root,self.cfg['account'])
        with self.assertRaisesRegex(PermissionError,'秒后重试'):second.login('用户',self.password)
        self.assertEqual(before,self.account.attempts.read_bytes())
        with patch('src.core.local_account.time.time',return_value=time.time()+301):self.assertTrue(second.login('用户',self.password))
        logs=(self.root/'.runtime/account-logs/events.jsonl').read_text(encoding='utf-8')
        self.assertNotIn(self.password,logs)
        self.assertNotIn(wrong,logs)

    def test_corrupt_files_fail_closed(self):
        self.account.setup('用户',self.password)
        for content in ('{broken','{}','null','[]'):
            self.account.path.write_text(content,encoding='utf-8')
            with self.subTest(content=content),self.assertRaises(PermissionError):self.account.status()

    def test_desktop_bridge_blocks_direct_reads_and_mutations_and_preserves_emergency_pause(self):
        with patch('src.core.desktop_api.ROOT',self.root),patch('src.core.desktop_api.load',return_value=self.cfg):
            backend=Mock();backend.port.return_value=False
            api=DesktopApi(backend)
            api.account('setup',{'username':'用户','password':self.password})
            api.account('lock')
            for fn in (lambda:api.request('chat'),lambda:api.request('config',{}),lambda:api.read_data('emotion'),lambda:api.ui_state(),lambda:api.qr(),lambda:api.events(),lambda:api.maintenance('list'),lambda:api.open_target('project'),lambda:api.preferences(),lambda:api.onboarding(),lambda:api.command('start')):
                with self.subTest(fn=fn),self.assertRaises(LoginRequired):fn()
            api.request('safety',{'mode':'paused'})
            backend.request.assert_called_with('safety',{'mode':'paused'})
            with self.assertRaises(LoginRequired):api.request('safety',{'mode':'active'})
            api._recover_once();backend.start_all.assert_not_called()
            api.account('login',{'username':'用户','password':self.password})
            api.request('chat');backend.request.assert_called_with('chat',None)
            self.assertTrue(api._backend._account_token())
            self.assertEqual(inspect.getfullargspec(api.preferences).args,['self','patch'])

    def test_setup_refuses_core_without_auth_enforcement(self):
        with patch('src.core.desktop_api.ROOT',self.root),patch('src.core.desktop_api.load',return_value=self.cfg):
            backend=Mock();backend.port.return_value=True;backend.request.return_value={'old_core':True}
            api=DesktopApi(backend)
            with self.assertRaisesRegex(ValueError,'重启聊天服务'):api.account('setup',{'username':'用户','password':self.password})
            self.assertFalse(self.account.path.exists())

    def test_hide_to_tray_revokes_login_without_changing_service_or_pause(self):
        from src.core.desktop_lifecycle import DesktopLifecycle
        with patch('src.core.desktop_api.ROOT',self.root),patch('src.core.desktop_api.load',return_value=self.cfg),patch('src.core.desktop_lifecycle.load',return_value=self.cfg):
            backend=Mock();backend.port.return_value=False
            api=DesktopApi(backend);api.account('setup',{'username':'用户','password':self.password})
            token=api._session
            life=DesktopLifecycle(api);life.window=Mock()
            life._hide()
            life.window.hide.assert_called_once();life.window.evaluate_js.assert_called_once_with('location.reload()')
            self.assertFalse(self.account.authenticated(token))
            backend.request.assert_not_called();backend.stop_all.assert_not_called();backend.start_all.assert_not_called()

    def test_legacy_ui_cannot_open_private_pages_with_account_enabled(self):
        try:from src.desktop_legacy import DesktopApp
        except ModuleNotFoundError:self.skipTest('当前运行时不含备用 Tk 界面')
        self.account.setup('用户',self.password)
        with patch('src.desktop_legacy.ROOT',self.root),patch('src.desktop_legacy.load',return_value=self.cfg):
            root=Mock()
            with self.assertRaisesRegex(PermissionError,'正式桌面入口'):DesktopApp(root,Mock(),auto_start=False)
            root.title.assert_not_called()

    def test_backup_includes_private_account_but_data_restore_keeps_current_account(self):
        from tools.manage import backup,restore
        self.account.setup('用户',self.password)
        data=self.root/self.cfg['paths']['data'];data.mkdir(parents=True,exist_ok=True)
        (data/'memory.jsonl').write_text('{"content":"fixture"}\n',encoding='utf-8')
        with patch('tools.manage.ROOT',self.root):
            saved=backup(self.cfg)
            self.assertEqual((saved/'config/account.local.json').read_bytes(),self.account.path.read_bytes())
            self.account.change(self.account.login('用户',self.password),self.password,'新名',self.password+'new')
            current=self.account.path.read_bytes()
            restore(self.cfg,saved)
            self.assertEqual(self.account.path.read_bytes(),current)

    def test_policy_cannot_disable_expiry_or_limits_and_corrupt_throttle_is_not_reset(self):
        import copy
        for key,value in (('session_seconds',0),('max_failures',False),('lockout_seconds',0),('failure_window_seconds',0),('lock_on_hide','false')):
            cfg=copy.deepcopy(self.cfg);cfg['account'][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError):validate(cfg)
        self.account.setup('用户',self.password)
        self.account.attempts.write_text('{}',encoding='utf-8')
        with self.assertRaises(PermissionError):self.account.login('用户',self.password)
        self.assertEqual(self.account.attempts.read_text(encoding='utf-8'),'{}')


class AccountHttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cfg=load(self.root/'absent.json')
        self.session=aiohttp.ClientSession();self.addAsyncCleanup(self.session.close)
        with patch('src.core.harness.ROOT',self.root):self.h=Harness(self.cfg,self.session)
        self.addAsyncCleanup(self.h.close)
        self.account=LocalAccount(self.root,self.cfg['account'])
        self.password='仅用于临时HTTP验收的密码'
        self.token=self.account.setup('用户',self.password)
        self.client=TestClient(TestServer(build(self.h,asyncio.Event())))
        await self.client.start_server();self.addAsyncCleanup(self.client.close)
        self.headers={'Host':'127.0.0.1:8765','X-Harness-Local':'1'}

    async def test_private_routes_protected_but_health_and_emergency_pause_remain_available(self):
        page=await self.client.get('/',headers=self.headers)
        self.assertIn('data-account-page="login"',await page.text())
        status=await (await self.client.get('/api/status',headers=self.headers)).json()
        self.assertFalse(status['account_authenticated'])
        self.assertNotIn('model_gateway',status);self.assertNotIn('qq_bot_id',status)
        for path in ('chat','memory','diary','soul','identity','config','models','data/notifications','group-monitor','supervision'):
            response=await self.client.get('/api/'+path,headers=self.headers)
            self.assertEqual(response.status,401,path)
        for body,code in (({'mode':'active'},401),({'mode':'reply_only'},401),({'mode':'paused'},200)):
            r=await self.client.post('/api/safety',json=body,headers=self.headers);self.assertEqual(r.status,code)
        self.assertEqual(self.h.safety.mode,'paused')

    async def test_corrupt_account_cannot_expose_data_but_emergency_pause_still_works(self):
        self.account.path.write_text('null',encoding='utf-8')
        self.assertEqual((await self.client.get('/api/chat',headers=self.headers)).status,403)
        response=await self.client.post('/api/safety',json={'mode':'paused'},headers=self.headers)
        self.assertEqual(response.status,200)
        self.assertNotIn('qq_bot_id',await response.json())
        self.assertEqual(self.h.safety.mode,'paused')

    async def test_browser_cookie_and_desktop_bearer_lock_and_cross_origin(self):
        body={'username':'用户','password':self.password}
        denied=await self.client.post('/api/account/login',json=body,headers=dict(self.headers,Origin='https://other.example'))
        self.assertEqual(denied.status,403)
        response=await self.client.post('/api/account/login',json=body,headers=self.headers)
        self.assertEqual(response.status,200)
        cookie=response.cookies[LocalAccount.COOKIE]
        self.assertTrue(cookie['httponly']);self.assertEqual(cookie['samesite'],'Strict')
        self.client.session.cookie_jar.clear()  # Explicit cookie: the test Host differs from its random-port URL.
        headers=dict(self.headers,Cookie=f'{LocalAccount.COOKIE}={cookie.value}')
        self.assertEqual((await self.client.get('/api/chat',headers=headers)).status,200)
        bearer=dict(self.headers,Authorization='Bearer '+self.token)
        self.assertEqual((await self.client.get('/api/config',headers=bearer)).status,200)
        self.assertEqual((await self.client.post('/api/account/lock',json={},headers=headers)).status,200)
        self.assertEqual((await self.client.get('/api/chat',headers=bearer)).status,401)
        self.assertEqual((await self.client.get('/api/chat',headers=headers)).status,401)
        self.assertEqual((await self.client.post('/api/account/setup',json=body,headers=self.headers)).status,401)


if __name__=='__main__':unittest.main()
