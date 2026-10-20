"""隔离 WebView2 群监听验收；协议夹具，不连接真实 QQ、不发消息或调用模型。"""
import asyncio
import copy
import json
import socket
import subprocess
import sys
import time
import urllib.request
import uuid
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.core.config import ROOT, load, merge, validate
from src.core.runtime_paths import python_command


def serve(run):
    import aiohttp
    from aiohttp import web
    from src.core.harness import Harness
    from src.channel.local_ui import build

    async def main():
        cfg = load(ROOT / '.runtime/absent-group-qa.json')
        cfg['paths'] = {k: (run / k).as_posix() for k in ('data', 'logs', 'backups')}
        cfg['owner']['qq_id'] = '12345'; cfg['qq'].update(enabled=True, bot_id='54321')
        cfg['safety']['mode'] = 'reply_only'
        sock = socket.socket(); sock.bind(('127.0.0.1', 0)); cfg['server']['port'] = sock.getsockname()[1]

        def save(patch):
            candidate = copy.deepcopy(cfg); merge(candidate, patch); validate(candidate); cfg.update(candidate)
            (ROOT / run / 'saved-config.json').write_text(json.dumps(cfg, ensure_ascii=False), encoding='utf-8')

        async with aiohttp.ClientSession() as session:
            h = Harness(cfg, session); h.qq.connected = h.qq.online = True

            async def forbidden(*args, **kw):
                (ROOT / run / 'forbidden-called').touch(); raise AssertionError('监听不应调用外部能力')

            h.model.complete = h.qq.action = forbidden

            async def fixture(request):
                a = await request.json()
                if 'event' in a:await h.qq.ingest(a['event'])
                if 'online' in a:h.qq.connected = h.qq.online = a['online']
                return web.json_response({'ok': True})

            with patch('src.channel.local_ui.load', lambda: copy.deepcopy(cfg)), patch('src.channel.local_ui.save_local', save):
                app = build(h, asyncio.Event()); app.router.add_post('/api/fixture-group', fixture)
                runner = web.AppRunner(app); await runner.setup(); await web.SockSite(runner, sock).start()
                (ROOT / run / 'ready.json').write_text(json.dumps({'port': cfg['server']['port']}))
                try:
                    while not (ROOT / run / 'stop').exists():await asyncio.sleep(.1)
                finally:await h.close(); await runner.cleanup()

    asyncio.run(main())


if '--serve' in sys.argv:
    run = Path(sys.argv[-1])
    if not (ROOT / run).resolve().is_relative_to(ROOT / '.runtime') or not run.name.startswith('group-monitor-qa-'):
        raise ValueError('隔离路径无效')
    serve(run); sys.exit(0)

import webview
from src.core.desktop_api import DesktopApi
from src.core.desktop_assets import DesktopAssets

run = Path('.runtime') / ('group-monitor-qa-' + uuid.uuid4().hex[:10]); (ROOT / run).mkdir(parents=True)
child = subprocess.Popen([python_command(), __file__, '--serve', str(run)], cwd=ROOT,
                         creationflags=subprocess.CREATE_NO_WINDOW, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
deadline = time.monotonic() + 15
while not (ROOT / run / 'ready.json').is_file():
    if child.poll() is not None or time.monotonic() > deadline:raise RuntimeError('群监听夹具服务未启动')
    time.sleep(.1)
port = json.loads((ROOT / run / 'ready.json').read_text())['port']
cfg = load(ROOT / '.runtime/absent-group-qa.json')


class Backend:
    def request(self, path, body=None, **kw):
        req = urllib.request.Request(f'http://127.0.0.1:{port}/api/' + path,
                                     data=None if body is None else json.dumps(body).encode(),
                                     headers={'Content-Type': 'application/json', 'X-Harness-Local': '1'})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=10) as r:return json.load(r)


class Api(DesktopApi):
    def __init__(self):super().__init__(Backend()); self.state = {}
    def ui_state(self, patch=None):
        if patch:self.state.update(patch)
        return self.state
    def runtime(self):return {'desktop': True, 'version': 'QA'}
    def preferences(self, patch=None):return {'settings': cfg['desktop'], 'startup': {'supported': False, 'registered': False}, 'version': 'QA'}
    def maintenance(self, *args):return []
    def events(self):return []
    def read_data(self, stream):return []
    def onboarding(self, action='status', body=None):return {'configured': True}


backend = Backend()
window = webview.create_window('QQ ChatBot 群监听验收', url=DesktopAssets(), js_api=Api(), width=1280, height=820, hidden=True)
result = {'ok': False}


def until(expression):
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        if window.evaluate_js(expression):return
        time.sleep(.1)
    raise RuntimeError('界面条件超时：' + expression)


def js(code):return window.evaluate_js(code)


def refresh():
    js("document.querySelector('#group-refresh').click()")
    time.sleep(.35)


def inject(ident, mid, text):
    backend.request('fixture-group', {'event': {'post_type': 'message', 'message_type': 'group', 'group_id': ident,
                    'message_id': mid, 'user_id': '33333', 'sender': {'card': '群成员甲', 'user_id': '33333'},
                    'time': 1792496100, 'message': [{'type': 'text', 'data': {'text': text}},
                                                  {'type': 'image', 'data': {'url': 'https://never-download.invalid'}}]}})


