"""隔离数据的真实WebView人设编辑验收，不调用模型或触碰正式人设。"""
import asyncio
import json
import socket
import sys
import subprocess
import time
import urllib.request
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.config import ROOT,load
from src.core.desktop_api import DesktopApi
from src.core.desktop_assets import DesktopAssets
from src.core.store import Store
from src.core.identity import Identity
from src.core.desktop_lifecycle import DesktopLifecycle
from src.modules.role import Role


def server(run):
    import aiohttp
    from aiohttp import web
    from src.core.harness import Harness
    from src.channel.local_ui import build
    async def serve():
        cfg=load(ROOT/'.runtime/no-soul-qa-local.json')
        cfg['paths']={name:(run/name).as_posix() for name in ('data','logs','backups')}
        sock=socket.socket();sock.bind(('127.0.0.1',0));cfg['server']['port']=sock.getsockname()[1]
        async with aiohttp.ClientSession() as session:
            h=Harness(cfg,session);runner=web.AppRunner(build(h,asyncio.Event()));await runner.setup()
            await web.SockSite(runner,sock).start()
            (ROOT/run/'ready.json').write_text(json.dumps({'port':cfg['server']['port']}))
            while not (ROOT/run/'stop').exists():await asyncio.sleep(.1)
            await runner.cleanup();await h.close()
    asyncio.run(serve())


if '--serve' in sys.argv:
    run=Path(sys.argv[sys.argv.index('--serve')+1])
    if not (ROOT/run).resolve().is_relative_to(ROOT/'.runtime') or not run.name.startswith('soul-qa-'):
        raise ValueError('隔离测试目录无效')
    server(run);sys.exit(0)

import webview

cfg=load(ROOT/'.runtime/no-soul-qa-local.json')
run=Path('.runtime')/('soul-qa-'+uuid.uuid4().hex[:10])
cfg['paths']={name:(run/name).as_posix() for name in ('data','logs','backups')}
(ROOT/run).mkdir(parents=True,exist_ok=True)
child=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),str(Path(__file__).resolve()),'--serve',run.as_posix()],
    cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
deadline=time.monotonic()+10
while not (ROOT/run/'ready.json').exists():
    if child.poll() is not None or time.monotonic()>deadline:raise RuntimeError('隔离服务启动失败')
    time.sleep(.1)
cfg['server']['port']=json.loads((ROOT/run/'ready.json').read_text())['port']
store=Store(ROOT/cfg['paths']['data']);identity=Identity(cfg['identity'],store,ROOT)
role=Role(cfg['role'],ROOT,store,identity);result={'ok':False}


class Backend:
    def request(self,path,body=None,**kwargs):
        if path=='config':return cfg
        payload=None if body is None else json.dumps(body,ensure_ascii=False).encode()
        request=urllib.request.Request(f'http://127.0.0.1:{cfg["server"]["port"]}/api/'+path,
            data=payload,headers={'Content-Type':'application/json','X-Harness-Local':'1'})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request,timeout=5) as response:return json.load(response)


class Api(DesktopApi):
    def __init__(self):super().__init__(Backend());self.state={}
    def ui_state(self,patch=None):
        if patch:self.state.update(patch)
        return self.state
    def runtime(self):return {'desktop':True,'version':'QA','poll_interval_ms':2000}
    def preferences(self,patch=None):return {'settings':cfg['desktop'],'startup':{'supported':False,'registered':False},'version':'QA'}
    def maintenance(self,*args):return []
    def events(self):return []
    def read_data(self,stream):return []
    def refresh_identity(self):return self._lifecycle.apply_identity(force=True,identity=identity,register=False)


api=Api();life=DesktopLifecycle(api)
window=webview.create_window('QQ ChatBot 专属人设验收',url=DesktopAssets(),js_api=api,width=1280,height=820,hidden=True)
life.window=window


def until(expression):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        if window.evaluate_js(expression):return
        time.sleep(.1)
    raise RuntimeError('界面条件超时: '+expression)


def edit(text):
    window.evaluate_js("(()=>{const e=document.querySelector('#soul-editor');e.value="+json.dumps(text)+";e.dispatchEvent(new Event('input',{bubbles:true}));})()")


