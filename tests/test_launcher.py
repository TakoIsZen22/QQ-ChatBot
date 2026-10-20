"""Experimental QQ must not launch personal clients or another engine."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.core.config import load
from src.core.desktop_backend import DesktopBackend

class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        root = patch('src.core.desktop_backend.ROOT', self.root)
        root.start()
        self.addCleanup(root.stop)

    def test_unverified_native_client_cannot_launch_or_fall_back(self):
        cfg=load(Path(tempfile.gettempdir())/'missing-qq-config.json');cfg['qq']['enabled']=True
        backend=DesktopBackend()
        with patch('src.core.desktop_backend.load',return_value=cfg),patch.object(backend,'spawn') as spawn:
            with patch('src.core.native_host.NativeHost.start',side_effect=ValueError('缺少自写加载器')),self.assertRaisesRegex(ValueError,'缺少自写加载器'):backend.start_qq()
            spawn.assert_not_called()

    def test_disabled_bridge_keeps_local_chat_and_stop_owns_no_qq(self):
        cfg=load(Path(tempfile.gettempdir())/'missing-qq-config.json')
        with patch('src.core.desktop_backend.load',return_value=cfg):
            self.assertIn('本机聊天',DesktopBackend().start_qq())
        with patch('src.core.desktop_backend.subprocess.run') as run, patch('src.core.native_host.NativeHost') as host:
            DesktopBackend().stop_qq();run.assert_not_called()
            host.assert_called_once_with(self.root)
            host.return_value.control.assert_called_once_with('stop')

    def test_startup_does_not_initiate_qq_login(self):
        backend=DesktopBackend()
        with patch.object(backend,'start_core',return_value='started'),patch.object(backend,'start_qq') as qq:
            backend.start_all(managed=True)
            qq.assert_not_called()
