# 通用维护 Agent 交接手册

适用于任意获得使用者授权的 Agent 或人工维护者，不依赖指定产品。所有命令从当前安装的项目根目录执行。先读 AGENTS.md、docs/AGENT_SUPERVISION.md 和 docs/ACCEPTANCE.md，不操作其他项目。

## 0. 接手与安装状态

产品显示名为 QQ ChatBot，默认伴侣昵称仍为大肥鱼。桌面与开始菜单入口为「QQ ChatBot」，根目录启动器为 `QQ ChatBot.vbs`，发布包前缀为 `qq-chatbot-`。昵称修改不会覆盖左侧产品品牌。

当前源码版本 1.00.02；同时发行 1.00.01（仅自有 API）与 1.00.02（自有 API + 可选 Magpie）。源码包不包含环境、运行数据、账号配置、个人角色卡、第三方客户端或登录态；按 README 安装，不把旧安装的登录与验收状态当作本机状态。

发行差异与逐步教程见 docs/EDITIONS.md。`src/version.py` 决定版本，`src/core/edition.py` 返回能力并拒绝不支持的 provider，`model_endpoint.py` 在配置、探测和模型请求前统一校验。1.00.01 允许全空模型的首次启动；填模型前必须有有效 Base URL。所有推理仍经 `modules/model.py`，不另建网络出口。1.00.02 沿用当前本机配置，不因构建另一版本而改动它。

`tools/build-editions.py` 从隐私白名单源码创建两个隔离构建目录，`tools/release_editions.py` 设置各版公开配置、版本、设置页和向导入口；各自再次校验后生成源代码与 Windows ZIP。构建步骤与回滚见 docs/EDITIONS.md。1.00.01 不能直接使用旧 Magpie 的 local.json，切换时按新安装在界面重配，再恢复 JSONL 与附件。两版默认图标均为使用者提供的新图，图标位置见 assets/README.md。

首先运行 tools/supervise.py --json（使用本安装的 .venv Python），只读检查版本、端口、暂停与已启用的 QQ。默认模型、QQ 账号留空，高权限关闭。设置页可改称呼、QQ 和维护 Agent 名称；名称是交接信息，不自动启动或授权 Agent。

定期巡检频率、通知渠道与修复权限由使用者在所选 Agent 中配置。更换 Agent 时停用旧调度再交接，更新源码不会迁移或删除现有外部任务。内置托盘恢复器与外部监管的边界见监管说明。

## Windows 绿色包与首次使用

普通使用者按接入方式选择 1.00.01 或 1.00.02 的 Windows 包，完整解压后双击 `QQ ChatBot.exe`，配置模型并使用本机聊天。首次向导可手动扫码。此前本机真实主人文字收发已通过；不同安装、群消息及断网恢复分别验收。教程在 docs/GETTING_STARTED.md 与程序内。源码包仍按原环境安装；下文 `.venv` 命令为源码运行方式。

**绿色包维护入口用 `_runtime/python.exe`，不要找不存在的 `.venv`：**

```powershell
# 从当前绿色包根目录执行，只读
& '.\_runtime\python.exe' 'tools\supervise.py' '--json'
& '.\_runtime\python.exe' 'tools\manage.py' 'health'
```

Hermes或任意维护Agent的独立签收流程：

1. 记录当前版本、模型ID与暂停模式，等busy=false且queue=0。托盘选择“退出并停止全部”；双击QQ ChatBot.exe，确认同一安装重启、QQ状态和保命模式。人工停止/重启保留暂停，需要用户手动恢复只回复。
2. 换模型：设置页记录旧ID，检查连接读取真实ID，保存新ID→重启聊天→核对状态；再恢复原ID并重启。没有第二个可用模型时明确标注待验收，不能编造。
3. 备份：程序设置→创建快照；或完全停止后执行下面命令，保留输出的完整快照路径。快照包含JSONL、媒体、私人soul与形象；config/local.json与QQ登录态不在data快照内，按需私下另存。
4. 恢复：GUI选择快照→验证→恢复；或保持聊天停止执行restore；对照原快照manifest核验JSONL数与附件SHA256。恢复会保留before-restore，保持停止；核对后双击EXE手动开始只回复。

```powershell
& '.\_runtime\python.exe' 'tools\manage.py' 'stop'
$snapshot = & '.\_runtime\python.exe' 'tools\manage.py' 'backup'
& '.\_runtime\python.exe' 'tools\manage.py' 'restore' $snapshot
```

构建：tools/build-windows.py→dist Windows ZIP，tools/package-release.py→干净源码ZIP。仓库Actions见.github/workflows/windows-release.yml。运行时/下载规则在core/runtime_paths.py、runtime_downloads.py、onboarding.py，GUI在channel/ui/desktop/onboarding.js/.css；均通过DesktopApi固定白名单调用，组件下载持有服务操作锁，安全暂停接口独立。下载清单集中config/runtime-downloads.json，固定官方HTTPS、SHA256和大小限制；不悄悄换镜像。已有组件与登录目录不覆盖。自写桥接随源码提供；向导仅可选下载官方独立QQ，不提供外部桥接管理页。

跨机器恢复时独立QQ绝对路径需在新向导重新准备，API环境变量由使用者重新设。首次模型下载/QQ设备验证/扫码不由维护Agent代为完成。若官方组件下架或结构变更，先更新清单与适配器并重验，不能删除登录态、取消哈希校验或操作日常QQ。WebView2与Windows .NET/VC/UCRT仍是系统前提，未内置自动修复。

## 聊天与外部工作边界

