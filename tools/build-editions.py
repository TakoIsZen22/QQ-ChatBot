"""Build 1.00.01 API-only and 1.00.02 API + optional Magpie distributions."""
import argparse
import json
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.package_release import build_release,version as release_version
from tools.release_editions import VERSIONS,prepare_edition


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--edition',choices=('all',*VERSIONS),default='all')
    parser.add_argument('--source-only',action='store_true')
    parser.add_argument('--sevenzip',type=Path)
    args=parser.parse_args()
    root=Path(__file__).resolve().parents[1]
    versions=VERSIONS if args.edition=='all' else (args.edition,)
    if release_version(root)=='1.00.01' and '1.00.02' in versions:
        raise ValueError('构建两版请使用 1.00.02 主源码；此专属源码请加 --edition 1.00.01')
    suffixes=('.zip',) if args.source_only else ('.zip','-windows-x64.zip')
    for version in versions:
        for suffix in suffixes:
            target=root/'dist'/f'qq-chatbot-{version}{suffix}'
            if target.exists() or target.with_suffix('.zip.sha256').exists():
                raise FileExistsError('保留已有发行文件，不覆盖：'+target.name)
    archive=root/('.edition-source-'+uuid.uuid4().hex+'.zip')
    results=[]
    try:
        build_release(root,archive)
        for version in versions:
            stage=prepare_edition(archive,root/'.runtime/edition-builds'/version,version)
            # Run each packager inside its own edition: configuration validation uses that version.
            subprocess.run([sys.executable,'tools/package-release.py'],cwd=stage,check=True)
            if not args.source_only:
                command=[sys.executable,'tools/build-windows.py','--download-cache',str(root/'.runtime/public-downloads')]
                if args.sevenzip:command+=['--sevenzip',str(args.sevenzip.resolve())]
                subprocess.run(command,cwd=stage,check=True)
            (root/'dist').mkdir(exist_ok=True)
            for suffix in suffixes:
                name=f'qq-chatbot-{version}{suffix}'
                for item in (name,name+'.sha256'):
                    target=root/'dist'/item
                    if target.exists():raise FileExistsError('不覆盖已有发行文件：'+item)
                    shutil.copyfile(stage/'dist'/item,target)
                results.append({'version':version,'path':str(root/'dist'/name)})
    finally:
        archive.unlink(missing_ok=True)
        archive.with_suffix('.zip.sha256').unlink(missing_ok=True)
    print(json.dumps({'editions':results},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
