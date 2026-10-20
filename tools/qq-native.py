"""Read-only diagnostics, explicit native-host lifecycle and legacy rollback."""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.core.qq_native import prepare, restore, status, diagnose
from src.core.native_host import NativeHost
from src.core.config import ROOT,load

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='QQ ChatBot 自写 QQ 桥接：手动扫码与只读诊断')
    parser.add_argument('action', choices=['prepare','restore','status','doctor','start','stop','refresh'])
    args = parser.parse_args()
    try:print(json.dumps({'prepare': prepare, 'restore': restore, 'status': status, 'doctor': diagnose,'start':lambda:NativeHost(ROOT).start(load()),'stop':lambda:NativeHost(ROOT).control('stop'),'refresh':lambda:NativeHost(ROOT).control('refresh_qr')}[args.action](), ensure_ascii=False, indent=2))
    except Exception as error:print(str(error), file=sys.stderr);sys.exit(1)
