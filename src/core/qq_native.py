"""Original native bridge experiment. Only patch a dedicated QQ copy, never system QQ."""
import hashlib
import http.client
import json
import re
from pathlib import Path

from .config import ROOT, load
from .native_compat import linked


def _packages(root):
    dedicated = root / '.runtime/qq-client'
    if any(linked(p) for p in [dedicated, *dedicated.parents]):
        raise ValueError('独立 QQ 路径不能使用链接')
    dedicated = dedicated.resolve()
    # The installer moves the directory containing QQ.exe, stripping NSIS's Files/.
    # Accept both this layout and older extracted copies; never search system QQ.
    packages = []
    for pattern in ('versions/*/resources/app/package.json', 'resources/app/package.json',
                    'Files/versions/*/resources/app/package.json', 'Files/resources/app/package.json'):
        packages.extend(dedicated.glob(pattern))
    for package in packages:
        if not package.resolve().is_relative_to(dedicated) or any(linked(p) for p in [package, *package.parents]):
            raise ValueError('独立 QQ 路径不能使用链接')
    return packages


def _package(root):
    packages = _packages(root)
    if len(packages) != 1:raise ValueError('旧实验入口要求项目内恰好一份独立 QQ；不修改系统 QQ')
    return packages[0].resolve()


def diagnose(root=ROOT, cfg=None, *, probe=True):
    """Read-only hashes/process identity/get_status. Never starts a kernel or sends."""
    from .native_host import NativeHost, runtime, executable
    root=Path(root).resolve();cfg=cfg or load();client=root/'.runtime/qq-client'
    report={'schema':'qq-chatbot.native-diagnostics.v2','experimental':True,'launch_available':False,
            'accounts_configured':bool(cfg['owner']['qq_id'] and cfg['qq']['bot_id']),
            'client':{'present':(client/'QQ.exe').is_file() or (client/'Files/QQ.exe').is_file()},
            'entry':{'prepared':False,'host_built':False,'runtime_verified':False},
            'gateway':{'checked':probe,'reachable':False,'driver_ready':False,'online':False},
            'session':NativeHost(root).status(),
            'pending':['real_login_and_message_acceptance_on_this_installation']}
    try:
        from .native_compat import installed_package
        try:target=installed_package(root,cfg['qq'].get('native_version',''))
        except (OSError,ValueError):target=_package(root)  # Metadata only; never authorizes launch.
        package=json.loads(target.read_text(encoding='utf-8-sig'))
        report['client']['metadata_valid']=True
        version=package.get('version')
        if isinstance(version,str) and re.fullmatch(r'[A-Za-z0-9._-]{1,64}',version):report['client']['version']=version
        report['entry']['prepared']=package.get('main')=='./qq-chatbot-entry.js'
        executable(root);report['entry']['host_built']=True
        runtime(root,cfg['qq'].get('native_version',''));report['entry']['runtime_verified']=True
        report['client']['present']=True
    except (OSError,ValueError,TypeError,KeyError,AttributeError) as error:
        # Only our fixed validation messages are exposed, never raw file/JSON content.
        report['compatibility_error']=str(error) if type(error) is ValueError else 'QQ 文件或兼容清单不完整，请检查组件'
    report['launch_available']=all((report['accounts_configured'],report['entry']['host_built'],report['entry']['runtime_verified']))
    if probe:
        connection=http.client.HTTPConnection('127.0.0.1',cfg['qq']['native_port'],timeout=1)
        try:
            connection.request('POST','/get_status',body=b'{}',headers={'Content-Type':'application/json','X-QQ-ChatBot':'1'})
            response=connection.getresponse();raw=response.read(8193)
            if response.status!=200 or response.getheader('Content-Type','').split(';')[0]!='application/json' or len(raw)>8192:raise ValueError('invalid gateway')
            value=json.loads(raw);data=value.get('data') if isinstance(value,dict) else None
            if value.get('status')!='ok' or value.get('retcode')!=0 or not isinstance(data,dict) or type(data.get('online')) is not bool or type(data.get('good')) is not bool:raise ValueError('invalid gateway')
            report['gateway'].update(reachable=True,driver_ready=data['good'],online=data['online'])
        except (OSError,ValueError,AttributeError,http.client.HTTPException):pass
        finally:connection.close()
    if not report['client']['present']:stage='client_missing';message='请先下载独立 QQ 组件'
    elif not report['client'].get('metadata_valid'):stage='client_layout_invalid';message=report.get('compatibility_error','独立 QQ 目录结构不完整')
    elif not report['entry']['host_built']:stage='host_missing';message='缺少自写加载器；源码运行请先执行 tools/build-native-host.py'
    elif not report['entry']['runtime_verified']:stage='runtime_unverified';message=report.get('compatibility_error','QQ 兼容校验未通过，禁止加载；如曾修改旧入口请先 restore')
    elif report['session']['phase']=='ready':stage='acceptance_pending';message='机器人已登录，仍需在本次安装核对真实收发；不会自动解除暂停'
    else:stage=report['session']['phase'];message='可手动扫码接入；聊天安全模式保持不变，升级 QQ 后必须重新适配'
    report.update(stage=stage,message=message)
    return report


