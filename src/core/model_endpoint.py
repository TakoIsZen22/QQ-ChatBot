"""模型出口配置与无凭据的 TCP 检查；所有推理仍通过同一个 Model 适配层。"""
import ipaddress
import re
import socket
from urllib.parse import urlsplit

MAGPIE_URL='http://127.0.0.1:3425/v1'


def endpoint(cfg, *, allow_unconfigured=False):
    provider=cfg.get('provider','magpie')
    if provider not in ('magpie','openai_compatible'):raise ValueError('请选择 Magpie 或自定义 OpenAI 兼容 API')
    from .edition import require_provider
    require_provider(provider)
    url=cfg.get('base_url')
    if url=='' and provider=='openai_compatible':
        if not re.fullmatch(r'[A-Z_][A-Z0-9_]*',str(cfg.get('key_env',''))):raise ValueError('key_env 只能填环境变量名称')
        if allow_unconfigured and not cfg.get('main') and not cfg.get('auxiliary'):return ''
        raise ValueError('尚未填写 API Base URL，请在模型设置中配置')
    if not isinstance(url,str) or not url or len(url)>2048 or any(c.isspace() or ord(c)<32 for c in url) or '\\' in url:
        raise ValueError('API Base URL 格式无效')
    try:
        parsed=urlsplit(url);port=parsed.port;host=parsed.hostname
    except ValueError:raise ValueError('API Base URL 的主机或端口无效') from None
    if parsed.scheme not in ('https','http') or not host or parsed.username is not None or parsed.password is not None or '?' in url or '#' in url:
        raise ValueError('API 地址仅允许 HTTP/HTTPS，不得含账号、密码、查询参数或 fragment')
    if port is not None and not 1<=port<=65535:raise ValueError('API 端口无效')
    if provider=='magpie' and url.rstrip('/')!=MAGPIE_URL:raise ValueError('Magpie 模式使用固定本机地址；其他地址请选择自定义 API')
    if parsed.scheme=='http':
        loopback=host.lower()=='localhost'
        try:loopback=loopback or ipaddress.ip_address(host).is_loopback
        except ValueError:pass
        if not loopback:raise ValueError('远程 API 请使用 HTTPS；HTTP 仅支持本机回环地址')
    if parsed.path.rstrip('/').endswith(('/chat/completions','/models','/responses')):
        raise ValueError('请填写 API Base URL，不要包含 chat/completions、models 或 responses 路径')
    if not isinstance(cfg.get('key_env'),str) or not re.fullmatch(r'[A-Z_][A-Z0-9_]*',cfg['key_env']):
        raise ValueError('key_env 只能填环境变量名称，不能填 API 密钥')
    return url.rstrip('/')


def label(cfg):return 'Magpie' if cfg.get('provider','magpie')=='magpie' else '自定义 API'


def probe_port(cfg,timeout=.5):
    address=endpoint(cfg,allow_unconfigured=True)
    if not address:return False
    url=urlsplit(address)
    try:
        with socket.create_connection((url.hostname,url.port or (443 if url.scheme=='https' else 80)),timeout=timeout):return True
    except OSError:return False
