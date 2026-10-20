"""产品显示名与兼容标识；改名不迁移私人数据或破坏旧版服务的维护。"""
NAME='QQ ChatBot'
APP_ID='dafeiyu-harness'
LEGACY_NAME='大肥鱼 Harness'


def is_harness(status):
    if not isinstance(status,dict):return False
    if 'app_id' in status:return status['app_id']==APP_ID
    return status.get('name') in (NAME,LEGACY_NAME)
