"""WebView桌面桥：固定本机端点与操作清单；外部内容不获得通用系统能力。"""
import base64
import json
import os
import threading
import time
import webbrowser
from datetime import datetime
from zoneinfo import ZoneInfo
from urllib.parse import urlsplit,parse_qs
from .config import ROOT,load,save_local,merge,validate
from .desktop_backend import DesktopBackend
from .desktop_platform import WindowsIntegration
from .desktop_maintenance import DesktopMaintenance
from .service_intent import ServiceIntent
from .product import is_harness
from ..version import VERSION
from functools import wraps
import inspect
from .local_account import LocalAccount
from .remembered_login import RememberedLogin

def signed_in(method):
    @wraps(method)
    def protected(self,*args,**kwargs):
        self._require_login()
        return method(self,*args,**kwargs)
    # pywebview exports argument names using getfullargspec, not __wrapped__.
    protected.__signature__=inspect.signature(method)
    return protected

READ_ENDPOINTS={'status','chat','memory','diary','config','models','sticker-intents','supervision','soul','identity','group-monitor'}
WRITE_ENDPOINTS={'chat','memory','diary','growth','promise','safety','config','emotion','music','device','study','mcp','persona','transcribe','share','sticker-intents','soul','identity','model-connection','group-monitor'}
DATA_STREAMS={'emotion','impressions','growth','promises','promise_results','learning','learning_reviews','notifications','plugin_audit','sleep_runs','share_drafts','media','stickers'}

