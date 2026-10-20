import asyncio
import copy
import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from datetime import datetime,timedelta,timezone
from unittest.mock import AsyncMock,patch
import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestClient,TestServer
from src.core.config import load,validate
from src.core.store import Store
from src.core.safety import Safety
from src.core.log import Log
from src.core.harness import Harness
from src.channel.local_ui import build
from src.modules.memory import Memory
from src.modules.diary import Diary
from src.modules.growth import Growth
from src.modules.qq_bridge import QQBridge
from src.modules.devices import Devices
from src.modules.plugins import MCPClient

class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.store=Store(self.temp.name);self.cfg=load(Path(self.temp.name)/'no-local.json')

    def test_memory_decay_delete_and_person_isolation(self):
        m=Memory(self.cfg['memory'],self.store)
        row=m.append('owner','测试用户喜欢蓝色',importance='permanent')
        m.append('other','别人的蓝色')
        self.assertEqual(m.query('owner','蓝色')[0]['id'],row['id'])
        m.remove('owner',row['id']);self.assertEqual(m.query('owner'),[])
        with self.assertRaises(ValueError):m.append('../escape','test')
        with self.assertRaises(ValueError):m.append('owner','token: sensitive123')
        old=m.append('owner','梨的约定',importance='normal')
        permanent=m.append('owner','梨的约定永远保留',importance='permanent')
        rows=self.store.read(m.stream('owner'))
        for r in rows:r['ts']=(datetime.now(timezone.utc)-timedelta(days=60)).isoformat()
        self.store.path(m.stream('owner')).write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8')
        results=m.query('owner','梨')
        self.assertEqual(results[0]['id'],permanent['id']);self.assertLess(results[1]['score'],.001)

    def test_diary_limits(self):
        d=Diary(self.cfg['diary'],self.store,'Asia/Hong_Kong')
        for i in range(3):d.append(f'他今天带来第{i}只梨。')
        with self.assertRaises(ValueError):d.append('那只梨还没回来。')
        with self.assertRaises(ValueError):d.append('今天真是充实的一天。')

    def test_growth_and_invalid_gateway(self):
        self.assertAlmostEqual(sum(Growth.normalize({'work':2,'companion':3,'learning':5}).values()),1)
        with self.assertRaises(ValueError):Growth.normalize({'work':-1,'companion':1,'learning':1})
        with self.assertRaises(ValueError):Growth.normalize({'work':float('nan'),'companion':1,'learning':1})
        self.cfg['model']['base_url']='https://example.com/v1'
        with self.assertRaises(ValueError):validate(self.cfg)

    def test_backup_path_overlap_forbidden(self):
        self.cfg['paths']['backups']='data/backups'
        with self.assertRaisesRegex(ValueError,'互不嵌套'):validate(self.cfg)

    def test_redaction_and_corruption(self):
        with patch.dict(os.environ,{'TEST_SECRET':'not-a-real-key'}):
            Log(self.store,('TEST_SECRET',))('ERROR','test',raw='oops not-a-real-key Bearer hidden')
        raw=self.store.path('events').read_text(encoding='utf-8')
        self.assertNotIn('not-a-real-key',raw);self.assertNotIn('hidden',raw)
        self.store.path('events').write_text('{broken',encoding='utf-8')
        with self.assertRaises(ValueError):self.store.read('events')

    def test_qq_limit_survives_restart(self):
        s=Safety(self.cfg['safety'],self.store,lambda *a,**k:None)
        for _ in range(20):self.assertTrue(s.reserve('private:1'))
        self.assertFalse(s.reserve('private:1'))
        s2=Safety(self.cfg['safety'],self.store,lambda *a,**k:None)
        self.assertFalse(s2.reserve('private:1'))
        s.reserve_irreversible('comment')
        with self.assertRaises(PermissionError):s.reserve_irreversible('comment')

class AsyncTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.cfg=load(Path(self.temp.name)/'no-local.json');self.cfg['safety']['mode']='reply_only';self.store=Store(self.temp.name)
        self.safety=Safety(self.cfg['safety'],self.store,lambda *a,**k:None)

    async def test_pause_cancels_delay_within_second(self):
        task=asyncio.create_task(self.safety.delay(10,self.safety.generation))
        await asyncio.sleep(.01);start=time.monotonic();self.safety.set('paused')
        self.assertFalse(await task);self.assertLess(time.monotonic()-start,1)

    async def test_onebot_owner_only_and_structured_text(self):
        received=[];sent=[]
        async def receive(e):received.append(e)
        async def handler(r):
            body=await r.json();sent.append((r.match_info['action'],body));return web.json_response({'status':'ok','retcode':0,'data':{'message_id':1}})
        app=web.Application();app.router.add_post('/{action}',handler)
        async with TestServer(app) as srv,aiohttp.ClientSession() as session:
            qcfg=copy.deepcopy(self.cfg['qq']);qcfg['http_url']=str(srv.make_url('')).rstrip('/')
            qq=QQBridge(qcfg,'123',session,self.store,lambda *a,**k:None,receive,self.safety)
            await qq.ingest({'post_type':'request','request_type':'friend'})
            await qq.ingest({'post_type':'message','message_type':'group','user_id':123,'message_id':1,'message':'hi'})
            await qq.ingest({'post_type':'message','message_type':'private','user_id':999,'message_id':2,'message':'hi'})
            await qq.ingest({'post_type':'message','message_type':'private','user_id':123,'message_id':3,'message':[{'type':'text','data':{'text':'测试用户来了'}}]})
            self.assertEqual(len(received),1)
            await qq.send('[CQ:at,qq=all]',self.safety.generation)
            self.assertEqual(sent[-1][1]['message'][0]['type'],'text')
            with self.assertRaises(PermissionError):await qq.action('set_friend_add_request',{})
            self.safety.set('paused');self.assertFalse(await qq.send('hello',self.safety.generation))

    async def test_adb_payment_and_keyboard_guard(self):
        c=copy.deepcopy(self.cfg['devices']);c.update(enabled=True,serial='emulator-5554',device_kind='emulator',allowed_packages=['com.example.notes'])
        d=Devices(c,self.store,self.safety)
        d.adb=AsyncMock(return_value=b'package:com.eg.android.AlipayGphone')
        with self.assertRaises(PermissionError):await d.execute('tap',{'x':1,'y':1})
        d.adb=AsyncMock(side_effect=[b'package:com.example.notes',b'mCurrentFocus=Window{a u0 com.example.notes/.Main}',b'',b''])
        with self.assertRaisesRegex(RuntimeError,'ADBKeyboard'):await d.execute('text',{'text':'中文'})

    async def test_mcp_stdio_real_fixture(self):
        import sys
        cfg={'command':[sys.executable,str(Path(__file__).parent/'fixtures/mcp_server.py')],'allowed_tools':['echo']}
        result=await MCPClient(cfg).call('echo',{'text':'鱼'})
        self.assertEqual(result['content'][0]['text'],'鱼')
        with self.assertRaises(PermissionError):await MCPClient(cfg).call('delete',{})

    async def test_harness_route_dedupe_tools_and_stop(self):
        # 临时路径完全隔离，模型 mock；不会写用户真实记忆或访问 QQ。
        root=Path(self.temp.name)
        with patch('src.core.harness.ROOT',root):
            self.cfg['paths']={'data':'data','logs':'logs','backups':'backups'}
            self.cfg['conversation'].update(min_delay_seconds=0,max_delay_seconds=0)
            self.cfg['model']['main']='fixture'
            async with aiohttp.ClientSession() as session:
                h=Harness(self.cfg,session)
                h.role.prompt=lambda:'fixture persona'
                h.model.complete=AsyncMock(side_effect=[{'role':'assistant','tool_calls':[{'id':'a','type':'function','function':{'name':'memory_append','arguments':json.dumps({'content':'测试用户喜欢蓝色','importance':'permanent'})}}]}, {'role':'assistant','content':'记住啦。\n\n蓝色很适合你。'}])
                h.start()
                try:
                    first=await h.receive({'text':'我喜欢蓝色','message_id':'x','channel':'local'})
                    duplicate=await h.receive({'text':'我喜欢蓝色','message_id':'x','channel':'local'})
                    self.assertTrue(duplicate['duplicate'])
                    await asyncio.wait_for(h.queue.join(),2)
                    self.assertEqual(len([r for r in h.store.read('chat') if r['role']=='assistant']),2)
                    self.assertEqual(h.memory.query('owner','蓝色')[0]['content'],'测试用户喜欢蓝色')
                    # 模型悬挂期间停止不能等待其完成。
                    async def slow(*a,**k):await asyncio.sleep(30)
                    h.model.complete=slow
                    await h.receive({'text':'等一下','message_id':'y'})
                    await asyncio.sleep(.02)
                    start=time.monotonic();await h.receive({'text':'闭嘴','message_id':'stop'})
                    await asyncio.wait_for(h.queue.join(),1)
                    self.assertLess(time.monotonic()-start,1)
                    self.assertEqual(h.safety.mode,'paused')
                    self.assertEqual(len([r for r in h.store.read('chat') if r['role']=='assistant']),2)
                finally:await h.close()

    async def test_http_csrf_and_pause(self):
        with patch('src.core.harness.ROOT',Path(self.temp.name)):
            async with aiohttp.ClientSession() as session:
                h=Harness(self.cfg,session)
                server=TestServer(build(h,asyncio.Event()))
                async with TestClient(server) as client:
                    host={'Host':'127.0.0.1:8765'}
                    r=await client.get('/api/status',headers=host);self.assertEqual(r.status,200)
                    r=await client.get('/missing-file',headers=host);self.assertEqual(r.status,404)
                    r=await client.post('/api/safety',json={'mode':'paused'},headers=host);self.assertEqual(r.status,403)
                    r=await client.post('/api/safety',json={'mode':'paused'},headers={**host,'X-Harness-Local':'1','Origin':'https://evil.example'});self.assertEqual(r.status,403)
                    r=await client.post('/api/safety',json={'mode':'paused'},headers={**host,'X-Harness-Local':'1'});self.assertEqual(r.status,200)

if __name__=='__main__':unittest.main()
