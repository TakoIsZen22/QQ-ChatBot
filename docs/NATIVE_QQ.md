# 自写 QQ 桥接：架构与验收

适用 1.10.01 / 1.10.02；原生宿主首次验证于 2026-10-20。本项目原创宿主嵌入固定官方 QQNT 内核，由官方内核完成网络、二维码登录与消息会话；没有自行实现腾讯网络协议，也没有依赖外部 QQ 桥接程序。客户端内部接口随版本变化，本版本只能加载兼容清单中的文件。

## 模块与调用

| 路径 | 职责 |
|---|---|
| src/qq_native/host.cpp | 原创 Windows x64 宿主，通过固定导出嵌入 QQNT 自带 Node/V8，加载 entry.js |
| config/qq-native-compat.json | QQ/Node/V8 版本、四个关键文件 SHA256、appid/qua、启动与控制超时 |
| src/core/native_host.py | 校验版本/文件/目录，启动自有宿主，按 PID+映像+创建时间+run_id 管理生命周期 |
| src/qq_native/entry.js | 先独占本机端口，再加载 wrapper；脱敏状态、控制文件、会话引用持有 |
| src/qq_native/session.js | 独立路径初始化、扫码/账密账号校验、二维码刷新、会话初始化、掉线状态 |
| src/qq_native/driver.js | 主人和群白名单过滤、群配置热同步，观察主人 UID/群事件，私聊/群纯文字发送、额外硬配额 |
| src/qq_native/protocol.js | 有界事件转换；消息 ID 保持字符串，不暴露媒体本地路径 |
| src/qq_native/gateway.js | 仅 127.0.0.1 HTTP/NDJSON，限制 Host/Origin/本机头/体积/连接数 |
| src/modules/qq_bridge.py | 唯一核心传输；事件流重连/去重、主人路由及独立白名单群监听/可选回复，发送经过 Safety |
| src/core/qq_native.py、tools/qq-native.py | 只读诊断；旧实验入口的 prepare/restore 仅供历史回滚 |
| src/core/onboarding.py、desktop_api.py | 扫码/账密、验证、可选自动登录、刷新、停止，服务操作锁；不自动解除暂停 |

无 npm 运行依赖。网关仅开放 get_status/get_login_info/send_private_msg，事件为 /events NDJSON。qq.native_port 默认 3002，不能公开到公网。本机标头是浏览器访问限制，不是同机恶意程序的安全隔离。

宿主不修改 package.json，不注入日常 QQ，不枚举已保存账号，不调用快速登录。旧实验安装若曾 prepare，先停止自有宿主并执行 restore；原字节和哈希核对后恢复，备份保留。新启动流程不再调用 prepare。

## 固定 ABI 与构建

2026-10-21：版本选择已改为 v2 多版本清单，向导提供本机安装检测与受支持程序文件的独立复制。已实现的宿主 ABI 仍只有一套，已登记版本仍只有 9.9.33-52230，不能据此宣称任意 QQ 版本通用。流程、字段、复制范围及逐版本验收见 [QQ_COMPATIBILITY.md](QQ_COMPATIBILITY.md)。旧 v1 清单继续兼容。

QQNT 9.9.33-52230 自带 Node 24.11.1、V8 14.4.258.16-electron.0。QQNT 导出使用 Chromium libc++ ABI，宿主使用 MSVC；host.cpp 只传递按固定布局构造的借用字符串、空容器和指针，不跨 CRT 释放对象。进程退出释放运行时；不卸载仍持有回调的 DLL。Windows Electron crashpad 支持绑定为空导出，宿主提供对应空绑定。该实现与固定版本绑定，不能只改下载链接就升级。

源码使用者安装 Visual Studio Build Tools 的 C++ x64 工具链及 Windows SDK，然后运行：

```powershell
python tools/build-native-host.py
```

输出 .runtime/native-host/QQChatBot.NativeHost.exe。Windows 发布包构建时编译到 _tools/qq-native，使用者不需要编译器。官方 QQ 不在发布包内，由向导另行下载并校验。

## 私有目录与停止

宿主配置、PID/创建时间、状态、二维码、控制请求均在 .runtime/qq-native。原生引擎全局路径为 profile/global，账号路径为 profile/account，下载为 profile/downloads；宿主 APPDATA/LOCALAPPDATA 指向 profile/os 下的独立目录。没有读取日常 QQ 登录文件。这是路径配置隔离，不是操作系统沙箱，也不代表已审计官方原生库的全部文件访问。

host-output.log 可能包含官方内核输出的敏感登录材料，不能打印、附在 issue 或公开上传。events.jsonl 仅保留时间、级别、阶段和数值错误码；doctor 不读取账号内容。data 快照不含 QQ profile，需要另备份时先停止 QQ，私下复制整个 profile 与本机配置。

```powershell
# 源码方式；绿色包将 Python 换为 .\_runtime\python.exe
.\.venv\Scripts\python.exe tools\qq-native.py doctor
.\.venv\Scripts\python.exe tools\qq-native.py start
.\.venv\Scripts\python.exe tools\qq-native.py refresh
.\.venv\Scripts\python.exe tools\qq-native.py stop
```

启动/刷新/停止必须是用户显式操作。桌面自启及异常恢复只启动聊天核心，不自动登录或重启 QQ。停止只控制本安装的进程；PID 被复用、映像/创建时间不符时拒绝接管。停止超时保留进程与证据，不按进程名批量杀 QQ。

## 状态与排障

