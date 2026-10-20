"""Build only our Windows x64 embedding host; never downloads or bundles QQ."""
import argparse
import json
import os
import subprocess
from pathlib import Path


def build(root, output=None):
    root=Path(root).resolve()
    if os.name!='nt':raise RuntimeError('原生加载器需要 Windows x64 构建机')
    import winreg
    locator=Path(os.environ.get('ProgramFiles(x86)',r'C:\Program Files (x86)'))/'Microsoft Visual Studio/Installer/vswhere.exe'
    result=subprocess.run([str(locator),'-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath'],capture_output=True,text=True,check=True)
    vs=Path(result.stdout.strip())
    versions=sorted((vs/'VC/Tools/MSVC').glob('*'),key=lambda p:tuple(int(x) for x in p.name.split('.')))
    if not versions:raise RuntimeError('构建机请安装 Visual Studio C++ x64 工具和 Windows SDK')
    vc=versions[-1]
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Windows Kits\Installed Roots') as key:sdk=Path(winreg.QueryValueEx(key,'KitsRoot10')[0])
    sdkver=sorted((sdk/'Include').glob('10.*'),key=lambda p:tuple(int(x) for x in p.name.split('.')))[-1].name
    env=os.environ.copy()
    env['INCLUDE']=';'.join(map(str,[vc/'include',sdk/'Include'/sdkver/'ucrt',sdk/'Include'/sdkver/'shared',sdk/'Include'/sdkver/'um']))
    env['LIB']=';'.join(map(str,[vc/'lib/x64',sdk/'Lib'/sdkver/'ucrt/x64',sdk/'Lib'/sdkver/'um/x64']))
    output=Path(output) if output else root/'.runtime/native-host/QQChatBot.NativeHost.exe'
    output.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([str(vc/'bin/Hostx64/x64/cl.exe'),'/nologo','/EHsc','/std:c++17','/MT','/guard:cf',str(root/'src/qq_native/host.cpp'),'/Fo'+str(output.with_suffix('.obj')),'/Fe'+str(output),'/link','/DYNAMICBASE','/NXCOMPAT'],env=env,check=True)
    return {'built':True,'path':str(output)}

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path);args=parser.parse_args()
    print(json.dumps(build(Path(__file__).resolve().parents[1],args.output),ensure_ascii=False))
