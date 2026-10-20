import asyncio
import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch
import aiohttp
from aiohttp.test_utils import TestClient, TestServer
from PIL import Image
from src.core.config import load
from src.core.harness import Harness
from src.channel.local_ui import build


def picture(fmt='PNG', color='blue'):
    out=io.BytesIO(); first=Image.new('RGB',(64,64),color)
    if fmt=='GIF':first.save(out,format=fmt,save_all=True,append_images=[Image.new('RGB',(64,64),'red')],duration=100,loop=0)
    else:first.save(out,format=fmt)
    return out.getvalue()


class StickerIntentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cfg=load(self.root/'no-local.json');self.cfg['safety']['mode']='reply_only'
        self.patch=patch('src.core.harness.ROOT',self.root);self.patch.start();self.addCleanup(self.patch.stop)
        self.session=aiohttp.ClientSession()
        self.h=Harness(self.cfg,self.session);self.service=self.h.sticker_intents
        self.analysis={'visual':'蓝色的小方块','text':'','emotion':'可能平静','intent':'可能是打招呼','reply_hint':'自然询问','uncertainty':'缺少语境','tags':['蓝色']}
        self.h.senses.understand_sticker=AsyncMock(return_value=self.analysis)

    async def asyncTearDown(self):
        await self.h.close();await self.session.close()

    async def upload(self,raw=None):
        return await self.service.analyze_upload('data:image/png;base64,'+base64.b64encode(raw or picture()).decode(),'测试.png')

    async def test_confirmation_wins_and_same_file_reuses_observation(self):
        row=await self.upload()
        self.assertIsNone(row['meaning'])
        self.service.save(row['media_id'],'蓝色问候','开玩笑','我其实是在撒娇','温柔地接话',['撒娇'])
        again=await self.upload()
        self.h.senses.understand_sticker.assert_awaited_once()
        self.assertEqual(again['meaning']['source'],'owner_confirmed')
        context=self.service.local_context(row['media_id'])
        self.assertIn('我其实是在撒娇',context);self.assertIn('model',self.h.store.read('sticker_analyses')[0]['source'])
        self.service.remove(row['media_id'])
        self.assertIsNone(self.service.list()[0]['meaning'])
        self.assertNotIn('我其实是在撒娇',self.service.local_context(row['media_id']))

    async def test_gif_is_sampled_into_static_preview(self):
        row=await self.upload(picture('GIF'))
        self.assertEqual(row['frames'],2)
        saved=self.h.store.read('media')[0]
        with Image.open(saved['preview_path']) as preview:
            self.assertEqual(preview.format,'JPEG');self.assertEqual(preview.width,128)

    async def test_invalid_oversize_and_unsupported_files_do_not_call_model(self):
        for data in ('file:///C:/private.png','data:image/png;base64,!!!','data:image/png;base64,'+base64.b64encode(b'not image').decode()):
            with self.assertRaises(ValueError):await self.service.analyze_upload(data)
        self.cfg['stickers']['max_image_bytes']=10
        with self.assertRaises(ValueError):await self.upload()
        self.h.senses.understand_sticker.assert_not_awaited();self.assertEqual(self.h.store.read('media'),[])

    async def test_failed_observation_leaves_no_bogus_meaning_or_media(self):
        self.h.senses.understand_sticker.side_effect=ValueError('bad response')
        with self.assertRaises(ValueError):await self.upload()
        self.assertEqual(self.h.store.read('media'),[])
        self.assertEqual(list((self.h.store.root/'media').iterdir()),[])

    async def test_local_and_qq_image_both_receive_confirmed_intent(self):
        row=await self.upload()
        self.service.save(row['media_id'],'撒娇','委屈','希望被安慰')
        local=await self.h.media_context({'media':[{'type':'sticker','media_id':row['media_id']}],'text':''})
        source=self.root/'qq.png';source.write_bytes(picture())
        self.h.qq.action=AsyncMock(return_value={'file':str(source)})
        qq=await self.h.media_context({'media':[{'type':'image','data':{'file':'onebot-file'}}],'text':''})
        for context in (local,qq):self.assertIn('希望被安慰',context)
        self.h.senses.understand_sticker.assert_awaited_once()
        self.h.generate=AsyncMock(return_value='我在，抱抱你');self.h.send=AsyncMock()
        self.h.role.prompt=Mock(return_value='测试角色')
        await self.h.turn({'media':[{'type':'sticker','media_id':row['media_id']}],'text':'','message_id':'local:test','channel':'local'},self.h.safety.generation)
        messages=self.h.generate.await_args.args[0]
        self.assertIn('希望被安慰',messages[-1]['content'])

    async def test_http_media_validation_and_save_source(self):
        headers={'Host':'127.0.0.1:8765','X-Harness-Local':'1'}
        async with TestClient(TestServer(build(self.h,asyncio.Event()))) as client:
            r=await client.post('/api/sticker-intents',json={'action':'analyze','data_url':'data:image/png;base64,'+base64.b64encode(picture()).decode()},headers=headers)
            self.assertEqual(r.status,200,await r.text());row=await r.json()
            r=await client.post('/api/sticker-intents',json={'action':'save','media_id':row['media_id'],'name':'打招呼','emotion':'轻松','intent':'只是在打招呼'},headers=headers)
            self.assertEqual(r.status,200,await r.text())
            r=await client.post('/api/chat',json={'media':[{'type':'sticker','media_id':'../../config'}]},headers=headers)
            self.assertEqual(r.status,400)
            r=await client.post('/api/chat',json={'media':[{'type':'sticker','media_id':row['media_id']}],'text':''},headers=headers)
            self.assertEqual(r.status,200,await r.text())
            self.assertEqual(self.h.store.read('chat')[-1]['media'][0]['media_id'],row['media_id'])

    async def test_pause_cancels_active_http_analysis_without_saving(self):
        started=asyncio.Event()
        async def slow(*args):started.set();await asyncio.sleep(30)
        self.h.senses.understand_sticker=slow
        headers={'Host':'127.0.0.1:8765','X-Harness-Local':'1'}
        async with TestClient(TestServer(build(self.h,asyncio.Event()))) as client:
            task=asyncio.create_task(client.post('/api/sticker-intents',json={'action':'analyze','data_url':'data:image/png;base64,'+base64.b64encode(picture()).decode()},headers=headers))
            await asyncio.wait_for(started.wait(),2)
            response=await client.post('/api/safety',json={'mode':'paused'},headers=headers)
            self.assertEqual(response.status,200)
            result=await asyncio.wait_for(task,1)
            self.assertEqual(result.status,409);self.assertEqual(self.h.store.read('media'),[])

    async def test_structured_vision_failure_is_not_silently_saved(self):
        from src.modules.senses import Senses
        folder=self.h.store.root/'media';folder.mkdir();path=folder/'test.jpg';path.write_bytes(picture('JPEG'))
        model=Mock();model.complete=AsyncMock(return_value={'content':'不合规输出'})
        senses=Senses(self.cfg['voice'],self.h.store,self.root,model)
        with self.assertRaises(ValueError):await senses.understand_sticker(path)
        model.complete.return_value={'content':'```json\n'+json.dumps(self.analysis)+'\n```'}
        value=await senses.understand_sticker(path)
        self.assertEqual(value['visual'],self.analysis['visual'])
        self.assertTrue(model.complete.await_args.kwargs['auxiliary'])

    async def test_chat_image_is_queued_without_manual_import_and_followup_keeps_context(self):
        headers={'Host':'127.0.0.1:8765','X-Harness-Local':'1'}
        async with TestClient(TestServer(build(self.h,asyncio.Event()))) as client:
            response=await client.post('/api/chat',json={'text':'这个图是什么意思','image':{'data_url':'data:image/png;base64,'+base64.b64encode(picture()).decode(),'name':'直接发送.png'}},headers=headers)
            self.assertEqual(response.status,200,await response.text())
            self.h.senses.understand_sticker.assert_not_awaited()
            row=self.h.store.read('inbox')[-1]
            self.assertEqual(row['media'][0]['type'],'chat_image')
            self.h.generate=AsyncMock(return_value='看起来像轻松地打招呼');self.h.send=AsyncMock();self.h.role.prompt=Mock(return_value='测试角色')
            await self.h.turn(row,self.h.safety.generation)
            self.h.senses.understand_sticker.assert_awaited_once()
            self.assertIn('蓝色的小方块',self.h.generate.await_args.args[0][-1]['content'])
            response=await client.get('/api/chat',headers={'Host':'127.0.0.1:8765'})
            self.assertTrue((await response.json())[-1]['media'][0]['thumbnail'].startswith('data:image/jpeg'))
            await self.h.receive({'text':'刚才那张呢','message_id':'followup','channel':'local'})
            await self.h.turn(self.h.store.read('inbox')[-1],self.h.safety.generation)
            previous=self.h.generate.await_args.args[0][-2]['content']
            self.assertIn('蓝色的小方块',previous)

    async def test_market_face_event_automatically_runs_vision(self):
        self.h.qq.owner='123';self.h.chat_media.fetch_qq_image=AsyncMock(return_value=picture())
        await self.h.qq.ingest({'message_id':'market-1','post_type':'message','message_type':'private','user_id':123,
            'message':[{'type':'mface','data':{'url':'https://gxh.vip.qq.com/example.gif'}}]})
        context=await self.h.media_context(self.h.store.read('inbox')[-1])
        self.assertIn('蓝色的小方块',context)
        self.h.senses.understand_sticker.assert_awaited_once()
        self.assertEqual(len(self.h.store.read('chat_media_results')),1)

    async def test_qq_image_cache_miss_falls_back_to_allowed_cdn(self):
        self.h.qq.action=AsyncMock(side_effect=RuntimeError('cache miss'))
        self.h.chat_media.fetch_qq_image=AsyncMock(return_value=picture())
        context=await self.h.media_context({'message_id':'qq-image','text':'','media':[{'type':'image','data':{'file':'cache','url':'https://gchat.qpic.cn/test.png'}}]})
        self.assertIn('蓝色的小方块',context)
        self.h.chat_media.fetch_qq_image.assert_awaited_once_with('https://gchat.qpic.cn/test.png')

    async def test_builtin_face_uses_verified_catalog_without_fake_vision(self):
        folder=self.root/'.runtime/napcat/static/assets';folder.mkdir(parents=True)
        (folder/'qface-test.js').write_text('JSON.parse(\'[{"QSid":"14","QDes":"/微笑"}]\')',encoding='utf-8')
        context=await self.h.media_context({'message_id':'builtin','text':'','media':[{'type':'face','data':{'id':'14'}}]})
        self.assertIn('微笑',context);self.assertIn('非视觉观察',context)
        self.h.senses.understand_sticker.assert_not_awaited()

    async def test_qq_image_urls_and_private_dns_are_rejected(self):
        for url in ('http://gxh.vip.qq.com/x','https://127.0.0.1/x','https://gxh.vip.qq.com.evil.test/x','https://user:password@gxh.vip.qq.com/x','https://gxh.vip.qq.com:8765/x'):
            with self.subTest(url=url):
                with self.assertRaises(PermissionError):await self.h.chat_media.fetch_qq_image(url)
        loop=asyncio.get_running_loop()
        with patch.object(loop,'getaddrinfo',AsyncMock(return_value=[(2,1,6,'',('127.0.0.1',443))])):
            with self.assertRaises(PermissionError):await self.h.chat_media.fetch_qq_image('https://gxh.vip.qq.com/x')

    async def test_paused_chat_image_does_not_run_model(self):
        self.h.set_safety('paused')
        attachment=await self.h.chat_media.stage('data:image/png;base64,'+base64.b64encode(picture()).decode())
        result=await self.h.receive({'text':'','media':[attachment]})
        self.assertTrue(result['paused']);self.assertEqual(self.h.queue.qsize(),0)
        self.h.senses.understand_sticker.assert_not_awaited()

    async def test_images_per_turn_are_bounded_and_failure_is_explicit(self):
        self.cfg['stickers']['max_images_per_turn']=1
        self.h.chat_media.qq_bytes=AsyncMock(return_value=picture())
        context=await self.h.media_context({'text':'','media':[{'type':'image','data':{}},{'type':'image','data':{}}]})
        self.assertIn('数量已达上限',context);self.h.chat_media.qq_bytes.assert_awaited_once()
        self.h.chat_media.qq_bytes.side_effect=ValueError('invalid image')
        context=await self.h.media_context({'text':'','media':[{'type':'image','data':{}}]})
        self.assertIn('不能猜内容',context)


if __name__=='__main__':unittest.main()