QQ ChatBot定位为聊天伴侣；工作通过明确转交由使用者自己的Agent执行。工作通道与maintenance.agent_name监管名称无关。侧栏“工作转交”可绑定通用CLI或桌面Agent，说明见docs/AGENT_WORK.md。

- core/agent_link.py：独立事件队列、固定argv CLI子进程、桌面领取/回执与取消；core/agent_mcp.py：仅工作队列的stdio MCP服务，入口tools/agent-mcp.py；tools/agent-link.py为本机CLI适配。
- Harness组合注入AgentLink；/工作只发送当前文字，历史/媒体不自动转交。模型agent_work_offer只建待确认草稿，无命令和任意上下文参数。
- channel/local_ui.py提供agent-work（使用者）、agent-binding（热保存）、agent-inbox（外部桌面Agent）固定接口，桌面桥只开放前两者。前端agent-work.js/.css，公开帮助白名单增加agent教程。
- 配置agent_link：enabled/name/transport(cli/desktop)/command(JSON argv)/cwd/notify_result/timeout_seconds/max_task_chars/max_output_bytes/max_result_chars/pending_limit/history_limit。默认禁用、无本机路径；凭据在外部Agent自身，不在本配置。
- data/agent_tasks.jsonl含正文与回执，全量备份覆盖；退出或恢复后未完成工作标为interrupted，不自动重发。更换Agent需先完成/取消已有工作；桌面取消待其确认。
- 全暂停取消排队并停止自有CLI进程树；外部桌面Agent只能请求取消，不能保证其已停。回执不是系统指令，不调用模型执行结果。默认不发回QQ，可选短回执遵守暂停/免打扰/配额。
- 状态agent_active反映未完成工作；程序维护/改首次设置/普通重启前要求先处理工作，强制停止仍可用于保命。不要把Agent正在执行当成聊天核心空闲而重启。只读监管不领取或执行工作。

验收要分别做：CLI的真实非交互stdin/最终stdout；桌面客户端的MCP配置、明确授权领取与回执。已有本机夹具不代替第三方Agent实连；本次没有替用户安装/登录或派发真实工作。

## 1. 十二模块地图

### 自写 QQ 宿主与通道

`core/native_host.py` → `qq_native/host.cpp` 宿主 → 官方固定 QQNT 的 Node/V8 → `qq_native/entry.js/session.js` → `driver.js/protocol.js/gateway.js` → `modules/qq_bridge.py` → Harness/GroupMonitor。发送经 Safety，不直接调用原生发送绕过暂停。兼容版本与文件哈希集中 `config/qq-native-compat.json`，本机端口 `qq.native_port=3002`。完整 ABI/生命周期见 docs/NATIVE_QQ.md。

Windows 包内置 `_tools/qq-native/QQChatBot.NativeHost.exe`；源码先执行 `python tools/build-native-host.py`，需 VS C++ x64 与 Windows SDK，输出 `.runtime/native-host`。官方 QQ 由向导另行下载到 `.runtime/qq-client`，新宿主不修改 package.main、不启动日常 QQ、不自动读取保存账号。旧 prepare 安装先停止宿主后 restore，不能覆盖变化的原文件。

程序设置→首次使用/QQ接入→保存双账号与模型→准备组件→扫码接入→机器人手机确认。二维码过期点刷新；账号错误/无法恢复的离线状态先停止QQ再手动扫码。启动、停止命令为 `tools/qq-native.py start/stop`，刷新为 `refresh`；Python 路径遵循源码/绿色包差别。桌面开机自启与恢复器仅启动核心，QQ 必须手动登录；仅退出界面保留当前QQ。停止按 PID/映像/创建时间/run_id 核对本项目进程，不批量结束 QQ。

私有 `.runtime/qq-native/profile` 下保存引擎全局、账号、下载与重定向 APPDATA/LOCALAPPDATA。是路径配置隔离，不是OS沙箱；不要声称官方内核全部访问已审计。`host-output.log` 可能有敏感原生登录材料，禁止复制到 issue 或打印；诊断仅用脱敏 state/events 和 doctor。data 快照不含QQ登录目录，需要另存时先停止QQ，再私下复制 profile 与 config/local.json。日志、去重和配额不清除。

本机正式宿主：真实扫码、机器人身份校验、主人文字接收、经模型与Harness/Safety发送、用户确认收到、随后恢复暂停已通过。真实断网重连、白名单群、多机安装及QQ媒体待验收；历史补拉、语音附件获取、图片上传发送尚未实现。每次宿主启动后主人先发新消息以学习其UID；不自动重发不确定发送或旧暂停消息。原生群白名单在启动时截取，新增或重新开启群需手动停止并启动QQ，停用/移除核心立即过滤。

只读 `tools/qq-native.py doctor` 分层核对客户端、固定哈希、自有宿主、网关及在线状态；旧状态/二维码/端口不能当成登录成功。`launch_available`只表示允许手动扫码，不是新安装已验收。回滚先保持暂停、停止QQ与核心、备份数据/附件/本机配置，换回可信源码，保留profile/日志/配额，旧版不自动启动新版宿主。

### 独立群监听

`modules/group_monitor.py` 属于通道模块9的只读扩展，由 Harness 注入 QQBridge。群 `post_type=message/message_type=group` 只交 GroupMonitor，随后返回；不会到 receive/worker、私人记忆、人设或 AgentLink，没有群发送动作。`channel/local_ui.py` 的 `/api/group-monitor` GET 提供白名单、连接与最近事件时间；GET `?group_id=群号` 返回该群有限条记录；POST 仅允许 add(group_id/name)、update(group_id/name/enabled)、remove(group_id)，字段严格校验，保留 Host/Origin/本机头限制。配置修改先 validate/save_local 成功再热替换。

