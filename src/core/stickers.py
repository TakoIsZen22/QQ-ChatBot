from datetime import datetime

class Stickers:
    def __init__(self,cfg,store,safety,localtime):
        self.cfg,self.store,self.safety,self.localtime=cfg,store,safety,localtime

    def list(self):
        notes={r['sticker_id']:r for r in self.store.read('sticker_notes')}
        uses=self.store.read('sticker_uses')
        return [dict(r,localNote=notes.get(r['id'],{}).get('note',r['description']),tags=notes.get(r['id'],{}).get('tags',[]),usage_count=sum(u['sticker_id']==r['id'] for u in uses)) for r in self.store.read('stickers')]

    def collect(self,media_id,note):
        if not self.cfg['enabled']:raise PermissionError('表情包能力未启用')
        media=next((r for r in self.store.read('media') if r['id']==media_id and r.get('description')),None)
        if not media:raise ValueError('收藏前必须先通过视觉模型观察图片，不能猜含义')
        if any(r['path']==media['path'] for r in self.store.read('stickers')):raise ValueError('这张已经收藏了')
        return self.store.append('stickers',path=media['path'],desc=media.get('desc',''),description=str(note)[:200],observation=media['description'])

    def note(self,sticker_id,note,tags=None):
        if not any(r['id']==sticker_id for r in self.store.read('stickers')):raise ValueError('表情不存在')
        return self.store.append('sticker_notes',sticker_id=sticker_id,note=str(note)[:200],tags=[str(t)[:30] for t in (tags or [])][:10])

    def reserve(self,sticker_id):
        if not self.cfg['enabled']:raise PermissionError('表情包能力未启用')
        day=self.localtime().date().isoformat()
        if sum(r['day']==day for r in self.store.read('sticker_uses'))>=self.cfg['daily_limit']:raise PermissionError('今天表情轮数已到上限')
        row=next((r for r in self.store.read('stickers') if r['id']==sticker_id),None)
        if not row:raise ValueError('表情不存在')
        self.store.append('sticker_uses',sticker_id=sticker_id,day=day,status='reserved')
        return row
