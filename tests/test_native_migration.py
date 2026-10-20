"""Retiring an external transport must preserve local identity and safety."""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.core import config
from src.core.desktop_api import DesktopApi


class NativeMigrationTests(unittest.TestCase):
    def test_old_fields_removed_without_changing_identity_model_or_pause(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);(root/'config').mkdir()
            default=config.load(root/'missing')
            (root/'config/settings.json').write_text(json.dumps(default))
            local={'owner':{'name':'测试者','qq_id':'11111'},
                   'qq':{'enabled':True,'bot_id':'22222','http_url':'http://127.0.0.1:3000',
                         'ws_url':'ws://127.0.0.1:3001','token_env':'LEGACY_BRIDGE_KEY','history_limit':20},
                   'model':{'main':'fixture'},'safety':{'mode':'paused'}}
            path=root/'config/local.json';path.write_text(json.dumps(local))
            before=path.read_bytes()
            with patch.object(config,'ROOT',root):
                loaded=config.load()
                self.assertEqual(path.read_bytes(),before)  # read-only checks never mutate
                self.assertEqual(loaded['owner'],local['owner'])
                self.assertEqual(loaded['model']['main'],'fixture')
                self.assertEqual(loaded['safety']['mode'],'paused')
                self.assertEqual(loaded['qq']['native_port'],3002)
                config.save_local({})
            saved=json.loads(path.read_text())
            self.assertEqual(saved['qq'],{'enabled':True,'bot_id':'22222'})
            self.assertEqual(saved['owner'],local['owner'])
            self.assertEqual(saved['safety']['mode'],'paused')

    def test_old_qr_files_cannot_appear_as_native_login(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);folder=root/'.runtime/qq-native';folder.mkdir(parents=True)
            (folder/'qrcode.png').write_bytes(b'\x89PNG\r\n\x1a\nold')
            (folder/'state.json').write_text(json.dumps({'schema':'qq-chatbot.native.v1','phase':'offline','online':False}))
            with patch('src.core.desktop_api.ROOT',root):
                result=DesktopApi().qr()
            self.assertEqual(result['state'],'unavailable')
            self.assertNotIn('data_url',result)
