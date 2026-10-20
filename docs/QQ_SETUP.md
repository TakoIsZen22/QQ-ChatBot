# QQ 接入

## 推荐：程序内向导

0.9.0起支持“程序设置 → 首次使用 / QQ 接入”，自动下载官方NapCat和独立QQ、校验SHA256、配置本机OneBot和显示二维码。完整步骤见 [新手教程](GETTING_STARTED.md)。Windows绿色包自带Python；源码安装后也可使用同一向导。

下面保留手动接入供维护者排错，不是普通用户的必经步骤。

：NapCat 与本机 OneBot

源码不附带 NapCat、QQ 客户端或登录态。自行准备兼容当前 Windows/NTQQ 的 NapCat 到 `.runtime/napcat`；独立机器人客户端可放到 `.runtime/qq-client`，高级配置 `qq.client_path` 指向其 QQ.exe。不要覆盖或读取日常 QQ 登录态。

1. 设置页填自己的 `owner.qq_id` 和独立 `qq.bot_id`，两者不同，先保持桥接关闭。
2. 按 NapCat 安装说明准备客户端，运行 `tools/setup-napcat.py` 创建配置（已有配置不覆盖）；首次登录用 `tools/start-napcat.bat`，用户本人扫码。脚本不自动下载客户端或伪造登录。
3. HTTP 服务为 `127.0.0.1:3000`；正向 WS 为 `127.0.0.1:3001`，消息格式 array，启用心跳、关闭 reportSelfMessage。本项目不是反向 WS 服务，不要让 NapCat 连 8765。
4. WebUI 也只监听本机；`tools/harden-napcat.py` 保留凭据并收紧地址，首次生成配置后重启核对。不要开放公网。
5. 若 OneBot 设置认证，由用户让进程继承 `NAPCAT_TOKEN`。WebUI token 和 OneBot token 用途不同，不发送到聊天或写文档，代码不生成、索取或复制其值。
6. 启用 QQ 桥接、保存、重启并手动恢复只回复；从自己账号发消息，核对 connected/online 及实际回复。群与非主人消息忽略。

登录后可用 `tools/start-napcat-background.ps1` 后台运行；已有实例不要双开。error 45 应检查客户端兼容性，从可信来源准备合适版本，不能把旧机器版本当作长期标准。

## 断线与补课

先实际收发，再停止 harness（保留 Magpie/NapCat），发新消息后重启，核对 `qq_catchup_complete`；再重启 NapCat，观察受限指数重连与去重。暂停期间收到的消息不自动积压补发，需重新发送。

补课依赖扩展 `get_friend_msg_history`，受 history_limit 与服务端范围限制；`qq_catchup_failed` 不能记作通过。发送超时不自动重发，避免实际已收到却重复发送。
