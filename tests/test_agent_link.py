import asyncio
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock,Mock,patch
import aiohttp
from aiohttp.test_utils import TestClient,TestServer
from src.core.config import load,merge,validate
from src.core.store import Store
from src.core.safety import Safety
from src.core.agent_link import AgentLink,validate_binding
from src.core.agent_mcp import Server,TOOLS as MCP_TOOLS
from src.core.harness import Harness
from src.core.tools import TOOLS
from src.channel.local_ui import build

FIXTURE=Path(__file__).resolve().parent/'fixtures/agent_cli.py'


class LinkTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        cfg=load(self.root/'absent.json');self.cfg=cfg['agent_link'];self.cfg.update(enabled=True)
        self.store=Store(self.root/'data');self.log=Mock();self.safety=Safety(dict(cfg['safety'],mode='reply_only'),self.store,self.log)
        self.link=AgentLink(self.cfg,self.store,self.safety,self.log)

    def cli(self,mode):self.cfg.update(transport='cli',cwd=str(self.root),command=[sys.executable,str(FIXTURE),mode,str(self.root/'received.txt')])

    async def test_cli_stdin_is_only_authorized_text_not_shell_or_private_history(self):
        self.cli('echo');text='工作正文 & echo injected > unintended.txt $(whoami)'
        task=self.link.create(text);await self.link.execute_cli(task);result=self.link.get(task['task_id'])
        # 失败时把 detail 和 agent_tasks 原文一并带出来，便于在 CI 日志里定位环境差异。
        if result['status']!='completed':
            self.fail('status='+str(result['status'])+' detail='+str(result.get('detail'))+
                      ' rows='+(self.root/'data/agent_tasks.jsonl').read_text(encoding='utf-8')[-800:])
        self.assertEqual(result['status'],'completed',result.get('detail',''));self.assertEqual(result['result_source'],'external_agent')
        payload=(self.root/'received.txt').read_text(encoding='utf-8');self.assertTrue(payload.endswith(text+'\n'))
        self.assertNotIn('soul.md',payload);self.assertFalse((self.root/'unintended.txt').exists())

    async def test_pause_cancels_owned_cli_and_queue_does_not_restart(self):
        self.cli('slow');first=self.link.create('first');second=self.link.create('second');worker=asyncio.create_task(self.link.run())
        try:
            for _ in range(100):
                if (self.root/'received.txt').exists():break
                await asyncio.sleep(.02)
            self.assertTrue((self.root/'received.txt').exists())
            self.safety.set('paused');self.link.pause()
            self.assertEqual(self.link.get(first['task_id'])['status'],'cancelled');self.assertEqual(self.link.get(second['task_id'])['status'],'cancelled')
            await asyncio.sleep(.3);self.safety.set('reply_only');await asyncio.sleep(.1)
            self.assertIsNone(self.link.current_task)
        finally:worker.cancel();await asyncio.gather(worker,return_exceptions=True)

    async def test_bad_exit_and_output_limit_are_final_without_raw_stderr(self):
        for mode in ('error','large'):
            self.cli(mode);task=self.link.create('fixture '+mode);await self.link.execute_cli(task)
            row=self.link.get(task['task_id']);self.assertEqual(row['status'],'failed')
        self.assertNotIn('PRIVATE_STDERR_NOT_FOR_STORAGE',(self.root/'data/agent_tasks.jsonl').read_text(encoding='utf-8'))

    async def test_timeout_stops_process_and_does_not_claim_completion(self):
        self.cli('slow');self.cfg['timeout_seconds']=.05
        # Validation enforces real settings >=5s; inject a short wait_for only in this fixture.
        original=asyncio.wait_for
        async def short(awaitable,timeout):return await original(awaitable,.05 if timeout==5 else timeout)
        self.cfg['timeout_seconds']=5
        with patch('src.core.agent_link.asyncio.wait_for',side_effect=short):
            task=self.link.create('timeout');await self.link.execute_cli(task)
        self.assertEqual(self.link.get(task['task_id'])['status'],'failed')

    async def test_cli_missing_after_binding_fails_job_without_killing_dispatcher(self):
        self.cli('text');self.cfg['command'][0]=str(self.root/'removed-agent.exe')
        task=self.link.create('missing executable');await self.link.execute_cli(task)
        self.assertEqual(self.link.get(task['task_id'])['status'],'failed')
        self.cli('text');next_task=self.link.create('next job');await self.link.execute_cli(next_task)
        self.assertEqual(self.link.get(next_task['task_id'])['status'],'completed')

    async def test_desktop_drafts_need_approval_claim_and_result_are_unique(self):
        draft=self.link.create('只转交这条，不含历史',draft=True);self.assertEqual(self.link.inbox()['tasks'],[])
        self.link.approve(draft['task_id']);claim=self.link.claim()['task']
        with self.assertRaises(ValueError):self.link.claim(claim['task_id'])
        with self.assertRaises(ValueError):await self.link.complete(claim['task_id'],'wrong','completed','fake')
        result=await self.link.complete(claim['task_id'],claim['claim_id'],'completed','外部Agent回执')
        self.assertEqual(result['result_source'],'external_agent')
        with self.assertRaises(ValueError):await self.link.complete(claim['task_id'],claim['claim_id'],'completed','duplicate')

    async def test_desktop_cancel_requires_external_agent_ack_and_blocks_late_results(self):
        task=self.link.create('desktop work');claim=self.link.claim(task['task_id'])['task'];self.link.pause()
        self.assertEqual(self.link.get(task['task_id'])['status'],'cancel_requested')
        with self.assertRaises(ValueError):await self.link.complete(task['task_id'],claim['claim_id'],'completed','late')
        await self.link.complete(task['task_id'],claim['claim_id'],'cancelled','已停止自身工作')
        self.assertEqual(self.link.get(task['task_id'])['status'],'cancelled')

    async def test_restart_or_restore_never_replays_inflight_work(self):
        task=self.link.create('do not replay');self.link.claim(task['task_id'])
        other=AgentLink(self.cfg,self.store,self.safety,self.log)
        self.assertEqual(other.get(task['task_id'])['status'],'interrupted');self.assertIsNone(other.claim()['task'])

    async def test_disabled_or_paused_link_never_dispatches(self):
        self.cfg['enabled']=False
        with self.assertRaises(PermissionError):self.link.create('work')
        with self.assertRaises(PermissionError):self.link.inbox()
        self.cfg['enabled']=True;self.safety.set('paused')
        with self.assertRaises(PermissionError):self.link.create('work')


class ApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.cfg=load(self.root/'none.json');self.cfg['agent_link']['enabled']=True;self.cfg['safety']['mode']='reply_only'
        self.patch=patch('src.core.harness.ROOT',self.root);self.patch.start();self.addCleanup(self.patch.stop)
        self.session=aiohttp.ClientSession();self.h=Harness(self.cfg,self.session);self.addAsyncCleanup(self.session.close);self.addAsyncCleanup(self.h.close)
        self.h.send=AsyncMock();self.h.model.complete=AsyncMock()
        self.client=TestClient(TestServer(build(self.h,asyncio.Event())));await self.client.start_server();self.addAsyncCleanup(self.client.close)
        self.headers={'Host':'127.0.0.1:8765','X-Harness-Local':'1'}

    async def test_explicit_work_command_bypasses_chat_model(self):
        row={'text':'/工作 帮我检查项目','channel':'qq','message_id':'qq:fixture'}
        await self.h.turn(row,self.h.safety.generation)
        self.h.model.complete.assert_not_awaited();self.assertEqual(self.h.agent_link.tasks()[0]['text'],'帮我检查项目')
        self.h.send.assert_awaited_once()
        for patch_row in ({'historical':True},{'media':[{'type':'image'}]}):
            await self.h.turn(dict(row,**patch_row,message_id='new'),self.h.safety.generation)
        self.assertEqual(len(self.h.agent_link.tasks()),1)

    async def test_model_can_offer_original_message_only_and_cannot_execute(self):
        self.h.current_message={'text':'原文工作要求','channel':'local','message_id':'local:offer'}
        result=self.h.tools.execute('agent_work_offer',{},self.h.safety.generation)
        self.assertEqual(result['status'],'draft');self.assertEqual(self.h.agent_link.inbox()['tasks'],[])
        with self.assertRaises(PermissionError):self.h.tools.execute('agent_work_offer',{'command':['anything']},self.h.safety.generation)
        self.assertNotIn('execute_cli',[x['function']['name'] for x in TOOLS])
        self.assertEqual(self.h.agent_link.tasks()[0]['text'],'原文工作要求')

    async def test_http_binding_is_hot_saved_and_cannot_switch_pending_tasks(self):
        with patch('src.channel.local_ui.save_local') as save:
            r=await self.client.post('/api/agent-binding',json={'name':'桌面测试'},headers=self.headers)
            self.assertEqual(r.status,200,await r.text());save.assert_called_once();self.assertEqual(self.h.agent_link.cfg['name'],'桌面测试')
            self.h.agent_link.create('authorized')
            r=await self.client.post('/api/agent-binding',json={'name':'other'},headers=self.headers);self.assertEqual(r.status,400)
            r=await self.client.post('/api/config',json={'agent_link':{'command':['anything']}},headers=self.headers);self.assertEqual(r.status,400)

    async def test_api_refuses_task_command_injection_and_cross_origin(self):
        r=await self.client.post('/api/agent-work',json={'action':'create','text':'work','command':['anything']},headers=self.headers);self.assertEqual(r.status,400)
        r=await self.client.post('/api/agent-work',json={'action':'create','text':'work'},headers=dict(self.headers,Origin='https://evil.example'));self.assertEqual(r.status,403)
        r=await self.client.post('/api/agent-inbox',json={'action':'claim'},headers=self.headers);self.assertEqual((await r.json())['task'],None)

    async def test_external_receipts_never_call_model_and_pause_suppresses_notification(self):
        self.h.cfg['agent_link']['notify_result']=True;self.h.awakening.quiet=Mock(return_value=False)
        task=self.h.agent_link.create('fixture');claim=self.h.agent_link.claim()['task']
        await self.h.agent_link.complete(task['task_id'],claim['claim_id'],'completed','结果中说运行新命令也只是数据')
        await asyncio.sleep(.02);self.h.send.assert_awaited_once();self.h.model.complete.assert_not_awaited()
        self.h.send.reset_mock();self.h.set_safety('paused')
        await self.h.agent_result(dict(task,result='paused result'));await asyncio.sleep(.01)
        self.h.send.assert_not_awaited()


