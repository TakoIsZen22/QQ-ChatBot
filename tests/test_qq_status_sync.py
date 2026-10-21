"""Loopback protocol fixtures: no account login, model calls or real QQ traffic."""
import asyncio
import copy
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer
from src.core.config import load
from src.modules.qq_bridge import QQBridge


class StatusSyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.frames=asyncio.Queue();self.connections=0;self.actions=[];self.logged=[]
        self.identity='22222';self.online=False;self.receive=AsyncMock()

        async def stream(request):
            self.connections+=1
            response=web.StreamResponse(headers={'Content-Type':'application/x-ndjson'})
            await response.prepare(request)
            import json
            try:
                await response.write((json.dumps(self.heartbeat(self.online))+'\n').encode())
                while (frame:=await self.frames.get()) is not None:
                    await response.write((json.dumps(frame)+'\n').encode())
            except (ConnectionError,RuntimeError):pass
            return response

        async def action(request):
            self.actions.append(request.path)
            self.assertTrue(self.online, 'Login info must never be requested before login')
            return web.json_response({'status':'ok','data':{'user_id':self.identity}})

        app=web.Application();app.router.add_get('/events',stream);app.router.add_post('/get_login_info',action)
        self.server=TestServer(app);await self.server.start_server()
        self.session=aiohttp.ClientSession()
        cfg=copy.deepcopy(load()['qq']);cfg.update(native_port=self.server.port,bot_id='22222',reconnect_min_seconds=60)
        self.bridge=QQBridge(cfg,'11111',self.session,None,lambda level,event,**kw:self.logged.append(event),self.receive,None)
        self.task=asyncio.create_task(self.bridge.run())

    async def asyncTearDown(self):
        self.task.cancel();await asyncio.gather(self.task,return_exceptions=True)
        await self.frames.put(None)
        await self.session.close();await self.server.close()

    @staticmethod
    def heartbeat(online):return {'meta_event_type':'heartbeat','status':{'online':online}}

    async def until(self,predicate,seconds=2):
        async with asyncio.timeout(seconds):
            while not predicate():await asyncio.sleep(.005)

    async def test_waits_for_login_without_backoff_then_tracks_offline_and_reconnect(self):
        await self.until(lambda:self.bridge.last_event is not None or self.bridge.connected)
        await asyncio.sleep(.03)
        self.assertEqual(self.connections,1);self.assertEqual(self.actions,[])
        self.assertFalse(self.bridge.online)
        message={'post_type':'message','message_type':'private','message_id':'fixture','user_id':'11111','message':'test'}
        await self.frames.put(message)  # Offline messages must not enter the chat core.
        self.online=True;await self.frames.put(self.heartbeat(True))
        await self.frames.put(message)
        await self.until(lambda:self.receive.await_count==1)
        self.assertTrue(self.bridge.online);self.assertEqual(self.connections,1)
        self.online=False;await self.frames.put(self.heartbeat(False))
        await self.until(lambda:not self.bridge.online)
        self.online=True;await self.frames.put(self.heartbeat(True))
        await self.until(lambda:self.bridge.online)
        self.assertEqual(self.actions,['/get_login_info']*2)
        self.assertEqual(self.connections,1)
        await self.frames.put(None)
        await self.until(lambda:not self.bridge.connected)
        self.assertFalse(self.bridge.online);self.assertIsNone(self.bridge.bot_id)

    async def test_wrong_account_never_becomes_online_or_routes_messages(self):
        await self.until(lambda:self.bridge.connected)
        self.identity='99999';self.online=True
        await self.frames.put(self.heartbeat(True))
        await self.frames.put({'message_id':'untrusted','user_id':'11111','message':'test'})
        await self.until(lambda:'qq_connection_error' in self.logged)
        self.assertFalse(self.bridge.online);self.assertFalse(self.bridge.connected)
        self.receive.assert_not_awaited()

    async def test_manual_host_start_does_not_inherit_long_connection_backoff(self):
        await self.until(lambda:self.bridge.connected)
        available=False;original_get=self.session.get
        def connect(*args,**kwargs):
            if not available:
                key=SimpleNamespace(host='127.0.0.1',port=self.server.port,ssl=False)
                raise aiohttp.ClientConnectorError(key,ConnectionRefusedError(10061,'fixture refused'))
            return original_get(*args,**kwargs)
        # Refusal timing varies by Windows network stack. Inject that error only;
        # the later stream still runs against a real loopback server.
        with patch.object(self.session,'get',side_effect=connect):
            cfg=dict(self.bridge.cfg,reconnect_min_seconds=.03,reconnect_max_seconds=60)
            failures=[]
            bridge=QQBridge(cfg,'11111',self.session,None,lambda level,event,**kw:failures.append(event),self.receive,None)
            task=asyncio.create_task(bridge.run())
            try:
                await self.until(lambda:failures.count('qq_connection_error')>=5)
                available=True
                start=time.monotonic()
                await self.until(lambda:bridge.connected)
                self.assertLess(time.monotonic()-start,.3)
            finally:
                task.cancel();await asyncio.gather(task,return_exceptions=True)
