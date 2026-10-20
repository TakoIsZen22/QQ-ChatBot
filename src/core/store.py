import json
import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

def now():
    return datetime.now(timezone.utc).isoformat()

class Store:
    """进程内串行追加，flush+fsync；事件不可变，删除用 tombstone。"""
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lock = threading.RLock()

    def path(self, stream):
        p = (self.root / (stream + '.jsonl')).resolve()
        if not p.is_relative_to(self.root.resolve()):
            raise ValueError('非法数据路径')
        return p

    def append(self, stream, **fields):
        with self.lock:
            row = dict(fields, id=uuid.uuid4().hex, ts=now())
            p = self.path(stream)
            p.parent.mkdir(parents=True, exist_ok=True)
            with p.open('a', encoding='utf-8', newline='\n') as f:
                f.write(json.dumps(row, ensure_ascii=False) + '\n')
                f.flush()
                os.fsync(f.fileno())
            return row

    def read(self, stream):
        p = self.path(stream)
        if not p.exists():
            return []
        rows = []
        with self.lock:
            for n, line in enumerate(p.read_text(encoding='utf-8-sig').splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError as e:
                    raise ValueError(f'{p.name}:{n} JSONL 损坏，请停机修复或恢复备份') from e
        return rows

    def latest(self, stream, default=None):
        rows = self.read(stream)
        return rows[-1] if rows else default

    def tail(self, stream, limit):
        """只读取末尾有限条 JSONL，群窗口轮询不扫描全部历史。"""
        p = self.path(stream)
        if not p.exists():
            return []
        with self.lock, p.open('rb') as f:
            f.seek(0, os.SEEK_END)
            position, raw = f.tell(), b''
            while position > 0 and raw.count(b'\n') <= limit:
                size = min(position, 65536)
                position -= size
                f.seek(position)
                raw = f.read(size) + raw
            lines = raw.splitlines()
            if position > 0:
                lines = lines[1:]
            try:
                return [json.loads(line.decode('utf-8-sig')) for line in lines if line.strip()][-limit:]
            except (ValueError, UnicodeError) as e:
                raise ValueError(f'{p.name} JSONL 损坏，请停机修复或恢复备份') from e
