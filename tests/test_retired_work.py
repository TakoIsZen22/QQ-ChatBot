"""An upgrade must not resurrect executable work bindings or consume old tasks."""
import asyncio
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
from aiohttp.test_utils import TestClient, TestServer
from src.channel.local_ui import build
from src.core.config import ROOT, load, save_local
from src.core.desktop_api import DesktopApi, READ_ENDPOINTS, WRITE_ENDPOINTS
from src.core.harness import Harness
from src.core.tools import TOOLS


class UpgradeTests(unittest.TestCase):
    def test_legacy_binding_ignored_and_removed_only_on_explicit_save(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'config').mkdir()
            shutil.copyfile(ROOT/'config/settings.json', root/'config/settings.json')
            path=root/'config/local.json'
            old={'owner':{'name':'测试使用者'},'agent_link':{'enabled':True,'command':['never-execute']}}
            raw=json.dumps(old,ensure_ascii=False).encode('utf-8');path.write_bytes(raw)
            with patch('src.core.config.ROOT',root):
                cfg=load()
                self.assertNotIn('agent_link',cfg)
                self.assertEqual(path.read_bytes(),raw)
                self.assertEqual(cfg['owner']['name'],'测试使用者')
                save_local({'owner':{'name':'新称呼'}})
                saved=json.loads(path.read_text(encoding='utf-8'))
                self.assertNotIn('agent_link',saved)
                self.assertEqual(saved['owner']['name'],'新称呼')
                with self.assertRaises(ValueError):save_local({'agent_link':old['agent_link']})


class RetiredRoutesTests(unittest.IsolatedAsyncioTestCase):
    async def test_no_work_routes_tools_or_workers_and_history_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'data').mkdir()
            tasks=root/'data/agent_tasks.jsonl'
            raw=b'{"status":"queued","text":"private legacy task"}\n';tasks.write_bytes(raw)
            cfg=load(root/'missing.json')
            with patch('src.core.harness.ROOT',root):
                async with aiohttp.ClientSession() as session:
                    h=Harness(cfg,session)
                    async with TestClient(TestServer(build(h,asyncio.Event()))) as client:
                        headers={'Host':'127.0.0.1:8765','X-Harness-Local':'1'}
                        for endpoint in ('agent-work','agent-binding','agent-inbox'):
                            for method in ('GET','POST'):
                                response=await client.request(method,'/api/'+endpoint,headers=headers)
                                self.assertEqual(response.status,404,(endpoint,method))
                            self.assertNotIn(endpoint,READ_ENDPOINTS|WRITE_ENDPOINTS)
                        h.start();await asyncio.sleep(.01);await h.close()
                        self.assertFalse(hasattr(h,'agent_link'))
                        self.assertEqual(tasks.read_bytes(),raw)
                        self.assertNotIn('agent_active',h.status())
                        self.assertNotIn('agent_work_offer',[tool['function']['name'] for tool in TOOLS])
                        h.safety.set('reply_only')
                        with self.assertRaises(PermissionError):
                            h.tools.execute('agent_work_offer',{},h.safety.generation)
                        # The old slash command is ordinary chat input, with no executor branch.
                        h.role.prompt=Mock(return_value='test persona')
                        h.media_context=AsyncMock(return_value='')
                        h.generate=AsyncMock(return_value='只负责聊天。')
                        h.send=AsyncMock()
                        await h.turn({'text':'/工作 test','channel':'local','message_id':'fixture'},h.safety.generation)
                        h.generate.assert_awaited_once()
                        h.send.assert_awaited_once_with('只负责聊天。','local',h.safety.generation)
                        self.assertEqual(tasks.read_bytes(),raw)

    async def test_native_bridge_cannot_open_old_work_connections(self):
        api=DesktopApi.__new__(DesktopApi)
        self.assertFalse(hasattr(api,'agent_connection'))
        self.assertFalse(hasattr(api,'agent_pick'))
        for name in ('agent-work','agent-binding'):
            with self.assertRaises(PermissionError):api.request(name,{})


if __name__=='__main__':unittest.main()
