import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import aiohttp
from aiohttp.test_utils import TestClient,TestServer
from src.core.config import load
from src.core.store import Store
from src.core.soul import Soul
from src.core.harness import Harness
from src.modules.role import Role
from src.channel.local_ui import build
from tools import manage


class SoulTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cfg=load(self.root/'absent.json')
        self.store=Store(self.root/'data');self.soul=Soul(self.cfg['role'],self.store,self.root)
        (self.root/'src/persona').mkdir(parents=True)
        (self.root/'src/persona/role.md').write_text('基础人设与工具规则',encoding='utf-8')
        (self.root/'src/persona/soul.example.md').write_text('# 专属人设模板',encoding='utf-8')
        (self.root/'config').mkdir();(self.root/'config/settings.json').write_text('{}')

    def save(self,text):return self.soul.save(text,self.soul.current()['revision'])

    def test_save_injects_next_prompt_without_restarting_and_no_model_permission_change(self):
        role=Role(self.cfg['role'],self.root,self.store)
        self.assertNotIn('先听完再回应',role.prompt())
        row=self.save('先听完再回应，认真时少用表情。')
        self.assertIn('先听完再回应',role.prompt())
        self.soul.path.write_text('说话自然一些。',encoding='utf-8')
        self.assertIn('说话自然一些',role.prompt())
        self.assertFalse(self.cfg['role']['evolution_enabled'])
        self.assertEqual(row['path'],'data/persona/soul.md')

    def test_external_edit_conflict_preserves_file_and_does_not_append_draft(self):
        first=self.save('旧设定')
        self.soul.path.write_text('外部编辑后的设定',encoding='utf-8')
        count=len(self.store.read(Soul.STREAM))
        with self.assertRaisesRegex(ValueError,'其他窗口'):
            self.soul.save('过期草稿',first['revision'])
        self.assertEqual(self.soul.current()['text'],'外部编辑后的设定')
        self.assertEqual(len(self.store.read(Soul.STREAM)),count)

    def test_history_restore_and_empty_fallback(self):
        first=self.save('第一份设定')
        old=next(r for r in first['history'] if r['revision']==first['revision'])
        second=self.save('第二份设定')
        restored=self.soul.restore(old['id'],second['revision'])
        self.assertEqual(restored['text'],'第一份设定')
        self.assertFalse(self.save('')['active'])
        self.assertNotIn('【主人专属',Role(self.cfg['role'],self.root,self.store).prompt())

    def test_secrets_size_and_path_escape_are_rejected(self):
        for content in ('api_key: do-not-store-this', 'x'*(self.cfg['role']['soul_max_chars']+1)):
            with self.assertRaises(ValueError):self.save(content)
        self.assertFalse(self.soul.path.exists())
        self.cfg['role']['soul_file']='../../soul.md'
        with self.assertRaises(ValueError):self.soul.current()

    def test_existing_backup_restore_preserves_soul_and_history(self):
        original=self.save('备份内的人设')
        with patch.object(manage,'ROOT',self.root):
            snapshot=manage.backup(self.cfg)
            self.save('备份后的人设')
            manage.restore(self.cfg,snapshot)
        self.assertEqual(self.soul.current()['text'],'备份内的人设')
        self.assertTrue(any(r['revision']==original['revision'] for r in self.soul.snapshot()['history']))


class SoulApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cfg=load(self.root/'absent.json')
        self.patch=patch('src.core.harness.ROOT',self.root);self.patch.start();self.addCleanup(self.patch.stop)
        self.session=aiohttp.ClientSession()
        self.h=Harness(self.cfg,self.session)
        self.client=TestClient(TestServer(build(self.h,asyncio.Event())))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close();await self.h.close();await self.session.close()

    async def test_local_editor_can_save_while_paused_without_unpausing(self):
        self.h.set_safety('paused')
        headers={'Host':'127.0.0.1:8765','X-Harness-Local':'1'}
        current=await (await self.client.get('/api/soul',headers=headers)).json()
        body={'action':'save','text':'我喜欢温柔的语气。','expected_revision':current['revision']}
        denied=await self.client.post('/api/soul',json=body,headers={'Host':'127.0.0.1:8765'})
        self.assertEqual(denied.status,403)
        response=await self.client.post('/api/soul',json=body,headers=headers)
        self.assertEqual(response.status,200,await response.text())
        self.assertTrue((await response.json())['active'])
        self.assertEqual(self.h.safety.mode,'paused')
        forbidden=await self.client.post('/api/soul',json=dict(body,source='forged'),headers=headers)
        self.assertEqual(forbidden.status,400)
        events=self.h.log.store.read('events')
        self.assertFalse(any('温柔' in str(r) for r in events))
