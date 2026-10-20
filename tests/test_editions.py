import asyncio
import copy
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock, patch
from src.core.config import ROOT,load,validate
from src.core.edition import capabilities
from src.core.guides import read_guide
from src.core.model_endpoint import endpoint,probe_port
from src.modules.model import Model
from tools.package_release import build_release
from tools.release_editions import VERSIONS,prepare_edition


class EditionTests(unittest.TestCase):
    def setUp(self):
        self.cfg=load(ROOT/'.runtime/absent-edition-test.json')
        self.cfg['model'].update(provider='magpie',base_url='http://127.0.0.1:3425/v1')

    def test_api_only_blocks_magpie_before_network_and_help_reads(self):
        with patch('src.core.edition.VERSION','1.00.01'):
            self.assertEqual(capabilities()['providers'],['openai_compatible'])
            for action in (lambda:endpoint(self.cfg['model']),lambda:validate(self.cfg),
                           lambda:read_guide(ROOT,'magpie')):
                with self.assertRaisesRegex(ValueError,'1.00.02'):action()
            session=Mock()
            with self.assertRaisesRegex(ValueError,'1.00.02'):
                asyncio.run(Model(self.cfg['model'],session,Mock()).models())
            session.get.assert_not_called()

    def test_empty_api_can_boot_but_cannot_infer_or_probe_a_default_address(self):
        self.cfg['model'].update(provider='openai_compatible',base_url='',key_env='HARNESS_API_KEY')
        with patch('src.core.edition.VERSION','1.00.01'),patch('src.core.model_endpoint.socket.create_connection') as connect:
            validate(self.cfg)
            self.assertFalse(probe_port(self.cfg['model']))
            connect.assert_not_called()
            with self.assertRaisesRegex(ValueError,'Base URL'):endpoint(self.cfg['model'])
            self.cfg['model']['main']='user-model'
            with self.assertRaisesRegex(ValueError,'Base URL'):validate(self.cfg)

    def test_both_editions_allow_user_api_and_only_02_allows_magpie(self):
        for version in VERSIONS:
            with self.subTest(version=version),patch('src.core.edition.VERSION',version):
                model=copy.deepcopy(self.cfg['model'])
                model.update(provider='openai_compatible',base_url='https://api.example/v1')
                self.assertEqual(endpoint(model),'https://api.example/v1')
        with patch('src.core.edition.VERSION','1.00.02'):
            self.assertEqual(endpoint(self.cfg['model']),'http://127.0.0.1:3425/v1')

    def test_clean_source_editions_boot_with_their_own_version_defaults_and_ui(self):
        with tempfile.TemporaryDirectory() as temp:
            temp=Path(temp)
            archive=build_release(ROOT,temp/'clean.zip')['path']
            for version in VERSIONS:
                stage=prepare_edition(archive,temp/version,version)
                code="""
import json
from pathlib import Path
from src.core.config import load,validate
from src.core.edition import capabilities
from src.core.model_endpoint import endpoint
c=load(Path('config/absent.json'));validate(c)
blocked=False
try:endpoint(dict(c['model'],provider='magpie',base_url='http://127.0.0.1:3425/v1'))
except ValueError:blocked=True
print(json.dumps({'edition':capabilities(),'provider':c['model']['provider'],'url':c['model']['base_url'],'blocked':blocked,'paused':c['safety']['mode'],'qq':c['qq']['enabled']}))
"""
                result=json.loads(subprocess.check_output([sys.executable,'-B','-c',code],cwd=stage,text=True,encoding='utf-8'))
                self.assertEqual(result['edition']['version'],version)
                self.assertEqual(result['paused'],'paused');self.assertFalse(result['qq'])
                only=version=='1.00.01'
                self.assertEqual(result['blocked'],only)
                self.assertEqual(result['provider'],'openai_compatible' if only else 'magpie')
                self.assertEqual(result['url'],'' if only else 'http://127.0.0.1:3425/v1')
                for name in ('index.html','onboarding.js'):
                    ui=(stage/'src/channel/ui/desktop'/name).read_text(encoding='utf-8')
                    self.assertEqual('<option value="magpie">' in ui,not only)
                    self.assertEqual('data-guide="magpie"' in ui,not only)
                self.assertEqual((stage/'docs/MAGPIE_SETUP.md').exists(),not only)
                self.assertFalse((stage/'config/local.json').exists())
                self.assertFalse((stage/'data').exists())
                with self.assertRaises(FileExistsError):prepare_edition(archive,stage,version)

    def test_edition_extractor_rejects_unsafe_archive_paths(self):
        with tempfile.TemporaryDirectory() as temp:
            archive=Path(temp)/'unsafe.zip'
            with zipfile.ZipFile(archive,'w') as bundle:bundle.writestr('source/../outside','bad')
            with self.assertRaisesRegex(ValueError,'路径'):
                prepare_edition(archive,Path(temp)/'destination','1.00.01')


if __name__=='__main__':unittest.main()
