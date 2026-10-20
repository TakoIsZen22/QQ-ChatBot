import copy
import hashlib
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from src.core.config import load
from src.version import VERSION
from tools.package_release import ROOT_FILES,build_release


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.cfg = load(self.root/'absent.json')
        for name in ROOT_FILES:
            self.write(name,'public fixture')
        # fixture 必须与被测发行版自洽：版本号取当前发行版，默认接入配置随之匹配。
        self.write('src/version.py',f"VERSION = '{VERSION}'\n")
        self.write('src/persona/role.md','通用角色')
        self.write('config/settings.json',json.dumps(self.cfg))
        self.write('config/local.example.json','{}')
        self.write('config/local.json',json.dumps({'owner':{'qq_id':'12345678901','name':'private-owner'}}))
        for name in ('data/chat.jsonl','logs/events.jsonl','backups/personal.json','config/persona.local.md',
                     '.runtime/qq-native/private-session.json','.git/config','user_plugins/private.py','src/secret.local.py',
                     'src/soul.md','docs/SOUL.md','data/persona/identity.jsonl','data/persona/appearance/icon-private.ico'):
            self.write(name,'DO-NOT-SHARE')

    def write(self,name,text):
        path = self.root/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(text,encoding='utf-8')

    def test_package_is_private_state_free_and_manifest_matches_every_file(self):
        result = build_release(self.root)
        prefix = f'qq-chatbot-{VERSION}/'
        with zipfile.ZipFile(result['path']) as archive:
            manifest = json.loads(archive.read(prefix+'manifest.json'))
            names = set(archive.namelist())-{prefix+'manifest.json'}
            self.assertEqual(names,{prefix+name for name in manifest['files']})
            for name,digest in manifest['files'].items():
                raw = archive.read(prefix+name)
                self.assertEqual(hashlib.sha256(raw).hexdigest(),digest)
                self.assertNotIn(b'DO-NOT-SHARE',raw)
            self.assertNotIn(prefix+'config/local.json',names)
            self.assertNotIn(prefix+'.git/config',names)
        with self.assertRaises(FileExistsError):build_release(self.root)

    def test_personal_field_in_public_source_fails_without_echoing_value(self):
        self.write('src/example.py','user = "12345678901"')
        with self.assertRaises(ValueError) as error:build_release(self.root)
        self.assertIn('src/example.py',str(error.exception))
        self.assertNotIn('12345678901',str(error.exception))
        self.assertFalse((self.root/'dist').exists())

    def test_public_defaults_cannot_ship_configured_accounts_or_permissions(self):
        self.cfg['devices']['enabled'] = True
        self.write('config/settings.json',json.dumps(self.cfg))
        with self.assertRaises(ValueError):build_release(self.root)

    def test_public_package_cannot_preconfigure_a_personal_api_endpoint(self):
        self.cfg['model'].update(provider='openai_compatible',base_url='https://api.example.com/v1')
        self.write('config/settings.json',json.dumps(self.cfg))
        with self.assertRaisesRegex(ValueError,'自定义 API'):build_release(self.root)

    def test_public_package_cannot_include_group_subscriptions(self):
        self.cfg['group_monitor']['groups'] = [{'group_id':'11111','name':'私人群','enabled':False}]
        self.write('config/settings.json',json.dumps(self.cfg))
        with self.assertRaisesRegex(ValueError,'监听群号'):build_release(self.root)
