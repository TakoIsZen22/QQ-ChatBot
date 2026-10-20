"""显式维护模式：从正式窗口读取样式并截取能力页，不读取聊天内容。"""
import json
import os
import time
from .config import ROOT


def inspect_appearance(window):
    result = {'ok': False, 'pid': os.getpid()}
    try:
        if not window.events.loaded.wait(25):
            raise RuntimeError('正式窗口加载超时')
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            if window.evaluate_js('!!window.DFY?.state.cfg && !!window.SystemUI'):
                break
            time.sleep(.2)
        else:
            raise RuntimeError('正式窗口尚未完成初始化')
        window.evaluate_js("window.DFY.navigate('abilities')")
        time.sleep(.5)
        details = window.evaluate_js("""(() => {
            const cards = [...document.querySelectorAll('.ability-card')];
            const rules = [...document.styleSheets].flatMap(s => {
                try { return [...s.cssRules].map(r => r.cssText); } catch { return []; }
            });
            return {url: location.href, user_agent: navigator.userAgent,
                theme: document.documentElement.dataset.theme,
                css: [...document.querySelectorAll('link[rel="stylesheet"]')].map(l => l.href),
                shared_surface_rule: rules.some(r => r.includes('.ability-card') && r.includes('var(--surface)')),
                cards: cards.map(c => ({background: getComputedStyle(c).backgroundColor,
                    color: getComputedStyle(c).color})),
                surface: getComputedStyle(document.documentElement).getPropertyValue('--surface')};
        })()""")
        result.update(details)
        expected = 'rgb(25, 35, 55)' if details['theme'] == 'dark' else 'rgb(255, 255, 255)'
        result['ok'] = len(details['cards']) == 9 and all(c['background'] == expected for c in details['cards'])
        # CapturePreview只截取本窗口的WebView内容，不抓取桌面或其他应用。
        from System import Func, Object
        from System.IO import FileStream, FileMode
        from Microsoft.Web.WebView2.Core import CoreWebView2CapturePreviewImageFormat
        stream = FileStream(str(ROOT/'.runtime/desktop-appearance.png'), FileMode.Create)
        try:
            control = window.native.webview
            task = control.Invoke(Func[Object](lambda: control.CoreWebView2.CapturePreviewAsync(
                CoreWebView2CapturePreviewImageFormat.Png, stream)))
            if not task.Wait(10000):
                raise RuntimeError('窗口截图超时')
            result['screenshot'] = '.runtime/desktop-appearance.png'
        finally:
            stream.Dispose()
    except Exception as e:
        result['error'] = str(e)
    (ROOT/'.runtime/desktop-appearance.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
