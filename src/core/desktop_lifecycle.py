"""窗口/托盘生命周期；关闭界面、后台驻留、停止服务各有明确出口。"""
import json
import os
import threading
from datetime import datetime,timezone
from .config import ROOT,load
from .log import Log
from .store import Store
from .product import NAME


class DesktopLifecycle:
    def __init__(self,api):
        self.api=api;self.window=None;self.tray=None;self.tray_available=False
        self._quit=False;self._stop=threading.Event();self._geometry={};self._geometry_lock=threading.Lock()
        self._last_error=None;self._timer=None
        self._identity_revision=None;self._identity_lock=threading.Lock();self._native_icon=None
        self.api._bind_lifecycle(self)

    def geometry(self):
        cfg=load()['desktop'];state={}
        try:state=json.loads((ROOT/'.runtime/window-state.json').read_text(encoding='utf-8'))
        except (OSError,ValueError):pass
        result={'width':cfg['window_width'],'height':cfg['window_height']}
        for key,minimum,maximum in (('width',940,7680),('height',650,4320)):
            if type(state.get(key)) is int:result[key]=max(minimum,min(maximum,state[key]))
        if type(state.get('x')) is int and type(state.get('y')) is int:
            if os.name=='nt':
                import ctypes
                u=ctypes.windll.user32;left,top=u.GetSystemMetrics(76),u.GetSystemMetrics(77)
                right,bottom=left+u.GetSystemMetrics(78),top+u.GetSystemMetrics(79)
                if left<=state['x']<=right-120 and top<=state['y']<=bottom-80:result.update(x=state['x'],y=state['y'])
            elif -10000<state['x']<10000 and -10000<state['y']<10000:result.update(x=state['x'],y=state['y'])
        result['maximized']=state.get('maximized') is True
        self._geometry=dict(result)
        return result

    def bind(self,window):
        self.window=window
        window.events.closing+=self.on_closing
        window.events.minimized+=self.on_minimized
        window.events.resized+=self.on_resize
        window.events.moved+=self.on_move
        window.events.maximized+=self.on_maximized
        window.events.restored+=self.on_restored
        window.events.closed+=self.close

    def _save_geometry(self):
        with self._geometry_lock:
            path=ROOT/'.runtime/window-state.json';path.parent.mkdir(parents=True,exist_ok=True)
            temp=path.with_suffix('.tmp');temp.write_text(json.dumps(self._geometry),encoding='utf-8');temp.replace(path)

    def _schedule_geometry(self):
        if self._timer:self._timer.cancel()
        self._timer=threading.Timer(.5,self._save_geometry);self._timer.daemon=True;self._timer.start()

    def on_resize(self,width,height):
        if self._geometry.get('maximized'):return
        if width>=940 and height>=650:
            self._geometry.update(width=width,height=height);self._schedule_geometry()

    def on_move(self,x,y):
        if self._geometry.get('maximized'):return
        if x>-30000 and y>-30000:
            self._geometry.update(x=x,y=y);self._schedule_geometry()

    def on_maximized(self):self._geometry['maximized']=True;self._schedule_geometry()

    def on_restored(self):self._geometry['maximized']=False;self._schedule_geometry()

    def on_closing(self):
        if self._quit:return True
        if self.tray_available and load()['desktop']['close_to_tray']:
            threading.Thread(target=self._hide,daemon=True).start()
            return False
        return True

    def on_minimized(self):
        if self.tray_available and load()['desktop']['minimize_to_tray']:self._hide()

    def _hide(self):
        if self.window and not self._quit:
            try:self.window.hide()
            except Exception:pass

    def _allow_windows_shutdown(self,sender,args):
        if str(args.CloseReason) in ('WindowsShutDown','TaskManagerClosing','ApplicationExitCall'):
            self._quit=True;self._stop.set();args.Cancel=False

    def action(self,action):
        if action=='show':self.window.show();self.window.restore()
        elif action=='hide':
            if not self.tray_available:raise RuntimeError('系统托盘不可用，保留窗口以免无法找回')
            self._hide()
        elif action in ('exit_ui','exit_all'):
            self._quit=True;self._stop.set()
            # 让桥先返回结果再销毁，避免前端误报退出失败。
            timer=threading.Timer(.2,self.window.destroy);timer.daemon=True;timer.start()
        else:raise ValueError('未知窗口动作')
        return {'action':action}

    def _background(self,fn):
        def run():
            try:fn()
            except Exception as e:self.report_error(str(e))
        threading.Thread(target=run,daemon=True).start()

    def _start_tray(self):
        import pystray
        from PIL import Image
        def item(label,fn,default=False):return pystray.MenuItem(label,lambda icon,menu:self._background(fn),default=default)
        from .identity import installed_identity
        identity=installed_identity(ROOT)
        self.tray=pystray.Icon('DaFeiYuHarness',Image.open(identity.image_path('icon')),identity.title(),pystray.Menu(
            item('打开主窗口',lambda:self.action('show'),True),
            item('全部暂停',lambda:self.api.request('safety',{'mode':'paused'})),
            item('恢复，只回复',lambda:self.api.request('safety',{'mode':'reply_only'})),pystray.Menu.SEPARATOR,
            item('启动聊天服务',lambda:self.api.command('start')),item('停止聊天与QQ',lambda:self.api.command('stop')),
            item('打开项目文件夹',lambda:self.api.open_target('project')),pystray.Menu.SEPARATOR,
            item('退出界面，后台继续',lambda:self.api.window_action('exit_ui')),
            item('退出并停止全部',lambda:self.api.window_action('exit_all'))))
        self.tray.run_detached()
        self.tray_available=True

    def start(self,startup=False):
        try:self._start_tray()
        except Exception as e:self.report_error('托盘启动失败，窗口保持可见：'+str(e));self.window.show()
        try:self.window.native.FormClosing+=self._allow_windows_shutdown
        except (AttributeError,TypeError):pass
        try:
            path=ROOT/'.runtime/desktop-window.json';path.parent.mkdir(parents=True,exist_ok=True)
            path.write_text(json.dumps({'pid':os.getpid(),'hwnd':int(self.window.native.Handle.ToInt64())}),encoding='utf-8')
            self.apply_identity()
        except Exception as e:self.report_error('角色外观应用失败：'+str(e))
        if startup and not self.tray_available:self.window.show()
        if load()['desktop']['auto_start_services']:
            try:self.api.command('start')
            except Exception as e:self.report_error(str(e))
        threading.Thread(target=self._supervise,daemon=True).start()

    def _supervise(self):
        while not self._stop.wait(load()['desktop']['supervisor_interval_seconds']):
            try:self.apply_identity();self.api._recover_once()
            except Exception as e:self.report_error(str(e))

    def apply_identity(self,force=False,identity=None,register=True):
        from .identity import installed_identity
        with self._identity_lock:
            identity=identity or installed_identity(ROOT)
            profile=identity.profile()
            if profile['revision']==self._identity_revision and not force:return {'applied':True}
            if os.name=='nt':
                from System import Action
                from System.Drawing import Icon
                icon=Icon(str(identity.image_path('icon','ico')))
                old=self._native_icon
                def update():
                    self.window.native.Text=identity.title();self.window.native.Icon=icon
                self.window.native.Invoke(Action(update));self._native_icon=icon
                if old:old.Dispose()
            else:self.window.set_title(identity.title())
            if self.tray:
                from PIL import Image
                with Image.open(identity.image_path('icon')) as source:self.tray.icon=source.copy()
                self.tray.title=identity.title()
            if register:self.api._integration.register()
            self._identity_revision=profile['revision']
            return {'applied':True,'shortcuts_updated':register}

    def report_error(self,message):
        repeated=message==self._last_error
        self._last_error=message
        cfg=load();Log(Store(ROOT/'.runtime/desktop-logs'),(cfg['model']['key_env'],))('ERROR','desktop_error',raw=message)
        if self.tray_available and not repeated:
            try:self.tray.notify('程序操作未完成，请打开运行记录或程序诊断查看。',NAME)
            except Exception:pass

    def close(self):
        self._stop.set()
        if self._timer:self._timer.cancel()
        self._save_geometry()
        if self.tray:
            try:self.tray.stop()
            except Exception:pass
        self.tray_available=False
