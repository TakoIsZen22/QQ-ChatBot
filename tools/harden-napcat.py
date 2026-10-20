"""只修改 NapCat WebUI 监听地址，不输出或替换已有认证值。"""
import json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
path=root/'.runtime/napcat/config/webui.json'
if not path.exists():
    print('WebUI config not created yet; run NapCat once, then close it and run this script.')
else:
    value=json.loads(path.read_text(encoding='utf-8-sig'))
    value['host']='127.0.0.1'
    temp=path.with_suffix('.local.tmp')
    temp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    temp.replace(path)
    print('WebUI host restricted to 127.0.0.1; existing credentials preserved without display. Restart NapCat.')
