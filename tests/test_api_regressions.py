"""本机 HTTP 接口的回归测试：只覆盖维护期踩过的坑。"""
import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import aiohttp
from aiohttp.test_utils import TestClient, TestServer
from src.core.config import load
from src.core.harness import Harness
from src.channel.local_ui import build


class MemoryApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cfg = load(Path(self.temp.name) / 'no-local.json')
        self.patch = patch('src.core.harness.ROOT', Path(self.temp.name))
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.session = aiohttp.ClientSession()
        self.addCleanup(self.session.close)
        self.h = Harness(self.cfg, self.session)

    async def asyncTearDown(self):
        await self.h.close()

    async def test_client_supplied_source_does_not_crash_and_cannot_be_forged(self):
        """前端曾传 source，导致 append 收到重复关键字直接 500。"""
        server = TestServer(build(self.h, asyncio.Event()))
        async with TestClient(server) as client:
            headers = {'Host': '127.0.0.1:8765', 'X-Harness-Local': '1'}
            r = await client.post('/api/memory', json={
                'content': '测试用户喜欢蓝色', 'category': 'knowledge',
                'importance': 'permanent', 'source': 'forged_source',
            }, headers=headers)
            self.assertEqual(r.status, 200, await r.text())
            row = await r.json()
            self.assertEqual(row['source'], 'owner_manual')

            r = await client.get('/api/memory', headers={'Host': '127.0.0.1:8765'})
            self.assertEqual(r.status, 200)
            self.assertEqual(len(await r.json()), 1)


if __name__ == '__main__':
    unittest.main()
