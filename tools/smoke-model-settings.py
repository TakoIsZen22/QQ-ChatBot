"""真实桌面 API 设置验收：使用隔离配置、本机协议夹具，不调用外部模型。"""
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
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.config import ROOT,load,merge,validate
from src.core.desktop_api import DesktopApi
from src.core.desktop_assets import DesktopAssets


def serve(run):
    import aiohttp
    from aiohttp import web
    from src.core.harness import Harness
    from src.channel.local_ui import build
    async def start():
        cfg=load(ROOT/'.runtime/no-model-qa-local.json')
        cfg['paths']={name:(run/name).as_posix() for name in ('data','logs','backups')}
        sock=socket.socket();sock.bind(('127.0.0.1',0));cfg['server']['port']=sock.getsockname()[1]
        async with aiohttp.ClientSession() as session:
            h=Harness(cfg,session);app=build(h,asyncio.Event())
            async def models(request):
                (ROOT/run/'models-requested').touch()
                return web.json_response({'data':[{'id':'qa-text'},{'id':'qa-vision'}]})
            app.router.add_get('/qa/v1/models',models)
            runner=web.AppRunner(app);await runner.setup();await web.SockSite(runner,sock).start()
            (ROOT/run/'ready.json').write_text(json.dumps({'port':cfg['server']['port']}))
            while not (ROOT/run/'stop').exists():await asyncio.sleep(.1)
            await runner.cleanup();await h.close()
    asyncio.run(start())


if '--serve' in sys.argv:
    run=Path(sys.argv[-1])
    if not (ROOT/run).resolve().is_relative_to(ROOT/'.runtime') or not run.name.startswith('model-qa-'):raise ValueError('隔离路径无效')
    serve(run);sys.exit(0)

import webview
run=Path('.runtime')/('model-qa-'+uuid.uuid4().hex[:10]);(ROOT/run).mkdir(parents=True)
child=subprocess.Popen([str(ROOT/'.venv/Scripts/python.exe'),__file__,'--serve',run.as_posix()],cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
deadline=time.monotonic()+10
while not (ROOT/run/'ready.json').is_file():
    if child.poll() is not None or time.monotonic()>deadline:raise RuntimeError('隔离服务未启动')
    time.sleep(.1)
cfg=load(ROOT/'.runtime/no-model-qa-local.json');cfg['paths']={name:(run/name).as_posix() for name in ('data','logs','backups')}
cfg['server']['port']=json.loads((ROOT/run/'ready.json').read_text())['port']


class Backend:
    def request(self,path,body=None,**kwargs):
        if path=='config':
            if body is not None:
                candidate=copy.deepcopy(cfg);merge(candidate,body);validate(candidate);cfg.update(candidate)
                (ROOT/run/'saved-config.json').write_text(json.dumps(cfg),encoding='utf-8')
                return {'saved':True,'restart_required':True}
            return cfg
        data=None if body is None else json.dumps(body).encode()
        req=urllib.request.Request(f'http://127.0.0.1:{cfg["server"]["port"]}/api/'+path,data=data,headers={'Content-Type':'application/json','X-Harness-Local':'1'})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=15) as response:return json.load(response)


class Api(DesktopApi):
    def __init__(self):super().__init__(Backend());self.state={}
    def ui_state(self,patch=None):
        if patch:self.state.update(patch)
        return self.state
    def runtime(self):return {'desktop':True,'version':'QA'}
    def preferences(self,patch=None):return {'settings':cfg['desktop'],'startup':{'supported':False,'registered':False},'version':'QA'}
    def maintenance(self,*args):return []
    def events(self):return []
    def read_data(self,stream):return []


window=webview.create_window('QQ ChatBot API 接入验收',url=DesktopAssets(),js_api=Api(),width=1280,height=820,hidden=True);result={'ok':False}
def until(expression):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        if window.evaluate_js(expression):return
        time.sleep(.1)
    raise RuntimeError('界面条件超时：'+expression)


