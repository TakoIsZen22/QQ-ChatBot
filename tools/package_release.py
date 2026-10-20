"""按白名单生成无本机状态、无Git历史的可分发源码包。"""
import hashlib
import json
import re
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {'README.md','HANDOFF.md','AGENTS.md','LICENSE','NOTICE.md','CHANGELOG.md',
              '架构文档.md','QQ ChatBot.vbs','.gitignore'}
TEXT_SUFFIXES = {'.py','.md','.json','.js','.html','.css','.ps1','.bat','.vbs','.txt','.yml','.yaml','.cs'}
TREE_SUFFIXES = {'.py','.md','.json','.js','.html','.css','.ps1','.bat','.vbs','.txt'}
PUBLIC_ASSETS = {'assets/README.md','assets/xiaojing-user-icon.png','assets/xiaojing-user-icon.ico',
         'assets/qq-chatbot-fish-chat-v1.png','assets/qq-chatbot-fish-chat-v1.ico','assets/qq-chatbot-fish-chat-v1.prompt.md',
         'src/channel/ui/icons/xiaojing-user-icon.png','src/channel/ui/icons/xiaojing-user-icon.ico',
         'src/channel/ui/desktop/assets/xiaojing-user-icon.png','src/channel/ui/desktop/assets/xiaojing-user-icon.ico',
         'docs/assets/magpie-quickstart.svg'}


def version(root):
    text = (root/'src/version.py').read_text(encoding='utf-8')
    match = re.fullmatch(r"\s*VERSION\s*=\s*['\"]([0-9]+\.[0-9]+\.[0-9]+)['\"]\s*", text)
    if not match:
        raise ValueError('src/version.py 版本格式无效')
    return match[1]


def candidates(root):
    result = []
    extras={'config/runtime-downloads.json','.github/workflows/windows-release.yml','tools/portable-launcher.cs'}
    paths = {root/name for name in ROOT_FILES | PUBLIC_ASSETS | extras | {'config/settings.json','config/local.example.json','user_plugins/impression_example.py'}}
    paths.update(root.glob('requirements*.txt'))
    for folder in ('src','tools','tests','docs'):
        paths.update((root/folder).rglob('*'))
    for path in sorted(paths):
        rel = path.relative_to(root)
        name = rel.as_posix()
        # 不读取被排除目录/文件的内容，也不跟随链接打包项目之外的文件。
        if name not in extras and any(part.startswith('.') or part in ('__pycache__','data','logs','backups','dist') for part in rel.parts[:-1]):
            continue
        if not path.is_file() or path.is_symlink() or not path.resolve().is_relative_to(root):
            continue
        if '.local.' in path.name or path.name in ('local.json','.env') or path.name.casefold()=='soul.md':
            continue
        allowed = name in ROOT_FILES or (len(rel.parts)==1 and path.name.startswith('requirements') and path.suffix=='.txt')
        allowed |= name in ('config/settings.json','config/local.example.json','user_plugins/impression_example.py') or name in PUBLIC_ASSETS or name in extras
        allowed |= rel.parts[0] in ('src','tools','tests','docs') and path.suffix in TREE_SUFFIXES
        if allowed:
            result.append((path,name))
    return result


def private_markers(root):
    # 用本机字段做额外泄漏检查，只输出文件名，从不回显实际字段。
    path = root/'config/local.json'
    if not path.exists():
        return []
    cfg = json.loads(path.read_text(encoding='utf-8-sig'))
    markers = [str(cfg.get('owner',{}).get('qq_id','')),str(cfg.get('qq',{}).get('bot_id',''))]
    name = cfg.get('owner',{}).get('name','')
    if name and name not in ('你','主人','用户','朋友'):
        markers.append(name)
    markers.extend((str(root),str(Path.home())))
    return [s for s in markers if len(s)>=2]


