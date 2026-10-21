"""探测本机已安装的 QQ 客户端，仅供只读诊断（当前向导不复用系统客户端）。

只读：不安装、不启动、不修改系统 QQ 与其登录态。
"""
import json
import os
import re
from pathlib import Path

# Windows 标准卸载项，仅用于只读识别。
REGISTRY_KEYS = (
    (r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\QQ', 'UninstallString'),
    (r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\QQ', 'UninstallString'),
    (r'SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\QQNT', 'UninstallString'),
    (r'SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\QQNT', 'UninstallString'),
)

# 常见安装位置，注册表缺失时兜底。
FALLBACK_ROOTS = (
    r'C:\Program Files\Tencent\QQNT',
    r'C:\Program Files (x86)\Tencent\QQNT',
    r'C:\Program Files\Tencent\QQ',
    r'C:\Program Files (x86)\Tencent\QQ',
)


def _registry_install_dir():
    if os.name != 'nt':
        return None
    try:
        import winreg
    except ImportError:
        return None
    for subkey, value_name in REGISTRY_KEYS:
        for hive in (winreg.HKEY_LOCAL_MACHINE,):
            try:
                with winreg.OpenKey(hive, subkey) as key:
                    value, _ = winreg.QueryValueEx(key, value_name)
            except OSError:
                continue
            # UninstallString 形如 C:\Program Files\Tencent\QQNT\Uninstall.exe
            match = re.match(r'^\s*"([^"]+)"', value) or re.match(r'^(.*?)(?:Uninstall|unins)\w*\.exe\s*$', value, re.I)
            if not match:
                continue
            candidate = Path(match.group(1).strip()).parent
            if (candidate / 'QQ.exe').is_file():
                return candidate
    return None


def _fallback_install_dirs():
    for root in FALLBACK_ROOTS:
        candidate = Path(root)
        if (candidate / 'QQ.exe').is_file():
            yield candidate


def install_dirs():
    """可能的系统 QQ 安装目录，注册表优先。"""
    seen = []
    primary = _registry_install_dir()
    if primary:
        seen.append(primary)
    for candidate in _fallback_install_dirs():
        if candidate not in seen:
            seen.append(candidate)
    return seen


def version_of(folder):
    """读取 QQ 的版本号；读不到返回空字符串。"""
    folder = Path(folder)
    config = folder / 'versions' / 'config.json'
    if config.is_file():
        try:
            data = json.loads(config.read_text(encoding='utf-8-sig'))
            return str(data.get('curVersion') or '')
        except (OSError, ValueError):
            pass
    package = folder / 'resources' / 'app' / 'package.json'
    if package.is_file():
        try:
            data = json.loads(package.read_text(encoding='utf-8-sig'))
            return str(data.get('version') or '')
        except (OSError, ValueError):
            pass
    return ''


def package_json_of(folder):
    """定位与该 QQ 二进制配套的 package.json。

    旧版 QQ 的 resources/app 在 versions/<版本>/ 下，必须与当前二进制配套，
    否则会拿旧版本元数据生成注入补丁，导致登录时误报版本过低。
    """
    folder = Path(folder)
    direct = folder / 'resources' / 'app' / 'package.json'
    if direct.is_file():
        return direct
    config = folder / 'versions' / 'config.json'
    if config.is_file():
        try:
            version = json.loads(config.read_text(encoding='utf-8-sig'))['curVersion']
            if not isinstance(version, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}', version):return None
        except (OSError, ValueError, KeyError):
            return None
        candidate = (folder / 'versions' / version / 'resources' / 'app' / 'package.json')
        if candidate.is_file():
            return candidate
    return None


def build_id_of(folder):
    """读取 QQ 的 buildId；读不到返回 0。"""
    folder = Path(folder)
    config = folder / 'versions' / 'config.json'
    if not config.is_file():
        return 0
    try:
        data = json.loads(config.read_text(encoding='utf-8-sig'))
        return int(data.get('buildId') or 0)
    except (OSError, ValueError, TypeError):
        return 0


def min_build_id(root=None):
    """本地下载清单登记的旧版本提示门槛，不是腾讯实时最低版本承诺。"""
    if root is None:
        from .config import ROOT as root
    try:
        catalog = json.loads((Path(root) / 'config' / 'runtime-downloads.json').read_text(encoding='utf-8-sig'))
        return int((catalog.get('qq') or {}).get('min_build_id') or 0)
    except (OSError, ValueError, TypeError):
        return 0


def too_old(folder, root=None):
    """该 QQ 是否低于本地登记的 buildId 提示门槛。"""
    floor = min_build_id(root)
    if not floor:
        return False
    build = build_id_of(folder)
    if not build:
        return False
    return build < floor


def detect():
    """返回可复用的系统 QQ 列表。

    每项含 path（QQ.exe）、dir、version、build_id、package_json、usable、too_old。
    usable 表示该目录具备 版本诊断所需的配套元数据。
    too_old 仅表示低于本地登记门槛，不能证明腾讯当前会拒绝。
    """
    results = []
    for folder in install_dirs():
        binary = folder / 'QQ.exe'
        package = package_json_of(folder)
        results.append({
            'path': str(binary),
            'dir': str(folder),
            'version': version_of(folder),
            'build_id': build_id_of(folder),
            'package_json': str(package) if package else '',
            'usable': bool(package and package.is_file()),
            'too_old': too_old(folder),
        })
    return results


def find_usable(root=None):
    """旧诊断助手：有元数据且不低于本地门槛；不代表原生适配兼容。"""
    for item in detect():
        if item['usable'] and not item['too_old']:
            return item
    return None
