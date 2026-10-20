"""白名单群的被动监听；不持有模型、私人记忆或发送消息的依赖。"""
import re
from collections import deque


def group_id(value):
    if not isinstance(value, str) or not re.fullmatch(r'[1-9][0-9]{4,11}', value):
        raise ValueError('群号必须是 5–12 位数字')
    return value


def validate_monitor(cfg):
    for key, maximum in (('max_groups', 12), ('history_limit', 500), ('max_text_chars', 4000)):
        if type(cfg[key]) is not int or not 1 <= cfg[key] <= maximum:
            raise ValueError('群监听限制无效: ' + key)
    if not isinstance(cfg['groups'], list) or len(cfg['groups']) > cfg['max_groups']:
        raise ValueError('监听群数量超出限制')
    seen = set()
    for row in cfg['groups']:
        if not isinstance(row, dict) or set(row) != {'group_id', 'name', 'enabled'}:
            raise ValueError('群监听配置字段无效')
        ident = group_id(row['group_id'])
        if ident in seen:
            raise ValueError('不能重复添加同一个群')
        seen.add(ident)
        if type(row['enabled']) is not bool:
            raise ValueError('群监听开关必须为布尔值')
        if not isinstance(row['name'], str) or len(row['name']) > 60 or any(ord(c) < 32 for c in row['name']):
            raise ValueError('群备注限 60 字单行文本')


class GroupMonitor:
    def __init__(self, cfg, store, log):
        self.cfg, self.store, self.log = cfg, store, log
        self.seen = {}

    def stream(self, ident):
        return 'groups/' + group_id(ident) + '/monitor'

    def rows(self, ident):
        if not any(g['group_id'] == group_id(ident) for g in self.cfg['groups']):
            raise PermissionError('该群未添加监听')
        return self.store.tail(self.stream(ident), self.cfg['history_limit'])

    def snapshot(self):
        groups = []
        for group in self.cfg['groups']:
            last = self.store.tail(self.stream(group['group_id']), 1)
            groups.append(dict(group, last_message_id=last[-1]['message_id'] if last else None,
                               last_received=last[-1]['ts'] if last else None))
        return {'groups': groups, 'max_groups': self.cfg['max_groups'],
                'history_limit': self.cfg['history_limit'], 'read_only': True}

    def ingest(self, event):
        ident = str(event.get('group_id', ''))
        if not any(g['group_id'] == ident and g['enabled'] for g in self.cfg['groups']):
            return False
        message_id = event.get('message_id')
        if not isinstance(message_id, (str, int)) or isinstance(message_id, bool) or not str(message_id) or len(str(message_id)) > 128:
            return False
        if ident not in self.seen:
            self.seen[ident] = deque((r['message_id'] for r in self.store.tail(self.stream(ident), self.cfg['history_limit'])), maxlen=self.cfg['history_limit'] * 2)
        if str(message_id) in self.seen[ident]:
            return False
        sender = event.get('sender') if isinstance(event.get('sender'), dict) else {}
        user = str(sender.get('user_id', event.get('user_id', '')))[:20]
        name = str(sender.get('card') or sender.get('nickname') or user or '群成员')[:80]
        segments = event.get('message', [])
        if isinstance(segments, str):
            text = segments
        else:
            parts = []
            for segment in segments[:500] if isinstance(segments, list) else []:
                if not isinstance(segment, dict):
                    continue
                kind, data = segment.get('type'), segment.get('data', {})
                if not isinstance(data, dict):
                    continue
                if kind == 'text':
                    parts.append(str(data.get('text', ''))[:self.cfg['max_text_chars']])
                elif kind == 'at':
                    parts.append('@全体成员' if str(data.get('qq')) == 'all' else '@' + str(data.get('qq', ''))[:20])
                else:
                    parts.append({'image': '[图片]', 'face': '[表情]', 'mface': '[表情包]', 'record': '[语音]',
                                  'video': '[视频]', 'file': '[文件]', 'reply': '[引用消息]', 'json': '[卡片]', 'forward': '[合并转发]'}.get(kind, '[消息片段]'))
            text = ''.join(parts)
        limit = self.cfg['max_text_chars']
        text = text if len(text) <= limit else (text[:max(0, limit - 5)] + '[已截断]')[:limit]
        stamp = event.get('time')
        self.store.append(self.stream(ident), group_id=ident, message_id=str(message_id), user_id=user,
                          sender_name=name, text=text, event_time=stamp if type(stamp) is int else None)
        self.seen[ident].append(str(message_id))
        self.log('INFO', 'group_message_observed', group_id=ident, message_id=str(message_id), chars=len(text))
        return True
