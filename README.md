# QQ ChatBot

[下载 Windows 桌面版](https://github.com/TakoIsZen22/QQ-ChatBot/releases/latest) · [新手教程](docs/GETTING_STARTED.md)

Windows 本机个人 AI 伴侣，采用 **MIT** 许可。本次提供两种发行版本，聊天、记忆、人设与 QQ 功能相同，区别在模型接入方式：

| 版本 | 模型接入 | Windows 包 |
|---|---|---|
| **1.00.01** | 仅自有 OpenAI 兼容 API，地址由使用者填写 | [Windows ZIP](https://github.com/TakoIsZen22/QQ-ChatBot/releases/download/v1.00.01-r2/qq-chatbot-1.00.01-windows-x64.zip) |
| **1.00.02** | 自有 API + 可选 Magpie 本机网关 | [Windows ZIP](https://github.com/TakoIsZen22/QQ-ChatBot/releases/download/v1.00.02-r2/qq-chatbot-1.00.02-windows-x64.zip) |

两包均自带 Python 与桌面启动器；1.00.02 的 Magpie 接入使用 `http://127.0.0.1:3425/v1`，不捆绑安装 Magpie。[版本选择、安装与切换](docs/EDITIONS.md)。源码主分支为 1.00.02，1.00.01 由同一份源码经发行脚本生成。

QQ ChatBot负责聊天、陪伴与记忆，不提供外部 Agent、CLI 绑定或工作转交。

当前下载为 **r2 修订**，已移除工作绑定；程序内版本号与模型接入差异仍为 1.00.01 / 1.00.02。旧 Release 保留用于回滚。

每份安装服务一个使用者，可交给任意获得用户授权的 Agent 或人工维护，不依赖指定 Agent 产品。

QQ ChatBot 是程序名；「大肥鱼」只是默认伴侣昵称，可在「专属人设」中独立修改，角色形象和程序图标也可自定义。

两个版本使用新提供的图片作为[默认图标 PNG](assets/xiaojing-user-icon.png)及[Windows ICO](assets/xiaojing-user-icon.ico)；「专属人设 → 程序图标」仍可自行更换。

侧栏新增[群聊监听](docs/GROUP_MONITOR.md)：手动添加多个群，单群切换或多窗并排查看实时消息，群备注和监听开关可在程序中修改。监听只保存本机记录，不调用模型或回复；聊天仍只回应已配置主人的私聊。[群内回复方案](docs/QQ_GROUP_PLAN.md)仍为后续设计稿。

## 安装与当前 QQ 状态

两个版本沿用已验证的原创 Windows QQ 宿主，加载固定官方 QQ 内核，向导支持下载、扫码、刷新与停止。此前本机已完成真实机器人登录、主人文字接收和经 Harness/Safety 的模型回复，用户确认收到。新安装仍需独立验收；真实断网恢复、群接收和 QQ 媒体尚待验证，历史补拉/语音取文件/图片上传发送未实现。

Windows包需与本版本一致，完整解压后双击QQ ChatBot.exe。旧版发布资产不能代表新版能力；Source code ZIP需按下面步骤安装环境。[完整教程](docs/GETTING_STARTED.md)可在程序内阅读。构建说明见[WINDOWS_BUILD](docs/WINDOWS_BUILD.md)。

## 源码运行

1.00.01 按 [自有 API 接入说明](docs/MODEL_API.md)配置。1.00.02 可使用同一教程，也可按 [Magpie 五步接入教程（仅 1.00.02，可选）](docs/MAGPIE_SETUP.md)配置已有网关。程序不会要求你先安装 Magpie。

1. 解压到自己的独立目录。准备 Python 3.11 或更新版本；桌面另外需要 Python 3.11、Microsoft Edge WebView2 Runtime，语音也使用独立 3.11 环境。
2. 双击 `tools/install.bat`，再双击 `tools/install-desktop.bat`。源码不包含环境、模型权重、第三方客户端或登录态。QQ 源码运行另需 Visual Studio C++ x64 工具链与 Windows SDK，执行 `python tools/build-native-host.py`；Windows 桌面包已内置自写宿主。
3. 选择 Magpie 时，自己配置并启动本机网关；使用自有 API 时，在设置中选择「自定义 OpenAI 兼容 API」，填写 Base URL 与密钥环境变量名称。不要把凭据发给维护 Agent。
4. 双击桌面“QQ ChatBot”或根目录 `QQ ChatBot.vbs`。在“设置 → 使用者与维护 Agent”填称呼及维护者名称，在“模型与 API 接入”检查连接并选择所选服务的模型 id。
5. 保存并重启聊天，再手动恢复“只回复”。模型 id 因安装而异，默认留空。QQ 在首次向导保存双账号、准备官方组件后手动扫码；收发与限制见 [QQ 接入](docs/QQ_SETUP.md)。

界面提供对话、总览、长期记忆、日记、专属人设、约定与学习、表情理解、能力与权限、设置、程序设置和运行记录。聊天可选择、粘贴、拖入图片，QQ图片路径已有受限CDN识图逻辑，真实QQ媒体仍待验收。

程序设置包含开机自启、托盘、主题/字号、备份恢复、诊断与 Agent 巡检。窗口 X 默认收进托盘；真正退出用 Ctrl Q 或托盘菜单。详见 [桌面说明](docs/DESKTOP.md)。

接入教程可在「设置 → 模型与 API 接入」直接阅读；1.00.01 仅显示自有 API 教程，1.00.02 同时显示 Magpie 教程。桌面帮助不依赖聊天核心正在运行。

## 任意 Agent 监管

将 [AGENTS.md](AGENTS.md)、[HANDOFF.md](HANDOFF.md) 和 [监管说明](docs/AGENT_SUPERVISION.md) 交给所选 Agent。

```powershell
# 从项目根目录运行，只读，不发消息或调用模型
.\.venv\Scripts\python.exe tools\supervise.py --json
```

固定 schema 为 `dafeiyu.supervision.v1`，退出码 0/1 表示通过/存在不可用项。相同入口在“程序设置 → Agent 监管”。维护 Agent 名称仅是交接信息，不自动授权、登录或启动 Agent。定期巡检和通知渠道由使用者在自己的 Agent/调度器配置，不继承原作者的任务或收件人。

## 配置与人设

默认值在 `config/settings.json`，本机覆盖在不入库的 `config/local.json`，参考 `config/local.example.json`。界面保存写本机覆盖，运行配置一般重启生效，保命开关立即生效。

- `owner.name/qq_id`：使用者称呼与 QQ；`qq.bot_id`：独立机器人。更换使用者请使用独立目录，不共用记忆和登录态。
- `maintenance.agent_name`：任意维护 Agent 或人工维护者名称。
- `model.provider/base_url`：Magpie 或自定义 OpenAI 兼容 API；`main/auxiliary` 为所选服务的模型 ID，共用该地址。设置页可检查连接和读取清单，也可手填模型。`model.key_env` 只存模型密钥环境变量名称。密钥通过 Windows 用户环境变量自行配置，完整步骤见 [API 接入](docs/MODEL_API.md)。
- 侧栏「专属人设」可导入、编辑和预览 `soul.md`，保存后下一轮对话生效，无需重启。私人文件默认在 `data/persona/soul.md`，版本历史同属 data，随备份恢复且不进入公开包。空白模板在 `src/persona/soul.example.md`。旧 `role.card` 仍可作为基础卡使用。
- 「专属人设」顶部可独立设置角色昵称、角色形象和程序图标，点「保存角色资料」应用。昵称同步界面与后续对话；形象用于聊天头像和角色卡；图标同步窗口、任务栏、托盘及桌面/开始菜单快捷方式。支持静态 PNG/JPG/WEBP，图标另支持 ICO，单张最多 2 MB；保留整张图片比例。可分别或全部恢复默认，再保存确认。形象文字描述会进入对话，上传图片不会自动调用模型。自定义资料与素材只存私有 data，不进入公开源码包。
- 主动、音乐控制、ADB、联网学习、插件/MCP、人格演化默认关闭；语音仅本机 Whisper。准备步骤见 [功能配置](docs/FEATURES.md)。

保留全暂停、只回复、群静默；QQ 单聊 ≤20 条/分钟、群更慢；不可撤回操作至少间隔 10 分钟、每天 ≤3 次。不加陌生人、不自动同意好友、不群 @全体、不操作支付或银行 App。

## 数据与维护

`data/` 保存 JSONL 与媒体附件。先停机再复制完整 data 即可备份，不能漏掉 `data/media/`；配置单独保存。备份是私人文件，不能随源码上传。

```powershell
.\tools\health.bat
.\tools\test.bat
.\tools\stop.bat
$snapshot = & '.\.venv\Scripts\python.exe' 'tools\manage.py' 'backup'
& '.\.venv\Scripts\python.exe' 'tools\manage.py' 'restore' $snapshot
.\tools\start.bat
```

运维见 HANDOFF，结构见 [架构文档](架构文档.md)，验证边界见 [验收说明](docs/ACCEPTANCE.md)。新用户必须实测自己的账号和设备，源码测试不代表它们可用。

## 分享与发布

```powershell
.\.venv\Scripts\python.exe tools\package-release.py
```

生成主源码包 `dist/qq-chatbot-1.00.02.zip`，只含白名单源码、通用配置与文档，附文件哈希清单；排除 Git 历史、私人配置、人设、数据、环境和登录态。双版本构建使用 `python tools/build-editions.py`，同时生成 1.00.01 与 1.00.02 的源码和 Windows 包。向已有公开仓库提交时，以远程主分支为基础更新干净源码，不上传本机旧历史。工具不创建仓库或推送。见 [发布步骤](docs/RELEASING.md)。

原创代码与文档为 [MIT](LICENSE)，第三方素材与依赖见 [NOTICE](NOTICE.md)；原图的第三方角色权利不由代码许可重新授予。

自写桥接架构、限制与回滚见 [研发说明](docs/NATIVE_QQ.md)。
