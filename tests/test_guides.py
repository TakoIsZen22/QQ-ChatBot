import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.core.guides import read_guide
from src.core.desktop_api import DesktopApi
from src.core.edition import capabilities

MAGPIE=capabilities()['providers']


class GuideTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        (self.root/'docs/assets').mkdir(parents=True)
        (self.root/'docs/MAGPIE_SETUP.md').write_bytes('# Magpie 可选\r\n\r\n## 标题\r\n公开教程\r\n'.encode())
        (self.root/'docs/MODEL_API.md').write_text('# 自有 API\n无需 Magpie',encoding='utf-8')
        (self.root/'docs/GROUP_MONITOR.md').write_text('# 群聊\n默认仅监听，逐群开启回复',encoding='utf-8')
        (self.root/'docs/assets/magpie-quickstart.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
        (self.root/'config').mkdir();(self.root/'config/local.json').write_text('PRIVATE-NOT-A-GUIDE')

    def test_only_fixed_public_guides_are_readable_without_core_or_network(self):
        # 桌面帮助在核心未启动时也可用，不加载配置或读取环境变量。
        with patch('src.core.desktop_api.ROOT',self.root),patch('src.core.desktop_api.load',side_effect=AssertionError('must not load private config')):
            guide=DesktopApi.guide(object(),'api')
        self.assertEqual(guide['file_target'],'model_api_guide');self.assertIn('无需 Magpie',guide['text'])
        self.assertNotIn('\r',guide['text'])
        self.assertIsNone(read_guide(self.root,'api')['image_data'])
        group=read_guide(self.root,'groups')
        self.assertEqual(group['file_target'],'group_guide')
        self.assertIn('逐群开启回复',group['text'])
        for name in ('../config/local.json','config/local.json','https://example.com','',None,{}):
            with self.subTest(name=name),self.assertRaises(ValueError):read_guide(self.root,name)

    def test_magpie_guide_is_readable_only_in_editions_that_support_magpie(self):
        # Magpie 教程只在支持 Magpie 的版本里可读；1.10.01 必须在读文件前就拒绝。
        if 'magpie' in MAGPIE:
            guide=read_guide(self.root,'magpie')
            self.assertEqual(guide['file_target'],'magpie_guide');self.assertIn('公开教程',guide['text'])
            self.assertNotIn('\r',guide['text']);self.assertIn('\n## 标题\n',guide['text'])
            self.assertTrue(guide['image_data'].startswith('data:image/svg+xml;base64,'))
        else:
            with self.assertRaisesRegex(ValueError,r'1\.10\.02'):
                read_guide(self.root,'magpie')

    def test_oversized_public_file_is_rejected_and_private_content_is_never_used(self):
        (self.root/'docs/MODEL_API.md').write_text('x'*131073)
        with self.assertRaisesRegex(ValueError,'大小'):read_guide(self.root,'api')
        self.assertEqual((self.root/'config/local.json').read_text(),'PRIVATE-NOT-A-GUIDE')
