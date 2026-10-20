import asyncio
import signal
import sys
import os
import aiohttp
from aiohttp import web
from .core.config import load,ROOT
from .core.harness import Harness
from .core.instance import InstanceLock
from .channel.local_ui import build
from .core.service_intent import ServiceIntent

async def run():
    cfg=load()
    if os.environ.get('DFY_MANAGED_START')=='1':
        if not ServiceIntent(ROOT).desired():return
    else:ServiceIntent(ROOT).write(True,'manual_core_start')
    lock=InstanceLock(ROOT/cfg['paths']['data']/'.instance.lock')
    try:
        async with aiohttp.ClientSession(trust_env=False) as session:
            h=Harness(cfg,session)
            shutdown=asyncio.Event()
            loop=asyncio.get_running_loop()
            for sig in (signal.SIGINT,signal.SIGTERM):
                try: loop.add_signal_handler(sig,shutdown.set)
                except (NotImplementedError,RuntimeError): pass
            runner=web.AppRunner(build(h,shutdown),access_log=None,shutdown_timeout=5)
            await runner.setup()
            site=web.TCPSite(runner,cfg['server']['host'],cfg['server']['port'])
            await site.start()
            h.start()
            print(f'QQ ChatBot 已启动：http://127.0.0.1:{cfg["server"]["port"]}；关闭请运行 tools\\stop.bat',flush=True)
            try:
                await shutdown.wait()
            finally:
                await h.close()
                await runner.cleanup()
    finally:
        lock.close()

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try: asyncio.run(run())
    except KeyboardInterrupt:ServiceIntent(ROOT).write(False,'console_interrupt')
