"""Isolated real WebView2 local-login QA. No QQ, models, user credentials or registry writes."""
import inspect
import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.config import ROOT,load
from src.core.desktop_api import DesktopApi,signed_in
from src.core.desktop_assets import DesktopAssets
from src.core.local_account import LocalAccount,LoginRequired
import webview

run=ROOT/'.runtime'/('account-qa-'+time.strftime('%Y%m%d-%H%M%S'));run.mkdir(parents=True)
temp=tempfile.TemporaryDirectory();private=Path(temp.name)
cfg=load(private/'absent.json');cfg['model']['main']='fixture';cfg['desktop']['theme']='light'
result={'ok':False}
password='disposable-webview-fixture-only'

class Backend:
    def port(self,*args):return False
    def request(self,path,body=None,**kw):
        if path=='status':return {'name':'QQ ChatBot','mode':'paused','busy':False,'queue':0,'qq_enabled':False,'weights':cfg['growth'],'memory_count':0,'diary_count':0}
        if path=='config':return cfg
        if path.startswith('identity'):return {'nickname':'验收角色','revision':'fixture','appearance':'','icon_data':None,'portrait_data':None,
            'icon_id':None,'portrait_id':None,'limits':{k:cfg['identity'][k] for k in ('max_image_bytes','max_nickname_chars','max_appearance_chars')},
            'defaults':{'nickname':cfg['identity']['default_nickname'],'image_data':None}}
        if path=='chat':return [{'role':'user','content':'隔离验收的私人聊天','ts':'2026-10-21T09:00:00+08:00','channel':'local'}]
        return []

class Api(DesktopApi):
    @signed_in
    def runtime(self):return {'desktop':True,'version':'QA'}
    @signed_in
    def preferences(self,patch=None):return {'settings':cfg['desktop'],'startup':{'supported':False,'registered':False},'version':'QA'}
    @signed_in
    def maintenance(self,*args):return []
    @signed_in
    def onboarding(self,action='status',body=None):return {'configured':True}

patches=[patch('src.core.desktop_api.ROOT',private),patch('src.core.desktop_api.load',return_value=cfg)]
for p in patches:p.start()
api=Api(Backend())
window=webview.create_window('QQ ChatBot 本机登录隔离验收',url=DesktopAssets(),js_api=api,width=1280,height=820,hidden=True)

def until(expression):
    deadline=time.monotonic()+15
    while time.monotonic()<deadline:
        if window.evaluate_js(expression):return
        time.sleep(.1)
    raise RuntimeError('界面条件超时：'+expression)

def js(value):return json.dumps(value,ensure_ascii=True)

def fill(selector,value):window.evaluate_js('document.querySelector('+js(selector)+').value='+js(value))

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
        window.events.loaded.wait(20)
        until('!!window.DFY?.state.cfg')
        window.evaluate_js("window.DFY.navigate('system');document.querySelector('#program-account-edit').click()")
        until("document.querySelector('#account-edit-dialog').open")
        fill('#account-new-username','验收用户');fill('#account-new-password',password);fill('#account-confirm',password)
        window.evaluate_js("document.querySelector('#edit-remember').click();document.querySelector('#edit-auto').click()")
        window.evaluate_js("document.querySelector('#account-edit-form').requestSubmit()")
        until("!document.querySelector('#account-edit-dialog').open && !document.querySelector('#account-quick-lock').hidden")
        initial=api._session
        assert password not in (private/'config/account.local.json').read_text(encoding='utf-8')
        assert password not in (private/'.runtime/account-remember.local.json').read_text(encoding='utf-8')
        assert api.account()['remember']['auto_login']
        result['setup_and_hashed_storage']=True
        capture('settings-light.png')
        # Fresh process behavior; the live bridge object is rebound on page reload.
        api._session=None;api._auto_login_attempted=False
        window.evaluate_js('location.reload()')
        until("!!window.DFY?.state.cfg && document.querySelector('#account-gate').hidden")
        assert api._signed_in()
        result['cold_start_auto_login']=True
        cfg['desktop']['theme']='dark'
        window.evaluate_js("document.querySelector('#account-quick-lock').click()")
        until("!!document.querySelector('#account-login') && !document.querySelector('#account-gate').hidden")
        assert not api._account().authenticated(initial)
        assert api.account()['remember']['saved'] and not api.account()['remember']['auto_login']
        assert window.evaluate_js("document.querySelector('#account-password').value==='' && !document.querySelector('#account-password').required && document.querySelector('#login-remember').checked && !document.querySelector('#login-auto').checked")
        assert window.evaluate_js("getComputedStyle(document.querySelector('.app-shell')).display==='none' && !document.querySelector('#message-list').textContent.includes('隔离验收的私人聊天')")
        try:api.request('chat');raise AssertionError('bridge bypass')
        except LoginRequired:pass
        capture('login-dark.png')
        fill('#account-username','验收用户');fill('#account-password','wrong')
        window.evaluate_js("document.querySelector('#account-login').requestSubmit()")
        until("document.querySelector('#account-message').textContent.includes('不正确')")
        assert window.evaluate_js("document.querySelector('#account-password').value===''")
        # No plaintext password is filled into the DOM; bridge uses DPAPI on click.
        window.evaluate_js("document.querySelector('#account-login').requestSubmit()")
        until("!!window.DFY?.state.cfg && document.querySelector('#account-gate').hidden")
        result['lock_login_wrong_password_and_bridge_enforcement']=True
        result['remembered_manual_unlock_without_dom_password']=True
        window.evaluate_js("window.DFY.navigate('system');document.querySelector('#program-account-edit').click()")
        until("document.querySelector('#account-edit-dialog').open")
        before=api._session
        fill('#account-current',password);fill('#account-new-username','新账号');fill('#account-new-password',password+'-new');fill('#account-confirm',password+'-new')
        window.evaluate_js("document.querySelector('#account-edit-form').requestSubmit()")
        until("!document.querySelector('#account-edit-dialog').open && document.querySelector('#program-account-status').textContent.includes('新账号')")
        assert not api._account().authenticated(before)
        assert api.account()['remember']['saved']
        window.evaluate_js("document.querySelector('#program-account-forget').click()")
        until("document.querySelector('#program-account-forget').hidden")
        assert not (private/'.runtime/account-remember.local.json').exists()
        result['forget_saved_password']=True
        result.update(ok=True,password_change_revokes_sessions=True,light_dark=True)
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
