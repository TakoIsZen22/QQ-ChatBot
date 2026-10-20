"""Agent 无关的只读巡检：只读状态与端口，不读聊天、密钥或登录态。"""
import json
import socket
import urllib.request
from datetime import datetime
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo
from .config import load
from .model_endpoint import probe_port
from .product import is_harness
from ..version import VERSION


def collect(cfg=None):
    cfg = cfg or load()
    def port(number):
        try:
            with socket.create_connection(('127.0.0.1', number), timeout=.3):
                return True
        except OSError:
            return False
    checks = {'harness': port(cfg['server']['port']), 'model_api': probe_port(cfg['model'])}
    if cfg['model']['provider']=='magpie':checks['magpie']=checks['model_api']
    if cfg['qq']['enabled']:
        checks['qq_native']=port(cfg['qq']['native_port'])
    status = {}
    if checks['harness']:
        try:
            url = f'http://127.0.0.1:{cfg["server"]["port"]}/api/status'
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(url, timeout=3) as response:
                raw = response.read(65537)
            if len(raw) > 65536:
                raise ValueError('status too large')
            value = json.loads(raw)
            if not is_harness(value):
                raise ValueError('wrong application')
            for key in ('mode','groups_muted','busy','queue','memory_count','last_spoke'):
                if key in value:
                    status[key] = value[key]
            if cfg['qq']['enabled']:
                checks['qq_online'] = value.get('qq_connected') is True and value.get('qq_online') is True
            checks['status_api'] = True
        except Exception:
            checks['status_api'] = False
    else:
        checks['status_api'] = False
    return {'schema':'dafeiyu.supervision.v1', 'version':VERSION,
            'generated_at':datetime.now(ZoneInfo(cfg['awakening']['timezone'])).isoformat(),
            'maintainer':cfg['maintenance']['agent_name'],
            'overall':'healthy' if all(checks.values()) else 'degraded',
            'checks':checks, 'status':status,
            'limits':['只查端口和状态，不代表模型推理成功','安静、暂停或从未说话不单独判为故障']}
