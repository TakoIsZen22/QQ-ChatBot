import asyncio
import time
from collections import defaultdict
from datetime import datetime

class Safety:
    def __init__(self, cfg, store, log):
        self.cfg, self.store, self.log = cfg, store, log
        state = store.latest('safety', cfg)
        self.mode = state['mode']
        self.groups_muted = state['groups_muted']
        self.generation = 0
        self.changed = asyncio.Event()
        self.rates = defaultdict(list)
        for row in store.read('outbound'):
            if row.get('channel') == 'qq':
                self.rates[row['target']].append(datetime.fromisoformat(row['ts']).timestamp())

    def set(self, mode=None, groups_muted=None):
        if mode is not None:
            if mode not in ('paused', 'reply_only', 'active'):
                raise ValueError('无效模式')
            self.mode = mode
        if groups_muted is not None:
            self.groups_muted = bool(groups_muted)
        self.generation += 1
        self.changed.set()
        self.changed = asyncio.Event()
        self.store.append('safety', mode=self.mode, groups_muted=self.groups_muted)
        self.log('WARN', 'safety_changed', mode=self.mode, groups_muted=self.groups_muted)

    def allowed(self, group=False, proactive=False, generation=None):
        return (self.mode != 'paused' and not (group and self.groups_muted)
                and not (proactive and self.mode != 'active')
                and (generation is None or generation == self.generation))

    async def delay(self, seconds, generation):
        if not self.allowed(generation=generation):
            return False
        event = self.changed
        try:
            await asyncio.wait_for(event.wait(), timeout=seconds)
            return False
        except asyncio.TimeoutError:
            return self.allowed(generation=generation)

    def reserve(self, target, group=False):
        t = time.time()
        bucket = self.rates[target] = [x for x in self.rates[target] if t-x < 60]
        limit = self.cfg['group_per_minute' if group else 'private_per_minute']
        if len(bucket) >= limit:
            return False
        bucket.append(t)
        # 发送前落盘；超时也占配额，绝不自动重发不确定结果。
        self.store.append('outbound', target=target, channel='qq', status='reserved')
        return True

    async def acquire(self,target,generation,group=False,proactive=False):
        while self.allowed(group,proactive,generation):
            if self.reserve(target,group):return True
            bucket=self.rates[target]
            wait=max(.05,60-(time.time()-min(bucket))+.02)
            if not await self.delay(wait,generation):return False
        return False

    def reserve_irreversible(self, action):
        rows = self.store.read('irreversible')
        t = time.time()
        today = datetime.now().astimezone().date()
        if rows and t-datetime.fromisoformat(rows[-1]['ts']).timestamp() < self.cfg['irreversible_interval_seconds']:
            raise PermissionError('不可撤回动作间隔至少十分钟')
        if sum(datetime.fromisoformat(r['ts']).astimezone().date() == today for r in rows) >= self.cfg['irreversible_per_day']:
            raise PermissionError('不可撤回动作每日最多三条')
        return self.store.append('irreversible', action=action)
