"""QQ ChatBot WebView2 桌面入口；核心与QQ进程独立于窗口生命周期。"""
import os
import subprocess
import sys
from pathlib import Path
from .core.config import ROOT,load,save_local
from .core.instance import InstanceLock
from .core.desktop_api import DesktopApi
from .core.desktop_lifecycle import DesktopLifecycle
from .core.desktop_platform import WindowsIntegration
from .core.desktop_assets import DesktopAssets
from .core.identity import installed_identity
from .core.runtime_paths import portable

from .core.product import NAME as TITLE,LEGACY_NAME

def __getattr__(name):
    if name=='DesktopApp':
        from .desktop_legacy import DesktopApp
        return DesktopApp
    raise AttributeError(name)

def _focus_existing():
    if os.name=='nt':
        import ctypes
        import json
        user32=ctypes.windll.user32
        user32.FindWindowW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p];user32.FindWindowW.restype=ctypes.c_void_p
        hwnd=user32.FindWindowW(None,installed_identity().title())
        if not hwnd:
            try:
                record=json.loads((ROOT/'.runtime/desktop-window.json').read_text(encoding='utf-8'))
                candidate=ctypes.c_void_p(record['hwnd']);pid=ctypes.c_ulong()
                user32.GetWindowThreadProcessId(candidate,ctypes.byref(pid))
                caption=ctypes.create_unicode_buffer(512);user32.GetWindowTextW(candidate,caption,512)
                if user32.IsWindow(candidate) and pid.value==record['pid'] and any(name in caption.value for name in (TITLE,LEGACY_NAME)):hwnd=record['hwnd']
            except (OSError,ValueError,KeyError,TypeError):pass
        if hwnd:
            user32.ShowWindow(ctypes.c_void_p(hwnd),9)
            user32.SetForegroundWindow(ctypes.c_void_p(hwnd))

def main():
    if '--register' in sys.argv:
        WindowsIntegration().register();return
    if '--unregister' in sys.argv:
        if os.name=='nt':
            import ctypes
            if ctypes.windll.user32.MessageBoxW(None,'移除开机自启、快捷方式和Windows程序登记？\n程序目录、data、备份与登录态全部保留。',TITLE,0x24)!=6:return
        WindowsIntegration().unregister();save_local({'desktop':{'start_with_windows':False}})
        return
    runtime=ROOT/'.venv-desktop'
    if not portable() and Path(sys.prefix).resolve()!=runtime.resolve():
        pythonw=runtime/'Scripts/pythonw.exe'
        if not pythonw.is_file():
            if os.name=='nt':
                import ctypes
                ctypes.windll.user32.MessageBoxW(None,'新版桌面运行时未安装。请先运行 tools\\install-desktop.bat。',TITLE,0x10)
            return
        subprocess.Popen([str(pythonw),'-m','src.desktop',*sys.argv[1:]],cwd=ROOT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        return
    try:lock=InstanceLock(ROOT/'.runtime/desktop-webview.lock')
    except (RuntimeError,OSError):
        if '--startup' not in sys.argv:_focus_existing()
        return
    try:
        import webview
        cfg=load();api=DesktopApi();lifecycle=DesktopLifecycle(api)
        if os.name=='nt':
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID('DaFeiYu.Harness.Desktop')
        identity=installed_identity()
        window=webview.create_window(identity.title(),url=DesktopAssets(),js_api=api,
                              **lifecycle.geometry(),hidden='--startup' in sys.argv and cfg['desktop']['startup_hidden'],
                              min_size=(940,650),background_color='#F5F7FB',text_select=True,zoomable=False)
        lifecycle.bind(window)
        def ready():
            lifecycle.start('--startup' in sys.argv)
            if '--inspect-appearance' in sys.argv:
                from .core.desktop_appearance import inspect_appearance
                import threading
                threading.Thread(target=inspect_appearance,args=(window,),daemon=True).start()
        webview.start(ready,gui='edgechromium',debug=False,private_mode=False,
                      storage_path=str(ROOT/'.runtime/webview-profile'),icon=str(identity.image_path('icon','ico')))
    except Exception as e:
        if os.name=='nt':
            import ctypes
            # 绿色包的 embeddable Python 不含 tkinter，legacy 界面不可用，别给无效建议。
            fallback=('请改用浏览器打开 http://127.0.0.1:8765 。'
                      if portable(ROOT) else '可用 src.desktop_legacy 作为维护备用界面。')
            ctypes.windll.user32.MessageBoxW(None,'桌面窗口启动失败：'+str(e)+'\n'+fallback,TITLE,0x10)
        else:raise
    finally:
        if 'lifecycle' in locals():lifecycle.close()
        lock.close()

if __name__=='__main__':main()
