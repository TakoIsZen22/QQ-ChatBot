"""Multiple runtime and system-install fixtures; never load native QQ."""
import copy
import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock, patch
from src.core.native_compat import catalog, CRITICAL
from src.core.native_host import runtime, atomic
from src.core import local_qq
from src.core.onboarding import Onboarding
from src.core.config import load


class CompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name).resolve();(self.root/'config').mkdir()
        self.profile={'version':'fixture-a','adapter':'embedded-qqnt-v1','node':'24.11.1',
                      'v8':'14.4.258.16-electron.0','appid':'12345','qua':'fixture',
                      'sha256':{p:hashlib.sha256(b'official').hexdigest() for p in CRITICAL}}
        self.cfg={'schema':'qq-chatbot.native-compat.v2','preferred':'fixture-a',
                  'profiles':[self.profile,dict(self.profile,version='fixture-b')],
                  'limits':{'start_timeout_seconds':20,'stop_timeout_seconds':5,'control_poll_ms':250,'qr_max_age_seconds':120}}
        self.write_catalog()
        atomic(self.root/'config/runtime-downloads.json',{'limits':{'max_files':40000,'max_unpacked_bytes':2000000000}})

    def write_catalog(self):atomic(self.root/'config/qq-native-compat.json',self.cfg)

    def client(self,client,version):
        for name in CRITICAL:
            p=client/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(b'official')
        atomic(client/'resources/app/package.json',{'version':version,'main':'./original.js'})
        return client

    def system(self):
        folder=self.root/'system-QQ';client=self.client(folder/'versions/fixture-a','fixture-a')
        (folder/'QQ.exe').write_bytes(b'program')
        atomic(folder/'versions/config.json',{'curVersion':'fixture-a'})
        (client/'private.db').write_bytes(b'NEVER-COPY')
        (client/'login.json').write_bytes(b'NEVER-COPY')
        (client/'extra.dll').write_bytes(b'program-dependency')
        return folder,client

    def test_two_profiles_select_preferred_or_explicit_without_rejecting_old_versions(self):
        a=self.client(self.root/'.runtime/qq-client/versions/fixture-a','fixture-a')
        b=self.client(self.root/'.runtime/qq-client/versions/fixture-b','fixture-b')
        self.assertEqual(runtime(self.root)[0],a)
        self.assertEqual(runtime(self.root,'fixture-b')[0],b)
        with self.assertRaisesRegex(ValueError,'尚未适配'):runtime(self.root,'unknown')
        # A corrupt preferred runtime must never silently fall back to another.
        (a/'QQNT.dll').write_bytes(b'tampered')
        with self.assertRaisesRegex(ValueError,'校验失败'):runtime(self.root)

    def test_unknown_version_and_adapter_and_missing_hash_fail_closed(self):
        self.client(self.root/'.runtime/qq-client/versions/unknown','unknown')
        with self.assertRaisesRegex(ValueError,'尚未适配'):runtime(self.root)
        for change in ({'adapter':'unimplemented'},{'node':'25.0.0'},{'sha256':{}}):
            with self.subTest(change=change):
                value=copy.deepcopy(self.cfg);value['profiles'][0].update(change)
                atomic(self.root/'config/qq-native-compat.json',value)
                with self.assertRaises(ValueError):catalog(self.root)

    def test_scan_is_readonly_and_copy_excludes_login_and_database(self):
        folder,client=self.system();original=(client/'resources/app/package.json').read_bytes()
        with patch.object(local_qq.system_qq,'install_dirs',return_value=[folder]):
            result=local_qq.scan(self.root)
            self.assertTrue(result['clients'][0]['compatible'])
            self.assertFalse((self.root/'.runtime').exists())
            stage=self.root/'stage'
            self.assertEqual(local_qq.copy_program(self.root,0,stage),'fixture-a')
        self.assertFalse((stage/'private.db').exists());self.assertFalse((stage/'login.json').exists())
        self.assertFalse((stage/'QQ.exe').exists());self.assertTrue((stage/'extra.dll').is_file())
        self.assertEqual(original,(client/'resources/app/package.json').read_bytes())

    def test_scan_checks_metadata_current_version_and_hashes_before_offering_copy(self):
        folder,client=self.system()
        with patch.object(local_qq.system_qq,'install_dirs',return_value=[folder]):
            (client/'QQNT.dll').write_bytes(b'tampered')
            self.assertFalse(local_qq.scan(self.root)['clients'][0]['compatible'])
            with self.assertRaisesRegex(ValueError,'校验失败'):local_qq.copy_program(self.root,0,self.root/'stage')
            self.assertFalse((self.root/'stage').exists())
            atomic(folder/'versions/config.json',{'curVersion':'../../escape'})
            self.assertIsNone(local_qq.system_qq.package_json_of(folder))

    def test_copy_action_preserves_existing_install_and_does_not_start_or_stop_services(self):
        folder,client=self.system()
        self.client(self.root/'.runtime/qq-client/versions/fixture-a','fixture-a')
        api=Mock();api._command_lock=threading.Lock();api._command_lock.acquire()
        setup=Onboarding(api)
        with patch('src.core.onboarding.ROOT',self.root),patch('src.core.native_host.NativeHost.owned',return_value=None),\
             patch.object(local_qq.system_qq,'install_dirs',return_value=[folder]),patch('src.core.onboarding.save_local') as save:
            setup._copy_local(0)
        self.assertIn('已存在',setup._job['message']);save.assert_not_called()
        api._backend.start_qq.assert_not_called();api._backend.stop_qq.assert_not_called()
        self.assertFalse(api._command_lock.locked())

    def test_copy_action_selects_new_runtime_without_restarting_any_services(self):
        folder,client=self.system();(self.root/'.runtime').mkdir()
        api=Mock();api._command_lock=threading.Lock();api._command_lock.acquire();setup=Onboarding(api)
        with patch('src.core.onboarding.ROOT',self.root),patch('src.core.native_host.NativeHost.owned',return_value=None),\
             patch.object(local_qq.system_qq,'install_dirs',return_value=[folder]),patch('src.core.onboarding.save_local') as save:
            setup._copy_local(0)
        self.assertEqual(setup._job['stage'],'done');save.assert_called_once_with({'qq':{'native_version':'fixture-a'}})
        self.assertEqual(runtime(self.root)[1]['version'],'fixture-a')
        self.assertFalse(api._backend.method_calls);self.assertFalse(api._command_lock.locked())

    def test_arbitrary_path_or_index_type_is_rejected(self):
        api=Mock();api._command_lock=threading.Lock();setup=Onboarding(api)
        for value in ({'path':'C:/private'},{'index':True},{'index':'0'},None):
            with self.subTest(value=value),self.assertRaises(ValueError):setup.use_local(value)
        self.assertFalse(api._command_lock.locked())


if __name__=='__main__':unittest.main()
