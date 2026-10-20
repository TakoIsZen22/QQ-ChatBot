"""Build identity and model-provider capabilities, derived from the release version."""
from ..version import VERSION

EDITIONS={
    '1.00.01':{'id':'api_only','name':'自有 API 版','providers':['openai_compatible']},
    '1.00.02':{'id':'api_magpie','name':'API + Magpie 版','providers':['openai_compatible','magpie']},
}

def capabilities():
    value=EDITIONS.get(VERSION,EDITIONS['1.00.02'])
    return {'version':VERSION,'id':value['id'],'name':value['name'],'providers':list(value['providers'])}

def require_provider(provider):
    if provider not in capabilities()['providers']:
        raise ValueError('此版本只支持自有 OpenAI 兼容 API；需要 Magpie 接入请使用 1.00.02')