def check():
    try:
        result['stage']='initial_load'
        window.events.loaded.wait(20);until('!!window.DFY?.state.cfg')
        window.evaluate_js("window.DFY.navigate('soul')")
        until("!document.querySelector('#soul-editor').disabled")
        result['stage']='identity_save'
        until("!!window.DFY.state.identity")
        life._start_tray()
        # 实际 FileReader/upload 处理与原生图标更新，全部写入隔离 data。
        window.evaluate_js("(()=>{for(const [id,text]of [['#identity-nickname','验收鱼'],['#identity-description','戴围巾的蓝发女孩']]){const e=document.querySelector(id);e.value=text;e.dispatchEvent(new Event('input',{bubbles:true}))}for(const kind of ['portrait','icon']){const canvas=document.createElement('canvas');canvas.width=180;canvas.height=90;const c=canvas.getContext('2d');c.fillStyle=kind==='icon'?'#45a58b':'#5478e5';c.fillRect(0,0,180,90);const data=atob(canvas.toDataURL('image/png').split(',')[1]);const bytes=Uint8Array.from(data,c=>c.charCodeAt(0));const dt=new DataTransfer();dt.items.add(new File([bytes],kind+'.png',{type:'image/png'}));const input=document.querySelector('#identity-'+kind+'-file');input.files=dt.files;input.dispatchEvent(new Event('change',{bubbles:true}))}})()")
        until("document.querySelector('#identity-icon-preview').src.startsWith('data:') && document.querySelector('#identity-portrait-preview').src!==window.DFY.state.identity.portrait_data")
        window.evaluate_js("document.querySelector('#identity-save').click()")
        until("window.DFY.state.identity.nickname==='验收鱼' && !document.querySelector('#identity-save').textContent.includes('保存中')")
        assert '验收鱼' in role.prompt() and '戴围巾' in role.prompt()
        assert window.native.Text=='验收鱼 · QQ ChatBot'
        assert window.native.Icon is not None
        assert life.tray.title=='验收鱼 · QQ ChatBot'
        assert life.tray.icon.getpixel((128,128))[:3]==(69,165,139)
        assert window.evaluate_js("Array.from(document.querySelectorAll('[data-character-name]')).every(e=>e.textContent==='验收鱼')")
        assert window.evaluate_js("document.querySelector('[data-product-name]').textContent==='QQ ChatBot'")
        assert identity.profile()['portrait_id']!=identity.profile()['icon_id']
        first='# 专属测试\n说话温柔。\n<img src=x onerror=alert(1)>'
        result['stage']='save'
        edit(first)
        assert window.evaluate_js("document.querySelector('#soul-preview').querySelectorAll('img').length") == 0
        window.evaluate_js("document.querySelector('#soul-save').click()")
        until("document.querySelector('#soul-dirty').textContent==='专属人设已启用'")
        assert role.soul.current()['text']==first
        assert first in role.prompt()
        edit('# 第二版\n简短自然。')
        result['stage']='restore'
        window.evaluate_js("document.querySelector('#soul-save').click()")
        until("document.querySelector('#soul-dirty').textContent==='专属人设已启用'")
        window.evaluate_js("window.confirm=()=>true;document.querySelectorAll('#soul-history button')[1].click()")
        until("document.querySelector('#soul-editor').value==="+json.dumps(first))
        assert role.soul.current()['text']==first
        draft='还没有保存的个人偏好'
        result['stage']='draft_reload'
        edit(draft);time.sleep(.5)
        assert role.soul.current()['text']==first
        window.evaluate_js('setTimeout(()=>location.reload(),100);true')
        time.sleep(.3)
        until("!!window.DFY?.state.cfg && document.querySelector('#soul-editor').value==="+json.dumps(draft))
        until("document.querySelector('#identity-nickname').value==='验收鱼'")
        until("document.querySelector('#program-version').textContent==='QA'")
        assert window.evaluate_js("document.querySelector('[data-identity-portrait]').src===window.DFY.state.identity.portrait_data")
        from System import Action
        window.native.Invoke(Action(lambda:window.native.Show()))
        for theme in ('dark','light'):
            result['stage']='themes'
            cfg['desktop']['theme']=theme;cfg['desktop']['font_scale']=1.25
            window.evaluate_js('window.SystemUI.appearance('+json.dumps({'theme':theme,'font_scale':1.25})+')')
            time.sleep(.25)
            assert window.evaluate_js('document.documentElement.dataset.theme')==theme,'主题尚未应用'
            assert window.evaluate_js("(()=>{const e=document.querySelector('[data-product-name]');return e.scrollWidth<=e.clientWidth+1})()"),'产品名称被截断'
            assert not window.evaluate_js('document.documentElement.scrollWidth>innerWidth+2')
            from System import Func,Object
            from System.IO import FileStream,FileMode
            from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
            stream=FileStream(str(ROOT/run/('identity-'+theme+'.png')),FileMode.Create)
            try:
                control=window.native.webview
                task=control.Invoke(Func[Object](lambda:control.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream)))
                assert task.Wait(10000)
            finally:stream.Dispose()
        from System import Action
        from System.Drawing import Size
        scale=window.native._scale
        window.native.Invoke(Action(lambda:setattr(window.native,'Size',Size(int(940*scale),int(650*scale)))))
        time.sleep(.3)
        assert not window.evaluate_js('document.documentElement.scrollWidth>innerWidth+2')
        assert window.evaluate_js("(()=>{const e=document.querySelector('[data-product-name]');return e.scrollWidth<=e.clientWidth+1})()"),'窄窗口的产品名称被截断'
        result['stage']='identity_reset'
        window.evaluate_js("document.querySelector('#identity-default').click();document.querySelector('#identity-save').click()")
        until("window.DFY.state.identity.nickname==='大肥鱼' && !document.querySelector('#identity-save').textContent.includes('保存中')")
        assert identity.profile()['icon_id'] is None and identity.profile()['portrait_id'] is None
        assert window.native.Text=='QQ ChatBot'
        result.update(ok=True,native_editor=True,save_and_next_prompt=True,history_restore=True,
                      draft_survives_reload=True,safe_markdown=True,both_themes=True,narrow_window=True,
                      identity_images_and_name=True,native_title_and_icon=True,tray_custom_icon=True,identity_survives_reload=True,identity_reset=True)
    except Exception as error:result['error']=str(error)
    finally:
        if life.tray:life.tray.stop()
        window.destroy()


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    webview.start(check,gui='edgechromium',private_mode=True,debug=False)
    (ROOT/run/'stop').touch();child.wait(10)
    (ROOT/run/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['ok'] else 1)
