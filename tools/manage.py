"""所有路径相对项目，不依赖调用者 cwd。health 为纯只读。"""
import argparse
import hashlib
import json
import shutil
import socket
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.config import ROOT,load,save_local
from src.core.instance import InstanceLock
from src.core.service_intent import ServiceIntent
from src.core.product import is_harness

def request(cfg,path,body=None):
    data=None if body is None else json.dumps(body).encode()
    req=urllib.request.Request(f'http://127.0.0.1:{cfg["server"]["port"]}/api/'+path,data=data,headers={'Content-Type':'application/json','X-Harness-Local':'1'})
    with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=3) as r:
        return json.load(r)

def port_open(port):
    try:
        with socket.create_connection(('127.0.0.1',port),timeout=1):return True
    except OSError:return False

def validate_jsonl(root):
    counts={}
    for p in root.rglob('*.jsonl'):
        count=0
        for n,line in enumerate(p.read_text(encoding='utf-8-sig').splitlines(),1):
            if not line.strip():continue
            try: json.loads(line)
            except json.JSONDecodeError as e:raise ValueError(f'{p}:{n} JSONL 损坏') from e
            count+=1
        counts[str(p.relative_to(root))]=count
    return counts

def manifest(root):
    return {str(p.relative_to(root)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob('*')) if p.is_file() and p.name!='.instance.lock'}

def backup(cfg):
    source=ROOT/cfg['paths']['data']
    lock=InstanceLock(source/'.instance.lock')
    try:
        counts=validate_jsonl(source)
        dest=ROOT/cfg['paths']['backups']/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        dest.mkdir(parents=True,exist_ok=False)
        shutil.copytree(source,dest/'data',ignore=shutil.ignore_patterns('.instance.lock'))
        hashes=manifest(dest/'data')
        (dest/'manifest.json').write_text(json.dumps({'files':hashes,'jsonl_counts':counts},ensure_ascii=False,indent=2),encoding='utf-8')
        # 配置独立备份，无密钥；恢复数据时不覆盖当前运行配置。
        shutil.copytree(ROOT/'config',dest/'config')
        return dest
    finally:lock.close()

def restore(cfg,source):
    src=Path(source).resolve()
    if not (src/'manifest.json').is_file() or not (src/'data').is_dir():
        raise ValueError('请选择含 manifest.json 和 data 目录的备份文件夹')
    expected=json.loads((src/'manifest.json').read_text(encoding='utf-8'))['files']
    if manifest(src/'data')!=expected:
        raise ValueError('备份 SHA256 校验失败，未修改现有数据')
    counts=validate_jsonl(src/'data')
    target=(ROOT/cfg['paths']['data']).resolve()
    if src.is_relative_to(target) or target.is_relative_to(src):
        raise ValueError('备份源不能在数据目录里或包含目标目录')
    lock=InstanceLock(target/'.instance.lock')
    try:
        stamp=datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        saved=ROOT/cfg['paths']['backups']/('before-restore-'+stamp)
        stage=target.with_name(target.name+'.restore-'+stamp)
        stage.mkdir(parents=True)
        try:
            shutil.copytree(src/'data',stage,dirs_exist_ok=True)
            if manifest(stage)!=expected: raise ValueError('恢复暂存校验失败')
            saved.mkdir(parents=True)
            for child in list(target.iterdir()):
                if child.name=='.instance.lock':continue
                shutil.move(str(child),str(saved/child.name))
            try:
                for child in list(stage.iterdir()):shutil.move(str(child),str(target/child.name))
            except BaseException:
                # 清理已搬入的条目后回滚；路径固定为已验证项目数据目录。
                for child in list(target.iterdir()):
                    if child.name=='.instance.lock':continue
                    if child.is_dir():shutil.rmtree(child)
                    else:child.unlink()
                for child in list(saved.iterdir()):shutil.move(str(child),str(target/child.name))
                raise
        finally:
            if stage.exists():shutil.rmtree(stage)
        return {'restored':str(src),'previous_data':str(saved),'jsonl_counts':counts}
    finally:lock.close()

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['health','stop','backup','restore','validate','pause','reply-only','active','set-model'])
    parser.add_argument('source',nargs='?')
    a=parser.parse_args();cfg=load()
    if a.command=='set-model':
        if not a.source:raise ValueError('set-model 必须提供所选 API 的模型 id')
        save_local({'model':{'main':a.source}})
        print('Model saved. Restart required.');return 0
    if a.command=='health':
        ports={'harness':cfg['server']['port']}
        if cfg['qq']['enabled']:
            from urllib.parse import urlsplit
            ports['qq_native']=cfg['qq']['native_port']
        report={'ports':{k:port_open(p) for k,p in ports.items()}}
        from src.core.model_endpoint import probe_port
        report['ports']['model_api']=probe_port(cfg['model'])
        if cfg['model']['provider']=='magpie':report['ports']['magpie']=report['ports']['model_api']
        try:report['status']=request(cfg,'status')
        except Exception as e:report['status_error']=str(e)
        print(json.dumps(report,ensure_ascii=False,indent=2))
        return 0 if all(report['ports'].values()) and (not cfg['qq']['enabled'] or (report.get('status',{}).get('qq_connected') and report.get('status',{}).get('qq_online'))) else 1
    if a.command=='stop':
        ServiceIntent(ROOT).write(False,'maintenance_stop')
        if not port_open(cfg['server']['port']):print('Already stopped');return 0
        if not is_harness(request(cfg,'status')):raise RuntimeError('端口不属于本项目，拒绝停止')
        request(cfg,'stop',{})
        for _ in range(100):
            if not port_open(cfg['server']['port']):print('Stopped');return 0
            time.sleep(.1)
        raise RuntimeError('停止超时；检查进程，不要重复启动')
    if a.command in ('pause','reply-only','active'):
        print(json.dumps(request(cfg,'safety',{'mode':{'pause':'paused','reply-only':'reply_only','active':'active'}[a.command]}),ensure_ascii=False));return 0
    if a.command=='validate':print(json.dumps(validate_jsonl(ROOT/cfg['paths']['data']),ensure_ascii=False,indent=2));return 0
    if a.command=='backup':print(backup(cfg));return 0
    if a.command=='restore':
        if not a.source:raise ValueError('restore 必须指定备份文件夹')
        print(json.dumps(restore(cfg,a.source),ensure_ascii=False,indent=2));return 0

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:sys.exit(main())
    except Exception as e:print('ERROR: '+str(e),file=sys.stderr);sys.exit(1)
