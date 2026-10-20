"""桌面WebView独立Python3.11环境，不修改核心/语音环境。"""
import re
import subprocess
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if (root/'.venv-desktop/Scripts/python.exe').exists():sys.exit(0)
listing=subprocess.run(['py','--list'],capture_output=True,text=True)
selectors=re.findall(r'-V:(\S*3\.11\S*)',listing.stdout+listing.stderr)
choices=[['py','-3.11']]+[['py','-V:'+s.replace('\\','/').removesuffix('*')] for s in selectors]
for prefix in choices:
    check=subprocess.run(prefix+['-c','import sys;print(sys.version_info[:2])'],capture_output=True,text=True)
    if check.returncode==0 and '(3, 11)' in check.stdout:
        subprocess.run(prefix+['-m','venv',str(root/'.venv-desktop')],check=True)
        break
else:
    print('Python 3.11 is required for the isolated desktop runtime.',file=sys.stderr);sys.exit(1)