def check():
    try:
        window.events.loaded.wait(20)
        until('!!window.DFY?.state.cfg && !!window.GroupMonitorUI')
        js("document.querySelector('[data-nav=groups]').click()")
        until("document.querySelector('#group-connection').textContent.includes('QQ 已连接')")
        for ident, name in (('11111', '游戏群'), ('22222', '学习群')):
            js("document.querySelector('#group-add').click()")
            js('document.querySelector("#group-number").value=' + json.dumps(ident) + ';document.querySelector("#group-name").value=' + json.dumps(name) + ';document.querySelector("#group-form").requestSubmit()')
            until("!document.querySelector('#group-dialog').open")
        until("document.querySelectorAll('.group-tab').length===2")
        inject('11111', 'a1', '游戏群第一条 <script>window.pwned=true</script>')
        inject('22222', 'b1', '学习群独立消息')
        inject('99999', 'secret', '未订阅消息不能出现')
        js("document.querySelector('[data-group-layout=grid]').click()")
        until("document.querySelectorAll('.group-pane:not([hidden])').length===2 && document.querySelector('#group-windows').textContent.includes('学习群独立消息')")
        assert '游戏群第一条' in js("document.querySelector('[data-group-id=\"11111\"] .group-message-list').textContent")
        assert '学习群独立消息' not in js("document.querySelector('[data-group-id=\"11111\"] .group-message-list').textContent")
        assert not js('!!window.pwned')
        assert not js("document.querySelector('#group-windows').textContent.includes('未订阅消息')")
        # 备注编辑、停用后不采集；全局全部暂停只限制输出，不触发监听副作用。
        js("document.querySelector('[data-group-id=\"11111\"] .group-pane-tools .text-button').click()")
        js("document.querySelector('#group-name').value='游戏与闲聊';document.querySelector('#group-form').requestSubmit()")
        until("!document.querySelector('#group-dialog').open && document.querySelector('#group-windows').textContent.includes('游戏与闲聊')")
        js("document.querySelector('[data-group-id=\"11111\"] .group-pane-tools button').click()")
        until("document.querySelector('[data-group-id=\"11111\"] header small').textContent.includes('已停用')")
        inject('11111', 'a2', '停用期间不能采集'); refresh()
        assert not js("document.querySelector('#group-windows').textContent.includes('停用期间不能采集')")
        backend.request('fixture-group', {'online': False}); refresh()
        until("document.querySelector('#group-connection').textContent.includes('QQ 未连接')")
        from System import Action, Func, Object
        from System.Drawing import Size
        from System.IO import FileStream, FileMode
        from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
        window.native.Invoke(Action(lambda: window.native.Show()))
        for theme in ('light', 'dark'):
            js('window.SystemUI.appearance(' + json.dumps(dict(cfg['desktop'], theme=theme)) + ')'); time.sleep(.3)
            assert not js('document.documentElement.scrollWidth>innerWidth+2')
            assert js("getComputedStyle(document.querySelector('.group-pane')).backgroundColor===getComputedStyle(document.querySelector('.panel')).backgroundColor")
            control = window.native.webview; stream = FileStream(str(ROOT / run / f'group-monitor-{theme}.png'), FileMode.Create)
            try:
                task = control.Invoke(Func[Object](lambda: control.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png, stream)))
                assert task.Wait(10000)
            finally:stream.Dispose()
        scale = window.native._scale
        window.native.Invoke(Action(lambda: setattr(window.native, 'Size', Size(int(940 * scale), int(650 * scale)))))
        time.sleep(.3); assert not js('document.documentElement.scrollWidth>innerWidth+2')
        # 单窗切换；移除保留本机历史。
        js("document.querySelector('[data-group-layout=single]').click();document.querySelector('.group-tab').click()")
        until("document.querySelectorAll('.group-pane:not([hidden])').length===1")
        js("document.querySelector('[data-group-id=\"11111\"] .group-pane-tools button:last-child').click()")
        until("document.querySelector('#group-remove-dialog').open")
        js("document.querySelector('#group-remove-confirm').click()")
        until("document.querySelectorAll('.group-tab').length===1")
        assert (ROOT / run / 'data/groups/11111/monitor.jsonl').exists()
        assert not (ROOT / run / 'forbidden-called').exists()
        assert not (ROOT / run / 'data/chat.jsonl').exists()
        result.update(ok=True, multi_window=True, single_switch=True, whitelist=True, scope_isolation=True,
                      edit_and_disable=True, remove_retains_history=True, no_model_or_send=True,
                      html_is_text=True, offline_status=True, light_dark_and_narrow=True)
    except Exception as error:result['error'] = str(error)
    finally:window.destroy()


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:webview.start(check, gui='edgechromium', private_mode=True, debug=False)
    finally:(ROOT / run / 'stop').touch(); child.wait(15)
    (ROOT / run / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(dict(result, folder=str(ROOT / run)), ensure_ascii=False, indent=2))
    sys.exit(0 if result['ok'] else 1)
