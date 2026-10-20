"""Lifecycle and exact-runtime checks; no real QQ, login files or network calls."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.core.native_host import NativeHost, atomic, runtime


class NativeHostTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.directory = self.root / '.runtime/qq-native'
        self.directory.mkdir(parents=True)
        self.exe = self.root / '.runtime/native-host/QQChatBot.NativeHost.exe'
        self.exe.parent.mkdir(parents=True)
        self.exe.touch()
        self.actual = {'image': str(self.exe), 'created': 1234}
        self.record = dict(self.actual, pid=123, run_id='a' * 32)
        atomic(self.directory / 'process.json', self.record)
        self.host = NativeHost(self.root)

    def test_stale_pid_and_foreign_image_never_owned_or_stopped(self):
        for actual in (None, dict(self.actual, created=4321), dict(self.actual, image=str(self.root/'other.exe'))):
            with self.subTest(actual=actual), patch('src.core.native_host._process', return_value=actual):
                self.assertIsNone(self.host.owned())
                self.assertEqual(self.host.status()['phase'], 'not_running')
                self.host.control('stop')
                self.assertFalse((self.directory/'control.json').exists())

    def test_only_current_run_can_report_online(self):
        with patch('src.core.native_host._process', return_value=self.actual):
            for value in ({'schema':'qq-chatbot.native.v1','run_id':'a'*32,'phase':'ready','online':True},
                          {'schema':'qq-chatbot.native.v2','run_id':'b'*32,'phase':'ready','online':True}):
                atomic(self.directory/'state.json', value)
                self.assertFalse(self.host.status()['online'])
            atomic(self.directory/'state.json', {'schema':'qq-chatbot.native.v2','run_id':'a'*32,'phase':'ready','online':True})
            self.assertTrue(self.host.status()['online'])
            self.host.control('refresh_qr')
            self.assertEqual(json.loads((self.directory/'control.json').read_text())['run_id'], 'a'*32)

    def test_runtime_hash_and_directory_are_required_without_modification(self):
        compat = {'version':'fixture','sha256':{'QQNT.dll':hashlib.sha256(b'official').hexdigest()}}
        (self.root/'config').mkdir()
        atomic(self.root/'config/qq-native-compat.json',compat)
        client=self.root/'.runtime/qq-client/versions/fixture'
        package=client/'resources/app/package.json'
        package.parent.mkdir(parents=True)
        atomic(package,{'version':'fixture','main':'./application.asar/app_launcher/index.js'})
        (client/'QQNT.dll').write_bytes(b'official')
        original=package.read_bytes()
        self.assertEqual(runtime(self.root)[0],client)
        (client/'QQNT.dll').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'校验失败'):runtime(self.root)
        self.assertEqual(package.read_bytes(),original)
        (self.root/'.runtime/qq-client/versions/fixture').rename(self.root/'.runtime/qq-client/versions/other')
        with self.assertRaisesRegex(ValueError,'目录'):runtime(self.root)


if __name__ == '__main__':
    unittest.main()
