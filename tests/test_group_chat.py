import asyncio
import copy
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import aiohttp
from aiohttp.test_utils import TestClient, TestServer

from src.core.config import load, validate
from src.core.harness import Harness
from src.core.safety import Safety
from src.modules.group_chat import GroupChat
from src.channel.local_ui import build


def event(ident='11111', mid='1', text='你好', at='54321', **kw):
    parts = [{'type': 'text', 'data': {'text': text}}]
    if at:parts.insert(0, {'type': 'at', 'data': {'qq': at}})
    return dict(post_type='message', message_type='group', group_id=ident, message_id=mid,
                user_id='33333', sender={'user_id':'33333'}, time=time.time(), message=parts, **kw)


class GroupTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        cfg = load(root/'none.json')
        cfg['safety'].update(mode='reply_only', groups_muted=False)
        cfg['group_monitor']['groups'] = [dict(group_id=i, name='', enabled=True, reply_enabled=True,
                                             trigger='at', public_prompt='公开群说明 '+i) for i in ('11111','22222')]
        patcher = patch('src.core.harness.ROOT', root);patcher.start();self.addCleanup(patcher.stop)
        self.session = aiohttp.ClientSession();self.addAsyncCleanup(self.session.close)
        self.h = Harness(cfg,self.session);self.addAsyncCleanup(self.h.close)
        self.h.qq.connected = self.h.qq.online = self.h.qq.group_policy_synced = True
        self.h.qq.bot_id = '54321'
        self.h.qq.action = AsyncMock(return_value={'configured':True})
        self.h.model.complete = AsyncMock(return_value={'content':'群回复'})
        self.h.prompt = lambda *a: (_ for _ in ()).throw(AssertionError('private prompt accessed'))
        self.h.role.prompt = self.h.prompt
        self.task = asyncio.create_task(self.h.group_chat.run())
        self.h.workers.append(self.task)

    async def drain(self):
        await asyncio.wait_for(self.h.group_chat.queue.join(),2)

    async def test_mention_replies_once_and_never_uses_private_state_or_tools(self):
        self.h.store.append('chat',person='owner',role='user',content='PRIVATE CHAT')
        self.h.store.append('people/owner/memory',content='PRIVATE MEMORY')
        self.h.store.append('diary',content='PRIVATE DIARY')
        await self.h.qq.ingest(event())
        await self.drain()
        self.h.model.complete.assert_awaited_once()
        args = self.h.model.complete.call_args
        self.assertEqual(len(args.args),1);self.assertEqual(args.kwargs,{})
        prompt = str(args.args)
        self.assertNotIn('PRIVATE',prompt);self.assertIn('公开群说明 11111',prompt)
        self.h.qq.action.assert_awaited_once_with('send_group_msg',{'group_id':'11111','message':[{'type':'text','data':{'text':'群回复'}}]})
        self.assertEqual(len(self.h.store.read('chat')),1)
        self.assertEqual(self.h.store.read('inbox'),[])
        self.assertEqual(self.h.store.tail('groups/11111/reply_events',1)[0]['status'],'replied')
        self.assertEqual(self.h.store.tail('outbound',1)[0]['target'],'group:11111')
        await self.h.qq.ingest(event())
        self.h.model.complete.assert_awaited_once()
        self.assertIsNotNone(self.h.status()['last_spoke'])

    async def test_not_mentioned_at_all_disabled_unknown_and_stale_never_infer(self):
        await self.h.qq.ingest(event(at=None))
        await self.h.qq.ingest(event(mid='2',at='all'))
        await self.h.qq.ingest(event('99999'))
        self.h.cfg['group_monitor']['groups'][1]['reply_enabled']=False
        await self.h.qq.ingest(event('22222'))
        old=event(mid='3');old['time']=time.time()-600
        await self.h.qq.ingest(old)
        await self.h.qq.ingest(event(mid='4'),historical=True)
        await self.h.qq.ingest(event(mid='5',text=''))
        await self.drain()
        self.h.model.complete.assert_not_awaited();self.h.qq.action.assert_not_awaited()

    async def test_group_history_isolation_and_reset_retains_records(self):
        self.h.store.append('groups/11111/chat',role='user',content='ONLY A',user_id='33333')
        self.h.store.append('groups/22222/chat',role='user',content='ONLY B',user_id='44444')
        await self.h.qq.ingest(event('22222'))
        await self.drain()
        prompt=str(self.h.model.complete.call_args)
        self.assertIn('ONLY B',prompt);self.assertNotIn('ONLY A',prompt)
        self.h.group_chat.reset_context('11111')
        await self.h.qq.ingest(event(mid='2'))
        await self.drain()
        self.assertNotIn('ONLY A',str(self.h.model.complete.call_args))
        self.assertIn('ONLY A',str(self.h.store.read('groups/11111/chat')))
        self.assertEqual(len(self.h.store.read('outbound')),2)

    async def test_cooldown_survives_restart_and_all_trigger_stays_bounded(self):
        self.h.cfg['group_monitor']['groups'][0]['trigger']='all'
        await self.h.qq.ingest(event(at=None))
        await self.drain()
        restarted=GroupChat(self.h.cfg['group_chat'],self.h.group_monitor,self.h.store,self.h.model,self.h.safety,
                            self.h.log,self.h.qq.send_group,self.h.turn_lock,lambda:'bot')
        # Lots of intervening statuses must not erase the cooldown reservation.
        for _ in range(110):restarted.state('11111','not_addressed')
        await restarted.receive(event(mid='2',at=None),self.h.qq.bot_id)
        self.assertTrue(restarted.queue.empty())
        self.assertEqual(restarted.last_result['11111']['status'],'cooldown')

    async def test_pause_or_mute_during_generation_cancels_without_send(self):
        entered=asyncio.Event()
        async def wait(*a):entered.set();await asyncio.Event().wait()
        self.h.model.complete.side_effect=wait
        await self.h.qq.ingest(event())
        await asyncio.wait_for(entered.wait(),1)
        self.h.set_safety(groups_muted=True)
        await self.drain()
        self.h.qq.action.assert_not_awaited()
        self.assertEqual(self.h.group_chat.last_result['11111']['status'],'safety_cancelled')
        await self.h.qq.ingest(event(mid='2'))
        self.assertTrue(self.h.group_chat.queue.empty())

    async def test_config_revision_cancels_queued_turn_even_after_reenable(self):
        await self.h.turn_lock.acquire()
        try:
            await self.h.qq.ingest(event())
            self.h.group_chat.cancel()
        finally:self.h.turn_lock.release()
        await self.drain()
        self.h.model.complete.assert_not_awaited()

    async def test_tools_ignored_native_failure_reserved_and_never_retried(self):
        self.h.model.complete.return_value={'content':'not sent','tool_calls':[{'function':{'name':'memory_append'}}]}
        await self.h.qq.ingest(event())
        await self.drain();self.h.qq.action.assert_not_awaited()
        self.h.model.complete.return_value={'content':'[CQ:at,qq=all]hello'}
        self.h.qq.action.side_effect=RuntimeError('fixture native timeout')
        await self.h.qq.ingest(event('22222'))
        await self.drain()
        self.h.qq.action.assert_awaited_once()
        self.assertEqual(self.h.qq.action.call_args.args[1]['message'][0]['data']['text'],'hello')
        self.assertEqual(self.h.group_chat.last_result['22222']['status'],'failed_requires_review')
        safety=Safety(self.h.cfg['safety'],self.h.store,self.h.log)
        self.assertEqual(len(safety.rates['group:22222']),1)

    async def test_queue_full_and_expired_queue_do_not_generate(self):
        self.task.cancel();await asyncio.gather(self.task,return_exceptions=True)
        self.h.group_chat.queue=asyncio.Queue(maxsize=1)
        await self.h.qq.ingest(event())
        await self.h.qq.ingest(event('22222'))
        self.assertEqual(self.h.group_chat.last_result['22222']['status'],'queue_full')
        ident,row,gen,rev=self.h.group_chat.queue.get_nowait()
        row['ts']='2020-01-01T00:00:00+00:00'
        self.assertEqual(await self.h.group_chat.turn(ident,row,gen,rev),'stale_ignored')
        self.h.model.complete.assert_not_awaited()

    async def test_native_sync_and_disabled_group_cannot_send(self):
        self.assertTrue(await self.h.qq.sync_groups())
        self.assertEqual(self.h.qq.action.call_args.args[0],'configure_groups')
        self.h.qq.action.reset_mock()
        self.h.qq.group_policy_synced=False
        self.assertFalse(await self.h.qq.send_group('11111','hello',self.h.safety.generation))
        self.h.qq.group_policy_synced=True
        self.h.cfg['group_monitor']['groups'][0]['reply_enabled']=False
        self.assertFalse(await self.h.qq.send_group('11111','hello',self.h.safety.generation))
        self.h.qq.action.assert_not_awaited()

    async def test_real_http_model_and_bridge_with_loopback_fixtures(self):
        from aiohttp import web
        from src.modules.model import Model
        from src.modules.qq_bridge import QQBridge
        calls = []
        async def route(request):
            body = await request.json();calls.append((request.path, body))
            if request.path == '/v1/chat/completions':
                return web.json_response({'choices':[{'message':{'role':'assistant','content':'HTTP 群回复'}}]})
            return web.json_response({'status':'ok','data':{'configured':True,'accepted':True}})
        app = web.Application();app.router.add_post('/{path:.*}',route)
        server = TestServer(app);await server.start_server();self.addAsyncCleanup(server.close)
        cfg = dict(self.h.cfg['model'], provider='openai_compatible',base_url=str(server.make_url('/v1')),
                   main='fixture',key_env='QQ_CHATBOT_UNUSED_FIXTURE_KEY')
        self.h.group_chat.model = Model(cfg,self.session,self.h.log)
        self.h.qq.cfg['native_port'] = server.port
        self.h.qq.action = QQBridge.action.__get__(self.h.qq,QQBridge)
        self.assertTrue(await self.h.qq.sync_groups())
        await self.h.qq.ingest(event());await self.drain()
        self.assertEqual([path for path, _ in calls],['/configure_groups','/v1/chat/completions','/send_group_msg'])
        self.assertNotIn('tools',calls[1][1]);self.assertEqual(calls[1][1]['model'],'fixture')
        self.assertEqual(calls[2][1],{'group_id':'11111','message':[{'type':'text','data':{'text':'HTTP 群回复'}}]})
        self.assertEqual(self.h.group_chat.last_result['11111']['status'],'replied')

    async def test_api_saves_hot_and_exposes_diagnostics_without_unmuting(self):
        self.h.set_safety(groups_muted=True)
        client=TestClient(TestServer(build(self.h,asyncio.Event())))
        await client.start_server();self.addAsyncCleanup(client.close)
        headers={'Host':'127.0.0.1:8765','X-Harness-Local':'1'}
        body=dict(action='update',group_id='11111',name='测试群',enabled=True,reply_enabled=True,trigger='all',public_prompt='公开设定')
        with patch('src.channel.local_ui.save_local') as save:
            response=await client.post('/api/group-monitor',json=body,headers=headers)
            self.assertEqual(response.status,200,await response.text())
            self.assertTrue((await response.json())['policy_synced']);save.assert_called_once()
        self.assertTrue(self.h.safety.groups_muted)
        response=await client.get('/api/group-monitor',headers=headers)
        value=await response.json()
        self.assertTrue(value['groups_muted']);self.assertIn('chat',value)
        self.assertEqual(value['groups'][0]['public_prompt'],'公开设定')
        response=await client.post('/api/group-monitor',json={'action':'reset_context','group_id':'11111'},headers=headers)
        self.assertEqual(response.status,200)
        with patch('src.channel.local_ui.save_local',side_effect=OSError('fixture write failure')):
            body['name']='should not apply'
            response=await client.post('/api/group-monitor',json=body,headers=headers)
            self.assertEqual(response.status,500)
        self.assertEqual(self.h.cfg['group_monitor']['groups'][0]['name'],'测试群')

    async def test_strict_group_setting_validation(self):
        for patch_value in ({'trigger':'random'}, {'reply_enabled':1}, {'public_prompt':'x'*2001}):
            candidate=copy.deepcopy(self.h.cfg)
            candidate['group_monitor']['groups'][0].update(patch_value)
            with self.assertRaises(ValueError):validate(candidate)
        for key in self.h.cfg['group_chat']:
            candidate=copy.deepcopy(self.h.cfg);candidate['group_chat'][key]=None
            with self.subTest(key=key),self.assertRaises(ValueError):validate(candidate)
