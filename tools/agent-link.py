"""已授权外部Agent的通用CLI接入口；只领取工作和写回执。"""
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.agent_mcp import request


def main():
    p=argparse.ArgumentParser();sub=p.add_subparsers(dest='command',required=True)
    sub.add_parser('inbox');claim=sub.add_parser('claim');claim.add_argument('--task-id')
    complete=sub.add_parser('complete');complete.add_argument('task_id');complete.add_argument('claim_id');complete.add_argument('--status',choices=['completed','failed','cancelled'],default='completed')
    complete.add_argument('--result-file',type=Path,required=True)
    a=p.parse_args();body=None
    if a.command=='claim':body={'action':'claim',**({'task_id':a.task_id} if a.task_id else {})}
    if a.command=='complete':
        if a.result_file.stat().st_size>200000:raise ValueError('回执文件过大')
        body={'action':'complete','task_id':a.task_id,'claim_id':a.claim_id,'status':a.status,'result':a.result_file.read_text(encoding='utf-8-sig')}
    print(json.dumps(request(body),ensure_ascii=False,indent=2))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    try:main()
    except (ValueError,OSError) as e:print(str(e),file=sys.stderr);sys.exit(1)
