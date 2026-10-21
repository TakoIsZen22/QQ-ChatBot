"""首次使用向导：独立 QQ 组件、配置和扫码前准备；不会解除暂停。"""
import shutil
import subprocess
import tempfile
import threading
import hashlib
from pathlib import Path
from .config import ROOT,load,save_local,merge,validate
from .runtime_downloads import catalog,download
from .runtime_paths import portable
from .qq_native import diagnose

HIDDEN=getattr(subprocess,'CREATE_NO_WINDOW',0)


class Onboarding:
    def __init__(self,api):
        self.api=api;self._lock=threading.Lock();self._job={'running':False,'stage':'idle','message':'等待准备 QQ 组件','received':0,'total':0}
        self._auto_attempted=False

    def _password(self):
        from .qq_password import QQPassword
        cfg=load()
        return QQPassword(ROOT,str(cfg['qq']['bot_id']),cfg['account']['remember_days'])

    def password_status(self):return self._password().status()

    def password_login(self,body):
        if not isinstance(body,dict) or set(body)!={'password','remember','auto'} or not isinstance(body['password'],str) or any(type(body[k]) is not bool for k in ('remember','auto')):
            raise ValueError('QQ 登录参数无效')
        if body['auto'] and not body['remember']:raise ValueError('自动登录需要先勾选记住密码')
        if len(body['password'])>256 or '\x00' in body['password']:raise ValueError('QQ 密码格式无效')
        cache=self._password()
        if body['password']:
            hashed=hashlib.md5(body['password'].encode()).hexdigest()  # Required QQNT protocol, not app password storage.
        else:
            saved=cache.read()
            if not saved:raise ValueError('请输入机器人 QQ 的密码；这不是本机程序账号密码')
            hashed=saved['hash']
        from .native_host import NativeHost
        if not self.api._command_lock.acquire(blocking=False):raise RuntimeError('正在处理其他服务操作，请稍候')
        try:
            host=NativeHost(ROOT)
            if not host.owned():self.start_unlocked()
            result=host.login({'action':'password','uin':str(load()['qq']['bot_id']),'password_md5':hashed})
            warning=''
            if result.get('phase') in ('password_authenticating','password_accepted','password_captcha','password_device','ready'):
                if body['remember']:
                    try:cache.save(hashed,body['auto'])
                    except (OSError,ValueError):
                        cache.forget()
                        warning='本次登录已提交，但 Windows 未能保存密码。'
                else:cache.forget()
            else:cache.disable_auto()
            self._auto_attempted=True
            return dict(result,message=warning or 'QQ 账密登录已提交，请查看登录状态；可能需要安全验证。')
        finally:self.api._command_lock.release()

    def start_unlocked(self):
        cfg=load()
        if not cfg['owner']['qq_id'] or not cfg['qq']['bot_id'] or not cfg['model']['main']:raise ValueError('请先保存账号与模型设置')
        return self.api._backend.start_qq()

    def password_auto(self):
        if self._auto_attempted:return {'attempted':False}
        self._auto_attempted=True
        from .service_intent import ServiceIntent
        if not ServiceIntent(ROOT).desired():return {'attempted':False}
        saved=self._password().read()
        if not saved or not saved['auto']:return {'attempted':False}
        from .native_host import NativeHost
        host=NativeHost(ROOT)
        if host.owned():return {'attempted':False,'message':'QQ 接入已运行，保留当前登录流程。'}
        return dict(self.password_login({'password':'','remember':True,'auto':True}),attempted=True)

    def password_verify(self,body):
        from .native_host import NativeHost
        from .qq_verification import open_verification
        if body=={'completed':True}:
            host=NativeHost(ROOT)
            challenge=host.login({'action':'challenge'})
            if challenge.get('kind')!='device':raise ValueError('当前不是设备验证，请重新打开安全验证')
            return host.login({'action':'continue','challenge_id':challenge['challenge_id']})
        if body is not None:raise ValueError('QQ 验证参数无效')
        host=NativeHost(ROOT)
        challenge=host.login({'action':'challenge'})
        return open_verification(challenge,lambda data:host.login(dict(data,challenge_id=challenge['challenge_id'])))

    def password_forget(self):
        self._password().forget()
        return {'message':'已清除本程序保存的 QQ 密码与自动登录设置；当前登录保持不变。'}

    def update(self,**patch):
        with self._lock:self._job.update(patch)

    def status(self):
        cfg=load();qq=ROOT/'.runtime/qq-client/QQ.exe'
        with self._lock:job=dict(self._job)
        bridge=diagnose(ROOT,cfg,probe=False)
        ready=qq.is_file() or bridge['entry']['runtime_verified']
        return {'portable':portable(),'configured':bool(cfg['owner']['qq_id'] and cfg['qq']['bot_id'] and cfg['model']['main']),
            'accounts':{'owner_name':cfg['owner']['name'],'owner_id':cfg['owner']['qq_id'],'bot_id':cfg['qq']['bot_id']},
            'model':{k:cfg['model'][k] for k in ('provider','base_url','key_env','main','auxiliary')},
            'components':{'bridge':(ROOT/'src/qq_native/entry.js').is_file(),'qq':ready},
            'bridge':bridge,
            'qq_client':{'path':str(qq) if qq.is_file() else '','reused':False},
            'job':job}

    def local_clients(self):
        from .local_qq import scan
        return scan(ROOT)

    def use_local(self,body):
        if not isinstance(body,dict) or set(body)!={'index'} or type(body['index']) is not int:
            raise ValueError('请选择检测结果中的 QQ，不能提交任意路径')
        if not self.api._command_lock.acquire(blocking=False):raise RuntimeError('正在处理其他服务操作，请稍候')
        self.update(running=True,stage='copy',message='正在检查并复制已适配的本机 QQ 程序文件…',received=0,total=0)
        threading.Thread(target=self._copy_local,args=(body['index'],),daemon=True).start()
        return {'started':True,'message':'正在复制到独立目录，日常 QQ 与登录态保持原样。'}

    def _copy_local(self,index):
        from .local_qq import copy_program
        from .native_host import NativeHost
        from .native_compat import linked
        try:
            if NativeHost(ROOT).owned():raise ValueError('独立 QQ 正在运行，请先在窗口手动停止接入后再更换程序文件')
            runtime=ROOT/'.runtime'
            if any(linked(p) for p in [runtime,*runtime.parents]):raise ValueError('运行目录不能使用链接或联接目录')
            runtime.mkdir(exist_ok=True)
            if shutil.disk_usage(ROOT).free<3*1024**3:raise ValueError('请至少预留 3 GB 可用空间')
            with tempfile.TemporaryDirectory(prefix='qq-local-',dir=runtime) as temp:
                version=copy_program(ROOT,index,Path(temp)/'client')
                destination=runtime/'qq-client/versions'/version
                if any(linked(p) for p in [destination,*destination.parents]):raise ValueError('独立 QQ 目录不能使用链接或联接目录')
                if destination.exists():raise ValueError('独立目录已存在此版本，保留原文件；可直接检查并启动，不覆盖现有安装')
                destination.parent.mkdir(parents=True,exist_ok=True)
                (Path(temp)/'client').rename(destination)
                save_local({'qq':{'native_version':version}})
            self.update(running=False,stage='done',message='已复制兼容的 QQ 程序文件；请手动扫码接入并验证收发，聊天模式保持不变。')
        except Exception as error:
            self.update(running=False,stage='error',message=str(error) if type(error) is ValueError else '复制失败（'+type(error).__name__+'），未改动系统 QQ 或既有安装')
        finally:self.api._command_lock.release()

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
                if status.get('busy') or status.get('queue'):raise RuntimeError('正在聊天，请完成后再修改首次设置')
                self.api._backend.stop_core()
            old=load()
            if (old['qq']['bot_id'],old['owner']['qq_id'])!=(bot,owner):self.api._backend.stop_qq()
            save_local(patch)
            self.api._set_desired(True)
            self.api._backend.start_core()
            return {'saved':True,'message':'账号与模型已保存。准备组件后可扫码；聊天安全模式保持不变。'}
        finally:self.api._command_lock.release()

    def install(self):
        if not self.api._command_lock.acquire(blocking=False):raise RuntimeError('正在处理其他服务操作，请稍候')
        self.update(running=True,stage='starting',message='正在准备组件…',received=0,total=0)
        threading.Thread(target=self._install,daemon=True).start()
        return {'started':True}

    def _sevenzip(self,cfg):
        candidates=[ROOT/'_tools/7zip/7z.exe']
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
                stage=Path(temp);qq=runtime/'qq-client';installed=self.status()['components']
                if not installed['qq']:
                    if qq.exists() and any(qq.iterdir()):raise ValueError('独立 QQ 目录已有不完整文件，向导不会覆盖，请交由维护者检查')
                    self.update(stage='qq',message='正在下载独立 QQ（腾讯官方 CDN）…',received=0,total=0)
                    archive=download(cfg['qq'],runtime/'public-downloads',self._progress,cfg['limits']['download_timeout_seconds'])
                    seven=self._sevenzip(cfg)
                    self.update(stage='extract',message='正在解压独立 QQ；自写桥接仍待实连验收…')
                    dest=stage/'qq-client';dest.mkdir()
                    subprocess.run([str(seven),'x',str(archive),'-y','-o'+str(dest)],creationflags=HIDDEN,check=True,timeout=cfg['limits']['extract_timeout_seconds'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    binaries=list(dest.rglob('QQ.exe'))
                    if len(binaries)!=1 or not binaries[0].parent.is_relative_to(dest):raise ValueError('QQ 安装包结构已变化，请由维护者更新适配')
                    client=binaries[0].parent
                    if not (client/'resources/app/package.json').is_file() and not (client/'versions/config.json').is_file():raise ValueError('QQ 版本元数据缺失')
                    if qq.exists():qq.rmdir()
                    client.rename(qq)
                    save_local({'qq':{'client_path':str(qq/'QQ.exe'),'native_version':''}})
                elif not load()['qq']['client_path'] and (qq/'QQ.exe').is_file():save_local({'qq':{'client_path':str(qq/'QQ.exe')}})
            self.update(running=False,stage='done',message='官方 QQ 文件已准备。点击扫码接入并在手机确认；不会自动解除暂停。',received=0,total=0)
        except Exception as e:
            # No upstream response/body or credentials are captured in setup diagnostics.
            message=str(e) if isinstance(e,ValueError) else '下载或解压失败（'+type(e).__name__+'）。检查网络后重试；已安装的组件与登录态会保留。'
            self.update(running=False,stage='error',message=message)
            from .log import Log
            from .store import Store
            c=load();Log(Store(ROOT/'.runtime/desktop-logs'),(c['model']['key_env'],))('ERROR','setup_failed',raw=message)
        finally:self.api._command_lock.release()

    def start(self):
        cfg=load()
        if not cfg['owner']['qq_id'] or not cfg['qq']['bot_id'] or not cfg['model']['main']:raise ValueError('请先保存账号与模型设置')
        if not all(self.status()['components'].values()):raise ValueError('请先完成 QQ 组件准备')
        if not self.api._command_lock.acquire(blocking=False):raise RuntimeError('正在处理其他服务操作，请稍候')
        try:
            return {'message':self.api._backend.start_qq()}
        finally:self.api._command_lock.release()

    def refresh_qr(self):
        from .native_host import NativeHost
        if not self.api._command_lock.acquire(blocking=False):raise RuntimeError('正在处理其他服务操作，请稍候')
        try:return NativeHost(ROOT).control('refresh_qr')
        finally:self.api._command_lock.release()

    def stop(self):
        if not self.api._command_lock.acquire(blocking=False):raise RuntimeError('正在处理其他服务操作，请稍候')
        try:
            return {'message':self.api._backend.stop_qq()}
        finally:self.api._command_lock.release()
