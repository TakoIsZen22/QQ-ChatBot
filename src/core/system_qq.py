"""探测本机已安装的 QQ 客户端，供向导优先复用而不必下载独立副本。

只读：不安装、不启动、不修改系统 QQ 与其登录态。
"""
import json
import os
import re
from pathlib import Path

# NapCat 官方 launcher 就是从这些注册表键找系统 QQ，保持一致。
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
        except (OSError, ValueError, KeyError):
            return None
        candidate = (folder / 'versions' / version / 'resources' / 'app' / 'package.json')
        if candidate.is_file():
            return candidate
    return None


def detect():
    """返回可复用的系统 QQ 列表。

    每项含 path（QQ.exe）、dir、version、package_json、usable。
    usable 表示该目录具备 NapCat 注入所需的配套元数据。
    """
    results = []
    for folder in install_dirs():
        binary = folder / 'QQ.exe'
        package = package_json_of(folder)
        results.append({
            'path': str(binary),
            'dir': str(folder),
            'version': version_of(folder),
            'package_json': str(package) if package else '',
            'usable': bool(package and package.is_file()),
        })
    return results


def find_usable():
    """第一个可用的系统 QQ；没有返回 None。"""
    for item in detect():
        if item['usable']:
            return item
    return None
