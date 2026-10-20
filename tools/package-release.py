"""仅在本地生成可公开源码包，不创建仓库、不提交、不推送。"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.package_release import build_release


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='生成无个人数据的 QQ ChatBot 源码包')
    parser.add_argument('--output',type=Path,help='可选的新 ZIP 路径，现有文件不会覆盖')
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding='utf-8')
    try:
        print(json.dumps(build_release(output=args.output),ensure_ascii=False,indent=2))
    except Exception as e:
        print(str(e),file=sys.stderr)
        sys.exit(1)
