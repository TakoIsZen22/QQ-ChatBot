"""从隐私白名单源码创建自带 CPython 的 Windows x64 绿色包；不复制本机环境。"""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.package_release import build_release,version
from src.core.runtime_downloads import catalog,download,safe_zip


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--sevenzip',type=Path);parser.add_argument('--download-cache',type=Path)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1];v=version(root)
    if os.name!='nt':raise RuntimeError('Windows x64 构建需要 Windows')
    stage=root/'.runtime/builds'/f'qq-chatbot-{v}-windows-x64'
    if stage.exists():raise FileExistsError('构建目录已存在，请保留旧构建并选择新版本')
    out=root/'dist'/f'qq-chatbot-{v}-windows-x64.zip'
    if out.exists():raise FileExistsError('发布包已存在，不覆盖')
    clean=build_release(root,root/'.runtime-build-source.zip')
    try:
        # Source builder is the privacy boundary; no copytree of the working directory.
        with zipfile.ZipFile(clean['path']) as z:
            for entry in z.infolist():
                rel=Path(*Path(entry.filename).parts[1:]);dest=stage/rel
                dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(entry))
    finally:Path(clean['path']).unlink()
    import importlib.util
    spec=importlib.util.spec_from_file_location('native_host_build',root/'tools/build-native-host.py');builder=importlib.util.module_from_spec(spec);spec.loader.exec_module(builder)
    builder.build(root,stage/'_tools/qq-native/QQChatBot.NativeHost.exe')
    (stage/'_tools/qq-native/QQChatBot.NativeHost.obj').unlink()
    cfg=catalog(root);cache=(args.download_cache or root/'.runtime/public-downloads').resolve();limits=cfg['limits']
    embedded=download(cfg['python'],cache);safe_zip(embedded,stage/'_runtime',limits)
    (stage/'_runtime/python313._pth').write_text('python313.zip\n.\nLib/site-packages\n..\nimport site\n',encoding='utf-8')
    # Builder pip vendors the pinned wheels; users never run pip or install Python.
    wheel_dir=cache/'wheels';wheel_dir.mkdir(exist_ok=True)
    subprocess.run([sys.executable,'-m','pip','wheel','--no-deps','--wheel-dir',str(wheel_dir),'proxy_tools==0.1.0'],check=True)
    subprocess.run([sys.executable,'-m','pip','install','--target',str(stage/'_runtime/Lib/site-packages'),
        '--python-version','3.13','--implementation','cp','--abi','cp313','--platform','win_amd64',
        '--only-binary=:all:','--find-links',str(wheel_dir),'--no-compile','-r',str(root/'requirements.windows.lock.txt')],check=True)
    seven=args.sevenzip or shutil.which('7z')
    if not seven:raise RuntimeError('构建机需要 7-Zip：传 --sevenzip 指定官方 7z.exe（用户不需要安装）')
    msi=download(cfg['sevenzip'],cache);seven_stage=stage/'_tools/7zip';seven_stage.mkdir(parents=True)
    subprocess.run([str(seven),'e',str(msi),'-y','-o'+str(seven_stage),'_7z.exe','_7z.dll','License.txt'],check=True,stdout=subprocess.DEVNULL)
    for name in ('7z.exe','7z.dll'):(seven_stage/('_'+name)).rename(seven_stage/name)
    if not all((seven_stage/n).is_file() for n in ('7z.exe','7z.dll','License.txt')):raise RuntimeError('7-Zip 分发文件不完整')
    compiler=Path(os.environ['WINDIR'])/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(compiler),'/nologo','/target:winexe','/platform:x64','/reference:System.Windows.Forms.dll',
        '/win32icon:'+str(stage/'assets/xiaojing-user-icon.ico'),'/out:'+str(stage/'QQ ChatBot.exe'),str(stage/'tools/portable-launcher.cs')],check=True)
    # Write no runtime state into the shipping directory during validation.
    check='import sys,aiohttp,webview,clr,pystray,PIL,tzdata;from src.core.config import load;assert not load()["qq"]["enabled"];print(sys.version.split()[0])'
    env=os.environ.copy();env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONUTF8']='1'
    subprocess.run([str(stage/'_runtime/python.exe'),'-B','-c',check],cwd=stage,env=env,check=True)
    (stage/'开始使用.txt').write_text('QQ ChatBot\n\n双击 QQ ChatBot.exe，在向导中配置模型后可使用本机聊天。\n向导可下载固定官方 QQ 内核并扫码；不会自动解除暂停。真实收发需在本次安装确认。\n完整教程：docs/GETTING_STARTED.md；QQ 进度：docs/QQ_SETUP.md（也可在程序内阅读）。\n请完整解压，不要只复制 EXE；不要放在 Program Files 或压缩包中运行。\n本包不含账号、密钥、聊天或 QQ 登录态。\n',encoding='utf-8-sig')
    files={p.relative_to(stage).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(stage.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    manifest={'schema':'qq-chatbot.windows-release.v1','version':v,'python':cfg['python']['version'],'files':files}
    (stage/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    out.parent.mkdir(exist_ok=True)
    with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file():z.write(p,stage.name+'/'+p.relative_to(stage).as_posix())
    sha=hashlib.sha256(out.read_bytes()).hexdigest()
    # 用 LF 换行：Windows 的 write_text 默认写 CRLF，会让 sha256sum -c 失败。
    out.with_suffix('.zip.sha256').write_bytes((sha+'  '+out.name+'\n').encode('ascii'))
    print(json.dumps({'path':str(out),'stage':str(stage),'sha256':sha,'files':len(files)},ensure_ascii=False))


if __name__=='__main__':main()
