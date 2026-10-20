"""仅当前Windows用户的自启/开始菜单/卸载登记，不申请管理员权限。"""
import os
import subprocess
from pathlib import Path
from .config import ROOT
from .identity import installed_identity
from .product import NAME
from ..version import VERSION
from .runtime_paths import portable

RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'
APP_KEY = r'Software\Microsoft\Windows\CurrentVersion\Uninstall\DaFeiYuHarness'
VALUE_NAME = 'QQChatBot'
LEGACY_VALUE_NAME = 'DaFeiYuHarness'


class WindowsIntegration:
    def __init__(self, root=ROOT, registry=None):
        self.root = Path(root).resolve()
        if registry is None and os.name == 'nt':
            import winreg
            registry = winreg
        self.registry = registry

    def command(self, argument):
        if argument not in ('--startup','--unregister'):
            raise ValueError('未允许的桌面启动参数')
        if portable(self.root):return subprocess.list2cmdline([str(self.root/'QQ ChatBot.exe'),argument])
        return subprocess.list2cmdline([str(self.root/'.venv/Scripts/pythonw.exe'),str(self.root/'tools/desktop-launch.py'),argument])

    def startup(self):
        r=self.registry
        if r is None:return {'registered':False,'supported':False}
        values=[]
        for name in (VALUE_NAME,LEGACY_VALUE_NAME):
            try:
                with r.OpenKey(r.HKEY_CURRENT_USER,RUN_KEY) as key:values.append(r.QueryValueEx(key,name)[0])
            except FileNotFoundError:values.append(None)
        expected=self.command('--startup')
        return {'registered':expected in values,'supported':True,'entry_exists':any(v is not None for v in values),
                'legacy_registered':values[1]==expected}

    def set_startup(self, enabled):
        if type(enabled) is not bool:raise ValueError('开机自启必须是布尔值')
        r=self.registry
        if r is None:raise RuntimeError('开机自启仅支持Windows')
        with r.CreateKey(r.HKEY_CURRENT_USER,RUN_KEY) as key:
            if enabled:
                try:
                    if r.QueryValueEx(key,VALUE_NAME)[0]!=self.command('--startup'):raise ValueError('QQ ChatBot 开机启动项属于其他安装目录')
                except FileNotFoundError:pass
                r.SetValueEx(key,VALUE_NAME,0,r.REG_SZ,self.command('--startup'))
            for name in (LEGACY_VALUE_NAME,) if enabled else (VALUE_NAME,LEGACY_VALUE_NAME):
                try:
                    if r.QueryValueEx(key,name)[0]==self.command('--startup'):r.DeleteValue(key,name)
                except FileNotFoundError:pass
        return self.startup()

    def register(self):
        r=self.registry
        if r is None:raise RuntimeError('系统登记仅支持Windows')
        try:
            with r.OpenKey(r.HKEY_CURRENT_USER,APP_KEY) as key:location=r.QueryValueEx(key,'InstallLocation')[0]
            if Path(location).resolve()!=self.root:
                return {'registered':False,'reason':'已有其他安装使用同名系统入口；本目录仍可直接打开 EXE'}
        except FileNotFoundError:pass
        icon=installed_identity(self.root).image_path('icon','ico')
        values={'DisplayName':NAME,'DisplayVersion':VERSION,'Publisher':'本机个人项目',
            'InstallLocation':str(self.root),'DisplayIcon':str(icon),
            'UninstallString':self.command('--unregister'),'NoModify':1,'NoRepair':1}
        with r.CreateKey(r.HKEY_CURRENT_USER,APP_KEY) as key:
            for name,value in values.items():r.SetValueEx(key,name,0,r.REG_DWORD if isinstance(value,int) else r.REG_SZ,value)
        # 复用固定脚本创建项目与开始菜单快捷方式，无字符串拼接脚本。
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(self.root/'tools/create-desktop-shortcut.ps1'),'-IconPath',str(icon)],
            cwd=self.root,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),capture_output=True,check=True,timeout=20)
        if self.startup().get('legacy_registered'):self.set_startup(True)
        return {'registered':True}

    def unregister(self):
        r=self.registry
        registered=False
        try:
            with r.OpenKey(r.HKEY_CURRENT_USER,APP_KEY) as key:location=r.QueryValueEx(key,'InstallLocation')[0]
            if Path(location).resolve()!=self.root:raise ValueError('系统登记属于其他目录，不移除')
            registered=True
        except FileNotFoundError:pass
        if self.startup()['registered']:self.set_startup(False)
        if registered:r.DeleteKey(r.HKEY_CURRENT_USER,APP_KEY)
        # 只移除本项目名称且目标匹配的快捷方式；程序与data始终保留。
        subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-ExecutionPolicy','Bypass','-File',str(self.root/'tools/create-desktop-shortcut.ps1'),'-Remove'],
            cwd=self.root,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),capture_output=True,check=True,timeout=20)
        return {'removed':True,'data_preserved':True}
