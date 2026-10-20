"""跨进程保存服务运行意图，避免桌面守护与人工停机维护相互打架。"""
import json
import uuid
from datetime import datetime,timezone
from pathlib import Path


class ServiceIntent:
    def __init__(self,root):self.path=Path(root)/'.runtime/service-intent.json'
    def desired(self,fallback=True):
        if not self.path.is_file():return fallback
        try:
            state=json.loads(self.path.read_text(encoding='utf-8'))
            return state.get('desired') is True
        except (OSError,ValueError):return False
    def write(self,desired,reason):
        self.path.parent.mkdir(parents=True,exist_ok=True)
        temp=self.path.with_name('service-intent-'+uuid.uuid4().hex+'.tmp')
        temp.write_text(json.dumps({'desired':bool(desired),'reason':reason,'ts':datetime.now(timezone.utc).isoformat()}),encoding='utf-8')
        temp.replace(self.path)
