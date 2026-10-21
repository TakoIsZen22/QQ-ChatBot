import asyncio
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer
from src.core.config import load
from src.core.instance import InstanceLock
from src.core.safety import Safety
from src.core.store import Store
from src.modules.qq_bridge import QQBridge
from tools import manage

class BackupTests(unittest.TestCase):
    def test_backup_restore_and_lock_and_tamper(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'config').mkdir();(root/'config/settings.json').write_text('{}')
            cfg=load(root/'no-local.json');store=Store(root/'data');store.append('people/owner/memory',content='恢复之前的约定')
            (root/'data/media').mkdir();(root/'data/media/example.bin').write_bytes(b'media-backup')
            with patch.object(manage,'ROOT',root):
                lock=InstanceLock(root/'data/.instance.lock')
                try:
                    with self.assertRaises((RuntimeError,OSError)):manage.backup(cfg)
                finally:lock.close()
                backup=manage.backup(cfg)
                store.append('people/owner/memory',content='备份之后新增的内容')
                result=manage.restore(cfg,backup)
                self.assertEqual(len(store.read('people/owner/memory')),1)
                self.assertEqual((root/'data/media/example.bin').read_bytes(),b'media-backup')
                self.assertTrue(Path(result['previous_data']).is_dir())
                (backup/'data/media/example.bin').write_bytes(b'corrupt')
                with self.assertRaisesRegex(ValueError,'SHA256'):manage.restore(cfg,backup)
                self.assertEqual(len(store.read('people/owner/memory')),1)

class ReconnectTests(unittest.IsolatedAsyncioTestCase):
    async def test_real_native_stream_reconnect_and_no_fabricated_history(self):
        with tempfile.TemporaryDirectory() as temp:
            cfg=load(Path(temp)/'no-local.json');store=Store(temp);safety=Safety(cfg['safety'],store,lambda *a,**k:None)
            received=[];seen=set();events=[];count=0;ready=asyncio.Event()
            async def receive(e):
                if e['message_id'] not in seen:
                    seen.add(e['message_id']);received.append(e)
            async def action(r):
                name=r.match_info['action']
                if name=='get_login_info':data={'user_id':456}
                elif name=='get_status':data={'online':True}
                else:data={'messages':[{'message_id':1,'sender':{'user_id':123},'time':1,'message':'没看过的约定'}, {'message_id':2,'user_id':123,'sender':{'user_id':456},'time':2,'message':'机器人自己发的话'}]}
                return web.json_response({'status':'ok','retcode':0,'data':data})
            async def event_handler(r):
                nonlocal count
                self.assertEqual(r.headers.get('X-QQ-ChatBot'),'1')
                stream=web.StreamResponse(headers={'Content-Type':'application/x-ndjson'})
                await stream.prepare(r);count+=1
                await stream.write((json.dumps({'meta_event_type':'heartbeat','status':{'online':True}})+'\n').encode())
                await stream.write((json.dumps({'post_type':'message','message_type':'private','message_id':1,'user_id':123,'time':1,'message':'重复上报'})+'\n').encode())
                if count>=2:ready.set()
                await asyncio.sleep(.03);await stream.write_eof();return stream
            app=web.Application();app.router.add_get('/events',event_handler);app.router.add_post('/{action}',action)
            async with TestServer(app) as srv,aiohttp.ClientSession() as session:
                c=copy.deepcopy(cfg['qq']);c.update(native_port=srv.port,reconnect_min_seconds=.01,reconnect_max_seconds=.05)
                q=QQBridge(c,'123',session,store,lambda level,event,**kw:events.append(event),receive,safety)
                task=asyncio.create_task(q.run())
                try:
                    await asyncio.wait_for(ready.wait(),3)
                    await asyncio.sleep(.02)
                finally:task.cancel();await asyncio.gather(task,return_exceptions=True)
            self.assertGreaterEqual(count,2)
            self.assertEqual(len(received),1)
            self.assertFalse(received[0]['historical'])
            self.assertIn('qq_catchup_unsupported',events)
            self.assertIn('qq_disconnected',events)

if __name__=='__main__':unittest.main()
