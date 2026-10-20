# QQ ChatBot 原创 QQ 适配层

host.cpp 嵌入固定官方 QQNT 自带 Node/V8；entry.js → session.js 手动二维码与独立路径会话 → driver.js/protocol.js → gateway.js 本机 HTTP/NDJSON → modules/qq_bridge.py → Harness/Safety。无 npm 依赖，不读密码、保存账号清单或登录票据。

Windows 宿主构建：python tools/build-native-host.py。源码、固定 ABI、哈希与状态说明见 ../../docs/NATIVE_QQ.md。官方客户端由使用者在向导另行下载，不随本项目分发。bootstrap.js 仅保留兼容旧实验入口，正式宿主不使用它或修改 QQ 的 package.main。

启动扫码是手动动作，保留暂停。真实收发及不同安装的验收范围见 ../../docs/ACCEPTANCE.md；历史补拉、语音附件、图片上传和群发送未支持。

测试：node --test tests/qq-native.test.js。
