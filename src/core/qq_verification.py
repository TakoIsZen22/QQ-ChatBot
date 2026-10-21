"""Human verification in a separate WebView with only a one-shot result API.

No application DesktopApi, QQ password, hash or native session is exposed to the
remote captcha script. New-device confirmation opens an official HTTPS URL.
"""
import json
import threading
import webbrowser
from urllib.parse import urlsplit,parse_qs


def official_url(value):
    if not isinstance(value,str) or len(value)>8192:raise ValueError('QQ 验证地址无效')
    url=urlsplit(value);host=url.hostname or ''
    if (url.scheme!='https' or url.username or url.password or url.port or
        not (host=='qq.com' or host.endswith('.qq.com') or host.endswith('.gtimg.com'))):
        raise ValueError('QQ 验证地址不是受支持的腾讯 HTTPS 页面，请改用扫码登录')
    return value


def open_verification(challenge,complete):
    url=official_url(challenge.get('url'))
    if challenge.get('kind')=='device':
        webbrowser.open(url)
        return {'message':'已打开腾讯新设备验证页。完成手机验证后，点击“我已完成设备验证”。'}
    if challenge.get('kind')!='captcha':raise ValueError('没有可继续的 QQ 验证')
    import webview
    params=parse_qs(urlsplit(url).query)
    aid=params.get('aid',[''])[0]
    if not aid.isascii() or not aid.isdigit():raise ValueError('QQ 验证页缺少验证码应用 ID，请改用扫码')
    options={k:params[k][0] for k in ('uin','sid','login_appid') if k in params}
    script=json.dumps({'aid':aid,'options':options}).replace('<','\\u003c')
    class Verification:
        def __init__(self):self.used=False;self.lock=threading.Lock()
        def submit(self,ticket,randstr):
            with self.lock:
                if self.used:raise ValueError('验证结果已提交，请回到登录窗口查看状态')
                if not isinstance(ticket,str) or not 1<=len(ticket)<=4096 or not isinstance(randstr,str) or not 1<=len(randstr)<=1024:
                    raise ValueError('验证码结果无效')
                self.used=True
            try:complete({'action':'continue','ticket':ticket,'randstr':randstr})
            finally:window.destroy()
            return {'submitted':True}
    # Native bridge is intentionally limited to submit; never pass DesktopApi.
    html='''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>QQ 安全验证</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline' https://ssl.captcha.qq.com https://*.captcha.qq.com https://*.gtimg.com; frame-src https://*.qq.com https://*.gtimg.com; connect-src https://*.qq.com https://*.gtimg.com; img-src data: https://*.qq.com https://*.gtimg.com; style-src 'unsafe-inline' https://*.qq.com https://*.gtimg.com">
<style>body{font:16px system-ui;background:#182235;color:#eef3fc;padding:28px}p{line-height:1.8}button{padding:10px 20px}</style>
<h2>QQ 安全验证</h2><p id="state">正在加载腾讯验证码…</p><button id="retry" hidden>重新打开验证</button>
<script>const config='''+script+''';let captcha;
function show(){document.querySelector('#state').textContent='请完成腾讯提供的安全验证。';captcha.show()}
function ready(){try{captcha=new TencentCaptcha(config.aid,async r=>{
 if(r.ret===0&&r.ticket&&r.randstr){document.querySelector('#state').textContent='正在提交验证…';
 try{await window.pywebview.api.submit(r.ticket,r.randstr)}catch{document.querySelector('#state').textContent='验证提交失败，请返回 QQ 登录窗口重新尝试。'}}
 else{document.querySelector('#state').textContent='验证已取消，可重试或关闭窗口改用扫码。';document.querySelector('#retry').hidden=false}
},config.options);show()}catch{document.querySelector('#state').textContent='验证组件加载失败，请关闭窗口改用扫码。'}}
document.querySelector('#retry').onclick=show;
</script><script src="https://ssl.captcha.qq.com/TCaptcha.js" onload="ready()" onerror="document.querySelector('#state').textContent='腾讯验证码无法加载，请关闭窗口改用扫码。'"></script></html>'''
    window=webview.create_window('QQ ChatBot · QQ 安全验证',html=html,js_api=Verification(),width=580,height=560)
    return {'message':'请在独立的 QQ 安全验证窗口完成滑块。验证窗口不会获得程序管理权限。'}
