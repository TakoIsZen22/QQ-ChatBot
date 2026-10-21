"""Isolated WebView2 QQ dual-login QA; no real QQ, model or user password."""
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.config import ROOT,load
from src.core.desktop_api import DesktopApi
from src.core.desktop_assets import DesktopAssets
import webview

run=ROOT/'.runtime'/('qq-login-qa-'+time.strftime('%Y%m%d-%H%M%S'));run.mkdir(parents=True)
temp=tempfile.TemporaryDirectory();private=Path(temp.name)
cfg=load(private/'absent.json');cfg['model']['main']='fixture';cfg['qq']['bot_id']='10002'
cfg['desktop']['theme']='light'
result={'ok':False}

class Backend:
    def port(self,*args):return False
    def request(self,path,body=None,**kw):
        if path=='status':return {'name':'QQ ChatBot','mode':'paused','busy':False,'queue':0,'qq_enabled':True,'qq_online':False,'qq_connected':False,'weights':cfg['growth'],'memory_count':0,'diary_count':0}
        if path=='config':return cfg
        if path.startswith('identity'):return {'nickname':'验收角色','revision':'fixture','appearance':'','icon_data':None,'portrait_data':None,
            'icon_id':None,'portrait_id':None,'limits':{k:cfg['identity'][k] for k in ('max_image_bytes','max_nickname_chars','max_appearance_chars')},
            'defaults':{'nickname':cfg['identity']['default_nickname'],'image_data':None}}
        return []

class Api(DesktopApi):
    phase='not_running';submitted=0;saved=False;auto=False;verified=False;auto_calls=0;refreshed=False
    def runtime(self):return {'desktop':True,'version':'QA'}
    def preferences(self,patch=None):return {'settings':cfg['desktop'],'startup':{'supported':False,'registered':False},'version':'QA'}
    def maintenance(self,*args):return []
    def ui_state(self,patch=None):return {}
    def events(self):return []
    def qr(self):return {'state':'unavailable','phase':self.phase,'message':'隔离 QQ 登录验收'}
    def onboarding(self,action='status',body=None):
        if action=='password_auto':self.auto_calls+=1;return {'attempted':False}
        if action=='password_status':return {'saved':self.saved,'auto':self.auto,'supported':True}
        if action=='password_login':
            assert body['password']=='disposable-qq-fixture-only' or self.saved
            assert body['remember'] and body['auto']
            self.saved=True;self.auto=True;self.submitted+=1;self.phase='password_captcha'
            return {'phase':self.phase}
        if action=='password_verify':self.verified=True;return {'message':'滑块验证窗口（夹具）'}
        if action=='password_forget':self.saved=False;self.auto=False;return {'message':'已清除（夹具）'}
        if action=='refresh_qr':self.refreshed=True;self.phase='waiting_qrcode';return {'message':'已刷新（夹具）'}
        return {'configured':True,'accounts':{'owner_name':'验收用户','owner_id':'10001','bot_id':'10002'},'model':cfg['model'],
            'components':{'bridge':True,'qq':True},'bridge':{'launch_available':True,'session':{'online':False,'phase':self.phase}},
            'job':{'running':False,'message':'隔离夹具','received':0,'total':0}}

patches=[patch('src.core.desktop_api.ROOT',private),patch('src.core.desktop_api.load',return_value=cfg)]
for p in patches:p.start()
api=Api(Backend())
window=webview.create_window('QQ ChatBot QQ 双登录隔离验收',url=DesktopAssets(),js_api=api,width=1280,height=850,hidden=True)

def until(expression):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        if window.evaluate_js(expression):return
        time.sleep(.1)
    raise RuntimeError('界面条件超时：'+expression)

def capture(name):
    from System import Action,Func,Object
    from System.IO import FileStream,FileMode
    from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
    window.native.Invoke(Action(lambda:window.native.Show()))
    stream=FileStream(str(run/name),FileMode.Create)
    try:
        control=window.native.webview
        task=control.Invoke(Func[Object](lambda:control.CoreWebView2.CapturePreviewAsync(CoreWebView2CapturePreviewImageFormat.Png,stream)))
        assert task.Wait(10000)
    finally:stream.Dispose()