配置 `group_monitor` 集中在 settings/local：`groups` 默认空，`max_groups=12/history_limit=100/max_text_chars=2000`；程序内管理群列表。记录私有 `data/groups/<id>/monitor.jsonl`，Store.tail 有限读取，按群保留近期 ID 去重。移除保留历史，停用不采集；没有历史补拉、撤回同步或附件抓取。全暂停只限制输出，被动监听继续；停止采集需单群停用或停服务。记录无自动清理，关注磁盘并在停机后归档。

桌面 `group-monitor.js/.css` 与 index 中“群聊监听”页；DesktopApi 固定接口白名单和 groups 窗口偏好；DesktopAssets 加内容指纹。多群标签/并排窗口、滚动不跳底、备注/启停/移除、断线提示与双主题见 docs/GROUP_MONITOR.md。群配置只存在 local.json，记录随 data 快照复制；数据恢复不覆盖当前配置。发布检查额外拒绝默认预填群号/备注。

验证：`tools/smoke-group-monitor.py` 隔离 WebView2 原生桥；`tests/test_group_monitor.py` 验证白名单、按群隔离、重启去重、热保存、暂停只读、消息不进入主人/模型/工作、移除保留、跨域/注入拒绝、窗口偏好。回滚先备份数据与配置，停止本项目核心/界面后换回受信任的发布版本源码或原目录；从私人配置去掉仅新增的 group_monitor 字段（旧版不识别），保留 monitor.jsonl，不删除其他数据或登录态；启动后保持原有暂停。真实 QQ 群接收需使用者扫码并在已加入的测试群验收，夹具不替代实连。

| # | 模块 / 文件 | 调用关系与数据 |
|---|---|---|
| 1 | `src/modules/conversation.py` | Harness → 拆气泡/停顿 → Safety → 通道；UI 在 `src/channel/ui` |
| 2 | `src/modules/memory.py` | Harness 检索、Dispatcher 写入；`people/owner/memory.jsonl`，六类记忆与衰减/删除标记 |
| 3 | `src/modules/role.py`、`src/persona/role.md` | Harness 拼人格提示；`emotion.jsonl` 持续情绪，`persona.jsonl` 审核稳定线 |
| 4 | `src/modules/impression.py` | 轮次后定期刷新；可选 Plugins.load 的 score；`impressions.jsonl` |
| 5 | `src/modules/diary.py` | 模型工具/本机 API/睡眠整合 → append/recent；`diary.jsonl` |
| 6 | `src/modules/music.py`、`tools/music.ps1` | 用户工作台 → Windows SMTC；切歌需额外 allow_control；`music.jsonl` |
| 7 | `src/modules/growth.py` | 工作台设置三权重 → 归一化 → 下一轮模型提示；`growth.jsonl` |
| 8 | `src/modules/learning.py` | 用户来源/闲时计划 → 允许域名获取/搜索 → 多源归档/模型对照；`learning*.jsonl` |
| 9 | `src/modules/qq_bridge.py`、`src/qq_native/` | 本机HTTP/NDJSON → owner/群过滤 → Harness/GroupMonitor；发送经Safety；本机主人文字收发已验收 |
| 10 | `src/modules/devices.py` | 用户本机 API → 单设备 ADB/前台包检查 → 动作；`device_actions/macros` |
| 11 | `src/modules/model.py` | Harness/感官/调度 → 所选 OpenAI 兼容 API 的 Chat Completions；主/辅助模型；usage 入日志 |
| 12 | `src/modules/plugins.py`、`user_plugins/` | 审核后的 Python 打分插件、MCP stdio；本机手动调用，模型无通用高权限口 |

其他组成：`core/harness.py` 是组合根、路由与轮次控制；`core/tools.py` 是模型可见工具清单；`core/safety.py` 负责模式/世代取消/分钟配额/不可撤回动作配额；`core/store.py` 是 JSONL 事实源；`core/instance.py` 是操作系统单实例锁；`modules/awakening.py` 管主动、承诺、睡眠及闲时触发；`modules/senses.py` 管图片/本机语音；`core/stickers.py` 管已观察图片的收藏与发送。

调用必须经组合根注入依赖。不要在插件中反向 import main 创建第二个 Harness，也不要绕过 Safety 直接发 QQ。架构图见 `架构文档.md`。

## 2. 配置清单

默认 `config/settings.json`，覆盖 `config/local.json`，后者不入版本控制。桌面「设置」和 `tools/manage.py set-model` 都写 local.json。保存配置需重启；顶部安全开关立即生效并存 `data/safety.jsonl`，其最新状态优先于默认 safety.mode。

