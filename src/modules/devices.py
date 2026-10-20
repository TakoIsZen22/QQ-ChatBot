import asyncio
import base64
import re
from pathlib import Path

DENIED = re.compile(r'(?i)(alipay|wallet|bank|pay|unionpay|tenpay|com\.tencent\.mm|com\.tencent\.mobileqq|finance|icbc|ccb|cmb|boc|abc|spdb|citic|pab|pingan)')

class Devices:
    """不向模型暴露；只允许本机用户明确调用。每一步重新检查设备与前台包。"""
    def __init__(self, cfg, store, safety):
        self.cfg, self.store, self.safety = cfg, store, safety
        self.lock = asyncio.Lock()

    async def adb(self, *args):
        proc = await asyncio.create_subprocess_exec(self.cfg['adb_path'], '-s', self.cfg['serial'], *map(str,args), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            out, err = await asyncio.wait_for(proc.communicate(), self.cfg['timeout_seconds'])
        except BaseException:
            proc.kill(); await proc.wait(); raise
        if proc.returncode:
            raise RuntimeError(err.decode('utf-8',errors='replace'))
        return out

    async def guard(self):
        if not self.cfg['enabled'] or self.cfg['device_kind'] not in ('emulator','spare') or not self.cfg['serial']:
            raise PermissionError('仅允许已声明 serial 的模拟器/备用机')
        if not self.safety.allowed():
            raise PermissionError('已暂停')
        packages = (await self.adb('shell','pm','list','packages')).decode(errors='replace')
        if any(DENIED.search(p) for p in packages.splitlines()):
            raise PermissionError('检测到支付/银行/高风险综合 App；请使用无此类 App 的专用设备')
        windows = (await self.adb('shell','dumpsys','window','windows')).decode(errors='replace')
        focus = next((s for s in windows.splitlines() if 'mCurrentFocus' in s), '')
        match = re.search(r'\s([a-zA-Z0-9_.]+)/', focus)
        if not match or match.group(1) not in self.cfg['allowed_packages'] or DENIED.search(match.group(1)):
            raise PermissionError('当前前台 App 未在精确允许清单，拒绝操作')

    async def execute(self, action, args):
        async with self.lock:
            await self.guard()
            if action == 'tap':
                x,y = self.coords(args,2)
                out = await self.adb('shell','input','tap',x,y)
            elif action == 'swipe':
                x,y,x2,y2 = self.coords(args,4)
                out = await self.adb('shell','input','swipe',x,y,x2,y2,300)
            elif action == 'text':
                text = str(args['text'])
                if len(text) > 1000:
                    raise ValueError('输入太长')
                methods = (await self.adb('shell','ime','list','-s')).decode(errors='replace')
                active = (await self.adb('shell','settings','get','secure','default_input_method')).decode(errors='replace')
                if 'com.android.adbkeyboard/.AdbIME' not in methods or 'com.android.adbkeyboard/.AdbIME' not in active:
                    raise RuntimeError('请先安装并手动选用 ADBKeyboard，中文输入未执行')
                payload = base64.b64encode(text.encode()).decode()
                out = await self.adb('shell','am','broadcast','-a','ADB_INPUT_B64','--es','msg',payload)
            elif action == 'screenshot':
                out = await self.adb('exec-out','screencap','-p')
                path = self.store.root / 'device-screen.png'
                path.write_bytes(out)
                return {'path':str(path), 'bytes':len(out)}
            else:
                raise PermissionError('设备动作不在白名单')
            self.store.append('device_actions', action=action, serial=self.cfg['serial'])
            return {'output':out.decode(errors='replace')}

    @staticmethod
    def coords(args, n):
        keys = ('x','y','x2','y2')[:n]
        values = [int(args[k]) for k in keys]
        if any(v < 0 or v > 20000 for v in values):
            raise ValueError('坐标范围无效')
        return values

    def save_macro(self, name, steps):
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,50}', name) or not 1 <= len(steps) <= self.cfg['max_macro_steps']:
            raise ValueError('宏名称或步骤数无效')
        if any(s.get('action') not in ('tap','swipe','text','screenshot') for s in steps):
            raise ValueError('宏含未授权动作')
        return self.store.append('macros', name=name, steps=steps)

    async def replay(self, name):
        rows = [r for r in self.store.read('macros') if r['name']==name]
        if not rows:
            raise ValueError('宏不存在')
        return [await self.execute(s['action'], s.get('args',{})) for s in rows[-1]['steps']]
