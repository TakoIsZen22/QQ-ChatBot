"""使用独立 QQ 客户端启动官方 NapCat loader，不修改系统 QQ 安装或登录态。"""
import json
import os
import subprocess
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.config import ROOT,load

def main():
    cfg=load();runtime=ROOT/'.runtime/napcat'
    binary=Path(cfg['qq']['client_path']) if cfg['qq']['client_path'] else None
    bot=str(cfg['qq']['bot_id'])
    if not bot.isdigit():raise ValueError('请先配置 qq.bot_id')
    if bot==str(cfg['owner']['qq_id']):raise ValueError('机器人不能使用主人账号')
    if binary is None:
        return subprocess.call(['cmd.exe','/c',str(runtime/'launcher-user.bat'),bot],cwd=runtime)
    binary=binary.resolve()
    if not binary.is_file():raise ValueError('qq.client_path 指向的 QQ 客户端不存在')
    # 与当前二进制配套的版本元数据，避免旧 Shell 包固定元数据造成登录版本误报。
    # 复用系统 QQ 时元数据在 versions/<版本>/resources/app 下，同样要取配套的那份。
    package=binary.parent/'resources/app/package.json'
    versions=binary.parent/'versions/config.json'
    if not package.is_file() and versions.is_file():
        version=json.loads(versions.read_text(encoding='utf-8-sig'))['curVersion']
        candidate=(binary.parent/'versions'/version/'resources/app/package.json').resolve()
        if not candidate.is_relative_to(binary.parent):raise ValueError('QQ 版本路径无效')
        package=candidate
    if not package.is_file():raise ValueError('无法定位 QQ 客户端的原始 package.json，拒绝沿用旧版本元数据')
    patch=json.loads(package.read_text(encoding='utf-8-sig'))
    patch['main']='./loadNapCat.js'
    generated=runtime/'qqnt-local-client.json'
    generated.write_text(json.dumps(patch,ensure_ascii=False,indent=2),encoding='utf-8')
    env=os.environ.copy()
    for key,file in {'NAPCAT_PATCH_PACKAGE':generated,'NAPCAT_LOAD_PATH':runtime/'loadNapCat.js','NAPCAT_INJECT_PATH':runtime/'NapCatWinBootHook.dll','NAPCAT_LAUNCHER_PATH':runtime/'NapCatWinBootMain.exe','NAPCAT_MAIN_PATH':runtime/'napcat.mjs'}.items():env[key]=str(file)
    print('Starting dedicated bot QQ client: '+str(binary),flush=True)
    hidden=getattr(subprocess,'CREATE_NO_WINDOW',0) if os.environ.get('DFY_DESKTOP_HIDDEN')=='1' else 0
    return subprocess.call([str(runtime/'NapCatWinBootMain.exe'),str(binary),str(runtime/'NapCatWinBootHook.dll'),bot],cwd=runtime,env=env,creationflags=hidden)

if __name__=='__main__':
    try:sys.exit(main())
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
