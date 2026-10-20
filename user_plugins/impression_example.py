"""可信本机代码示例。插件不是沙箱，启用等于信任其全部 Python 代码。"""
def score(messages, current):
    return {'affinity':current['affinity'], 'text':'最近关注：'+(messages[-1]['content'][:50] if messages else '等待新的聊天')}