def prepare(root=ROOT, cfg=None):
    root = Path(root).resolve()
    cfg = cfg or load()
    q = cfg['qq']; owner = str(cfg['owner']['qq_id']); bot = str(q['bot_id'])
    if not re.fullmatch(r'[0-9]{5,12}',owner) or not re.fullmatch(r'[0-9]{5,12}',bot) or owner == bot:
        raise ValueError('先配置不同的主人号与机器人号')
    target = _package(root)
    directory = root / '.runtime/qq-native'
    directory.mkdir(parents=True, exist_ok=True)
    backup = directory / 'package.original.json'
    marker = directory / 'installation.json'
    raw = target.read_bytes()
    original = json.loads(raw.decode('utf-8-sig'))
    if marker.exists():
        meta = json.loads(marker.read_text(encoding='utf-8'))
        digest = hashlib.sha256(raw).hexdigest()
        if meta['package'] != str(target) or digest not in (meta['patched_sha256'],meta['original_sha256']):
            raise ValueError('QQ 文件发生变化，保留备份并先恢复；拒绝覆盖新版本')
        if hashlib.sha256(backup.read_bytes()).hexdigest() != meta['original_sha256']:
            raise ValueError('QQ 原文件备份发生变化，拒绝继续准备')
        original = json.loads(backup.read_text(encoding='utf-8-sig'))
    elif backup.exists():
        raise ValueError('已有未完成安装的原文件备份，拒绝覆盖')
    else:
        with backup.open('xb') as handle:
            handle.write(raw)
    main = original.get('main')
    if not isinstance(main, str) or not main.startswith('./') or '..' in Path(main).parts:
        raise ValueError('QQ 主入口格式不支持')
    original_entry = (target.parent / main).resolve()
    if not original_entry.is_relative_to(target.parent):
        raise ValueError('QQ 原入口越界')
    policy = {'owner': owner, 'bot': bot, 'groups': [str(g['group_id']) for g in cfg['group_monitor']['groups'] if g['enabled']],
              'port': q['native_port'], 'directory': str(directory)}
    entry = target.parent / 'qq-chatbot-entry.js'
    script = "'use strict';\nrequire(" + json.dumps(str(root/'src/qq_native/bootstrap.js')) + ').install(' + json.dumps(policy) + ');\nrequire(' + json.dumps(str(original_entry)) + ');\n'
    if entry.exists() and not marker.exists():
        raise ValueError('已有未知的 QQ 入口文件，拒绝覆盖')
    entry.write_text(script, encoding='utf-8')
    patched = dict(original, main='./qq-chatbot-entry.js')
    data = (json.dumps(patched, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
    # Manifest is kept before the last replace, so failures remain recoverable.
    meta = {'package': str(target), 'original_sha256': hashlib.sha256(backup.read_bytes()).hexdigest(),
            'patched_sha256': hashlib.sha256(data).hexdigest()}
    marker.write_text(json.dumps(meta), encoding='utf-8')
    pending = target.with_suffix('.qq-chatbot.tmp')
    pending.write_bytes(data); pending.replace(target)
    return {'prepared': True, 'experimental': True, 'message': '独立 QQ 实验入口已准备；尚未证明真实客户端可加载'}


def restore(root=ROOT):
    root = Path(root).resolve(); directory = root/'.runtime/qq-native'
    meta = json.loads((directory/'installation.json').read_text(encoding='utf-8'))
    target = _package(root); backup = directory/'package.original.json'
    if meta['package'] != str(target) or hashlib.sha256(backup.read_bytes()).hexdigest() != meta['original_sha256']:
        raise ValueError('原文件备份或目标不匹配，未恢复')
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    if digest == meta['original_sha256']:
        return {'restored': True, 'message': '独立 QQ 原入口已经恢复'}
    if digest != meta['patched_sha256']:
        raise ValueError('QQ 已发生变化，拒绝覆盖；保留原文件备份')
    pending = target.with_suffix('.qq-chatbot.tmp'); pending.write_bytes(backup.read_bytes()); pending.replace(target)
    # Keep installation metadata and both entry/backup for audit; no login data touched.
    return {'restored': True, 'message': '独立 QQ 原入口已恢复，备份保留；未更改生产连接'}


def status(root=ROOT):
    from .native_host import NativeHost
    return NativeHost(root).status()