| 阶段 | 处理 |
|---|---|
| client_missing / client_layout_invalid | 向导准备固定官方 QQ；保留已有不完整目录，维护者核对后处理 |
| host_missing | Windows 包应自带宿主；源码先运行构建命令 |
| runtime_unverified | 核对固定版本和哈希；旧入口先 restore，不取消校验 |
| waiting_qrcode / qrcode_expired | 用户扫码并手机确认；过期点刷新二维码 |
| account_mismatch | 扫错账号；停止再启动，用已配置机器人号扫码 |
| session_init_failed / unsupported_message_service | 保留脱敏阶段记录，维护者核对固定版本接口；不要清空账号文件 |
| offline | 事件流会重连；原生会话未恢复时手动停止再扫码，不自动重复登录 |
| acceptance_pending / ready | 自有进程消息服务在线；仍须核对本次安装的真实收发 |

旧 state.json、旧二维码或其他程序占用端口不能当成在线。launch_available 只表示组件/版本/账号配置允许用户手动尝试扫码，不是收发验收标志。

### 登录状态同步

QQ 登录状态（原生宿主的 `ready`）与消息通道状态（核心的 `qq_connected && qq_online`）分层显示。二维码窗口、顶部和总览共用核心消息状态；原生已登录但通道未就绪时显示“已登录 · 通道连接中”，核心不可查询时显示“状态待确认”，不能以原生登录成功代替消息通道在线。

核心在扫码前保持 NDJSON 流，收到在线心跳后才读取并验证机器人身份，验证前不路由任何消息。驱动在登录消息服务就绪、掉线、同会话恢复时立即发心跳；15 秒周期心跳仅用于保活兜底。宿主尚未启动时，本机连接拒绝按 `qq.reconnect_min_seconds` 重试，避免已运行的核心在用户手动启动 QQ 后继续等待一分钟。此事件流不会发起登录或重发消息；用户另行勾选的 QQ 账密自动登录由桌面启动入口管理。

桌面状态请求与聊天记录、用量日志、记忆读取独立，状态请求、二维码和向导各自限制并发，避免慢请求拖住顶部刷新。界面刷新间隔仍取 `desktop.poll_interval_ms`（默认 2000ms）；登录完成到顶部同步通常是一个轮询周期加本机调度时间，不承诺网络或内核初始化耗时。

回归：`python -m unittest discover -s tests -p test_qq_status_sync.py`、`node --test tests/qq-native.test.js tests/desktop-status.test.js`。Windows 桌面环境执行 `python tools/smoke-qq-status.py`，独立窗口模拟慢读取、通道就绪/掉线/恢复；不发 QQ、不改配置。它属于界面/协议夹具，真实断网重连仍须另验。

## 能力边界与验收

核心 Safety 保留持久化分钟配额、暂停世代；驱动再限每分钟20条。失败/超时不重试，避免不确定发送被重复。主人 UID 仅从本人新私聊学习，冷启动后先由主人发消息。群默认被动监听；逐群明确允许后，经独立 GroupChat 和 Safety 回复文字。configure_groups 即时同步白名单/回复许可，未同步成功不推理或回复。群发送要求已观察到本群新消息，每群额外最多5条/分钟，失败同样占额，策略同步不清空配额。首次更新须手动重启 QQ 加载新版驱动；群不读取私人资料、不执行工具。结构化 @ 识别与 chatType=2 发送已通过夹具，仍需真实 QQ 群验收。

尚未实现历史补拉、语音附件获取、图片上传发送和群媒体理解。群文字回复实现见 modules/group_chat.py，教程见 GROUP_MONITOR.md。只处理观察到的受支持图片 URL，后续仍须通过核心精确 CDN 与图片校验，真实 QQ 图片另行验收。账号切换及退出会丢弃旧消息回调，不用旧 UID 发消息。

本机已有真实二维码登录及主人文字接收证据；正式宿主、发送、真实断网恢复、白名单群与新机器分别记录在 docs/ACCEPTANCE.md，不能相互替代。授权发送验收必须走正常 Harness/Safety，不直接调用原生发送绕过暂停。

```powershell
node --test tests/qq-native.test.js
python -m unittest tests.test_native_host tests.test_qq_native tests.test_launcher
```

回滚：保持暂停，停止自有宿主和聊天，备份 data/附件/config/local.json；换回可信源码版本。保留 profile、日志、去重与配额，旧版不支持的宿主不要自动拉起。若存在旧 prepare 记录，仅按哈希 restore，不删除审计文件。

## QQ 账密通道

`core/qq_password.py` 负责当前 Windows 用户 DPAPI 缓存；`qq_native/password_login.js` 负责 QQNT `passwordLogin` 分阶段请求、内存验证材料、过期和尝试限流。`core/qq_verification.py` 的独立验证码窗口只有一次提交接口，不注入 DesktopApi。界面共用 `channel/ui/desktop/qq-login.js/.css`，向导与快速 QQ 窗口均可进入。

密码先在 Python 内存转换为 QQ 协议摘要，经仅监听 loopback 的 `/login_control` 发送给本项目宿主。宿主每次启动生成本机 IPC 能力值并保存在私有 host-config.json，仅桌面管理通道使用；常规聊天工具不能访问此通道。验证 URL/票据/协议摘要不写公开 state/events；host-output.log 和 profile 仍须视为私有登录资料。原生报错只映射固定状态，不把厂商错误原文交给界面或日志。

阶段包括 password_authenticating、password_accepted、password_captcha、password_device、password_failed、password_expired。accepted 不是在线：必须收到官方成功回调，并校验机器人身份、初始化消息服务后才能标为 ready。旧验证回调绑定当前 challenge_id；切换、到期或新挑战后拒绝旧结果。无响应请求到期后不叠加新账密请求，要求手动重启宿主。操作和实际验收边界见 QQ_SETUP.md。
