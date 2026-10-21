import asyncio
import json
import aiohttp

class QQBridge:
    """自写 QQ 本机网关：HTTP 动作和有界 NDJSON 事件流。"""
    ACTIONS = {'get_login_info','send_private_msg','send_group_msg','configure_groups','get_status'}
    def __init__(self, cfg, owner, session, store, log, receive, safety, group_monitor=None, group_receive=None):
        self.cfg, self.owner, self.session, self.store, self.log = cfg, str(owner), session, store, log
        self.receive, self.safety = receive, safety
        self.group_monitor = group_monitor
        self.group_receive = group_receive
        self.group_policy_synced = False
        self._group_sync_lock = asyncio.Lock()
        self.connected = False
        self.online = False
        self.bot_id = None
        self.last_event = None
        self.stop = asyncio.Event()

    def headers(self):
        return {'X-QQ-ChatBot':'1'}

    @property
    def base_url(self):
        return 'http://127.0.0.1:'+str(self.cfg['native_port'])

    async def action(self, name, params):
        if name not in self.ACTIONS:
            raise PermissionError('自写 QQ 桥接尚不支持此动作')
        async with self.session.post(self.base_url+'/'+name, json=params, headers=self.headers(), allow_redirects=False, timeout=aiohttp.ClientTimeout(total=10)) as r:
            raw = await r.content.read(65537)
            if len(raw)>65536:raise ValueError('QQ 网关响应过大')
            if r.status != 200:
                self.log('ERROR','qq_http_error', status=r.status)
                raise RuntimeError(f'QQ 网关 HTTP {r.status}')
            data = json.loads(raw)
            if data.get('status') != 'ok' or data.get('retcode', 0) != 0:
                self.log('ERROR','qq_action_error', action=name, raw='native action rejected')
                raise RuntimeError(f'QQ 网关 {name} failed')
            return data.get('data')

    async def send(self, text, generation, proactive=False):
        if not self.safety.allowed(proactive=proactive, generation=generation):
            return False
        if not await self.safety.acquire('private:'+self.owner,generation,proactive=proactive):
            return False
        await self.action('send_private_msg', {'user_id':int(self.owner), 'message':[{'type':'text','data':{'text':text}}]})
        return True

    async def sync_groups(self):
        async with self._group_sync_lock:
            return await self._sync_groups()

    async def _sync_groups(self):
        self.group_policy_synced = False
        if not self.connected or not self.online or not self.group_monitor:return False
        groups = [dict(group_id=g['group_id'], reply_enabled=g.get('reply_enabled', False))
                  for g in self.group_monitor.cfg['groups'] if g['enabled']]
        try:
            result = await self.action('configure_groups', {'groups': groups, 'group_per_minute': self.safety.cfg['group_per_minute']})
            current = [dict(group_id=g['group_id'], reply_enabled=g.get('reply_enabled', False))
                       for g in self.group_monitor.cfg['groups'] if g['enabled']]
            self.group_policy_synced = isinstance(result, dict) and result.get('configured') is True and current == groups
        except Exception as error:
            self.log('WARN', 'qq_group_policy_pending', raw=str(error))
        return self.group_policy_synced

    async def send_group(self, ident, text, generation):
        def enabled():
            return (self.connected and self.online and self.group_policy_synced and self.group_monitor
                    and any(g['group_id'] == ident and g['enabled'] and g.get('reply_enabled', False) for g in self.group_monitor.cfg['groups'])
                    and self.safety.allowed(group=True, generation=generation))
        if not enabled():return False
        if not await self.safety.acquire('group:'+ident, generation, group=True):return False
        if not enabled():return False
        await self.action('send_group_msg', {'group_id': ident, 'message': [{'type': 'text', 'data': {'text': text}}]})
        return True

    async def ingest(self, event, historical=False):
        self.last_event = event.get('time',self.last_event)
        if event.get('meta_event_type')=='heartbeat':
            self.online=event.get('status',{}).get('online') is True
            return
        # 群事件走独立监听/群对话，绝不进入主人 receive/记忆或工具。
        if event.get('post_type') == 'message' and event.get('message_type') == 'group':
            if self.group_monitor:
                fresh = self.group_monitor.ingest(event)
                if fresh and self.group_receive and self.group_policy_synced:
                    await self.group_receive(event, self.bot_id, historical=historical)
            return
        # request / 非主人事件均不进入核心，绝不自动同意请求。
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
        self.log('WARN','qq_catchup_unsupported', raw='原生桥接尚未实现历史补拉；仅接收在线事件')

    async def run(self):
        delay = self.cfg['reconnect_min_seconds']
        while not self.stop.is_set():
            try:
                async with self.session.get(self.base_url+'/events', headers=self.headers(), allow_redirects=False,
                        timeout=aiohttp.ClientTimeout(total=None,sock_connect=5,sock_read=45),read_bufsize=262144) as stream:
                    if stream.status!=200 or stream.content_type!='application/x-ndjson':raise RuntimeError('QQ 事件流无效')
                    self.connected = True
                    self.online = False
                    self.log('INFO','qq_gateway_connected')
                    # The stream exists before QR login. Keep it open while waiting;
                    # querying login_info here used to fail and back off for a minute.
                    delay = self.cfg['reconnect_min_seconds']
                    async for line in stream.content:
                        if len(line)>262144:raise ValueError('QQ 事件过大')
                        if line.strip():
                            event=json.loads(line)
                            if not isinstance(event,dict):raise ValueError('QQ 事件格式无效')
                            if event.get('meta_event_type')=='heartbeat':
                                if self.online and event.get('status',{}).get('online') is not True:
                                    self.log('WARN','qq_offline')
                                    self.bot_id=None
                                if event.get('status',{}).get('online') is True and not self.online:
                                    info=await self.action('get_login_info',{})
                                    bot_id=str(info['user_id'])
                                    if bot_id==self.owner:raise ValueError('主人 QQ 号不能与机器人登录账号相同')
                                    if self.cfg.get('bot_id') and bot_id!=str(self.cfg['bot_id']):raise ValueError('当前 QQ 账号与配置的 bot_id 不符，拒绝接入')
                                    self.bot_id=bot_id
                                    self.log('INFO','qq_connected')
                                    self.online=True
                                    await self.sync_groups()
                                    await self.catchup()
                                await self.ingest(event)
                            elif self.online:
                                # Never route messages until this stream's account is verified.
                                await self.ingest(event)
            except asyncio.CancelledError:
                raise
            except aiohttp.ClientConnectorError as e:
                # A manually started local host should be discovered on the next
                # normal retry, even if the chat core has been running for hours.
                delay = self.cfg['reconnect_min_seconds']
                self.log('ERROR','qq_connection_error', raw=str(e))
            except Exception as e:
                self.log('ERROR','qq_connection_error', raw=str(e))
            finally:
                self.connected = False
                self.online = False
                self.bot_id = None
                self.group_policy_synced = False
                self.log('WARN','qq_disconnected')
            try:
                await asyncio.wait_for(self.stop.wait(), timeout=delay)
            except asyncio.TimeoutError:
                pass
            delay = min(self.cfg['reconnect_max_seconds'], delay*2)
