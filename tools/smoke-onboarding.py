"""真实WebView2向导验收，隔离核心+本机模型清单夹具；不登录QQ、不调用外部模型。"""
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
from src.core.runtime_paths import python_command


def serve(run):
    import aiohttp
    from aiohttp import web
    from src.core.harness import Harness
    from src.channel.local_ui import build
    async def main():
        cfg=load(ROOT/'.runtime/nonexistent-setup-qa.json');cfg['paths']={k:(run/k).as_posix() for k in ('data','logs','backups')}
        sock=socket.socket();sock.bind(('127.0.0.1',0));cfg['server']['port']=sock.getsockname()[1]
        async with aiohttp.ClientSession() as session:
            h=Harness(cfg,session);app=build(h,asyncio.Event())
            async def models(request):return web.json_response({'data':[{'id':'setup-text'},{'id':'setup-vision'}]})
            app.router.add_get('/fixture/v1/models',models)
            runner=web.AppRunner(app);await runner.setup();await web.SockSite(runner,sock).start()
            (ROOT/run/'ready.json').write_text(json.dumps({'port':cfg['server']['port']}))
            while not (ROOT/run/'stop').exists():await asyncio.sleep(.1)
            await runner.cleanup();await h.close()
    asyncio.run(main())


if '--serve' in sys.argv:
    run=Path(sys.argv[-1])
    if not (ROOT/run).resolve().is_relative_to(ROOT/'.runtime') or not run.name.startswith('onboarding-qa-'):raise ValueError('隔离路径无效')
    serve(run);sys.exit(0)

import webview
from src.core.desktop_api import DesktopApi
from src.core.desktop_assets import DesktopAssets