| 配置组 | 字段与用途 |
|---|---|
| server | host 强制 127.0.0.1；port 默认8765；max_body_bytes 请求大小 |
| paths | data/logs/backups，相对项目根；必须互不嵌套，不可指向源码/配置 |
| maintenance | agent_name：任意维护 Agent/人工维护者显示名称，不自动授权或调度 |
| owner | name、qq_id（收消息的使用者，不是机器人登录 QQ） |
| model | provider 为 magpie/openai_compatible；base_url 为对应 Base URL；main/auxiliary 为所选服务的模型 ID；key_env 默认 MAGPIE_API_KEY（自定义可用 HARNESS_API_KEY）；timeout_seconds、models_timeout_seconds、max_response_bytes、max_tokens、temperature、history_messages、max_tool_rounds |
| qq | enabled 默认false；bot_id 预期机器人；client_path 仅作独立QQ文件记录；native_port=3002；reconnect_min/max_seconds；media_hosts/media_timeout_seconds |
| safety | mode paused/reply_only/active；groups_muted；private/group_per_minute；irreversible_interval_seconds/per_day；stop_words |
| conversation | min/max_delay_seconds、night_multiplier、max_bubbles、bubble_chars、max_input_chars、queue_size |
| memory | retrieval_limit、普通/重要半衰期、max_content_chars |
| role | card 角色卡路径；evolution_enabled 默认false |
| diary | daily_limit ≤3、max_chars |
| impression | enabled、plugin（本机插件名）、refresh_hours |
| awakening | enabled、min/max_minutes、idle_minutes、probability、quiet_start/end、sleep_hour、timezone |
| music | enabled、allow_control 单独授权、allowed_sources、max_lyrics_chars |
| growth | work/companion/learning 默认0.2/0.6/0.2；运行时界面改动以 growth.jsonl 最新值优先 |
| learning | enabled、allowed_hosts、search_url（含{query}）、max_page_bytes、max_items_per_day、idle_plans |
| devices | enabled、adb_path、serial、device_kind emulator/spare、allowed_packages、timeout_seconds、max_macro_steps |
| voice | enabled、python 专用环境、whisper_model、model_dir 权重目录、cpu_threads、initial_prompt 人名提示、language、timeout_seconds、tts_command 本机argv、max_audio_bytes |
| plugins | enabled、allowed Python插件名、mcp 服务及精确工具清单；publish_enabled 为未启用的公共发布保留位 |
| stickers | enabled、daily_limit |
| stickers（理解） | recognition_enabled 独立于发送开关；max_image_bytes 默认5MB、max_pixels 默认1600万、preview_edge 默认768、animation_samples 默认3、max_animation_frames 默认300、library_limit 默认100 |
| 聊天自动识图 | stickers.max_images_per_turn 默认3；qq.media_hosts 精确允许QQ图片CDN，qq.media_timeout_seconds 默认15；视觉通过所选 API 的辅助模型 |
| desktop | poll_interval_ms、请求/启动/停止超时、qr_max_age_seconds、window_width/window_height（默认1280×820，最小940×650） |

**密钥在哪里**：Magpie上游在Magpie配置；自定义API密钥在model.key_env指定的环境变量中。配置仅存变量名，日志遮盖该值。自写QQ网关没有凭据配置，不采集QQ登录票据。不要打印全量环境变量。

## 3. 启动、停止、重启

### 程序壳与 v0.4 通用监管入口

程序设置独立在 `channel/ui/desktop/system.js`，配置仍为desktop组：start_with_windows、startup_hidden、auto_start_services、close_to_tray、minimize_to_tray、auto_recover、theme、font_scale，以及supervisor_interval_seconds/max_auto_restarts/restart_window_seconds/maintenance_timeout_seconds。程序开关保存立即生效；自启只登记当前用户HKCU Run，下一次Windows登录执行，不需要管理员权限。默认模板自启关闭，本机开关以界面/注册状态为准。

`core/desktop_platform.py` 管自启、开始菜单/Windows已安装程序登记；绝对路径入口 `tools/desktop-launch.py` 不依赖登录时cwd。`core/desktop_lifecycle.py` 管托盘、隐藏/唤回、退出、窗口边界与限次恢复线程；`core/desktop_maintenance.py` 管快照列表/校验、复用manage.py备份恢复与不含正文的诊断导出。`src/version.py` 是版本号唯一来源。桌面新增pystray/Pillow依赖，锁定在requirements.desktop.lock.txt。

**维护前处理托盘守护**：优先托盘「退出并停止全部」，或使用tools/stop.bat（会写停止意图）。`core/service_intent.py` 跨进程保存 `.runtime/service-intent.json`，显式停机使desired=false，恢复守护不会干扰维护 Agent停机维护；显式启动重新置true。全部暂停只限制行为，服务可以继续监听，但守护绝不解除暂停。恢复只在托盘/窗口进程存活期间运行，5分钟最多3次；网关不自动启动，QQ失效需用户扫码。

窗口X现在默认**收进托盘**；真正退出用Ctrl Q或托盘菜单。`exit_ui`只退出界面/托盘，后台继续；`exit_all`先停本项目核心/QQ再退出。Windows注销/关机放行，托盘不可用不隐藏窗口。`.runtime/window-state.json` 保存窗口位置/尺寸/最大化，越界位置忽略；桌面错误在 `.runtime/desktop-logs/events.jsonl`，运行记录合并显示。

备份入口要求确认，当前忙碌时拒绝。临时停核心、生成快照、重启保持暂停；完成后用户手动恢复。恢复仅允许当前backups下合法快照、先SHA256校验、保留before-restore；恢复完成保持核心停止，需核对QQ去重后手动启动。诊断文件在 `.runtime/diagnostics`，不包含聊天/记忆正文/账号或凭据。操作步骤见 `docs/DESKTOP.md`。

迁移目录后运行 `tools/install-desktop.bat` 更新快捷方式与程序登记，再在程序设置重新保存自启，修复Run旧路径。Windows卸载入口只移除该项目的集成，保留源码/data/登录态；它不是整目录删除器。当前提供未签名Windows绿色EXE包；尚未提供自动升级。源码安装更新仍使用受信任源码+依赖锁文件。

日常使用桌面「QQ ChatBot」或根目录 `QQ ChatBot.vbs`；入口进入独立桌面环境并复用本项目核心。窗口X默认收进托盘，停止全部只停止本项目核心。此版本不会启动或管理QQ进程，不影响个人QQ和Magpie。

桌面文件地图：`src/desktop.py` 为WebView2窗口与单实例入口；`src/channel/ui/desktop/` 为HTML/CSS/JS界面；`src/core/desktop_api.py` 为固定操作白名单桥；`src/core/desktop_backend.py` 负责本机API与服务生命周期。`src/desktop_legacy.py` 保留旧Tk实现供兼容与回归，不是默认入口。桌面不创建第二个Harness。

