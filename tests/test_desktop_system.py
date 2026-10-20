"""程序壳回归：不触碰本机自启、真实服务、正式数据或系统托盘。"""
import json
import copy
import os
import re
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
from src.core.config import load
from src.core.desktop_api import DesktopApi
from src.core.desktop_platform import WindowsIntegration,RUN_KEY,VALUE_NAME,LEGACY_VALUE_NAME,APP_KEY
from src.core.product import is_harness,NAME,APP_ID,LEGACY_NAME
from src.core.desktop_maintenance import DesktopMaintenance
from src.core.desktop_lifecycle import DesktopLifecycle
from tools.manage import manifest
from src.core.service_intent import ServiceIntent


def normalize_path(command):
    """从命令行里取出绝对路径并规范化，忽略 Windows 8.3 短名与大小写差异。

    8.3 短名（RUNNER~1 / DESKTO~1.PY）与长名指向同一文件，
    但字符串不同，CI 上按字符串比较会误判失败。
    """
    parts=re.findall(r'"[^"]+"|\S+',command)
    candidates=[p.strip('"') for p in parts if p.strip('"').startswith(('C:\\','D:\\','E:\\','%')) or p.strip('"').startswith(('/',))]
    for raw in candidates:
        # 优先取脚本本身（.py），命令行里常同时有解释器（.exe）。
        if not raw.lower().endswith('.py'):continue
        if os.path.exists(raw):
            # 用 realpath 把 8.3 短名还原成长名；同一文件即可判定相等。
            try:raw=os.path.abspath(os.path.realpath(raw))
            except OSError:pass
        return os.path.normcase(raw)
    return ''


class FakeKey:
    def __init__(self,name):self.name=name
    def __enter__(self):return self
    def __exit__(self,*args):pass


class FakeRegistry:
    HKEY_CURRENT_USER='HKCU';REG_SZ=1;REG_DWORD=4
    def __init__(self):self.values={}
    def OpenKey(self,hive,key):
        if key not in self.values:raise FileNotFoundError()
        return FakeKey(key)
    def CreateKey(self,hive,key):self.values.setdefault(key,{});return FakeKey(key)
    def SetValueEx(self,key,name,reserved,kind,value):self.values[key.name][name]=value
    def QueryValueEx(self,key,name):
        if name not in self.values[key.name]:raise FileNotFoundError()
        return self.values[key.name][name],1
    def DeleteValue(self,key,name):del self.values[key.name][name]
    def DeleteKey(self,hive,key):del self.values[key]


class DesktopSystemTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.cfg=load(self.root/'missing.json')
        self.backend=Mock();self.backend.port.return_value=False
        self.backend.request.return_value={'name':'大肥鱼 Harness','busy':False,'queue':0,'mode':'reply_only','chat':'private text','qq_bot_id':'private id'}
        self.patches=[patch('src.core.desktop_api.load',side_effect=lambda:copy.deepcopy(self.cfg)),patch('src.core.desktop_api.ROOT',self.root),patch('src.core.desktop_api.save_local'),patch('src.core.desktop_lifecycle.load',return_value=self.cfg),patch('src.core.desktop_lifecycle.ROOT',self.root),patch('src.core.desktop_maintenance.load',return_value=self.cfg)]
        for p in self.patches:p.start();self.addCleanup(p.stop)
        self.api=DesktopApi(self.backend);self.registry=FakeRegistry()
        self.api._integration=WindowsIntegration(self.root,self.registry)
        self.api._maintenance=DesktopMaintenance(self.root)

    def snapshot(self):
        folder=self.root/'backups/20261020-100000-123456';(folder/'data').mkdir(parents=True)
        (folder/'data/example.jsonl').write_text('{"value":1}\n',encoding='utf-8')
        (folder/'manifest.json').write_text(json.dumps({'files':manifest(folder/'data'),'jsonl_counts':{'example.jsonl':1}}),encoding='utf-8')
        return folder

    def test_startup_uses_current_user_and_absolute_launcher(self):
        integration=self.api._integration
        self.assertFalse(integration.startup()['registered'])
        integration.set_startup(True);cmd=self.registry.values[RUN_KEY][VALUE_NAME]
        # Windows 可能把同一目录写成 8.3 短名（RUNNER~1），只比较规范化后的路径。
        self.assertEqual(normalize_path(cmd),normalize_path(f'{self.root}{os.sep}tools{os.sep}desktop-launch.py'))
        self.assertIn('--startup',cmd)
        self.assertNotIn('-m src.desktop',cmd)
        self.assertTrue(integration.startup()['registered'])
        integration.set_startup(False);self.assertFalse(integration.startup()['registered'])

    def test_custom_icon_is_used_for_registry_and_shortcut_registration(self):
        custom=self.root/'data/persona/appearance/icon-example.ico'
        identity=Mock();identity.image_path.return_value=custom
        with patch('src.core.desktop_platform.installed_identity',return_value=identity),patch('src.core.desktop_platform.subprocess.run') as run:
            self.api._integration.register()
        self.assertEqual(self.registry.values[APP_KEY]['DisplayIcon'],str(custom))
        args=run.call_args.args[0]
        self.assertEqual(args[args.index('-IconPath')+1],str(custom))

    def test_parallel_portable_install_does_not_steal_registered_application(self):
        self.registry.values[APP_KEY]={'InstallLocation':str(self.root/'other'),'DisplayVersion':'fixture'}
        before=copy.deepcopy(self.registry.values)
        with patch('src.core.desktop_platform.subprocess.run') as run:
            result=self.api._integration.register()
        self.assertFalse(result['registered']);self.assertEqual(self.registry.values,before);run.assert_not_called()

    def test_product_rename_migrates_enabled_startup_without_duplicate_entry(self):
        integration=self.api._integration;command=integration.command('--startup')
        self.registry.values[RUN_KEY]={LEGACY_VALUE_NAME:command}
        self.assertTrue(integration.startup()['registered'])
        with patch('src.core.desktop_platform.subprocess.run'):integration.register()
        self.assertEqual(self.registry.values[APP_KEY]['DisplayName'],'QQ ChatBot')
        self.assertEqual(self.registry.values[RUN_KEY],{VALUE_NAME:command})

    def test_startup_cleanup_only_removes_this_installation_and_keeps_foreign_entries(self):
        integration=self.api._integration;own=integration.command('--startup');foreign='another installation'
        self.registry.values[RUN_KEY]={VALUE_NAME:foreign,LEGACY_VALUE_NAME:own}
        with self.assertRaisesRegex(ValueError,'其他安装'):integration.set_startup(True)
        integration.set_startup(False)
        self.assertEqual(self.registry.values[RUN_KEY],{VALUE_NAME:foreign})

    def test_renamed_service_identity_accepts_old_installation_but_rejects_wrong_service(self):
        self.assertTrue(is_harness({'name':NAME,'app_id':APP_ID}))
        self.assertTrue(is_harness({'name':LEGACY_NAME}))
        self.assertFalse(is_harness({'name':NAME,'app_id':'some-other-app'}))
        self.assertFalse(is_harness({'name':'unrelated'}));self.assertFalse(is_harness(None))

    def test_preferences_are_validated_and_registry_rolls_back_on_save_error(self):
        with self.assertRaises(ValueError):self.api.preferences({'theme':'invalid'})
        with self.assertRaises(ValueError):self.api.preferences({'shell':'calc.exe'})
        with patch('src.core.desktop_api.save_local',side_effect=OSError('disk full')):
            with self.assertRaises(OSError):self.api.preferences({'start_with_windows':True})
        self.assertFalse(self.api._integration.startup()['registered'])

    def test_unregister_only_removes_own_integration_and_keeps_data(self):
        integration=self.api._integration;integration.set_startup(True)
        self.registry.values[APP_KEY]={'InstallLocation':str(self.root)}
        (self.root/'data').mkdir();(self.root/'data/memory.jsonl').write_text('{}\n')
        with patch('src.core.desktop_platform.subprocess.run'):
            self.assertTrue(integration.unregister()['data_preserved'])
        self.assertTrue((self.root/'data/memory.jsonl').exists())
        self.assertNotIn(APP_KEY,self.registry.values)
        self.registry.values[APP_KEY]={'InstallLocation':str(self.root/'other')}
        integration.set_startup(True)
        with self.assertRaises(ValueError):integration.unregister()
        self.assertTrue(integration.startup()['registered'])

    def test_windows_logout_is_not_cancelled_by_tray_close_behavior(self):
        life=DesktopLifecycle(self.api);life.tray_available=True
        args=SimpleNamespace(CloseReason='WindowsShutDown',Cancel=True)
        life._allow_windows_shutdown(None,args)
        self.assertFalse(args.Cancel);self.assertTrue(life.on_closing())

    def test_explicit_stop_prevents_supervisor_restart(self):
        self.api.command('stop');self.api._recover_once(10)
        self.backend.start_all.assert_not_called()
        self.api.command('start');self.api._recover_once(20)
        self.assertEqual(self.backend.start_all.call_count,2)

    def test_recovery_has_window_limit_and_does_not_clear_safety(self):
        for t in (1,2,3,4,5):self.api._recover_once(t)
        self.assertEqual(self.backend.start_all.call_count,3)
        self.api._recover_once(400);self.assertEqual(self.backend.start_all.call_count,4)
        self.backend.request.assert_not_called()

    def test_external_manual_stop_is_respected_by_supervisor(self):
        ServiceIntent(self.root).write(False,'maintenance_stop')
        self.api._recover_once(10)
        self.backend.start_all.assert_not_called()
        self.api.command('start')
        self.assertTrue(ServiceIntent(self.root).desired())

    def test_closing_uses_tray_but_exit_and_missing_tray_are_distinct(self):
        life=DesktopLifecycle(self.api);life.window=Mock();life.tray_available=True
        with patch('src.core.desktop_lifecycle.threading.Thread') as thread:
            self.assertFalse(life.on_closing());thread.assert_called_once()
        life.tray_available=False;self.assertTrue(life.on_closing())
        with self.assertRaises(RuntimeError):life.action('hide')
        life.tray_available=True
        with patch('src.core.desktop_lifecycle.threading.Timer'):
            life.action('exit_ui')
        self.assertTrue(life.on_closing());self.backend.stop_all.assert_not_called()

    def test_exit_all_stops_own_services_before_window(self):
        lifecycle=Mock();self.api._bind_lifecycle(lifecycle)
        self.api.window_action('exit_all')
        self.backend.stop_all.assert_called_once();lifecycle.action.assert_called_once_with('exit_all')
        with self.assertRaises(PermissionError):self.api.window_action('shell')

    def test_geometry_survives_restart_and_rejects_offscreen_values(self):
        life=DesktopLifecycle(self.api);life._geometry={'width':1200,'height':800,'x':-999999,'y':-999999};life._save_geometry()
        new=DesktopLifecycle(self.api);saved=new.geometry()
        self.assertEqual(saved['width'],1200);self.assertNotIn('x',saved)

    def test_backup_validation_refuses_traversal_and_tampered_snapshot(self):
        folder=self.snapshot();service=self.api._maintenance
        self.assertTrue(service.verify(folder.name)['verified'])
        for name in ('../config','C:/private','before-restore-20261020'):
            with self.assertRaises(ValueError):service.backup_path(name)
        (folder/'data/example.jsonl').write_text('{"value":2}\n',encoding='utf-8')
        with self.assertRaises(ValueError):service.verify(folder.name)

    def test_backup_stops_then_restarts_without_unpausing(self):
        self.backend.port.return_value=True
        self.api._maintenance.run=Mock(return_value={'name':'snapshot'})
        result=self.api.maintenance('backup',confirmation='backup')
        self.backend.stop_core.assert_called_once();self.backend.start_core.assert_called_once()
        self.assertIn('保持暂停',result['message'])
        self.backend.request.assert_called_once_with('status')

    def test_busy_backup_is_refused_without_stopping(self):
        self.backend.port.return_value=True;self.backend.request.return_value={'busy':True}
        with self.assertRaises(RuntimeError):self.api.maintenance('backup',confirmation='backup')
        self.backend.stop_core.assert_not_called();self.backend.start_core.assert_not_called()

    def test_restore_requires_confirmation_and_leaves_core_stopped(self):
        folder=self.snapshot();self.api._maintenance.run=Mock(return_value={'restored':folder.name})
        with self.assertRaises(ValueError):self.api.maintenance('restore',folder.name)
        self.backend.port.return_value=True
        self.api.maintenance('restore',folder.name,'restore')
        self.backend.stop_core.assert_called_once();self.backend.start_core.assert_not_called()
        self.assertFalse(self.api._desired_services)

    def test_diagnostics_export_excludes_chat_qq_account_and_config_values(self):
        report=self.api.maintenance('export_diagnostics')
        contents=Path(report['path']).read_text(encoding='utf-8')
        self.assertNotIn('private text',contents);self.assertNotIn('private id',contents)
        self.assertNotIn('key_env',contents);self.assertNotIn('token_env',contents)
        self.assertIn('version',contents)


if __name__=='__main__':unittest.main()
