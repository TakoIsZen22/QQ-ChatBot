"""源码/绿色包共用入口；不依赖系统 Python 或当前工作目录。"""
from pathlib import Path
from .config import ROOT


def portable(root=ROOT):
    return (Path(root)/'_runtime/python.exe').is_file()


def python_command(root=ROOT, windowless=False):
    root=Path(root)
    if portable(root):return str(root/'_runtime'/('pythonw.exe' if windowless else 'python.exe'))
    return str(root/'.venv/Scripts'/('pythonw.exe' if windowless else 'python.exe'))
