"""本机程序维护：备份复用已验收的manage.py；诊断导出仅包含运行元数据。"""
import json
import platform
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from .config import ROOT, load
from ..version import VERSION
from .runtime_paths import python_command,portable


class DesktopMaintenance:
    def __init__(self, root=ROOT):self.root=Path(root).resolve()

    def backups(self):
        root=self.root/load()['paths']['backups'];rows=[]
        if root.exists():
            for folder in sorted(root.iterdir(),reverse=True):
                if not folder.is_dir() or not re.fullmatch(r'\d{8}-\d{6}-\d{6}',folder.name):continue
                try:
                    manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
                    rows.append({'name':folder.name,'files':len(manifest['files']),
                        'records':sum(manifest['jsonl_counts'].values()),'created':datetime.fromtimestamp(folder.stat().st_mtime).isoformat()})
                except (OSError,ValueError,KeyError,TypeError):rows.append({'name':folder.name,'invalid':True})
        return rows[:30]

    def backup_path(self,name):
        if not isinstance(name,str) or not re.fullmatch(r'\d{8}-\d{6}-\d{6}',name):raise ValueError('请选择本机备份列表中的快照')
        root=(self.root/load()['paths']['backups']).resolve();path=(root/name).resolve()
        if not path.is_relative_to(root) or path.parent!=root:raise ValueError('备份路径越界')
        if not (path/'manifest.json').is_file() or not (path/'data').is_dir():raise ValueError('备份不完整')
        return path

    def verify(self,name):
        from tools.manage import manifest, validate_jsonl
        path=self.backup_path(name)
        expected=json.loads((path/'manifest.json').read_text(encoding='utf-8'))
        if manifest(path/'data')!=expected['files']:raise ValueError('备份SHA256不匹配，不能恢复')
        counts=validate_jsonl(path/'data')
        return {'verified':True,'name':name,'files':len(expected['files']),'records':sum(counts.values())}

    def run(self,operation,name=None):
        if operation not in ('backup','restore'):raise PermissionError('未允许的维护操作')
        args=[python_command(self.root),str(self.root/'tools/manage.py'),operation]
        if operation=='restore':args.append(str(self.backup_path(name)))
        result=subprocess.run(args,cwd=self.root,capture_output=True,text=True,encoding='utf-8',
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),timeout=load()['desktop']['maintenance_timeout_seconds'])
        if result.returncode:raise RuntimeError((result.stderr or result.stdout or '维护失败').strip()[-1500:])
        if operation=='backup':return {'name':Path(result.stdout.strip().splitlines()[-1]).name,'message':'快照已创建，包含JSONL与媒体附件'}
        return json.loads(result.stdout)

    def diagnostics(self,backend):
        from .model_endpoint import probe_port
        from .qq_native import diagnose
        cfg=load();data=self.root/cfg['paths']['data']
        report={'version':VERSION,'time':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),
            'desktop_python':platform.python_version(),'ports':{'core':backend.port(cfg['server']['port']),'model_api':probe_port(cfg['model'])},
            'disk_free_gb':round(shutil.disk_usage(self.root).free/1024**3,2),
            'jsonl_files':len(list(data.rglob('*.jsonl'))) if data.exists() else 0,
            'dependencies':{'core_python':Path(python_command(self.root)).is_file(),
                'desktop_python':portable(self.root) or (self.root/'.venv-desktop/Scripts/python.exe').is_file(),
                'qq_client':bool(cfg['qq']['client_path'] and Path(cfg['qq']['client_path']).is_file())},
            'backup_count':len(self.backups()),'qq_bridge':diagnose(self.root,cfg),
            'note':'只读诊断不调用模型；不包含聊天、记忆正文、环境变量值或登录凭据。'}
        try:
            status=backend.request('status')
            report['status']={k:status[k] for k in ('name','time','mode','qq_enabled','qq_connected','qq_online','last_spoke','memory_count','queue','busy') if k in status}
        except Exception:report['status_error']='本机聊天服务未连接或响应无效'
        return report

    def export_diagnostics(self,backend):
        report=self.diagnostics(backend);folder=self.root/'.runtime/diagnostics';folder.mkdir(parents=True,exist_ok=True)
        path=folder/(datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.json')
        path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
        return {'path':str(path),'report':report}
