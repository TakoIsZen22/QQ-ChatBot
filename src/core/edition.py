"""Build identity and model-provider capabilities, derived from the release version."""
import re
from ..version import VERSION

EDITIONS={
    '01':{'id':'api_only','name':'自有 API 版','providers':['openai_compatible']},
    '02':{'id':'api_magpie','name':'API + Magpie 版','providers':['openai_compatible','magpie']},
}

def release_versions(version):
    """The final two digits select providers, never the feature revision."""
    if not isinstance(version,str) or not re.fullmatch(r'[0-9]+\.[0-9]+\.(01|02)',version):
        raise ValueError('发行版本必须为 主版本.功能版本.01 或 .02')
    family=version.rsplit('.',1)[0]
    return (family+'.01',family+'.02')


def capabilities():
    release_versions(VERSION)
    value=EDITIONS[VERSION.rsplit('.',1)[1]]
    return {'version':VERSION,'id':value['id'],'name':value['name'],'providers':list(value['providers'])}

def require_provider(provider):
    if provider not in capabilities()['providers']:
        raise ValueError('此版本只支持自有 OpenAI 兼容 API；需要 Magpie 接入请使用 '+release_versions(VERSION)[1])
