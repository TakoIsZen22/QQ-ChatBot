import json
import tempfile
import unittest
import io
import urllib.error
from datetime import datetime,timedelta,timezone
from pathlib import Path
from unittest.mock import Mock,patch
from src.core.config import load
from src.core.desktop_api import DesktopApi
from src.core.desktop_backend import DesktopBackend

class DesktopApiTests(unittest.TestCase):
    def test_soul_draft_persists_separately_and_can_be_cleared(self):
        draft={'text':'未提交的个人设定','revision':'a'*64}
        self.api.ui_state({'page':'soul','soul_draft':draft})
        second=DesktopApi(self.backend)
        self.assertEqual(second.ui_state()['soul_draft'],draft)
        second.ui_state({'soul_draft':None})
        self.assertIsNone(second.ui_state()['soul_draft'])
        with self.assertRaises(ValueError):second.ui_state({'soul_draft':{'text':'x','path':'arbitrary'}})
        self.backend.request.assert_not_called()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cfg=load(self.root/'no-local.json')
        self.backend=Mock();self.backend.request.return_value={'ok':True}
        self.api=DesktopApi(self.backend)
        self.patches=[patch('src.core.desktop_api.ROOT',self.root),patch('src.core.desktop_api.load',return_value=self.cfg)]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def test_bridge_rejects_arbitrary_urls_paths_and_actions(self):
        for path in ('http://example.com/status','//example.com','../config/local.json','data/../chat','stop','status?token=abc','memory?q=x&extra=y'):
            with self.subTest(path=path):
                with self.assertRaises(PermissionError):self.api.request(path)
        with self.assertRaises(PermissionError):self.api.command('run-shell')
        self.backend.request.assert_not_called()
        self.api.request('memory?q=')
        self.backend.request.assert_called_once_with('memory?q=',None)

    def test_pause_bypasses_slow_lifecycle_operation_lock(self):
        self.api._command_lock.acquire()
        try:
            with self.assertRaises(RuntimeError):self.api.command('start')
            self.api.request('safety',{'mode':'paused'})
            self.backend.request.assert_called_once_with('safety',{'mode':'paused'})
        finally:self.api._command_lock.release()

    def test_draft_restores_and_rejects_unknown_fields(self):
        original={'draft':'这句话还没有发出去','page':'memory','channel':'qq'}
        self.api.ui_state(original)
        second=DesktopApi(self.backend)
        self.assertEqual(second.ui_state(),original)
        with self.assertRaises(ValueError):self.api.ui_state({'path':'../other'})
        with self.assertRaises(ValueError):self.api.ui_state({'draft':'x'*(self.cfg['conversation']['max_input_chars']+1)})
        self.assertEqual(second.ui_state(),original)

    def test_read_views_and_logs_do_not_expose_chat_text(self):
        (self.root/'logs').mkdir();(self.root/'data').mkdir()
        private={'ts':datetime.now(timezone.utc).isoformat(),'level':'INFO','event':'message_received','text':'不能进入运行记录界面的私聊正文'}
        (self.root/'logs/events.jsonl').write_text(json.dumps(private,ensure_ascii=False)+'\n',encoding='utf-8')
        self.assertNotIn('私聊正文',json.dumps(self.api.events(),ensure_ascii=False))
        with self.assertRaises(PermissionError):self.api.read_data('../config/settings')
        self.assertEqual(self.api.read_data('promise_results'),[])

    def test_usage_summary_counts_entire_day_not_only_log_tail(self):
        (self.root/'logs').mkdir()
        now=datetime.now(timezone.utc);old=(now-timedelta(days=2)).isoformat()
        rows=[{'ts':old,'event':'model_usage','usage':{'total_tokens':99999}}]
        rows += [{'ts':now.isoformat(),'event':'model_usage','usage':{'prompt_tokens':2,'completion_tokens':3}} for _ in range(250)]
        (self.root/'logs/events.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n',encoding='utf-8')
        summary=self.api._usage_today(self.cfg)
        self.assertEqual(summary['total_tokens'],1250);self.assertEqual(summary['samples'],250)

    def test_qq_failure_keeps_local_chat_available(self):
        backend=DesktopBackend()
        with patch.object(backend,'start_core',return_value='聊天已启动') as core,patch.object(backend,'start_qq',side_effect=RuntimeError('缺少专用QQ')):
            result=backend.start_all()
            core.assert_called_once();self.assertIn('聊天已启动',result);self.assertIn('QQ未就绪',result)

    def test_http_error_keeps_actionable_server_message(self):
        error=urllib.error.HTTPError('http://127.0.0.1:8765/api/diary',400,'Bad Request',{},io.BytesIO(json.dumps({'error':'今天日记已经三条'},ensure_ascii=False).encode('utf-8')))
        opener=Mock();opener.open.side_effect=error
        with patch('src.core.desktop_backend.urllib.request.build_opener',return_value=opener):
            with self.assertRaisesRegex(RuntimeError,'今天日记已经三条'):DesktopBackend().request('diary',{'text':'测试'})
