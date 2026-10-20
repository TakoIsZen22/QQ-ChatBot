"""首次使用向导：独立 QQ 组件、配置和扫码前准备；不会解除暂停。"""
import json
import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from .config import ROOT,load,save_local,merge,validate
from .runtime_downloads import catalog,download,safe_zip
from .runtime_paths import python_command,portable

HIDDEN=getattr(subprocess,'CREATE_NO_WINDOW',0)


class Onboarding:
    def __init__(self,api):
        self.api=api;self._lock=threading.Lock();self._job={'running':False,'stage':'idle','message':'等待准备 QQ 组件','received':0,'total':0}

    def update(self,**patch):
        with self._lock:self._job.update(patch)

    def status(self):
        cfg=load();qq=Path(cfg['qq']['client_path']) if cfg['qq']['client_path'] else ROOT/'.runtime/qq-client/QQ.exe'
        with self._lock:job=dict(self._job)
        return {'portable':portable(),'configured':bool(cfg['owner']['qq_id'] and cfg['qq']['bot_id'] and cfg['model']['main']),
            'accounts':{'owner_name':cfg['owner']['name'],'owner_id':cfg['owner']['qq_id'],'bot_id':cfg['qq']['bot_id']},
            'model':{k:cfg['model'][k] for k in ('provider','base_url','key_env','main','auxiliary')},
            'components':{'napcat':(ROOT/'.runtime/napcat/NapCatWinBootMain.exe').is_file(),'qq':qq.is_file()},'job':job}

    def save(self,body):
        if not isinstance(body,dict) or set(body)!={'owner_name','owner_id','bot_id','model'}:raise ValueError('首次设置字段无效')
        if not isinstance(body['model'],dict) or set(body['model'])!={'provider','base_url','key_env','main','auxiliary'}:raise ValueError('模型设置字段无效')
        if any(not isinstance(body[k],str) for k in ('owner_name','owner_id','bot_id')):raise ValueError('账号字段必须是文本')
        owner=body['owner_id'].strip();bot=body['bot_id'].strip()
        if not owner.isascii() or not bot.isascii() or not owner.isdigit() or not bot.isdigit() or owner==bot:raise ValueError('请填写不同的主人 QQ 与机器人 QQ 号')
        if not body['model']['main'].strip():raise ValueError('请填写可用的主模型 ID')
        patch={'owner':{'name':body['owner_name'].strip() or '你','qq_id':owner},'qq':{'enabled':True,'bot_id':bot},'model':body['model']}
        candidate=load();merge(candidate,patch);validate(candidate)
        if not self.api._command_lock.acquire(blocking=False):raise RuntimeError('正在处理其他服务操作，请稍候')
        try:
            if self.api._backend.port(load()['server']['port']):
                status=self.api._backend.request('status')
                if status.get('busy') or status.get('queue') or status.get('agent_active'):raise RuntimeError('正在聊天或处理已转交工作，请完成或取消后再修改首次设置')
                self.api._backend.stop_core()
            old=load()
            if (old['qq']['bot_id'],old['owner']['qq_id'])!=(bot,owner):self.api._backend.stop_qq()
            save_local(patch)
            self.api._set_desired(True)
            self.api._backend.start_core()
            return {'saved':True,'message':'账号与模型已保存。完成组件准备后启动扫码，最后手动开启只回复。'}
        finally:self.api._command_lock.release()

    def install(self):
        if not self.api._command_lock.acquire(blocking=False):raise RuntimeError('正在处理其他服务操作，请稍候')
        self.update(running=True,stage='starting',message='正在准备组件…',received=0,total=0)
        threading.Thread(target=self._install,daemon=True).start()
        return {'started':True}

    def _sevenzip(self,cfg):
        candidates=[ROOT/'_tools/7zip/7z.exe',ROOT/'.runtime/napcat-installer/7z.exe']
        system=shutil.which('7z')
        if system:candidates.append(Path(system))
        for file in candidates:
            if file.is_file():return file
        self.update(stage='tools',message='正在准备解压工具…')
        msi=download(cfg['sevenzip'],ROOT/'.runtime/public-downloads',self._progress)
        target=(ROOT/'.runtime/components/7zip').resolve();target.mkdir(parents=True,exist_ok=True)
        args=['msiexec.exe','/a',str(msi),'/qn','TARGETDIR='+str(target)]
        subprocess.run(args,creationflags=HIDDEN,check=True,timeout=cfg['limits']['extract_timeout_seconds'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        files=list(target.rglob('7z.exe'))
        if len(files)!=1:raise ValueError('解压工具准备失败，请使用 Windows 发布包')
        return files[0]

    def _progress(self,size,total):self.update(received=size,total=total)

    def _install(self):
        try:
            cfg=catalog(ROOT);runtime=ROOT/'.runtime';runtime.mkdir(exist_ok=True)
            if shutil.disk_usage(ROOT).free<3*1024**3:raise ValueError('请至少预留 3 GB 可用空间')
            # A private staging directory is removed on exit, existing installations never overwritten.
            with tempfile.TemporaryDirectory(prefix='qq-setup-',dir=runtime) as temp:
                stage=Path(temp);nap=runtime/'napcat';qq=runtime/'qq-client';installed=self.status()['components']
                if not installed['napcat']:
                    if nap.exists() and any(nap.iterdir()):raise ValueError('NapCat 目录已有不完整文件，请保留后交由维护者修复；向导不会覆盖登录数据')
                    self.update(stage='napcat',message='正在下载 NapCat（官方 GitHub）…',received=0,total=0)
                    archive=download(cfg['napcat'],runtime/'public-downloads',self._progress,cfg['limits']['download_timeout_seconds'])
                    self.update(stage='extract',message='正在校验和解压 NapCat…')
                    safe_zip(archive,stage/'napcat',cfg['limits'])
                    if not all((stage/'napcat'/n).is_file() for n in ('NapCatWinBootMain.exe','NapCatWinBootHook.dll','loadNapCat.js','napcat.mjs')):raise ValueError('NapCat 包结构与适配器不匹配')
                    if nap.exists():nap.rmdir()
                    (stage/'napcat').rename(nap)
                if not installed['qq']:
                    if qq.exists() and any(qq.iterdir()):raise ValueError('独立 QQ 目录已有不完整文件，向导不会覆盖，请交由维护者检查')
                    self.update(stage='qq',message='正在下载独立 QQ（腾讯官方 CDN）…',received=0,total=0)
                    archive=download(cfg['qq'],runtime/'public-downloads',self._progress,cfg['limits']['download_timeout_seconds'])
                    seven=self._sevenzip(cfg)
                    self.update(stage='extract',message='正在解压独立机器人 QQ，不修改系统 QQ…')
                    dest=stage/'qq-client';dest.mkdir()
                    subprocess.run([str(seven),'x',str(archive),'-y','-o'+str(dest)],creationflags=HIDDEN,check=True,timeout=cfg['limits']['extract_timeout_seconds'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    binaries=list(dest.rglob('QQ.exe'))
                    if len(binaries)!=1 or not binaries[0].parent.is_relative_to(dest):raise ValueError('QQ 安装包结构已变化，请由维护者更新适配')
                    client=binaries[0].parent
                    if not (client/'resources/app/package.json').is_file() and not (client/'versions/config.json').is_file():raise ValueError('QQ 版本元数据缺失')
                    if qq.exists():qq.rmdir()
                    client.rename(qq)
                    save_local({'qq':{'client_path':str(qq/'QQ.exe')}})
                elif not load()['qq']['client_path'] and (qq/'QQ.exe').is_file():save_local({'qq':{'client_path':str(qq/'QQ.exe')}})
            self.update(running=False,stage='done',message='组件已准备好。保存账号后即可启动扫码。',received=0,total=0)
        except Exception as e:
            # No upstream response/body or credentials are captured in setup diagnostics.
            message=str(e) if isinstance(e,ValueError) else '下载或解压失败（'+type(e).__name__+'）。检查网络后重试；已安装的组件与登录态会保留。'
            self.update(running=False,stage='error',message=message)
            from .log import Log
            from .store import Store
            c=load();Log(Store(ROOT/'.runtime/desktop-logs'),(c['model']['key_env'],c['qq']['token_env']))('ERROR','setup_failed',raw=message)
        finally:self.api._command_lock.release()

    def start(self):
        cfg=load()
        if not cfg['owner']['qq_id'] or not cfg['qq']['bot_id'] or not cfg['model']['main']:raise ValueError('请先保存账号与模型设置')
        if not all(self.status()['components'].values()):raise ValueError('请先完成 QQ 组件准备')
        if not self.api._command_lock.acquire(blocking=False):raise RuntimeError('正在处理其他服务操作，请稍候')
        try:
            folder=ROOT/'.runtime/napcat/config';folder.mkdir(parents=True,exist_ok=True)
            web=folder/'webui.json'
            if not web.exists():web.write_text(json.dumps({'host':'127.0.0.1','port':6099}),encoding='utf-8')
            # NapCat itself fills its auth defaults; harness never generates/reads WebUI tokens.
            result=subprocess.run([python_command(),str(ROOT/'tools/setup-napcat.py')],creationflags=HIDDEN,capture_output=True,timeout=15)
            if result.returncode:raise ValueError('OneBot 配置准备失败，请检查账号与本机端口设置')
            self.api._set_desired(True)
            return {'message':self.api._backend.start_all()}
        finally:self.api._command_lock.release()