新机器先安装Python 3.11和Microsoft Edge WebView2 Runtime，运行 `tools/install.bat`，再运行 `tools/install-desktop.bat`。桌面依赖冻结在 `requirements.desktop.lock.txt`，与核心及whisper环境隔离；创建脚本会识别Python Launcher列出的3.11安装。若找不到3.11，先补装再重跑，不要把pythonnet装进3.14核心环境。

桌面状态通过本机API轮询；模型设置仍写统一config/local.json。服务停止后保存暂停，重启聊天后需点「只回复」。顶部暂停按钮独立于耗时的启动/重启操作。重复打开唤回同一窗口，锁在 `.runtime/desktop-webview.lock`。`.runtime/webview-profile` 是窗口缓存，`.runtime/desktop-ui.json` 保存未发送草稿、当前页与通道，均不属于人格记忆。若迁移要保留草稿可单独复制后者；JSONL备份恢复不包含窗口缓存。

桌面静态资源由 `src/core/desktop_assets.py` 提供：响应禁用缓存，CSS/JS地址包含内容指纹，更新后不会继续复用旧样式。不要改回pywebview默认静态文件服务器；该服务器的文件响应曾覆盖禁用缓存标记，导致正式窗口仍显示旧CSS。样式验收使用 `--inspect-appearance` 启动参数（先退出已有界面），检查 `.runtime/desktop-appearance.json` 的 `ok` 和正式能力页截图；详见 `docs/DESKTOP.md`。不需要删除WebView用户目录或登录态。

快捷方式丢失运行 `tools/create-desktop-shortcut.ps1`。二维码读取私有 `.runtime/qq-native/qrcode.png`，仅waiting_qrcode阶段、未过期且有效PNG可显示；启动仍被研发状态阻止。

当前应用图标为本项目自产的「聊天小鱼」形象，设计图稿为 `assets/qq-chatbot-fish-chat-v1.png`，Windows多尺寸图标为 `assets/qq-chatbot-fish-chat-v1.ico`；生成提示词与说明见 `assets/README.md`。程序运行时引用的文件名 `assets/xiaojing-user-icon.png/.ico` 是历史沿用，内容即上述自产图标。旧 `xiaojing-icon.*` 和生成提示词仅为存档，当前程序不再引用。网页图标副本位于 `src/channel/ui/icons` 和 `src/channel/ui/desktop/assets`，更新时同步。变更ICO文件名后运行 `tools/create-desktop-shortcut.ps1`，并重新登记Windows程序图标（`.venv\Scripts\python.exe -m src.desktop --register`）。更新图标无需停QQ/核心；在托盘菜单选“退出界面，后台继续”后重新打开桌面程序即可刷新窗口和托盘，直接点X默认只收进托盘。

以下终端命令留给维护与自动化：

```powershell
# 在当前安装的项目根目录执行
.\tools\install.bat             # 新机或重建虚拟环境时才需要
.\tools\start.bat               # 前台运行，保持窗口打开
```

打开 `http://127.0.0.1:8765`。在另一 PowerShell：

```powershell
# 在当前安装的项目根目录执行
.\tools\health.bat
.\tools\stop.bat
.\tools\start.bat
```

一条命令重启是 `tools\restart.bat`，会先等旧服务完全退出再前台启动。同一 data 目录有文件锁，不可双开。要后台启动可使用下面的固定路径命令；在新窗口运行不会弹出控制台：

```powershell
$projectRoot = (Get-Location).Path
$corePython = Join-Path $projectRoot '.venv\Scripts\python.exe'
Start-Process -FilePath $corePython -ArgumentList '-m','src.main' -WorkingDirectory $projectRoot -WindowStyle Hidden
```

后台服务同样用 stop.bat 停止。不要 kill 全部 Python/QQ 进程。停止会保存“已暂停”，重启后先点击「只回复不主动」或：

```powershell
.\.venv\Scripts\python.exe tools\manage.py reply-only
```

`pause` 全暂停、`reply-only` 只回复、`active` 允许主动。active 还需 awakening.enabled=true 才实际主动。更改 safety.mode 配置不会覆盖持久化保命状态。

当前版本没有QQ进程启动器，不要执行旧启动脚本。只读诊断检查本机3002及qq_connected/qq_online，不证明真实扫码已通过。

## 4. 表情理解与换模型

### 表情包理解窗口

侧栏「表情包理解」进入表情库，点「识别表情包」选择/拖入图片，可补充聊天语境。辅助视觉模型返回画面、可辨文字、可能情绪/意图、接话建议与歧义；界面中修正名称、情绪、含义、接话偏好及标签，再点「确认并记住」。要用于本机聊天，点「放进对话」后再发送。不会因识别自动发QQ消息，也不会自动确认模型猜测。发送失败保留表情附件与文字。

实现地图：`core/sticker_intents.py` 负责校验、动图抽样、去重、含义修订与上下文；`modules/senses.py` 负责视觉结构化分析；`channel/local_ui.py` 的 GET/POST `/api/sticker-intents` 是本机入口；`channel/ui/desktop/stickers.js` 是独立窗口前端。`Harness.media_context` 同时接入本机表情引用与QQ图片。桌面桥对识别采用模型超时+10秒，普通接口保持原超时；全部暂停会取消进行中的识别。

