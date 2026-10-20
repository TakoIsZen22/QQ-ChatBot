"""桌面静态资源：按内容版本加载，并在响应本身禁用持久缓存。"""
import hashlib
import mimetypes
import re
from pathlib import Path
from .config import ROOT


class DesktopAssets:
    def __init__(self, root=None):
        self.root = Path(root or ROOT/'src/channel/ui/desktop').resolve()

    def __call__(self, environ, start_response):
        status, body, mime = '200 OK', b'', 'text/plain; charset=utf-8'
        host = environ.get('HTTP_HOST', '')
        name = environ.get('PATH_INFO', '/').lstrip('/') or 'index.html'
        path = (self.root/name).resolve()
        if host != '127.0.0.1:'+str(environ['SERVER_PORT']):
            status, body = '403 Forbidden', b'Local host required'
        elif environ.get('REQUEST_METHOD') not in ('GET', 'HEAD'):
            status, body = '405 Method Not Allowed', b'Read only'
        elif '\\' in name or not path.is_relative_to(self.root) or not path.is_file():
            status, body = '404 Not Found', b'Not found'
        else:
            body = path.read_bytes()
            mime = mimetypes.guess_type(str(path))[0] or 'application/octet-stream'
            if path == self.root/'index.html':
                html = body.decode('utf-8').replace('<html lang="zh-CN">', '<html lang="zh-CN" data-desktop-host="native">')
                def version(match):
                    attr, asset = match.groups()
                    digest = hashlib.sha256((self.root/asset).read_bytes()).hexdigest()[:16]
                    return f'{attr}="{asset}?v={digest}"'
                html = re.sub(r'(href|src)="(desktop\.css|desktop\.js|stickers\.js|system\.js|soul\.js|soul\.css|identity\.js|identity\.css|model-settings\.js|guides\.js|guides\.css|onboarding\.js|onboarding\.css|agent-work\.js|agent-work\.css|group-monitor\.js|group-monitor\.css)"', version, html)
                body = html.encode('utf-8')
        headers = [('Content-Type', mime), ('Content-Length', str(len(body))),
                   ('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0'),
                   ('Pragma', 'no-cache'), ('Expires', '0'), ('X-Content-Type-Options', 'nosniff')]
        start_response(status, headers)
        return [b'' if environ.get('REQUEST_METHOD') == 'HEAD' else body]
