"""Opt-in desktop login, encrypted for the current Windows user with DPAPI.

Passwords never cross the desktop bridge on retrieval. Copying an installation
to another path/user does not copy an automatic-login grant.
"""
import base64
import ctypes
import hashlib
import json
import os
import time
from ctypes import wintypes
from .local_account import LocalAccount


def _dpapi(data, entropy, decrypt=False):
    if os.name != 'nt':raise ValueError('记住密码仅支持 Windows 桌面程序')

    class Blob(ctypes.Structure):
        _fields_=[('size',wintypes.DWORD),('data',ctypes.POINTER(ctypes.c_ubyte))]

    def blob(value):
        buffer=ctypes.create_string_buffer(value)
        return Blob(len(value),ctypes.cast(buffer,ctypes.POINTER(ctypes.c_ubyte))),buffer

    source,source_buffer=blob(data)
    extra,extra_buffer=blob(entropy)
    output=Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    # CRYPTPROTECT_UI_FORBIDDEN; never use CRYPTPROTECT_LOCAL_MACHINE.
    if decrypt:
        fn=crypt.CryptUnprotectData
        fn.argtypes=[ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        fn.restype=wintypes.BOOL
        ok=fn(ctypes.byref(source),None,ctypes.byref(extra),None,None,1,ctypes.byref(output))
    else:
        fn=crypt.CryptProtectData
        fn.argtypes=[ctypes.POINTER(Blob),wintypes.LPCWSTR,ctypes.POINTER(Blob),ctypes.c_void_p,ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(Blob)]
        fn.restype=wintypes.BOOL
        ok=fn(ctypes.byref(source),'QQ ChatBot 本机登录',ctypes.byref(extra),None,None,1,ctypes.byref(output))
    if not ok:raise ValueError('Windows 无法读取或保存登录信息，请手动输入密码')
    try:return ctypes.string_at(output.data,output.size)
    finally:kernel.LocalFree(ctypes.cast(output.data,ctypes.c_void_p))


class RememberedLogin:
    def __init__(self,root,policy):
        self.root=root.resolve()
        self.path=self.root/'.runtime/account-remember.local.json'
        self.policy=policy
        self.entropy=hashlib.sha256(('QQChatBot/login/v1/'+os.path.normcase(str(self.root))).encode()).digest()

    @property
    def supported(self):return os.name=='nt'

    def read(self,account):
        record=account._record()
        if not self.supported or record is None:return None
        try:
            wrapper=LocalAccount._read(self.path)
            if wrapper is None:return None
            if wrapper['version']!=1:raise ValueError()
            encrypted=base64.b64decode(wrapper['blob'],validate=True)
            value=json.loads(_dpapi(encrypted,self.entropy,decrypt=True))
            if (value['version']!=1 or value['revision']!=record['revision']
                or value['username']!=record['username']
                or type(value['auto_login']) is not bool
                or type(value['expires']) not in (int,float)
                or not time.time()<value['expires']<=time.time()+self.policy['remember_days']*86400+5):return None
            LocalAccount._input(value['username'],value['password'])
            return value
        except (ValueError,TypeError,KeyError,UnicodeError,PermissionError,OSError):return None

    def status(self,account):
        value=self.read(account)
        return {'supported':self.supported,'saved':value is not None,
                'username':value['username'] if value else '',
                'auto_login':value['auto_login'] if value else False,
                'days':self.policy['remember_days']}

    def save(self,account,username,password,auto_login=False,expires=None):
        if not self.supported:raise ValueError('记住密码仅支持 Windows 桌面程序')
        record=account._record()
        if record is None or username!=record['username']:raise ValueError('本机账号已变化，请重新登录')
        LocalAccount._input(username,password)
        value={'version':1,'username':username,'password':password,'auto_login':auto_login,
               'revision':record['revision'],
               'expires':expires if expires is not None else time.time()+self.policy['remember_days']*86400}
        encrypted=_dpapi(json.dumps(value,ensure_ascii=False).encode(),self.entropy)
        LocalAccount._write(self.path,{'version':1,'blob':base64.b64encode(encrypted).decode()})

    def forget(self):
        # Only the optional encrypted convenience record, never audit/throttle data.
        self.path.unlink(missing_ok=True)
