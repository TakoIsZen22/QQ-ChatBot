import asyncio
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import aiohttp
from aiohttp import web
from aiohttp.test_utils import TestServer,TestClient
from src.core.config import load,validate
from src.core.model_endpoint import endpoint
from src.core.store import Store
from src.core.log import Log
from src.core.harness import Harness
from src.core.desktop_api import DesktopApi
from src.core.supervision import collect
from src.modules.model import Model
from src.channel.local_ui import build


class EndpointTests(unittest.TestCase):
    def setUp(self):self.cfg=load(Path(tempfile.gettempdir())/'absent-api-local.json')

    def test_custom_https_and_loopback_support_without_changing_default_magpie(self):
        self.assertEqual(self.cfg['model']['provider'],'magpie')
        self.cfg['model'].update(provider='openai_compatible',base_url='https://api.example/v1/')
        validate(self.cfg);self.assertEqual(endpoint(self.cfg['model']),'https://api.example/v1')
        for url in ('http://localhost:11434/v1','http://127.0.0.1:8080/api/v1','http://[::1]:8080/v1'):
            self.cfg['model']['base_url']=url;validate(self.cfg)

    def test_credentials_query_bad_schemes_and_plaintext_remote_are_rejected(self):
        self.cfg['model']['provider']='openai_compatible'
        for url in ('https://user:pass@api.example/v1','https://api.example/v1?key=x','https://api.example/v1?',
                    'https://api.example/v1#','file:///v1','http://api.example/v1','https://api.example:70000/v1',
                    'https://api.example/v1/chat/completions','https://api.example/v1/models',' https://api.example/v1'):
            with self.subTest(url=url),self.assertRaises(ValueError):
                self.cfg['model']['base_url']=url;validate(self.cfg)
        self.cfg['model'].update(provider='magpie',base_url='https://api.example/v1')
        with self.assertRaisesRegex(ValueError,'自定义'):validate(self.cfg)

    def test_bridge_probe_uses_dedicated_timeout_and_cannot_receive_secret_fields(self):
        backend=Mock();api=DesktopApi(backend)
        api.request('model-connection',{'provider':'magpie'})
        backend.request.assert_called_once_with('model-connection',{'provider':'magpie'},timeout=load()['model']['models_timeout_seconds']+5)

    def test_supervision_probes_selected_endpoint_instead_of_requiring_magpie(self):
        self.cfg['model'].update(provider='openai_compatible',base_url='https://api.example:8443/v1')
        response=Mock();response.__enter__=Mock(return_value=response);response.__exit__=Mock(return_value=False)
        response.read.return_value=b'{"name":"DaFeiYu"}'
        opener=Mock();opener.open.return_value=response
        with patch('src.core.supervision.socket.create_connection') as connect,patch('src.core.supervision.urllib.request.build_opener',return_value=opener):
            report=collect(self.cfg)
        targets=[call.args[0] for call in connect.call_args_list]
        self.assertIn(('api.example',8443),targets);self.assertNotIn(('127.0.0.1',3425),targets)
        self.assertIn('model_api',report['checks']);self.assertNotIn('magpie',report['checks'])


class ModelApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.cfg=load(self.root/'absent.json');self.seen=[];self.reply=None;self.model_reply=None
        async def models(r):
            self.seen.append((r.method,r.path,r.headers.get('Authorization'),None))
            if self.model_reply is not None:return self.model_reply()
            return web.json_response({'data':[{'id':'fixture-text'},{'id':'fixture-vision'}]})
        async def complete(r):
            self.seen.append((r.method,r.path,r.headers.get('Authorization'),await r.json()))
            if self.reply is not None:return self.reply()
            return web.json_response({'choices':[{'message':{'role':'assistant','content':'夹具回复','tool_calls':[{'id':'t','type':'function','function':{'name':'remember','arguments':'{}'}}]}}],'usage':{'total_tokens':3}})
        self.redirected=0
        async def destination(r):self.redirected+=1;return web.json_response({})
        app=web.Application();app.router.add_get('/custom/v1/models',models);app.router.add_post('/custom/v1/chat/completions',complete);app.router.add_get('/redirected',destination)
        self.server=TestServer(app);await self.server.start_server();self.addAsyncCleanup(self.server.close)
        self.cfg['model'].update(provider='openai_compatible',base_url=str(self.server.make_url('/custom/v1/')),main='fixture-text',auxiliary='fixture-vision',key_env='HARNESS_FIXTURE_API_KEY')
        self.session=aiohttp.ClientSession();self.addAsyncCleanup(self.session.close)
        self.store=Store(self.root/'logs');self.model=Model(self.cfg['model'],self.session,Log(self.store,('HARNESS_FIXTURE_API_KEY',)))

    async def test_actual_compatible_requests_preserve_tools_images_and_usage(self):
        messages=[{'role':'user','content':[{'type':'text','text':'看看这张图'},{'type':'image_url','image_url':{'url':'data:image/png;base64,fixture'}}]}]
        tools=[{'type':'function','function':{'name':'remember','parameters':{'type':'object'}}}]
        with patch.dict(os.environ,{'HARNESS_FIXTURE_API_KEY':'fixture-only-credential'}):
            self.assertEqual(len(await self.model.models()),2)
            answer=await self.model.complete(messages,tools,auxiliary=True)
        self.assertEqual(answer['tool_calls'][0]['function']['name'],'remember')
        self.assertEqual([r[1] for r in self.seen],['/custom/v1/models','/custom/v1/chat/completions'])
        self.assertTrue(all(r[2]=='Bearer fixture-only-credential' for r in self.seen))
        body=self.seen[-1][3];self.assertEqual(body['model'],'fixture-vision');self.assertEqual(body['messages'],messages);self.assertEqual(body['tools'],tools)
        self.assertEqual(self.store.latest('events')['usage']['total_tokens'],3)

    async def test_optional_auth_and_no_fallback_to_magpie(self):
        with patch.dict(os.environ,{'HARNESS_FIXTURE_API_KEY':''}):await self.model.complete([{'role':'user','content':'hi'}])
        self.assertIsNone(self.seen[0][2])
        self.model_reply=lambda:web.Response(status=503,text='down')
        with self.assertRaisesRegex(RuntimeError,'503'):await self.model.models()
        self.assertEqual(len(self.seen),2)

    async def test_error_raw_is_redacted_but_diagnostic_and_redirect_never_followed(self):
        self.reply=lambda:web.Response(status=401,text='denied fixture-only-credential')
        with patch.dict(os.environ,{'HARNESS_FIXTURE_API_KEY':'fixture-only-credential'}):
            with self.assertRaisesRegex(RuntimeError,'密钥环境变量'):await self.model.complete([])
        row=self.store.latest('events');self.assertEqual(row['status'],401);self.assertIn('[REDACTED]',row['raw']);self.assertNotIn('fixture-only-credential',row['raw'])
        self.model_reply=lambda:web.Response(status=302,headers={'Location':str(self.server.make_url('/redirected'))})
        with self.assertRaisesRegex(RuntimeError,'302'):await self.model.models()
        self.assertEqual(self.redirected,0)

    async def test_bad_json_shape_and_large_response_are_actionable(self):
        self.model_reply=lambda:web.Response(text='<html>not an API</html>')
        with self.assertRaisesRegex(RuntimeError,'JSON'):await self.model.models()
        self.model_reply=lambda:web.json_response({'models':[]})
        with self.assertRaisesRegex(RuntimeError,'手动'):await self.model.models()
        self.reply=lambda:web.json_response({'choices':[]})
        with self.assertRaisesRegex(RuntimeError,'不兼容'):await self.model.complete([])
        self.cfg['model']['max_response_bytes']=1024;self.model_reply=lambda:web.Response(text='x'*2048)
        with self.assertRaisesRegex(RuntimeError,'大小上限'):await self.model.models()

    async def test_local_probe_uses_unsaved_draft_without_sending_chat_or_changing_mode(self):
        defaults=load(self.root/'absent.json')
        with patch('src.core.harness.ROOT',self.root):h=Harness(defaults,self.session)
        h.set_safety('paused')
        self.addAsyncCleanup(h.close)
        client=TestClient(TestServer(build(h,asyncio.Event())));await client.start_server();self.addAsyncCleanup(client.close)
        headers={'Host':'127.0.0.1:8765','X-Harness-Local':'1'}
        body={key:self.cfg['model'][key] for key in ('provider','base_url','key_env')}
        denied=await client.post('/api/model-connection',headers={'Host':'127.0.0.1:8765'},json=body)
        self.assertEqual(denied.status,403)
        before=copy.deepcopy(h.cfg)
        with patch.dict(os.environ,{'HARNESS_FIXTURE_API_KEY':'fixture-only-credential'}):
            response=await client.post('/api/model-connection',headers=headers,json=body)
            self.assertEqual(response.status,200,await response.text());result=await response.json()
        self.assertTrue(result['ok']);self.assertTrue(result['key_present']);self.assertNotIn('fixture-only-credential',json.dumps(result))
        self.assertEqual(h.cfg,before);self.assertEqual(h.safety.mode,'paused');self.assertEqual(self.seen[0][0],'GET')
        self.assertEqual(len(self.seen),1)
        bad=await client.post('/api/model-connection',headers=headers,json=dict(body,api_key='not-allowed'))
        self.assertEqual(bad.status,400)