数据在 `data/media/` 原图/预览、`data/media.jsonl` 媒体索引、`data/sticker_analyses.jsonl`（model_inference）与 `data/sticker_meanings.jsonl`（owner_confirmed 修订事件）。都被现有 data 备份覆盖，不需要额外云库。清除含义写tombstone，原图/历史仍可审计。每张图片按原文件SHA256精确复用，重新压缩、裁剪或改字后的图片视为新图，需重识别/确认，不做可能串错意思的模糊复用。表情库只展示最近 library_limit 张，老图片的已确认含义仍可按哈希命中。

新依赖Pillow在核心requirements及锁文件中。部署更新后用 `tools/install.bat` 更新核心依赖，再重启聊天和窗口；QQ登录进程无需重启。PNG/JPEG/WEBP/GIF验证真实解码格式，限制文件大小/像素/动图帧数；动图最多抽样三帧拼图，不能声称理解全部动画。视觉路由需支持图片和结构化JSON，失败时明确提示，不能把失败内容当成确认的含义。表情文字始终当作观察数据，不能绕过安全规则。

聊天中无需预先导入：桌面「图片」选择、输入框粘贴、对话区拖入 → 按发送 → POST `/api/chat` 将附件校验后写入本机队列 → worker自动视觉观察并交给主模型接话。选择图片时不会调用模型，发送失败保留附件；暂停时只记录、不识图或回复。当前每次桌面发送一张图；QQ每轮观察数量由max_images_per_turn控制。

`core/chat_media.py` 负责本机上传、QQ受限CDN取图与观察记录。QQ只接受已有HTTPS图片URL；验证精确域名/公共DNS/大小，拒绝跳转。内置表情仅显示编号，不加载外部JS名称表。未取得像素不能声称看过。

新增 `data/chat_uploads.jsonl` 是本机待观察图片索引，`data/chat_media_results.jsonl` 把message_id与观察关联；原图仍在data/media。全部包含在现有data备份中。观察会随近期聊天历史带入后续轮次，因此可以追问“刚才那张”。QQ新表情的自动理解不代表自动确认成主人习惯，仍可在表情库修正。

### 换模型（不改密钥）

1. 打开桌面「设置」，点「检查连接 / 读取模型」，取得 **真实存在** 的 id。401 时由用户检查所选 API 的鉴权环境变量与权限。连接检查读取当前表单，不改配置或发送聊天；接口不提供清单时可手填模型 ID。可在此保存模型后点击提示条「重启聊天」，也可使用以下维护命令。
2. 记录旧 id，执行：

```powershell
.\.venv\Scripts\python.exe tools\manage.py set-model '实际要换的模型 id'
.\tools\restart.bat
```

3. 另一终端运行 reply-only，刷新界面，核对主模型字段，发送一句简单测试。日志应有 model_usage、she_spoke。
4. 需要换回时对旧 id 重复 set-model + restart。主模型要支持 OpenAI Chat Completions 和标准 tool_calls；视觉辅助要支持 image_url。模型列表存在不代表所有能力都支持，必须实测。

model.provider 选择 magpie 或 openai_compatible；后者可填写 HTTPS Base URL 或本机 HTTP 地址。保存后重启生效；更改环境变量值需完全退出窗口及核心再打开。Magpie 模式仍固定原地址，旧安装无需迁移。所有请求继续通过 model.py，不自动回退。协议、鉴权及手动模型配置见 docs/MODEL_API.md。

Magpie 是可选项，已有安装按 docs/MAGPIE_SETUP.md 的五步教程连接；不要求在 Magpie 的 Agent 列表中注册。非默认本机端口通过自定义兼容 API 填实际地址，不改 Magpie 的配置或登录。设置页两份教程由 desktop/guides.js/.css 展示；原生桥 guide(name) 调 core/guides.py 的固定公开文档白名单，因此核心停止时仍能阅读。浏览器方式 GET /api/guide/{name} 沿用本机安全校验。只返回公开文档和固定插图，不读取私人文件，也不自动保存配置或调用模型。

## 5. 备份（JSONL 复制即可）

**先停机**，避免复制一半的 JSONL/附件。项目数据很小时也不要冒险在线逐文件复制。

```powershell
# 在当前安装的项目根目录执行
.\tools\stop.bat
.\.venv\Scripts\python.exe tools\manage.py validate
.\.venv\Scripts\python.exe tools\manage.py backup
```

backup 打印一个 `backups\YYYYMMDD-HHMMSS-ffffff` 绝对目录。记下这行；文件夹内是 data、config、manifest.json（每个数据文件 SHA256 与 JSONL 行数）。运行中的进程占锁时会拒绝备份。脚本复制全部 data，包括媒体、限流/去重/暂停状态；config 单独保存，不包含程序生成的密钥值。

手工备份：停机后复制完整data（包括JSONL、附件、人设和形象），另存config与源码版本。logs另存供审计。QQ入口原文件和登录态不是data快照的一部分；私有.runtime与外部历史归档不能公开上传。

## 6. 恢复与回滚

用脚本创建的备份可直接恢复：

```powershell
.\tools\stop.bat
.\.venv\Scripts\python.exe tools\manage.py restore 'backups/替换成实际目录名'
.\.venv\Scripts\python.exe tools\manage.py validate
.\tools\start.bat
```

脚本先检查源 JSONL 和 manifest 全部哈希，再暂存并核对，最后移动当前数据到 `backups/before-restore-*`，放入恢复数据。失败不会静默覆盖。恢复不改变当前 config；如需恢复 config，先人工比较备份内的 config/local.json，确认模型 id、路径、QQ 账号仍然正确，再停机复制回 config/local.json。

恢复后先核对长期记忆、日记、成长、去重与配额基线，再由用户手动开启只回复。QQ历史补拉尚未实现；恢复旧快照不能据此宣称已同步新历史。

