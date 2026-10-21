import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch,Mock

try:
    import tkinter as tk
except ModuleNotFoundError:  # 绿色包的 embeddable Python 不含 tkinter
    tk=None
from src.core.config import load
from src.core.desktop_backend import DesktopBackend
if tk is not None:
    from src.desktop import DesktopApp
else:
    DesktopApp=None

class FakeBackend:
    def __init__(self):self.sent=[];self.fail=False
    def request(self,path,body=None,**kwargs):
        if self.fail:raise RuntimeError('服务未启动')
        if path=='chat' and body is not None:self.sent.append(body);return {'accepted':True}
        if path=='memory':return []
        if path=='diary':return []
        if path=='status':
            return {'mode':'reply_only','qq_connected':True,'qq_online':True,'qq_bot_id':'123','model':'fixture','model_gateway':'http://127.0.0.1:3425/v1','memory_count':0,'queue':0,'last_spoke':None,'weights':{}}
        return []
    def start_all(self):return '已启动'
    def restart_core(self):return '已重启'
    def stop_all(self):return '已停止'
    def start_qq(self):return 'QQ启动'
    def logs(self):return 'INFO fixture'

@unittest.skipIf(tk is None,'当前 Python 不含 tkinter（绿色包运行时），跳过旧桌面界面测试')
class DesktopTests(unittest.TestCase):
    def setUp(self):
        # The fixture must not read the user's real local-account lock.
        private=tempfile.TemporaryDirectory();self.addCleanup(private.cleanup)
        isolation=patch('src.desktop_legacy.LocalAccount',return_value=Mock(status=Mock(return_value={'configured':False})))
        isolation.start();self.addCleanup(isolation.stop)
        self.root=tk.Tk();self.root.withdraw();self.backend=FakeBackend()
        self.app=DesktopApp(self.root,self.backend,auto_start=False)  # type: ignore[arg-type]
        self.addCleanup(lambda:self.app.close() if not self.app.closed else None)

    def pump_until(self,predicate):
        deadline=time.monotonic()+2
        while not predicate() and time.monotonic()<deadline:self.root.update();time.sleep(.01)
        self.assertTrue(predicate())

    def test_native_chat_and_tabs(self):
        self.assertEqual(len(self.app.notebook.tabs()),5)
        self.app.input.insert('1.0','你好，大肥鱼')
        self.app.send()
        self.pump_until(lambda:self.app.input.get('1.0','end').strip()=='')
        self.assertEqual(self.backend.sent,[{'text':'你好，大肥鱼'}])
        self.app.mode('paused')
        self.pump_until(lambda:'暂停' in self.app.notice.get())

    def test_failed_send_preserves_draft_and_close_keeps_services(self):
        self.backend.fail=True;self.app.input.insert('1.0','这句不能丢')
        self.app.send();self.pump_until(lambda:'服务未启动' in self.app.notice.get())
        self.assertEqual(self.app.input.get('1.0','end').strip(),'这句不能丢')
        self.backend.stop_all=Mock();self.app.close();self.backend.stop_all.assert_not_called()

class LifecycleTests(unittest.TestCase):
    def test_existing_services_are_reused(self):
        backend=DesktopBackend()
        with patch.object(backend,'port',return_value=True),patch.object(backend,'request',return_value={'name':'大肥鱼 Harness'}),patch('src.core.desktop_backend.ServiceIntent'),patch.object(backend,'spawn') as spawn:
            backend.start_all();spawn.assert_not_called()

    def test_hidden_process_creation(self):
        backend=DesktopBackend()
        with patch('src.core.desktop_backend.subprocess.Popen') as popen:
            backend.spawn(['fixture'])
            self.assertEqual(popen.call_args.kwargs['creationflags'],getattr(__import__('subprocess'),'CREATE_NO_WINDOW',0))
            self.assertEqual(popen.call_args.kwargs['stdout'],__import__('subprocess').DEVNULL)
