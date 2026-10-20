"""私人 soul.md：原子写入、乐观并发保护、可审计版本；不向模型暴露写接口。"""
import hashlib
import os
import re
import uuid
from pathlib import Path


class Soul:
    STREAM = 'persona/soul_history'

    def __init__(self, cfg, store, root):
        self.cfg, self.store, self.root = cfg, store, Path(root).resolve()

    @property
    def path(self):
        base = self.store.root.resolve()
        path = (base/self.cfg['soul_file']).resolve()
        if path.name != 'soul.md' or not path.is_relative_to(base) or not base.is_relative_to(self.root):
            raise ValueError('soul.md 必须位于本安装的私有 data 子目录')
        return path

    def _validate(self, text):
        if not isinstance(text,str) or '\x00' in text:
            raise ValueError('人设必须为 UTF-8 文本，不能包含空字符')
        if len(text)>self.cfg['soul_max_chars'] or len(text.encode('utf-8'))>self.cfg['soul_max_bytes']:
            raise ValueError('人设超出配置的长度或大小限制')
        if re.search(r'(?i)(sk-[a-z0-9]{12,}|bearer\s+\S+|(?:password|api[_ -]?key|token|密码|密钥)\s*[:=：]\s*\S+)',text):
            raise ValueError('人设中含疑似凭据，请移除秘密后保存')
        return text

    def current(self):
        path = self.path
        if path.exists() and path.stat().st_size>self.cfg['soul_max_bytes']:
            raise ValueError('磁盘 soul.md 过大，请缩短后重新读取')
        raw = path.read_bytes() if path.exists() else b''
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise ValueError('请将 soul.md 保存为 UTF-8') from None
        self._validate(text)
        return {'text':text,'revision':hashlib.sha256(raw).hexdigest(),
                'exists':path.exists(),'active':bool(text.strip())}

    def snapshot(self):
        current = self.current()
        rows = self.store.read(self.STREAM)[-self.cfg['soul_history_limit']:]
        template = self.root/'src/persona/soul.example.md'
        return dict(current,path=self.path.relative_to(self.root).as_posix(),
                    limits={'max_chars':self.cfg['soul_max_chars'],'max_bytes':self.cfg['soul_max_bytes']},
                    template=template.read_text(encoding='utf-8') if template.is_file() else '# 专属人设\n',
                    history=[{k:r[k] for k in ('id','ts','revision','chars','source')} for r in reversed(rows)])

    def _remember(self,text,revision,source):
        if any(r['revision']==revision for r in self.store.read(self.STREAM)):
            return
        self.store.append(self.STREAM,text=text,revision=revision,chars=len(text),source=source)

    def save(self,text,expected_revision,source='owner_manual'):
        text = self._validate(text)
        if not isinstance(expected_revision,str):
            raise ValueError('保存前必须读取当前版本')
        with self.store.lock:
            previous = self.current()
            if previous['revision']!=expected_revision:
                raise ValueError('磁盘人设已被其他窗口或编辑器修改；草稿已保留，请重新读取后合并')
            # 版本记录是可恢复内容，不表示该版本一定已成为当前文件。
            self._remember(previous['text'],previous['revision'],'previous_file')
            raw = text.encode('utf-8')
            revision = hashlib.sha256(raw).hexdigest()
            self._remember(text,revision,source)
            path = self.path
            path.parent.mkdir(parents=True,exist_ok=True)
            temp = path.with_name('soul-'+uuid.uuid4().hex+'.tmp')
            try:
                with temp.open('xb') as file:
                    file.write(raw);file.flush();os.fsync(file.fileno())
                temp.replace(path)
            finally:
                if temp.exists():temp.unlink()
            return self.snapshot()

    def restore(self,version_id,expected_revision):
        with self.store.lock:
            row = next((r for r in self.store.read(self.STREAM) if r['id']==version_id),None)
            if not row:
                raise ValueError('找不到该人设版本')
            return self.save(row['text'],expected_revision,source='owner_restore')
