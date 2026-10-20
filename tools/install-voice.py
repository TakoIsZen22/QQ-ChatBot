import subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
python=str(root/'.venv-voice/Scripts/python.exe')
lock=root/'requirements.voice.lock.txt'
torch='torch'
if lock.exists():torch=next((s.strip() for s in lock.read_text(encoding='utf-8-sig').splitlines() if s.startswith('torch==')),torch)
subprocess.run([python,'-m','pip','install',torch,'--index-url','https://download.pytorch.org/whl/cpu'],check=True)
subprocess.run([python,'-m','pip','install',*(['-r',str(lock)] if lock.exists() else ['openai-whisper','scipy'])],check=True)
