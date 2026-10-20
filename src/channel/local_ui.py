import asyncio
import json
import traceback
from pathlib import Path
from aiohttp import web
from ..core.config import ROOT,load,save_local
from ..core.service_intent import ServiceIntent

def build(h,shutdown):
    origin=f'http://127.0.0.1:{h.cfg["server"]["port"]}'
    @web.middleware
    async def security(request,handler):
        # Host 防 DNS rebinding；浏览器跨域不能读取或写入，CLI 写入需显式头。
        if request.host != origin.removeprefix('http://'):
            return web.json_response({'error':'Host 必须为 '+origin},status=403)
        if request.headers.get('Origin') not in (None,origin):
            return web.json_response({'error':'拒绝跨域请求'},status=403)
        if request.method != 'GET' and request.headers.get('X-Harness-Local') != '1':
            return web.json_response({'error':'本机操作缺少 X-Harness-Local: 1'},status=403)
        tracked=request.path in ('/api/music','/api/device','/api/study','/api/mcp','/api/transcribe','/api/sticker-intents','/api/model-connection')
        task=asyncio.current_task()
        if tracked:h.active_operations.add(task)
        try:
            result=await handler(request)
        except asyncio.CancelledError:
            if not tracked:raise
            result=web.json_response({'error':'操作已取消；如已暂停，请恢复只回复后重试'},status=409)
        except web.HTTPException:
            raise
        except (ValueError,KeyError,TypeError) as e:
            result=web.json_response({'error':str(e)},status=400)
        except PermissionError as e:
            result=web.json_response({'error':str(e)},status=403)
        except Exception as e:
            h.log('ERROR','api_error',raw=str(e),traceback=traceback.format_exc())
            result=web.json_response({'error':str(e)},status=500)
        finally:
            if tracked:h.active_operations.discard(task)
        result.headers['Cache-Control']='no-store'
        result.headers['X-Content-Type-Options']='nosniff'
        result.headers['Content-Security-Policy']="default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'none'"
        return result

    app=web.Application(middlewares=[security],client_max_size=h.cfg['server']['max_body_bytes'])
    async def index(r): return web.FileResponse(ROOT/'src/channel/ui/index.html')
    async def status(r): return web.json_response(h.status())
    async def guide(r):
        from ..core.guides import read_guide
        return web.json_response(read_guide(ROOT,r.match_info['name']))
    async def identity(r):
        if r.method=='GET':
            if r.query.get('revision')==h.identity.profile()['revision']:return web.json_response({'unchanged':True})
            return web.json_response(await asyncio.to_thread(h.identity.snapshot))
        a=await r.json()
        if not isinstance(a,dict) or set(a)-{'nickname','appearance','expected_revision','portrait','icon'}:raise ValueError('角色设置参数无效')
        result=await asyncio.to_thread(h.identity.save,**a)
        h.log('INFO','identity_changed',revision=result['revision'])
        return web.json_response(result)
    async def supervision(r):
        from ..core.supervision import collect
        return web.json_response(await asyncio.to_thread(collect,h.cfg))
    async def group_monitor(r):
        if r.method == 'GET':
            if r.query:
                if set(r.query) != {'group_id'} or len(r.query.getall('group_id')) != 1:
                    raise ValueError('群监听查询参数无效')
                return web.json_response({'messages': h.group_monitor.rows(r.query['group_id'])})
            return web.json_response(dict(h.group_monitor.snapshot(), qq_enabled=h.cfg['qq']['enabled'],
                                         connected=h.qq.connected, online=h.qq.online))
        import copy
        from ..core.config import validate
        from ..modules.group_monitor import group_id
        a = await r.json()
        if not isinstance(a, dict):raise ValueError('群监听参数无效')
        action = a.pop('action', None)
        ident = group_id(a.get('group_id'))
        candidate = copy.deepcopy(h.cfg)
        groups = candidate['group_monitor']['groups']
        current = next((g for g in groups if g['group_id'] == ident), None)
        if action == 'add' and set(a) == {'group_id', 'name'}:
            if current:raise ValueError('该群已添加，请切换到对应窗口')
            groups.append(dict(a, enabled=True))
        elif action == 'update' and set(a) == {'group_id', 'name', 'enabled'}:
            if not current:raise ValueError('该群未添加监听')
            current.update(a)
        elif action == 'remove' and set(a) == {'group_id'}:
            if not current:raise ValueError('该群未添加监听')
            groups.remove(current)
        else:raise ValueError('群监听只允许添加、修改或移除')
        validate(candidate)
        save_local({'group_monitor': candidate['group_monitor']})
        h.cfg['group_monitor'] = candidate['group_monitor']
        h.group_monitor.cfg = h.cfg['group_monitor']
        if action == 'remove':h.group_monitor.seen.pop(ident, None)
        h.log('INFO', 'group_monitor_changed', action=action, group_id=ident)
        return web.json_response({'saved': True, 'restart_required': False})
    async def chat(r): return web.json_response(h.chat_media.chat_rows())
    async def send(r):
        a=await r.json()
        if not isinstance(a,dict):raise ValueError('消息参数必须为对象')
        media=a.get('media',[])
        if not isinstance(media,list) or len(media)>1:raise ValueError('每次对话最多附加一张表情')
        image=a.pop('image',None)
        if image is not None:
            if media or not isinstance(image,dict) or set(image)-{'data_url','name'}:raise ValueError('请每次发送一张图片')
            media=[await h.chat_media.stage(**image)]
            a['media']=media
        for item in media:
            if not isinstance(item,dict):raise ValueError('聊天图片参数无效')
            if item.get('type')=='sticker':h.sticker_intents.local_context(item.get('media_id'))
            elif item.get('type')=='chat_image':
                upload=h.chat_media.upload(item.get('media_id'))
                item.clear();item.update(type='chat_image',media_id=upload['id'],thumbnail=upload['thumbnail'])
            else:raise ValueError('请选择聊天图片或表情包')
        return web.json_response(await h.receive(dict(a,channel='local')))
    async def safety(r):
        a=await r.json();h.set_safety(**a)
        return web.json_response(h.status())
    async def stop(r):
        ServiceIntent(h.root).write(False,'api_manual_stop')
        h.set_safety('paused')
        asyncio.get_running_loop().call_later(0.2,shutdown.set)
        return web.json_response({'stopping':True})
    async def models(r): return web.json_response(await h.model.models())
    async def model_connection(r):
        import copy,os
        from ..core.config import merge,validate
        from ..modules.model import Model
        a=await r.json()
        if not isinstance(a,dict) or set(a)-{'provider','base_url','key_env'}:raise ValueError('连接检查仅接受接入方式、Base URL 和密钥环境变量名称')
        cfg=copy.deepcopy(h.cfg);merge(cfg,{'model':a});validate(cfg)
        # 只读取所选 API 的模型清单；不发聊天内容、不写配置、不记录服务端正文。
        try:rows=await Model(cfg['model'],h.model.session,h.log).models()
        except RuntimeError as error:return web.json_response({'ok':False,'error':str(error),'key_present':bool(os.environ.get(cfg['model']['key_env']))},status=400)
        return web.json_response({'ok':True,'models':rows,'key_present':bool(os.environ.get(cfg['model']['key_env'])),'provider':cfg['model']['provider']})
    async def memory(r):
        if r.method=='GET': return web.json_response(h.memory.query(h.person,r.query.get('q',''),limit=200))
        a=await r.json()
        # 来源由服务端固定，客户端传 source 会被覆盖，不能借此伪造来源。
        a.pop('source',None)
        if a.pop('action','append')=='remove': result=h.memory.remove(h.person,**a)
        else: result=h.memory.append(h.person,source='owner_manual',**a)
        return web.json_response(result)
    async def diary(r):
        return web.json_response(h.diary.recent(30) if r.method=='GET' else h.diary.append(**await r.json()))
    async def growth(r): return web.json_response(h.growth.set(await r.json()))
    async def music(r):
        a=await r.json()
        result=await h.music.lyrics(a['url'],h.learning) if a.get('action')=='lyrics' else await h.music.invoke(a.get('action','status'))
        return web.json_response(result)
    async def device(r):
        a=await r.json()
        if a['action']=='macro_save': result=h.devices.save_macro(a['name'],a['steps'])
        elif a['action']=='macro_replay': result=await h.devices.replay(a['name'])
        else: result=await h.devices.execute(a['action'],a.get('args',{}))
        return web.json_response(result)
    async def study(r):
        a=await r.json()
        if a.get('action')=='search':return web.json_response(await h.learning.search(a['query']))
        return web.json_response(await h.learning.study(h.person,**a))
    async def plugin(r):
        return web.json_response(await h.plugins.mcp(**await r.json()))
    async def persona(r): return web.json_response(h.role.evolve((await r.json())['text']))
    async def soul(r):
        if r.method=='GET':return web.json_response(h.role.soul.snapshot())
        a=await r.json()
        if not isinstance(a,dict):raise ValueError('人设参数必须是对象')
        action=a.pop('action',None)
        if action=='save':
            if set(a)!={'text','expected_revision'}:raise ValueError('人设保存参数无效')
            result=h.role.soul.save(**a)
        elif action=='restore':result=h.role.soul.restore(**a)
        else:raise ValueError('未知专属人设操作')
        h.log('INFO','soul_changed',revision=result['revision'],chars=len(result['text']),action=action)
        return web.json_response(result)
    async def emotion(r): return web.json_response(h.role.emotion(**await r.json()))
    async def promise(r): return web.json_response(h.awakening.promise(**await r.json()))
    async def inspect(r):
        allowed={'emotion','impressions','growth','promises','learning','notifications','plugin_audit','sleep_runs','share_drafts','media','stickers'}
        stream=r.match_info['stream']
        if stream not in allowed: raise PermissionError('数据视图未授权')
        return web.json_response(h.store.read(stream)[-100:])
    async def transcribe(r): return web.json_response({'text':await h.senses.transcribe((await r.json())['path'])})
    async def share(r): return web.json_response(h.plugins.publish((await r.json())['text']))
    async def sticker_intents(r):
        if r.method=='GET':return web.json_response(h.sticker_intents.list())
        a=await r.json()
        if not isinstance(a,dict):raise ValueError('表情操作参数必须为对象')
        action=a.pop('action',None)
        if action=='analyze':result=await h.sticker_intents.analyze_upload(**a)
        elif action=='save':result=h.sticker_intents.save(**a)
        elif action=='remove':result=h.sticker_intents.remove(**a)
        else:raise ValueError('未知表情理解操作')
        return web.json_response(result)
    async def config(r):
        if r.method=='GET':return web.json_response(load())
        patch=await r.json()
        if 'group_monitor' in patch:
            import copy
            from ..core.config import merge
            candidate=copy.deepcopy(h.cfg);merge(candidate,patch)
            if candidate['group_monitor']!=h.cfg['group_monitor']:raise ValueError('请在“群聊监听”页管理监听群；其他限制请停机后修改配置')
        save_local(patch)
        return web.json_response({'saved':True,'restart_required':True})
    app.router.add_get('/',index)
    app.router.add_get('/api/group-monitor',group_monitor)
    app.router.add_post('/api/group-monitor',group_monitor)
    app.router.add_get('/api/guide/{name}',guide)
    app.router.add_get('/api/identity',identity)
    app.router.add_post('/api/identity',identity)
    app.router.add_post('/api/model-connection',model_connection)
    app.router.add_get('/api/soul',soul)
    app.router.add_post('/api/soul',soul)
    app.router.add_get('/api/supervision',supervision)
    app.router.add_static('/assets/',ROOT/'src/channel/ui',show_index=False)
    app.router.add_get('/api/sticker-intents',sticker_intents)
    app.router.add_post('/api/sticker-intents',sticker_intents)
    for path,handler in [('/api/status',status),('/api/chat',chat),('/api/models',models),('/api/memory',memory),('/api/diary',diary),('/api/config',config),('/api/data/{stream}',inspect)]:
        app.router.add_get(path,handler)
    for path,handler in [('/api/chat',send),('/api/safety',safety),('/api/stop',stop),('/api/memory',memory),('/api/diary',diary),('/api/growth',growth),('/api/music',music),('/api/device',device),('/api/study',study),('/api/mcp',plugin),('/api/persona',persona),('/api/emotion',emotion),('/api/promise',promise),('/api/transcribe',transcribe),('/api/share',share),('/api/config',config)]:
        app.router.add_post(path,handler)
    return app