如果恢复期间 Windows 突然断电：保持停机，检查 `backups/before-restore-*` 和 `data.restore-*`；不要再启动或盲目运行第二次恢复。旧数据保存在 before-restore 目录，可复制到一个新的恢复快照并验证 JSONL后手工替换 data；排除 `.instance.lock`，锁文件内容无业务意义，进程退出锁会由 OS 自动释放。脚本运行时异常有回滚，跨断电移动多个文件不具有数据库级事务保证。

手工复制的备份没有 manifest：停机 → 把当前 data **复制保存到新目录** → 把选定备份完整复制替换 data → validate → start。绝不能把旧 JSONL 追加到现有 JSONL 来“恢复”，会造成重复事件。相对路径/文件夹名称变动后要核对 paths；完整项目换目录时，附件注册中的绝对路径也要迁移（当前只保证同机同目录恢复）。

## 7. 维护 Agent 独立验收路线

1. `health.bat` 查当前状态；记录 model、memory_count、weights、last_spoke。
2. 重启，手动 reply-only，确认页面可开、发送一句能答。
3. 换成清单里另一个支持工具的 id，重启并测试；然后换回。
4. 页面记忆手动写一条明确标记为“验收用”的事实，记下文本。
5. stop → validate → backup，保存打印路径。
6. start → reply-only → 再新增一条“备份后”的临时记忆。
7. stop → restore 第5步路径 → validate → start → reply-only。
8. 第4步记忆还在，第6步新增已消失。媒体附件与日记行数对应 manifest，权重一致。最后删除/标记遗忘验收事实（备份仍会保留副本）。
9. 运行 `tools\test.bat`；保存验收结论到 docs/ACCEPTANCE.md，未连接的外部能力继续标待验收。完成这套流程后才可声明交接验收通过。

## 8. 日志与只读健康检查

```powershell
.\tools\health.bat
Get-Content -LiteralPath '.\logs\events.jsonl' -Tail 30
Get-Content -LiteralPath '.\logs\events.jsonl' -Tail 30 -Wait
```

日志每行JSON含id/ts UTC/level/event。关键事件message_received、she_spoke、qq_connected/disconnected、qq_catchup_unsupported、qq_http_error、qq_action_error、model_error、turn_error、safety_changed。模型错误脱敏；原生不透明错误仅记录固定代码以防包含登录数据。日志私人，不随源码上传。

health 只查 TCP 端口和 GET `/api/status`，不发消息、不唤醒模型、不改 JSONL/状态。返回码 0 代表核心端口和所选 API 主机端口存在，启用 QQ 时还要求 WS+QQ online；不代表已成功做过模型推理或网易云/ADB 可用。last_spoke 为空表示从未成功回复，不是服务必然故障。

## 9. 已知坑与维护规则

- QQ WS 在线不等于 QQ 账号在线；同时看 qq_online。机器人不能登录为主人。打开 qq.bot_id 校验可防错号。
- 当前自写QQ仍需完成客户端加载、真实扫码及账号目录隔离验证；不要复用日常QQ或将下载就绪视为登录成功。
- 尚无原生历史补拉/冷启动UID查询/会话掉线重建；核心HTTP事件流会指数重连，但不等于QQ原生会话自动恢复。主人须先发新私聊，发送失败或未知状态不自动重发。
- 限流是发送前预占，失败/不确定发送也占配额，跨重启保存；打满后可中断地等待。不要删 outbound.jsonl 来“修复慢回复”。
- 空间评论/点赞/加陌生人/群 @全体当前没有动作接口。不可撤回动作通用配额函数至少10分钟/日3条；今后新接口必须使用它并单独人工授权，不能仅靠提示词。
- 硬暂停阻止后续发送；已提交到客户端、系统或远程MCP的动作不可撤回。本机暂停按钮优先，休眠或断网无法保证收到远端消息。
- whisper 首次权重下载/ffmpeg 缺失/Python 3.14 的 torch 支持可能失败，使用单独3.11环境；不自动安装整套 GPU 依赖，不上传音频求第三方转写。
- 网易云必须支持 SMTC；当前没有通用曲库搜索/按歌名点播，歌词/热评需授权来源页面，社区公共上传只保留本地草稿。这些扩展不能写成已经真实验收。
- ADB 只选专用模拟器/备用机。包名检测不是银行 App 的完整清单；不要在允许清单里放浏览器、商店或内置支付能力 App。
- Python 插件和 MCP 进程是可信代码，不能指望主进程规则沙箱它们。仅启用审查过的代码；不把通用 shell、浏览器任意控制或文件写工具交给模型。
- 数据都是明文，适合本机审计；复制即备份也意味着复制可读。环境变量值不入备份；手动遗忘是 tombstone，彻底删除需停机清理原事件与备份。
- JSONL 当前全文件扫描，长期增长会慢。归档/索引优化前备份，保持索引可从 JSONL 重建。不要直接删近期限流/seen 文件。
- 改功能先建分支、跑有意义的测试、记录迁移。公开发布使用 tools/package-release.py，不直接推送含私人历史的工作目录。源码和 requirements.lock.txt 可纳入 Git；data/logs/local配置/运行时/凭据不得入库。

参考配置和外部准备细节见 `docs/QQ_SETUP.md` 与 `docs/FEATURES.md`。新增需求不能以修改人格卡的方式绕过权限结构。

## 10. 公开版本与个人安装隔离

公共角色卡为通用模板，个人卡放在被忽略的 config/persona.local.md 并由 role.card 引用。升级保留 local.json 的称呼、账号、模型和私有人设路径，不覆盖 data。发布排除本地卡、数据、登录态与 Git 历史，附文件哈希 manifest；步骤见 docs/RELEASING.md。详细旧安装验收只在原电脑保存。