def check():
    try:
        window.events.loaded.wait(20);until('!!window.QQLoginUI && document.querySelectorAll(".qq-login-panel").length===2')
        window.evaluate_js("document.querySelector('#bridge-chip').click()")
        until("document.querySelector('#qr-dialog').open")
        window.evaluate_js("document.querySelector('#qr-dialog [data-login-mode=password]').click()")
        until("document.querySelector('#qr-dialog .qq-login-uin').value==='10002'")
        assert window.evaluate_js("document.querySelector('#qr-dialog .qq-login-auto').disabled && !document.querySelector('#qr-dialog .qq-login-remember').checked && getComputedStyle(document.querySelector('.qr-image-wrap')).display==='none'")
        capture('qq-password-light.png')
        window.evaluate_js("document.querySelector('#qr-dialog .qq-login-password').value='disposable-qq-fixture-only';document.querySelector('#qr-dialog .qq-login-remember').click();document.querySelector('#qr-dialog .qq-login-auto').click();document.querySelector('#qr-dialog form').requestSubmit()")
        until("document.querySelector('#qr-dialog .qq-login-status').textContent.includes('滑块') && !document.querySelector('#qr-dialog .qq-login-verify').hidden")
        assert api.submitted==1
        assert window.evaluate_js("document.querySelector('#qr-dialog .qq-login-password').value==='' && !document.body.innerHTML.includes('disposable-qq-fixture-only')")
        window.evaluate_js("document.querySelector('#qr-dialog .qq-login-verify').click()")
        until("document.querySelector('#qr-dialog .qq-login-status').textContent.includes('夹具')")
        assert api.verified
        cfg['desktop']['theme']='dark'
        window.evaluate_js("document.documentElement.dataset.theme='dark'")
        time.sleep(.3)  # Let the button background transition and WebView compositor finish.
        assert window.evaluate_js("['.qq-login-verify','#qr-stop'].every(s=>parseInt(getComputedStyle(document.querySelector(s)).backgroundColor.match(/\\d+/)[0])<80)")
        capture('qq-password-dark.png')
        api.phase='password_device'
        window.evaluate_js("window.QQLoginUI.update('password_device')")
        assert window.evaluate_js("!document.querySelector('#qr-dialog .qq-login-complete').hidden")
        window.evaluate_js("document.querySelector('#qr-dialog [data-login-mode=qr]').click()")
        until("!document.querySelector('#qr-dialog [data-login-mode=qr]').getAttribute('aria-pressed').includes('false') && getComputedStyle(document.querySelector('.qr-image-wrap')).display!=='none'")
        assert api.refreshed
        window.evaluate_js("document.querySelector('#close-qr').click();window.OnboardingUI.open()")
        until("document.querySelector('#onboarding-dialog').open")
        window.evaluate_js("document.querySelector('#onboarding-dialog [data-login-mode=password]').click()")
        until("document.querySelector('#onboarding-dialog .qq-login-remember').checked")
        assert window.evaluate_js("document.querySelector('#onboarding-dialog .qq-login-password').value==='' && document.querySelector('#onboarding-dialog .qq-login-auto').checked")
        window.evaluate_js("document.querySelector('#onboarding-dialog .qq-login-forget').click()")
        until("!document.querySelector('#onboarding-dialog .qq-login-remember').checked")
        assert not api.saved and not api.auto and api.auto_calls==1
        window.resize(900,760)
        assert window.evaluate_js("document.querySelector('#onboarding-dialog').scrollWidth<=document.querySelector('#onboarding-dialog').clientWidth+2")
        result.update(ok=True,dual_entry=True,defaults_off=True,password_cleared=True,challenge_ui=True,remember_not_in_dom=True,forget=True,light_dark=True,narrow=True,auto_once=True)
    except Exception as e:result['error']=str(e)
    finally:window.destroy()

if __name__=='__main__':
    try:webview.start(check,gui='edgechromium',private_mode=True,debug=False)
    finally:
        for p in patches:p.stop()
        temp.cleanup()
    (run/'result.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(result,folder=str(run)),ensure_ascii=True,indent=2))
    sys.exit(0 if result['ok'] else 1)
