"""从统一配置为已解压的 NapCat 创建首次 OneBot 配置。不覆盖已有文件，不处理凭据。"""
import json
import sys
from pathlib import Path
from urllib.parse import urlsplit
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.config import ROOT,load

def main():
    cfg=load();bot=str(cfg['qq']['bot_id'])
    if not bot.isdigit():raise ValueError('请先填 qq.bot_id（机器人号，不是主人号）')
    folder=ROOT/'.runtime/napcat/config'
    if not folder.is_dir():raise ValueError('请先解压官方 NapCat Shell 到 .runtime/napcat')
    dest=folder/f'onebot11_{bot}.json'
    http=urlsplit(cfg['qq']['http_url']);ws=urlsplit(cfg['qq']['ws_url'])
    body={'network':{'httpServers':[{'name':'da-fei-yu-http','enable':True,'port':http.port or 80,'host':'127.0.0.1','enableCors':False,'messagePostFormat':'array','token':'','debug':False}], 'httpClients':[], 'websocketServers':[{'name':'da-fei-yu-ws','enable':True,'host':'127.0.0.1','port':ws.port or 80,'messagePostFormat':'array','reportSelfMessage':False,'token':'','enableForcePushEvent':False,'debug':False,'heartInterval':30000}], 'websocketClients':[]},'musicSignUrl':'','enableLocalFile2Url':False}
    try:
        with dest.open('x',encoding='utf-8') as f:json.dump(body,f,ensure_ascii=False,indent=2)
    except FileExistsError:
        print('Existing NapCat config kept unchanged; use WebUI to edit.');return
    print('Created loopback-only OneBot HTTP/WS config. Tokens left blank for user configuration.')
    print('Restart NapCat if it has already logged in. Do not expose these ports to the network.')

if __name__=='__main__':
    try:main()
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