class DesktopApi:
    def __init__(self,backend=None):
        self._backend=backend or DesktopBackend()
        self._session=None
        self._account_lock=threading.RLock()
        self._auto_login_attempted=False
        self._backend._account_token=lambda:self._session
        self._command_lock=threading.Lock()
        self._ui_lock=threading.Lock()
        self._integration=WindowsIntegration()
        self._maintenance=DesktopMaintenance()
        self._lifecycle=None
        self._desired_services=load()['desktop']['auto_start_services']
        self._recoveries=[]
        self._gateway_probe=None
        from .onboarding import Onboarding
        self._onboarding=Onboarding(self)

    def _account(self):return LocalAccount(ROOT,load()['account'])

    def _require_login(self):self._account().require(getattr(self,'_session',None))

    def _signed_in(self):return self._account().authenticated(getattr(self,'_session',None))

    def account(self,action='status',body=None):
        with self._account_lock:
            return self._account_action(action,body)

    def _account_action(self,action,body):
        account=self._account()
        saved=RememberedLogin(ROOT,load()['account'])
        if action=='status':
            appearance={k:load()['desktop'][k] for k in ('theme','font_scale')}
            return dict(account.status(self._session),appearance=appearance,remember=saved.status(account))
        if body is None:body={}
        if not isinstance(body,dict):raise ValueError('账号参数必须为对象')
        fields={'setup':{'username','password'},'login':{'username','password'},'change':{'username','password','current_password'},'lock':set(),'resume':set(),'forget':set()}
        options={'remember_password','auto_login'} if action in ('setup','login','change') else set()
        if action=='login':options.add('use_saved')
        if action not in fields or not fields[action]<=set(body) or set(body)-fields[action]-options:raise ValueError('本机账号操作参数无效')
        if any(type(body[k]) is not bool for k in options & set(body)):raise ValueError('记住密码与自动登录开关必须为布尔值')
        if body.get('auto_login') and not body.get('remember_password'):raise ValueError('自动登录需要先勾选记住密码')
        credentials={k:body[k] for k in fields[action]}
        if action=='resume':
            if not self._auto_login_attempted:
                self._auto_login_attempted=True
                value=saved.read(account)
                if value and value['auto_login']:
                    try:self._session=account.login(value['username'],value['password'],expected_revision=value['revision'])
                    except (ValueError,PermissionError):
                        # A rejected automatic attempt is not repeated on reload.
                        saved.forget()
            return self.account()
        if action=='forget':
            saved.forget();account._audit('remember_forgotten')
            return self.account()
        if action=='setup':
            # An older running core must not silently remain an unauthenticated backdoor.
            if self._backend.port(load()['server']['port']):
                try:ready=self._backend.request('account/status').get('enforcement')==1
                except Exception:ready=False
                if not ready:raise ValueError('当前聊天服务尚未支持账号校验，请先在总览重启聊天服务，再设置本机账号')
            self._session=account.setup(**credentials)
        elif action=='login':
            if body.get('use_saved'):
                value=saved.read(account)
                if not value or value['username']!=body['username'] or body['password']:raise ValueError('已保存的密码不可用，请手动输入')
                credentials['password']=value['password']
                credentials['expected_revision']=value['revision']
            self._session=account.login(**credentials)
        elif action=='change':self._session=account.change(self._session,**credentials)
        elif action=='lock':
            value=saved.read(account)
            account.lock(self._session);self._session=None
            self._auto_login_attempted=True
            # Explicit lock/hide always disables automatic unlocking, across restart.
            if value:
                try:saved.save(account,value['username'],value['password'],False,value['expires'])
                except (ValueError,OSError):saved.forget()
        warning=''
        if action in ('setup','login','change'):
            self._auto_login_attempted=True
            if body.get('remember_password'):
                try:
                    account.require(self._session)
                    saved.save(account,credentials['username'].strip(),credentials['password'],body.get('auto_login',False))
                    account._audit('remember_enabled')
                except (ValueError,PermissionError,OSError):
                    saved.forget();warning='已登录，但 Windows 未能保存密码，请重新勾选后登录。'
            else:saved.forget()
        return dict(self.account(),warning=warning)

    @signed_in
    def onboarding(self,action='status',body=None):
        if action=='status':return self._onboarding.status()
        if action=='save':return self._onboarding.save(body)
        if action=='install':return self._onboarding.install()
        if action=='local_clients':return self._onboarding.local_clients()
        if action=='use_local':return self._onboarding.use_local(body)
        if action=='start':return self._onboarding.start()
        if action=='refresh_qr':return self._onboarding.refresh_qr()
        if action=='stop':return self._onboarding.stop()
        if action=='password_status':return self._onboarding.password_status()
        if action=='password_login':return self._onboarding.password_login(body)
        if action=='password_auto':return self._onboarding.password_auto()
        if action=='password_verify':return self._onboarding.password_verify(body)
        if action=='password_forget':return self._onboarding.password_forget()
        raise PermissionError('未允许的首次设置操作')

    def _bind_lifecycle(self,lifecycle):self._lifecycle=lifecycle

    @signed_in
    def refresh_identity(self):
        if not self._lifecycle:return {'applied':False,'note':'桌面窗口打开后自动应用程序图标'}
        return self._lifecycle.apply_identity(force=True)

    def _set_desired(self,value):
        self._desired_services=value
        ServiceIntent(ROOT).write(value,'desktop_intent')

    @signed_in
    def preferences(self,patch=None):
        allowed={'start_with_windows','startup_hidden','auto_start_services','close_to_tray','minimize_to_tray','auto_recover','theme','font_scale'}
        if patch is not None:
            if not isinstance(patch,dict) or set(patch)-allowed:raise ValueError('未允许的程序设置')
            candidate=load();merge(candidate,{'desktop':patch});validate(candidate)
            previous=self._integration.startup()
            try:
                if 'start_with_windows' in patch:self._integration.set_startup(patch['start_with_windows'])
                save_local({'desktop':patch})
            except Exception:
                if 'start_with_windows' in patch and previous['supported']:self._integration.set_startup(previous['registered'])
                raise
        cfg=load()['desktop']
        attempts=sum(time.monotonic()-t<cfg['restart_window_seconds'] for t in self._recoveries)
        return {'settings':{k:cfg[k] for k in allowed},'startup':self._integration.startup(),
                'tray_available':bool(self._lifecycle and self._lifecycle.tray_available),'version':VERSION,
                'recovery':{'desired':self._desired_services and ServiceIntent(ROOT).desired(),'attempts':attempts,'limited':attempts>=cfg['max_auto_restarts']}}

    def window_action(self,action):
        if action not in ('show','hide','exit_ui','exit_all'):raise PermissionError('未允许的窗口操作')
        if not self._lifecycle:raise RuntimeError('请在桌面程序中操作窗口')
        if action=='exit_all':self.command('stop')
        return self._lifecycle.action(action)

    @signed_in
    def maintenance(self,action,name=None,confirmation=None):
        if action=='list':return self._maintenance.backups()
        if action=='verify':return self._maintenance.verify(name)
        if action=='diagnostics':return self._maintenance.diagnostics(self._backend)
        if action=='export_diagnostics':return self._maintenance.export_diagnostics(self._backend)
        if action not in ('backup','restore'):raise PermissionError('未允许的维护操作')
        if confirmation!=action:raise ValueError('请在程序窗口确认这次维护操作')
        if action=='restore':self._maintenance.verify(name)
        if not self._command_lock.acquire(blocking=False):raise RuntimeError('有服务操作正在进行，请稍候')
        was_running=False;stopped=False;changed=False;desired=self._desired_services and ServiceIntent(ROOT).desired()
        try:
            was_running=self._backend.port(load()['server']['port'])
            if was_running:
                status=self._backend.request('status')
                if not is_harness(status):raise RuntimeError('聊天端口不属于本项目，拒绝停止')
                if status.get('busy') or status.get('queue'):raise RuntimeError('正在聊天，请完成后再维护')
            self._set_desired(False)
            changed=True
            if was_running:self._backend.stop_core();stopped=True
            result=self._maintenance.run(action,name)
            return dict(result,message='备份已完成，聊天保持暂停，请手动恢复只回复。' if action=='backup' and was_running else '数据已恢复，聊天保持停止，请核对后再启动。' if action=='restore' else '备份已完成。')
        finally:
            try:
                if action=='backup' and changed:
                    if stopped:self._backend.start_core()
                    self._set_desired(desired)
            finally:self._command_lock.release()

    def _recover_once(self,now=None):
        if not self._signed_in():return
        cfg=load();d=cfg['desktop'];now=time.monotonic() if now is None else now
        if not d['auto_recover'] or not self._desired_services or not ServiceIntent(ROOT).desired() or not self._command_lock.acquire(blocking=False):return
        try:
            from urllib.parse import urlsplit
            missing_core=not self._backend.port(cfg['server']['port'])
            # Experimental QQ has no automatic process launcher in this release.
            missing_qq=False
            if not (missing_core or missing_qq):return
            self._recoveries=[t for t in self._recoveries if now-t<d['restart_window_seconds']]
            if len(self._recoveries)>=d['max_auto_restarts']:return
            self._recoveries.append(now)
            self._backend.start_all(managed=True)
        except Exception as e:
            if self._lifecycle:self._lifecycle.report_error('后台恢复失败：'+str(e))
        finally:self._command_lock.release()

    def request(self,path,body=None):
        if not (path=='safety' and body=={'mode':'paused'}):self._require_login()
        if not isinstance(path,str) or path.startswith(('/','\\')):raise PermissionError('桌面请求路径无效')
        url=urlsplit(path)
        if url.scheme or url.netloc or url.fragment or '..' in url.path:raise PermissionError('桌面请求仅允许固定本机接口')
        endpoint=url.path
        queries={'memory':{'q'},'identity':{'revision'},'group-monitor':{'group_id'}}
        if url.query and (endpoint not in queries or set(parse_qs(url.query,keep_blank_values=True))!=queries[endpoint]):raise PermissionError('查询参数不在允许清单')
        allowed=endpoint in (READ_ENDPOINTS if body is None else WRITE_ENDPOINTS)
        if endpoint.startswith('data/') and body is None:allowed=endpoint[5:] in DATA_STREAMS-{'promise_results','learning_reviews'}
        if not allowed:raise PermissionError('桌面接口不在允许清单')
        if body is not None and not isinstance(body,dict):raise ValueError('操作参数必须为对象')
        if path=='sticker-intents' and body and body.get('action')=='analyze':
            return self._backend.request(path,body,timeout=load()['model']['timeout_seconds']+10)
        if path=='model-connection':
            return self._backend.request(path,body,timeout=load()['model']['models_timeout_seconds']+5)
        return self._backend.request(path,body)

    def command(self,action):
        if action!='stop':self._require_login()
        actions={'start':self._backend.start_all,'restart':self._backend.restart_core,'stop':self._backend.stop_all,'qq':self._backend.start_qq}
        if action not in actions:raise PermissionError('未允许的服务操作')
        if not self._command_lock.acquire(blocking=False):raise RuntimeError('有一个服务操作正在进行，请稍候')
        try:
            if action=='stop':self._set_desired(False)
            elif action in ('start','restart','qq'):self._set_desired(True);self._recoveries=[]
            return {'message':actions[action]()}
        finally:self._command_lock.release()

    @signed_in
    def read_data(self,stream):
        if stream not in DATA_STREAMS:raise PermissionError('数据视图未授权')
        path=ROOT/load()['paths']['data']/(stream+'.jsonl')
        if not path.is_file():return []
        rows=[]
        for n,line in enumerate(path.read_text(encoding='utf-8-sig').splitlines(),1):
            if not line.strip():continue
            try:rows.append(json.loads(line))
            except json.JSONDecodeError as e:raise ValueError(f'{path.name}:{n} JSONL损坏，请停机修复') from e
        return rows[-200:]

    @signed_in
    def events(self):
        cfg=load();path=ROOT/cfg['paths']['logs']/'events.jsonl'
        desktop_log=ROOT/'.runtime/desktop-logs/events.jsonl'
        lines=[]
        for source in (path,desktop_log):
            if source.is_file():lines.extend(source.read_text(encoding='utf-8-sig').splitlines()[-200:])
        rows=[]
        for line in lines:
            if not line.strip():continue
            try:
                value=json.loads(line)
                rows.append({k:value[k] for k in ('ts','level','event','raw','model','usage','mode','channel') if k in value})
            except json.JSONDecodeError:continue
        # 不向界面暴露用户聊天原文、工具参数或凭据；错误原文已由核心日志脱敏。
        return sorted(rows,key=lambda r:r.get('ts',''))[-200:]

    @signed_in
    def runtime(self):
        from urllib.parse import urlsplit
        from .model_endpoint import probe_port
        cfg=load()
        key=(cfg['model']['provider'],cfg['model']['base_url']);now=time.monotonic()
        if not self._gateway_probe or self._gateway_probe[0]!=key or now-self._gateway_probe[1]>=cfg['desktop']['supervisor_interval_seconds']:
            self._gateway_probe=(key,now,probe_port(cfg['model']))
        return {'core':self._backend.port(cfg['server']['port']),'gateway':self._gateway_probe[2],
                'qq_native':self._backend.port(cfg['qq']['native_port']),
                'qq_experimental':True,'qq_launch_available':False,
                'desktop':True,'version':VERSION,'poll_interval_ms':cfg['desktop']['poll_interval_ms'],'usage':self._usage_today(cfg)}

    def _usage_today(self,cfg):
        path=ROOT/cfg['paths']['logs']/'events.jsonl';zone=ZoneInfo(cfg['awakening']['timezone']);today=datetime.now(zone).date()
        total=0;samples=0
        if path.is_file():
            for line in path.read_text(encoding='utf-8-sig').splitlines():
                try:
                    row=json.loads(line)
                    if row.get('event')!='model_usage' or datetime.fromisoformat(row['ts']).astimezone(zone).date()!=today:continue
                    usage=row.get('usage',{});tokens=usage.get('total_tokens')
                    if not isinstance(tokens,(int,float)):
                        prompt=usage.get('prompt_tokens');completion=usage.get('completion_tokens')
                        tokens=prompt+completion if isinstance(prompt,(int,float)) and isinstance(completion,(int,float)) else None
                    if isinstance(tokens,(int,float)) and tokens>=0:total+=tokens;samples+=1
                except (ValueError,KeyError,TypeError):continue
        return {'day':today.isoformat(),'total_tokens':total if samples else None,'samples':samples}

    @signed_in
    def qr(self):
        cfg=load();path=ROOT/'.runtime/qq-native/qrcode.png'
        from .qq_native import status
        current=status(ROOT)
        phase=current.get('phase','not_running')
        messages={
            'not_running':'QQ 接入尚未启动。点击“启动 QQ”，等待二维码出现。',
            'stopped':'QQ 接入已停止。点击“启动 QQ”重新扫码。',
            'starting':'正在启动 QQ 接入，请稍候…',
            'loading_kernel':'正在加载 QQ 组件，请稍候…',
            'connecting':'正在连接 QQ 登录服务，请稍候…',
            'generating_qrcode':'正在生成二维码，请稍候…',
            'qrcode_scanned':'已扫码，请在机器人账号的手机 QQ 上确认登录。',
            'initializing':'登录已确认，正在连接消息服务…',
            'ready':'QQ 已登录，无需扫码。',
            'password_authenticating':'正在验证 QQ 账号密码，请稍候…',
            'password_accepted':'QQ 已接受登录，等待内核确认与消息通道连接…',
            'password_captcha':'QQ 要求滑块验证，请点击“打开安全验证”。',
            'password_device':'QQ 要求新设备验证，请打开安全验证并按手机提示完成。',
            'password_failed':'QQ 账密登录失败。请检查机器人 QQ 密码，或切换扫码；这不是本机程序密码。',
            'password_expired':'账密验证已超时，临时登录信息已清除，请重新提交或改用扫码。',
            'offline':'QQ 连接已断开。请先停止 QQ，再点击启动重新扫码。',
            'qrcode_expired':'二维码已过期，点击“刷新二维码”获取新码。',
        }
        if phase!='waiting_qrcode':
            return {'state':'expired' if phase=='qrcode_expired' else 'unavailable',
                    'phase':phase,'message':messages.get(phase,'QQ 接入异常，请在运行记录查看诊断，或停止后重新启动。')}
        if not path.is_file():return {'state':'missing','phase':phase,'message':'正在等待二维码，请稍候…'}
        age=time.time()-path.stat().st_mtime
        if age>cfg['desktop']['qr_max_age_seconds']:return {'state':'expired','phase':phase,'message':'二维码已过期，点击“刷新二维码”获取新码。'}
        if path.stat().st_size>cfg['server']['max_body_bytes']:raise ValueError('二维码文件过大')
        raw=path.read_bytes()
        if not raw.startswith(b'\x89PNG\r\n\x1a\n'):raise ValueError('二维码不是有效PNG')
        return {'state':'ready','phase':phase,'data_url':'data:image/png;base64,'+base64.b64encode(raw).decode(),'age_seconds':round(max(0,age))}

    @signed_in
    def open_target(self,target):
        if target in ('magpie_guide','magpie_official_docs'):
            from .edition import require_provider
            require_provider('magpie')
        cfg=load()
        if target=='soul':
            from .soul import Soul
            from .store import Store
            path=Soul(cfg['role'],Store(ROOT/cfg['paths']['data']),ROOT).path
            if not path.is_file():raise ValueError('请先在专属人设页保存 soul.md')
            os.startfile(str(path));return {'opened':target}
        files={'project':ROOT,'handoff':ROOT/'HANDOFF.md','logs':ROOT/cfg['paths']['logs'],
               'data':ROOT/cfg['paths']['data'],'backups':ROOT/cfg['paths']['backups'],
               'diagnostics':ROOT/'.runtime/diagnostics','help':ROOT/'docs/DESKTOP.md',
               'agent_guide':ROOT/'docs/AGENT_SUPERVISION.md','agent_rules':ROOT/'AGENTS.md','model_api_guide':ROOT/'docs/MODEL_API.md','magpie_guide':ROOT/'docs/MAGPIE_SETUP.md','getting_started':ROOT/'docs/GETTING_STARTED.md','qq_guide':ROOT/'docs/QQ_SETUP.md','group_guide':ROOT/'docs/GROUP_MONITOR.md'}
        for key in ('backups','diagnostics'):files[key].mkdir(parents=True,exist_ok=True)
        urls={'web':f'http://127.0.0.1:{cfg["server"]["port"]}','magpie_official_docs':'https://usemagpie.ai/docs/zh/start'}
        if target in files:os.startfile(str(files[target]))
        elif target in urls:webbrowser.open(urls[target])
        else:raise PermissionError('只能打开预设的本机项目入口')
        return {'opened':target}

    def guide(self,name):
        from .guides import read_guide
        return read_guide(ROOT,name)

    @signed_in
    def ui_state(self,patch=None):
        # 仅是本机窗口偏好/未发送草稿，不注入对话或人格记忆。
        path=ROOT/'.runtime/desktop-ui.json'
        with self._ui_lock:
            try:state=json.loads(path.read_text(encoding='utf-8')) if path.is_file() else {}
            except json.JSONDecodeError:state={}
            if patch is not None:
                if not isinstance(patch,dict) or set(patch)-{'draft','page','channel','soul_draft'}:raise ValueError('不支持的桌面偏好')
                if 'soul_draft' in patch:
                    draft=patch['soul_draft']
                    if draft is not None and (not isinstance(draft,dict) or set(draft)!={'text','revision'} or not isinstance(draft['text'],str) or len(draft['text'])>load()['role']['soul_max_chars'] or not isinstance(draft['revision'],str) or len(draft['revision'])>64):raise ValueError('人设草稿无效')
                if 'draft' in patch and (not isinstance(patch['draft'],str) or len(patch['draft'])>load()['conversation']['max_input_chars']):raise ValueError('草稿长度无效')
                if 'page' in patch and patch['page'] not in ('chat','overview','memory','diary','tasks','stickers','soul','abilities','settings','system','logs','groups'):raise ValueError('页面无效')
                if 'channel' in patch and patch['channel'] not in ('all','qq','local'):raise ValueError('通道无效')
                state.update(patch);path.parent.mkdir(parents=True,exist_ok=True)
                temp=path.with_suffix('.tmp');temp.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8');temp.replace(path)
            return state
