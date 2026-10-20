"""桌面控制器的进程/HTTP边界；GUI线程不直接等待网络或子进程。"""
import json
import os
import socket
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
from urllib.parse import urlsplit
from .config import ROOT,load
from .service_intent import ServiceIntent
from .product import is_harness
from .runtime_paths import python_command

HIDDEN = getattr(subprocess,'CREATE_NO_WINDOW',0)

class DesktopBackend:
    def request(self,path,body=None,timeout=None):
        cfg=load()
        timeout=timeout or cfg['desktop']['request_timeout_seconds']
        data=None if body is None else json.dumps(body,ensure_ascii=False).encode('utf-8')
        req=urllib.request.Request(f'http://127.0.0.1:{cfg["server"]["port"]}/api/'+path,data=data,headers={'Content-Type':'application/json','X-Harness-Local':'1'})
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=timeout) as r:return json.load(r)
        except urllib.error.HTTPError as e:
            try:message=json.loads(e.read().decode('utf-8')).get('error')
            except (ValueError,UnicodeDecodeError):message=None
            raise RuntimeError(message or f'本机接口返回 HTTP {e.code}') from None
        except urllib.error.URLError as e:
            raise RuntimeError('本机聊天服务尚未连接，请检查服务状态。') from None

    @staticmethod
    def port(port):
        try:
            with socket.create_connection(('127.0.0.1',port),timeout=.3):return True
        except OSError:return False

    def spawn(self,args,env=None):
        return subprocess.Popen(args,cwd=ROOT,env=env,creationflags=HIDDEN,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,close_fds=True)

    def start_core(self,managed=False):
        cfg=load()
        if not managed:ServiceIntent(ROOT).write(True,'manual_start')
        if self.port(cfg['server']['port']):
            try:
                if is_harness(self.request('status')):return '聊天服务已经在运行'
            except Exception:pass
            raise RuntimeError('聊天端口被其他程序占用或服务无响应，请在程序诊断中检查')
        env=os.environ.copy();env['DFY_MANAGED_START']='1'
        process=self.spawn([python_command(),'-m','src.main'],env)
        deadline=time.monotonic()+cfg['desktop']['start_timeout_seconds']
        while time.monotonic()<deadline:
            if process.poll() is not None:raise RuntimeError('聊天服务启动失败，请在运行记录页检查日志或核对配置')
            try:self.request('status',timeout=.5);return '聊天服务已启动'
            except Exception:time.sleep(.25)
        raise RuntimeError('聊天服务启动超时')

    def start_qq(self):
        cfg=load()
        if not cfg['qq']['enabled']:return 'QQ桥接未启用，可先使用本机聊天'
        port=urlsplit(cfg['qq']['ws_url']).port or 80
        if self.port(port):return 'QQ桥接已经在运行'
        runtime=ROOT/'.runtime/napcat'
        if not (runtime/'NapCatWinBootMain.exe').is_file():raise RuntimeError('未安装NapCat，请按QQ接入指南准备')
        # 凭据只在现有本机环境/原配置中；不采集控制台输出中的登录token。
        harden=subprocess.run([python_command(),str(ROOT/'tools/harden-napcat.py')],cwd=ROOT,creationflags=HIDDEN,capture_output=True,timeout=10)
        if harden.returncode:raise RuntimeError('NapCat本机地址配置失败')
        env=os.environ.copy();env['DFY_DESKTOP_HIDDEN']='1'
        self.spawn([python_command(),str(ROOT/'tools/launch-napcat.py')],env)
        return 'QQ已后台启动；需要登录时请查看「QQ扫码」页'

    def start_all(self,managed=False):
        core=self.start_core(managed=managed)
        try:qq=self.start_qq()
        except Exception as e:qq='QQ未就绪：'+str(e)
        return core+'；'+qq

    def stop_core(self):
        ServiceIntent(ROOT).write(False,'manual_stop')
        cfg=load()
        if not self.port(cfg['server']['port']):return '聊天服务已经停止'
        if not is_harness(self.request('status')):raise RuntimeError('聊天端口不属于本项目，拒绝停止')
        self.request('stop',{})
        deadline=time.monotonic()+cfg['desktop']['stop_timeout_seconds']
        while time.monotonic()<deadline:
            if not self.port(cfg['server']['port']):return '聊天服务已停止'
            time.sleep(.15)
        raise RuntimeError('停止超时，请查看运行记录')

    def stop_qq(self):
        # 仅停止本项目官方loader的进程树，不碰个人QQ、Magpie或其他Python进程。
        env=os.environ.copy();env['DFY_EXPECTED_BOOTER']=str(ROOT/'.runtime/napcat/NapCatWinBootMain.exe')
        command="$ErrorActionPreference='Stop'; $expected=$env:DFY_EXPECTED_BOOTER; Get-CimInstance Win32_Process -Filter \"Name = 'NapCatWinBootMain.exe'\" | Where-Object {$_.ExecutablePath -eq $expected} | ForEach-Object { & taskkill.exe /PID $_.ProcessId /T /F | Out-Null }"
        result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',command],env=env,creationflags=HIDDEN,capture_output=True,timeout=15)
        if result.returncode:raise RuntimeError('QQ后台进程停止失败')
        return '本项目QQ桥接已停止'

    def stop_all(self):
        core=self.stop_core();qq=self.stop_qq();return core+'；'+qq

    def restart_core(self):
        if self.port(load()['server']['port']) and self.request('status').get('agent_active'):
            raise RuntimeError('请先完成或取消已有工作，再重启聊天，避免中断外部 Agent')
        self.stop_core();return self.start_core()+'；为安全起见保留暂停，请点「只回复」恢复'

    def logs(self):
        cfg=load();path=ROOT/cfg['paths']['logs']/'events.jsonl'
        if not path.exists():return '还没有运行记录'
        rows=[]
        for line in path.read_text(encoding='utf-8').splitlines()[-80:]:
            try:
                r=json.loads(line)
                rows.append(f'{r["ts"]}  {r["level"]}  {r["event"]}'+('  '+str(r['raw']) if 'raw' in r else ''))
            except json.JSONDecodeError:rows.append('[无法解析的一行日志，请停机检查]')
        return '\n'.join(rows)
