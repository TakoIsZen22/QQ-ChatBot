import re
import tempfile
import unittest
from pathlib import Path
from src.core.desktop_assets import DesktopAssets


class DesktopAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'ui'
        self.root.mkdir()
        (self.root/'index.html').write_text('<html lang="zh-CN"><link href="desktop.css"><script src="desktop.js"></script></html>', encoding='utf-8')
        (self.root/'desktop.css').write_text('body{background:white}', encoding='utf-8')
        (self.root/'desktop.js').write_text('/* fixture */', encoding='utf-8')
        self.app = DesktopAssets(self.root)

    def request(self, path='/', method='GET', host='127.0.0.1:42001', **extra):
        response = {}
        def start(status, headers):
            response.update(status=status, headers=dict(headers))
        body = b''.join(self.app(dict(REQUEST_METHOD=method, PATH_INFO=path,
            HTTP_HOST=host, SERVER_PORT='42001', **extra), start))
        return response, body

    def test_changed_assets_get_new_urls_and_existing_profiles_cannot_reuse_them(self):
        first, html = self.request()
        first_url = re.search(rb'desktop.css\?v=[a-f0-9]+', html).group()
        (self.root/'desktop.css').write_text('body{background:#192337}', encoding='utf-8')
        second, updated = self.request(HTTP_IF_NONE_MATCH='old', HTTP_IF_MODIFIED_SINCE='old')
        self.assertNotIn(first_url, updated)
        self.assertIn(b'data-desktop-host="native"', updated)
        for result in (first, second):
            self.assertEqual(result['status'], '200 OK')
            self.assertIn('no-store', result['headers']['Cache-Control'])
        result, css = self.request('/desktop.css', HTTP_IF_NONE_MATCH='old')
        self.assertEqual(css, b'body{background:#192337}')
        self.assertEqual(result['status'], '200 OK')
        self.assertIn('no-cache', result['headers']['Cache-Control'])

    def test_head_and_read_only_boundary(self):
        result, body = self.request('/desktop.css', method='HEAD')
        self.assertEqual(body, b'')
        self.assertGreater(int(result['headers']['Content-Length']), 0)
        for args, status in [({'method':'POST'}, '405'), ({'host':'other.example:42001'}, '403'),
                             ({'path':'/../outside'}, '404'), ({'path':'/..\\outside'}, '404')]:
            with self.subTest(args=args):
                result, _ = self.request(**args)
                self.assertTrue(result['status'].startswith(status))


if __name__ == '__main__':
    unittest.main()
