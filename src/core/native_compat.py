"""QQ compatibility catalog. Unknown native ABIs are never executed to probe them."""
import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path

# Each entry corresponds to an implemented C++ host / JS session adapter, not a
# claim that arbitrary QQ versions sharing a marketing version are compatible.
ADAPTERS = {'embedded-qqnt-v1': ('24.11.1', '14.4.258.16-electron.0')}
CRITICAL = {'QQNT.dll', 'resources/app/wrapper.node', 'snapshot_blob.bin', 'icudtl.dat'}


def linked(path):
    # Path.is_junction is new in Python 3.12; desktop environments may be 3.11.
    import os
    import stat
    try:
        attributes = getattr(Path(path).lstat(), 'st_file_attributes', 0)
    except FileNotFoundError:return False
    return Path(path).is_symlink() or (os.name == 'nt' and bool(attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT))


def read_json(path):
    path = Path(path)
    if path.is_symlink() or path.stat().st_size > 65536:
        raise ValueError('QQ 兼容元数据无效')
    value = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(value, dict):
        raise ValueError('QQ 兼容元数据无效')
    return value


def catalog(root):
    value = read_json(Path(root)/'config/qq-native-compat.json')
    if value.get('schema') == 'qq-chatbot.native-compat.v1':
        # Existing installations can roll forward without rewriting private state.
        value = {'schema': 'qq-chatbot.native-compat.v2', 'preferred': value['version'],
                 'profiles': [dict(value, adapter='embedded-qqnt-v1')], 'limits': value['limits']}
    profiles = value.get('profiles')
    if value.get('schema') != 'qq-chatbot.native-compat.v2' or not isinstance(profiles, list) or not profiles:
        raise ValueError('QQ 兼容清单格式无效')
    versions = set()
    for item in profiles:
        if not isinstance(item, dict):raise ValueError('QQ 兼容配置无效')
        version = item.get('version')
        if not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', version) or version in versions:
            raise ValueError('QQ 版本标识无效或重复')
        versions.add(version)
        abi = ADAPTERS.get(item.get('adapter'))
        if abi != (item.get('node'), item.get('v8')):
            raise ValueError('QQ 配置需要尚未实现的原生加载器，不能仅添加版本号')
        if not re.fullmatch(r'[0-9]{1,16}', str(item.get('appid', ''))) or not isinstance(item.get('qua'), str) or not item['qua'] or len(item['qua']) > 128:
            raise ValueError('QQ 登录版本参数无效')
        hashes = item.get('sha256')
        if not isinstance(hashes, dict) or set(hashes) != CRITICAL or any(not isinstance(h, str) or not re.fullmatch('[a-f0-9]{64}', h) for h in hashes.values()):
            raise ValueError('QQ 兼容配置缺少完整文件校验')
    if value.get('preferred') not in versions:raise ValueError('QQ 首选版本不在兼容清单内')
    limits = value.get('limits', {})
    if not isinstance(limits, dict):raise ValueError('QQ 兼容清单时间参数无效')
    for key in ('start_timeout_seconds', 'stop_timeout_seconds', 'control_poll_ms', 'qr_max_age_seconds'):
        if type(limits.get(key)) is not int or not 1 <= limits[key] <= 300000:raise ValueError('QQ 兼容清单时间参数无效')
    for key,maximum in (('password_timeout_ms',600000),('login_window_ms',86400000),('login_min_interval_ms',600000),('login_max_attempts',20)):
        if key in limits and (type(limits[key]) is not int or not 1<=limits[key]<=maximum):raise ValueError('QQ 账密登录参数无效')
    return value


def profile(root, version):
    cfg = catalog(root)
    for item in cfg['profiles']:
        if item['version'] == version:return dict(item, limits=cfg['limits'])
    raise ValueError('本机 QQ '+str(version)[:64]+' 尚未适配；可使用向导下载的兼容客户端')


def installed_package(root, selected=''):
    from .qq_native import _packages
    packages = _packages(root)
    cfg = catalog(root)
    order = [cfg['preferred']] + [p['version'] for p in cfg['profiles'] if p['version'] != cfg['preferred']]
    if selected:
        profile(root,selected)
        order=[selected]
    for version in order:
        matches = [p for p in packages if read_json(p).get('version') == version]
        if len(matches) > 1:raise ValueError('独立 QQ 同一版本存在多个目录，请保留原文件并检查布局')
        if matches:return matches[0]
    if len(packages) == 1:profile(root, read_json(packages[0]).get('version'))
    raise ValueError('独立 QQ 目录内未找到已适配的版本，请先准备兼容客户端')


@lru_cache(maxsize=32)
def _digest(file, size, modified):
    with Path(file).open('rb') as stream:return hashlib.file_digest(stream, 'sha256').hexdigest()


def verify_client(client, compat):
    client = Path(client)
    for relative, expected in compat['sha256'].items():
        file = client/relative
        if not file.resolve().is_relative_to(client.resolve()) or any(linked(p) for p in [file, *file.parents]):
            raise ValueError('QQ 文件不能使用链接或联接目录')
        stat = file.stat()
        if _digest(str(file), stat.st_size, stat.st_mtime_ns) != expected:
            raise ValueError('QQ 文件校验失败，拒绝加载；不会覆盖原文件或尝试未知内核')
