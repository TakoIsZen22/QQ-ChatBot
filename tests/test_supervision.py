import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from src.core.config import load, validate
from src.core.supervision import collect


class SupervisionTests(unittest.TestCase):
    def setUp(self):
        self.cfg = load(Path(tempfile.gettempdir())/'no-dafeiyu-local-config.json')
        self.cfg['maintenance']['agent_name'] = '其他监管助手'

    def test_any_agent_can_read_health_without_private_fields_or_actions(self):
        data = {'name':'大肥鱼 Harness','mode':'paused','last_spoke':None,'memory_count':2,'agent_active':1,
                'qq_bot_id':'sensitive-account','content':'private-dialogue','key':'private-value'}
        response = Mock()
        response.__enter__ = Mock(return_value=response)
        response.__exit__ = Mock(return_value=False)
        response.read.return_value = json.dumps(data).encode()
        opener = Mock()
        opener.open.return_value = response
        with patch('src.core.supervision.socket.create_connection'), patch('src.core.supervision.urllib.request.build_opener',return_value=opener):
            report = collect(self.cfg)
        self.assertEqual(report['overall'],'healthy')
        self.assertEqual(report['maintainer'],'其他监管助手')
        self.assertEqual(report['status']['mode'],'paused')
        self.assertIsNone(report['status']['last_spoke'])
        self.assertEqual(report['status']['agent_active'],1)
        self.assertTrue(opener.open.call_args.args[0].endswith('/api/status'))
        self.assertEqual(opener.open.call_count,1)
        serialized = json.dumps(report)
        for value in ('sensitive-account','private-dialogue','private-value'):
            self.assertNotIn(value,serialized)

    def test_offline_is_reported_without_inference_or_writing_state(self):
        with patch('src.core.supervision.socket.create_connection',side_effect=OSError), patch('src.core.supervision.urllib.request.build_opener') as opener:
            report = collect(self.cfg)
        self.assertEqual(report['overall'],'degraded')
        self.assertFalse(report['checks']['harness'])
        opener.assert_not_called()

    def test_labels_are_configurable_but_not_multiline_or_blank(self):
        validate(self.cfg)
        for name in ('','x\ny', 'x'*81):
            self.cfg['maintenance']['agent_name'] = name
            with self.assertRaises(ValueError):validate(self.cfg)
