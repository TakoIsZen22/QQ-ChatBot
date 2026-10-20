import json
import os
import re
from .store import now

class Log:
    def __init__(self, store, secret_envs=()):
        self.store = store
        self.secret_envs = secret_envs

    def __call__(self, level, event, **fields):
        def clean(x):
            if isinstance(x, str):
                for env in self.secret_envs:
                    secret = os.environ.get(env, '')
                    if secret:
                        x = x.replace(secret, '[REDACTED]')
                return re.sub(r'(?i)(bearer\s+)\S+', r'\1[REDACTED]', x)
            if isinstance(x, dict):
                return {k: '[REDACTED]' if k.lower() in ('authorization', 'token', 'api_key') else clean(v) for k,v in x.items()}
            if isinstance(x, list):
                return [clean(v) for v in x]
            return x
        row = self.store.append('events', level=level, event=event, **clean(fields))
        print(json.dumps({k: row[k] for k in ('ts','level','event')}, ensure_ascii=False), flush=True)
