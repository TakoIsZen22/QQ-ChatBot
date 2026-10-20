"""真实Windows托盘与窗口验收。不会改自启、停止服务或写入正式窗口偏好。"""
import json
import sys
import time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.config import ROOT
from src.core.desktop_api import DesktopApi
from src.core.desktop_lifecycle import DesktopLifecycle
from src.core.desktop_assets import DesktopAssets
import webview


class SmokeApi(DesktopApi):
    def __init__(self):super().__init__();self._state={}
    def ui_state(self,patch=None):
        if patch:self._state.update(patch)
        return self._state


class SmokeLifecycle(DesktopLifecycle):
    def _save_geometry(self):pass


api=SmokeApi();api._desired_services=False;life=SmokeLifecycle(api)
window=webview.create_window('QQ ChatBot 程序壳验收',url=DesktopAssets(),js_api=api,width=1100,height=760,hidden=True)
life.bind(window);result={'ok':False}

def check():
    try:
        if not window.events.loaded.wait(25):raise RuntimeError('页面加载超时')
        life._start_tray()
        for _ in range(40):
            if life.tray.visible:break
            time.sleep(.05)
        if not life.tray.visible:raise RuntimeError('托盘未显示')
        if life.on_closing() is not False:raise RuntimeError('关闭没有收进托盘')
        time.sleep(.2)
        life.action('show');time.sleep(.2)
        if not window.native.Visible:raise RuntimeError('窗口未能从托盘恢复')
        life.action('hide');time.sleep(.2)
        if window.native.Visible:raise RuntimeError('窗口没有隐藏')
        life.action('show')
        value=window.evaluate_js("(()=>{window.DFY.navigate('system');return {page:window.DFY.state.page,prefs:!!document.querySelector('#program-start_with_windows'),backup:!!document.querySelector('#program-backup'),exit:!!document.querySelector('#program-exit')}})()")
        if value['page']!='system' or not all(value[k] for k in ('prefs','backup','exit')):raise RuntimeError('程序设置入口缺失')
        result.update(ok=True,tray=True,close_to_tray=True,restore=True,hide=True,program_page=True)
    except Exception as e:result['error']=str(e)
    finally:
        life._quit=True;window.destroy()

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    webview.start(check,gui='edgechromium',debug=False,private_mode=True,icon=str(ROOT/'assets/xiaojing-user-icon.ico'))
    (ROOT/'.runtime/desktop-system-smoke.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(0 if result['ok'] else 1)
