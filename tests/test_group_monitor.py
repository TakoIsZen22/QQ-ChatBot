import asyncio
import copy
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiohttp
from aiohttp.test_utils import TestClient, TestServer

from src.channel.local_ui import build
from src.core.config import load, validate
from src.core.desktop_api import DesktopApi
from src.core.harness import Harness
from src.core.store import Store
from src.modules.group_monitor import GroupMonitor


def event(ident='11111', message_id=1, text='群消息', **kw):
    return dict(post_type='message', message_type='group', group_id=ident, message_id=message_id,
                user_id=123, sender={'card': '<b>群成员</b>', 'user_id': 123}, time=1,
                message=[{'type': 'text', 'data': {'text': text}}], **kw)


class MonitorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.store = Store(self.temp.name)
        self.cfg = load(Path(self.temp.name) / 'absent.json')['group_monitor']
        self.cfg['groups'] = [{'group_id': '11111', 'name': '第一群', 'enabled': True},
                              {'group_id': '22222', 'name': '第二群', 'enabled': False}]
        self.monitor = GroupMonitor(self.cfg, self.store, lambda *a, **k: None)

    def test_allowlist_pause_dedup_restart_and_group_isolation(self):
        self.assertFalse(self.monitor.ingest(event('33333')))
        self.assertFalse(self.monitor.ingest(event('22222')))
        self.assertTrue(self.monitor.ingest(event()))
        self.assertFalse(self.monitor.ingest(event()))
        restarted = GroupMonitor(self.cfg, self.store, lambda *a, **k: None)
        self.assertFalse(restarted.ingest(event()))
        self.cfg['groups'][1]['enabled'] = True
        self.assertTrue(restarted.ingest(event('22222', text='另一群')))
        self.assertEqual(restarted.rows('11111')[0]['text'], '群消息')
        self.assertEqual(restarted.rows('22222')[0]['text'], '另一群')
        with self.assertRaises(PermissionError):restarted.rows('33333')
        with self.assertRaises(ValueError):restarted.rows('../owner')

    def test_media_never_downloaded_urls_and_html_are_only_text(self):
        msg = event(text='<script>alert(1)</script>')
        msg['message'] += [{'type': 'image', 'data': {'url': 'https://private.invalid/image'}},
                           {'type': 'record', 'data': {'file': 'private-audio'}},
                           {'type': 'at', 'data': {'qq': 'all'}}, {'type': 'face', 'data': {'id': '14'}},
                           {'type': 'unknown', 'data': None}]
        self.monitor.ingest(msg)
        row = self.monitor.rows('11111')[0]
        self.assertEqual(row['text'], '<script>alert(1)</script>[图片][语音]@全体成员[表情]')
        self.assertNotIn('private.invalid', self.store.path('groups/11111/monitor').read_text(encoding='utf-8'))
        self.assertEqual(len(list(Path(self.temp.name).rglob('*.*'))), 1)

    def test_limits_and_tail_multibyte_boundaries(self):
        self.cfg['history_limit'] = 2; self.cfg['max_text_chars'] = 20
        for i in range(4):self.monitor.ingest(event(message_id=i, text='鱼' * 100))
        rows = self.monitor.rows('11111');self.assertEqual(len(rows), 2)
        self.assertEqual(rows[-1]['message_id'], '3');self.assertLessEqual(len(rows[-1]['text']), 20)
        for i in range(40):self.store.append('large', text='鱼' * 3000, n=i)
        self.assertEqual([r['n'] for r in self.store.tail('large', 9)], list(range(31, 40)))
        self.assertEqual(self.store.tail('large', 100), self.store.read('large'))

    def test_invalid_configuration_is_rejected(self):
        cfg = load(Path(self.temp.name) / 'none.json')
        for groups in ([{'group_id': '../x', 'name': '', 'enabled': True}],
                       [{'group_id': '11111', 'name': '', 'enabled': 1}],
                       [{'group_id': '11111', 'name': '', 'enabled': True}] * 2):
            with self.subTest(groups=groups), self.assertRaises(ValueError):
                validate(dict(cfg, group_monitor=dict(self.cfg, groups=groups)))

    def test_native_group_page_preference_preserves_existing_draft(self):
        bridge = DesktopApi.__new__(DesktopApi)
        import threading
        bridge._ui_lock = threading.Lock()
        with patch('src.core.desktop_api.ROOT', Path(self.temp.name)):
            bridge.ui_state({'draft': '还没发送的草稿', 'page': 'chat'})
            self.assertEqual(bridge.ui_state({'page': 'groups'})['draft'], '还没发送的草稿')
            self.assertEqual(bridge.ui_state()['page'], 'groups')


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name); cfg = load(root / 'none.json')
        cfg['safety']['mode'] = 'reply_only'
        self.root_patch = patch('src.core.harness.ROOT', root); self.root_patch.start(); self.addCleanup(self.root_patch.stop)
        self.session = aiohttp.ClientSession(); self.addAsyncCleanup(self.session.close)
        self.h = Harness(cfg, self.session); self.addAsyncCleanup(self.h.close)
        self.h.receive = AsyncMock(); self.h.qq.receive = self.h.receive; self.h.model.complete = AsyncMock()
        self.h.qq.action = AsyncMock()
        self.client = TestClient(TestServer(build(self.h, asyncio.Event())))
        await self.client.start_server(); self.addAsyncCleanup(self.client.close)
        self.headers = {'Host': '127.0.0.1:8765', 'X-Harness-Local': '1'}
        self.saved = patch('src.channel.local_ui.save_local');self.save = self.saved.start();self.addCleanup(self.saved.stop)

    async def post(self, **body):
        return await self.client.post('/api/group-monitor', json=body, headers=self.headers)

    async def test_hot_add_multi_group_passive_bridge_and_remove_preserves_history(self):
        for ident in ('11111', '22222'):
            r = await self.post(action='add', group_id=ident, name='群 ' + ident)
            self.assertEqual(r.status, 200, await r.text());self.assertFalse((await r.json())['restart_required'])
            await self.h.qq.ingest(event(ident))
        self.assertEqual(len(self.h.group_monitor.snapshot()['groups']), 2)
        self.h.receive.assert_not_awaited();self.h.model.complete.assert_not_awaited();self.h.qq.action.assert_not_awaited()
        self.assertEqual(self.h.store.read('chat'), []);self.assertEqual(self.h.store.read('inbox'), [])
        self.assertFalse(hasattr(self.h, 'agent_link'))
        self.h.set_safety('paused')
        await self.h.qq.ingest(event(message_id=2))  # 全暂停禁止说话，独立只读监听仍可接收。
        self.assertEqual(len(self.h.group_monitor.rows('11111')), 2)
        r = await self.post(action='update', group_id='11111', name='新备注', enabled=False)
        self.assertEqual(r.status, 200)
        await self.h.qq.ingest(event(message_id=3));self.assertEqual(len(self.h.group_monitor.rows('11111')), 2)
        r = await self.post(action='remove', group_id='11111');self.assertEqual(r.status, 200)
        r = await self.client.get('/api/group-monitor?group_id=11111', headers=self.headers);self.assertEqual(r.status, 403)
        await self.post(action='add', group_id='11111', name='重新添加')
        r = await self.client.get('/api/group-monitor?group_id=11111', headers=self.headers)
        self.assertEqual(len((await r.json())['messages']), 2)
        self.save.assert_called()

    async def test_untrusted_controls_and_queries_rejected(self):
        r = await self.client.post('/api/group-monitor', json={'action': 'add', 'group_id': '11111', 'name': ''}, headers=dict(self.headers, Origin='https://evil.invalid'))
        self.assertEqual(r.status, 403)
        for body in ({'action': 'add', 'group_id': '../owner', 'name': ''},
                     {'action': 'add', 'group_id': '11111', 'name': '', 'send': True},
                     {'action': 'update', 'group_id': '11111', 'name': '', 'enabled': True}):
            r = await self.post(**body);self.assertEqual(r.status, 400)
        await self.post(action='add', group_id='11111', name='')
        r = await self.post(action='add', group_id='11111', name='');self.assertEqual(r.status, 400)
        r = await self.client.get('/api/group-monitor?group_id=11111&group_id=22222', headers=self.headers);self.assertEqual(r.status, 400)
        self.h.cfg['group_monitor']['max_groups'] = 1
        r = await self.post(action='add', group_id='22222', name='');self.assertEqual(r.status, 400)
        bridge = DesktopApi.__new__(DesktopApi);bridge._backend = type('Backend', (), {'request': lambda s, *a: {'ok': True}})()
        with patch('src.core.desktop_api.ROOT',self.h.store.root.parent):
            self.assertEqual(bridge.request('group-monitor?group_id=11111'), {'ok': True})
            with self.assertRaises(PermissionError):bridge.request('group-monitor?path=owner')

    async def test_configuration_save_cannot_reenable_removed_group(self):
        r = await self.client.post('/api/config', json={'group_monitor': {'groups': [{'group_id': '11111', 'name': '', 'enabled': True}]}}, headers=self.headers)
        self.assertEqual(r.status, 400);self.save.assert_not_called()
