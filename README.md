# QQ ChatBot

[下载 Windows 桌面版](https://github.com/TakoIsZen22/QQ-ChatBot/releases/latest) · [新手教程](docs/GETTING_STARTED.md) · [CLI / 桌面 Agent 接入](docs/AGENT_WORK.md)

Windows 本机个人 AI 伴侣，版本 **0.10.0**，采用 **MIT** 许可。对话、记忆、日记、人格、QQ 桥接与工具均在本机组织；模型可选默认 Magpie `http://127.0.0.1:3425/v1`，也可直接接入自己的 OpenAI 兼容 API。

QQ ChatBot负责聊天陪伴，不承接工作执行。工作可明确转交给你绑定的通用CLI或桌面Agent（MCP/本机接口），回执单独标注来源。

每份安装服务一个使用者，可交给任意获得用户授权的 Agent 或人工维护，不依赖指定 Agent 产品。

QQ ChatBot 是程序名；「大肥鱼」只是默认伴侣昵称，可在「专属人设」中独立修改，角色形象和程序图标也可自定义。

新增的[聊天小鱼图标 PNG](assets/qq-chatbot-fish-chat-v1.png)与[Windows ICO](assets/qq-chatbot-fish-chat-v1.ico)可在「专属人设 → 程序图标」导入使用，角色形象与昵称分别设置。

QQ群目前仍未接入；[群聊方案](docs/QQ_GROUP_PLAN.md)是后续设计稿。当前版本只回应已配置主人的私聊。

## 下载即用（推荐）

在 GitHub **Releases → Assets** 下载 `qq-chatbot-0.10.0-windows-x64.zip`，完整解压后双击 **QQ ChatBot.exe**，无需手动安装 Python。

首次向导：填写你的 QQ 与独立机器人 QQ → 选择 Magpie 或自己的 API → 点击下载 QQ 组件 → 用机器人账号扫码 → 开启“只回复”。以后双击打开；登录失效时重新扫码。模型访问权限、两个 QQ 账号仍需使用者自行准备。

**[完整新手使用教程](docs/GETTING_STARTED.md)**，也可在“程序设置 → 新手教程”直接阅读。支持 Windows10/11 x64；系统需有 WebView2、.NET/VC 运行库，缺失时教程提供官方安装入口。首次组件下载约350MB，建议3GB可用空间。

仓库自动生成的 Source code ZIP 是源码，不是可执行版。Windows 发布包构建与 GitHub Actions 见 [构建说明](docs/WINDOWS_BUILD.md)。

## 源码运行

模型接入任选一条：已有 Magpie 看 [Magpie 五步接入教程（可选）](docs/MAGPIE_SETUP.md)；没有或不想用 Magpie，看 [自有 API 接入说明](docs/MODEL_API.md)。程序不会要求你先安装 Magpie。

1. 解压到自己的独立目录。准备 Python 3.11 或更新版本；桌面另外需要 Python 3.11、Microsoft Edge WebView2 Runtime，语音也使用独立 3.11 环境。
2. 双击 `tools/install.bat`，再双击 `tools/install-desktop.bat`。源码不包含环境、模型权重、第三方客户端或登录态。
3. 选择 Magpie 时，自己配置并启动本机网关；使用自有 API 时，在设置中选择「自定义 OpenAI 兼容 API」，填写 Base URL 与密钥环境变量名称。不要把凭据发给维护 Agent。
4. 双击桌面“QQ ChatBot”或根目录 `QQ ChatBot.vbs`。在“设置 → 使用者与维护 Agent”填称呼及维护者名称，在“模型与 API 接入”检查连接并选择所选服务的模型 id。
5. 保存并重启聊天，再手动恢复“只回复”。模型 id 因安装而异，默认留空。需要 QQ 时填自己的账号与独立机器人号，打开“程序设置 → 首次使用 / QQ 接入”，下载独立组件并扫码；手动接入见 [QQ 接入](docs/QQ_SETUP.md)。

界面提供对话、总览、长期记忆、日记、专属人设、约定与学习、表情理解、能力与权限、设置、程序设置和运行记录。聊天可选择、粘贴、拖入图片，QQ 图片也可通过辅助视觉路由识别。

程序设置包含开机自启、托盘、主题/字号、备份恢复、诊断与 Agent 巡检。窗口 X 默认收进托盘；真正退出用 Ctrl Q 或托盘菜单。详见 [桌面说明](docs/DESKTOP.md)。

两份接入教程也可在「设置 → 模型与 API 接入」直接打开，支持在程序内阅读；桌面帮助不依赖聊天核心或 Magpie 正在运行。

## 工作转交与 CLI / 桌面 Agent

侧栏“工作转交”可配置通用CLI的固定argv与工作目录，或复制MCP配置接入支持stdio MCP的桌面Agent。默认关闭，保存绑定不自动测试执行。

明确转交：在页面填写并确认，或主人QQ私聊发送 `/工作 具体请求`。聊天模型的建议只生成待确认草稿；不携带完整聊天、记忆、人设或密钥。桌面Agent需主动领取，接入MCP不会自动唤醒另一会话。

**[完整接入教程](docs/AGENT_WORK.md)**。取消、暂停、失败不自动重跑；独立桌面Agent的停止需要它自己配合。维护监管名称与真正工作绑定分别设置。

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
- `model.provider/base_url`：Magpie 或自定义 OpenAI 兼容 API；`main/auxiliary` 为所选服务的模型 ID，共用该地址。设置页可检查连接和读取清单，也可手填模型。`model.key_env`、`qq.token_env` 只存环境变量名称。密钥通过 Windows 用户环境变量自行配置，完整步骤见 [API 接入](docs/MODEL_API.md)。
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

生成 `dist/qq-chatbot-0.10.0.zip`，只含白名单源码、通用配置与文档，附文件哈希清单；排除 Git 历史、私人配置、人设、数据、环境和登录态。将干净包解压到新目录再创建公开仓库，避免上传本机旧历史。工具不创建仓库或推送。见 [发布步骤](docs/RELEASING.md)。

原创代码与文档为 [MIT](LICENSE)，第三方素材与依赖见 [NOTICE](NOTICE.md)；原图的第三方角色权利不由代码许可重新授予。
