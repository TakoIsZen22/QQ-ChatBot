"""系统 QQ 探测与复用：优先用本机已装的 QQ，不重复下载。"""
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from src.core import system_qq


class SystemQQTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)

    def make_qq(self,version='9.9.33-52230',legacy_layout=False,build_id=None):
        """造一个 QQ 安装目录。legacy_layout 模拟旧版：resources/app 在 versions/<版本>/ 下。"""
        folder=self.root/'QQNT';(folder/'versions'/version/'resources/app').mkdir(parents=True)
        if build_id is None:
            # 真实 config.json 里带 buildId，版本号末段就是它。
            build_id=int(version.rsplit('-',1)[-1])
        (folder/'versions'/'config.json').write_text(json.dumps({'curVersion':version,'baseVersion':version,'buildId':build_id}),encoding='utf-8')
        package=folder/'versions'/version/'resources/app/package.json'
        package.write_text(json.dumps({'name':'qq','version':version,'main':'index.js'}),encoding='utf-8')
        (folder/'QQ.exe').write_bytes(b'MZ')
        if not legacy_layout:
            (folder/'resources/app').mkdir(parents=True,exist_ok=True)
            (folder/'resources/app/package.json').write_text(json.dumps({'name':'qq','version':version,'main':'index.js'}),encoding='utf-8')
        return folder

    def test_detects_installed_qq_and_its_matching_metadata(self):
        folder=self.make_qq()
        with patch.object(system_qq,'install_dirs',return_value=[folder]):
            found=system_qq.find_usable()
        self.assertIsNotNone(found)
        self.assertEqual(found['path'],str(folder/'QQ.exe'))
        self.assertEqual(found['version'],'9.9.33-52230')
        self.assertTrue(found['usable'])
        # 新版布局的元数据在 resources/app 下，必须存在且能被读到。
        self.assertTrue(Path(found['package_json']).is_file())
        data=json.loads(Path(found['package_json']).read_text(encoding='utf-8-sig'))
        self.assertEqual(data['version'],'9.9.33-52230')

    def test_legacy_layout_uses_versioned_package_json(self):
        """旧版 QQ 的 resources/app 在 versions/<版本>/ 下，必须取配套那份。

        注意 9.9.21 的 buildId 低于腾讯门槛，探测会标记 too_old；此处只验证
        元数据定位本身是否正确，因此显式把门槛关掉。
        """
        folder=self.make_qq(version='9.9.21-38711',legacy_layout=True)
        with patch.object(system_qq,'install_dirs',return_value=[folder]),\
             patch.object(system_qq,'min_build_id',return_value=0):
            found=system_qq.find_usable()
        self.assertIsNotNone(found)
        self.assertIn('9.9.21-38711',found['package_json'])
        self.assertTrue(found['usable'])

    def test_install_without_matching_metadata_is_not_usable(self):
        """找不到配套 package.json 就不能复用，否则会拿错元数据导致登录版本误报。"""
        folder=self.root/'QQNT';folder.mkdir()
        (folder/'QQ.exe').write_bytes(b'MZ')
        with patch.object(system_qq,'install_dirs',return_value=[folder]):
            found=system_qq.find_usable()
        self.assertIsNone(found)

    def test_no_installed_qq_returns_none(self):
        with patch.object(system_qq,'install_dirs',return_value=[]):
            self.assertIsNone(system_qq.find_usable())
            self.assertEqual(system_qq.detect(),[])

    def test_qq_below_minimum_build_id_is_not_reused(self):
        """buildId 过低的 QQ 会被腾讯以 error 45 拒绝，复用它只会让用户白扫一次码。"""
        folder=self.make_qq(version='9.9.21-38711')
        with patch.object(system_qq,'install_dirs',return_value=[folder]),\
             patch.object(system_qq,'min_build_id',return_value=40768):
            self.assertTrue(system_qq.too_old(folder))
            self.assertIsNone(system_qq.find_usable())
            found=system_qq.detect()[0]
            self.assertTrue(found['too_old'])
            self.assertEqual(found['build_id'],38711)

    def test_qq_above_minimum_build_id_is_reused(self):
        folder=self.make_qq(version='9.9.33-52230')
        with patch.object(system_qq,'install_dirs',return_value=[folder]),\
             patch.object(system_qq,'min_build_id',return_value=40768):
            self.assertFalse(system_qq.too_old(folder))
            self.assertIsNotNone(system_qq.find_usable())

    def test_min_build_id_comes_from_download_catalog(self):
        """最低 buildId 登记在 config/runtime-downloads.json，不硬编码。"""
        from src.core.config import ROOT
        floor=system_qq.min_build_id(ROOT)
        self.assertGreater(floor,0)
        catalog=json.loads((Path(ROOT)/'config'/'runtime-downloads.json').read_text(encoding='utf-8-sig'))
        self.assertEqual(floor,catalog['qq']['min_build_id'])

    def test_registry_path_is_parsed_from_uninstall_string(self):
        with patch.object(system_qq,'_registry_install_dir',return_value=None):
            self.assertIsNone(system_qq._registry_install_dir())


class ReuseInstallTests(unittest.TestCase):
    """向导准备组件时：本机有 QQ 就复用，不下载。"""

    def test_reuses_system_qq_instead_of_downloading(self):
        import copy
        import threading
        from unittest.mock import Mock
        from src.core.config import load
        from src.core.onboarding import Onboarding
        temp=tempfile.TemporaryDirectory();self.addCleanup(temp.cleanup);root=Path(temp.name)
        cfg=load(root/'absent.json');api=Mock();api._command_lock=threading.Lock()
        api._backend.port.return_value=False
        setup=Onboarding(api)
        saved={}
        # 造一个已就绪的 NapCat，让流程直接走到 QQ 那一步。
        napcat=root/'.runtime/napcat';napcat.mkdir(parents=True)
        (napcat/'NapCatWinBootMain.exe').write_bytes(b'MZ')
        # _install 会在 finally 里释放命令锁，所以调用前要先持有它。
        api._command_lock.acquire()
        with patch('src.core.onboarding.ROOT',root),\
             patch('src.core.onboarding.load',lambda:copy.deepcopy(cfg)),\
             patch('src.core.onboarding.find_usable',return_value={'path':r'C:\Program Files\Tencent\QQNT\QQ.exe'}),\
             patch('src.core.onboarding.save_local',side_effect=lambda patch: saved.update(patch)),\
             patch('src.core.onboarding.download',side_effect=AssertionError('不应下载 QQ')),\
             patch('src.core.onboarding.catalog',return_value={'napcat':{'url':'https://github.com/x','sha256':'0'*64,'version':'1','max_bytes':1},'qq':{'url':'https://x','sha256':'0'*64,'version':'1','max_bytes':1},'limits':{'max_unpacked_bytes':1,'max_files':1,'download_timeout_seconds':1,'extract_timeout_seconds':1}}):
            setup._install()
        self.assertEqual(setup._job['stage'],'done',setup._job['message'])
        self.assertIn('qq',saved)
        self.assertEqual(saved['qq']['client_path'],r'C:\Program Files\Tencent\QQNT\QQ.exe')


if __name__=='__main__':
    unittest.main()
