import json
import sys
for line in sys.stdin:
    req=json.loads(line)
    if 'id' not in req:continue
    result={'protocolVersion':'2024-11-05','capabilities':{'tools':{}},'serverInfo':{'name':'fixture','version':'1'}} if req['method']=='initialize' else {'content':[{'type':'text','text':req['params']['arguments']['text']}]}
    print(json.dumps({'jsonrpc':'2.0','id':req['id'],'result':result}),flush=True)
