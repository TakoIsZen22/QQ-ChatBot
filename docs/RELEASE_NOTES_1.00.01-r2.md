# QQ ChatBot 1.00.01 · 自有 API 版（r2 修订）

仅使用自有 OpenAI 兼容 API。下载 `qq-chatbot-1.00.01-windows-x64.zip`，完整解压后双击 `QQ ChatBot.exe`；`qq-chatbot-1.00.01.zip` 为源码包。两者均附 SHA256 校验文件。程序内版本号保留 **1.00.01**。

本次删除外部 Agent / CLI 绑定、工作转交页面、工作 MCP 桥与模型转交工具。旧配置中的 `agent_link` 加载时忽略，旧任务记录保留在本机，不读取或恢复执行。聊天、记忆、人设、日记、只读群监听和维护巡检继续保留。

升级前退出旧程序并备份原目录；将新版解压到新目录，按 HANDOFF.md 恢复数据与附件，再启动并保持暂停核对。不要把旧版源码或 EXE 覆盖回新版；需要回滚时退出新版，使用备份的旧目录，勿同时启动两套程序。

验证：153 项 Python 测试、11 项 Node 协议测试；首次向导使用隔离 WebView2 与本机协议夹具验证。未调用外部模型或发送 QQ 消息。新机器真实扫码与私聊收发仍需独立验收。群 AI 回复、群记忆、历史补拉、QQ 语音取文件与图片上传发送尚未实现。

首次运行需要自己的主人号、独立机器人号和 API；默认全部暂停，账号和密钥不随包分发。教程见 README.md、docs/GETTING_STARTED.md、docs/EDITIONS.md。需要可选 Magpie 接入可选 [1.00.02-r2](https://github.com/TakoIsZen22/QQ-ChatBot/releases/tag/v1.00.02-r2)。

MIT；第三方及素材声明见 NOTICE.md。原有 v1.00.01 标签保留。
