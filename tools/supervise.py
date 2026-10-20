"""供任意维护 Agent/任务计划程序调用；不安装定时任务或发送通知。"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.core.supervision import collect


def main():
    parser = argparse.ArgumentParser(description='QQ ChatBot Agent 无关只读巡检')
    parser.add_argument('--json', action='store_true', help='输出固定 schema 的 JSON')
    args = parser.parse_args()
    report = collect()
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print(f'QQ ChatBot {report["version"]}: {report["overall"]}')
        for name, healthy in report['checks'].items():
            print(f'  {name}: {"OK" if healthy else "FAIL"}')
        print('最后说话: '+str(report['status'].get('last_spoke') or '尚无记录'))
    return 0 if report['overall'] == 'healthy' else 1


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    sys.exit(main())