run=Path('.runtime')/('onboarding-qa-'+uuid.uuid4().hex[:10]);(ROOT/run).mkdir(parents=True)
child=subprocess.Popen([python_command(),__file__,'--serve',str(run)],cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
deadline=time.monotonic()+15
while not (ROOT/run/'ready.json').is_file():
    if child.poll() is not None or time.monotonic()>deadline:raise RuntimeError('隔离核心启动失败')
    time.sleep(.1)
cfg=load(ROOT/'.runtime/nonexistent-setup-qa.json');cfg['server']['port']=json.loads((ROOT/run/'ready.json').read_text())['port']
cfg['paths']={k:(run/k).as_posix() for k in ('data','logs','backups')}


class Backend:
    def request(self,path,body=None,**kw):
        if path=='config':return cfg
        req=urllib.request.Request(f'http://127.0.0.1:{cfg["server"]["port"]}/api/'+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Harness-Local':'1'})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=15) as r:return json.load(r)


class Api(DesktopApi):
    def __init__(self):super().__init__(Backend());self.state={};self.installed=False;self.saved=False;self.started=False;self.refreshed=False;self.stopped=False;self.qr_phase="not_running"
    def ui_state(self,patch=None):
        if patch:self.state.update(patch)
        return self.state
    def runtime(self):return {'desktop':True,'version':'QA'}
    def preferences(self,patch=None):return {'settings':cfg['desktop'],'startup':{'supported':False,'registered':False},'version':'QA'}
    def maintenance(self,*args):return []
    def events(self):return []
    def read_data(self,stream):return []
    def qr(self):return {'state':'expired' if self.qr_phase=='qrcode_expired' else 'unavailable','phase':self.qr_phase,'message':'等待扫码（协议夹具）'}
    def onboarding(self,action='status',body=None):
        if action=='save':
            if body['owner_id']==body['bot_id']:raise ValueError('主人和机器人必须不同')
            candidate=copy.deepcopy(cfg);merge(candidate,{'owner':{'name':body['owner_name'],'qq_id':body['owner_id']},'qq':{'enabled':True,'bot_id':body['bot_id']},'model':body['model']});validate(candidate);cfg.update(candidate)
            self.saved=True;(ROOT/run/'saved.json').write_text(json.dumps(body),encoding='utf-8');return {'message':'已保存（协议夹具）'}
        if action=='install':self.installed=True;return {'started':True}
        if action=='start':self.started=True;self.qr_phase='waiting_qrcode';return {'message':'等待扫码（协议夹具）'}
        if action=='refresh_qr':self.refreshed=True;self.qr_phase='waiting_qrcode';return {'message':'已刷新（协议夹具）'}
        if action=='stop':self.stopped=True;self.qr_phase='not_running';return {'message':'已停止（协议夹具）'}
        return {'configured':self.saved,'portable':False,'accounts':{'owner_name':'你','owner_id':'','bot_id':''},'model':cfg['model'],
            'bridge':{'experimental':True,'launch_available':self.installed and self.saved,'session':{'online':False}},'components':{'bridge':True,'qq':self.installed},'job':{'running':False,'stage':'done' if self.installed else 'idle','message':'组件已准备好' if self.installed else '等待准备','received':0,'total':0}}


api=Api();window=webview.create_window('QQ ChatBot 首次向导验收',url=DesktopAssets(),js_api=api,width=1280,height=820,hidden=True);result={'ok':False}

def until(expression):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if window.evaluate_js(expression):return
        time.sleep(.1)
    raise RuntimeError('界面条件超时：'+expression)


def check():
    try:
        window.events.loaded.wait(20);until("!!window.DFY?.state.cfg && document.querySelector('#onboarding-dialog')?.open")
        assert window.evaluate_js("!document.querySelector('[data-nav=agent]') && !document.querySelector('#page-agent') && !window.AgentWorkUI")
        window.evaluate_js("window.DFY.navigate('agent')")
        assert window.evaluate_js("window.DFY.state.page==='chat'")
        result['retired_work_absent']=True
        from src.core.edition import capabilities
        expected=capabilities()['providers']
        for selector in ('#setup-provider','#model-provider'):
            actual=window.evaluate_js('Array.from(document.querySelector('+json.dumps(selector)+').options,o=>o.value)')
            assert set(actual)==set(expected),(selector,actual,expected)
        assert window.evaluate_js('!!document.querySelector(\'[data-guide="magpie"]\')')==('magpie' in expected)
        result['edition']=capabilities()['version'];result['provider_options']=expected
        assert not api.saved and not api.started and not api.installed
        window.evaluate_js("document.querySelector('#setup-tutorial').click()")
        until("document.querySelector('#guide-dialog').open && document.querySelector('#guide-title').textContent.includes('新手')")
        assert window.evaluate_js("document.querySelector('#guide-content').textContent.includes('Releases')")
        window.evaluate_js("document.querySelector('#guide-close').click()")
        base=f'http://127.0.0.1:{cfg["server"]["port"]}/fixture/v1'
        values={'provider':'openai_compatible','base_url':base,'key_env':'SETUP_QA_UNUSED','owner_name':'向导测试','owner_id':'10001','bot_id':'10002','main':'setup-text','auxiliary':'setup-vision'}
        window.evaluate_js("document.querySelector('#setup-provider').value='openai_compatible';document.querySelector('#setup-provider').dispatchEvent(new Event('change'))")
        window.evaluate_js('for(const [k,v]of Object.entries('+json.dumps(values)+'))document.querySelector("#setup-"+k).value=v;document.querySelector("#setup-check").click()')
        until("document.querySelector('#setup-api-state').textContent.includes('连接成功')")
        assert not api.saved
        window.evaluate_js("document.querySelector('#setup-form').requestSubmit()")
        until("document.querySelector('#setup-result').textContent.includes('已保存')")
        assert json.loads((ROOT/run/'saved.json').read_text(encoding='utf-8'))['model']['main']=='setup-text'
        window.evaluate_js("document.querySelector('#setup-download').click()")
        until("document.querySelector('#setup-download-state').textContent.includes('已就绪')")
        until("!document.querySelector('#setup-start').disabled")
        assert not api.started
        window.evaluate_js("document.querySelector('#setup-start').click()")
        until("document.querySelector('#setup-result').textContent.includes('等待扫码')")
        assert api.started
        until("!document.querySelector('#setup-start').disabled")
        window.evaluate_js("document.querySelector('#setup-refresh-qr').click()")
        until("document.querySelector('#setup-result').textContent.includes('已刷新')")
        assert api.refreshed
        until("!document.querySelector('#setup-start').disabled")
        window.evaluate_js("document.querySelector('#setup-stop-qq').click()")
        until("document.querySelector('#setup-result').textContent.includes('已停止')")
        assert api.stopped
        assert window.evaluate_js("document.querySelector('#setup-finish').disabled")
        from System import Action,Func,Object
        from System.IO import FileStream,FileMode
        from System.Drawing import Size
        from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
        window.native.Invoke(Action(lambda:window.native.Show()))
        for theme in ('light','dark'):
            window.evaluate_js('window.SystemUI.appearance('+json.dumps(dict(cfg['desktop'],theme=theme))+')')
            time.sleep(.4)
            assert not window.evaluate_js("document.querySelector('#onboarding-dialog').scrollWidth>document.querySelector('#onboarding-dialog').clientWidth+2")
            assert window.evaluate_js("getComputedStyle(document.querySelector('#onboarding-dialog')).backgroundColor")==('rgb(25, 35, 55)' if theme=='dark' else 'rgb(255, 255, 255)')
            control=window.native.webview;stream=FileStream(str(ROOT/run/f'first-run-{theme}.png'),FileMode.Create)
            try:
                task=control.Invoke(Func[Object](lambda:control.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream)));assert task.Wait(10000)
            finally:stream.Dispose()
        scale=window.native._scale;window.native.Invoke(Action(lambda:setattr(window.native,'Size',Size(int(940*scale),int(650*scale)))))
        time.sleep(.3);assert not window.evaluate_js("document.querySelector('#onboarding-dialog').scrollWidth>document.querySelector('#onboarding-dialog').clientWidth+2")
        window.evaluate_js("document.querySelector('#setup-close').click();window.DFY.navigate('system');document.querySelector('#program-onboarding').click()")
        until("document.querySelector('#onboarding-dialog').open")
        window.evaluate_js("document.querySelector('#setup-close').click();document.querySelector('#bridge-chip').click()")
        until("document.querySelector('#qr-dialog').open && !document.querySelector('#qr-start').disabled")
        assert window.evaluate_js("document.querySelector('#refresh-qr').disabled && document.querySelector('#qr-empty').textContent.includes('启动 QQ')")
        api.started=False;api.refreshed=False;api.stopped=False
        window.evaluate_js("document.querySelector('#qr-start').click()")
        until("document.querySelector('#qr-start').disabled && !document.querySelector('#refresh-qr').disabled")
        assert api.started
        api.qr_phase='qrcode_expired'
        window.evaluate_js("document.querySelector('#refresh-qr').click()")
        until("!document.querySelector('#refresh-qr').disabled")
        assert api.refreshed
        window.evaluate_js("document.querySelector('#qr-stop').click()")
        until("!document.querySelector('#qr-start').disabled")
        assert api.stopped
        window.evaluate_js("document.querySelector('#qr-settings').click()")
        until("document.querySelector('#onboarding-dialog').open && !document.querySelector('#qr-dialog').open")
        result['quick_qr_start_refresh_stop_settings']=True
        result.update(ok=True,first_run_auto_open=True,guide_offline=True,model_probe_without_save=True,account_save=True,download_and_explicit_qr_start=True,qr_refresh_and_stop=True,offline_cannot_resume=True,themes_and_narrow=True,reopen_entry=True)
    except Exception as e:result['error']=str(e)
    finally:
        window.evaluate_js("document.querySelector('#onboarding-dialog')?.close()");time.sleep(.25);window.destroy()


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');webview.start(check,gui='edgechromium',private_mode=True,debug=False)
    (ROOT/run/'stop').touch();child.wait(10);(ROOT/run/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result,folder=str(ROOT/run)),ensure_ascii=False,indent=2));sys.exit(0 if result['ok'] else 1)