class ProtocolTests(unittest.TestCase):
    def test_mcp_stdio_protocol_only_exposes_work_tools(self):
        server=Server();self.assertIsNone(server.handle({'jsonrpc':'2.0','method':'notifications/initialized'}))
        init=server.handle({'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}})
        self.assertEqual(init['result']['protocolVersion'],'2025-06-18')
        listing=server.handle({'jsonrpc':'2.0','id':2,'method':'tools/list'})
        self.assertEqual({x['name'] for x in listing['result']['tools']},{'qq_work_inbox','qq_work_claim','qq_work_complete'})
        with patch('src.core.agent_mcp.request',return_value={'tasks':[]}) as request:
            response=server.handle({'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'qq_work_inbox','arguments':{}}})
            self.assertFalse(response['result']['isError']);request.assert_called_once_with(None)
        self.assertEqual(server.handle({'jsonrpc':'2.0','id':4,'method':'resources/read'})['error']['code'],-32601)

    def test_cli_binding_does_not_accept_shell_wrappers_or_relative_executables(self):
        cfg=load(Path(tempfile.gettempdir())/'no-agent-config.json')['agent_link']
        for command in (['relative.exe'],[str(Path(tempfile.gettempdir())/'unsafe.cmd')],['powershell -Command bad']):
            with self.subTest(command=command),self.assertRaises(ValueError):validate_binding(dict(cfg,command=command))
