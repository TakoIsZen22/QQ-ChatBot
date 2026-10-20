"""Own QQNT host lifecycle. No system QQ search, process-wide kills or auto-login."""
import ctypes
import hashlib
import json
import os
import re
import socket
import subprocess
import time
import uuid
from functools import lru_cache
from pathlib import Path
from .instance import InstanceLock


def atomic(path, value):
    pending=path.with_suffix('.tmp');pending.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8');pending.replace(path)


def _read(path):
    if path.is_symlink() or path.stat().st_size>65536:raise ValueError('原生桥接元数据无效')
    return json.loads(path.read_text(encoding='utf-8'))


@lru_cache(maxsize=24)
def _digest(file, size, modified):
    with Path(file).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def runtime(root):
    from .qq_native import _package
    root=Path(root).resolve();compat=_read(root/'config/qq-native-compat.json')
    package=_package(root);client=package.parents[2]
    if _read(package).get('version')!=compat['version']:raise ValueError('QQ 版本不匹配，请使用向导下载的固定版本')
    if client != root/'.runtime/qq-client/versions'/compat['version']:
        raise ValueError('QQ 目录不符合独立加载器布局，请使用向导准备的固定版本')
    if (root/'.runtime/qq-native/installation.json').exists():
        meta=_read(root/'.runtime/qq-native/installation.json')
        if hashlib.sha256(package.read_bytes()).hexdigest()!=meta['original_sha256']:raise ValueError('请先恢复旧实验入口：tools/qq-native.py restore')
    for relative,expected in compat['sha256'].items():
        file=client/relative
        if not file.resolve().is_relative_to(client.resolve()) or any(p.is_symlink() for p in [file,*file.parents]):raise ValueError('QQ 文件不能使用链接')
        stat=file.stat()
        if _digest(str(file),stat.st_size,stat.st_mtime_ns)!=expected:raise ValueError('QQ 文件校验失败，拒绝加载；保留当前文件并重新准备官方组件')
    return client,compat


def executable(root):
    root=Path(root).resolve()
    for file in (root/'_tools/qq-native/QQChatBot.NativeHost.exe',root/'.runtime/native-host/QQChatBot.NativeHost.exe'):
        if file.is_file() and not any(p.is_symlink() for p in [file,*file.parents]):return file
    raise ValueError('缺少自写加载器：Windows 发布包已内置；源码使用者请运行 python tools/build-native-host.py')


def _process(pid):
    """Read only image path + creation time, never command line or environment."""
    if os.name!='nt' or type(pid) is not int or pid<=0:return None
    from ctypes import wintypes as w
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];kernel.OpenProcess.restype=w.HANDLE
    kernel.CloseHandle.argtypes=[w.HANDLE]
    kernel.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,ctypes.POINTER(w.DWORD)]
    kernel.GetProcessTimes.argtypes=[w.HANDLE,*([ctypes.POINTER(w.FILETIME)]*4)]
    kernel.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)]
    handle=kernel.OpenProcess(0x1000,False,pid)
    if not handle:return None
    try:
        code=w.DWORD()
        if not kernel.GetExitCodeProcess(handle,ctypes.byref(code)) or code.value!=259:return None
        size=w.DWORD(32768);image=ctypes.create_unicode_buffer(size.value)
        born,exit,kern,user=(w.FILETIME() for _ in range(4))
        if not kernel.QueryFullProcessImageNameW(handle,0,image,ctypes.byref(size)) or not kernel.GetProcessTimes(handle,ctypes.byref(born),ctypes.byref(exit),ctypes.byref(kern),ctypes.byref(user)):return None
        return {'image':str(Path(image.value).resolve()),'created':(born.dwHighDateTime<<32)|born.dwLowDateTime}
    finally:kernel.CloseHandle(handle)


