import json

def schema(name, description, properties, required=()):
    return {'type':'function','function':{'name':name,'description':description,'parameters':{'type':'object','properties':properties,'required':list(required),'additionalProperties':False}}}

TOOLS = [
    schema('memory_query','查询主人长期记忆；查不到不要编造',{'query':{'type':'string'}},['query']),
    schema('memory_append','仅记未来有用的已确认事实，不保存秘密',{'content':{'type':'string'},'category':{'type':'string','enum':['knowledge','relationship','work','weights','multimodal','reflection']},'importance':{'type':'string','enum':['normal','important','permanent']}},['content']),
    schema('memory_remove','将已过时的记忆标记删除',{'memory_id':{'type':'string'}},['memory_id']),
    schema('diary_append','写一两句具体日记，每日不超过三条',{'text':{'type':'string'}},['text']),
    schema('diary_recent','看最近几条日记',{'count':{'type':'integer'}}),
    schema('emotion_set','记下有原因和时长的心情；不影响正事',{'state':{'type':'string'},'reason':{'type':'string'},'duration_hours':{'type':'number'}},['state','reason']),
    schema('promise_add','记录主人明确提到的约定；时间必须含时区，不要擅自许诺',{'text':{'type':'string'},'due':{'type':'string'}},['text','due']),
    schema('list_stickers','查询已观察并收藏的表情包、备注和使用次数',{}),
    schema('sticker_note','补充已收藏表情的含义',{'sticker_id':{'type':'string'},'note':{'type':'string'},'tags':{'type':'array','items':{'type':'string'}}},['sticker_id','note']),
    schema('collect_sticker','仅收藏本轮已视觉观察的主人图片，别频繁偷图',{'media_id':{'type':'string'},'note':{'type':'string'}},['media_id','note']),
    schema('send_sticker','排队发送一张独立表情气泡；严肃/道歉/表白场景不可用',{'sticker_id':{'type':'string'}},['sticker_id'])
]

class ToolDispatcher:
    def __init__(self, harness):
        self.h = harness

    def execute(self, name, arguments, generation):
        h = self.h
        if not h.safety.allowed(generation=generation):
            raise PermissionError('安全状态已改变，本轮工具取消')
        a = json.loads(arguments) if isinstance(arguments,str) else arguments
        if not isinstance(a,dict):
            raise ValueError('工具参数必须为对象')
        if name == 'memory_query': return h.memory.query(h.person,**a)
        if name == 'memory_append': return h.memory.append(h.person,source='model_from_conversation',**a)
        if name == 'memory_remove': return h.memory.remove(h.person,**a)
        if name == 'diary_append': return h.diary.append(**a)
        if name == 'diary_recent': return h.diary.recent(**a)
        if name == 'emotion_set': return h.role.emotion(**a)
        if name == 'promise_add': return h.awakening.promise(**a)
        if name == 'list_stickers': return h.stickers.list()
        if name == 'sticker_note': return h.stickers.note(**a)
        if name == 'collect_sticker': return h.stickers.collect(**a)
        if name == 'send_sticker':
            if h.sticker_pending or h.serious_turn:raise PermissionError('每轮最多一张，严肃场景不发表情')
            h.sticker_pending.append(a['sticker_id'])
            return {'queued':True}
        raise PermissionError('工具不在模型权限白名单')
