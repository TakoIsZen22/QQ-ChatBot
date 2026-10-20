"""可选 Python 3.11 环境执行。音频只传给本机 whisper，不走网络转写。"""
import json
import os
import sys
os.environ['PYTHONIOENCODING'] = 'utf-8'
sys.stdout.reconfigure(encoding='utf-8')
import whisper
import wave
import numpy as np
import torch
torch.set_num_threads(int(sys.argv[5]) if len(sys.argv)>5 else 2)
model = whisper.load_model(sys.argv[2],download_root=sys.argv[4] if len(sys.argv)>4 else None)
try:
    # 本机 PCM wav 的16k单声道可直接进入 whisper，无需 ffmpeg。
    with wave.open(sys.argv[1],'rb') as wav:
        if wav.getsampwidth()!=2:raise ValueError('非16bit PCM')
        rate=wav.getframerate();channels=wav.getnchannels();pcm=wav.readframes(wav.getnframes())
    audio=np.frombuffer(pcm,dtype=np.int16).astype(np.float32).reshape(-1,channels).mean(axis=1)/32768.0
    if rate!=16000:
        # polyphase 滤波重采样（可选 scipy）；没有则按 ffmpeg 路径明确报依赖错误。
        from scipy.signal import resample_poly
        from math import gcd
        divisor=gcd(rate,16000)
        audio=resample_poly(audio,16000//divisor,rate//divisor)
except (wave.Error,ValueError,ImportError):
    audio=whisper.load_audio(sys.argv[1])
result = model.transcribe(audio, language=sys.argv[3], fp16=False,initial_prompt=sys.argv[6] if len(sys.argv)>6 else None)
print(json.dumps({'text':result['text']}, ensure_ascii=False))