class NativeHost:
    def __init__(self,root):
        self.root=Path(root).resolve();self.directory=self.root/'.runtime/qq-native'

    def owned(self):
        try:
            record=_read(self.directory/'process.json');file=executable(self.root)
            actual=_process(record.get('pid'))
            if actual and Path(actual['image'])==file and record['image']==actual['image'] and record['created']==actual['created'] and re.fullmatch('[a-f0-9]{32}',record['run_id']):return record
        except (OSError,ValueError,KeyError,TypeError):pass
        return None

    def status(self):
        record=self.owned()
        if not record:return {'phase':'not_running','online':False,'experimental':True}
        try:
            value=_read(self.directory/'state.json')
            if value.get('schema')!='qq-chatbot.native.v2' or value.get('run_id')!=record['run_id']:raise ValueError('stale_state')
            phase=value.get('phase','starting')
            if not isinstance(phase,str) or not re.fullmatch('[a-z_]{1,48}',phase):raise ValueError('invalid_state')
            return {'phase':phase,'online':value.get('online') is True,'time':value.get('time'),'experimental':True}
        except (OSError,ValueError,TypeError):return {'phase':'starting','online':False,'experimental':True}

    def start(self,cfg):
        if os.name!='nt':raise RuntimeError('真实 QQ 接入需要 Windows x64')
        if not cfg['qq']['enabled']:raise ValueError('请先在向导启用 QQ')
        owner=str(cfg['owner']['qq_id']);bot=str(cfg['qq']['bot_id'])
        if not re.fullmatch('[0-9]{5,12}',owner) or not re.fullmatch('[0-9]{5,12}',bot) or owner==bot:raise ValueError('请配置不同的主人号与机器人号')
        self.directory.mkdir(parents=True,exist_ok=True)
        if any(p.is_symlink() for p in [self.directory,*self.directory.parents]):raise ValueError('运行目录不能使用链接')
        lock=InstanceLock(self.directory/'manager.lock')
        try:
            if self.owned():return {'started':False,'message':'独立 QQ 已运行；需要新二维码时点击刷新二维码'}
            client,compat=runtime(self.root);host=executable(self.root)
            # A foreign process is never killed or adopted because it owns our port.
            with socket.socket() as check:
                try:check.bind(('127.0.0.1',cfg['qq']['native_port']))
                except OSError:raise RuntimeError('QQ 桥接端口已占用，未启动；请先检查所属进程') from None
            run_id=uuid.uuid4().hex
            policy={'owner':owner,'bot':bot,'groups':[str(g['group_id']) for g in cfg['group_monitor']['groups'] if g['enabled']],
                    'port':cfg['qq']['native_port'],'directory':str(self.directory),'client':str(client),'run_id':run_id,'compatibility':compat}
            atomic(self.directory/'host-config.json',policy)
            profile=self.directory/'profile/os';(profile/'roaming').mkdir(parents=True,exist_ok=True);(profile/'local').mkdir(exist_ok=True)
            env=os.environ.copy();env.pop('NODE_OPTIONS',None);env.pop('NODE_PATH',None)
            env['APPDATA']=str(profile/'roaming');env['LOCALAPPDATA']=str(profile/'local')
            # Kernel output may contain opaque login material. It is private, never shown in diagnostics.
            with (self.directory/'host-output.log').open('ab') as log:
                process=subprocess.Popen([str(host),str(client),str(self.root)],cwd=self.root,env=env,
                    stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            actual=_process(process.pid)
            if actual is None:raise RuntimeError('原生加载器未能启动；请核对 Windows x64 与固定 QQ 版本')
            atomic(self.directory/'process.json',dict(actual,pid=process.pid,run_id=run_id))
            deadline=time.monotonic()+compat['limits']['start_timeout_seconds']
            while time.monotonic()<deadline:
                if process.poll() is not None:raise RuntimeError('原生加载器已退出；诊断只报告退出状态，不展示登录数据')
                phase=self.status()['phase']
                if phase not in ('starting','loading_kernel','connecting','generating_qrcode'):return {'started':True,'message':'独立 QQ 已启动；请扫码并在手机确认。聊天安全模式保持不变。'}
                time.sleep(.1)
            return {'started':True,'message':'内核仍在连接，请刷新状态；不要连续重复启动'}
        finally:lock.close()

    def control(self,action):
        if action not in ('refresh_qr','stop'):raise ValueError('无效的原生桥接命令')
        record=self.owned()
        if not record:
            if action=='stop':return {'message':'独立 QQ 加载器已停止；没有停止其他 QQ'}
            raise RuntimeError('请先启动独立 QQ')
        atomic(self.directory/'control.json',{'run_id':record['run_id'],'action':action})
        if action=='refresh_qr':return {'message':'已请求新二维码；在线账号无需刷新，掉线后请停止再启动'}
        timeout=_read(self.root/'config/qq-native-compat.json')['limits']['stop_timeout_seconds']
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if not self.owned():return {'message':'独立 QQ 已停止，登录文件保留；其他 QQ 未受影响'}
            time.sleep(.1)
        # No process-name kill fallback: keep the evidence for manual inspection.
        raise RuntimeError('独立 QQ 停止超时；保留进程与日志，请检查诊断，不会批量结束 QQ')
