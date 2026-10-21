import asyncio
import base64
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock,patch
import aiohttp
from aiohttp.test_utils import TestClient,TestServer
from PIL import Image
from src.core.config import load,validate
from src.core.identity import Identity
from src.core.store import Store
from src.core.harness import Harness
from src.core.desktop_api import DesktopApi
from src.modules.role import Role
from src.channel.local_ui import build
from tools import manage


def picture(color='red',size=(160,80),fmt='PNG'):
    out=io.BytesIO();Image.new('RGB',size,color).save(out,format=fmt)
    return 'data:image/'+fmt.lower()+';base64,'+base64.b64encode(out.getvalue()).decode()


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cfg=load(self.root/'absent.json')
        self.store=Store(self.root/'data');self.identity=Identity(self.cfg['identity'],self.store,self.root)
        (self.root/'assets').mkdir();Image.new('RGB',(32,32),'blue').save(self.identity.default_path())
        Image.new('RGB',(32,32),'blue').save(self.identity.default_path('ico'))
        (self.root/'config').mkdir();(self.root/'config/settings.json').write_text('{}')

    def save(self,**images):
        return self.identity.save('测试鱼','蓝色头发，说话自然。',self.identity.profile()['revision'],**images)

    def test_independent_images_metadata_removed_and_multisize_icon_preserves_aspect(self):
        p=self.save(portrait=picture('red'),icon=picture('green'))
        self.assertNotEqual(p['portrait_id'],p['icon_id'])
        with Image.open(self.identity.image_path('portrait')) as image:
            self.assertEqual(image.size,(160,80));self.assertEqual(image.info,{})
        with Image.open(self.identity.image_path('icon')) as image:
            self.assertEqual(image.size,(256,256));self.assertEqual(image.getpixel((0,0))[3],0)
        with Image.open(self.identity.image_path('icon','ico')) as image:
            self.assertTrue({(16,16),(32,32),(256,256)}<=image.ico.sizes())
        self.assertEqual(self.identity.title(),'测试鱼 · QQ ChatBot')
        self.assertEqual(p['nickname'],'测试鱼')
        self.assertEqual(p['product_name'],'QQ ChatBot')
        self.assertEqual(p['defaults']['nickname'],'大肥鱼')

    def test_conflict_and_invalid_files_cannot_replace_saved_identity(self):
        first=self.save(portrait=picture())
        with self.assertRaisesRegex(ValueError,'变化'):
            self.identity.save('过期','', 'default',icon=picture())
        for invalid in ('data:image/svg+xml;base64,PHN2Zz4=',picture(fmt='GIF'),'data:image/png;base64,YWJj'):
            with self.subTest(invalid=invalid[:30]),self.assertRaises(ValueError):self.save(icon=invalid)
        self.assertEqual(self.identity.profile()['revision'],first['revision'])
        self.cfg['identity']['max_pixels']=100
        with self.assertRaisesRegex(ValueError,'像素'):self.save(icon=picture())
        with self.assertRaises(ValueError):self.save(icon='x'*3000000)

    def test_reset_and_backup_restore_include_profile_and_assets(self):
        first=self.save(portrait=picture(),icon=picture('green'))
        with patch.object(manage,'ROOT',self.root):
            snapshot=manage.backup(self.cfg)
            reset=self.identity.save('大肥鱼','',''+first['revision'],portrait=None,icon=None)
            self.assertIsNone(reset['icon_id']);self.assertIsNone(reset['portrait_id'])
            self.assertEqual(self.identity.image_path('icon'),self.identity.default_path())
            manage.restore(self.cfg,snapshot)
        self.assertEqual(self.identity.profile()['revision'],first['revision'])
        self.assertTrue(self.identity.image_path('icon','ico').is_file())

    def test_next_role_prompt_uses_current_name_without_changing_permissions(self):
        (self.root/'src/persona').mkdir(parents=True)
        (self.root/'src/persona/role.md').write_text('旧名字大肥鱼',encoding='utf-8')
        role=Role(self.cfg['role'],self.root,self.store,self.identity)
        self.save()
        self.assertIn('昵称以此处为准',role.prompt());self.assertIn('测试鱼',role.prompt())
        self.assertFalse(self.cfg['role']['evolution_enabled'])

    def test_paths_and_limits_cannot_escape_or_expose_arbitrary_file(self):
        for key,value in (('asset_dir','../../outside'),('default_image','config/settings.json'),('max_image_bytes',3000000)):
            cfg=load(self.root/'absent.json');cfg['identity'][key]=value
            with self.assertRaises(ValueError):validate(cfg)
        self.identity.cfg=dict(self.cfg['identity'],default_image='config/settings.json')
        with self.assertRaises(ValueError):self.identity.snapshot()
        with self.assertRaises(ValueError):self.identity.asset('icon','../file')

    def test_desktop_bridge_only_allows_identity_revision_query(self):
        isolation=patch('src.core.desktop_api.ROOT',self.root);isolation.start();self.addCleanup(isolation.stop)
        backend=Mock();api=DesktopApi(backend)
        api.request('identity?revision=default')
        backend.request.assert_called_once_with('identity?revision=default',None)
        with self.assertRaises(PermissionError):api.request('identity?file=config/local.json')
        with self.assertRaises(PermissionError):api.request('identity?revision=x&path=x')
        api.request('identity',{'nickname':'测试鱼','appearance':'','expected_revision':'default'})


class IdentityApiTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cfg=load(self.root/'absent.json')
        self.patcher=patch('src.core.harness.ROOT',self.root);self.patcher.start();self.addCleanup(self.patcher.stop)
        self.session=aiohttp.ClientSession();self.h=Harness(self.cfg,self.session)
        self.client=TestClient(TestServer(build(self.h,asyncio.Event())));await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close();await self.h.close();await self.session.close()

    async def test_save_requires_local_header_preserves_pause_and_revision_detects_external_changes(self):
        self.h.set_safety('paused');headers={'Host':'127.0.0.1:8765','X-Harness-Local':'1'}
        body={'nickname':'测试鱼','appearance':'蓝色头发','expected_revision':'default','icon':picture()}
        denied=await self.client.post('/api/identity',headers={'Host':'127.0.0.1:8765'},json=body)
        self.assertEqual(denied.status,403)
        response=await self.client.post('/api/identity',headers=headers,json=body)
        self.assertEqual(response.status,200,await response.text());saved=await response.json()
        same=await (await self.client.get('/api/identity?revision='+saved['revision'],headers=headers)).json()
        self.assertEqual(same,{'unchanged':True});self.assertEqual(self.h.safety.mode,'paused')
        conflict=await self.client.post('/api/identity',headers=headers,json=body)
        self.assertEqual(conflict.status,400)
        bad=await self.client.post('/api/identity',headers=headers,json=dict(body,path='file'))
        self.assertEqual(bad.status,400)
        self.assertNotIn('测试鱼',str(self.h.log.store.read('events')))
