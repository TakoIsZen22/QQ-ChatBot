"""快捷方式脚本读取当前已验证的图标路径，不读取凭据。"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.identity import installed_identity

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    print(installed_identity().image_path('icon','ico'))
