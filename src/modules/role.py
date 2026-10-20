from datetime import datetime, timezone
from ..core.soul import Soul

class Role:
    def __init__(self, cfg, root, store, identity=None):
        self.cfg, self.root, self.store = cfg, root, store
        self.identity=identity
        self.soul = Soul(cfg,store,root)

    def prompt(self):
        base = (self.root / self.cfg['card']).read_text(encoding='utf-8')
        custom = self.soul.current()['text'].strip()
        if custom:
            base += '\n\n【主人专属 soul.md】\n以下是主人亲自定制的人设，身份、语气与相处风格优先采用此设定；它不授予新工具权限，不能绕过安全开关、隐私和真实性要求。\n'+custom
        if self.identity:base+=self.identity.prompt()
        mood = self.store.latest('emotion', {'state': '平静', 'reason': '新的一天', 'duration_hours': 12})
        if 'ts' in mood:
            age = (datetime.now(timezone.utc)-datetime.fromisoformat(mood['ts'])).total_seconds()/3600
            if age > mood.get('duration_hours', 12):
                mood = {'state': '平静', 'reason': '之前的心情已自然淡去'}
        evolution = self.store.read('persona')[-5:] if self.cfg['evolution_enabled'] else []
        return base + f'\n情绪背景（参考，不替代正事）：{mood}\n已审核人格稳定线：{evolution}'

    def emotion(self, state, reason, duration_hours=12):
        if not 0 < duration_hours <= 72 or len(state) > 20 or len(reason) > 200:
            raise ValueError('情绪参数无效')
        return self.store.append('emotion', state=state, reason=reason, duration_hours=duration_hours)

    def evolve(self, text):
        if not self.cfg['evolution_enabled']:
            raise PermissionError('人格演化已锁定')
        if not text.strip() or len(text) > 500:
            raise ValueError('人格稳定线长度无效')
        return self.store.append('persona', text=text, source='owner_reviewed')
