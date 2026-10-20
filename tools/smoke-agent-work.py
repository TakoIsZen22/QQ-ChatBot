"""隔离原生UI + 真CLI夹具 + stdio MCP回环；不连接真实第三方Agent或QQ。"""
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
from unittest.mock import patch,AsyncMock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.config import ROOT,load,merge,validate
from src.core.runtime_paths import python_command


def serve(run):
    import aiohttp
    from aiohttp import web
    from src.core.harness import Harness
    from src.channel.local_ui import build
    async def main():
        cfg=load(ROOT/'.runtime/nonexistent-agent-qa.json');cfg['paths']={k:(run/k).as_posix() for k in ('data','logs','backups')};cfg['safety']['mode']='reply_only'
        sock=socket.socket();sock.bind(('127.0.0.1',0));cfg['server']['port']=sock.getsockname()[1]
        def save(patch):
            candidate=copy.deepcopy(cfg);merge(candidate,patch);validate(candidate);cfg.update(candidate)
            (ROOT/run/'saved-config.json').write_text(json.dumps(cfg,ensure_ascii=False),encoding='utf-8');return copy.deepcopy(cfg)
        async with aiohttp.ClientSession() as session:
            h=Harness(cfg,session)
            async def model(*a,**k):(ROOT/run/'model-called').touch();return {'role':'assistant','content':'fixture chat'}
            h.model.complete=model
            with patch('src.channel.local_ui.load',lambda:copy.deepcopy(cfg)),patch('src.channel.local_ui.save_local',save):
                app=build(h,asyncio.Event());runner=web.AppRunner(app);await runner.setup();await web.SockSite(runner,sock).start();h.start()
                (ROOT/run/'ready.json').write_text(json.dumps({'port':cfg['server']['port']}))
                try:
                    while not (ROOT/run/'stop').exists():await asyncio.sleep(.1)
                finally:await h.close();await runner.cleanup()
    asyncio.run(main())


if '--serve' in sys.argv:
    run=Path(sys.argv[-1])
    if not (ROOT/run).resolve().is_relative_to(ROOT/'.runtime') or not run.name.startswith('agent-work-qa-'):raise ValueError('隔离路径无效')
    serve(run);sys.exit(0)

import webview
from src.core.desktop_api import DesktopApi
from src.core.desktop_assets import DesktopAssets

