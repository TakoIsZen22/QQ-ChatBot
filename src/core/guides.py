"""固定白名单的公开帮助文档；不访问配置、私人文件或网络。"""
import base64
from pathlib import Path

GUIDES={'agent':('CLI 与桌面 Agent 工作转交教程','docs/AGENT_WORK.md',None),
        'start':('QQ ChatBot 新手使用教程','docs/GETTING_STARTED.md',None),
        'magpie':('Magpie 接入教程（可选）','docs/MAGPIE_SETUP.md','docs/assets/magpie-quickstart.svg'),
        'api':('自有 API 接入说明','docs/MODEL_API.md',None)}


def read_guide(root,name):
    if not isinstance(name,str) or name not in GUIDES:raise ValueError('未知帮助文档')
    root=Path(root).resolve();title,document,illustration=GUIDES[name]
    def read(relative):
        path=(root/relative).resolve()
        if not path.is_relative_to(root/'docs') or path.stat().st_size>131072:raise ValueError('帮助文档路径或大小无效')
        return path.read_bytes()
    return {'title':title,'text':read(document).decode('utf-8-sig').replace('\r\n','\n').replace('\r','\n'),
            'image_data':'data:image/svg+xml;base64,'+base64.b64encode(read(illustration)).decode() if illustration else None,
            'file_target':{'agent':'agent_work_guide','start':'getting_started','magpie':'magpie_guide','api':'model_api_guide'}[name]}
