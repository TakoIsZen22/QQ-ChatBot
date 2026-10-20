import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def merge(a, b):
    if not isinstance(b,dict):raise ValueError('配置覆盖必须是对象')
    for k, v in b.items():
        if k not in a:raise ValueError(f'未知配置: {k}')
        if isinstance(v,dict) and isinstance(a[k],dict):merge(a[k],v)
        else:a[k]=v

def load(path=None):
    base = json.loads((ROOT / 'config/settings.json').read_text(encoding='utf-8-sig'))
    local = Path(path) if path else ROOT / 'config/local.json'
    if local.exists():
        merge(base, json.loads(local.read_text(encoding='utf-8-sig')))
    validate(base)
    return copy.deepcopy(base)

def save_local(patch):
    candidate=load()
    # 凭据永远只允许外部环境变量；配置里只有变量名。
    merge(candidate,patch)
    validate(candidate)
    path=ROOT/'config/local.json'
    local=json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else {}
    def overlay(a,b):
        for k,v in b.items():
            if isinstance(v,dict):overlay(a.setdefault(k,{}),v)
            else:a[k]=v
    overlay(local,patch)
    temp=path.with_suffix('.tmp')
    temp.write_text(json.dumps(local,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    temp.replace(path)
    return candidate

def validate(c):
    import re
    import math
    def finite(value):
        if isinstance(value,float) and not math.isfinite(value):raise ValueError('配置数字不能是 NaN/Infinity')
        if isinstance(value,dict):
            for v in value.values():finite(v)
        if isinstance(value,list):
            for v in value:finite(v)
    finite(c)
    from .agent_link import validate_binding
    validate_binding(c['agent_link'])
    identity=c['identity']
    for key,maximum in (('max_nickname_chars',80),('max_appearance_chars',12000),('max_image_bytes',2097152),('max_pixels',32000000),('portrait_edge',2048),('icon_edge',256)):
        if type(identity[key]) is not int or not 1<=identity[key]<=maximum:raise ValueError('角色定制限制无效: '+key)
    if not isinstance(identity['default_nickname'],str) or not identity['default_nickname'].strip() or len(identity['default_nickname'])>identity['max_nickname_chars']:raise ValueError('默认昵称无效')
    for key in ('stream','asset_dir','default_image','default_icon_ico'):
        value=identity[key]
        if not isinstance(value,str) or not value or Path(value).is_absolute() or '..' in Path(value).parts:raise ValueError('角色素材路径必须在项目/数据目录内')
    for key,suffix in (('default_image','.png'),('default_icon_ico','.ico')):
        path=Path(identity[key])
        if path.parts[0]!='assets' or path.suffix.lower()!=suffix:raise ValueError('默认角色素材必须是 assets 内的 PNG/ICO')
    if not isinstance(identity['ico_sizes'],list) or not identity['ico_sizes'] or len(identity['ico_sizes'])>10 or any(type(n) is not int or not 1<=n<=identity['icon_edge'] for n in identity['ico_sizes']):raise ValueError('ICO 尺寸无效')
    role=c['role'];soul_path=Path(role['soul_file'])
    if soul_path.is_absolute() or soul_path.name!='soul.md' or '..' in soul_path.parts:raise ValueError('role.soul_file 必须为 data 内的相对 soul.md 路径')
    for key,maximum in (('soul_max_chars',50000),('soul_max_bytes',262144),('soul_history_limit',100)):
        if type(role[key]) is not int or not 1<=role[key]<=maximum:raise ValueError('专属人设大小/历史限制无效: '+key)
    for label,value,limit in (('主人称呼',c['owner']['name'],40),('维护 Agent 名称',c['maintenance']['agent_name'],80)):
        if not isinstance(value,str) or not value.strip() or len(value)>limit or any(ord(ch)<32 for ch in value):raise ValueError(label+'必须为非空单行短文本')
    if c['qq']['enabled'] and (not str(c['qq']['bot_id']).isdigit() or str(c['qq']['bot_id'])==str(c['owner']['qq_id'])):
        raise ValueError('启用 QQ 需要与主人不同的机器人 QQ 号')
    d=c['desktop']
    for name in ('start_with_windows','startup_hidden','auto_start_services','close_to_tray','minimize_to_tray','auto_recover'):
        if type(d[name]) is not bool:raise ValueError('程序开关必须是布尔值: '+name)
    if d['theme'] not in ('system','light','dark') or d['font_scale'] not in (1.0,1.1,1.25):raise ValueError('程序主题/字号无效')
    if not 940<=d['window_width']<=7680 or not 650<=d['window_height']<=4320:raise ValueError('程序窗口尺寸无效')
    if d['supervisor_interval_seconds']<2 or not 1<=d['max_auto_restarts']<=10 or d['restart_window_seconds']<60 or d['maintenance_timeout_seconds']<10:raise ValueError('程序恢复/维护参数无效')
    stickers=c['stickers']
    for name in ('max_image_bytes','max_pixels','preview_edge','animation_samples','max_animation_frames','library_limit','max_images_per_turn'):
        if not isinstance(stickers[name],int) or stickers[name]<=0:raise ValueError('表情理解大小/采样/条数限制必须为正整数')
    if stickers['preview_edge']>2048 or stickers['animation_samples']>3 or stickers['library_limit']>200:raise ValueError('表情理解预览/采样/条数超出上限')
    if stickers['max_images_per_turn']>10 or c['qq']['media_timeout_seconds']<=0:raise ValueError('聊天图片数量/超时参数无效')
    if not isinstance(c['qq']['media_hosts'],list) or any(not isinstance(host,str) or not re.fullmatch(r'[a-z0-9.-]+',host) for host in c['qq']['media_hosts']):raise ValueError('QQ图片CDN必须填写精确域名，不能包含通配符或URL')
    if d['poll_interval_ms']<250 or min(d['request_timeout_seconds'],d['start_timeout_seconds'],d['stop_timeout_seconds'],d['qr_max_age_seconds'])<=0:raise ValueError('桌面端轮询/超时参数无效')
    if not isinstance(c['server']['port'],int) or not 1024<=c['server']['port']<=65535 or c['server']['port']==3425:raise ValueError('本机 UI 端口无效或与 Magpie 冲突')
    for name in (c['model']['key_env'],c['qq']['token_env']):
        if not re.fullmatch(r'[A-Z_][A-Z0-9_]*',name):raise ValueError('key_env/token_env 只能填环境变量名称，不能填密钥')
    from .model_endpoint import endpoint
    endpoint(c['model'])
    if c['server']['host'] != '127.0.0.1':
        raise ValueError('管理界面只允许绑定 127.0.0.1')
    from urllib.parse import urlsplit
    for name in ('http_url', 'ws_url'):
        u = urlsplit(c['qq'][name])
        if u.hostname != '127.0.0.1' or u.username or u.password or u.query or u.fragment or u.scheme not in ('http', 'ws'):
            raise ValueError('OneBot 必须是无凭据的本机 HTTP/WS 地址')
    s = c['safety']
    if s['mode'] not in ('paused', 'reply_only', 'active'):
        raise ValueError('safety.mode 无效')
    if not 1 <= s['private_per_minute'] <= 20 or not 1 <= s['group_per_minute'] < s['private_per_minute']:
        raise ValueError('QQ 限流必须单聊 <=20，群更慢')
    if s['irreversible_interval_seconds'] < 600 or not 1 <= s['irreversible_per_day'] <= 3:
        raise ValueError('不可撤回操作限流不允许放宽')
    if not 1 <= c['diary']['daily_limit'] <= 3:
        raise ValueError('日记每天最多三条')
    if c['qq']['enabled'] and not str(c['owner']['qq_id']).isdigit():
        raise ValueError('启用 QQ 前填写 owner.qq_id')
    a = c['awakening']
    if not 0 <= a['probability'] <= 1 or not 0 < a['min_minutes'] <= a['max_minutes']:
        raise ValueError('主动概率或间隔无效')
    h = c['conversation']
    if not 0 <= h['min_delay_seconds'] <= h['max_delay_seconds'] or not 1 <= h['max_bubbles'] <= 10:
        raise ValueError('拟人嘴参数无效')
    if h['bubble_chars']<10 or h['queue_size']<1 or h['max_input_chars']<1:raise ValueError('对话长度/队列参数无效')
    if c['memory']['short_half_life_days']<=0 or c['memory']['important_half_life_days']<=0:raise ValueError('记忆半衰期必须大于零')
    if c['model']['timeout_seconds']<=0 or not 1<=c['model']['max_tool_rounds']<=10 or c['model']['history_messages']<1:raise ValueError('模型参数无效')
    if not 1<=c['model']['models_timeout_seconds']<=60 or type(c['model']['max_response_bytes']) is not int or not 1024<=c['model']['max_response_bytes']<=16777216:raise ValueError('模型清单超时/响应大小限制无效')
    if not 0<=a['quiet_start']<=23 or not 0<=a['quiet_end']<=23 or not 0<=a['sleep_hour']<=23 or a['idle_minutes']<1:raise ValueError('时间感参数无效')
    from zoneinfo import ZoneInfo
    ZoneInfo(a['timezone'])
    roots=[]
    for p in c['paths'].values():
        resolved = (ROOT / p).resolve()
        if not resolved.is_relative_to(ROOT) or resolved == ROOT:
            raise ValueError('数据目录必须在项目内的子目录')
        if any(resolved.is_relative_to(ROOT/name) or (ROOT/name).is_relative_to(resolved) for name in ('src','tools','config','tests','docs','user_plugins','.venv')):raise ValueError('数据路径不能与代码/配置/环境目录重叠')
        if any(resolved.is_relative_to(other) or other.is_relative_to(resolved) for other in roots):raise ValueError('data/logs/backups 必须互不嵌套，防止备份递归')
        roots.append(resolved)
