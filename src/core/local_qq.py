"""Read local QQ program metadata; copy verified program files only on request.

Never recurse into accounts, profiles, databases or logs, and never run system QQ.
"""
import shutil
from pathlib import Path
from . import system_qq
from .native_compat import catalog, profile, read_json, verify_client, linked
from .runtime_downloads import catalog as downloads


def _source(item):
    folder = Path(item['dir'])
    package = system_qq.package_json_of(folder)
    if package is None or not package.resolve().is_relative_to(folder.resolve()):
        raise ValueError('本机 QQ 版本元数据缺失或路径越界')
    if any(linked(p) for p in [package, *package.parents]):
        raise ValueError('本机 QQ 目录不能使用链接或联接目录')
    return package, package.parents[2]


def scan(root):
    cfg = catalog(root)
    rows = []
    for index, item in enumerate(system_qq.detect()):
        row = {'index': index, 'dir': item['dir'], 'version': item['version'][:64],
               'compatible': False, 'reason': '未适配', 'below_catalog_floor': item['too_old']}
        try:
            package, client = _source(item)
            version = read_json(package).get('version')
            if version != item['version']:raise ValueError('本机 QQ 当前版本与元数据不一致，请完成更新后重试')
            compat = profile(root, version)
            verify_client(client, compat)
            row.update(compatible=True, reason='已适配且关键文件校验通过；可复制到独立目录，需重新扫码')
        except (OSError, ValueError, KeyError, TypeError) as error:
            row['reason'] = str(error) if type(error) is ValueError else '本机 QQ 文件不完整，请使用独立兼容客户端'
        rows.append(row)
    return {'clients': rows, 'supported_versions': [p['version'] for p in cfg['profiles']],
            'message': '检测仅读取安装位置、版本元数据和程序文件校验，不读取账号或登录态。'}


def copy_program(root, index, stage):
    """Copy into a new staging directory. Never replace existing runtime versions."""
    items = system_qq.detect()
    if type(index) is not int or not 0 <= index < len(items):raise ValueError('请重新检测并选择本机 QQ')
    item = items[index]
    package, client = _source(item)
    version = read_json(package).get('version')
    if version != item['version']:raise ValueError('本机 QQ 版本已变化，请重新检测')
    compat = profile(root, version)
    verify_client(client, compat)
    # Only the native runtime and direct library dependencies are used by the
    # embedded host. In particular, never copy guild*.db, account JSON or QQ.exe.
    names = set(compat['sha256']) | {'resources/app/package.json'}
    for folder in (client, client/'resources/app'):
        names.update(p.relative_to(client).as_posix() for p in folder.glob('*.dll'))
    limits = downloads(root)['limits']
    if len(names) > limits['max_files']:raise ValueError('本机 QQ 程序文件数量超过限制')
    size = 0
    for name in sorted(names):
        file = client/name
        if not file.resolve().is_relative_to(client.resolve()) or not file.is_file() or any(linked(p) for p in [file, *file.parents]):
            raise ValueError('本机 QQ 程序文件路径无效')
        size += file.stat().st_size
        if size > limits['max_unpacked_bytes']:raise ValueError('本机 QQ 程序文件超过空间限制')
        target = Path(stage)/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, target)
    # QQ updater can replace files during the copy. Validate the copy again.
    if read_json(Path(stage)/'resources/app/package.json').get('version') != version:
        raise ValueError('复制时 QQ 版本发生变化，请重试')
    verify_client(stage, compat)
    return version
