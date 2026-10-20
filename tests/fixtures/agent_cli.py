"""本地CLI协议夹具；不会调用模型、网络或真实Agent。"""
import subprocess
import sys
import time
from pathlib import Path

mode=sys.argv[1];payload=sys.stdin.buffer.read().decode('utf-8')
if mode=='echo':
    Path(sys.argv[2]).write_text(payload,encoding='utf-8');print('夹具已收到工作正文')
elif mode=='slow':
    Path(sys.argv[2]).touch();time.sleep(30);print('too late')
elif mode=='large':print('x'*200000)
elif mode=='error':
    print('PRIVATE_STDERR_NOT_FOR_STORAGE',file=sys.stderr);sys.exit(2)
elif mode=='text':print('外部回执 <script>fake()</script>，只是文本')
