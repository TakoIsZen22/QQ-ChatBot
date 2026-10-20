import asyncio
import tempfile
import time
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock,patch
from src.core.config import load
from src.core.safety import Safety
from src.core.store import Store
from src.core.stickers import Stickers
from src.modules.awakening import Awakening
from src.modules.learning import Learning

class BehaviorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.cfg=load(Path(self.temp.name)/'no-local.json');self.store=Store(self.temp.name)
        self.safety=Safety(self.cfg['safety'],self.store,lambda *a,**k:None)

    async def test_quiet_hours_and_reply_only_block_proactive(self):
        cfg=self.cfg['awakening'];cfg['enabled']=True;cfg['probability']=1
        h=SimpleNamespace(store=self.store,safety=self.safety,cfg=self.cfg,queue=asyncio.Queue(),busy=False,last_received=time.time()-7200,localtime=lambda:datetime.fromisoformat('2026-10-20T23:30:00+08:00'),proactive=AsyncMock(return_value=['hi']))
        a=Awakening(cfg,h)
        self.safety.set('active');await a.tick();h.proactive.assert_not_awaited()
        h.localtime=lambda:datetime.fromisoformat('2026-10-20T12:30:00+08:00')
        self.safety.set('reply_only');await a.tick();h.proactive.assert_not_awaited()
        self.safety.set('active');await a.tick();h.proactive.assert_awaited_once()
        self.assertGreater(a.next_check,time.time()+44*60)

    async def test_sticker_requires_observation_and_daily_limit(self):
        cfg=self.cfg['stickers'];cfg['enabled']=True;cfg['daily_limit']=1
        s=Stickers(cfg,self.store,self.safety,lambda:datetime.now())
        with self.assertRaises(ValueError):s.collect('unknown','梨')
        observed=self.store.append('media',description='一只蓝色小鲸鱼在笑',path='fixture.png')
        sticker=s.collect(observed['id'],'开心时用的小鲸鱼')
        s.note(sticker['id'],'嘿嘿',['开心'])
        self.assertEqual(s.list()[0]['localNote'],'嘿嘿')
        s.reserve(sticker['id'])
        with self.assertRaises(PermissionError):s.reserve(sticker['id'])

    async def test_learning_blocks_private_network_and_disabled(self):
        c=self.cfg['learning'];c.update(enabled=True,allowed_hosts=['127.0.0.1'])
        learning=Learning(c,None,self.store,None)
        with self.assertRaises(PermissionError):await learning.fetch('https://127.0.0.1/private')
        with self.assertRaises(PermissionError):await learning.fetch('http://127.0.0.1/private')
        c['enabled']=False
        with self.assertRaises(PermissionError):await learning.fetch('https://example.com')

    async def test_waiting_rate_slot_is_interruptible(self):
        for _ in range(20):self.safety.reserve('private:1')
        task=asyncio.create_task(self.safety.acquire('private:1',self.safety.generation))
        await asyncio.sleep(.01);self.safety.set('paused')
        self.assertFalse(await asyncio.wait_for(task,1))

if __name__=='__main__':unittest.main()
