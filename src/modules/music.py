import asyncio
import json

class Music:
    def __init__(self, cfg, root, safety, store):
        self.cfg, self.root, self.safety, self.store = cfg, root, safety, store
        self.lock = asyncio.Lock()

    async def invoke(self, action='status'):
        if not self.cfg['enabled']:
            raise PermissionError('网易云读取未启用')
        if action not in ('status','next','previous','play','pause'):
            raise ValueError('音乐动作无效')
        if action != 'status' and (not self.cfg['allow_control'] or not self.safety.allowed()):
            raise PermissionError('一起听控制需单独在配置启用 music.allow_control，且不能处于暂停')
        async with self.lock:
            proc = await asyncio.create_subprocess_exec('powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(self.root/'tools/music.ps1'),'-Action',action, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
            try:
                out, err = await asyncio.wait_for(proc.communicate(),20)
            except BaseException:
                proc.kill(); await proc.wait(); raise
            if proc.returncode:
                raise RuntimeError(err.decode(errors='replace'))
            result = json.loads(out.decode('utf-8-sig'))
            self.store.append('music', action=action, result=result)
            return result

    async def lyrics(self, url, learning):
        # 来源必须在音乐和联网读取两份清单中，绝不猜歌词/热评。
        from urllib.parse import urlsplit
        if urlsplit(url).hostname not in self.cfg['allowed_sources']:
            raise PermissionError('歌词/热评来源未授权')
        return (await learning.fetch(url))[:self.cfg['max_lyrics_chars']]
