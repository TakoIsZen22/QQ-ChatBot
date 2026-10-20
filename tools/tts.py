"""Windows 自带 System.Speech 离线 TTS；文字通过 stdin JSON，绝不拼进 PowerShell 代码。"""
import json
import subprocess
import sys
from pathlib import Path

SCRIPT=r'''
$ErrorActionPreference='Stop'
[Console]::InputEncoding=[System.Text.UTF8Encoding]::new($false)
[Console]::OutputEncoding=[System.Text.UTF8Encoding]::new($false)
$payload=[Console]::In.ReadToEnd() | ConvertFrom-Json
Add-Type -AssemblyName System.Speech
$speaker=[System.Speech.Synthesis.SpeechSynthesizer]::new()
try {
    $voices=$speaker.GetInstalledVoices() | Where-Object {$_.Enabled -and $_.VoiceInfo.Culture.Name -like 'zh-*'}
    if (-not $voices) {throw 'No installed Chinese System.Speech voice. Install a Windows Chinese speech voice first.'}
    $speaker.SelectVoice(($voices | Select-Object -First 1).VoiceInfo.Name)
    $format=[System.Speech.AudioFormat.SpeechAudioFormatInfo]::new(16000,[System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen,[System.Speech.AudioFormat.AudioChannel]::Mono)
    $speaker.SetOutputToWaveFile($payload.output,$format)
    $speaker.Speak($payload.text)
} finally {$speaker.Dispose()}
'''

def main():
    if len(sys.argv)!=3:raise ValueError('用法: python tools/tts.py 文本 输出.wav')
    output=Path(sys.argv[2]).resolve()
    if output.suffix.lower()!='.wav':raise ValueError('输出必须为 wav')
    output.parent.mkdir(parents=True,exist_ok=True)
    result=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',SCRIPT],input=json.dumps({'text':sys.argv[1],'output':str(output)},ensure_ascii=False).encode('utf-8'),stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120)
    if result.returncode:raise RuntimeError(result.stderr.decode('utf-8',errors='replace'))

if __name__=='__main__':
    try:main()
    except Exception as e:print(str(e),file=sys.stderr);sys.exit(1)
