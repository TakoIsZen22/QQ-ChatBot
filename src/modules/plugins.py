import asyncio
import importlib.util
import json
from pathlib import Path
from ..version import VERSION

class MCPClient:
    """MCP stdio JSON-RPC：进程只在本机用户调用时启动；不暴露给模型。"""
    def __init__(self, cfg):
        self.cfg = cfg
        self.seq = 0
        self.proc = None

    async def request(self, method, params):
        self.seq += 1
        ident = self.seq
        msg = {'jsonrpc':'2.0','id':ident,'method':method,'params':params}
        self.proc.stdin.write((json.dumps(msg)+'\n').encode())
        await self.proc.stdin.drain()
        async def read():
            while True:
                raw = await self.proc.stdout.readline()
                if not raw:
                    raise RuntimeError('MCP 进程已退出')
                result = json.loads(raw)
                if result.get('id') == ident:
                    if 'error' in result:
                        raise RuntimeError(str(result['error']))
                    return result.get('result')
        return await asyncio.wait_for(read(), self.cfg.get('timeout_seconds',20))

    async def call(self, tool, arguments):
        if tool not in self.cfg.get('allowed_tools',[]):
            raise PermissionError('MCP 工具未在精确清单中')
        command = self.cfg['command']
        if not isinstance(command,list) or not command:
            raise ValueError('MCP command 必须是 argv 数组')
        self.proc = await asyncio.create_subprocess_exec(*command, stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL, limit=1048576)
        try:
            await self.request('initialize', {'protocolVersion':'2024-11-05','capabilities':{},'clientInfo':{'name':'da-fei-yu','version':VERSION}})
            self.proc.stdin.write(b'{"jsonrpc":"2.0","method":"notifications/initialized"}\n')
            await self.proc.stdin.drain()
            return await self.request('tools/call', {'name':tool,'arguments':arguments})
        finally:
            if self.proc.returncode is None:
                self.proc.terminate()
                try:
                    await asyncio.wait_for(self.proc.wait(),3)
                except asyncio.TimeoutError:
                    self.proc.kill(); await self.proc.wait()

class Plugins:
    def __init__(self, cfg, root, store, safety):
        self.cfg, self.root, self.store, self.safety = cfg, root, store, safety

    def load(self, name):
        if not self.cfg['enabled'] or name not in self.cfg['allowed']:
            raise PermissionError('插件未启用或不在清单')
        p = (self.root/'user_plugins'/f'{name}.py').resolve()
        if not p.is_relative_to((self.root/'user_plugins').resolve()):
            raise ValueError('非法插件路径')
        spec = importlib.util.spec_from_file_location('dfy_plugin_'+name,p)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    async def mcp(self, name, tool, arguments):
        if not self.cfg['enabled'] or not self.safety.allowed():
            raise PermissionError('插件已关闭或已暂停')
        server = next((s for s in self.cfg['mcp'] if s['name']==name),None)
        if not server:
            raise PermissionError('MCP server 未配置')
        self.store.append('plugin_audit', server=name, tool=tool, state='requested_by_owner')
        result = await MCPClient(server).call(tool,arguments)
        self.store.append('plugin_audit', server=name, tool=tool, state='completed')
        return result

    def publish(self, text, approved=False):
        # 仅生成可审核的分享草稿；不自动上传社区或隐私对话。
        return self.store.append('share_drafts', text=str(text)[:1000], status='local_only')
