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

READ_ENDPOINTS={'status','chat','memory','diary','config','models','sticker-intents','supervision','soul','identity','group-monitor'}
WRITE_ENDPOINTS={'chat','memory','diary','growth','promise','safety','config','emotion','music','device','study','mcp','persona','transcribe','share','sticker-intents','soul','identity','model-connection','group-monitor'}
DATA_STREAMS={'emotion','impressions','growth','promises','promise_results','learning','learning_reviews','notifications','plugin_audit','sleep_runs','share_drafts','media','stickers'}

class DesktopApi:
    def __init__(self,backend=None):
        self._backend=backend or DesktopBackend()
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

    def onboarding(self,action='status',body=None):
        if action=='status':return self._onboarding.status()
        if action=='save':return self._onboarding.save(body)
        if action=='install':return self._onboarding.install()
        if action=='start':return self._onboarding.start()
        if action=='refresh_qr':return self._onboarding.refresh_qr()
        if action=='stop':return self._onboarding.stop()
        raise PermissionError('未允许的首次设置操作')

    def _bind_lifecycle(self,lifecycle):self._lifecycle=lifecycle

    def refresh_identity(self):
        if not self._lifecycle:return {'applied':False,'note':'桌面窗口打开后自动应用程序图标'}
        return self._lifecycle.apply_identity(force=True)

    def _set_desired(self,value):
        self._desired_services=value
        ServiceIntent(ROOT).write(value,'desktop_intent')

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
        actions={'start':self._backend.start_all,'restart':self._backend.restart_core,'stop':self._backend.stop_all,'qq':self._backend.start_qq}
        if action not in actions:raise PermissionError('未允许的服务操作')
        if not self._command_lock.acquire(blocking=False):raise RuntimeError('有一个服务操作正在进行，请稍候')
        try:
            if action=='stop':self._set_desired(False)
            elif action in ('start','restart','qq'):self._set_desired(True);self._recoveries=[]
            return {'message':actions[action]()}
        finally:self._command_lock.release()

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
               'agent_guide':ROOT/'docs/AGENT_SUPERVISION.md','agent_rules':ROOT/'AGENTS.md','model_api_guide':ROOT/'docs/MODEL_API.md','magpie_guide':ROOT/'docs/MAGPIE_SETUP.md','getting_started':ROOT/'docs/GETTING_STARTED.md','qq_guide':ROOT/'docs/QQ_SETUP.md'}
        for key in ('backups','diagnostics'):files[key].mkdir(parents=True,exist_ok=True)
        urls={'web':f'http://127.0.0.1:{cfg["server"]["port"]}','magpie_official_docs':'https://usemagpie.ai/docs/zh/start'}
        if target in files:os.startfile(str(files[target]))
        elif target in urls:webbrowser.open(urls[target])
        else:raise PermissionError('只能打开预设的本机项目入口')
        return {'opened':target}

    def guide(self,name):
        from .guides import read_guide
        return read_guide(ROOT,name)

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
