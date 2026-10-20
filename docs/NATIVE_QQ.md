# 自写 QQ 桥接：架构与验收

适用 0.13.0，2026-10-20。本项目原创宿主嵌入固定官方 QQNT 内核，由官方内核完成网络、二维码登录与消息会话；没有自行实现腾讯网络协议，也没有依赖外部 QQ 桥接程序。客户端内部接口随版本变化，本版本只能加载兼容清单中的文件。

## 模块与调用

| 路径 | 职责 |
|---|---|
| src/qq_native/host.cpp | 原创 Windows x64 宿主，通过固定导出嵌入 QQNT 自带 Node/V8，加载 entry.js |
| config/qq-native-compat.json | QQ/Node/V8 版本、四个关键文件 SHA256、appid/qua、启动与控制超时 |
| src/core/native_host.py | 校验版本/文件/目录，启动自有宿主，按 PID+映像+创建时间+run_id 管理生命周期 |
| src/qq_native/entry.js | 先独占本机端口，再加载 wrapper；脱敏状态、控制文件、会话引用持有 |
| src/qq_native/session.js | 独立路径初始化、二维码刷新、扫码账号校验、会话初始化、掉线状态 |
| src/qq_native/driver.js | 主人和群白名单过滤，观察主人 UID，纯文字发送、额外硬配额 |
| src/qq_native/protocol.js | 有界事件转换；消息 ID 保持字符串，不暴露媒体本地路径 |
| src/qq_native/gateway.js | 仅 127.0.0.1 HTTP/NDJSON，限制 Host/Origin/本机头/体积/连接数 |
| src/modules/qq_bridge.py | 唯一核心传输；事件流重连/去重、主人路由及群被动监听，发送经过 Safety |
| src/core/qq_native.py、tools/qq-native.py | 只读诊断；旧实验入口的 prepare/restore 仅供历史回滚 |
| src/core/onboarding.py、desktop_api.py | 手动扫码、刷新、停止，服务操作锁；不自动解除暂停 |

无 npm 运行依赖。网关仅开放 get_status/get_login_info/send_private_msg，事件为 /events NDJSON。qq.native_port 默认 3002，不能公开到公网。本机标头是浏览器访问限制，不是同机恶意程序的安全隔离。

宿主不修改 package.json，不注入日常 QQ，不枚举已保存账号，不调用快速登录。旧实验安装若曾 prepare，先停止自有宿主并执行 restore；原字节和哈希核对后恢复，备份保留。新启动流程不再调用 prepare。

## 固定 ABI 与构建

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

## 能力边界与验收

核心 Safety 保留持久化分钟配额、暂停世代；驱动再限每分钟20条。失败/超时不重试，避免不确定发送被重复。主人 UID 仅从本人新私聊学习，冷启动后先由主人发消息。群只被动监听，不调用模型、工作或群发送；原生群白名单在宿主启动时截取，新增或重新开启群后需手动停止并启动 QQ。

尚未实现历史补拉、语音附件获取、图片上传发送和群回复。只处理观察到的受支持图片 URL，后续仍须通过核心精确 CDN 与图片校验，真实 QQ 图片另行验收。账号切换及退出会丢弃旧消息回调，不用旧 UID 发消息。

本机已有真实二维码登录及主人文字接收证据；正式宿主、发送、真实断网恢复、白名单群与新机器分别记录在 docs/ACCEPTANCE.md，不能相互替代。授权发送验收必须走正常 Harness/Safety，不直接调用原生发送绕过暂停。

```powershell
node --test tests/qq-native.test.js
python -m unittest tests.test_native_host tests.test_qq_native tests.test_launcher
```

回滚：保持暂停，停止自有宿主和聊天，备份 data/附件/config/local.json；换回可信源码版本。保留 profile、日志、去重与配额，旧版不支持的宿主不要自动拉起。若存在旧 prepare 记录，仅按哈希 restore，不删除审计文件。
