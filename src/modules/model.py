import asyncio
import json
import os
import aiohttp
from ..core.model_endpoint import endpoint,label

class Model:
    """统一 OpenAI 兼容出口：Magpie 或使用者选择的 API；工具仅建议。"""
    def __init__(self, cfg, session, log):
        self.cfg, self.session, self.log = cfg, session, log

    def headers(self):
        key=os.environ.get(self.cfg['key_env'],'')
        return {'Authorization':'Bearer '+key} if key else {}

    async def _json(self,response):
        raw=bytearray();limit=self.cfg['max_response_bytes']
        async for chunk in response.content.iter_chunked(65536):
            raw.extend(chunk)
            if len(raw)>limit:raise RuntimeError('模型 API 响应超过配置大小上限')
        text=raw.decode('utf-8',errors='replace')
        if response.status!=200:raise ApiError(response.status,text)
        try:return json.loads(text)
        except ValueError:raise RuntimeError('模型 API 未返回有效 JSON，请检查 Base URL 和兼容协议') from None

    def _error(self,status):
        hint={401:'请检查 API 密钥环境变量及权限',403:'请检查 API 权限或服务限制',404:'请检查 Base URL；模型清单不可用时可手动填写模型 ID',429:'请求受限，请检查额度或稍后重试'}.get(status,'请查看服务状态或运行日志')
        return f'{label(self.cfg)} HTTP {status}，{hint}'

    async def complete(self, messages, tools=None, auxiliary=False):
        base=endpoint(self.cfg)
        name = self.cfg['auxiliary'] if auxiliary else self.cfg['main']
        if not name:
            raise ValueError('尚未设置'+('视觉辅助模型' if auxiliary else '主模型')+'，请在设置中填写模型 ID')
        body = {'model':name,'messages':messages,'max_tokens':self.cfg['max_tokens'],'temperature':self.cfg['temperature']}
        if tools:
            body['tools'] = tools
        try:
            async with self.session.post(base+'/chat/completions', json=body, headers=self.headers(), allow_redirects=False, timeout=aiohttp.ClientTimeout(total=self.cfg['timeout_seconds'])) as r:
                result=await self._json(r)
            if not isinstance(result,dict) or not isinstance(result.get('choices'),list) or not result['choices'] or not isinstance(result['choices'][0],dict) or not isinstance(result['choices'][0].get('message'),dict):
                raise RuntimeError('模型 API 返回结构不兼容，需要 Chat Completions choices[].message')
            if 'usage' in result:self.log('INFO','model_usage',model=name,usage=result['usage'])
            return result['choices'][0]['message']
        except ApiError as error:
            self.log('ERROR','model_error',status=error.status,raw=error.raw)
            raise RuntimeError(self._error(error.status)) from None
        except (aiohttp.ClientError, asyncio.TimeoutError) as e:
            self.log('ERROR','model_connection_error', raw=str(e))
            raise RuntimeError(label(self.cfg)+' 无法连接或超时，请检查 API 地址、网络和服务状态') from None

    async def models(self):
        base=endpoint(self.cfg)
        try:
            async with self.session.get(base+'/models',headers=self.headers(),allow_redirects=False,timeout=aiohttp.ClientTimeout(total=self.cfg['models_timeout_seconds'])) as r:
                result=await self._json(r)
            if not isinstance(result,dict) or not isinstance(result.get('data'),list) or any(not isinstance(row,dict) or not isinstance(row.get('id'),str) for row in result['data']):
                raise RuntimeError('模型清单结构不兼容，可按服务商说明手动填写模型 ID')
            return result['data']
        except ApiError as error:raise RuntimeError(self._error(error.status)) from None
        except (aiohttp.ClientError,asyncio.TimeoutError):
            raise RuntimeError(label(self.cfg)+' 无法读取模型清单，请检查地址和网络；也可手动填写模型 ID') from None


class ApiError(Exception):
    def __init__(self,status,raw):self.status,self.raw=status,raw