清理旧外部桥接后，弃用的 QQ HTTP/WS 地址、鉴权环境变量名和历史补拉参数会在读取本机配置时忽略，并在下次保存时移除。不会更换模型出口或清除聊天、限流、去重。旧安装、日志和备份移到项目外私人归档，新快照重新校验；本机位置见 `.runtime/cleanup-report.json`，不要公开归档。回退时先按本手册停机备份，仅恢复同版本代码和所需配置；不要覆盖当前 data 或自动启动旧组件。当前自写 QQ 尚不能通过 GUI 扫码，真实接入待验收，离线阶段可使用本机聊天。

## 11. 专属人设 soul.md

侧栏「专属人设」读写 role.soul_file（默认 persona/soul.md，相对于 paths.data），完整默认位置 data/persona/soul.md。core/soul.py 负责原子写入、版本冲突与内容历史；modules/role.py 每次构造提示读取文件，所以保存后下一轮生效，不影响已在生成的轮次。空文件只使用基础卡。模型工具没有此文件的写入口，人格演化锁与工具权限不受 soul.md 授权。

GET/POST /api/soul 沿用本机 Host/Origin/写请求头保护；保存必须带 expected_revision，磁盘有新改动时拒绝覆盖。persona/soul_history.jsonl保存可恢复内容版本。大小由 role.soul_max_chars/soul_max_bytes 控制，界面历史条数由 role.soul_history_limit 控制。编辑器脚本为 channel/ui/desktop/soul.js，样式为 soul.css。

旧个人角色卡可导入编辑器后保存；原卡保持不删。若希望只用通用基础卡加 soul.md，将本机 role.card 改为 src/persona/role.md 并重启一次；后续编辑 soul 无需重启。个人 soul 和历史均位于 data，已有备份/恢复自动包含；恢复 data 会同时恢复它们。未保存草稿在 .runtime/desktop-ui.json 的 soul_draft，属于私有窗口数据，不随 data 快照恢复。Git 与发布工具排除实际 soul.md，公共包只含 soul.example.md 模板。

## 12. 昵称、角色形象与程序图标

在「专属人设」顶部填写昵称/形象描述，分别选择形象图和程序图标，最后点「保存角色资料」。选图只是预览，保存后才生效；单项「恢复默认」和「全部恢复默认」也需保存。支持静态 PNG/JPG/WEBP，程序图标另支持 ICO，默认每张上限 2 MB；不裁掉原图内容，图标透明补边。昵称用于界面署名和下一轮模型提示，文字描述进入提示；上传图片本身不调用视觉模型。保存不改变 QQ 账号的服务器资料。

实现：`core/identity.py` 处理资料、版本冲突和 Pillow 图片转换；`Harness.identity` 注入 `modules/role.py`；GET/POST `/api/identity` 提供本机接口，继续使用 Host/Origin/写请求头限制；`channel/ui/desktop/identity.js/.css` 提供编辑器。资料写 `data/persona/identity.jsonl`，图片写 `data/persona/appearance/portrait-<hash>.png`、`icon-<hash>.png/.ico`，不接受用户指定文件路径。文件名由内容生成，旧图片保留以供快照恢复；不要手动删除仍被资料记录引用的文件。

统一配置 `identity` 包含 `default_nickname`、`default_image/default_icon_ico`（公开 assets 内默认文件）、`stream/asset_dir`（相对于 paths.data）和昵称/描述长度、图片字节/像素、缩放边长及 ICO 尺寸限制。个人定制通过界面保存在 data，不修改公开默认值。配置、API与模型均不增加密钥出口。

`desktop_lifecycle.apply_identity` 在保存时及监督周期同步原生窗口、托盘与图标，`desktop_platform` 更新注册表 DisplayIcon，`tools/create-desktop-shortcut.ps1 -IconPath` 更新两个快捷方式；角色编辑不改变 QQ ChatBot 的安装标识、启动项或快捷方式文件名（产品更名迁移见第13节）。旧固定窗口名查找脚本改用 `.runtime/desktop-window.json` 中本程序 PID/HWND，操作前仍需核验。Windows 对已固定的任务栏快捷方式可能保留系统缓存，可取消固定后重新固定。全部 data 备份/恢复已包含资料及 PNG/ICO，恢复后桌面监督周期自动应用；前端下次刷新同步。源码发布一律排除 data，因此不携带自定义昵称、图片和历史。

## 13. QQ ChatBot 更名迁移

`core/product.py` 集中产品显示名和兼容标识。0.8.0 的核心 status.name 为 QQ ChatBot，app_id 保持 dafeiyu-harness；维护工具使用 is_harness，同样识别旧版本的产品名，以便原地升级时停机备份，不绕过非本项目端口的保护。

重新登记桌面后，新建 QQ ChatBot 桌面/开始菜单快捷方式。仅在工作目录、启动参数和 Python 目标均匹配本安装时移除旧入口；同名但属于其他位置的入口不会覆盖。已启用的本安装 Run 项由 DaFeiYuHarness 迁移为 QQChatBot，清除匹配的旧项以免重复启动；未启用时不擅自开启。角色自定义本身不重命名这些入口。

卸载登记键 DaFeiYuHarness、Windows AppUserModelID、旧版监管 schema 与源码 manifest schema 均作为内部兼容标识保留；Windows 显示名称已更新。项目目录和 data 不移动，原地升级不用迁移附件路径。旧本机 `大肥鱼.vbs` 可继续作为兼容入口，公开包只提供新启动器。不要为了消除内部旧字符串去重建账户、删除数据或改监管协议。
