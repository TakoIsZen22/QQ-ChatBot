"""选择 Windows launcher 中的 Python 3.11（包括 uv/Astral provider）。"""
import re
import subprocess
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
if (root/'.venv-voice/Scripts/python.exe').exists():sys.exit(0)
listing=subprocess.run(['py','--list'],capture_output=True,text=True)
selectors=re.findall(r'-V:(\S*3\.11\S*)',listing.stdout+listing.stderr)
choices=[['py','-3.11']]+[['py','-V:'+s.replace('\\','/').removesuffix('*')] for s in selectors]
for prefix in choices:
    check=subprocess.run(prefix+['-c','import sys;print(sys.version_info[:2])'],capture_output=True,text=True)
    if check.returncode==0 and '(3, 11)' in check.stdout:
        subprocess.run(prefix+['-m','venv',str(root/'.venv-voice')],check=True)
        break
else:
    print('Python 3.11 not installed. Install Python 3.11, then run this again.',file=sys.stderr)
    sys.exit(1)
