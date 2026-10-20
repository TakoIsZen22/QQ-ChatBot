"""使用者定制的昵称、形象和图标；素材仅存私有 data，文件名按内容生成。"""
import base64
import hashlib
import io
import json
import re
import uuid
from pathlib import Path
from .config import ROOT,load
from .store import Store


from .product import NAME as PRODUCT_TITLE


class Identity:
    def __init__(self,cfg,store,root):
        self.cfg,self.store,self.root=cfg,store,Path(root).resolve()

    def profile(self):
        row=self.store.latest(self.cfg['stream'])
        return {'nickname':row['nickname'] if row else self.cfg['default_nickname'],
                'appearance':row['appearance'] if row else '',
                'portrait_id':row['portrait_id'] if row else None,
                'icon_id':row['icon_id'] if row else None,
                'revision':row['id'] if row else 'default'}

    def title(self):
        name=self.profile()['nickname']
        return PRODUCT_TITLE if name==self.cfg['default_nickname'] else name+' · '+PRODUCT_TITLE

    def asset(self,kind,ident,suffix='png'):
        if kind not in ('portrait','icon') or suffix not in ('png','ico') or not re.fullmatch('[a-f0-9]{64}',str(ident)):
            raise ValueError('角色素材标识无效')
        base=self.store.root.resolve()
        path=(base/self.cfg['asset_dir']/(kind+'-'+ident+'.'+suffix)).resolve()
        if not path.is_relative_to(base) or not base.is_relative_to(self.root):raise ValueError('角色素材必须位于私有 data')
        return path

    def default_path(self,suffix='png'):
        path=(self.root/self.cfg['default_'+('icon_ico' if suffix=='ico' else 'image')]).resolve()
        if not path.is_relative_to((self.root/'assets').resolve()):raise ValueError('默认素材必须位于 assets')
        return path

    def image_path(self,kind,suffix='png',profile=None):
        if kind not in ('portrait','icon') or suffix not in ('png','ico'):raise ValueError('角色素材类型无效')
        ident=(profile or self.profile())[kind+'_id']
        if ident:
            path=self.asset(kind,ident,suffix)
            if path.is_file():return path
        return self.default_path(suffix)

    def snapshot(self):
        profile=self.profile()
        profile.update(product_name=PRODUCT_TITLE,window_title=self.title())
        for kind in ('portrait','icon'):
            path=self.image_path(kind,profile=profile)
            profile[kind+'_data']='data:image/png;base64,'+base64.b64encode(path.read_bytes()).decode() if path.is_file() else None
        profile['limits']={key:self.cfg[key] for key in ('max_image_bytes','max_nickname_chars','max_appearance_chars')}
        default=self.default_path()
        profile['defaults']={'nickname':self.cfg['default_nickname'],'image_data':'data:image/png;base64,'+base64.b64encode(default.read_bytes()).decode() if default.is_file() else None}
        return profile

    def _image(self,data,kind):
        from PIL import Image,ImageOps
        if not isinstance(data,str) or len(data)>self.cfg['max_image_bytes']*4//3+128:
            raise ValueError('图片超过配置大小上限')
        match=re.fullmatch(r'data:image/(?:png|jpeg|webp|x-icon|vnd.microsoft.icon);base64,([A-Za-z0-9+/=]+)',data)
        if not match:raise ValueError('请选择 PNG/JPG/WEBP 图片；程序图标也可使用 ICO')
        try:
            raw=base64.b64decode(match[1],validate=True)
            if len(raw)>self.cfg['max_image_bytes']:raise ValueError('图片过大')
            with Image.open(io.BytesIO(raw)) as source:
                allowed=('PNG','JPEG','WEBP','ICO') if kind=='icon' else ('PNG','JPEG','WEBP')
                if source.format not in allowed or getattr(source,'n_frames',1)!=1:raise ValueError('仅支持静态图片')
                if source.width*source.height>self.cfg['max_pixels']:raise ValueError('图片像素过大')
                source.load();image=ImageOps.exif_transpose(source).convert('RGBA');image.info.clear()
        except Exception as error:
            raise ValueError('无法读取角色图片：'+str(error)) from None
        edge=self.cfg['icon_edge'] if kind=='icon' else self.cfg['portrait_edge']
        image.thumbnail((edge,edge),Image.Resampling.LANCZOS)
        if kind=='icon':
            canvas=Image.new('RGBA',(edge,edge));canvas.alpha_composite(image,((edge-image.width)//2,(edge-image.height)//2));image=canvas
        png=io.BytesIO();image.save(png,format='PNG');files={'png':png.getvalue()}
        if kind=='icon':
            ico=io.BytesIO();image.save(ico,format='ICO',sizes=[(n,n) for n in self.cfg['ico_sizes']]);files['ico']=ico.getvalue()
        return hashlib.sha256(b''.join(files.values())).hexdigest(),files

    def save(self,nickname,appearance,expected_revision,**images):
        if not isinstance(nickname,str) or not nickname.strip() or len(nickname)>self.cfg['max_nickname_chars'] or any(ord(c)<32 for c in nickname):raise ValueError('昵称需为非空单行短文本')
        if not isinstance(appearance,str) or len(appearance)>self.cfg['max_appearance_chars'] or '\x00' in appearance:raise ValueError('形象描述长度无效')
        if set(images)-{'portrait','icon'}:raise ValueError('未允许的角色素材字段')
        if self.profile()['revision']!=expected_revision:raise ValueError('角色设置已变化，请重新读取后保存')
        prepared={kind:self._image(data,kind) if data is not None else None for kind,data in images.items()}
        # 解码与落盘不占全局Store锁，不阻塞保命开关或消息日志。
        for kind,value in prepared.items():
            if value is None:continue
            ident,files=value
            for suffix,raw in files.items():
                path=self.asset(kind,ident,suffix);path.parent.mkdir(parents=True,exist_ok=True)
                temp=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
                try:
                    temp.write_bytes(raw);temp.replace(path)
                finally:
                    if temp.exists():temp.unlink()
        with self.store.lock:
            current=self.profile()
            if current['revision']!=expected_revision:raise ValueError('角色设置已变化，图片已暂存但未应用，请重新读取')
            for kind,value in prepared.items():current[kind+'_id']=value[0] if value else None
            self.store.append(self.cfg['stream'],nickname=nickname.strip(),appearance=appearance.strip(),
                              portrait_id=current['portrait_id'],icon_id=current['icon_id'],source='owner_manual')
        return self.snapshot()

    def prompt(self):
        p=self.profile()
        return '\n【当前专属角色资料】\n昵称以此处为准，旧角色卡或 soul.md 中出现旧名字时仍使用此昵称：'+json.dumps(p['nickname'],ensure_ascii=False)+'。\n形象文字描述：'+(p['appearance'] or '以 soul.md 中的描述为准；界面图片未经过视觉分析，不猜其中细节。')


def installed_identity(root=ROOT):
    cfg=load();return Identity(cfg['identity'],Store(Path(root)/cfg['paths']['data']),root)
