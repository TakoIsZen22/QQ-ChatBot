import random
import re

class Conversation:
    def __init__(self, cfg, safety, localtime):
        self.cfg, self.safety, self.localtime = cfg, safety, localtime

    def bubbles(self, text):
        # 不把 CQ 码当协议输出；QQ 出口进一步使用结构化 text segment。
        text = re.sub(r'\[CQ:[^\]]*\]', '', str(text)).strip()
        parts = [p.strip() for p in re.split(r'\n\s*\n', text) if p.strip()]
        chunks = []
        for p in parts:
            while len(p) > self.cfg['bubble_chars']:
                end = self.cfg['bubble_chars']
                candidates = [p.rfind(mark, 0, end) for mark in ('。','！','？','\n')]
                cut = max(candidates) + 1
                cut = cut if cut > end//3 else end
                chunks.append(p[:cut]); p = p[cut:].strip()
            if p:
                chunks.append(p)
        # 不静默丢内容；将超出的内容合并入最后一条。
        n = self.cfg['max_bubbles']
        return chunks[:n-1] + ['\n'.join(chunks[n-1:])] if len(chunks) > n else chunks

    async def speak(self, text, send, generation, group=False, proactive=False):
        sent = []
        for bubble in self.bubbles(text):
            if not self.safety.allowed(group, proactive, generation):
                break
            delay = random.uniform(self.cfg['min_delay_seconds'], self.cfg['max_delay_seconds'])
            if self.localtime().hour >= 23 or self.localtime().hour < 8:
                delay *= self.cfg['night_multiplier']
            if not await self.safety.delay(delay, generation):
                break
            if not self.safety.allowed(group, proactive, generation):
                break
            if await send(bubble):
                sent.append(bubble)
        return sent
