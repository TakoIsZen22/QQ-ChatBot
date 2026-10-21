"""Optional QQ password cache, independent from the local application account."""
import base64
import hashlib
import json
import os
import re
import time
from .local_account import LocalAccount
from .remembered_login import _dpapi


class QQPassword:
    def __init__(self,root,uin,days=30):
        self.root=root.resolve();self.uin=uin;self.days=days
        self.path=self.root/'.runtime/qq-password.local.json'
        self.entropy=hashlib.sha256(('QQChatBot/qq-password/v1/'+os.path.normcase(str(self.root))+'/'+uin).encode()).digest()

    def read(self):
        if os.name!='nt':return None
        try:
            outer=LocalAccount._read(self.path)
            if not outer or outer['version']!=1:return None
            value=json.loads(_dpapi(base64.b64decode(outer['blob'],validate=True),self.entropy,True))
            if (value['uin']!=self.uin or not re.fullmatch('[a-f0-9]{32}',value['hash'])
                or type(value['auto']) is not bool or type(value['expires']) not in (int,float)
                or not time.time()<value['expires']<=time.time()+self.days*86400+5):return None
            return value
        except (OSError,ValueError,KeyError,TypeError,UnicodeError):return None

    def status(self):
        value=self.read()
        return {'saved':value is not None,'auto':value['auto'] if value else False,'supported':os.name=='nt'}

    def save(self,hash_value,auto=False):
        if not re.fullmatch('[a-f0-9]{32}',hash_value) or type(auto) is not bool:raise ValueError('QQ 登录保存参数无效')
        value={'uin':self.uin,'hash':hash_value,'auto':auto,'expires':time.time()+self.days*86400}
        encrypted=_dpapi(json.dumps(value).encode(),self.entropy)
        LocalAccount._write(self.path,{'version':1,'blob':base64.b64encode(encrypted).decode()})

    def disable_auto(self):
        value=self.read()
        if value and value['auto']:
            value['auto']=False
            encrypted=_dpapi(json.dumps(value).encode(),self.entropy)
            LocalAccount._write(self.path,{'version':1,'blob':base64.b64encode(encrypted).decode()})

    def forget(self):self.path.unlink(missing_ok=True)
