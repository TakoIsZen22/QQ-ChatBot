import re
from datetime import datetime
from zoneinfo import ZoneInfo

class Diary:
    def __init__(self, cfg, store, timezone):
        self.cfg, self.store, self.zone = cfg, store, ZoneInfo(timezone)

    def append(self, text):
        text = str(text).strip()
        if not text or len(text) > self.cfg['max_chars'] or len([s for s in re.split('[。！？!?]+', text) if s.strip()]) > 2:
            raise ValueError('日记限一两句短句')
        if any(s in text for s in ('充实的一天', '总而言之', '总结一下', '今天收获满满')):
            raise ValueError('请写具体事件，不写总结')
        day = datetime.now(self.zone).date().isoformat()
        with self.store.lock:
            if sum(r['day'] == day for r in self.store.read('diary')) >= self.cfg['daily_limit']:
                raise ValueError('今天日记已经三条或达到配置上限')
            return self.store.append('diary', day=day, text=text)

    def recent(self, count=5):
        return self.store.read('diary')[-max(1,min(30,int(count))):]
