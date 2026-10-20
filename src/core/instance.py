import os
from pathlib import Path

class InstanceLock:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.file=open(path,'a+b')
        self.file.seek(0)
        if os.name=='nt':
            import msvcrt
            if Path(path).stat().st_size==0:
                self.file.write(b'0');self.file.flush()
            self.file.seek(0)
            try:
                msvcrt.locking(self.file.fileno(),msvcrt.LK_NBLCK,1)
            except OSError:
                self.file.close()
                raise RuntimeError('同一数据目录已有进程运行；请先停止，不能双开')
        else:
            import fcntl
            fcntl.flock(self.file.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)

    def close(self):
        self.file.close()
