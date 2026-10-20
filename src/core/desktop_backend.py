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
        from .native_host import NativeHost
        return NativeHost(ROOT).start(cfg)['message']

    def start_all(self,managed=False):
        core=self.start_core(managed=managed)
        # Desktop startup/recovery starts local chat only. QR login is a manual action.
        return core+'；QQ 登录请在首次使用向导手动启动'

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
        from .native_host import NativeHost
        return NativeHost(ROOT).control('stop')['message']

    def stop_all(self):
        core=self.stop_core();qq=self.stop_qq();return core+'；'+qq

    def restart_core(self):
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
