import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.core.config import load

spec=importlib.util.spec_from_file_location('dfy_launcher',Path(__file__).resolve().parents[1]/'tools/launch-napcat.py')
launcher=importlib.util.module_from_spec(spec);spec.loader.exec_module(launcher)

class LauncherTests(unittest.TestCase):
    def test_independent_client_uses_matching_version_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);runtime=root/'.runtime/napcat';runtime.mkdir(parents=True)
            client=root/'client';client.mkdir();binary=client/'QQ.exe';binary.write_bytes(b'fixture')
            (client/'versions').mkdir();(client/'versions/config.json').write_text(json.dumps({'curVersion':'9.9.33-52230'}))
            package=client/'versions/9.9.33-52230/resources/app/package.json';package.parent.mkdir(parents=True)
            original={'version':'9.9.33-52230','buildVersion':'52230','main':'original-entry','name':'qq-chat'}
            package.write_text(json.dumps(original))
            cfg=load(root/'absent');cfg['qq'].update(client_path=str(binary),bot_id='123');cfg['owner']['qq_id']='456'
            with patch.object(launcher,'ROOT',root),patch.object(launcher,'load',return_value=cfg),patch.object(launcher.subprocess,'call',return_value=0) as call:
                self.assertEqual(launcher.main(),0)
                self.assertEqual(call.call_args.args[0][1],str(binary.resolve()))
                self.assertEqual(call.call_args.kwargs['env']['NAPCAT_MAIN_PATH'],str(runtime/'napcat.mjs'))
            generated=json.loads((runtime/'qqnt-local-client.json').read_text(encoding='utf-8'))
            self.assertEqual(generated['version'],'9.9.33-52230');self.assertEqual(generated['main'],'./loadNapCat.js')
            self.assertEqual(json.loads(package.read_text()),original)

    def test_bot_cannot_use_owner_account(self):
        cfg=load(Path(tempfile.gettempdir())/'dfy-missing-config.json');cfg['qq']['bot_id']='123';cfg['owner']['qq_id']='123'
        with patch.object(launcher,'load',return_value=cfg):
            with self.assertRaises(ValueError):launcher.main()