def build_release(root=ROOT, output=None):
    root = Path(root).resolve()
    release_version = version(root)
    cfg = json.loads((root/'config/settings.json').read_text(encoding='utf-8-sig'))
    from src.core.config import validate
    validate(cfg)
    if cfg['owner']['name']!='你' or cfg['maintenance']['agent_name']!='维护 Agent':
        raise ValueError('公开默认配置必须使用通用称呼与维护者名称')
    if cfg['owner']['qq_id'] or cfg['qq']['bot_id'] or cfg['qq']['enabled'] or cfg['model']['main'] or cfg['model']['auxiliary']:
        raise ValueError('公开默认配置必须保持账号/模型为空且 QQ 关闭')
    if cfg['safety']['mode']!='paused' or not cfg['safety']['groups_muted']:
        raise ValueError('公开默认配置必须暂停且群静默，由新用户手动开启回复')
    if cfg['agent_link']['enabled'] or cfg['agent_link']['command'] or cfg['agent_link']['cwd'] or cfg['agent_link']['name']!='工作 Agent':
        raise ValueError('公开包不得包含私人 Agent 命令、路径或已启用绑定')
    if cfg['role']['card']!='src/persona/role.md':
        raise ValueError('公开默认配置必须使用通用人设')
    if cfg['model']['provider']!='magpie' or cfg['model']['base_url']!='http://127.0.0.1:3425/v1':
        raise ValueError('公开包默认使用 Magpie；自定义 API 地址必须保留在本机配置')
    if cfg['identity']['default_nickname']!='大肥鱼':
        raise ValueError('公开默认角色昵称必须使用通用名称；个人自定义应保存在 data')
    if any(cfg[group]['enabled'] for group in ('awakening','music','devices','voice','learning','plugins')) or cfg['music']['allow_control'] or cfg['role']['evolution_enabled']:
        raise ValueError('公开默认配置必须关闭可选高权限能力')
    markers = private_markers(root)
    entries = candidates(root)
    required = ROOT_FILES | {'config/settings.json','config/local.example.json','src/version.py','src/persona/role.md'}
    if required - {name for _,name in entries}:
        raise ValueError('缺少发布必需文件: '+', '.join(sorted(required - {name for _,name in entries})))
    files = {}
    for path,name in entries:
        raw = path.read_bytes()
        if path.suffix in TEXT_SUFFIXES or name in ROOT_FILES:
            text = raw.decode('utf-8-sig')
            if any(marker in text for marker in markers):
                raise ValueError('发现本机个人字段或路径，请先清理公开文件: '+name)
            if re.search(r'\bsk-[A-Za-z0-9_-]{20,}\b|-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----', text):
                raise ValueError('发现疑似凭据，未生成发布包: '+name)
        files[name] = raw
    output = Path(output) if output else root/'dist'/f'qq-chatbot-{release_version}.zip'
    if output.exists():
        raise FileExistsError('发布包已存在，选择新输出路径或先保留旧包')
    # 先完成全部校验才创建输出，绝不写入私有数据目录。
    resolved = output.resolve()
    if any(resolved.is_relative_to(root/folder) for folder in ('data','logs','backups','config','src','.runtime','.git')):
        raise ValueError('发布包输出不能放在私有数据或源码目录内')
    output.parent.mkdir(parents=True,exist_ok=True)
    manifest = {'schema':'dafeiyu.source-release.v1','version':release_version,
                'files':{name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()}}
    prefix = f'qq-chatbot-{release_version}/'
    with zipfile.ZipFile(output,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for name,raw in files.items():
            archive.writestr(prefix+name,raw)
        archive.writestr(prefix+'manifest.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    # 源码包同样给出校验文件，和 Windows 绿色包保持一致。
    # 用 LF 换行，Windows 的 write_text 默认会写 CRLF，导致 sha256sum -c 失败。
    output.with_suffix('.zip.sha256').write_bytes((digest+'  '+output.name+'\n').encode('ascii'))
    return {'path':str(output.resolve()),'version':release_version,'files':len(files),
            'sha256':digest}
