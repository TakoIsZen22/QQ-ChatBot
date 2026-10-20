import asyncio
import json
import os
import aiohttp

class QQBridge:
    """NapCat 正向 WebSocket 事件 + HTTP 动作。只允许私聊文字/表情/语音白名单。"""
    ACTIONS = {'get_login_info','get_friend_msg_history','send_private_msg','get_status','get_record','get_image'}
    def __init__(self, cfg, owner, session, store, log, receive, safety):
        self.cfg, self.owner, self.session, self.store, self.log = cfg, str(owner), session, store, log
        self.receive, self.safety = receive, safety
        self.connected = False
        self.online = False
        self.bot_id = None
        self.last_event = None
        self.stop = asyncio.Event()

    def headers(self):
        token = os.environ.get(self.cfg['token_env'], '')
        return {'Authorization': 'Bearer '+token} if token else {}

    async def action(self, name, params):
        if name not in self.ACTIONS:
            raise PermissionError('OneBot 动作不在白名单')
        async with self.session.post(self.cfg['http_url'].rstrip('/')+'/'+name, json=params, headers=self.headers(), allow_redirects=False, timeout=aiohttp.ClientTimeout(total=10)) as r:
            raw = await r.text()
            if r.status != 200:
                self.log('ERROR','onebot_http_error', status=r.status, raw=raw)
                raise RuntimeError(f'OneBot HTTP {r.status}')
            data = json.loads(raw)
            if data.get('status') != 'ok' or data.get('retcode', 0) != 0:
                self.log('ERROR','onebot_action_error', action=name, raw=raw)
                raise RuntimeError(f'OneBot {name} failed')
            return data.get('data')

    async def send(self, text, generation, proactive=False):
        if not self.safety.allowed(proactive=proactive, generation=generation):
            return False
        if not await self.safety.acquire('private:'+self.owner,generation,proactive=proactive):
            return False
        await self.action('send_private_msg', {'user_id':int(self.owner), 'message':[{'type':'text','data':{'text':text}}]})
        return True

    async def ingest(self, event, historical=False):
        self.last_event = event.get('time',self.last_event)
        if event.get('meta_event_type')=='heartbeat':
            self.online=event.get('status',{}).get('online',False)
            return
        # request / group / 非主人事件均不进入核心，绝不自动同意请求。
        if event.get('post_type') == 'request':
            self.log('WARN','qq_request_ignored', request_type=event.get('request_type'))
            return
        if event.get('post_type') == 'notice' and event.get('sub_type') == 'poke' and str(event.get('user_id')) == self.owner and not event.get('group_id') and str(event.get('target_id')) == self.bot_id:
            await self.receive({'message_id':'poke:'+str(event.get('time')), 'text':'[主人拍了拍你]', 'channel':'qq', 'historical':historical})
            return
        sender=event.get('sender',{}).get('user_id',event.get('user_id'))
        if event.get('post_type', 'message') != 'message' or event.get('message_type', 'private') != 'private' or str(sender) != self.owner:
            return
        segments = event.get('message', [])
        if isinstance(segments, str):
            # CQ 字符串不执行，只当字面文本。
            segments = [{'type':'text','data':{'text':segments}}]
        texts, media = [], []
        for s in segments:
            if s.get('type') == 'text':
                texts.append(str(s.get('data',{}).get('text','')))
            elif s.get('type') in ('image','record','face','mface'):
                media.append(s)
        await self.receive({'message_id':str(event['message_id']), 'text':''.join(texts), 'media':media, 'channel':'qq', 'historical':historical, 'event_time':event.get('time')})

    async def catchup(self):
        try:
            data = await self.action('get_friend_msg_history', {'user_id':int(self.owner),'count':self.cfg['history_limit']})
            messages = data.get('messages', []) if isinstance(data,dict) else []
            for event in sorted(messages, key=lambda e: e.get('time',0)):
                await self.ingest(event, historical=True)
            self.log('INFO','qq_catchup_complete', count=len(messages))
        except Exception as e:
            self.log('ERROR','qq_catchup_failed', raw=str(e))

    async def run(self):
        delay = self.cfg['reconnect_min_seconds']
        while not self.stop.is_set():
            try:
                async with self.session.ws_connect(self.cfg['ws_url'], headers=self.headers(), heartbeat=20, timeout=aiohttp.ClientWSTimeout(ws_close=5)) as ws:
                    self.connected = True
                    info=await self.action('get_login_info',{})
                    self.bot_id=str(info['user_id'])
                    if self.bot_id==self.owner:raise ValueError('主人 QQ 号不能与机器人登录账号相同')
                    if self.cfg.get('bot_id') and self.bot_id!=str(self.cfg['bot_id']):raise ValueError('NapCat 当前账号与配置的 bot_id 不符，拒绝接入')
                    status=await self.action('get_status',{})
                    self.online=bool(status.get('online'))
                    self.log('INFO','qq_connected')
                    # 先建立 WS 再补课；期间事件由 socket 缓冲，核心按 ID 去重。
                    await self.catchup()
                    delay = self.cfg['reconnect_min_seconds']
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            try:
                                await self.ingest(json.loads(msg.data))
                            except Exception as e:
                                self.log('ERROR','qq_event_error', raw=str(e))
                        elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSE):
                            break
            except asyncio.CancelledError:
                raise
            except Exception as e:
                self.log('ERROR','qq_connection_error', raw=str(e))
            finally:
                self.connected = False
                self.online = False
                self.log('WARN','qq_disconnected')
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
            delay = min(self.cfg['reconnect_max_seconds'], delay*2)
