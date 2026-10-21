"""Optional single local account; no model/vendor credentials or QQ passwords."""
import base64
import hashlib
import hmac
import json
import os
import secrets
import stat
import time
from contextlib import contextmanager
from pathlib import Path
from .instance import InstanceLock


class LoginRequired(PermissionError):
    def __init__(self):super().__init__('请先登录 QQ ChatBot 本机账号')


class LocalAccount:
    COOKIE = 'qqchatbot_session'

    def __init__(self, root, policy):
        self.root = Path(root)
        self.policy = policy
        self.path = self.root/'config/account.local.json'
        self.attempts = self.root/'.runtime/account-attempts.json'

    @staticmethod
    def _read(path):
        try:
            info = path.lstat()
        except FileNotFoundError:return None
        if not stat.S_ISREG(info.st_mode) or getattr(info, 'st_file_attributes', 0) & 0x400 or info.st_size > 16384:
            raise PermissionError('本机账号文件异常，请停止程序后按本机登录文档恢复')
        try:
            value=json.loads(path.read_text(encoding='utf-8'))
            if not isinstance(value,dict):raise ValueError()
            return value
        except (ValueError, OSError):raise PermissionError('本机账号文件无法读取，请按本机登录文档恢复') from None

    def _record(self):
        row = self._read(self.path)
        if row is None:return None
        try:
            if (type(row['version']) is not int or row['version'] != 1
                or not isinstance(row['username'], str) or not 1 <= len(row['username']) <= 64
                or any(len(bytes.fromhex(row[key])) != size for key,size in (('salt',16),('hash',32),('secret',32),('revision',16)))):
                raise ValueError()
        except (ValueError, KeyError, TypeError):
            raise PermissionError('本机账号文件损坏，拒绝跳过登录，请按文档恢复') from None
        return row

    @staticmethod
    def _write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        # Unique same-directory file and atomic replace; never write a plaintext password.
        temp = path.with_name(path.name+'.'+secrets.token_hex(8)+'.tmp')
        try:
            with temp.open('x', encoding='utf-8') as f:
                if os.name != 'nt':os.chmod(temp, 0o600)
                json.dump(value, f, ensure_ascii=False);f.flush();os.fsync(f.fileno())
            temp.replace(path)
        finally:
            if temp.exists():temp.unlink()

    @contextmanager
    def _locked(self):
        try:lock = InstanceLock(self.root/'.runtime/account.lock')
        except (OSError, RuntimeError):raise ValueError('账号操作正在进行，请稍后再试') from None
        try:yield
        finally:lock.close()

    @staticmethod
    def _hash(password, salt):
        return hashlib.scrypt(password.encode('utf-8'), salt=bytes.fromhex(salt), n=32768, r=8, p=1, dklen=32, maxmem=64*1024*1024).hex()

    @staticmethod
    def _input(username, password):
        if not isinstance(username, str) or not username.strip() or len(username) > 64 or any(ord(c) < 32 for c in username):
            raise ValueError('账号需为 1～64 字的单行文本')
        if not isinstance(password, str) or not 8 <= len(password) <= 128:
            raise ValueError('密码需为 8～128 个字符')
        return username.strip()

    def _throttle(self):
        row = self._read(self.attempts)
        if row is None:row={'failures': [], 'blocked_until': 0}
        try:
            if (not isinstance(row['failures'], list) or len(row['failures']) > 100
                or not all(type(t) in (int,float) and 0 <= t < 1e12 for t in row['failures'])
                or type(row['blocked_until']) not in (int,float) or not 0 <= row['blocked_until'] < 1e12):
                raise ValueError()
        except (ValueError, TypeError, KeyError):raise PermissionError('账号限流记录异常，请按文档恢复') from None
        now = time.time()
        if row['blocked_until'] > now:
            raise PermissionError(f'密码连续输错，请在 {int(row["blocked_until"]-now)+1} 秒后重试')
        row['failures'] = [t for t in row['failures'] if now-t < self.policy['failure_window_seconds']]
        return row

    def _verify_password(self, row, username, password):
        attempts = self._throttle()
        # Malformed/incorrect inputs also count; error never echoes inputs.
        valid = isinstance(password, str) and len(password) <= 128
        candidate = self._hash(password if valid else '', row['salt'])
        if not (valid and hmac.compare_digest(candidate, row['hash']) and username == row['username']):
            attempts['failures'].append(time.time())
            if len(attempts['failures']) >= self.policy['max_failures']:
                attempts['blocked_until'] = time.time()+self.policy['lockout_seconds']
                attempts['failures'] = []
            self._write(self.attempts, attempts)
            self._audit('login_failed')
            raise PermissionError('账号或密码不正确')
        self._write(self.attempts, {'failures': [], 'blocked_until': 0})

    def _audit(self, event):
        from .log import Log
        from .store import Store
        Log(Store(self.root/'.runtime/account-logs'))('INFO', 'local_account_'+event)

    def authenticated(self, token=None):
        row = self._record()
        if row is None:return True
        if not isinstance(token, str) or len(token) > 2048:return False
        try:
            payload, signature = token.split('.')
            expected = hmac.new(bytes.fromhex(row['secret']), payload.encode('ascii'), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):return False
            data = json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
            return (data['revision'] == row['revision'] and type(data['expires']) is int
                    and time.time() < data['expires'] <= time.time()+self.policy['session_seconds']+5)
        except (ValueError, KeyError, TypeError, UnicodeError):return False

    def require(self, token=None):
        if not self.authenticated(token):raise LoginRequired()

    def status(self, token=None):
        row = self._record()
        authorized = self.authenticated(token)
        return {'configured': row is not None, 'authenticated': authorized,
                'username': row['username'] if row and authorized else '',
                'session_seconds': self.policy['session_seconds']}

    def _token(self, row):
        data = {'revision': row['revision'], 'expires': int(time.time())+self.policy['session_seconds'], 'nonce': secrets.token_hex(16)}
        payload = base64.urlsafe_b64encode(json.dumps(data, separators=(',', ':')).encode()).decode().rstrip('=')
        return payload+'.'+hmac.new(bytes.fromhex(row['secret']), payload.encode(), hashlib.sha256).hexdigest()

    def setup(self, username, password):
        username = self._input(username, password)
        with self._locked():
            if self._record() is not None:raise PermissionError('本机账号已设置，请登录后修改')
            row = {'version': 1, 'username': username, 'salt': secrets.token_hex(16),
                   'secret': secrets.token_hex(32), 'revision': secrets.token_hex(16)}
            row['hash'] = self._hash(password, row['salt'])
            self._write(self.path, row);self._audit('configured')
            return self._token(row)

    def login(self, username, password, *, expected_revision=None):
        with self._locked():
            row = self._record()
            if row is None:raise ValueError('请先在桌面程序的“程序设置”中创建本机账号')
            if expected_revision is not None and row['revision']!=expected_revision:
                raise PermissionError('已保存的登录已失效，请手动输入密码')
            self._verify_password(row, username, password)
            self._audit('login_success')
            return self._token(row)

    def change(self, token, current_password, username, password):
        username = self._input(username, password)
        with self._locked():
            self.require(token)
            row = self._record()
            if row is None:raise ValueError('本机账号尚未设置')
            self._verify_password(row, row['username'], current_password)
            row.update(username=username, salt=secrets.token_hex(16), revision=secrets.token_hex(16))
            row['hash'] = self._hash(password, row['salt'])
            self._write(self.path, row);self._audit('changed')
            return self._token(row)

    def lock(self, token):
        with self._locked():
            self.require(token)
            row = self._record()
            if row:
                row['revision'] = secrets.token_hex(16)
                self._write(self.path, row);self._audit('locked')
