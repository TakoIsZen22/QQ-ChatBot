"""真实WebView2渲染与只读桥接验收；不发聊天、不停服务、不改配置。"""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.config import ROOT
from src.core.desktop_api import DesktopApi
from src.core.desktop_assets import DesktopAssets
import webview

result={'ok':False,'renderer':'edgechromium'}
class SmokeApi(DesktopApi):
    def __init__(self):super().__init__();self._state={}
    def ui_state(self,patch=None):
        if patch:self._state.update(patch)
        return self._state

window=webview.create_window('QQ ChatBot 桌面验收',url=DesktopAssets(),js_api=SmokeApi(),width=1280,height=820,hidden=True)

def check():
    try:
        if not window.events.loaded.wait(25):raise RuntimeError('WebView页面加载超时')
        deadline=time.monotonic()+25
        snap=None
        while time.monotonic()<deadline:
            snap=window.evaluate_js("({ready:!!window.DFY,bridge:!!window.pywebview?.api,status:window.DFY?.state.status,runtime:window.DFY?.state.runtime})")
            if snap and snap.get('status') and snap.get('runtime',{}).get('desktop'):break
            time.sleep(.25)
        if not snap or not snap.get('status'):raise RuntimeError('页面未读到本机Harness状态')
        if not snap.get('runtime',{}).get('desktop'):raise RuntimeError('未使用真实原生桥')
        pages=[]
        for page in ('chat','overview','memory','diary','soul','tasks','agent','stickers','abilities','settings','system','logs'):
            value=window.evaluate_js("(()=>{window.DFY.navigate("+json.dumps(page)+");return {page:window.DFY.state.page,active:document.querySelectorAll('.page.active').length,title:document.querySelector('#page-title').textContent,width:innerWidth,scrollWidth:document.documentElement.scrollWidth}})()")
            if value.get('page')!=page or value.get('active')!=1:raise RuntimeError('导航状态错误：'+page)
            if value['scrollWidth']>value['width']+2:raise RuntimeError('布局横向溢出：'+page)
            pages.append(page)
        safe=window.evaluate_js("(()=>{const box=document.createElement('div');box.append(window.DFY.renderContent('<img src=x onerror=alert(1)>'));return {images:box.querySelectorAll('img').length,text:box.textContent}})()")
        if safe['images']!=0:raise RuntimeError('消息内容被当成HTML执行')
        window.evaluate_js("window.DFY.navigate('soul')")
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            soul_ready=window.evaluate_js("!document.querySelector('#soul-editor').disabled && !document.querySelector('#soul-save').disabled")
            if soul_ready:break
            time.sleep(.1)
        if not soul_ready:raise RuntimeError('专属人设入口未加载当前文件')
        identity_ready=window.evaluate_js("!!window.DFY.state.identity && document.querySelector('#identity-nickname').value===window.DFY.state.identity.nickname && !!document.querySelector('#identity-icon-choose') && !!document.querySelector('#identity-portrait-choose')")
        if not identity_ready:raise RuntimeError('昵称/形象/图标设置未加载')
        profile=window.evaluate_js("(()=>{window.DFY.navigate('settings');return {owner:document.querySelector('#owner-name').value===window.DFY.state.cfg.owner.name,agent:document.querySelector('#maintenance-agent').value===window.DFY.state.cfg.maintenance.agent_name,qq:!!document.querySelector('#owner-qq'),rules:!!document.querySelector('[data-open=agent_rules]')}})()")
        if not all(profile.values()):raise RuntimeError('通用使用者/维护Agent设置未加载')
        model_settings=window.evaluate_js("document.querySelector('#model-provider').value===window.DFY.state.cfg.model.provider && document.querySelector('#model-base-url').value===window.DFY.state.cfg.model.base_url && document.querySelector('#model-key-env').value===window.DFY.state.cfg.model.key_env")
        if not model_settings:raise RuntimeError('API 接入表单未加载当前配置')
        window.evaluate_js("window.DFY.navigate('system');document.querySelector('#program-supervise').click()")
        deadline=time.monotonic()+10
        while time.monotonic()<deadline:
            report=window.evaluate_js("document.querySelector('#program-supervision-output').textContent")
            if report:break
            time.sleep(.1)
        if not report or json.loads(report).get('schema')!='dafeiyu.supervision.v1':raise RuntimeError('桌面只读巡检入口未返回标准报告')
        window.evaluate_js("window.DFY.navigate('chat')")
        result.update(ok=True,pages=pages,native_bridge=True,core_online=True,qq_online=bool(snap['status'].get('qq_online')),safe_text_rendering=True,agent_settings=True,readonly_supervision=True,soul_editor=True,identity_settings=True,model_settings=True)
    except Exception as e:result['error']=str(e)
    finally:window.destroy()

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    webview.start(check,gui='edgechromium',debug=False,private_mode=True,icon=str(ROOT/'assets/xiaojing-user-icon.ico'))
    (ROOT/'.runtime/webview-smoke.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(0 if result['ok'] else 1)
