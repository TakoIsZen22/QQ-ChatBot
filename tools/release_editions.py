"""Derive each edition only from privacy-checked source, never from local settings."""
import json
import re
import zipfile
from pathlib import Path

VERSIONS = ('1.00.01', '1.00.02')


def prepare_edition(archive, destination, version):
    if version not in VERSIONS:
        raise ValueError('未知发行版本')
    destination = Path(destination).resolve()
    if destination.exists():
        raise FileExistsError('发行源码目录已存在，不覆盖')
    with zipfile.ZipFile(archive) as bundle:
        entries = []
        for item in bundle.infolist():
            parts = item.filename.split('/')
            if len(parts)<2 or any(p in ('', '.', '..') or ':' in p or '\\' in p for p in parts):
                raise ValueError('无效源码包路径')
            relative = Path(*parts[1:])
            if relative.as_posix() == 'manifest.json':
                continue
            target = destination/relative
            if not target.resolve().is_relative_to(destination):
                raise ValueError('源码包越界')
            entries.append((item,target))
        destination.mkdir(parents=True)
        for item,target in entries:
            target.parent.mkdir(parents=True,exist_ok=True)
            target.write_bytes(bundle.read(item))
    (destination/'src/version.py').write_text(f"VERSION = '{version}'\n",encoding='utf-8')
    api_only = version == '1.00.01'
    for name in ('config/settings.json','config/local.example.json'):
        path=destination/name
        cfg=json.loads(path.read_text(encoding='utf-8-sig'))
        cfg.setdefault('model',{}).update(
            provider='openai_compatible' if api_only else 'magpie',
            base_url='' if api_only else 'http://127.0.0.1:3425/v1',
            key_env='HARNESS_API_KEY' if api_only else 'MAGPIE_API_KEY',main='',auxiliary='')
        path.write_text(json.dumps(cfg,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    if api_only:
        for name in ('src/channel/ui/desktop/index.html','src/channel/ui/desktop/onboarding.js'):
            path=destination/name
            text=path.read_text(encoding='utf-8')
            text=re.sub(r'<option value="magpie">[^<]*</option>','',text)
            text=re.sub(r'<button\b[^>]*data-guide="magpie"[^>]*>.*?</button>','',text)
            text=re.sub(r'<button\b[^>]*id="guide-official"[^>]*>.*?</button>',
                        '<button id="guide-official" type="button" hidden></button>',text)
            for old,new in (
                ('选择 Magpie 或直接接入你自己的 OpenAI 兼容 API。','接入你自己的 OpenAI 兼容 API。'),
                ('模型可用 Magpie 或自己的 OpenAI 兼容 API。','模型使用你自己的 OpenAI 兼容 API。'),
                ('Windows 用户环境变量或 Magpie','Windows 用户环境变量'),
                ('密钥由你在 Magpie 或系统环境中配置。','密钥由你在系统环境中配置。'),
                ('<code id="model-gateway-address">http://127.0.0.1:3425/v1</code>',
                 '<code id="model-gateway-address">尚未填写 API 地址</code>')):
                text=text.replace(old,new)
            path.write_text(text,encoding='utf-8')
        for name in ('docs/MAGPIE_SETUP.md','docs/assets/magpie-quickstart.svg'):
            (destination/name).unlink(missing_ok=True)
        # The API-only package links to the edition comparison instead of an absent guide.
        for path in [destination/'README.md',*(destination/'docs').glob('*.md')]:
            text=path.read_text(encoding='utf-8')
            text=text.replace('(docs/MAGPIE_SETUP.md)','(docs/EDITIONS.md)').replace('(MAGPIE_SETUP.md)','(EDITIONS.md)')
            path.write_text(text,encoding='utf-8')
    label='自有 API 版' if api_only else 'API + Magpie 版'
    for name in ('README.md','HANDOFF.md','docs/GETTING_STARTED.md','docs/MODEL_API.md'):
        path=destination/name
        text=path.read_text(encoding='utf-8')
        first,separator,body=text.partition('\n')
        path.write_text(first+'\n\n'+f'当前发行：**{version} · {label}**。'+
                        ('仅支持自有 OpenAI 兼容 API；没有 Magpie 接入入口。' if api_only else '支持自有 API 与可选 Magpie；不内置 Magpie 软件。')+
                        '\n'+body,encoding='utf-8')
    return destination
