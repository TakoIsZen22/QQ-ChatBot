import asyncio
import random
from datetime import datetime, timezone

class Awakening:
    def __init__(self, cfg, harness):
        self.cfg, self.h = cfg, harness
        self.next_check = 0

    def quiet(self):
        hour = self.h.localtime().hour
        start,end = self.cfg['quiet_start'],self.cfg['quiet_end']
        return start <= hour < end if start < end else hour >= start or hour < end

    def promise(self, text, due):
        dt = datetime.fromisoformat(due)
        if dt.tzinfo is None or dt <= datetime.now(timezone.utc) or not text.strip() or len(text)>500:
            raise ValueError('约定需要未来的带时区时间和短句')
        return self.h.store.append('promises', text=text, due=dt.isoformat(), kind='pending')

    async def tick(self):
        h = self.h
        # 无人值守首次安装绝不消耗模型；全暂停时不整合、不学习。
        if h.safety.mode == 'paused':
            return
        day = h.localtime().date().isoformat()
        if h.localtime().hour == self.cfg['sleep_hour'] and h.cfg['model']['main']:
            done = {r['day'] for r in h.store.read('sleep_runs')}
            if day not in done and h.queue.empty() and not h.busy:
                await h.sleep_integrate(day)
        t = datetime.now(timezone.utc).timestamp()
        if h.cfg['learning']['enabled'] and h.cfg['model']['main'] and not h.busy and h.queue.empty() and (t-h.last_received)/60>=self.cfg['idle_minutes']:
            async with h.turn_lock:
                h.busy=True
                try:await h.learning.idle(h)
                finally:h.busy=False
        if not self.cfg['enabled'] or self.quiet() or not h.safety.allowed(proactive=True) or h.busy or not h.queue.empty():
            return
        t = datetime.now(timezone.utc).timestamp()
        idle = (t-h.last_received)/60
        if idle < self.cfg['idle_minutes']:
            return
        done = {r['promise_id'] for r in h.store.read('promise_results')}
        due = next((r for r in h.store.read('promises') if r['id'] not in done and datetime.fromisoformat(r['due']).timestamp()<=t), None)
        if due:
            sent = await h.proactive('你之前记录的约定到时间了：'+due['text']+'。诚实提醒，做不到要直说。')
            if sent:
                h.store.append('promise_results', promise_id=due['id'], status='reminded')
            return
        if t < self.next_check:
            return
        self.next_check = t+random.uniform(self.cfg['min_minutes'],self.cfg['max_minutes'])*60
        if random.random() < self.cfg['probability']:
            await h.proactive('主人安静了一段时间；自然地问候或延续已有话题。不要编造看过的新资料，不用内疚施压。')

    async def run(self):
        self.next_check = datetime.now(timezone.utc).timestamp()+random.uniform(self.cfg['min_minutes'],self.cfg['max_minutes'])*60
        while True:
            tick_task=asyncio.create_task(self.tick())
            self.h.active_operations.add(tick_task)
            try:
                await tick_task
            except asyncio.CancelledError:
                if asyncio.current_task().cancelling():raise
            except Exception as e:
                self.h.log('ERROR','scheduler_error',raw=str(e))
            finally:
                self.h.active_operations.discard(tick_task)
            await asyncio.sleep(10)
