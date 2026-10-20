from datetime import datetime, timezone

class Impression:
    def __init__(self, cfg, store, plugin=None):
        self.cfg, self.store, self.plugin = cfg, store, plugin

    def get(self, person):
        rows = [r for r in self.store.read('impressions') if r['person'] == person]
        return rows[-1] if rows else {'person': person, 'affinity': 10, 'text': '当前主人，是最亲近的人。'}

    def update(self, person, messages):
        if not self.cfg['enabled']:
            return self.get(person)
        current = self.get(person)
        if 'ts' in current and (datetime.now(timezone.utc)-datetime.fromisoformat(current['ts'])).total_seconds() < self.cfg['refresh_hours']*3600:
            return current
        score = self.plugin(messages, current) if self.plugin else {'affinity': current['affinity'], 'text': '最近聊到：' + (messages[-1]['content'][:60] if messages else '暂无新对话')}
        return self.store.append('impressions', person=person, affinity=max(1,min(10,float(score['affinity']))), text=str(score['text'])[:100])
