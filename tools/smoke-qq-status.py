"""Read-only WebView2 QA. Simulates connection states in a separate window only."""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import webview
from src.core.config import ROOT
from src.core.desktop_api import DesktopApi
from src.core.desktop_assets import DesktopAssets


class Api(DesktopApi):
    def __init__(self):super().__init__();self.state={}
    def ui_state(self,patch=None):
        if patch:self.state.update(patch)
        return self.state


result={'ok':False,'renderer':'edgechromium','fixtures_only':True}
window=webview.create_window('QQ 状态同步验收',url=DesktopAssets(),js_api=Api(),width=1280,height=820,hidden=True)


def until(expression,seconds=15):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        if window.evaluate_js(expression):return
        time.sleep(.05)
    raise RuntimeError('界面条件超时：'+expression)


def check():
    try:
        if not window.events.loaded.wait(25):raise RuntimeError('WebView2 加载超时')
        until('!!window.DFY?.state.cfg && !!window.DFY?.state.status')
        window.evaluate_js("""(()=>{
          const api=window.pywebview.api,request=api.request;
          window.qa={online:false,phase:'ready',slowReads:0};
          const base=window.DFY.state.status;
          api.request=(path,body)=>path==='status'?Promise.resolve({...base,qq_enabled:true,qq_connected:qa.online,qq_online:qa.online}):path==='chat'?(qa.slowReads++,new Promise(()=>{})):request(path,body);
          api.runtime=()=>new Promise(()=>{});
          api.qr=()=>Promise.resolve({state:'unavailable',phase:qa.phase,message:qa.phase==='offline'?'QQ 连接已断开，请先停止 QQ 再重新扫码。':'QQ 已登录，无需扫码。'});
          document.querySelector('#bridge-chip').click();window.DFY.poll();
        })()""")
        until("document.querySelector('#bridge-chip').textContent.includes('通道连接中') && document.querySelector('#qr-empty').textContent.includes('等待消息通道') && qa.slowReads>0")
        start=time.monotonic();window.evaluate_js('qa.online=true')
        until("document.querySelector('#bridge-chip').textContent.includes('QQ 已连接') && document.querySelector('#qr-state').textContent.includes('消息通道已连接')")
        result['online_sync_seconds']=round(time.monotonic()-start,3)
        start=time.monotonic();window.evaluate_js("qa.online=false;qa.phase='offline'")
        until("document.querySelector('#bridge-chip').textContent.includes('QQ 未连接') && document.querySelector('#qr-state').textContent.includes('停止')")
        result['offline_sync_seconds']=round(time.monotonic()-start,3)
        interval=window.evaluate_js('window.DFY.state.cfg.desktop.poll_interval_ms')/1000
        if max(result['online_sync_seconds'],result['offline_sync_seconds'])>interval+1:raise RuntimeError('状态同步超过一个轮询周期及界面调度余量')
        window.evaluate_js("qa.online=true;qa.phase='ready'")
        until("document.querySelector('#bridge-chip').textContent.includes('QQ 已连接') && document.querySelector('#qr-state').textContent.includes('消息通道已连接')")
        result.update(ok=True,slow_reads_do_not_block=True,login_pending=True,recovery=True)
    except Exception as e:result['error']=str(e)
    finally:window.destroy()


if __name__=='__main__':
    webview.start(check,gui='edgechromium',debug=False,private_mode=True,icon=str(ROOT/'assets/xiaojing-user-icon.ico'))
    (ROOT/'.runtime/qq-status-ui-qa.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if result['ok'] else 1)
