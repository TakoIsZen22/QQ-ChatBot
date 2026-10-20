import math
import re
from datetime import datetime, timezone

CATEGORIES = ('knowledge', 'relationship', 'work', 'weights', 'multimodal', 'reflection')

class Memory:
    def __init__(self, cfg, store):
        self.cfg, self.store = cfg, store

    def stream(self, person):
        if not re.fullmatch(r'[a-zA-Z0-9_-]+', person):
            raise ValueError('非法 person 标识')
        return f'people/{person}/memory'

    def append(self, person, content, category='relationship', importance='normal', source='user'):
        if category not in CATEGORIES or importance not in ('permanent', 'important', 'normal'):
            raise ValueError('记忆分类或重要性无效')
        content = str(content).strip()
        if not content or len(content) > self.cfg['max_content_chars']:
            raise ValueError('记忆长度无效')
        if re.search(r'(?i)(sk-[a-z0-9]{12,}|bearer\s+\S+|(?:password|api[_ -]?key|token|密码|密钥)\s*[:=：]\s*\S+)', content):
            raise ValueError('记忆包含疑似凭据，请删除秘密后重试')
        return self.store.append(self.stream(person), kind='memory', content=content, category=category, importance=importance, source=source)

    def remove(self, person, memory_id):
        rows = self.store.read(self.stream(person))
        if not any(r['id'] == memory_id and r.get('kind') == 'memory' for r in rows):
            raise ValueError('找不到该记忆')
        return self.store.append(self.stream(person), kind='removed', memory_id=memory_id)

    def query(self, person, query='', limit=None):
        rows = self.store.read(self.stream(person))
        removed = {r['memory_id'] for r in rows if r.get('kind') == 'removed'}
        terms = set(re.findall(r'[a-z0-9]+|[\u4e00-\u9fff]', query.lower()))
        result = []
        for r in rows:
            if r.get('kind') != 'memory' or r['id'] in removed:
                continue
            age = max(0, (datetime.now(timezone.utc)-datetime.fromisoformat(r['ts'])).total_seconds()/86400)
            imp = r['importance']
            half = self.cfg['important_half_life_days'] if imp == 'important' else self.cfg['short_half_life_days']
            weight = 1 if imp == 'permanent' else math.pow(0.5, age/half)
            hits = sum(t in r['content'].lower() for t in terms)
            if terms and not hits:
                continue
            result.append(dict(r, score=weight * (1+hits)))
        return sorted(result, key=lambda r: (r['score'], r['ts']), reverse=True)[:limit or self.cfg['retrieval_limit']]