run=Path('.runtime')/('agent-work-qa-'+uuid.uuid4().hex[:10]);(ROOT/run).mkdir(parents=True)
child=subprocess.Popen([python_command(),__file__,'--serve',str(run)],cwd=ROOT,creationflags=subprocess.CREATE_NO_WINDOW,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
deadline=time.monotonic()+15
while not (ROOT/run/'ready.json').is_file():
    if child.poll() is not None or time.monotonic()>deadline:raise RuntimeError('工作转交隔离服务未启动')
    time.sleep(.1)
port=json.loads((ROOT/run/'ready.json').read_text())['port'];cfg=load(ROOT/'.runtime/nonexistent-agent-qa.json')


class Backend:
    def request(self,path,body=None,**kw):
        req=urllib.request.Request(f'http://127.0.0.1:{port}/api/'+path,data=None if body is None else json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Harness-Local':'1'})
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=15) as r:return json.load(r)


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
    def onboarding(self,action='status',body=None):return {'configured':True}


backend=Backend();window=webview.create_window('QQ ChatBot 工作转交验收',url=DesktopAssets(),js_api=Api(),width=1280,height=820,hidden=True);result={'ok':False}


def until(expression):
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if window.evaluate_js(expression):return
        time.sleep(.1)
    raise RuntimeError('界面条件超时：'+expression)


def fill(values):
    window.evaluate_js('for(const [id,value]of Object.entries('+json.dumps(values)+')){const e=document.querySelector("#"+id);e.value=value;e.dispatchEvent(new Event("input",{bubbles:true}))}')


def desktop_roundtrip():
    fixture={'server':{'port':port,'max_body_bytes':1048576}}
    code='from src.core import agent_mcp as m;m.load=lambda:'+repr(fixture)+';m.main()'
    proc=subprocess.Popen([sys.executable,'-c',code],cwd=ROOT,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,text=True,encoding='utf-8')
    def rpc(ident,method,params=None):
        proc.stdin.write(json.dumps({'jsonrpc':'2.0','id':ident,'method':method,'params':params or {}})+'\n');proc.stdin.flush();response=json.loads(proc.stdout.readline());assert response['id']==ident;return response['result']
    def call(ident,name,args=None):
        response=rpc(ident,'tools/call',{'name':name,'arguments':args or {}});assert not response.get('isError'),response;return json.loads(response['content'][0]['text'])
    try:
        rpc(1,'initialize',{'protocolVersion':'2025-06-18'});proc.stdin.write('{"jsonrpc":"2.0","method":"notifications/initialized"}\n');proc.stdin.flush()
        assert {x['name'] for x in rpc(2,'tools/list')['tools']}=={'qq_work_inbox','qq_work_claim','qq_work_complete'}
        listing=call(3,'qq_work_inbox');assert len(listing['tasks'])==1
        task=call(4,'qq_work_claim')['task'];assert task['text']=='桌面 Agent 专用的这条工作'
        call(5,'qq_work_complete',{'task_id':task['task_id'],'claim_id':task['claim_id'],'status':'completed','result':'桌面 MCP 回执 <script>window.pwned=true</script>'})
    finally:proc.stdin.close();proc.wait(10)


def check():
    try:
        window.events.loaded.wait(20);until("!!window.DFY?.state.cfg && !!window.AgentWorkUI && !!document.querySelector('#chat-forward-work')")
        window.evaluate_js("window.DFY.navigate('agent')");until("document.querySelector('#agent-status').textContent.includes('未启用')")
        command=[python_command(),str(ROOT/'tests/fixtures/agent_cli.py'),'echo',str(ROOT/run/'received.txt')]
        window.evaluate_js("document.querySelector('#agent-transport').value='cli';document.querySelector('#agent-transport').dispatchEvent(new Event('change'));document.querySelector('#agent-enabled').checked=true")
        fill({'agent-name':'CLI 协议夹具','agent-command':json.dumps(command),'agent-cwd':str(ROOT/run),'agent-timeout_seconds':'30'})
        window.evaluate_js("document.querySelector('#agent-binding-form').requestSubmit()")
        until("document.querySelector('#agent-binding-note').textContent.includes('已保存')")
        fill({'agent-new-text':'只转交这条工作 & echo test > do-not-create.txt'});window.evaluate_js("document.querySelector('#agent-new-form').requestSubmit()")
        until("document.querySelector('#agent-task-list').textContent.includes('Agent 已回执')")
        assert (ROOT/run/'received.txt').read_text(encoding='utf-8').endswith('只转交这条工作 & echo test > do-not-create.txt\n')
        assert not (ROOT/run/'do-not-create.txt').exists();assert not (ROOT/run/'model-called').exists()
        window.evaluate_js("document.querySelector('#agent-transport').value='desktop';document.querySelector('#agent-transport').dispatchEvent(new Event('change'))")
        fill({'agent-name':'桌面 MCP 夹具'});window.evaluate_js("document.querySelector('#agent-binding-form').requestSubmit()")
        until("document.querySelector('#agent-status').textContent.includes('桌面 MCP 夹具')")
        assert 'tools' in window.evaluate_js("document.querySelector('#agent-connection-config').textContent")
        fill({'agent-new-text':'桌面 Agent 专用的这条工作'});window.evaluate_js("document.querySelector('#agent-new-form').requestSubmit()")
        until("document.querySelector('#agent-task-list').textContent.includes('待 Agent 接单')")
        desktop_roundtrip();window.evaluate_js("document.querySelector('#agent-refresh').click()")
        until("document.querySelector('#agent-task-list').textContent.includes('桌面 MCP 回执')")
        assert not window.evaluate_js('!!window.pwned');assert window.evaluate_js("document.querySelectorAll('#agent-task-list script').length===0")
        assert not (ROOT/run/'model-called').exists()
        from System import Action,Func,Object
        from System.IO import FileStream,FileMode
        from System.Drawing import Size
        from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
        window.native.Invoke(Action(lambda:window.native.Show()))
        for theme in ('light','dark'):
            window.evaluate_js('window.SystemUI.appearance('+json.dumps(dict(cfg['desktop'],theme=theme))+')');time.sleep(.4)
            assert not window.evaluate_js('document.documentElement.scrollWidth>innerWidth+2')
            control=window.native.webview;stream=FileStream(str(ROOT/run/f'agent-work-{theme}.png'),FileMode.Create)
            try:
                task=control.Invoke(Func[Object](lambda:control.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream)));assert task.Wait(10000)
            finally:stream.Dispose()
        scale=window.native._scale;window.native.Invoke(Action(lambda:setattr(window.native,'Size',Size(int(940*scale),int(650*scale)))))
        time.sleep(.3);assert not window.evaluate_js('document.documentElement.scrollWidth>innerWidth+2')
        window.evaluate_js("document.querySelector('#agent-guide').click()");until("document.querySelector('#guide-dialog').open && document.querySelector('#guide-title').textContent.includes('桌面')")
        window.evaluate_js("document.querySelector('#guide-close').click();document.querySelector('#emergency-pause').click()")
        until("window.DFY.state.status.mode==='paused'");window.evaluate_js("document.querySelector('#agent-refresh').click()")
        until("document.querySelector('#agent-submit').disabled")
        result.update(ok=True,native_binding=True,real_fixture_cli_stdin=True,no_shell_interpolation=True,no_chat_model_for_work=True,stdio_mcp_claim_complete=True,result_is_plain_text=True,guide=True,themes_and_narrow=True,pause_blocks_dispatch=True)
    except Exception as e:result['error']=str(e)
    finally:time.sleep(.2);window.destroy()


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');webview.start(check,gui='edgechromium',private_mode=True,debug=False)
    (ROOT/run/'stop').touch();child.wait(15);(ROOT/run/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result,folder=str(ROOT/run)),ensure_ascii=False,indent=2));sys.exit(0 if result['ok'] else 1)