def check():
    try:
        window.events.loaded.wait(20);until('!!window.DFY?.state.cfg && !!window.ModelUI')
        window.evaluate_js("window.DFY.navigate('settings')")
        assert window.evaluate_js("document.querySelector('#model-provider').value==='magpie' && document.querySelector('#model-base-url').readOnly")
        window.evaluate_js("document.querySelector('[data-guide=magpie]').click()")
        until("document.querySelector('#guide-dialog').open && !!document.querySelector('#guide-content h3')")
        assert window.evaluate_js("document.querySelector('#guide-title').textContent.includes('可选') && document.querySelector('#guide-content').textContent.includes('不使用它')")
        until("document.querySelector('#guide-content img').complete && document.querySelector('#guide-content img').naturalWidth>0")
        window.evaluate_js("document.querySelector('#guide-close').click()")
        assert not (ROOT/run/'saved-config.json').exists()
        base=f'http://127.0.0.1:{cfg["server"]["port"]}/qa/v1/'
        window.evaluate_js("(()=>{const p=document.querySelector('#model-provider');p.value='openai_compatible';p.dispatchEvent(new Event('change',{bubbles:true}));for(const [id,value]of "+json.dumps([['#model-base-url',base],['#model-key-env','HARNESS_QA_UNUSED'],['#model-main','qa-text'],['#model-auxiliary','qa-vision']])+ "){const e=document.querySelector(id);e.value=value;e.dispatchEvent(new Event('input',{bubbles:true}))}document.querySelector('#load-models').click()})()")
        until("document.querySelector('#model-connection-result').textContent.includes('连接成功')")
        assert (ROOT/run/'models-requested').is_file();assert cfg['model']['provider']=='magpie'
        assert not (ROOT/run/'saved-config.json').exists()
        assert window.evaluate_js("document.querySelectorAll('#model-options option').length===2")
        window.evaluate_js("document.querySelector('#settings-form').requestSubmit()")
        until("window.DFY.state.cfg.model.provider==='openai_compatible' && document.querySelector('#settings-note').textContent.includes('已保存')")
        saved=json.loads((ROOT/run/'saved-config.json').read_text());assert saved['model']['base_url']==base.rstrip('/')
        assert saved['model']['key_env']=='HARNESS_QA_UNUSED';assert saved['model']['main']=='qa-text'
        window.evaluate_js('setTimeout(()=>location.reload(),100);true');time.sleep(.3)
        until("!!window.DFY?.state.cfg && document.querySelector('#model-provider').value==='openai_compatible'")
        assert window.evaluate_js("!document.querySelector('#model-base-url').readOnly")
        window.evaluate_js("(()=>{const p=document.querySelector('#model-provider');p.value='magpie';p.dispatchEvent(new Event('change',{bubbles:true}))})()")
        assert window.evaluate_js("document.querySelector('#model-base-url').value==='http://127.0.0.1:3425/v1' && document.querySelector('#model-key-env').value==='MAGPIE_API_KEY'")
        window.evaluate_js("(()=>{const p=document.querySelector('#model-provider');p.value='openai_compatible';p.dispatchEvent(new Event('change',{bubbles:true}))})()")
        assert window.evaluate_js("document.querySelector('#model-base-url').value==="+json.dumps(base.rstrip('/')))
        assert not window.evaluate_js('document.documentElement.scrollWidth>innerWidth+2')
        until("document.querySelector('#program-version').textContent==='QA'")
        from System import Action,Func,Object
        from System.IO import FileStream,FileMode
        from System.Drawing import Size
        from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
        window.native.Invoke(Action(lambda:window.native.Show()))
        # 截图聚焦本次新增的 API 面板；只改变隔离验收窗口的显示。
        window.evaluate_js("document.querySelector('#settings-form>article').style.display='none'")
        for theme in ('dark','light'):
            cfg['desktop']['theme']=theme;cfg['desktop']['font_scale']=1.25
            window.evaluate_js('window.SystemUI.appearance('+json.dumps(cfg['desktop'])+');document.querySelector("main").scrollTo({top:650,behavior:"instant"})')
            time.sleep(.5)
            assert window.evaluate_js('document.documentElement.dataset.theme')==theme
            assert not window.evaluate_js('document.documentElement.scrollWidth>innerWidth+2')
            control=window.native.webview;stream=FileStream(str(ROOT/run/('model-'+theme+'.png')),FileMode.Create)
            try:
                task=control.Invoke(Func[Object](lambda:control.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream)))
                assert task.Wait(10000)
            finally:stream.Dispose()
            window.evaluate_js("document.querySelector('[data-guide=magpie]').click()")
            until("document.querySelector('#guide-dialog').open")
            assert not window.evaluate_js("document.querySelector('#guide-content').scrollWidth>document.querySelector('#guide-content').clientWidth+2")
            stream=FileStream(str(ROOT/run/('guide-'+theme+'.png')),FileMode.Create)
            try:
                task=control.Invoke(Func[Object](lambda:control.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream)))
                assert task.Wait(10000)
            finally:stream.Dispose()
            window.evaluate_js("document.querySelector('#guide-close').click()")
        scale=window.native._scale
        window.native.Invoke(Action(lambda:setattr(window.native,'Size',Size(int(940*scale),int(650*scale)))))
        time.sleep(.3);assert not window.evaluate_js('document.documentElement.scrollWidth>innerWidth+2')
        window.evaluate_js("document.querySelector('[data-guide=api]').click()")
        until("document.querySelector('#guide-dialog').open && document.querySelector('#guide-title').textContent.includes('自有 API')")
        assert not window.evaluate_js("document.querySelector('#guide-content').scrollWidth>document.querySelector('#guide-content').clientWidth+2")
        window.evaluate_js("window.GuideUI.render({text:'# 安全预览\\n<img src=x onerror=alert(1)>',image_data:null})")
        assert window.evaluate_js("document.querySelector('#guide-content').querySelectorAll('img').length===0")
        window.evaluate_js("document.querySelector('#guide-close').click()")
        result.update(ok=True,native_bridge=True,custom_connection_probe=True,probe_does_not_save=True,save_and_reload=True,provider_drafts_preserved=True,themes_and_narrow_window=True,optional_magpie_guide=True,api_guide=True,safe_guide_renderer=True)
    except Exception as error:
        result['error']=str(error)
        result['guide_debug']=window.evaluate_js("({guideUI:!!window.GuideUI,guideBridge:typeof window.pywebview?.api.guide,open:document.querySelector('#guide-dialog').open,title:document.querySelector('#guide-title').textContent,headings:document.querySelectorAll('#guide-content h3').length,bodyLength:document.querySelector('#guide-content').textContent.length,toast:document.querySelector('#toast-region').textContent})")
    finally:window.destroy()


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');webview.start(check,gui='edgechromium',private_mode=True,debug=False)
    (ROOT/run/'stop').touch();child.wait(10)
    (ROOT/run/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['ok'] else 1)
