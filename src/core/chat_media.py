"""聊天图片入口：本机附件、OneBot本机缓存与精确允许的QQ图片CDN。"""
import asyncio
import base64
import ipaddress
import re
import socket
import uuid
from pathlib import Path
from urllib.parse import urlsplit, unquote
import aiohttp


class ChatMedia:
    def __init__(self, cfg, store, root, intents):
        self.cfg, self.store, self.root, self.intents = cfg, store, root, intents

    async def stage(self, data_url, name='聊天图片'):
        raw = self.intents.decode_upload(data_url)
        suffix, _, thumb, frames = await asyncio.to_thread(self.intents.prepare_image,raw)
        folder=self.store.root/'media';folder.mkdir(parents=True,exist_ok=True)
        path=folder/(uuid.uuid4().hex+'-chat'+suffix);path.write_bytes(raw)
        row=self.store.append('chat_uploads',path=str(path),name=str(name)[:80],frames=frames,
            thumbnail='data:image/jpeg;base64,'+base64.b64encode(thumb).decode())
        return {'type':'chat_image','media_id':row['id'],'thumbnail':row['thumbnail']}

    def upload(self,media_id):
        row=next((r for r in self.store.read('chat_uploads') if r['id']==media_id),None)
        if not row:raise ValueError('聊天图片不存在，请重新选择图片')
        return row

    def local_bytes(self,raw_path):
        path=Path(unquote(urlsplit(raw_path).path.lstrip('/'))) if raw_path.startswith('file:///') else Path(raw_path)
        if not path.is_absolute() or not path.is_file():raise ValueError('NapCat未返回本机图片文件')
        if path.stat().st_size>self.intents.cfg['max_image_bytes']:raise ValueError('聊天图片过大')
        return path.read_bytes()

    async def qq_bytes(self,item,qq):
        data=item.get('data',{});url=data.get('url','')
        if data.get('file'):
            try:
                result=await qq.action('get_image',{'file':data['file']}) or {}
                raw_path=result.get('file','')
                if raw_path:return self.local_bytes(raw_path)
                url=result.get('url') or url
            except (ValueError,OSError,RuntimeError,aiohttp.ClientError,asyncio.TimeoutError):
                if not url:raise
        if not url:
            emoji=str(data.get('emoji_id',''))
            if re.fullmatch(r'[a-fA-F0-9]{32}',emoji):
                url=f'https://gxh.vip.qq.com/club/item/parcel/item/{emoji[:2]}/{emoji}/raw300.gif'
        if not url:raise ValueError('QQ未提供可读取的表情图片')
        return await self.fetch_qq_image(url)

    async def fetch_qq_image(self,url):
        u=urlsplit(url)
        if (u.scheme!='https' or u.port not in (None,443) or u.username or u.password
                or u.fragment or u.hostname not in self.cfg['media_hosts']):
            raise PermissionError('图片链接不在QQ图片CDN允许清单')
        records=await asyncio.get_running_loop().getaddrinfo(u.hostname,443,type=socket.SOCK_STREAM)
        if not records or any(not ipaddress.ip_address(r[4][0]).is_global for r in records):
            raise PermissionError('QQ图片域名解析到了内网或保留地址')
        class Resolver(aiohttp.abc.AbstractResolver):
            async def resolve(self,host,port=0,family=socket.AF_INET):
                return [{'hostname':host,'host':r[4][0],'port':port,'family':r[0],'proto':r[2],'flags':socket.AI_NUMERICHOST} for r in records]
            async def close(self):pass
        connector=aiohttp.TCPConnector(resolver=Resolver(),use_dns_cache=False)
        async with aiohttp.ClientSession(connector=connector,trust_env=False) as session:
            async with session.get(url,allow_redirects=False,timeout=aiohttp.ClientTimeout(total=self.cfg['media_timeout_seconds'])) as response:
                if response.status!=200:raise ValueError(f'QQ图片HTTP {response.status}，不跟随跳转')
                if response.content_length and response.content_length>self.intents.cfg['max_image_bytes']:raise ValueError('QQ图片过大')
                chunks=[];size=0
                async for chunk in response.content.iter_chunked(16384):
                    size+=len(chunk)
                    if size>self.intents.cfg['max_image_bytes']:raise ValueError('QQ图片过大')
                    chunks.append(chunk)
                return b''.join(chunks)

    def face_context(self,data):
        # QQ内置表情没有像素时，仅使用安装包自带的编号名称，不伪称视觉识别。
        face_id=str(data.get('id',''))
        folder=self.root/'.runtime/napcat/static/assets'
        for path in folder.glob('qface-*.js'):
            text=path.read_text(encoding='utf-8')
            names=dict(re.findall(r'"QSid":"(\d+)","QDes":"([^"\\]+)"',text))
            if face_id in names:
                return f'[QQ内置表情：{names[face_id].lstrip("/")}；来自本机QQ表情名称表，非视觉观察。结合语境理解，不认定真实情绪。]'
        return '[QQ内置表情：没有可验证的图片或名称，请说明无法辨认，不猜内容。]'

    def remember(self,row,index,observed,context):
        if row.get('message_id'):
            self.store.append('chat_media_results',message_id=row['message_id'],index=index,
                media_id=observed['id'],thumbnail=observed.get('thumbnail',''),context=context)

    def results(self):
        grouped={}
        for row in self.store.read('chat_media_results'):
            grouped.setdefault(row['message_id'],{})[row['index']]=row
        return grouped

    def history_context(self,message_id,grouped=None):
        rows=(grouped if grouped is not None else self.results()).get(message_id,{})
        return '\n'.join(r['context'] for _,r in sorted(rows.items()))

    def chat_rows(self,limit=100):
        grouped=self.results();rows=[]
        for row in self.store.read('chat')[-limit:]:
            item=dict(row);results=grouped.get(row.get('message_id'),{})
            if results:
                item['media']=[{'type':'sticker','media_id':r['media_id'],'thumbnail':r['thumbnail']} for _,r in sorted(results.items())]
            rows.append(item)
        return rows
