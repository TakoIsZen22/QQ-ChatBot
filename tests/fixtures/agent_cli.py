"""本地CLI协议夹具；不会调用模型、网络或真实Agent。

注意：不要向 stdout 打印中文。Windows CI 是英文区域，stdout 编码为 cp1252，
打印中文会抛 UnicodeEncodeError 并让进程以非零码退出。
"""
import subprocess
import sys
import time
from pathlib import Path

mode=sys.argv[1];payload=sys.stdin.buffer.read().decode('utf-8')
if mode=='echo':
    Path(sys.argv[2]).write_text(payload,encoding='utf-8');print('fixture received task text')
elif mode=='slow':
    Path(sys.argv[2]).touch();time.sleep(30);print('too late')
elif mode=='large':print('x'*200000)
elif mode=='error':
    print('PRIVATE_STDERR_NOT_FOR_STORAGE',file=sys.stderr);sys.exit(2)
elif mode=='text':print('external receipt <script>fake()</script>, text only')
