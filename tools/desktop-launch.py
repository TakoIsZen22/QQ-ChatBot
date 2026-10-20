"""绝对路径入口：Windows登录时不依赖工作目录或PATH。"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.desktop import main
if __name__=='__main__':main()
