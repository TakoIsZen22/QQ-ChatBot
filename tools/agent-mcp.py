"""供桌面Agent配置的stdio MCP入口，不主动启动/操控任何Agent。"""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from src.core.agent_mcp import main
if __name__=='__main__':main()
